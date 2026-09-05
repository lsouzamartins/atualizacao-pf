"""
==============================================================================
ATUALIZAÇÃO DA POSIÇÃO FINANCEIRA — HOSPITAL ISRAELITA ALBERT SABIN
Ponto de entrada Streamlit: navegação entre as páginas do aplicativo.

Páginas:
  • Processamento — execução das fases 0–4 (app_pages/processamento.py)
  • Resumo do dia — valores diários por convênio (app_pages/resumo_dia.py)
  • Histórico — consulta dos resumos diários salvos no banco (app_pages/historico.py)
  • Administração — usuários, senhas e backup (app_pages/administracao.py)

Revisão: Claude Code (Anthropic) · 19/08/2026 · 01/09/2026 · gate de login e páginas novas
==============================================================================
"""
import os
import sys

import streamlit as st

# Garante que o diretório do script está no path (Streamlit muda o cwd)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auth
from ui_comum import injetar_css, barra_cabecalho


# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA STREAMLIT
# ==============================================================================
st.set_page_config(
    page_title="Atualização PF",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ==============================================================================
# GATE DE LOGIN — sem usuário autenticado, nada além do formulário renderiza
# ==============================================================================
auth.exigir_login()


# ==============================================================================
# ELEMENTOS GLOBAIS (visíveis em todas as páginas)
# ==============================================================================
injetar_css()
col_cab, col_sair = st.columns([6, 1], vertical_alignment="center")
with col_cab:
    barra_cabecalho()
with col_sair:
    auth.sair()


# ==============================================================================
# NAVEGAÇÃO
# ==============================================================================
pagina = st.navigation(
    [
        st.Page(
            "app_pages/processamento.py",
            title="Processamento",
            icon=":material/play_circle:",
            default=True,
        ),
        st.Page(
            "app_pages/resumo_dia.py",
            title="Resumo do dia",
            icon=":material/calendar_today:",
        ),
        st.Page(
            "app_pages/historico.py",
            title="Histórico",
            icon=":material/history:",
        ),
        st.Page(
            "app_pages/administracao.py",
            title="Administração",
            icon=":material/settings:",
        ),
    ],
    position="top",
)
pagina.run()
