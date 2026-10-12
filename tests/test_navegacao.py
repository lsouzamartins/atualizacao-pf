"""Testes da montagem de páginas do nav (sem tocar no Streamlit)."""
import navegacao


def test_sem_acesso_e_admin_nav_fica_como_hoje():
    paginas = navegacao.montar_paginas(False, admin=True)
    assert [p["titulo"] for p in paginas] == \
        ["Processamento", "Resumo do dia", "Histórico", "Administração"]
    assert paginas[0]["default"] is True
    assert all(not p["titulo"].startswith(("PF ·", "CR ·")) for p in paginas)


def test_nao_admin_nao_ve_a_aba_administracao():
    """12/10: a aba Administração deixou de aparecer para quem não é admin
    (antes aparecia e devolvia 'Acesso restrito' ao clicar)."""
    paginas = navegacao.montar_paginas(False)
    assert [p["titulo"] for p in paginas] == \
        ["Processamento", "Resumo do dia", "Histórico"]
    assert paginas[0]["default"] is True


def test_com_acesso_cr_portal_e_default_sem_paginas_cr():
    paginas = navegacao.montar_paginas(True, admin=True)
    titulos = [p["titulo"] for p in paginas]
    assert titulos[0] == "Início" and paginas[0]["default"] is True
    assert "PF · Processamento" in titulos
    assert not any(t.startswith("CR ·") for t in titulos)
    assert len(paginas) == 5
    assert all(not p["default"] for p in paginas[1:])


def test_com_acesso_cr_nao_admin_portal_sem_administracao():
    paginas = navegacao.montar_paginas(True)
    titulos = [p["titulo"] for p in paginas]
    assert titulos[0] == "Início" and paginas[0]["default"] is True
    assert "PF · Processamento" in titulos
    assert "Administração" not in titulos
    assert len(paginas) == 4


def test_so_acesso_glosa_tambem_ganha_o_portal():
    """12/10: quem tem só o acesso aos Recursos de Glosa vê o Início (é onde
    o card aparece) — antes o portal só entrava com acesso_contas_receber."""
    paginas = navegacao.montar_paginas(False, acesso_glosa=True)
    titulos = [p["titulo"] for p in paginas]
    assert titulos[0] == "Início" and paginas[0]["default"] is True
    assert "PF · Processamento" in titulos
    assert "Administração" not in titulos
    assert len(paginas) == 4
