import ui_comum


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
