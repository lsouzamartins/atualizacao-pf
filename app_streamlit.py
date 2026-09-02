"""
==============================================================================
ATUALIZAÇÃO DA POSIÇÃO FINANCEIRA — HOSPITAL ISRAELITA ALBERT SABIN
Ponto de entrada Streamlit: navegação entre as páginas do aplicativo.

Páginas:
  • Processamento — execução das fases 0–4 (app_pages/processamento.py)
  • Resumo do dia — valores diários por convênio (app_pages/resumo_dia.py)

Revisão: Claude Code (Anthropic) · 19/08/2026
==============================================================================
"""
import os
import sys

import streamlit as st

# Garante que o diretório do script está no path (Streamlit muda o cwd)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui_comum import injetar_css, barra_cabecalho


# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA STREAMLIT
# ==============================================================================
st.set_page_config(
    page_title="Atualização PF · Hias",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ==============================================================================
# ELEMENTOS GLOBAIS (visíveis em todas as páginas)
# ==============================================================================
injetar_css()
barra_cabecalho()


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
    ],
    position="top",
)
pagina.run()
