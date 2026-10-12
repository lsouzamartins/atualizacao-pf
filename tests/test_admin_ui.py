"""Testes da página Administração — verificação de fonte (UI Streamlit)."""
from pathlib import Path

FONTE = (Path(__file__).resolve().parents[1] / "app_pages" / "administracao.py") \
    .read_text(encoding="utf-8")


def test_admin_criar_usuario_pede_login_sem_cpf():
    """12/10 (a pedido do Leonardo): o login NÃO é mais CPF — o cadastro pede
    "Login" (o 'Login CPF', planejado em 30/09, foi revertido antes de sair)."""
    assert 'st.text_input("Login"' in FONTE
    assert "Login CPF" not in FONTE


def test_admin_e_so_para_administrador():
    """As informações de cadastro só podem ser vistas pelo administrador."""
    assert 'st.session_state.get("usuario", {}).get("admin")' in FONTE
    assert "Acesso restrito ao administrador." in FONTE
