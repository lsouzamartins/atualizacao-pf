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
    /* Fundo azul-marinho em tela cheia */
    html, body, .stApp { min-height: 100vh; }
    .stApp { background: #131A3D; }
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

    /* Área do formulário: centralizada vertical e horizontalmente */
    div[data-testid="stHorizontalBlock"] { min-height: calc(100vh - 9rem); align-items: center; }

    /* Cartão branco */
    .login-card { background: #FFFFFF; border-radius: 18px; box-shadow: 0 24px 60px rgba(0, 0, 0, .35);
                  padding: 2.6rem 2.4rem 2.2rem 2.4rem; max-width: 430px; margin: 0 auto; }
    .login-card-titulo { font-size: 1.55rem; font-weight: 800; color: #131A3D; margin-bottom: .25rem; }
    .login-card-sub { font-size: .86rem; color: #64748B; margin-bottom: 1.7rem; }

    /* Avatar no cartão de login: foto do usuário (tamanho fixo, sem distorção)
       ou círculo padrão com a inicial */
    .login-avatar { display: block; width: 120px; height: 120px; margin: 0 auto 1.4rem auto;
                    border-radius: 50%; object-fit: cover; border: 4px solid #E2E8F0;
                    background: #F8FAFC; }
    .login-avatar-padrao { display: flex; align-items: center; justify-content: center;
                           width: 120px; height: 120px; margin: 0 auto 1.4rem auto;
                           border-radius: 50%; border: 4px solid #E2E8F0;
                           background: linear-gradient(135deg, #4D7CFE 0%, #3153E8 100%);
                           color: #FFFFFF; font-size: 2.4rem; font-weight: 800; }
    .login-avatar-padrao svg { margin: 0; }

    /* Campos com ícones (usuário / cadeado) */
    .login-card div[data-testid="stTextInput"] { margin-bottom: .85rem; }
    .login-card div[data-testid="stTextInput"] input {
        border: 1px solid #E2E8F0 !important; border-radius: 12px !important;
        background: #F8FAFC !important; padding: .68rem .9rem .68rem 2.7rem !important;
        font-size: .95rem !important; color: #131A3D !important; min-height: 48px;
    }
    .login-card div[data-testid="stTextInput"] input:focus {
        border-color: #4D7CFE !important; box-shadow: 0 0 0 3px rgba(77, 124, 254, .18) !important;
    }
    .login-card div[data-testid="stTextInput"]:has(+ div[data-testid="stTextInput"]) input {
        background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='%2364748B' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2'/%3E%3Ccircle cx='12' cy='7' r='4'/%3E%3C/svg%3E") !important;
        background-repeat: no-repeat !important; background-position: .85rem center !important; background-size: 18px !important;
    }
    .login-card div[data-testid="stTextInput"] + div[data-testid="stTextInput"] input {
        background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='%2364748B' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect width='18' height='11' x='3' y='11' rx='2' ry='2'/%3E%3Cpath d='M7 11V7a5 5 0 0 1 10 0v4'/%3E%3C/svg%3E") !important;
        background-repeat: no-repeat !important; background-position: .85rem center !important; background-size: 18px !important;
    }

    /* Botão Entrar */
    .login-card div.stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #4D7CFE 0%, #3153E8 100%) !important;
        border: none !important; border-radius: 12px !important;
        padding: .8rem 1rem !important; font-weight: 700 !important; font-size: .98rem !important;
        color: #FFFFFF !important; width: 100%; transition: filter .2s ease !important;
    }
    .login-card div.stButton > button[kind="primary"]:hover { filter: brightness(1.1); }
    .login-card div.stButton > button[kind="primary"]:disabled { background: #CBD5E1 !important; }

    /* Mensagens de erro dentro do cartão */
    .login-card [data-testid="stAlert"] { border-radius: 10px; }
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
