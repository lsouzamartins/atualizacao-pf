"""Testes da montagem de páginas do nav (sem tocar no Streamlit)."""
import navegacao


def test_admin_sem_flags_ve_o_portal_e_o_ponto():
    """06/11: admin sempre tem acesso — o spec manda Início (portal) + Ponto
    no nav mesmo com as permissões próprias zeradas (o banco cria admin sem
    marcar as colunas de acesso, e a Administração não as salva para ele)."""
    paginas = navegacao.montar_paginas(False, admin=True)
    assert [p["titulo"] for p in paginas] == \
        ["Início", "Ponto", "PF · Processamento", "PF · Resumo do dia",
         "PF · Histórico", "PF · Administração"]
    assert paginas[0]["default"] is True
    assert all(not p["default"] for p in paginas[1:])


def test_admin_com_glosa_tambem_tem_a_pagina_ponto():
    """Cenário do card do portal: admin com outra permissão e acesso_ponto
    zerado — o card aparece, então a página precisa existir no nav (senão o
    Abrir Controle de Ponto quebra com 'Could not find page')."""
    paginas = navegacao.montar_paginas(False, acesso_glosa=True, admin=True)
    assert "Ponto" in [p["titulo"] for p in paginas]


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
    assert len(paginas) == 6  # admin também ganha a página Ponto (06/11)
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


def test_ponto_entra_no_nav_com_permissao():
    paginas = navegacao.montar_paginas(False, acesso_ponto=True)
    titulos = [p["titulo"] for p in paginas]
    assert titulos[0] == "Início" and paginas[0]["default"] is True
    assert titulos[1] == "Ponto"
    assert "PF · Processamento" in titulos
    assert "Administração" not in titulos


def test_sem_permissao_ponto_nao_aparece():
    paginas = navegacao.montar_paginas(False)
    assert "Ponto" not in [p["titulo"] for p in paginas]
