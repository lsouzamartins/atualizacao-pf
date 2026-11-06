"""Testes das tabelas e funções de ponto no banco."""
import sqlite3
from datetime import date

import banco


def _conn(tmp_path):
    conn = banco.conectar(str(tmp_path / "pf.db"))
    banco.inicializar_banco(conn)
    return conn


def _registro(dia, entrada="08:00", saida="18:00", tipo="trabalho",
              observacao=None):
    return {"data": dia, "entrada": entrada, "saida": saida,
            "tipo": tipo, "observacao": observacao}


def test_cria_tabelas_de_ponto(tmp_path):
    conn = _conn(tmp_path)
    tabelas = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"ponto_uploads", "ponto_registros"} <= tabelas
    conn.close()


def test_migracao_acesso_ponto_em_banco_antigo(tmp_path):
    db = str(tmp_path / "antigo.db")
    antigo = sqlite3.connect(db)
    antigo.execute("""CREATE TABLE usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login TEXT UNIQUE NOT NULL,
        nome TEXT NOT NULL,
        senha_hash TEXT NOT NULL,
        admin INTEGER NOT NULL DEFAULT 0,
        falhas_seguidas INTEGER NOT NULL DEFAULT 0,
        bloqueado_ate TEXT,
        criado_em TEXT NOT NULL)""")
    antigo.commit()
    antigo.close()

    conn = banco.conectar(db)
    banco.inicializar_banco(conn)
    banco.inicializar_banco(conn)
    colunas = [r["name"] for r in conn.execute("PRAGMA table_info(usuarios)")]
    assert "acesso_ponto" in colunas
    conn.close()


def test_definir_acesso_ponto_e_listar(tmp_path):
    conn = _conn(tmp_path)
    banco.criar_usuario(conn, "leo", "Leo", "senha12345")
    assert [r["acesso_ponto"] for r in banco.listar_usuarios(conn)
            if r["login"] == "leo"] == [0]
    banco.definir_acesso_ponto(conn, "leo", True)
    assert [r["acesso_ponto"] for r in banco.listar_usuarios(conn)
            if r["login"] == "leo"] == [1]
    banco.definir_acesso_ponto(conn, "leo", False)
    assert [r["acesso_ponto"] for r in banco.listar_usuarios(conn)
            if r["login"] == "leo"] == [0]
    conn.close()


def test_importacao_grava_upload_e_registros(tmp_path):
    conn = _conn(tmp_path)
    registros = [
        _registro(date(2026, 11, 3)),
        _registro(date(2026, 11, 4), "08:00", None, "trabalho", "x"),
    ]
    upload_id = banco.salvar_importacao_ponto(
        conn, "leo", "ponto.xlsx", registros,
        date(2026, 11, 3), date(2026, 11, 4), ["aviso"],
        agora="2026-11-06T10:00:00")
    assert upload_id
    upload = banco.ultimo_upload_ponto(conn)
    assert upload["nome_arquivo"] == "ponto.xlsx"
    assert upload["linhas"] == 2
    assert upload["periodo_de"] == "2026-11-03"
    registros_banco = banco.registros_ponto(conn)
    assert [r["data"] for r in registros_banco] == \
        [date(2026, 11, 3), date(2026, 11, 4)]
    conn.close()


def test_reimportacao_nao_duplica_e_nao_toca_fora_do_arquivo(tmp_path):
    conn = _conn(tmp_path)
    banco.salvar_importacao_ponto(
        conn, "leo", "a.xlsx",
        [_registro(date(2026, 11, 3), "08:00", "18:00"),
         _registro(date(2026, 11, 4), "08:00", "18:00")],
        date(2026, 11, 3), date(2026, 11, 4), [])
    banco.salvar_importacao_ponto(
        conn, "leo", "b.xlsx", [_registro(date(2026, 11, 3), "09:00", "19:00")],
        date(2026, 11, 3), date(2026, 11, 3), [])
    registros = {r["data"]: r for r in banco.registros_ponto(conn)}
    assert len(registros) == 2
    assert registros[date(2026, 11, 3)]["entrada"] == "09:00"
    assert registros[date(2026, 11, 4)]["entrada"] == "08:00"
    conn.close()


def test_importacao_preserva_manual_por_padrao(tmp_path):
    conn = _conn(tmp_path)
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "09:00", "18:00",
                                 "trabalho", "manual", "leo")
    banco.salvar_importacao_ponto(
        conn, "leo", "ponto.xlsx",
        [_registro(date(2026, 11, 3)), _registro(date(2026, 11, 4))],
        date(2026, 11, 3), date(2026, 11, 4), [])
    registros = {r["data"]: r for r in banco.registros_ponto(conn)}
    assert registros[date(2026, 11, 3)]["entrada"] == "09:00"
    assert registros[date(2026, 11, 3)]["origem"] == "manual"
    assert registros[date(2026, 11, 4)]["origem"] == "upload"
    conn.close()


def test_importacao_sobrescreve_manual_quando_pedido(tmp_path):
    conn = _conn(tmp_path)
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "09:00", "18:00",
                                 "trabalho", None, "leo")
    banco.salvar_importacao_ponto(
        conn, "leo", "ponto.xlsx", [_registro(date(2026, 11, 3))],
        date(2026, 11, 3), date(2026, 11, 3), [],
        sobrescrever_manuais=True)
    registro = banco.registros_ponto(conn)[0]
    assert registro["entrada"] == "08:00"
    assert registro["origem"] == "upload"
    conn.close()


def test_salvar_registro_manual_cria_e_atualiza(tmp_path):
    conn = _conn(tmp_path)
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "08:00", "17:00",
                                 "trabalho", None, "leo",
                                 agora="2026-11-06T10:00:00")
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "09:00", "19:00",
                                 "trabalho", "obs", "ana",
                                 agora="2026-11-06T11:00:00")
    registro = banco.registros_ponto(conn)[0]
    assert registro["entrada"] == "09:00"
    assert registro["origem"] == "manual"
    assert registro["atualizado_por"] == "ana"
    assert registro["atualizado_em"] == "2026-11-06T11:00:00"
    conn.close()


def test_excluir_registro_ponto(tmp_path):
    conn = _conn(tmp_path)
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "08:00", "17:00",
                                 "trabalho", None, "leo")
    assert banco.excluir_registro_ponto(conn, date(2026, 11, 3)) == 1
    assert banco.registros_ponto(conn) == []
    conn.close()


def test_historico_de_uploads(tmp_path):
    conn = _conn(tmp_path)
    banco.salvar_importacao_ponto(
        conn, "leo", "a.xlsx", [_registro(date(2026, 11, 3))],
        date(2026, 11, 3), date(2026, 11, 3), [])
    banco.salvar_importacao_ponto(
        conn, "ana", "b.xlsx", [_registro(date(2026, 11, 4))],
        date(2026, 11, 4), date(2026, 11, 4), [])
    uploads = banco.listar_uploads_ponto(conn)
    assert [u["nome_arquivo"] for u in uploads] == ["b.xlsx", "a.xlsx"]
    conn.close()
