"""
==============================================================================
BANCO DE DADOS — CONTAS A RECEBER (DASHBOARD DE GLOSAS)
SQLite (WAL) em dados/dacm_glosas.db — SEPARADO do banco do PF.
Uma conexão por operação; nunca compartilhada.
==============================================================================
"""
import os
import re
import shutil
import time
import urllib.parse
from datetime import datetime

import pandas as pd
import sqlite3

CAMINHO_PADRAO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "dacm_glosas.db")
PASTA_UPLOADS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "uploads_dacm")

STATUS = ["A iniciar recurso", "Em análise", "Glosa Recebida", "Recurso Negado", "Livre de Glosa"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS convenios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT UNIQUE NOT NULL,
  registro_ans TEXT NOT NULL DEFAULT '',
  cnpj TEXT NOT NULL DEFAULT '',
  prazo_recurso_dias INTEGER,
  criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS uploads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  convenio_id INTEGER NOT NULL REFERENCES convenios(id),
  nome_arquivo TEXT NOT NULL,
  num_dacm TEXT NOT NULL DEFAULT '',
  data_emissao TEXT NOT NULL DEFAULT '',
  guias_novas INTEGER NOT NULL DEFAULT 0,
  guias_atualizadas INTEGER NOT NULL DEFAULT 0,
  usuario TEXT NOT NULL,
  criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS guias (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  convenio_id INTEGER NOT NULL REFERENCES convenios(id),
  upload_id INTEGER NOT NULL REFERENCES uploads(id),
  guia_prestador TEXT NOT NULL,
  guia_operadora TEXT NOT NULL DEFAULT '',
  senha TEXT NOT NULL DEFAULT '',
  lote TEXT NOT NULL DEFAULT '',
  protocolo TEXT NOT NULL DEFAULT '',
  data_protocolo TEXT NOT NULL DEFAULT '',
  beneficiario TEXT NOT NULL DEFAULT '',
  nome_social TEXT NOT NULL DEFAULT '',
  carteira TEXT NOT NULL DEFAULT '',
  data_inicio TEXT NOT NULL DEFAULT '',
  data_fim TEXT NOT NULL DEFAULT '',
  cod_situacao_guia TEXT NOT NULL DEFAULT '',
  vl_informado REAL NOT NULL DEFAULT 0,
  vl_processado REAL NOT NULL DEFAULT 0,
  vl_liberado REAL NOT NULL DEFAULT 0,
  vl_glosa REAL NOT NULL DEFAULT 0,
  status_recurso TEXT NOT NULL DEFAULT '',
  vl_recuperado REAL NOT NULL DEFAULT 0,
  observacao TEXT NOT NULL DEFAULT '',
  aviso_glosa_zerada INTEGER NOT NULL DEFAULT 0,
  atualizado_em TEXT NOT NULL,
  UNIQUE(convenio_id, guia_prestador)
);
CREATE INDEX IF NOT EXISTS idx_guias_status ON guias(status_recurso);
CREATE TABLE IF NOT EXISTS itens_guia (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  guia_id INTEGER NOT NULL REFERENCES guias(id),
  data_realizacao TEXT NOT NULL DEFAULT '',
  tabela TEXT NOT NULL DEFAULT '',
  cod_procedimento TEXT NOT NULL DEFAULT '',
  descricao TEXT NOT NULL DEFAULT '',
  grau_participacao TEXT NOT NULL DEFAULT '',
  quantidade REAL NOT NULL DEFAULT 0,
  vl_informado REAL NOT NULL DEFAULT 0,
  vl_processado REAL NOT NULL DEFAULT 0,
  vl_liberado REAL NOT NULL DEFAULT 0,
  vl_glosa REAL NOT NULL DEFAULT 0,
  cod_glosa TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_itens_guia ON itens_guia(guia_id);
CREATE TABLE IF NOT EXISTS recursos_hist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  guia_id INTEGER NOT NULL REFERENCES guias(id),
  status_de TEXT NOT NULL DEFAULT '',
  status_para TEXT NOT NULL,
  vl_recuperado REAL NOT NULL DEFAULT 0,
  observacao TEXT NOT NULL DEFAULT '',
  usuario TEXT NOT NULL DEFAULT '',
  atualizado_em TEXT NOT NULL
);
"""


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


# ==============================================================================
# CONVÊNIOS
# ==============================================================================
def listar_convenios(conn):
    """Convênios ordenados por nome (rows com id, nome, registro_ans, cnpj, prazo)."""
    return conn.execute("SELECT * FROM convenios ORDER BY nome").fetchall()


def criar_ou_obter_convenio(conn, nome, registro_ans="", cnpj=""):
    """Devolve o convênio com este nome; cria se não existir."""
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Informe o nome do convênio.")
    row = conn.execute("SELECT * FROM convenios WHERE nome=?", (nome,)).fetchone()
    if row:
        return dict(row)
    cur = conn.execute(
        "INSERT INTO convenios (nome, registro_ans, cnpj, criado_em) VALUES (?,?,?,?)",
        (nome, registro_ans or "", cnpj or "", datetime.now().isoformat()))
    conn.commit()
    return dict(conn.execute("SELECT * FROM convenios WHERE id=?", (cur.lastrowid,)).fetchone())


def definir_prazo_convenio(conn, convenio_id, dias):
    """Define (ou limpa, com dias=None) o prazo de recurso do convênio."""
    conn.execute("UPDATE convenios SET prazo_recurso_dias=? WHERE id=?",
                 (None if dias is None else int(dias), convenio_id))
    conn.commit()


# ==============================================================================
# IMPORTACAO
# ==============================================================================
_RE_NOME_SEGURO = re.compile(r"^[\w.-]{1,64}$")


def _nome_arquivo_seguro(nome):
    """Nome de arquivo seguro para guardar em uploads_dacm (nunca escapa da pasta)."""
    nome = os.path.basename(nome or "").strip()
    if not nome:
        raise ValueError("Arquivo sem nome válido.")
    if _RE_NOME_SEGURO.match(nome) and ".." not in nome:
        return nome
    # quote() deixa "." intacto — codifica pares ".." para nunca escapar da pasta.
    return urllib.parse.quote(nome, safe="").replace("..", "%2E%2E")[:64]


def _copiar_arquivo_original(caminho):
    """Copia o arquivo do upload para dados/uploads_dacm/ e devolve o nome guardado."""
    os.makedirs(PASTA_UPLOADS, exist_ok=True)
    nome = _nome_arquivo_seguro(os.path.basename(caminho))
    destino = os.path.join(PASTA_UPLOADS, nome)
    if os.path.exists(destino):
        base, ext = os.path.splitext(nome)
        nome = f"{base}_{int(time.time())}{ext}"
        destino = os.path.join(PASTA_UPLOADS, nome)
    shutil.copy2(caminho, destino)
    return nome


def importar_dacm(conn, parsed, convenio_nome, usuario, caminho_arquivo):
    """Importa o DACM parseado. Guias já existentes no convênio (mesma guia do
    prestador) são ATUALIZADAS (status do recurso é preservado); guias novas
    entram com status inicial. O arquivo original é copiado para
    dados/uploads_dacm/. Devolve {novas, atualizadas, avisos_glosa_zerada, upload_id}."""
    metadados = parsed["metadados"]
    nome = (convenio_nome or metadados.get("operadora") or "").strip()
    if not nome:
        raise ValueError("Informe o nome do convênio.")
    convenio = criar_ou_obter_convenio(
        conn, nome, metadados.get("registro_ans", ""), metadados.get("cnpj", ""))
    nome_arquivo = _copiar_arquivo_original(caminho_arquivo)
    agora = datetime.now().isoformat()
    cur = conn.execute(
        "INSERT INTO uploads (convenio_id, nome_arquivo, num_dacm, data_emissao, "
        "usuario, criado_em) VALUES (?, ?, ?, ?, ?, ?)",
        (convenio["id"], nome_arquivo, metadados.get("num_dacm", ""),
         metadados.get("data_emissao", ""), usuario, agora))
    upload_id = cur.lastrowid
    novas = atualizadas = avisos = 0
    for g in parsed["guias"]:
        existente = conn.execute(
            "SELECT * FROM guias WHERE convenio_id=? AND guia_prestador=?",
            (convenio["id"], g["guia_prestador"])).fetchone()
        data_inicio = min((i["data_realizacao"] for i in g["itens"]
                           if i["data_realizacao"]), default="")
        if existente is None:
            status_inicial = "A iniciar recurso" if g["vl_glosa"] > 0 else "Livre de Glosa"
            cur = conn.execute(
                "INSERT INTO guias (convenio_id, upload_id, guia_prestador, guia_operadora, "
                "senha, lote, protocolo, data_protocolo, beneficiario, nome_social, carteira, "
                "data_inicio, data_fim, cod_situacao_guia, vl_informado, vl_processado, "
                "vl_liberado, vl_glosa, status_recurso, atualizado_em) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (convenio["id"], upload_id, g["guia_prestador"], g["guia_operadora"],
                 g["senha"], g["lote"], g["protocolo"], g["data_protocolo"],
                 g["beneficiario"], g["nome_social"], g["carteira"],
                 data_inicio, g["data_fim_fat"], g["cod_situacao_guia"],
                 g["vl_informado"], g["vl_processado"], g["vl_liberado"], g["vl_glosa"],
                 status_inicial, agora))
            guia_id = cur.lastrowid
            conn.execute(
                "INSERT INTO recursos_hist (guia_id, status_de, status_para, usuario, "
                "atualizado_em) VALUES (?, '', ?, ?, ?)",
                (guia_id, status_inicial, usuario, agora))
            novas += 1
        else:
            novo_aviso = 0
            if existente["vl_glosa"] > 0.005 and g["vl_glosa"] == 0:
                novo_aviso = 1
                avisos += 1
            # Com aviso (glosa zerada no reenvio), preserva o valor glosado
            # anterior até a confirmação de 1 clique (confirmar_glosa_recebida).
            vl_glosa_final = existente["vl_glosa"] if novo_aviso else g["vl_glosa"]
            conn.execute(
                "UPDATE guias SET upload_id=?, guia_operadora=?, senha=?, lote=?, protocolo=?, "
                "data_protocolo=?, beneficiario=?, nome_social=?, carteira=?, data_inicio=?, "
                "data_fim=?, cod_situacao_guia=?, vl_informado=?, vl_processado=?, "
                "vl_liberado=?, vl_glosa=?, aviso_glosa_zerada=?, atualizado_em=? WHERE id=?",
                (upload_id, g["guia_operadora"], g["senha"], g["lote"], g["protocolo"],
                 g["data_protocolo"], g["beneficiario"], g["nome_social"], g["carteira"],
                 data_inicio, g["data_fim_fat"], g["cod_situacao_guia"],
                 g["vl_informado"], g["vl_processado"], g["vl_liberado"], vl_glosa_final,
                 novo_aviso, agora, existente["id"]))
            guia_id = existente["id"]
            conn.execute("DELETE FROM itens_guia WHERE guia_id=?", (guia_id,))
            atualizadas += 1
        conn.executemany(
            "INSERT INTO itens_guia (guia_id, data_realizacao, tabela, cod_procedimento, "
            "descricao, grau_participacao, quantidade, vl_informado, vl_processado, "
            "vl_liberado, vl_glosa, cod_glosa) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [(guia_id, i["data_realizacao"], i["tabela"], i["cod_procedimento"],
              i["descricao"], i["grau_participacao"], i["quantidade"],
              i["vl_informado"], i["vl_processado"], i["vl_liberado"], i["vl_glosa"],
              i["cod_glosa"]) for i in g["itens"]])
    conn.execute("UPDATE uploads SET guias_novas=?, guias_atualizadas=? WHERE id=?",
                 (novas, atualizadas, upload_id))
    conn.commit()
    return {"novas": novas, "atualizadas": atualizadas,
            "avisos_glosa_zerada": avisos, "upload_id": upload_id}


# ==============================================================================
# RECURSOS (STATUS)
# ==============================================================================
def registrar_status(conn, guia_id, status_novo, vl_recuperado=None, observacao=None,
                     usuario=""):
    """Muda o status do recurso da guia e registra a mudança em recursos_hist.
    vl_recuperado/observacao None mantêm o valor atual."""
    if status_novo not in STATUS:
        raise ValueError(f"Status inválido: {status_novo}")
    guia = conn.execute("SELECT * FROM guias WHERE id=?", (guia_id,)).fetchone()
    if guia is None:
        raise ValueError("Guia não encontrada.")
    novo_vl = guia["vl_recuperado"] if vl_recuperado is None else float(vl_recuperado)
    nova_obs = guia["observacao"] if observacao is None else str(observacao)
    agora = datetime.now().isoformat()
    conn.execute(
        "UPDATE guias SET status_recurso=?, vl_recuperado=?, observacao=?, "
        "aviso_glosa_zerada=0, atualizado_em=? WHERE id=?",
        (status_novo, novo_vl, nova_obs, agora, guia_id))
    conn.execute(
        "INSERT INTO recursos_hist (guia_id, status_de, status_para, vl_recuperado, "
        "observacao, usuario, atualizado_em) VALUES (?,?,?,?,?,?,?)",
        (guia_id, guia["status_recurso"], status_novo, novo_vl, nova_obs, usuario, agora))
    conn.commit()


def confirmar_glosa_recebida(conn, guia_id, usuario=""):
    """Botão de 1 clique do aviso: status vira 'Glosa Recebida' e o valor
    recuperado assume o valor da glosa (se ainda for 0)."""
    guia = conn.execute("SELECT * FROM guias WHERE id=?", (guia_id,)).fetchone()
    if guia is None:
        raise ValueError("Guia não encontrada.")
    vl = guia["vl_recuperado"] if guia["vl_recuperado"] > 0 else guia["vl_glosa"]
    registrar_status(conn, guia_id, "Glosa Recebida", vl_recuperado=vl, usuario=usuario)
    if guia["aviso_glosa_zerada"]:
        # A glosa zerada no reenvio vira 0 em definitivo: o valor original já
        # foi usado como default de vl_recuperado acima, e reenvios futuros do
        # mesmo arquivo não podem re-disparar o aviso (a condição
        # existente["vl_glosa"] > 0.005 deixa de valer).
        conn.execute("UPDATE guias SET vl_glosa=0 WHERE id=?", (guia_id,))
        conn.commit()


def historico_status(conn, guia_id):
    return conn.execute(
        "SELECT * FROM recursos_hist WHERE guia_id=? ORDER BY id", (guia_id,)).fetchall()


def diff_guias_editadas(antes, depois):
    """Linhas alteradas entre o snapshot e o data_editor: [{guia_id, status,
    vl_recuperado, observacao}] só com o que mudou. Células limpas no editor
    chegam como None/NaN e saem como None (registrar_status mantém o atual)."""
    indices = set(antes["guia_id"]) & set(depois["guia_id"])
    alteradas = []
    for gid in indices:
        a = antes[antes["guia_id"] == gid].iloc[0]
        d = depois[depois["guia_id"] == gid].iloc[0]
        vl_a = 0.0 if pd.isna(a["vl_recuperado"]) else float(a["vl_recuperado"])
        vl_d = 0.0 if pd.isna(d["vl_recuperado"]) else float(d["vl_recuperado"])
        obs_a = "" if pd.isna(a["observacao"]) else str(a["observacao"])
        obs_d = "" if pd.isna(d["observacao"]) else str(d["observacao"])
        if a["status"] != d["status"] or vl_a != vl_d or obs_a != obs_d:
            alteradas.append({
                "guia_id": int(gid), "status": d["status"],
                "vl_recuperado": None if pd.isna(d["vl_recuperado"]) else float(d["vl_recuperado"]),
                "observacao": None if pd.isna(d["observacao"]) else str(d["observacao"])})
    return alteradas


# ==============================================================================
# CONSULTAS DO DASHBOARD
# ==============================================================================
def motivo_glosado(conn, guia_id):
    """Descrição dos itens com glosa da guia: 'DESC [código] · DESC [código]'."""
    itens = conn.execute(
        "SELECT descricao, cod_glosa FROM itens_guia WHERE guia_id=? AND vl_glosa > 0",
        (guia_id,)).fetchall()
    partes = []
    for i in itens:
        if i["cod_glosa"]:
            partes.append(f"{i['descricao']} [{i['cod_glosa']}]")
        else:
            partes.append(i["descricao"])
    return " · ".join(partes)


def guias_filtradas(conn, convenio_id=None, status=None, busca=None, de=None, ate=None,
                    somente_avisos=False):
    """Guias como dicts (inclui guia_id, convenio e motivo glosado)."""
    sql = ("SELECT g.id AS guia_id, g.*, c.nome AS convenio "
           "FROM guias g JOIN convenios c ON c.id = g.convenio_id WHERE 1=1")
    params = []
    if convenio_id:
        sql += " AND g.convenio_id = ?"; params.append(convenio_id)
    if status:
        sql += " AND g.status_recurso = ?"; params.append(status)
    if busca:
        sql += " AND (g.guia_prestador LIKE ? OR g.beneficiario LIKE ?)"
        params += [f"%{busca}%", f"%{busca}%"]
    if de:
        sql += " AND g.data_inicio >= ?"; params.append(de)
    if ate:
        sql += " AND g.data_inicio <= ?"; params.append(ate)
    if somente_avisos:
        sql += " AND g.aviso_glosa_zerada = 1"
    sql += " ORDER BY g.data_inicio DESC, g.guia_prestador"
    linhas = [dict(r) for r in conn.execute(sql, params).fetchall()]
    for linha in linhas:
        linha["motivo"] = motivo_glosado(conn, linha["guia_id"])
    return linhas


def resumo_kpis(conn, convenio_id=None, de=None, ate=None):
    """Totais + taxas para os KPI cards. Valores float."""
    linhas = guias_filtradas(conn, convenio_id=convenio_id, de=de, ate=ate)
    processado = sum(g["vl_processado"] for g in linhas)
    liberado = sum(g["vl_liberado"] for g in linhas)
    glosado = sum(g["vl_glosa"] for g in linhas)
    em_recurso = sum(g["vl_glosa"] for g in linhas
                     if g["status_recurso"] in ("A iniciar recurso", "Em análise"))
    recuperado = sum(g["vl_recuperado"] for g in linhas)
    perda_real = sum(g["vl_glosa"] for g in linhas if g["status_recurso"] == "Recurso Negado")
    return {
        "processado": processado, "liberado": liberado, "glosado": glosado,
        "em_recurso": em_recurso, "recuperado": recuperado, "perda_real": perda_real,
        "taxa_glosa": (glosado / processado * 100) if processado > 0 else 0.0,
        "taxa_recuperacao": (recuperado / glosado * 100) if glosado > 0 else 0.0,
    }


def agrupado_por_convenio(conn, de=None, ate=None):
    """DataFrame por convênio: convenio_id, convenio, processado, liberado, glosado, pct_glosa."""
    sql = ("SELECT c.id AS convenio_id, c.nome AS convenio, "
           "SUM(g.vl_processado) AS processado, SUM(g.vl_liberado) AS liberado, "
           "SUM(g.vl_glosa) AS glosado "
           "FROM guias g JOIN convenios c ON c.id=g.convenio_id WHERE 1=1")
    params = []
    if de:
        sql += " AND g.data_inicio >= ?"; params.append(de)
    if ate:
        sql += " AND g.data_inicio <= ?"; params.append(ate)
    sql += " GROUP BY c.id, c.nome ORDER BY glosado DESC"
    df = pd.read_sql_query(sql, conn, params=params)
    df["pct_glosa"] = df.apply(
        lambda r: r["glosado"] / r["processado"] * 100 if r["processado"] > 0 else 0.0,
        axis=1)
    return df


def evolucao_mensal(conn, convenio_id=None, de=None, ate=None):
    """DataFrame mensal (mes, glosado, recuperado) por mês de data_inicio."""
    sql = ("SELECT substr(g.data_inicio, 1, 7) AS mes, SUM(g.vl_glosa) AS glosado, "
           "SUM(g.vl_recuperado) AS recuperado "
           "FROM guias g WHERE g.data_inicio != ''")
    params = []
    if convenio_id:
        sql += " AND g.convenio_id = ?"; params.append(convenio_id)
    if de:
        sql += " AND g.data_inicio >= ?"; params.append(de)
    if ate:
        sql += " AND g.data_inicio <= ?"; params.append(ate)
    sql += " GROUP BY mes ORDER BY mes"
    return pd.read_sql_query(sql, conn, params=params)


def ranking_motivos(conn, convenio_id=None, de=None, ate=None):
    """Ranking de motivos de glosa (descrição + código), por valor total glosado."""
    sql = ("SELECT i.descricao, i.cod_glosa, SUM(i.vl_glosa) AS total "
           "FROM itens_guia i JOIN guias g ON g.id = i.guia_id "
           "WHERE i.vl_glosa > 0")
    params = []
    if convenio_id:
        sql += " AND g.convenio_id = ?"; params.append(convenio_id)
    if de:
        sql += " AND g.data_inicio >= ?"; params.append(de)
    if ate:
        sql += " AND g.data_inicio <= ?"; params.append(ate)
    sql += " GROUP BY i.descricao, i.cod_glosa ORDER BY total DESC"
    return pd.read_sql_query(sql, conn, params=params)


def alertas_aging(conn, hoje=None):
    """Guias 'A iniciar recurso' estouradas além do prazo do convênio.
    [{convenio, guia, beneficiario, protocolo, dias, prazo, vl_glosa}] por dias desc."""
    hoje = hoje or datetime.now().date()
    linhas = conn.execute(
        "SELECT g.guia_prestador AS guia, g.beneficiario, g.protocolo, "
        "g.data_protocolo, g.vl_glosa, c.nome AS convenio, c.prazo_recurso_dias AS prazo "
        "FROM guias g JOIN convenios c ON c.id=g.convenio_id "
        "WHERE g.status_recurso='A iniciar recurso' AND c.prazo_recurso_dias IS NOT NULL "
        "AND g.data_protocolo != ''").fetchall()
    alertas = []
    for r in linhas:
        try:
            dt = datetime.fromisoformat(r["data_protocolo"]).date()
        except ValueError:
            continue
        dias = (hoje - dt).days
        if dias > r["prazo"]:
            alertas.append({"convenio": r["convenio"], "guia": r["guia"],
                            "beneficiario": r["beneficiario"], "protocolo": r["protocolo"],
                            "dias": dias, "prazo": r["prazo"], "vl_glosa": r["vl_glosa"]})
    return sorted(alertas, key=lambda a: a["dias"], reverse=True)


def avisos_glosa_zerada(conn):
    """Guias com aviso de glosa zerada no reenvio (para o botão de 1 clique)."""
    linhas = [dict(r) for r in conn.execute(
        "SELECT g.*, c.nome AS convenio FROM guias g JOIN convenios c ON c.id=g.convenio_id "
        "WHERE g.aviso_glosa_zerada=1").fetchall()]
    for linha in linhas:
        linha["motivo"] = motivo_glosado(conn, linha["id"])
    return linhas


def listar_uploads(conn, limite=10):
    return conn.execute(
        "SELECT u.*, c.nome AS convenio FROM uploads u JOIN convenios c ON c.id=u.convenio_id "
        "ORDER BY u.id DESC LIMIT ?", (limite,)).fetchall()
