"""Testes da lógica de autenticação (parte pura; o gate Streamlit é validado manualmente)."""
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
