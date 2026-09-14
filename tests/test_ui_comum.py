import ui_comum


def test_versao_rodape_padronizado():
    """Rodapé padrão (13/09, a pedido — 'deixa todas iguais'): o crédito do
    app passa de 'Criado por' para 'Desenvolvedor:' e a versão vira a da
    rodada 13/09; o rodapé do login usa o MESMO texto."""
    assert ui_comum.VERSAO == ("Desenvolvedor: Leonardo Martins · Revisado por "
                               "Claude Code (Anthropic) · V 4.2026.0913 · "
                               "Streamlit + Lucide")


def test_formatar_data_br_converte_iso_para_br():
    assert ui_comum.formatar_data_br("2026-09-01") == "01-09-2026"
    assert ui_comum.formatar_data_br("2026-01-02") == "02-01-2026"


def test_formatar_data_br_devolve_entrada_quando_nao_e_iso():
    assert ui_comum.formatar_data_br("01-09-2026") == "01-09-2026"
    assert ui_comum.formatar_data_br("") == ""


def test_badge_status_contem_rotulo_e_cor():
    from ui_comum import badge_status
    html = badge_status("A iniciar recurso")
    assert "A iniciar recurso" in html
    assert "#3b82f6" in html
    assert 'class="badge-status"' in html
    html2 = badge_status("Status desconhecido")
    assert "Status desconhecido" in html2  # cai no cinza padrão


def test_icones_das_paginas_cr_existem_no_lucide():
    """Regressão: icone() devolve '' silenciosamente para nomes fora do _LUCIDE —
    os ícones do portal pós-login e das páginas do Contas a Receber precisam
    existir no set para o visual não sumir sem erro."""
    from ui_comum import _LUCIDE
    for nome in ("home", "play-circle", "hand-coins", "layout-dashboard", "upload",
                 "history", "chart-column", "alarm-clock", "bell-ring", "trending-up",
                 "list", "triangle-alert", "percent", "clock", "circle-minus",
                 "file-down"):
        assert nome in _LUCIDE
        assert ui_comum.icone(nome) != ""
