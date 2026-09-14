"""
==============================================================================
ELEMENTOS DE INTERFACE COMPARTILHADOS — ATUALIZAÇÃO PF · HIAS
CSS global, ícones Lucide, faixa de cabeçalho e helpers de formatação.

Importado pelo ponto de entrada (app_streamlit.py) e pelas páginas em app_pages/.
Revisão: Claude Code (Anthropic) · 19/08/2026
==============================================================================
"""
import os
import base64

import streamlit as st

from core import obter_pasta_raiz, garantir_pastas


VERSAO = "Criado por Leonardo Martins · Revisado por Claude Code (Anthropic) · V 4.2026.0906 · Streamlit + Lucide"

# ---------------------------------------------------------------------------
# CAMINHOS PRINCIPAIS
# ---------------------------------------------------------------------------
PASTA_RAIZ = obter_pasta_raiz()
PASTA_RELATORIOS = os.path.join(PASTA_RAIZ, "relatórios")
PASTA_SAIDA = os.path.join(PASTA_RAIZ, "saída")
PASTA_ERROS = os.path.join(PASTA_RAIZ, "logo de erro")
PASTA_LOGS = os.path.join(PASTA_RAIZ, "logs")
PASTA_FOTOS = os.path.join(PASTA_RAIZ, "dados", "fotos")


def pastas() -> dict:
    """Garante as pastas do app e retorna os caminhos principais."""
    garantir_pastas(PASTA_RAIZ)
    return {
        "raiz": PASTA_RAIZ,
        "relatorios": PASTA_RELATORIOS,
        "saida": PASTA_SAIDA,
        "erros": PASTA_ERROS,
        "logs": PASTA_LOGS,
        "fotos": PASTA_FOTOS,
    }


# ---------------------------------------------------------------------------
# CSS GLOBAL (apenas o que o config.toml não cobre)
# ---------------------------------------------------------------------------
CSS = """
<style>
    :root {
        --accent: #1C5A8A;
        --accent-hover: #0F3B5C;
        --border: #E2E8F0;
        --surface: #F8FAFC;
        --text: #0F172A;
        --text-muted: #64748B;
    }

    .stApp { background-color: #FFFFFF; }

    div.stButton > button[kind="primary"] {
        background: var(--accent) !important;
        border: none !important; border-radius: 10px !important;
        padding: 0.75rem 2rem !important; font-weight: 600 !important;
        font-size: 0.95rem !important; letter-spacing: 0.2px !important;
        transition: background 0.2s ease !important; color: #FFFFFF !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background: var(--accent-hover) !important;
    }
    div.stButton > button[kind="primary"]:disabled {
        background: #CBD5E1 !important; color: #64748B !important; cursor: not-allowed;
    }

    div.stButton > button[kind="secondary"] {
        border: 1px solid var(--border) !important; border-radius: 10px !important;
        color: var(--text) !important; font-weight: 600 !important;
        padding: 0.75rem 1.5rem !important; background: #FFFFFF !important;
        transition: all 0.2s ease !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        border-color: var(--accent) !important; background: var(--surface) !important;
    }

    div[data-testid="stExpander"] {
        background: #FFFFFF !important; border: 1px solid var(--border) !important;
        border-radius: 10px !important; color: var(--text) !important;
    }
    /* Bloco de progresso: faixa de texto em acento (texto branco) + trilha clara */
    div[data-testid="stProgress"] > div:first-child {
        background: var(--accent);
        color: #FFFFFF !important;
        padding: 0.35rem 0.8rem;
        border-radius: 10px 10px 0 0;
        font-size: 0.88rem;
    }
    div[data-testid="stProgress"] > div:first-child p { color: #FFFFFF !important; }
    div[data-testid="stProgressBarTrack"] {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 0 0 6px 6px;
    }
    div[data-testid="stProgressBarTrack"] > div {
        background: var(--accent);
        border-radius: 0 0 6px 6px;
    }
    div[data-testid="stCodeBlock"] {
        background: var(--surface) !important; border: 1px solid var(--border) !important;
        border-radius: 10px !important; font-family: 'Consolas', monospace !important;
        font-size: 0.82rem !important; color: #0F172A !important;
    }
    div[data-testid="stToast"] { border-radius: 10px !important; }

    .app-footer { text-align: center; color: var(--text-muted); font-size: 0.75rem; padding: 1.5rem 0 0.5rem 0; }

    /* Foto do usuário na Administração */
    .foto-admin-preview { width: 110px; height: 110px; border-radius: 50%;
                          object-fit: cover; border: 3px solid var(--border); }
    .info-card { background: #FFFFFF; border: 1px solid var(--border); border-radius: 10px; padding: 1.2rem 1.5rem; }
    .info-card h4 { color: var(--text); margin-top: 0; margin-bottom: 0.8rem; }
    .info-card ol { color: var(--text); padding-left: 1.2rem; }
    .info-card ol li { margin-bottom: 0.4rem; }
    .info-card code { background: var(--surface); color: var(--accent); padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; }
    .info-card .info-paths { color: var(--text-muted); font-size: 0.82rem; margin-bottom: 0; margin-top: 0.8rem; }

    /* Faixa do cabeçalho: branca com borda sutil, logo à esquerda e título centralizado */
    .brand-bar { background: #FFFFFF; border: 1px solid var(--border); border-radius: 10px;
                 padding: 1.3rem 1.8rem; margin-bottom: 1.2rem;
                 display: flex; align-items: center; }
    .brand-bar .brand-logo { flex-shrink: 0; display: flex; align-items: center; }
    .brand-bar .brand-text { flex: 1; text-align: center; padding: 0 1.5rem; }
    .brand-bar .brand-spacer { flex-shrink: 0; width: 180px; }
    .brand-bar .brand-title { color: var(--text); font-size: 1.35rem; font-weight: 700; margin-bottom: 0.15rem; }
    .brand-bar .brand-sub { color: var(--text-muted) !important; font-size: 0.88rem; margin: 0; }

    /* Badges de status do recurso (Contas a Receber) */
    .badge-status {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        white-space: nowrap;
    }
    .badge-status .dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        display: inline-block;
        flex-shrink: 0;
    }

    /* Cartões de KPI do dashboard de glosas (visual v1.0) */
    .kpi-card { background: #FFFFFF; border: 1px solid var(--border); border-radius: 16px;
                padding: 1.1rem 1.2rem; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04); }
    .kpi-card .kpi-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
    .kpi-card .kpi-label { font-size: 0.78rem; color: var(--text-muted); font-weight: 500; }
    .kpi-card .kpi-value { font-size: 1.65rem; font-weight: 700; letter-spacing: -0.5px; margin-top: 0.2rem; }
    .kpi-card svg { margin-right: 0 !important; opacity: 0.9; }

    /* Tabela de alertas de prazo (visual v1.0) */
    .tabela-alertas { width: 100%; border-collapse: collapse; font-size: 0.85rem;
                      background: #FFFFFF; border: 1px solid var(--border); border-radius: 16px; }
    .tabela-alertas th { text-align: left; color: var(--text-muted); background: var(--surface);
                         border-bottom: 1px solid var(--border); padding: 0.55rem 0.75rem;
                         font-weight: 600; }
    .tabela-alertas td { padding: 0.55rem 0.75rem; border-bottom: 1px solid var(--surface); }
    .badge-crit { display: inline-block; padding: 2px 10px; border-radius: 999px;
                  font-size: 0.72rem; font-weight: 600; white-space: nowrap; }

    /* Chrome do Streamlit: preserva as abas de navegação (dentro do stToolbar)
       e oculta logo, ações/deploy e decoração */
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    [data-testid="stDecoration"] {visibility: hidden;}
    [data-testid="stHeaderLogo"] {visibility: hidden;}
    [data-testid="stToolbarActions"] {visibility: hidden;}
    hr { border-color: var(--border) !important; }
    .stApp, .stMarkdown, p, label { color: var(--text) !important; }
    .stCaption { color: var(--text-muted) !important; }
    code { color: var(--accent) !important; }
</style>
"""


def injetar_css():
    st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# TELA DE LOGIN — fundo escuro, título no topo centralizado e cartão branco ao centro
# ---------------------------------------------------------------------------
LOGIN_CSS = """
<style>
    /* Fundo da tela de login: vetor de setas ascendentes (escolha do
       Leonardo, 13/09) com véu navy por cima para manter o contraste do
       cartão branco. Imagem embutida em base64 — nenhum arquivo extra. */
    html, body, .stApp { min-height: 100vh; }
    .stApp {
        background: linear-gradient(rgba(19, 26, 61, .35), rgba(19, 26, 61, .35)),
                    url("data:image/jpeg;base64,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") center center / cover no-repeat #131A3D;
    }
    div[data-testid="stMainBlockContainer"], .block-container {
        max-width: 100%; padding-left: 0; padding-right: 0; padding-top: 0; padding-bottom: 0;
    }

    /* Chrome do Streamlit oculto nesta tela */
    #MainMenu, footer, [data-testid="stDecoration"], header[data-testid="stHeader"] { visibility: hidden; }

    /* Título da página, no topo e centralizado */
    .login-titulo-pagina {
        text-align: center; color: #FFFFFF; font-size: 1.9rem; font-weight: 800;
        padding: 2.2rem 1rem 0 1rem; letter-spacing: .2px;
    }

    /* Rodapé da tela de login: crédito do desenvolvedor, fixo na base */
    .login-rodape {
        position: fixed; left: 0; right: 0; bottom: .8rem;
        text-align: center; color: rgba(255, 255, 255, .55); font-size: .75rem;
        letter-spacing: .2px;
    }

    /* Área do formulário: centralizada vertical e horizontalmente.
       O :not(... *) exclui stHorizontalBlock ANINHADOS — o st.columns interno
       do cartão também é um stHorizontalBlock e, sem a exclusão, herdava o
       min-height de 100vh (vão de ~424px entre a Senha e o checkbox). */
    div[data-testid="stHorizontalBlock"]:not(div[data-testid="stHorizontalBlock"] *) {
        min-height: calc(100vh - 9rem); align-items: center;
    }

    /* Cartão branco — 470px de largura com ALTURA NATURAL (13/09, a pedido:
       'alarga mais um pouco o quadrado branco'; o min-height 440px forçava
       um quadrado com ~70px de vazio no rodapé). 470px fica na faixa de
       380–500px das telas de login modernas; padding 32px é o padrão das
       referências pesquisadas. O st.container(border=True) de exigir_login
       renderiza, no Streamlit 1.60, stColumn > stLayoutWrapper >
       stVerticalBlock (a borda/padding padrão ficam no bloco interno; o
       testid stVerticalBlockBorderWrapper é de versões mais novas e NÃO
       existe aqui). Div aberta/fechada em markdowns separados também não
       aninha — era o quadrado branco fantasma sem formulário. */
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] {
        width: 470px; max-width: calc(100vw - 32px); margin: 0 auto;
    }
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"] {
        background: #FFFFFF; border: none; border-radius: 18px;
        box-shadow: 0 24px 60px rgba(0, 0, 0, .35);
        padding: 2rem 2rem 1.5rem 2rem;
        box-sizing: border-box; gap: .35rem;
    }
    /* Avatar no cartão de login: foto do usuário (tamanho fixo, sem distorção)
       ou círculo padrão com a inicial — proporcional ao cartão de 470px */
    .login-avatar { display: block; width: 88px; height: 88px; margin: 0 auto 2rem auto;
                    border-radius: 50%; object-fit: cover; border: 3px solid #E2E8F0;
                    background: #F8FAFC; }
    .login-avatar-padrao { display: flex; align-items: center; justify-content: center;
                           width: 88px; height: 88px; margin: 0 auto 2rem auto;
                           border-radius: 50%; border: 3px solid #E2E8F0;
                           background: linear-gradient(135deg, #4D7CFE 0%, #3153E8 100%);
                           color: #FFFFFF; font-size: 1.7rem; font-weight: 800; }
    .login-avatar-padrao svg { margin: 0; width: 32px; height: 32px; }

    /* Campos com ícones (usuário / cadeado) — 44px de altura (alvo mínimo de
       toque WCAG), espaçamento ~18px entre campos. Login renderiza
       <input type="text"> e Senha, type="password": atributo distingue de
       forma robusta (seletor de irmãos falharia — cada widget vive no
       próprio stElement). */
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] div[data-testid="stTextInput"] {
        margin-bottom: 1.25rem;
    }
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] div[data-testid="stTextInput"] input {
        border: 1px solid #E2E8F0 !important; border-radius: 10px !important;
        background: #F8FAFC !important; padding: .55rem .9rem .55rem 2.6rem !important;
        font-size: 1rem !important; color: #131A3D !important; min-height: 44px;
    }
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] div[data-testid="stTextInput"] input:focus {
        border-color: #4D7CFE !important; box-shadow: 0 0 0 3px rgba(77, 124, 254, .18) !important;
    }
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] div[data-testid="stTextInput"] input:not([type="password"]) {
        background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2364748B' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2'/%3E%3Ccircle cx='12' cy='7' r='4'/%3E%3C/svg%3E") !important;
        background-repeat: no-repeat !important; background-position: .8rem center !important; background-size: 16px !important;
    }
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] div[data-testid="stTextInput"] input[type="password"] {
        background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2364748B' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect width='18' height='11' x='3' y='11' rx='2' ry='2'/%3E%3Cpath d='M7 11V7a5 5 0 0 1 10 0v4'/%3E%3C/svg%3E") !important;
        background-repeat: no-repeat !important; background-position: .8rem center !important; background-size: 16px !important;
    }

    /* Botão Entrar — largura total, altura confortável */
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] [data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(90deg, #4D7CFE 0%, #3153E8 100%) !important;
        border: none !important; border-radius: 10px !important;
        padding: .65rem 1rem !important; font-weight: 700 !important; font-size: 1rem !important;
        color: #FFFFFF !important; width: 100%; transition: filter .2s ease !important;
    }
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] [data-testid="stButton"] > button[kind="primary"]:hover { filter: brightness(1.1); }
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] [data-testid="stButton"] > button[kind="primary"]:disabled { background: #CBD5E1 !important; }

    /* Mensagens de erro dentro do cartão */
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] [data-testid="stAlert"] { border-radius: 10px; }

    /* Checkbox 'Lembrar de mim' — texto sempre visível sobre o cartão branco,
       mínimo de 14px (legibilidade) */
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] div[data-testid="stCheckbox"] { margin: 0 0 .75rem 0; }
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] div[data-testid="stCheckbox"] label p {
        color: #64748B !important; font-size: .875rem !important;
    }

    /* Link 'Esqueceu a senha?' (botão terciário) — à direita da linha,
       ao lado do 'Lembrar de mim' (padrão clássico das telas de login) */
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] [data-testid="stButton"]:has(button[kind="tertiary"]) {
        text-align: right; margin-top: 0;
    }
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] [data-testid="stButton"] > button[kind="tertiary"] {
        background: transparent !important; border: none !important; box-shadow: none !important;
        color: #4D7CFE !important; font-size: .875rem !important; font-weight: 600 !important;
        padding: .1rem .4rem !important;
    }
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] [data-testid="stButton"] > button[kind="tertiary"]:hover {
        color: #3153E8 !important; text-decoration: underline !important;
    }
</style>
"""


def injetar_css_login():
    """CSS exclusivo da tela de login (injetado antes do formulário renderizar)."""
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)



# ---------------------------------------------------------------------------
# ÍCONES LUCIDE SVG INLINE
# ---------------------------------------------------------------------------
_LUCIDE = {
    'activity':           '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    'building-2':         '<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/>',
    'camera':             '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/>',
    'calendar':           '<rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/>',
    'circle-check':       '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    'circle-x':           '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    'file-spreadsheet':   '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><path d="M8 13h2"/><path d="M8 17h2"/><path d="M14 13h2"/><path d="M14 17h2"/>',
    'folder':             '<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/>',
    'folder-output':      '<path d="M2 7.5V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H20a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2"/><path d="M2 13h10"/><path d="m5 10-3 3 3 3"/>',
    'info':               '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    'play':               '<polygon points="5 3 19 12 5 21 5 3"/>',
    'trash-2':            '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>',
    'user-round':         '<circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/>',
    'scroll-text':        '<path d="M8 21h12a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2Z"/><path d="M19 8H7"/><path d="M19 12H7"/><path d="M13 16H7"/>',
    # Ícones do portal pós-login e das páginas do Contas a Receber (plano glosas)
    'home':               '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
    'play-circle':        '<circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/>',
    'hand-coins':         '<path d="M11 15h2a2 2 0 1 0 0-4h-3c-.6 0-1.1.2-1.4.6L3 17"/><path d="m7 21 1.6-1.4c.3-.4.8-.6 1.4-.6h4c1.1 0 2.1-.4 2.8-1.2l4.6-4.4a2 2 0 0 0-2.75-2.91l-4.2 3.9"/><path d="m2 16 6 6"/><circle cx="16" cy="9" r="2.9"/><circle cx="6" cy="5" r="3"/>',
    'layout-dashboard':   '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
    'upload':             '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
    'history':            '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
    'chart-column':       '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    'alarm-clock':        '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2"/><path d="M5 3 2 6"/><path d="m22 6-3-3"/><path d="M6.38 18.7 4 21"/><path d="M17.64 18.67 20 21"/>',
    'bell-ring':          '<path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M22 8c0-2.3-.8-4.3-2-6"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/><path d="M4 2C2.8 3.7 2 5.7 2 8"/>',
    'trending-up':        '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    'list':               '<path d="M3 12h.01"/><path d="M3 18h.01"/><path d="M3 6h.01"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M8 6h13"/>',
    # Ícones do dashboard de glosas no visual v1.0 (KPI cards e exportação)
    'triangle-alert':     '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    'percent':            '<line x1="19" x2="5" y1="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
    'clock':              '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    'circle-minus':       '<circle cx="12" cy="12" r="10"/><path d="M8 12h8"/>',
    'file-down':          '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M12 18v-6"/><path d="m9 15 3 3 3-3"/>',
}


def icone(nome: str, tamanho: int = 18, cor: str = None) -> str:
    path = _LUCIDE.get(nome, '')
    if not path:
        return ''
    stroke = cor if cor else 'currentColor'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{tamanho}" height="{tamanho}"'
        f' viewBox="0 0 24 24" fill="none" stroke="{stroke}" stroke-width="2"'
        f' stroke-linecap="round" stroke-linejoin="round"'
        f' style="display:inline-block;vertical-align:middle;margin-right:6px;flex-shrink:0;">'
        f'{path}</svg>'
    )


# ---------------------------------------------------------------------------
# FAIXA DO CABEÇALHO (identidade do hospital)
# ---------------------------------------------------------------------------
def barra_cabecalho():
    # Sistema de uso particular: sem logotipos nem identidade do hospital.
    st.markdown("""
    <div class="brand-bar">
        <div class="brand-text">
            <div class="brand-title">Atualização da Posição Financeira</div>
            <p class="brand-sub">Integração automática WPD-26 + Não Identificado</p>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# FORMATAÇÃO
# ---------------------------------------------------------------------------
def formatar_brl(valor: float) -> str:
    """Formata número como moeda Brasil: 1234567.89 -> '1.234.567,89'."""
    texto = f"{float(valor):,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_data_br(data_iso: str) -> str:
    """'2026-09-01' -> '01-09-2026' (exibição brasileira dd-mm-aaaa).
    Entradas que não são ISO permanecem como estão."""
    try:
        ano, mes, dia = data_iso.split("-")
        if len(ano) == 4 and len(mes) == 2 and len(dia) == 2:
            return f"{dia}-{mes}-{ano}"
    except (ValueError, AttributeError):
        pass
    return data_iso


# ==============================================================================
# CONTAS A RECEBER — BADGES DE STATUS DO RECURSO
# ==============================================================================
CORES_STATUS = {
    "A iniciar recurso": "#3b82f6",
    "Em análise": "#f59e0b",
    "Glosa Recebida": "#22c55e",
    "Recurso Negado": "#ef4444",
    "Livre de Glosa": "#94a3b8",
}


def badge_status(status: str) -> str:
    """HTML do badge colorido do status do recurso (padrão do dashboard de glosas)."""
    cor = CORES_STATUS.get(status, "#94a3b8")
    return (f'<span class="badge-status" style="background:{cor}1a;color:{cor};">'
            f'<span class="dot" style="background:{cor};"></span>{status}</span>')
