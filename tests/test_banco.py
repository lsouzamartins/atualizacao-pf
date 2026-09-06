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

