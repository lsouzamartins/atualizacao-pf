"""Testes da montagem de páginas do nav (sem tocar no Streamlit)."""
import navegacao


def test_sem_acesso_cr_nav_fica_como_hoje():
    paginas = navegacao.montar_paginas(False)
    assert [p["titulo"] for p in paginas] == \
        ["Processamento", "Resumo do dia", "Histórico", "Administração"]
    assert paginas[0]["default"] is True
    assert all(not p["titulo"].startswith(("PF ·", "CR ·")) for p in paginas)


def test_com_acesso_cr_portal_e_default_e_prefixos():
    paginas = navegacao.montar_paginas(True)
    titulos = [p["titulo"] for p in paginas]
    assert titulos[0] == "Início" and paginas[0]["default"] is True
    assert "PF · Processamento" in titulos
    assert "CR · Dashboard" in titulos
    assert "CR · Upload DACM" in titulos
    assert "CR · Recursos de Glosa" in titulos
    assert len(paginas) == 8
    assert all(not p["default"] for p in paginas[1:])
