"""Testes da página Ponto — fonte e fumaça com AppTest."""
from datetime import date
from pathlib import Path

import banco
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
FONTE = (RAIZ / "app_pages" / "ponto.py").read_text(encoding="utf-8")


def _app(tmp_path, monkeypatch, usuario=None, registros=()):
    caminho = str(tmp_path / "pf.db")
    monkeypatch.setattr(banco, "CAMINHO_PADRAO", caminho)
    conn = banco.conectar(caminho)
    banco.inicializar_banco(conn)
    for registro in registros:
        banco.salvar_registro_manual(
            conn, registro["data"], registro.get("entrada"),
            registro.get("saida"), registro.get("tipo", "trabalho"),
            registro.get("observacao"), "leo")
    conn.close()
    at = AppTest.from_file(str(RAIZ / "app_pages" / "ponto.py"),
                           default_timeout=30)
    at.session_state["usuario"] = usuario or {
        "login": "leo", "admin": True, "acesso_ponto": True}
    return at


def test_pagina_exige_permissao(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch,
              usuario={"login": "leo", "admin": False, "acesso_ponto": False})
    at.run()
    assert not at.exception
    assert any("Acesso restrito ao Controle de Ponto" in e.value
               for e in at.error)


def test_pagina_sem_dados_mostra_estado_vazio(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    at.run()
    assert not at.exception
    assert any("Nenhum ponto registrado" in i.value for i in at.info)


def test_pagina_com_dados_mostra_kpis(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch, registros=[
        {"data": date(2026, 11, 3), "entrada": "08:00", "saida": "18:00"},
    ])
    at.run()
    assert not at.exception
    texto = " ".join(m.value for m in at.markdown)
    texto += " ".join(c.value for c in at.caption)
    assert "Saldo acumulado" in texto
    assert "Horas no período" in texto


def test_fonte_tem_formulario_manual():
    assert "Lançar/editar ponto" in FONTE
    assert "Excluir dia" in FONTE
    assert "salvar_registro_manual" in FONTE
    assert "excluir_registro_ponto" in FONTE
