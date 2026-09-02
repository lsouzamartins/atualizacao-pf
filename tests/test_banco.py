import os, sqlite3
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

