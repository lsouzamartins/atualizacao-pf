"""
==============================================================================
NAVEGAÇÃO — PORTAL E PÁGINAS
Monta a lista de páginas do st.navigation. Sem o acesso ao portal, o nav
é EXATAMENTE o de hoje; com acesso, ganha o portal (default) e as páginas
do PF, com prefixo 'PF ·' nos títulos.
==============================================================================
"""


def montar_paginas(acesso_cr):
    """Lista de páginas [{path, titulo, icone, default}] para o st.navigation."""
    base_pf = [
        {"path": "app_pages/processamento.py", "titulo": "Processamento",
         "icone": ":material/play_circle:", "default": not acesso_cr},
        {"path": "app_pages/resumo_dia.py", "titulo": "Resumo do dia",
         "icone": ":material/calendar_today:", "default": False},
        {"path": "app_pages/historico.py", "titulo": "Histórico",
         "icone": ":material/history:", "default": False},
        {"path": "app_pages/administracao.py", "titulo": "Administração",
         "icone": ":material/settings:", "default": False},
    ]
    if not acesso_cr:
        return base_pf
    pf = [{**p, "titulo": f"PF · {p['titulo']}", "default": False} for p in base_pf]
    portal = {"path": "app_pages/portal.py", "titulo": "Início",
              "icone": ":material/home:", "default": True}
    return [portal] + pf
