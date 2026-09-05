"""
Testes da tela de login (CSS e requisitos de identidade).

Cobre os artefatos de ui_comum usados por auth.exigir_login():
LOGIN_CSS (estrutura centralizada) e a regra de sistema particular —
nenhum logotipo ou nome do hospital na interface. A lógica de
autenticação em si é coberta por tests/test_auth.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ui_comum

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_login_css_tem_estrutura_centralizada():
    assert ".login-card" in ui_comum.LOGIN_CSS
    assert ".login-titulo-pagina" in ui_comum.LOGIN_CSS
    assert "stTextInput" in ui_comum.LOGIN_CSS
    assert "linear-gradient" in ui_comum.LOGIN_CSS


def test_login_css_nao_cita_o_hospital():
    assert "Hospital" not in ui_comum.LOGIN_CSS
    assert "Hias" not in ui_comum.LOGIN_CSS


def test_nenhum_logo_do_hospital_na_interface():
    """Sistema particular: nada de logotipos do hospital na UI do app."""
    with open(ui_comum.__file__, encoding="utf-8") as f:
        src_ui = f.read()
    assert "Logo_Hias" not in src_ui
    assert "logo_topo_Israelita" not in src_ui
    with open(os.path.join(RAIZ, "app_streamlit.py"), encoding="utf-8") as f:
        src_app = f.read()
    assert "🏥" not in src_app


def test_exigir_login_tem_titulo_cartao_e_mesma_logica():
    import auth
    with open(auth.__file__, encoding="utf-8") as f:
        src = f.read()
    assert "Atualização da Posição Financeira" in src
    assert "Acesso ao sistema" in src
    assert "banco.pode_tentar" in src
    assert "banco.autenticar" in src
    assert "banco.registrar_falha" in src
    assert "st.stop()" in src
