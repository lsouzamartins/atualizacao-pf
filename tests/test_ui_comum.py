import ui_comum


def test_formatar_data_br_converte_iso_para_br():
    assert ui_comum.formatar_data_br("2026-09-01") == "01-09-2026"
    assert ui_comum.formatar_data_br("2026-01-02") == "02-01-2026"


def test_formatar_data_br_devolve_entrada_quando_nao_e_iso():
    assert ui_comum.formatar_data_br("01-09-2026") == "01-09-2026"
    assert ui_comum.formatar_data_br("") == ""
