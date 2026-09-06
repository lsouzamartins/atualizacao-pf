"""Testes do parser do DACM ANS (formato das abas do arquivo da Porto Saúde)."""
import os

import pytest

import parser_dacm
from parser_dacm import _Folha, extrair_dacm, parse_dacm_ans, parsear_data_br

CAMINHO_PORTO = (r"G:\Dashboard - Contas a Receber\Convênios\Porto Saúde"
                 r"\DACM _PORTO_SAÚDE_15.07.26.xls")


def _folha_ans(nome, linhas):
    """Folha fake a partir de lista de linhas (listas de 27 colunas completadas com '')."""
    matriz = []
    for linha in linhas:
        matriz.append(list(linha) + [""] * (27 - len(linha)))
    return _Folha(nome, matriz)


def _cabecalho_fake(prot="20274355", lote="272327", guia="25489130",
                    op="12474769", benef="JEFERSON PASSOS PEREIRA"):
    return [
        ["", "", "", "", "", "", "DEMONSTRATIVO DE ANÁLISE DE CONTA",
         "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "2-Nº", "14880859"],
        ["", "1 - REGISTRO ANS", "", "", "3 - NOME DA OPERADORA", "", "", "", "", "",
         "", "", "", "", "", "", "", "4 - CNPJ DA OPERADORA", "", "", "", "", "", "",
         "5 - DATA DE EMISSÃO"],
        ["", "000582", "", "", "Porto Seguro - Seguro Saude S.A.", "", "", "", "", "",
         "", "", "", "", "", "", "", "04540010000170", "", "", "", "", "", "",
         "16/07/2026"],
        ["", "9 -  NÚMERO DO LOTE", "", "", "10 - NÚMERO DO PROTOCOLO", "", "", "",
         "11 - DATA DO PROTOCOLO", "", "", "12 - CÓDIGO DA GLOSA DO PROTOCOLO",
         "", "", "", "", "", "13 - CÓDIGO DA SITUAÇÃO DO PROTOCOLO"],
        ["", lote, "", "", prot, "", "", "", "12/06/2026", "", "", "", "", "", "",
         "", "", "6"],
        ["", "14 - NÚMERO DA GUIA DO PRESTADOR", "", "", "", "", "", "", "", "",
         "15 - NÚMERO DA GUIA ATRIBUÍDO PELA OPERADORA", "", "", "", "", "",
         "16 - SENHA"],
        ["", guia, "", "", "", "", "", "", "", "", op, "", "", "", "", "", ""],
        ["", "17 - NOME DO BENEFICIÁRIO", "", "", "", "", "", "", "", "", "", "",
         "", "", "", "", "18 - NÚMERO DA CARTEIRA"],
        ["", benef, "", "", "", "", "", "", "", "", "", "", "", "", "", "",
         "2234973211568118"],
        ["", "19 - DATA DO  INÍCIO DO FATURAMENTO", "", "", "", "", "", "20 - HORA",
         "", "21 - DATA DO FIM DO FATURAMENTO", "", "22 - HORA", "", "", "",
         "23 - CÓDIGO DA GLOSA DA GUIA", "", "", "", "", "", "24 - CÓDIGO DA SITUAÇÃO DA GUIA"],
        ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
         "", "", "", "6"],
        ["", "25 - DATA DE REALIZAÇÃO", "", "26 - TABELA", "27 - CÓDIGO DO PROCEDIMENTO",
         "", "", "", "28 - DESCRIÇÃO", "", "", "29 - GRAU DE PARTICIPAÇÃO", "",
         "30 - VALOR INFORMADO", "", "31 - QUANT. EXECUTADA", "32 - VALOR PROCESSADO",
         "", "", "33 - VALOR\nLIBERADO", "", "", "", "", "34 - VALOR GLOSA", "",
         "35 - CÓDIGO DA \nGLOSA"],
        ["", "18/05/2026", "", "22", "10101039", "", "", "", "CONSULTA EM PRONTO SOCORRO",
         "", "", "08", "", 44.22, "", 1.0, 44.22, "", "", 44.22, "", "", "", ""],
        ["", "18/05/2026", "", "22", "40302040", "", "", "", "GLICOSE - PESQUISA E/OU DOSAGEM",
         "", "", "", "", 6.3, "", 1.0, 6.3, "", "", 6.06, "", "", "", "", 0.24, "", "1714"],
        ["", "TOTAL DA GUIA"],
        ["", "36 - VALOR INFORMADO DA GUIA(R$)", "", "", "", "", "", "", "37 - VALOR PROCESSADO DA GUIA(R$)",
         "", "", "38 - VALOR LIBERADO DA GUIA(R$)", "", "", "", "", "39 - VALOR GLOSA DA GUIA(R$)"],
        ["", 50.52, "", "", "", "", "", "", 50.52, "", "", 50.28, "", "", "", "", 0.24],
        ["", "TOTAL DO PROTOCOLO"],
        ["", "40 - VALOR INFORMADO DO PROTOCOLO(R$)", "", "", "", "", "", "", "41 - VALOR PROCESSADO DO PROTOCOLO(R$)",
         "", "", "42 - VALOR LIBERADO DO PROTOCOLO(R$)", "", "", "", "", "43 - VALOR GLOSA DO PROTOCOLO(R$)"],
        ["", 1978.97, "", "", "", "", "", "", 1978.97, "", "", 1943.05, "", "", "", "", 35.92],
        ["", "TOTAL GERAL"],
        ["", "44 - VALOR INFORMADO GERAL(R$)", "", "", "", "", "", "", "45 - VALOR PROCESSADO GERAL(R$)",
         "", "", "46 - VALOR LIBERADO GERAL(R$)", "", "", "", "", "47 - VALOR GLOSA GERAL(R$)"],
        ["", 25276.6, "", "", "", "", "", "", 25276.6, "", "", 24613.4, "", "", "", "", 663.2],
    ]


def _livro_com_duas_folhas_da_mesma_guia():
    folha1 = _folha_ans("Sheet1", _cabecalho_fake())
    # segunda aba da MESMA guia: só os itens continuados + totais repetidos
    linhas2 = _cabecalho_fake()[:12] + [
        ["", "18/05/2026", "", "20", "0000075456", "", "", "", "AGUA DESTILADA 10ML AMP",
         "", "", "", "", 0.77, "", 1.0, 0.77, "", "", 0.77, "", "", "", ""],
        ["", "TOTAL DA GUIA"],
        ["", "36 - VALOR INFORMADO DA GUIA(R$)", "", "", "", "", "", "", "37 - VALOR PROCESSADO DA GUIA(R$)",
         "", "", "38 - VALOR LIBERADO DA GUIA(R$)", "", "", "", "", "39 - VALOR GLOSA DA GUIA(R$)"],
        ["", 51.29, "", "", "", "", "", "", 51.29, "", "", 51.05, "", "", "", "", 0.24],
    ] + _cabecalho_fake()[18:]
    folha2 = _folha_ans("Sheet2", linhas2)
    return [_Folha("Sheet3", [["sem conteúdo"]]), folha1, folha2]


def test_parsear_data_br_converte_e_preserva_nao_iso():
    assert parsear_data_br("16/07/2026") == "2026-07-16"
    assert parsear_data_br("2026-07-16") == "2026-07-16"
    assert parsear_data_br("") == ""


def test_extrai_guia_com_itens_e_totais():
    livro = [_folha_ans("Sheet1", _cabecalho_fake())]
    parsed = extrair_dacm(livro)
    assert parsed["metadados"]["num_dacm"] == "14880859"
    assert parsed["metadados"]["operadora"] == "Porto Seguro - Seguro Saude S.A."
    assert parsed["metadados"]["data_emissao"] == "2026-07-16"
    assert parsed["metadados"]["tot_geral_glosa"] == 663.2
    assert len(parsed["guias"]) == 1
    guia = parsed["guias"][0]
    assert guia["guia_prestador"] == "25489130"
    assert guia["guia_operadora"] == "12474769"
    assert guia["beneficiario"] == "JEFERSON PASSOS PEREIRA"
    assert guia["data_protocolo"] == "2026-06-12"
    assert guia["cod_situacao_guia"] == "6"
    assert guia["vl_glosa"] == 0.24
    assert len(guia["itens"]) == 2
    glosado = [i for i in guia["itens"] if i["vl_glosa"] > 0]
    assert len(glosado) == 1
    assert glosado[0]["cod_glosa"] == "1714"
    assert glosado[0]["descricao"] == "GLICOSE - PESQUISA E/OU DOSAGEM"


def test_concatena_abas_consecutivas_da_mesma_guia():
    livro = _livro_com_duas_folhas_da_mesma_guia()
    parsed = extrair_dacm(livro)
    assert len(parsed["guias"]) == 1
    guia = parsed["guias"][0]
    assert len(guia["itens"]) == 3  # 2 + 1 continuados
    # totais vêm da ÚLTIMA aba da guia
    assert guia["vl_informado"] == 51.29


def test_folha_sem_guia_vira_aviso():
    livro = _livro_com_duas_folhas_da_mesma_guia()
    parsed = extrair_dacm(livro)
    assert any("Sheet3" in a for a in parsed["avisos"])


def test_sem_nenhuma_guia_levanta_erro_claro():
    livro = [_folha_ans("Sheet1", [["vazia"]])]
    with pytest.raises(ValueError, match="Nenhuma guia encontrada"):
        extrair_dacm(livro)


def test_integracao_xlsx_ans(tmp_path):
    """Caminho completo: .xlsx real (openpyxl) -> parse_dacm_ans."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    for linha in _cabecalho_fake():
        ws.append(linha)
    ws2 = wb.create_sheet("Sheet2")
    for linha in _cabecalho_fake()[:12] + [["", "TOTAL DA GUIA"]]:
        ws2.append(linha)
    caminho = tmp_path / "dacm_teste.xlsx"
    wb.save(caminho)
    parsed = parse_dacm_ans(str(caminho))
    assert len(parsed["guias"]) == 1
    assert parsed["metadados"]["num_dacm"] == "14880859"


@pytest.mark.skipif(not os.path.exists(CAMINHO_PORTO),
                    reason="pendrive com o DACM da Porto Saúde não está conectado")
def test_arquivo_real_porto_saude():
    """Valida o parser contra o DACM real da Porto Saúde (somente leitura)."""
    parsed = parse_dacm_ans(CAMINHO_PORTO)
    assert parsed["metadados"]["num_dacm"] == "14880859"
    assert parsed["metadados"]["operadora"] == "Porto Seguro - Seguro Saude S.A."
    assert parsed["metadados"]["tot_geral_glosa"] == 663.2
    # 66 abas; guias quebradas concatenam (73685102 = 5 abas, 74698014 = 5 abas)
    assert 55 <= len(parsed["guias"]) <= 60
    vanessa = next(g for g in parsed["guias"] if g["guia_prestador"] == "73685102")
    assert len(vanessa["itens"]) == 82
    maria = next(g for g in parsed["guias"] if g["guia_prestador"] == "74698014")
    assert len(maria["itens"]) == 71
    # nenhum item com descrição vazia entre as guias
    assert all(i["descricao"] for g in parsed["guias"] for i in g["itens"])
