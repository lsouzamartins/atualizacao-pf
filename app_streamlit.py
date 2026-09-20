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
import navegacao
from ui_comum import injetar_css, barra_cabecalho


# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA STREAMLIT
# ==============================================================================
st.set_page_config(
    page_title="Sistemas Integrados",
    page_icon="🧩",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ==============================================================================
# GATE DE LOGIN — sem usuário autenticado, nada além do formulário renderiza
# ==============================================================================
auth.exigir_login()
# "Manter conectado": grava o cookie de sessão no navegador (componente invisível)
auth.manter_cookie_sessao()


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
paginas = [
    st.Page(p["path"], title=p["titulo"], icon=p["icone"], default=p["default"])
    for p in navegacao.montar_paginas(
        st.session_state.get("usuario", {}).get("acesso_contas_receber", False))
]
pagina = st.navigation(paginas, position="top")
pagina.run()
