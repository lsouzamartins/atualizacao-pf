"""Testes da lógica de autenticação (parte pura; o gate Streamlit é validado manualmente)."""
from types import SimpleNamespace

import banco
import auth

def _conn(tmp_path):
    conn = banco.conectar(str(tmp_path / "pf.db"))
    banco.inicializar_banco(conn)
    return conn

def test_verificar_credenciais_e_troca_senha(tmp_path):
    conn = _conn(tmp_path)
    banco.criar_usuario(conn, "leo", "Leo", "senha12345")
    assert auth.verificar_credenciais(conn, "leo", "senha12345") is True
    assert auth.verificar_credenciais(conn, "leo", "errada") is False
    assert auth.trocar_senha(conn, "leo", "senha12345", "novaSenha99") is True
    assert auth.verificar_credenciais(conn, "leo", "novaSenha99") is True
    assert auth.trocar_senha(conn, "leo", "errada", "outra12345") is False
    conn.close()

def test_senha_fraca_rejeitada(tmp_path):
    conn = _conn(tmp_path)
    banco.criar_usuario(conn, "leo", "Leo", "senha12345")
    assert auth.trocar_senha(conn, "leo", "senha12345", "curta") is False
    conn.close()


def _fake_st(monkeypatch, session_state):
    """st fake: session_state como dict e html() que grava o script recebido."""
    chamadas = []
    html = lambda script, **kw: chamadas.append(script)
    fake = SimpleNamespace(
        session_state=session_state,
        components=SimpleNamespace(v1=SimpleNamespace(html=html)),
    )
    monkeypatch.setattr(auth, "st", fake)
    return chamadas


def test_script_cookie_sessao_grava_token():
    script = auth.script_cookie_sessao("abc123")
    assert "pf_sessao=abc123" in script
    assert "max-age=604800" in script


def test_script_cookie_sessao_sem_token_apaga():
    script = auth.script_cookie_sessao(None)
    assert "pf_sessao=;" in script
    assert "max-age=0" in script


def test_manter_cookie_com_lembrar_grava_token(monkeypatch):
    chamadas = _fake_st(monkeypatch,
                        {"token_sessao": "abc123", "lembrar_sessao": True})
    auth.manter_cookie_sessao()
    assert len(chamadas) == 1
    assert "pf_sessao=abc123" in chamadas[0]
    assert "max-age=604800" in chamadas[0]


def test_manter_cookie_sem_lembrar_apaga(monkeypatch):
    chamadas = _fake_st(monkeypatch,
                        {"token_sessao": "abc123", "lembrar_sessao": False})
    auth.manter_cookie_sessao()
    assert len(chamadas) == 1
    assert "max-age=0" in chamadas[0]
    assert "pf_sessao=abc123" not in chamadas[0]


def test_manter_cookie_sem_token_nao_emite(monkeypatch):
    chamadas = _fake_st(monkeypatch, {"lembrar_sessao": True})
    auth.manter_cookie_sessao()
    assert chamadas == []


def test_restaurar_sessao_marca_lembrar(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    banco.criar_usuario(conn, "leo", "Leo", "senha12345")
    token = banco.criar_sessao(conn, "leo")
    conn.close()
    monkeypatch.setattr(auth, "_conexao",
                        lambda: banco.conectar(str(tmp_path / "pf.db")))
    ss = {}
    _fake_st(monkeypatch, ss)
    assert auth._restaurar_sessao(token) is True
    assert ss["autenticado"] is True
    assert ss["lembrar_sessao"] is True
