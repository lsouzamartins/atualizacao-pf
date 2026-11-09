"""
==============================================================================
BANCO DE DADOS — ATUALIZAÇÃO PF · NUVEM
SQLite (WAL) em dados/pf.db. Uma conexão por operação; nunca compartilhada.
==============================================================================
"""
import os
import json
import secrets
import hashlib
import sqlite3
from datetime import date, datetime, timedelta

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
  acesso_contas_receber INTEGER NOT NULL DEFAULT 0,
  acesso_glosa INTEGER NOT NULL DEFAULT 0,
  acesso_pediu_chegou INTEGER NOT NULL DEFAULT 0,
  acesso_dacm INTEGER NOT NULL DEFAULT 0,
  acesso_conciliador INTEGER NOT NULL DEFAULT 0,
  acesso_ponto INTEGER NOT NULL DEFAULT 0,
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
CREATE TABLE IF NOT EXISTS sessoes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  login TEXT NOT NULL,
  token_hash TEXT NOT NULL,
  criado_em TEXT NOT NULL,
  expira_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessoes_hash ON sessoes(token_hash);
CREATE TABLE IF NOT EXISTS ponto_uploads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  usuario TEXT NOT NULL,
  dono TEXT,
  nome_arquivo TEXT NOT NULL,
  enviado_em TEXT NOT NULL,
  periodo_de TEXT NOT NULL,
  periodo_ate TEXT NOT NULL,
  linhas INTEGER NOT NULL,
  avisos TEXT
);
CREATE TABLE IF NOT EXISTS ponto_registros (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  upload_id INTEGER REFERENCES ponto_uploads(id),
  dono TEXT NOT NULL,
  data TEXT NOT NULL,
  entrada TEXT,
  saida TEXT,
  tipo TEXT NOT NULL DEFAULT 'trabalho',
  observacao TEXT,
  origem TEXT NOT NULL DEFAULT 'upload',
  atualizado_em TEXT,
  atualizado_por TEXT,
  UNIQUE(dono, data)
);
CREATE INDEX IF NOT EXISTS idx_ponto_data ON ponto_registros(data);
"""

BLOQUEIO_MINUTOS = 5
MAX_FALHAS = 5
DURACAO_SESSAO_DIAS = 7


def conectar(caminho=None):
    caminho = caminho or CAMINHO_PADRAO
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _garantir_coluna(conn, nome):
    """Cria a coluna usuarios.<nome> se o banco for anterior à feature."""
    colunas = [r["name"] for r in conn.execute("PRAGMA table_info(usuarios)").fetchall()]
    if nome not in colunas:
        conn.execute(f"ALTER TABLE usuarios ADD COLUMN {nome} "
                     "INTEGER NOT NULL DEFAULT 0")


def _colunas(conn, tabela):
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({tabela})")]


def _migrar_ponto_por_dono(conn):
    """Separa o ponto por dono (login) em bancos anteriores a 09/11/2026.

    Uploads ganham dono = usuario (quem enviou é o dono do envio). Registros
    são reconstruídos com UNIQUE(dono, data): cada dia vai para o usuário do
    upload que o gravou, ou para quem o editou por último, ou para o primeiro
    admin. Idempotente.
    """
    if "dono" not in _colunas(conn, "ponto_uploads"):
        conn.execute("ALTER TABLE ponto_uploads ADD COLUMN dono TEXT")
        conn.execute("UPDATE ponto_uploads SET dono = usuario")
    if "dono" in _colunas(conn, "ponto_registros"):
        return
    conn.execute("""CREATE TABLE ponto_registros_nova (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        upload_id INTEGER REFERENCES ponto_uploads(id),
        dono TEXT NOT NULL,
        data TEXT NOT NULL,
        entrada TEXT,
        saida TEXT,
        tipo TEXT NOT NULL DEFAULT 'trabalho',
        observacao TEXT,
        origem TEXT NOT NULL DEFAULT 'upload',
        atualizado_em TEXT,
        atualizado_por TEXT,
        UNIQUE(dono, data))""")
    conn.execute("""
        INSERT INTO ponto_registros_nova
            (id, upload_id, dono, data, entrada, saida, tipo, observacao,
             origem, atualizado_em, atualizado_por)
        SELECT r.id, r.upload_id,
               COALESCE((SELECT u.usuario FROM ponto_uploads u
                         WHERE u.id = r.upload_id),
                        NULLIF(r.atualizado_por, ''),
                        (SELECT login FROM usuarios WHERE admin = 1
                         ORDER BY id LIMIT 1),
                        (SELECT login FROM usuarios ORDER BY id LIMIT 1),
                        'lsmartins'),
               r.data, r.entrada, r.saida, r.tipo, r.observacao, r.origem,
               r.atualizado_em, r.atualizado_por
        FROM ponto_registros r""")
    conn.execute("DROP TABLE ponto_registros")
    conn.execute("ALTER TABLE ponto_registros_nova RENAME TO ponto_registros")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ponto_data "
                 "ON ponto_registros(data)")


def inicializar_banco(conn):
    conn.executescript(SCHEMA)
    for coluna in ("acesso_contas_receber", "acesso_glosa", "acesso_pediu_chegou",
                   "acesso_dacm", "acesso_conciliador", "acesso_ponto"):
        _garantir_coluna(conn, coluna)
    _migrar_ponto_por_dono(conn)
    conn.commit()


def _hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def definir_senha(conn, login, senha):
    """Troca a senha do próprio usuário (via auth.trocar_senha): re-hash
    bcrypt. False se a senha for curta ou o login não existir. Diferente de
    redefinir_senha (uso administrativo), NÃO mexe em falhas/bloqueio."""
    if len(senha) < 8:
        return False
    row = conn.execute("SELECT id FROM usuarios WHERE login=?", (login,)).fetchone()
    if row is None:
        return False
    conn.execute("UPDATE usuarios SET senha_hash=? WHERE id=?",
                 (_hash_senha(senha), row["id"]))
    conn.commit()
    return True


def criar_usuario(conn, login, nome, senha, admin=False):
    login = login.strip()
    nome = nome.strip()
    if not login or not nome:
        raise ValueError("Login e nome são obrigatórios.")
    if len(senha) < 8:
        raise ValueError("A senha deve ter pelo menos 8 caracteres.")
    cur = conn.execute(
        "INSERT INTO usuarios (login, nome, senha_hash, admin, criado_em) "
        "VALUES (?, ?, ?, ?, ?)",
        (login, nome, _hash_senha(senha), int(admin), datetime.now().isoformat()))
    conn.commit()
    return cur.lastrowid


def listar_usuarios(conn):
    """Usuários ordenados por login (linhas sqlite3.Row com id, login, nome,
    admin e as marcas de acesso das plataformas)."""
    return conn.execute(
        "SELECT id, login, nome, admin, acesso_contas_receber, acesso_glosa, "
        "acesso_pediu_chegou, acesso_dacm, acesso_conciliador, acesso_ponto "
        "FROM usuarios ORDER BY login").fetchall()


def definir_acesso_contas_receber(conn, login, valor):
    """Liga/desliga o acesso ao sistema Contas a Receber para o usuário."""
    conn.execute("UPDATE usuarios SET acesso_contas_receber=? WHERE login=?",
                 (1 if valor else 0, login))
    conn.commit()


def definir_acesso_glosa(conn, login, valor):
    """Liga/desliga o card do Recursos de Glosa no portal para o usuário."""
    conn.execute("UPDATE usuarios SET acesso_glosa=? WHERE login=?",
                 (1 if valor else 0, login))
    conn.commit()


def definir_acesso_pediu_chegou(conn, login, valor):
    """Liga/desliga o card do Pediu Chegou no portal para o usuário."""
    conn.execute("UPDATE usuarios SET acesso_pediu_chegou=? WHERE login=?",
                 (1 if valor else 0, login))


def definir_acesso_dacm(conn, login, valor):
    """Liga/desliga a marca do DACM × FATURAMENTO para o usuário (12/10: a
    marca fica guardada no portal; o app tem login próprio por CPF)."""
    conn.execute("UPDATE usuarios SET acesso_dacm=? WHERE login=?",
                 (1 if valor else 0, login))
    conn.commit()


def definir_acesso_conciliador(conn, login, valor):
    """Liga/desliga a marca do Conciliador de Convênios para o usuário (12/10:
    a marca fica guardada no portal; o app tem login próprio por CPF)."""
    conn.execute("UPDATE usuarios SET acesso_conciliador=? WHERE login=?",
                 (1 if valor else 0, login))
    conn.commit()


def definir_acesso_ponto(conn, login, valor):
    """Liga/desliga o acesso ao Controle de Ponto no portal."""
    conn.execute("UPDATE usuarios SET acesso_ponto=? WHERE login=?",
                 (1 if valor else 0, login))
    conn.commit()


def login_existe(conn, login):
    """True se já existe usuário com este login (usado pelo avatar no login)."""
    return conn.execute(
        "SELECT 1 FROM usuarios WHERE login=?", (login.strip(),)).fetchone() is not None


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


def redefinir_senha(conn, login_alvo, nova_senha):
    """Redefine a senha de um usuário (uso administrativo): re-hash bcrypt e
    zera falhas_seguidas/bloqueado_ate do alvo. Devolve dict de resultado."""
    if len(nova_senha) < 8:
        return {"ok": False, "erro": "A senha deve ter no mínimo 8 caracteres."}
    row = conn.execute("SELECT id FROM usuarios WHERE login=?", (login_alvo,)).fetchone()
    if row is None:
        return {"ok": False, "erro": "Usuário não encontrado."}
    conn.execute(
        "UPDATE usuarios SET senha_hash=?, falhas_seguidas=0, bloqueado_ate=NULL "
        "WHERE id=?", (_hash_senha(nova_senha), row["id"]))
    conn.commit()
    return {"ok": True}


def remover_usuario(conn, login_alvo, login_operador):
    """Remove um usuário com as guardas da spec 3.4: não remove o próprio
    admin nem o último administrador. Devolve dict de resultado."""
    alvo = conn.execute("SELECT * FROM usuarios WHERE login=?", (login_alvo,)).fetchone()
    if alvo is None:
        return {"ok": False, "erro": "Usuário não encontrado."}
    operador = conn.execute("SELECT * FROM usuarios WHERE login=?",
                            (login_operador,)).fetchone()
    if login_alvo == login_operador and operador is not None and operador["admin"]:
        return {"ok": False, "erro": "Você não pode remover o seu próprio usuário."}
    if alvo["admin"]:
        total_admins = conn.execute(
            "SELECT COUNT(*) FROM usuarios WHERE admin=1").fetchone()[0]
        if total_admins <= 1:
            return {"ok": False, "erro": "Não é possível remover o último administrador."}
    conn.execute("DELETE FROM usuarios WHERE id=?", (alvo["id"],))
    conn.commit()
    return {"ok": True}


# ==============================================================================
# SESSÕES "MANTER CONECTADO" (7 dias)
# ==============================================================================
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def criar_sessao(conn, login, agora=None):
    """Cria uma sessão "manter conectado" (7 dias) e devolve o token — que
    aparece só aqui; no banco fica apenas o hash. Também limpa expiradas."""
    limpar_sessoes_expiradas(conn, agora)
    agora = datetime.fromisoformat(agora) if agora else datetime.now()
    token = secrets.token_urlsafe(32)
    expira = agora + timedelta(days=DURACAO_SESSAO_DIAS)
    conn.execute(
        "INSERT INTO sessoes (login, token_hash, criado_em, expira_em) VALUES (?, ?, ?, ?)",
        (login, _hash_token(token), agora.isoformat(), expira.isoformat()))
    conn.commit()
    return token


def validar_token_sessao(conn, token, agora=None):
    """Devolve o dict do usuário da sessão do token; None se inválida ou
    expirada (sessões expiradas são apagadas)."""
    agora = datetime.fromisoformat(agora) if agora else datetime.now()
    row = conn.execute(
        "SELECT * FROM sessoes WHERE token_hash=?", (_hash_token(token),)).fetchone()
    if row is None:
        return None
    if datetime.fromisoformat(row["expira_em"]) <= agora:
        conn.execute("DELETE FROM sessoes WHERE id=?", (row["id"],))
        conn.commit()
        return None
    usuario = conn.execute(
        "SELECT * FROM usuarios WHERE login=?", (row["login"],)).fetchone()
    return dict(usuario) if usuario is not None else None


def remover_sessao(conn, token):
    """Apaga a sessão do token (botão 'Sair')."""
    conn.execute("DELETE FROM sessoes WHERE token_hash=?", (_hash_token(token),))
    conn.commit()


def limpar_sessoes_expiradas(conn, agora=None):
    agora = datetime.fromisoformat(agora) if agora else datetime.now()
    conn.execute("DELETE FROM sessoes WHERE expira_em <= ?", (agora.isoformat(),))
    conn.commit()


def iniciar_execucao(conn, usuario, agora=None):
    """Grava o INÍCIO de uma execução (status 'em_andamento') e devolve o id.
    Antes, a execução só era gravada no fim — se o processo morresse no meio,
    nada ficava registrado."""
    agora = datetime.fromisoformat(agora) if agora else datetime.now()
    cur = conn.execute(
        "INSERT INTO execucoes (usuario, inicio, fim, status, mensagem, arquivos_gerados) "
        "VALUES (?, ?, NULL, 'em_andamento', NULL, NULL)",
        (usuario, agora.isoformat()))
    conn.commit()
    return cur.lastrowid


def finalizar_execucao(conn, execucao_id, status, mensagem, arquivos, agora=None):
    """Fecha a execução: grava fim, status, mensagem e arquivos gerados.
    Devolve o nº de linhas alteradas (0 se o id não existir)."""
    agora = datetime.fromisoformat(agora) if agora else datetime.now()
    cur = conn.execute(
        "UPDATE execucoes SET fim=?, status=?, mensagem=?, arquivos_gerados=? WHERE id=?",
        (agora.isoformat(), status, mensagem, json.dumps(arquivos), execucao_id))
    conn.commit()
    return cur.rowcount


def listar_execucoes(conn, limite=50):
    """Execuções mais recentes primeiro (id, usuario, inicio, fim, status,
    mensagem, arquivos_gerados)."""
    return conn.execute(
        "SELECT id, usuario, inicio, fim, status, mensagem, arquivos_gerados "
        "FROM execucoes ORDER BY id DESC LIMIT ?", (limite,)).fetchall()


def registrar_execucao(conn, usuario, status, mensagem, arquivos):
    eid = iniciar_execucao(conn, usuario)
    finalizar_execucao(conn, eid, status, mensagem, arquivos)
    return eid


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


def concluir_sucesso(conn, execucao_id, arquivos, df):
    """Fecha a execução como sucesso e grava os resumos diários. Chamar com a
    conexão AINDA ABERTA — nunca depois de conn.close() (bug da execução 20:
    o registro ficava 'em_andamento' para sempre)."""
    finalizar_execucao(conn, execucao_id, "sucesso", "", arquivos)
    gravar_resumos(conn, execucao_id, df)


def resumos_disponiveis(conn):
    return [r["data"] for r in conn.execute(
        "SELECT DISTINCT data FROM resumos_diarios ORDER BY data DESC")]


def convenios_disponiveis(conn):
    """Convênios distintos já registrados, em ordem alfabética."""
    return [r["convenio"] for r in conn.execute(
        "SELECT DISTINCT convenio FROM resumos_diarios ORDER BY convenio")]


def arquivos_da_execucao(conn, execucao_id):
    """Lista de arquivos gravados para uma execução (JSON de arquivos_gerados)."""
    row = conn.execute(
        "SELECT arquivos_gerados FROM execucoes WHERE id=?", (execucao_id,)).fetchone()
    if row is None or not row["arquivos_gerados"]:
        return []
    try:
        return json.loads(row["arquivos_gerados"])
    except (ValueError, TypeError):
        return []


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
    """Linhas de resumos_diarios unidas às execuções, no período [de, ate]
    (datas no formato 'YYYY-MM-DD'). convenio opcional: filtra por igualdade
    exata do nome do convênio (SQL parametrizado).

    Cada reprocessamento grava de novo os resumos dos mesmos dias — para
    cada data vale a execução MAIS RECENTE que a gravou (posição atual do
    dia), como na página Resumo do dia; sem linhas repetidas."""
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
    sql += (" AND r.execucao_id = (SELECT MAX(r2.execucao_id) FROM resumos_diarios r2 "
            "WHERE r2.data = r.data)")
    sql += " ORDER BY r.data DESC, e.id DESC"
    return pd.read_sql_query(sql, conn, params=params)


# ==============================================================================
# CONTROLE DE PONTO — uploads e registros diários
# ==============================================================================
def salvar_importacao_ponto(conn, usuario, nome_arquivo, registros,
                            periodo_de, periodo_ate, avisos,
                            sobrescrever_manuais=False, agora=None, dono=None):
    """Grava o upload e os dias em uma transação; devolve o id do upload.

    `usuario` é quem envia; `dono` é o login dono do ponto (padrão: o próprio
    remetente — o admin pode importar para outra pessoa). Preserva os
    registros com origem 'manual' do MESMO dono, salvo
    sobrescrever_manuais=True. Datas fora do arquivo não são tocadas.
    """
    dono = dono or usuario
    agora = agora or datetime.now().isoformat()
    periodo_de = periodo_de.isoformat() if hasattr(periodo_de, "isoformat") else str(periodo_de)
    periodo_ate = periodo_ate.isoformat() if hasattr(periodo_ate, "isoformat") else str(periodo_ate)
    with conn:
        cursor = conn.execute(
            "INSERT INTO ponto_uploads (usuario, dono, nome_arquivo, "
            "enviado_em, periodo_de, periodo_ate, linhas, avisos) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (usuario, dono, nome_arquivo, agora, periodo_de, periodo_ate,
             len(registros), json.dumps(avisos, ensure_ascii=False)))
        upload_id = cursor.lastrowid
        for registro in registros:
            data = registro["data"]
            data_iso = data.isoformat() if hasattr(data, "isoformat") else str(data)
            existente = conn.execute(
                "SELECT origem FROM ponto_registros WHERE dono=? AND data=?",
                (dono, data_iso)).fetchone()
            if (existente is not None and existente["origem"] == "manual"
                    and not sobrescrever_manuais):
                continue
            conn.execute(
                "INSERT INTO ponto_registros (upload_id, dono, data, entrada, "
                "saida, tipo, observacao, origem) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'upload') "
                "ON CONFLICT(dono, data) DO UPDATE SET "
                "upload_id=excluded.upload_id, entrada=excluded.entrada, "
                "saida=excluded.saida, tipo=excluded.tipo, "
                "observacao=excluded.observacao, origem='upload', "
                "atualizado_em=NULL, atualizado_por=NULL",
                (upload_id, dono, data_iso, registro.get("entrada"),
                 registro.get("saida"), registro.get("tipo", "trabalho"),
                 registro.get("observacao")))
    return upload_id


def salvar_registro_manual(conn, data, entrada, saida, tipo, observacao,
                           usuario, agora=None, dono=None):
    """Cria/atualiza um dia com origem 'manual' do dono (padrão: o autor)."""
    dono = dono or usuario
    agora = agora or datetime.now().isoformat()
    data_iso = data.isoformat() if hasattr(data, "isoformat") else str(data)
    conn.execute(
        "INSERT INTO ponto_registros (upload_id, dono, data, entrada, saida, "
        "tipo, observacao, origem, atualizado_em, atualizado_por) "
        "VALUES (NULL, ?, ?, ?, ?, ?, ?, 'manual', ?, ?) "
        "ON CONFLICT(dono, data) DO UPDATE SET "
        "upload_id=NULL, entrada=excluded.entrada, saida=excluded.saida, "
        "tipo=excluded.tipo, observacao=excluded.observacao, origem='manual', "
        "atualizado_em=excluded.atualizado_em, "
        "atualizado_por=excluded.atualizado_por",
        (dono, data_iso, entrada, saida, tipo, observacao, agora, usuario))
    conn.commit()


def excluir_registro_ponto(conn, dono, data):
    """Remove o dia do dono; devolve o número de linhas apagadas."""
    data_iso = data.isoformat() if hasattr(data, "isoformat") else str(data)
    cursor = conn.execute(
        "DELETE FROM ponto_registros WHERE dono=? AND data=?", (dono, data_iso))
    conn.commit()
    return cursor.rowcount


def ultimo_upload_ponto(conn, dono=None):
    """Última linha de ponto_uploads do dono (ou None). dono=None vê todos."""
    if dono is None:
        return conn.execute(
            "SELECT * FROM ponto_uploads ORDER BY id DESC LIMIT 1").fetchone()
    return conn.execute(
        "SELECT * FROM ponto_uploads WHERE dono=? ORDER BY id DESC LIMIT 1",
        (dono,)).fetchone()


def listar_uploads_ponto(conn, dono=None, limite=20):
    """Uploads mais recentes primeiro; dono=None lista todos."""
    if dono is None:
        return conn.execute(
            "SELECT * FROM ponto_uploads ORDER BY id DESC LIMIT ?",
            (limite,)).fetchall()
    return conn.execute(
        "SELECT * FROM ponto_uploads WHERE dono=? ORDER BY id DESC LIMIT ?",
        (dono, limite)).fetchall()


def registros_ponto(conn, dono=None):
    """Dias do dono (ou todos, com dono=None), em ordem de data."""
    sql = ("SELECT dono, data, entrada, saida, tipo, observacao, origem, "
           "atualizado_em, atualizado_por FROM ponto_registros")
    parametros = ()
    if dono is not None:
        sql += " WHERE dono=?"
        parametros = (dono,)
    sql += " ORDER BY data"
    linhas = conn.execute(sql, parametros).fetchall()
    return [{
        "dono": linha["dono"],
        "data": date.fromisoformat(linha["data"]),
        "entrada": linha["entrada"],
        "saida": linha["saida"],
        "tipo": linha["tipo"],
        "observacao": linha["observacao"],
        "origem": linha["origem"],
        "atualizado_em": linha["atualizado_em"],
        "atualizado_por": linha["atualizado_por"],
    } for linha in linhas]


def backup_banco(caminho, destino):
    origem = sqlite3.connect(caminho)
    alvo = sqlite3.connect(destino)
    with alvo:
        origem.backup(alvo)
    alvo.close(); origem.close()
