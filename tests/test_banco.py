import sqlite3

import pytest
import pandas as pd
import banco

def test_inicializa_e_cria_usuario(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db)
    banco.inicializar_banco(conn)
    uid = banco.criar_usuario(conn, "leonardo", "Leonardo", "senha12345", admin=True)
    row = conn.execute("SELECT login, admin FROM usuarios WHERE id=?", (uid,)).fetchone()
    # comparação por nome de coluna (e não == tuple): sqlite3.Row deixou de ser tupla no Python 3.14
    assert row["login"] == "leonardo" and row["admin"] == 1
    # senha nunca em claro
    hash_ = conn.execute("SELECT senha_hash FROM usuarios WHERE id=?", (uid,)).fetchone()[0]
    assert hash_ != "senha12345" and hash_.startswith("$2")
    conn.close()

def test_autentica_e_bloqueia(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    banco.criar_usuario(conn, "leo", "Leo", "senha12345")
    assert banco.autenticar(conn, "leo", "senha12345")["login"] == "leo"
    assert banco.autenticar(conn, "leo", "errada") is None
    agora = "2026-09-01T10:00:00"
    for _ in range(5):
        banco.registrar_falha(conn, "leo", agora=agora)
    ok, _ = banco.pode_tentar(conn, "leo", agora=agora)
    assert ok is False
    ok2, _ = banco.pode_tentar(conn, "leo", agora="2026-09-01T10:06:00")
    assert ok2 is True
    conn.close()

def test_registra_execucao_e_resumos(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    eid = banco.registrar_execucao(conn, "leo", "sucesso", "ok", ["a.xlsx"])
    df = pd.DataFrame({
        "data": ["2026-09-01", "2026-09-01"],
        "convenio": ["BRADESCO", "GEAP"],
        "vlr_bruto": [100.0, 200.0], "vlr_liquido": [90.0, 180.0],
        "quitado": [0.0, 0.0], "nao_identificado": [10.0, 20.0],
    })
    n = banco.gravar_resumos(conn, eid, df)
    assert n == 2
    datas = banco.resumos_disponiveis(conn)
    assert datas == ["2026-09-01"]
    dia = banco.resumos_do_dia(conn, "2026-09-01")
    assert dia.loc[dia["convenio"] == "BRADESCO", "vlr_bruto"].iloc[0] == 100.0
    conn.close()

def test_autenticar_devolve_estado_zerado_apos_falhas(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    banco.criar_usuario(conn, "leo", "Leo", "senha12345")
    agora = "2026-09-01T10:00:00"
    banco.registrar_falha(conn, "leo", agora=agora)
    banco.registrar_falha(conn, "leo", agora=agora)
    usuario = banco.autenticar(conn, "leo", "senha12345", agora=agora)
    assert usuario["falhas_seguidas"] == 0 and usuario["bloqueado_ate"] is None
    conn.close()

def test_criar_usuario_rejeita_login_ou_nome_vazio(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    with pytest.raises(ValueError):
        banco.criar_usuario(conn, "   ", "Leo", "senha12345")
    with pytest.raises(ValueError):
        banco.criar_usuario(conn, "leo", "  ", "senha12345")
    conn.close()

def test_inicia_e_finaliza_execucao(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    eid = banco.iniciar_execucao(conn, "leo", agora="2026-09-05T10:00:00")
    row = conn.execute("SELECT * FROM execucoes WHERE id=?", (eid,)).fetchone()
    assert row["status"] == "em_andamento"
    assert row["inicio"] == "2026-09-05T10:00:00"
    assert row["fim"] is None and row["mensagem"] is None
    n = banco.finalizar_execucao(conn, eid, "falha", "Erro X", [],
                                 agora="2026-09-05T10:05:00")
    assert n == 1
    row = conn.execute("SELECT * FROM execucoes WHERE id=?", (eid,)).fetchone()
    assert row["status"] == "falha"
    assert row["fim"] == "2026-09-05T10:05:00"
    assert row["mensagem"] == "Erro X"
    assert banco.arquivos_da_execucao(conn, eid) == []
    # finalizar id inexistente: devolve 0, sem erro
    assert banco.finalizar_execucao(conn, 999, "sucesso", "", []) == 0
    conn.close()

def test_lista_execucoes_mais_recente_primeiro_com_limite(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    for i in range(3):
        eid = banco.iniciar_execucao(conn, f"u{i}", agora=f"2026-09-05T10:0{i}:00")
        banco.finalizar_execucao(conn, eid, "sucesso", "", [],
                                 agora=f"2026-09-05T10:0{i}:30")
    linhas = banco.listar_execucoes(conn, limite=2)
    assert [r["usuario"] for r in linhas] == ["u2", "u1"]
    assert [r["status"] for r in linhas] == ["sucesso", "sucesso"]
    conn.close()

def test_criar_sessao_grava_hash_e_expira_em_7_dias(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    banco.criar_usuario(conn, "leo", "Leo", "senha12345")
    token = banco.criar_sessao(conn, "leo", agora="2026-09-05T10:00:00")
    assert token and "senha" not in token
    row = conn.execute("SELECT * FROM sessoes").fetchone()
    # no banco fica só o hash — nunca o token em claro
    assert row["token_hash"] != token
    assert row["login"] == "leo"
    assert row["expira_em"] == "2026-09-12T10:00:00"
    conn.close()

def test_validar_token_sessao_dentro_da_validade(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    banco.criar_usuario(conn, "leo", "Leo", "senha12345")
    token = banco.criar_sessao(conn, "leo", agora="2026-09-05T10:00:00")
    usuario = banco.validar_token_sessao(conn, token, agora="2026-09-11T23:59:59")
    assert usuario is not None and usuario["login"] == "leo"
    # token errado → None
    assert banco.validar_token_sessao(conn, "token-invalido",
                                       agora="2026-09-06T10:00:00") is None
    conn.close()

def test_sessao_expirada_devolve_none_e_e_apagada(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    banco.criar_usuario(conn, "leo", "Leo", "senha12345")
    token = banco.criar_sessao(conn, "leo", agora="2026-09-05T10:00:00")
    assert banco.validar_token_sessao(conn, token,
                                      agora="2026-09-12T10:00:01") is None
    # a linha expirada some do banco
    assert conn.execute("SELECT COUNT(*) FROM sessoes").fetchone()[0] == 0
    conn.close()

def test_remover_sessao_invalida_o_token(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    banco.criar_usuario(conn, "leo", "Leo", "senha12345")
    token = banco.criar_sessao(conn, "leo", agora="2026-09-05T10:00:00")
    banco.remover_sessao(conn, token)
    assert banco.validar_token_sessao(conn, token,
                                      agora="2026-09-06T10:00:00") is None
    conn.close()

def test_criar_sessao_limpa_sessoes_expiradas(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    banco.criar_usuario(conn, "leo", "Leo", "senha12345")
    banco.criar_sessao(conn, "leo", agora="2026-08-01T10:00:00")  # já expirou
    token2 = banco.criar_sessao(conn, "leo", agora="2026-09-05T10:00:00")
    linhas = conn.execute("SELECT login FROM sessoes ORDER BY id").fetchall()
    assert [r["login"] for r in linhas] == ["leo"]  # só a sessão nova ficou
    assert banco.validar_token_sessao(conn, token2,
                                      agora="2026-09-06T10:00:00")["login"] == "leo"
    conn.close()

def test_concluir_sucesso_grava_status_e_resumos(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    eid = banco.iniciar_execucao(conn, "leo", agora="2026-09-05T10:00:00")
    df = pd.DataFrame({
        "data": ["2026-09-05"], "convenio": ["BRADESCO"],
        "vlr_bruto": [100.0], "vlr_liquido": [90.0],
        "quitado": [0.0], "nao_identificado": [10.0],
    })
    banco.concluir_sucesso(conn, eid, ["a.xlsx"], df)
    row = conn.execute("SELECT status, fim FROM execucoes WHERE id=?",
                       (eid,)).fetchone()
    assert row["status"] == "sucesso" and row["fim"] is not None
    assert banco.arquivos_da_execucao(conn, eid) == ["a.xlsx"]
    assert len(banco.historico(conn)) == 1
    conn.close()

def test_concluir_sucesso_com_conexao_fechada_falha(tmp_path):
    # Bug da execução 20 (05/09/2026): o bloco de sucesso da página rodava
    # DEPOIS do conn.close() do finally — o registro ficava 'em_andamento'
    # para sempre e os resumos nunca eram gravados.
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    eid = banco.iniciar_execucao(conn, "leo")
    conn.close()
    df = pd.DataFrame({
        "data": ["2026-09-05"], "convenio": ["BRADESCO"],
        "vlr_bruto": [100.0], "vlr_liquido": [90.0],
        "quitado": [0.0], "nao_identificado": [10.0],
    })
    with pytest.raises(sqlite3.ProgrammingError):
        banco.concluir_sucesso(conn, eid, ["a.xlsx"], df)

def test_login_existe(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    assert banco.login_existe(conn, "leo") is False
    banco.criar_usuario(conn, "leo", "Leo", "senha12345")
    assert banco.login_existe(conn, " leo ") is True
    conn.close()

def test_historico_mostra_so_a_execucao_mais_recente_por_data(tmp_path):
    """Cada reprocessamento grava de novo os resumos do mesmo dia; a grade
    deve mostrar só a execução MAIS RECENTE de cada data (posição atual),
    sem linhas repetidas do mesmo dia+convênio."""
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    eid1 = banco.registrar_execucao(conn, "leo", "sucesso", "", ["a.xlsx"])
    eid2 = banco.registrar_execucao(conn, "ana", "sucesso", "", ["b.xlsx"])
    df_bradesco = pd.DataFrame({
        "data": ["2026-09-02"], "convenio": ["BRADESCO OPERADORA PLANO"],
        "vlr_bruto": [17151.47], "vlr_liquido": [17151.47],
        "quitado": [0.0], "nao_identificado": [0.0],
    })
    banco.gravar_resumos(conn, eid1, df_bradesco)
    banco.gravar_resumos(conn, eid2, df_bradesco)
    tudo = banco.historico(conn)
    assert len(tudo) == 1
    assert tudo.iloc[0]["execucao_id"] == eid2
    assert tudo.iloc[0]["convenio"] == "BRADESCO OPERADORA PLANO"
    # outra data gravada só pela execução antiga continua visível
    df_geap = pd.DataFrame({
        "data": ["2026-09-01"], "convenio": ["GEAP"],
        "vlr_bruto": [200.0], "vlr_liquido": [180.0],
        "quitado": [0.0], "nao_identificado": [20.0],
    })
    banco.gravar_resumos(conn, eid1, df_geap)
    tudo = banco.historico(conn)
    assert len(tudo) == 2
    assert set(tudo["convenio"]) == {"BRADESCO OPERADORA PLANO", "GEAP"}
    assert tudo[tudo["convenio"] == "GEAP"].iloc[0]["execucao_id"] == eid1
    conn.close()


def test_historico_filtra_por_convenio(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    eid1 = banco.registrar_execucao(conn, "leo", "sucesso", "", ["a.xlsx"])
    eid2 = banco.registrar_execucao(conn, "ana", "sucesso", "", ["b.xlsx"])
    df1 = pd.DataFrame({
        "data": ["2026-09-01"], "convenio": ["BRADESCO"],
        "vlr_bruto": [100.0], "vlr_liquido": [90.0],
        "quitado": [0.0], "nao_identificado": [10.0],
    })
    df2 = pd.DataFrame({
        "data": ["2026-09-02"], "convenio": ["GEAP"],
        "vlr_bruto": [200.0], "vlr_liquido": [180.0],
        "quitado": [0.0], "nao_identificado": [20.0],
    })
    banco.gravar_resumos(conn, eid1, df1)
    banco.gravar_resumos(conn, eid2, df2)
    tudo = banco.historico(conn)
    assert sorted(tudo["convenio"].unique()) == ["BRADESCO", "GEAP"]
    so_bradesco = banco.historico(conn, convenio="BRADESCO")
    assert set(so_bradesco["convenio"].unique()) == {"BRADESCO"}
    assert banco.convenios_disponiveis(conn) == ["BRADESCO", "GEAP"]
    assert banco.arquivos_da_execucao(conn, eid1) == ["a.xlsx"]
    assert banco.arquivos_da_execucao(conn, 999) == []
    conn.close()


def test_migracao_acesso_contas_receber_banca_antigo_sem_coluna(tmp_path):
    """Banco criado ANTES da feature ganha a coluna ao inicializar."""
    db = str(tmp_path / "pf_antigo.db")
    conn_antigo = sqlite3.connect(db)
    conn_antigo.execute("""CREATE TABLE usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login TEXT UNIQUE NOT NULL,
        nome TEXT NOT NULL,
        senha_hash TEXT NOT NULL,
        admin INTEGER NOT NULL DEFAULT 0,
        falhas_seguidas INTEGER NOT NULL DEFAULT 0,
        bloqueado_ate TEXT,
        criado_em TEXT NOT NULL
    )""")
    conn_antigo.commit()
    conn_antigo.close()

    conn = banco.conectar(db)
    banco.inicializar_banco(conn)  # não pode quebrar
    banco.inicializar_banco(conn)  # idempotente
    colunas = [r["name"] for r in conn.execute("PRAGMA table_info(usuarios)").fetchall()]
    assert "acesso_contas_receber" in colunas
    conn.close()


def test_definir_acesso_contas_receber_e_listar(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    login = "alguem_cr"
    banco.criar_usuario(conn, login, "Alguém", "senha12345")
    assert [r["acesso_contas_receber"] for r in banco.listar_usuarios(conn)
            if r["login"] == login] == [0]
    banco.definir_acesso_contas_receber(conn, login, True)
    assert [r["acesso_contas_receber"] for r in banco.listar_usuarios(conn)
            if r["login"] == login] == [1]
    banco.definir_acesso_contas_receber(conn, login, False)
    assert [r["acesso_contas_receber"] for r in banco.listar_usuarios(conn)
            if r["login"] == login] == [0]
    conn.close()


def test_autenticar_devolve_acesso_contas_receber(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    login = "com_acesso"
    banco.criar_usuario(conn, login, "Com Acesso", "senha12345")
    banco.definir_acesso_contas_receber(conn, login, True)
    usuario = banco.autenticar(conn, login, "senha12345")
    assert usuario is not None and usuario["acesso_contas_receber"] == 1
    conn.close()

