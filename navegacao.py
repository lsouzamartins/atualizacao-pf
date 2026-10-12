"""
==============================================================================
NAVEGAÇÃO — PORTAL E PÁGINAS
Monta a lista de páginas do st.navigation. O portal (Início) entra quando o
usuário tem QUALQUER acesso próprio (Contas a Receber/Cobrança ou Recursos
de Glosa) e vira a página padrão; as páginas do PF ganham o prefixo 'PF ·'.
A aba Administração só existe para admin (12/10).
==============================================================================
"""


def montar_paginas(acesso_cr, acesso_glosa=False, admin=False):
    """Lista de páginas [{path, titulo, icone, default}] para o st.navigation.

    12/10/2026: o Início passou a entrar também com acesso_glosa (é onde o
    card dos Recursos de Glosa aparece) e a aba Administração ficou restrita
    a admin — antes aparecia para todos e devolvia 'Acesso restrito'.
    """
    tem_portal = acesso_cr or acesso_glosa
    base_pf = [
        {"path": "app_pages/processamento.py", "titulo": "Processamento",
         "icone": ":material/play_circle:", "default": not tem_portal},
        {"path": "app_pages/resumo_dia.py", "titulo": "Resumo do dia",
         "icone": ":material/calendar_today:", "default": False},
        {"path": "app_pages/historico.py", "titulo": "Histórico",
         "icone": ":material/history:", "default": False},
    ]
    if admin:
        base_pf.append(
            {"path": "app_pages/administracao.py", "titulo": "Administração",
             "icone": ":material/settings:", "default": False})
    if not tem_portal:
        return base_pf
    pf = [{**p, "titulo": f"PF · {p['titulo']}", "default": False} for p in base_pf]
    portal = {"path": "app_pages/portal.py", "titulo": "Início",
              "icone": ":material/home:", "default": True}
    return [portal] + pf
