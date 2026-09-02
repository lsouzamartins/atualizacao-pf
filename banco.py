"""
==============================================================================
BANCO DE DADOS — ATUALIZAÇÃO PF · NUVEM
SQLite (WAL) em dados/pf.db. Uma conexão por operação; nunca compartilhada.
==============================================================================
"""
import os
import json
import sqlite3
from datetime import datetime, timedelta

import bcrypt
import pandas as pd

CAMINHO_PADRAO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "pf.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  login TEXT UNIQUE NOT NULL,
  nome TEXT NOT NULL,
  senha_hash TEXT NOT NULL,
  admin INTEGER NOT NULL DEFAULT 0,
  falhas_seguidas INTEGER NOT NULL DEFAULT 0,
  bloqueado_ate TEXT,
  criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS execucoes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  usuario TEXT NOT NULL,
  inicio TEXT NOT NULL,
  fim TEXT,
  status TEXT NOT NULL,
  mensagem TEXT,
  arquivos_gerados TEXT
);
CREATE TABLE IF NOT EXISTS resumos_diarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  execucao_id INTEGER NOT NULL REFERENCES execucoes(id),
  data TEXT NOT NULL,
  convenio TEXT NOT NULL,
  vlr_bruto REAL NOT NULL DEFAULT 0,
  vlr_liquido REAL NOT NULL DEFAULT 0,
  quitado REAL NOT NULL DEFAULT 0,
  nao_identificado REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_resumos_data ON resumos_diarios(data);
"""

BLOQUEIO_MINUTOS = 5
MAX_FALHAS = 5


def conectar(caminho=None):
    caminho = caminho or CAMINHO_PADRAO
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def inicializar_banco(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def _hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def criar_usuario(conn, login, nome, senha, admin=False):
    if len(senha) < 8:
        raise ValueError("A senha deve ter pelo menos 8 caracteres.")
    cur = conn.execute(
        "INSERT INTO usuarios (login, nome, senha_hash, admin, criado_em) "
        "VALUES (?, ?, ?, ?, ?)",
        (login, nome, _hash_senha(senha), int(admin), datetime.now().isoformat()))
    conn.commit()
    return cur.lastrowid


def autenticar(conn, login, senha, agora=None):
    """Autentica e devolve dict do usuário; None se login/senha inválidos."""
    agora = datetime.fromisoformat(agora) if agora else datetime.now()
    row = conn.execute("SELECT * FROM usuarios WHERE login=?", (login,)).fetchone()
    if row is None:
        return None
    if row["bloqueado_ate"] and datetime.fromisoformat(row["bloqueado_ate"]) > agora:
        return None
    if not bcrypt.checkpw(senha.encode("utf-8"), row["senha_hash"].encode("utf-8")):
        return None
    conn.execute("UPDATE usuarios SET falhas_seguidas=0, bloqueado_ate=NULL WHERE id=?",
                 (row["id"],))
    conn.commit()
    row = conn.execute("SELECT * FROM usuarios WHERE id=?", (row["id"],)).fetchone()
    return dict(row)


def registrar_falha(conn, login, agora=None):
    agora = datetime.fromisoformat(agora) if agora else datetime.now()
    row = conn.execute("SELECT * FROM usuarios WHERE login=?", (login,)).fetchone()
    if row is None:
        return
    falhas = row["falhas_seguidas"] + 1
    bloqueio = (agora + timedelta(minutes=BLOQUEIO_MINUTOS)).isoformat() \
        if falhas >= MAX_FALHAS else None
    conn.execute(
        "UPDATE usuarios SET falhas_seguidas=?, bloqueado_ate=? WHERE id=?",
        (falhas, bloqueio, row["id"]))
    conn.commit()


def pode_tentar(conn, login, agora=None):
    """(pode_tentar, falhas_restantes) — considera bloqueio ativo."""
    agora = datetime.fromisoformat(agora) if agora else datetime.now()
    row = conn.execute("SELECT * FROM usuarios WHERE login=?", (login,)).fetchone()
    if row is None:
        return True, MAX_FALHAS
    if row["bloqueado_ate"] and datetime.fromisoformat(row["bloqueado_ate"]) > agora:
        return False, 0
    return True, max(MAX_FALHAS - row["falhas_seguidas"], 1)


def registrar_execucao(conn, usuario, status, mensagem, arquivos):
    cur = conn.execute(
        "INSERT INTO execucoes (usuario, inicio, fim, status, mensagem, arquivos_gerados) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (usuario, datetime.now().isoformat(), datetime.now().isoformat(),
         status, mensagem, json.dumps(arquivos)))
    conn.commit()
    return cur.lastrowid


def gravar_resumos(conn, execucao_id, df):
    linhas = [
        (execucao_id, str(r["data"]), str(r["convenio"]),
         float(r["vlr_bruto"]), float(r["vlr_liquido"]),
         float(r["quitado"]), float(r["nao_identificado"]))
        for _, r in df.iterrows()
    ]
    conn.executemany(
        "INSERT INTO resumos_diarios (execucao_id, data, convenio, vlr_bruto, "
        "vlr_liquido, quitado, nao_identificado) VALUES (?, ?, ?, ?, ?, ?, ?)", linhas)
    conn.commit()
    return len(linhas)


def resumos_disponiveis(conn):
    return [r["data"] for r in conn.execute(
        "SELECT DISTINCT data FROM resumos_diarios ORDER BY data DESC")]


def resumos_do_dia(conn, data):
    """Valores por convênio da execução MAIS RECENTE do dia informado."""
    ultima = conn.execute(
        "SELECT MAX(execucao_id) FROM resumos_diarios WHERE data=?", (data,)).fetchone()[0]
    if ultima is None:
        return pd.DataFrame(columns=["convenio", "vlr_bruto", "vlr_liquido",
                                     "quitado", "nao_identificado"])
    return pd.read_sql_query(
        "SELECT convenio, SUM(vlr_bruto) AS vlr_bruto, SUM(vlr_liquido) AS vlr_liquido, "
        "SUM(quitado) AS quitado, SUM(nao_identificado) AS nao_identificado "
        "FROM resumos_diarios WHERE data=? AND execucao_id=? GROUP BY convenio",
        conn, params=(data, ultima))


def historico(conn, de=None, ate=None, convenio=None):
    sql = ("SELECT e.id AS execucao_id, e.usuario, e.status, r.data, r.convenio, "
           "r.vlr_bruto, r.vlr_liquido, r.quitado, r.nao_identificado "
           "FROM resumos_diarios r JOIN execucoes e ON e.id = r.execucao_id WHERE 1=1")
    params = []
    if de:
        sql += " AND r.data >= ?"; params.append(de)
    if ate:
        sql += " AND r.data <= ?"; params.append(ate)
    if convenio:
        sql += " AND r.convenio = ?"; params.append(convenio)
    sql += " ORDER BY r.data DESC, e.id DESC"
    return pd.read_sql_query(sql, conn, params=params)


def backup_banco(caminho, destino):
    origem = sqlite3.connect(caminho)
    alvo = sqlite3.connect(destino)
    with alvo:
        origem.backup(alvo)
    alvo.close(); origem.close()
