"""Testes do motor cirúrgico integracao_excel.py.

A fixture base é um .xlsx SINTÉTICO escrito à mão (partes XML em dict),
reproduzindo a anatomia do arquivo real: sharedStrings + tabelas + calcPr
sem fullCalcOnLoad + caches embutidos (defs/records/rels) + timelines +
slicerCaches + pivotFields posicionais. O openpyxl nunca grava o Hias real —
aqui ele só LÊ (fixture e gate), e os arquivos WPD/limpo sintéticos podem
usar pandas.
"""
import re
import zipfile
from datetime import date, datetime

import pandas as pd
import pytest

import integracao_excel as ie

DECL = ie._DECL


def _sst(textos):
    sis = "".join(f"<si><t>{t}</t></si>" for t in textos)
    return (DECL
            + '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
              f'count="9" uniqueCount="{len(textos)}">{sis}</sst>')


# ==============================================================================
# Lógica herdada do core.py (contrato verbatim)
# ==============================================================================
def test_normalizar_remessa_formas():
    assert ie._normalizar_remessa(117129) == "117129"
    assert ie._normalizar_remessa(117129.0) == "117129"
    assert ie._normalizar_remessa(" 117129 ") == "117129"


def test_identificar_linhas_novas_bd1():
    df = pd.DataFrame({"Remessa": [117129.0, "200002 (R)", 200003],
                       "Emissão": [pd.Timestamp("2026-08-31")] * 3})
    novas = ie.identificar_linhas_novas_bd1(df, {"117129"})
    assert list(novas["Remessa"]) == ["200002 (R)", "200003"]


# ==============================================================================
# sharedStrings
# ==============================================================================
def test_strings_compartilhadas_acrescenta_e_conta():
    s = ie._StringsCompartilhadas(_sst(["CONVÊNIO A", "CONVÊNIO B"]))
    assert s.obter_indice("CONVÊNIO A") == 0
    assert s.obter_indice("CONVÊNIO C") == 2
    xml = s.para_xml(novas_celulas=1)
    assert xml.count("<si>") == 3
    assert 'count="10"' in xml
    assert 'uniqueCount="3"' in xml
    assert '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"' in xml


# ==============================================================================
# Montagem de linhas (BD1 e BD2)
# ==============================================================================
def test_linha_bd2_estilos_e_referencias():
    """Linha nova da BD2 com os MESMOS estilos das linhas existentes: A s=5
    (fonte escura — s=34 era fonte branca, nome invisível) e C–I s=49
    (máscara #,##0.00 — s=53 era fundo amarelo sem máscara)."""
    s = ie._StringsCompartilhadas(_sst(["ALGUM CONVÊNIO"]))
    linha = ie._linha_bd2(806, "ALGUM CONVÊNIO", 45001,
                          [1.5, 2.0, None, 1000, 0.0, 0.0, 0.0], s)
    assert '<row r="806">' in linha
    assert '<c r="A806" s="5" t="s"><v>0</v></c>' in linha
    assert '<c r="B806" s="16"><v>45001</v></c>' in linha
    assert '<c r="C806" s="49"><v>1.5</v></c>' in linha
    assert '<c r="D806" s="49"><v>2</v></c>' in linha
    assert '<c r="E806" s="49"/>' in linha
    assert '<c r="J806" s="17"><v>1</v></c>' in linha


def test_linha_bd1_formulas_e_cache_da_coluna_v():
    s = ie._StringsCompartilhadas(_sst(["HOSPITAL ABC"]))
    dados = {"Remessa": "139159 (R)", "Protocolo": 118,
             "Emissão": date(2026, 8, 31), "Vencimento": date(2026, 9, 30),
             "Entrega": None, "Baixa": None, "Nota Fiscal": None,
             "Convênio": "HOSPITAL ABC", "Faturado": 100.0, "Valor Pago": 100.0,
             "Valor ISS": 5.0, "Vlr Guia": 100.0, "% Pré-glosa": 0.0,
             "Valor Glosa": 0.0, "% Glosa": 0.0, "Atraso": 0.0, "Faturas": 1.0}
    linha, refs = ie._linha_bd1_nova(34112, dados, s)
    serial_emissao = (date(2026, 8, 31) - ie.SERIAL_EPOCA).days
    assert refs == 2  # A (string) + H (convênio)
    # a remessa "139159 (R)" é acrescentada ao fim (índice 1); H usa o índice 0
    assert '<c r="A34112" s="36" t="s"><v>1</v></c>' in linha
    assert '<c r="B34112" s="45"><v>118</v></c>' in linha
    assert f'<c r="C34112" s="46"><v>{serial_emissao}</v></c>' in linha
    assert '<c r="E34112" s="46"/>' in linha   # Entrega vazia
    assert '<c r="F34112" s="57"/>' in linha   # Baixa vazia usa s=57
    assert '<c r="H34112" s="14" t="s"><v>0</v></c>' in linha
    assert ('<c r="R34112" s="41"><f>=SUMIFS(L34112,D34112,"&lt;"&amp;TODAY(),F34112,"")</f></c>'
            in linha)
    assert ('<c r="V34112" s="43" t="str"><f>=IF(RIGHT(A34112,3)="(R)","Recurso","Comum")</f><v>Recurso</v></c>'
            in linha)


def test_linha_bd1_remessa_numerica_sem_string():
    s = ie._StringsCompartilhadas(_sst(["HOSPITAL ABC"]))
    dados = {"Remessa": 200001, "Protocolo": "118-A",  # protocolo string vira t="str"
             "Emissão": date(2026, 8, 31), "Vencimento": date(2026, 9, 30),
             "Entrega": None, "Baixa": None, "Nota Fiscal": None,
             "Convênio": "HOSPITAL ABC", "Faturado": 100.0, "Valor Pago": 100.0,
             "Valor ISS": 5.0, "Vlr Guia": 100.0, "% Pré-glosa": 0.0,
             "Valor Glosa": 0.0, "% Glosa": 0.0, "Atraso": 0.0, "Faturas": 1.0}
    linha, refs = ie._linha_bd1_nova(34113, dados, s)
    assert refs == 1  # só o H é string
    assert '<c r="A34113" s="36"><v>200001</v></c>' in linha
    assert '<c r="B34113" s="45" t="str"><v>118-A</v></c>' in linha
    assert '<c r="V34113" s="43" t="str">' in linha
    assert '<v>Comum</v>' in linha  # cache da V para remessa numérica


# ==============================================================================
# Edição da BD2
# ==============================================================================
XML_BD2_MINI = (
    DECL
    + '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    + '<dimension ref="A1:J808"/>'
    + '<sheetData>'
    + '<row r="1" spans="1:10"><c r="A1" s="34" t="s"><v>0</v></c></row>'
    + '<row r="2" spans="1:10"><c r="A2" s="34" t="s"><v>1</v></c><c r="B2" s="35"><v>45000</v></c></row>'
    + '<row r="805" spans="1:10"><c r="A805" s="34" t="s"><v>1</v></c></row>'
    + '<row r="806" spans="1:10"><c r="A806" s="5" t="s"><v>2</v></c></row>'
    + '<row r="808" spans="1:10"><c r="A808" s="16"><v>7</v></c></row>'
    + '</sheetData>'
    + '</worksheet>'
)


def test_editar_bd2_preserva_base_deduplica_e_insere():
    s = ie._StringsCompartilhadas(_sst(["CABEÇALHO", "Convênio ", "OBJETO"]))
    xml, fim, novas_celulas, mapeamento, novas, atualizacoes = ie._editar_bd2(
        XML_BD2_MINI,
        [{"convenio": "Convênio", "data": 45001,
          "valores": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]},
         # chave já existente (Convênio + serial 45000 da linha 2) com valores
         # diferentes — upsert: atualiza a linha 2 em vez de anexar
         {"convenio": "Convênio", "data": 45000,
          "valores": [9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0]}],
        s)
    assert fim == 809
    assert novas_celulas == 1
    assert len(novas) == 1
    assert novas[0]["convenio"] == "Convênio" and novas[0]["data"] == 45001
    assert len(atualizacoes) == 1
    assert atualizacoes[0]["linha"] == 2 and atualizacoes[0]["record"] == 0
    assert atualizacoes[0]["valores"] == ["9"] * 7
    assert mapeamento == {"Convênio ": "Convênio"}
    assert '<c r="C2" s="49"><v>9</v></c>' in xml   # upsert na linha 2
    # todas as linhas da base preservadas
    assert '<c r="A806" s="5"' in xml
    assert '<c r="A808"' in xml
    # coluna A normalizada: "Convênio " -> "Convênio" (si novo = índice 3)
    assert '<c r="A2" s="34" t="s"><v>3</v></c>' in xml
    assert '<c r="A805" s="34" t="s"><v>3</v></c>' in xml
    # linha nova começa em 809 (fim atual + 1), com a data em estilo mm-dd-yy
    assert '<c r="A809" s="5" t="s"><v>3</v></c>' in xml
    assert '<c r="B809" s="16"><v>45001</v></c>' in xml
    assert '<c r="J809" s="17"><v>1</v></c>' in xml
    # dimension
    assert 'ref="A1:J809"' in xml
    assert 'ref="A1:J808"' not in xml


def test_editar_bd2_upsert_atualiza_linha_com_chave_existente():
    """Linha do NI com chave já existente e VALOR DIFERENTE deve ATUALIZAR a
    linha da base (upsert) — a edição do usuário no NI prevalece (causa raiz
    do reporte de 05/09: valor editado no NI voltou ao original)."""
    s = ie._StringsCompartilhadas(_sst(["CABEÇALHO", "Convênio ", "OBJETO"]))
    xml, fim, novas_celulas, mapeamento, novas, atualizacoes = ie._editar_bd2(
        XML_BD2_MINI,
        [{"convenio": "Convênio", "data": 45000,   # chave da linha 2 existente
          "valores": [9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0]}],
        s)
    assert fim == 808                        # nenhuma linha nova
    assert novas_celulas == 0
    assert novas == []
    assert mapeamento == {"Convênio ": "Convênio"}
    assert len(atualizacoes) == 1
    att = atualizacoes[0]
    assert att["linha"] == 2
    assert att["record"] == 0                # record 0 = linha 2
    assert att["valores"] == ["9", "8", "7", "6", "5", "4", "3"]
    # células C2:I2 ganham os novos valores (s="49" como as numéricas da BD2)
    assert '<c r="C2" s="49"><v>9</v></c>' in xml
    assert '<c r="I2" s="49"><v>3</v></c>' in xml
    assert '<c r="A2" s="34" t="s"><v>3</v></c>' in xml   # convênio normalizado
    assert '<c r="B2" s="35"><v>45000</v></c>' in xml     # data preservada
    assert 'ref="A1:J808"' in xml


def test_editar_bd2_chave_existente_com_valores_iguais_e_pulada():
    """Dedupe puro: chave existente com os MESMOS valores não gera nada."""
    xml_base = (DECL
                + '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                + '<dimension ref="A1:J2"/>'
                + '<sheetData>'
                + '<row r="1" spans="1:10"><c r="A1" s="34" t="s"><v>0</v></c></row>'
                + '<row r="2" spans="1:10"><c r="A2" s="34" t="s"><v>1</v></c>'
                + '<c r="B2" s="35"><v>45000</v></c>'
                + '<c r="C2" s="49"><v>1</v></c><c r="D2" s="49"><v>2</v></c>'
                + '<c r="E2" s="49"><v>3</v></c><c r="F2" s="49"><v>4</v></c>'
                + '<c r="G2" s="49"><v>5</v></c><c r="H2" s="49"><v>6</v></c>'
                + '<c r="I2" s="49"><v>7</v></c></row>'
                + '</sheetData>'
                + '</worksheet>')
    s = ie._StringsCompartilhadas(_sst(["CABEÇALHO", "Convênio"]))
    xml, fim, novas_celulas, mapeamento, novas, atualizacoes = ie._editar_bd2(
        xml_base,
        [{"convenio": "Convênio", "data": 45000,
          "valores": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]}],
        s)
    assert xml is None and fim is None          # nada mudou
    assert novas == [] and atualizacoes == []


def test_editar_bd2_upsert_nao_toca_string_nem_repr_de_float():
    """Comparação SEMÂNTICA: célula t='s' (string histórica) e repr de float
    equivalente ('610.41999999999996' vs 610.42) ficam intocadas — só o valor
    numericamente diferente é atualizado (e a célula ausente é criada)."""
    xml_base = (DECL
                + '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                + '<dimension ref="A1:J2"/>'
                + '<sheetData>'
                + '<row r="1" spans="1:10"><c r="A1" s="34" t="s"><v>0</v></c></row>'
                + '<row r="2" spans="1:10"><c r="A2" s="34" t="s"><v>1</v></c>'
                + '<c r="B2" s="35"><v>45000</v></c>'
                + '<c r="C2" s="49"><v>610.41999999999996</v></c>'
                + '<c r="E2" s="49" t="s"><v>107</v></c></row>'
                + '</sheetData>'
                + '</worksheet>')
    s = ie._StringsCompartilhadas(_sst(["CABEÇALHO", "Convênio"]))
    xml, fim, nc, mapa, novas, atts = ie._editar_bd2(
        xml_base,
        [{"convenio": "Convênio", "data": 45000,
          "valores": [610.42, 9.0, 0.0, None, None, None, None]}],
        s)
    assert fim == 2
    assert novas == [] and nc == 0
    assert len(atts) == 1
    assert atts[0]["valores"] == [None, "9", None, None, None, None, None]
    assert '<c r="C2" s="49"><v>610.41999999999996</v></c>' in xml  # repr intocado
    assert '<c r="E2" s="49" t="s"><v>107</v></c>' in xml             # string intocada
    assert '<c r="D2" s="49"><v>9</v></c>' in xml                     # ausente criada


def test_editar_bd2_quitacao_converte_string_de_espacos_em_numero():
    """Quitação registrada no NI (valor ≠ 0) em célula t='s' de espaços deve
    converter a célula para número s=49 — defeito de 11/09: as quitações de
    02/09 (10,69 / 17.151,47 / 18.730) não apareciam na BD2. String de espaços
    com NI=0 (vazio histórico) e string com conteúdo real ficam intocadas."""
    s = ie._StringsCompartilhadas(
        _sst(["CABEÇALHO", "Convênio", "              ", "TEXTO REAL"]))
    xml_base = (DECL
                + '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                + '<dimension ref="A1:J2"/>'
                + '<sheetData>'
                + '<row r="1" spans="1:10"><c r="A1" s="34" t="s"><v>0</v></c></row>'
                + '<row r="2" spans="1:10"><c r="A2" s="5" t="s"><v>1</v></c>'
                + '<c r="B2" s="16"><v>45000</v></c>'
                + '<c r="E2" s="49" t="s"><v>2</v></c>'      # espaços
                + '<c r="G2" s="49" t="s"><v>3</v></c>'      # texto real
                + '<c r="H2" s="49" t="s"><v>2</v></c></row>'  # espaços
                + '</sheetData>'
                + '</worksheet>')
    xml, fim, nc, mapa, novas, atts = ie._editar_bd2(
        xml_base,
        [{"convenio": "Convênio", "data": 45000,
          "valores": [1.0, 2.0, 10.69, 4.0, 5.0, 0.0, 7.0]}],  # E=10,69 H=0
        s)
    assert fim == 2
    assert novas == [] and nc == 0
    assert len(atts) == 1
    # E: espaços + NI=10,69 -> número s=49 (a quitação aparece)
    assert '<c r="E2" s="49"><v>10.69</v></c>' in xml
    # H: espaços + NI=0 -> intocada; G: texto real -> intocada
    assert '<c r="H2" s="49" t="s"><v>2</v></c>' in xml
    assert '<c r="G2" s="49" t="s"><v>3</v></c>' in xml
    assert atts[0]["valores"][2] == "10.69"       # E entra no upsert do record
    assert atts[0]["valores"][5] is None          # H fora


def test_editar_bd2_sem_mudanca_devolve_none():
    xml_limpo = (DECL
                 + '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                 + '<dimension ref="A1:J2"/>'
                 + '<sheetData>'
                 + '<row r="1" spans="1:10"><c r="A1" s="34" t="s"><v>0</v></c></row>'
                 + '<row r="2" spans="1:10"><c r="A2" s="34" t="s"><v>1</v></c></row>'
                 + '</sheetData>'
                 + '</worksheet>')
    s = ie._StringsCompartilhadas(_sst(["CABEÇALHO", "Convênio"]))
    xml, fim, n, mapeamento, novas, atualizacoes = ie._editar_bd2(xml_limpo, None, s)
    assert xml is None and fim is None and n == 0
    assert mapeamento == {} and novas == [] and atualizacoes == []


# ==============================================================================
# Partes auxiliares
# ==============================================================================
def test_ajustar_cache1_ref_atualizado():
    xml = (DECL
           + '<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
           + '<cacheSource type="worksheet"><worksheetSource ref="A1:I1020" sheet="BD2"/></cacheSource>'
           + '</pivotCacheDefinition>')
    saida = ie._ajustar_cache1(xml, 812)
    assert 'ref="A1:I812"' in saida


def test_ajustar_workbook_calcpr_e_nome_definido():
    xml = (DECL
           + '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
           + '<calcPr calcId="191029"/>'
           + '<definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="4">'
           + "'BD1'!$A$1:$V$34111</definedName></definedNames></workbook>")
    saida = ie._ajustar_workbook(xml, 34250, calc_completo=True)
    assert 'fullCalcOnLoad="1"' in saida
    assert "'BD1'!$A$1:$V$34250" in saida
    # sem calc_completo não mexe no calcPr
    intacto = ie._ajustar_workbook(xml, 34250, calc_completo=False)
    assert 'fullCalcOnLoad' not in intacto
    assert "'BD1'!$A$1:$V$34250" in intacto


def test_ajustar_tabela_atualiza_refs():
    xml = (DECL
           + '<table xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
           + 'id="2" name="BD_1" displayName="BD_1" ref="A1:V34111" '
           + 'totalsRowShown="0"><autoFilter ref="A1:V34111"/></table>')
    saida = ie._ajustar_tabela(xml, "A1:V", 34250)
    assert saida.count('ref="A1:V34250"') == 2


# ==============================================================================
# Helper _substituir_ou_falhar (M7): falha alta em substituição sem casamento
# ==============================================================================
def test_substituir_ou_falhar_sem_casamento_levanta():
    with pytest.raises(RuntimeError, match="Padrão não encontrado em dimension da BD2"):
        ie._substituir_ou_falhar(r'<dimension ref="A1:J\d+"/>',
                                 '<dimension ref="A1:J9"/>',
                                 "<worksheet><sheetData/></worksheet>",
                                 "dimension da BD2")


def test_substituir_ou_falhar_com_casamento_substitui():
    xml = '<dimension ref="A1:J2"/>'
    saida = ie._substituir_ou_falhar(
        r'<dimension ref="A1:J(\d+)"/>',
        lambda m: f'<dimension ref="A1:J{int(m.group(1)) + 1}"/>',
        xml, "dimension da BD2")
    assert saida == '<dimension ref="A1:J3"/>'


# ==============================================================================
# Integração completa (fixture sintética escrita à mão)
# ==============================================================================
def _pivot_campos_bd1():
    """22 pivotFields posicionais (índice = posição no cache da BD1).
    Campos com <items>: 0 Remessa, 1 Protocolo, 3 Vencimento, 4 Entrega,
    5 Baixa, 7 Convênio, 21 Tipo (com missing m=1 e default, como o Excel)."""
    simples = '<pivotField showAll="0"/>'
    campos = []
    for i in range(22):
        if i == 5:
            campos.append('<pivotField axis="axisRow" showAll="0">'
                          '<items count="2"><item x="0"/><item x="1"/></items>'
                          '</pivotField>')
        elif i == 21:
            campos.append('<pivotField axis="axisRow" showAll="0">'
                          '<items count="4"><item x="0"/><item x="1"/>'
                          '<item m="1" x="2"/><item t="default"/></items>'
                          '</pivotField>')
        elif i in (0, 1, 3, 4, 7):
            campos.append('<pivotField axis="axisRow" showAll="0">'
                          '<items count="1"><item x="0"/></items></pivotField>')
        else:
            campos.append(simples)
    return "".join(campos)


def _pivot_campos_bd2():
    """9 pivotFields da pivô À Quitar (cache BD2): 0 Convênio e 1 Data com items."""
    simples = '<pivotField showAll="0"/>'
    campos = []
    for i in range(9):
        if i in (0, 1):
            campos.append('<pivotField axis="axisRow" showAll="0">'
                          '<items count="1"><item x="0"/></items></pivotField>')
        else:
            campos.append(simples)
    return "".join(campos)


def _criar_base(tmp_path, sem_dimension_bd2=False):
    """Hias sintético mínimo com a anatomia do real: BD1/BD2 + sharedStrings +
    tabelas + calcPr sem fullCalcOnLoad + caches embutidos (defs/records/rels)
    + 2 timelines + 7 slicerCaches + pivôs com pivotFields posicionais.
    Escrito à mão porque o openpyxl 3.1.5 usa strings inline (o motor exige
    sharedStrings). Os caches/pivôs nascem COM refreshOnLoad="1" (estado do
    template da nuvem) — a FASE 3c deve removê-lo.
    sem_dimension_bd2=True gera uma BD2 sem <dimension> (fixture de falha)."""
    ser_ago = (date(2026, 8, 31) - ie.SERIAL_EPOCA).days
    ser_set = (date(2026, 9, 30) - ie.SERIAL_EPOCA).days

    cabecalho_bd1 = ["Remessa", "Protocolo", "Emissão", "Vencimento", "Entrega",
                     "Baixa", "Nota Fiscal", "Convênio", "Faturado", "Valor Pago",
                     "Valor ISS", "Vlr Guia", "% Pré-glosa", "Valor Glosa", "% Glosa",
                     "Atraso", "Faturas", "R", "S", "T", "U", "V"]
    cabecalho_bd2 = ["Convênio", "Data", "Dep. Líq.", "Dep. Bruto", "Quitação",
                     "Não Identificado", "Acordos", "Glosa Aceita", "NI Real", "FLAG"]
    textos_sst = cabecalho_bd1 + ["HOSPITAL ABC", "Convênio Z "] + cabecalho_bd2
    sis = "".join(f'<si><t xml:space="preserve">{t}</t></si>' if t.endswith(" ")
                  else f"<si><t>{t}</t></si>" for t in textos_sst)
    shared = (DECL
              + '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
              + f'count="34" uniqueCount="{len(textos_sst)}">{sis}</sst>')

    letras_bd1 = "ABCDEFGHIJKLMNOPQRSTUV"
    cel_bd1_header = "".join(f'<c r="{c}1" t="s"><v>{i}</v></c>'
                             for i, c in enumerate(letras_bd1))
    row2_bd1 = ('<row r="2">'
                '<c r="A2"><v>117129</v></c>'
                '<c r="B2"><v>118</v></c>'
                f'<c r="C2"><v>{ser_ago}</v></c>'
                f'<c r="D2"><v>{ser_set}</v></c>'
                '<c r="H2" t="s"><v>22</v></c>'          # HOSPITAL ABC
                '<c r="I2"><v>100</v></c><c r="J2"><v>100</v></c><c r="K2"><v>5</v></c>'
                '<c r="L2"><v>100</v></c><c r="M2"><v>0</v></c><c r="N2"><v>0</v></c>'
                '<c r="O2"><v>0</v></c><c r="P2"><v>0</v></c><c r="Q2"><v>1</v></c>'
                '</row>')

    letras_bd2 = "ABCDEFGHIJ"
    cel_bd2_header = "".join(f'<c r="{c}1" t="s"><v>{24 + i}</v></c>'
                             for i, c in enumerate(letras_bd2))
    row2_bd2 = ('<row r="2">'
                '<c r="A2" t="s"><v>23</v></c>'          # "Convênio Z "
                f'<c r="B2"><v>{ser_ago}</v></c>'
                + "".join(f'<c r="{c}2"><v>{n}</v></c>'
                          for c, n in zip("CDEFGHI", [1, 2, 3, 4, 5, 6, 7]))
                + '<c r="J2"><v>1</v></c>'
                + '</row>')

    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    sheet1 = (DECL + f'<worksheet {ns}><dimension ref="A1:A1"/><sheetData>'
              + '<row r="1"><c r="A1" t="s"><v>24</v></c></row></sheetData></worksheet>')
    sheet5 = (DECL + f'<worksheet {ns}><dimension ref="A1:V2"/><sheetData>'
              + f'<row r="1">{cel_bd1_header}</row>{row2_bd1}</sheetData></worksheet>')
    dimension_bd2 = '<dimension ref="A1:J2"/>' if not sem_dimension_bd2 else ""
    sheet6 = (DECL + f'<worksheet {ns}>{dimension_bd2}<sheetData>'
              + f'<row r="1">{cel_bd2_header}</row>{row2_bd2}</sheetData></worksheet>')

    def tabela(id_, nome, ref, colunas):
        cols = "".join(f'<tableColumn id="{i}" name="{c}"/>'
                       for i, c in enumerate(colunas, 1))
        return (DECL + f'<table {ns} id="{id_}" name="{nome}" displayName="{nome}" '
                + f'ref="{ref}" totalsRowShown="0"><autoFilter ref="{ref}"/>'
                + f'<tableColumns count="{len(colunas)}">{cols}</tableColumns>'
                + '<tableStyleInfo name="TableStyleMedium2" showFirstColumn="0" '
                + 'showLastColumn="0" showRowStripes="1" showColumnStripes="0"/></table>')

    table1 = tabela(1, "BD_1", "A1:V2", cabecalho_bd1)
    # no arquivo real a tabela da BD2 cobre só A1:I (a coluna J/FLAG fica fora)
    table2 = tabela(2, "Tabela1", "A1:I2", cabecalho_bd2[:9])

    # pivôs com pivotFields posicionais e refreshOnLoad="1" (estado do template
    # da nuvem — a FASE 3c remove); cacheIds da investigação: pivôs 1–3 = 1
    # (cache da BD1), pivô 4 = 0 (cache da BD2)
    pivots = []
    for num, cache_id, campos in ((1, 1, _pivot_campos_bd1()),
                                  (2, 1, _pivot_campos_bd1()),
                                  (3, 1, _pivot_campos_bd1()),
                                  (4, 0, _pivot_campos_bd2())):
        pivots.append((f"xl/pivotTables/pivotTable{num}.xml",
                       DECL + f'<pivotTableDefinition {ns} name="Tabela dinâmica{num}" '
                       + f'cacheId="{cache_id}" applyNumberFormats="0" refreshOnLoad="1">'
                       + '<location ref="A1:B5" firstHeaderRow="1"/>'
                       + f'<pivotFields count="{campos.count("<pivotField")}">{campos}</pivotFields>'
                       + '</pivotTableDefinition>'))

    # caches embutidos: def1 = BD2 (worksheetSource ref A1:I), def2 = BD1
    # (worksheetSource name="BD_1"); campos com sharedItems recebem x-ref nos
    # records — os demais são auto-contidos (d/n/m inline), como no real.
    ns_r = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    campos_bd1 = [
        '<cacheField name="Remessa" numFmtId="0"><sharedItems count="1"><n v="117129"/></sharedItems></cacheField>',
        '<cacheField name="Protocolo" numFmtId="0"><sharedItems count="1"><n v="118"/></sharedItems></cacheField>',
        '<cacheField name="Emissão" numFmtId="14"/>',
        '<cacheField name="Vencimento" numFmtId="14"><sharedItems count="1"><d v="2026-09-30T00:00:00"/></sharedItems></cacheField>',
        '<cacheField name="Entrega" numFmtId="14"><sharedItems count="1"><d v="2026-08-20T00:00:00"/></sharedItems></cacheField>',
        '<cacheField name="Baixa" numFmtId="14"><sharedItems count="2"><m/><d v="2026-08-31T00:00:00"/></sharedItems></cacheField>',
        '<cacheField name="Nota Fiscal" numFmtId="0"/>',
        '<cacheField name="Convênio" numFmtId="0"><sharedItems count="1"><s v="HOSPITAL ABC"/></sharedItems></cacheField>',
    ] + [f'<cacheField name="{n}" numFmtId="0"/>' for n in (
        "Faturado", "Valor Pago", "Valor ISS", "Vlr Guia", "% Pré-glosa",
        "Valor Glosa", "% Glosa", "Atraso", "Faturas",
        "Atrasado", "A vencer", "Recurso", "Recurso pago")] + [
        '<cacheField name="Tipo de remessa" numFmtId="0">'
        '<sharedItems count="3"><s v="Comum"/><s v="Recurso"/><m/></sharedItems></cacheField>',
    ]
    campos_bd2 = [
        '<cacheField name="Convênio" numFmtId="0"><sharedItems count="1"><s v="Convênio Z "/></sharedItems></cacheField>',
        '<cacheField name="Data" numFmtId="14"><sharedItems count="1"><d v="2026-08-31T00:00:00"/></sharedItems></cacheField>',
    ] + [f'<cacheField name="{n}" numFmtId="0"/>' for n in (
        "Dep Líq", "Dep Bruto", "Quitação", "Não Identificado", "Acordos",
        "Glosa Aceita", "NI Real")]

    def1 = (DECL + f'<pivotCacheDefinition {ns} {ns_r} '
            + 'refreshedBy="Sistema" refreshedDate="46200.0" recordCount="1" '
            + 'createdVersion="7" refreshedVersion="7" refreshOnLoad="1">'
            + '<cacheSource type="worksheet"><worksheetSource ref="A1:I2" sheet="BD2"/></cacheSource>'
            + f'<cacheFields count="9">{"".join(campos_bd2)}</cacheFields>'
            + '</pivotCacheDefinition>')
    def2 = (DECL + f'<pivotCacheDefinition {ns} {ns_r} '
            + 'refreshedBy="Sistema" refreshedDate="46200.0" recordCount="1" '
            + 'createdVersion="7" refreshedVersion="7" refreshOnLoad="1">'
            + '<cacheSource type="worksheet"><worksheetSource name="BD_1"/></cacheSource>'
            + f'<cacheFields count="22">{"".join(campos_bd1)}</cacheFields>'
            + '</pivotCacheDefinition>')

    # records iniciais espelhando as linhas 2 (formato do Excel na referência:
    # x-ref para campos com sharedItems, d/n/m inline nos demais)
    rec_bd1 = (DECL + f'<pivotCacheRecords {ns} {ns_r} count="1"><r>'
               + '<x v="0"/><x v="0"/>'                          # Remessa, Protocolo
               + '<d v="2026-08-31T00:00:00"/>'                  # Emissão inline
               + '<x v="0"/>'                                    # Vencimento
               + '<m/>'                                          # Entrega (sem blank)
               + '<x v="0"/>'                                    # Baixa → blank
               + '<m/>'                                          # NF
               + '<x v="0"/>'                                    # Convênio
               + '<n v="100"/><n v="100"/><n v="5"/><n v="100"/>'
               + '<n v="0"/><n v="0"/><n v="0"/><n v="0"/><n v="1"/>'
               + '<n v="0"/><n v="100"/><n v="0"/><n v="0"/>'    # R–U calculadas
               + '<x v="0"/>'                                    # Tipo (Comum)
               + '</r></pivotCacheRecords>')
    rec_bd2 = (DECL + f'<pivotCacheRecords {ns} {ns_r} count="1"><r>'
               + '<x v="0"/><x v="0"/>'                          # Convênio, Data
               + '<n v="1"/><n v="2"/><n v="3"/><n v="4"/>'
               + '<n v="5"/><n v="6"/><n v="7"/>'
               + '</r></pivotCacheRecords>')

    def rels_def(n_rec):
        return (DECL
                + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                + '<Relationship Id="rId1" '
                + 'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheRecords" '
                + f'Target="pivotCacheRecords{n_rec}.xml"/></Relationships>')

    # timeline "Entrega" (tabId 3) com filterType="unknown" — a FASE 3c fixa a
    # janela do mês de fechamento; "Vencimento" (tabId 6) fica intocada.
    ns9 = 'xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"'
    timeline1 = (DECL + f'<timelineCache {ns9} {ns_r} sourceName="Entrega" name="TimelineEntrega1">'
                 + '<pivotTables><pivotTable tabId="3" name="Data Entrega"/></pivotTables>'
                 + '<state filterType="unknown" startDate="2024-01-01T00:00:00" '
                 + 'endDate="2027-01-01T00:00:00">'
                 + '<bounds startDate="2024-01-01T00:00:00" endDate="2027-01-01T00:00:00"/>'
                 + '</state></timelineCache>')
    timeline2 = (DECL + f'<timelineCache {ns9} {ns_r} sourceName="Vencimento" name="TimelineVencimento2">'
                 + '<pivotTables><pivotTable tabId="6" name="Data Vencimento"/></pivotTables>'
                 + '<state filterType="unknown" startDate="2024-01-01T00:00:00" '
                 + 'endDate="2027-01-01T00:00:00">'
                 + '<bounds startDate="2024-01-01T00:00:00" endDate="2027-01-01T00:00:00"/>'
                 + '</state></timelineCache>')

    # 7 slicerCaches na ordem da referência: 1 Convênio tab3, 2 Convênio tab6,
    # 3 Tipo tab3, 4 Tipo tab11, 5 Convênio tab11, 6 Tipo tab6, 7 Convênio tab8
    def slicer(nome, tab_id, fonte, n_itens):
        itens = "".join(f'<i x="{i}" s="1"/>' for i in range(n_itens))
        return (DECL + f'<slicerCache {ns9} sourceName="{fonte}" name="SegmentaçãoDeDados{nome}">'
                + f'<pivotTables><pivotTable tabId="{tab_id}" name="Pivot{tab_id}"/></pivotTables>'
                + f'<items count="{n_itens}">{itens}</items></slicerCache>')

    slicers = {
        "xl/slicerCaches/slicerCache1.xml": slicer(1, 3, "Convênio", 1),
        "xl/slicerCaches/slicerCache2.xml": slicer(2, 6, "Convênio", 1),
        "xl/slicerCaches/slicerCache3.xml": slicer(3, 3, "Tipo de remessa", 3),
        "xl/slicerCaches/slicerCache4.xml": slicer(4, 11, "Tipo de remessa", 3),
        "xl/slicerCaches/slicerCache5.xml": slicer(5, 11, "Convênio", 1),
        "xl/slicerCaches/slicerCache6.xml": slicer(6, 6, "Tipo de remessa", 3),
        "xl/slicerCaches/slicerCache7.xml": slicer(7, 8, "Convênio", 1),
    }

    slicer_view = ('<slicer xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" '
                   'name="SegmentaçãoDeDados1"><preservar>BYTES</preservar></slicer>')

    workbook = (DECL
                + f'<workbook {ns} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                + '<calcPr calcId="191029"/>'
                + '<sheets>'
                + '<sheet name="À Quitar" sheetId="1" r:id="rId1"/>'
                + '<sheet name="BD1" sheetId="5" r:id="rId5"/>'
                + '<sheet name="BD2" sheetId="6" r:id="rId6"/>'
                + '</sheets>'
                + '<definedNames>'
                + '<definedName name="_xlnm._FilterDatabase" localSheetId="1">'
                + "'BD1'!$A$1:$V$2</definedName>"
                + '<definedName name="_xlnm._FilterDatabase" localSheetId="2">'
                + "'BD2'!$A$1:$J$1</definedName>"
                + '</definedNames></workbook>')

    xfs = "".join('<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
                  for _ in range(60))  # cobre os estilos 0..57 usados pelo motor
    styles = (DECL
              + f'<styleSheet {ns}>'
              + '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
              + '<fills count="2"><fill><patternFill patternType="none"/></fill>'
              + '<fill><patternFill patternType="gray125"/></fill></fills>'
              + '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
              + '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              + f'<cellXfs count="60">{xfs}</cellXfs>'
              + '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
              + '</styleSheet>')

    core = (DECL
            + '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            + 'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            + 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            + '<dcterms:created xsi:type="dcterms:W3CDTF">2026-09-01T12:00:00Z</dcterms:created>'
            + '<dcterms:modified xsi:type="dcterms:W3CDTF">2026-09-01T12:00:00Z</dcterms:modified>'
            + '</cp:coreProperties>')

    content_types = (DECL
                     + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     + '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     + '<Default Extension="xml" ContentType="application/xml"/>'
                     + '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                     + '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                     + '<Override PartName="/xl/worksheets/sheet5.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                     + '<Override PartName="/xl/worksheets/sheet6.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                     + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                     + '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
                     + '<Override PartName="/xl/tables/table1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml"/>'
                     + '<Override PartName="/xl/tables/table2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml"/>'
                     + '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
                     + '<Override PartName="/xl/pivotTables/pivotTable1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotTable+xml"/>'
                     + '<Override PartName="/xl/pivotTables/pivotTable2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotTable+xml"/>'
                     + '<Override PartName="/xl/pivotTables/pivotTable3.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotTable+xml"/>'
                     + '<Override PartName="/xl/pivotTables/pivotTable4.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotTable+xml"/>'
                     + '<Override PartName="/xl/slicers/slicer1.xml" ContentType="application/vnd.ms-excel.slicer+xml"/>'
                     + '</Types>')

    rels_raiz = (DECL
                 + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 + '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                 + '</Relationships>')

    rel_tipo = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    rels_wb = (DECL
               + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               + f'<Relationship Id="rId1" Type="{rel_tipo}/worksheet" Target="worksheets/sheet1.xml"/>'
               + f'<Relationship Id="rId5" Type="{rel_tipo}/worksheet" Target="worksheets/sheet5.xml"/>'
               + f'<Relationship Id="rId6" Type="{rel_tipo}/worksheet" Target="worksheets/sheet6.xml"/>'
               + f'<Relationship Id="rId7" Type="{rel_tipo}/styles" Target="styles.xml"/>'
               + f'<Relationship Id="rId8" Type="{rel_tipo}/sharedStrings" Target="sharedStrings.xml"/>'
               + f'<Relationship Id="rId9" Type="{rel_tipo}/table" Target="tables/table1.xml"/>'
               + f'<Relationship Id="rId10" Type="{rel_tipo}/table" Target="tables/table2.xml"/>'
               + '</Relationships>')

    caminho = tmp_path / "base.xlsx"
    partes = {
        "[Content_Types].xml": content_types,
        "_rels/.rels": rels_raiz,
        "docProps/core.xml": core,
        "xl/workbook.xml": workbook,
        "xl/_rels/workbook.xml.rels": rels_wb,
        "xl/styles.xml": styles,
        "xl/sharedStrings.xml": shared,
        "xl/worksheets/sheet1.xml": sheet1,
        "xl/worksheets/sheet5.xml": sheet5,
        "xl/worksheets/sheet6.xml": sheet6,
        "xl/tables/table1.xml": table1,
        "xl/tables/table2.xml": table2,
        **dict(pivots),
        "xl/pivotCache/pivotCacheDefinition1.xml": def1,
        "xl/pivotCache/pivotCacheDefinition2.xml": def2,
        "xl/pivotCache/pivotCacheRecords1.xml": rec_bd2,
        "xl/pivotCache/pivotCacheRecords2.xml": rec_bd1,
        "xl/pivotCache/_rels/pivotCacheDefinition1.xml.rels": rels_def(1),
        "xl/pivotCache/_rels/pivotCacheDefinition2.xml.rels": rels_def(2),
        "xl/timelineCaches/timelineCache1.xml": timeline1,
        "xl/timelineCaches/timelineCache2.xml": timeline2,
        **slicers,
        "xl/slicers/slicer1.xml": slicer_view,
        "customXml/item1.xml": "<preservar>BYTES</preservar>",
    }
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, conteudo in partes.items():
            z.writestr(nome, conteudo)
    return caminho


def _criar_wpd(tmp_path):
    caminho = tmp_path / "wpd.xlsx"
    pd.DataFrame({
        "Remessa": [117129, 200001, "200002 (R)"],
        "Protocolo": [118, 119, 120],
        "Emissão": [datetime(2026, 8, 31)] * 3,
        "Vencimento": [datetime(2026, 9, 30)] * 3,
        "Entrega": [None] * 3,
        "Baixa": [None] * 3,
        "Nota Fiscal": [None] * 3,
        "Convênio": ["HOSPITAL ABC", "OUTRO CONVÊNIO", "TERCEIRO"],
        "Faturado": [100.0] * 3,
        "Valor Pago": [100.0] * 3,
        "Valor ISS": [5.0] * 3,
        "Vlr Guia": [100.0] * 3,
        "% Pré-glosa": [0.0] * 3,
        "Valor Glosa": [0.0] * 3,
        "% Glosa": [0.0] * 3,
        "Atraso": [0.0] * 3,
        "Faturas": [1.0] * 3,
    }).to_excel(caminho, index=False)
    return caminho


def _criar_limpo(tmp_path):
    caminho = tmp_path / "nao_identificado.xlsx"
    pd.DataFrame({
        "Convênio": ["Convênio Novo", "Convênio Novo 2"],
        "Data": [datetime(2026, 9, 1)] * 2,
        "Dep. Líq.": [10.0, 20.0],
        "Dep. Bruto": [11.0, 21.0],
        "Quitação": [12.0, 22.0],
        "Não Identificado": [13.0, 23.0],
        "Acordos": [14.0, 24.0],
        "Glosa Aceita": [15.0, 25.0],
        "NI Real": [16.0, 26.0],
    }).to_excel(caminho, index=False)
    return caminho


def test_processamento_completo(tmp_path):
    base = _criar_base(tmp_path)
    wpd = _criar_wpd(tmp_path)
    limpo = _criar_limpo(tmp_path)
    final = tmp_path / "final.xlsx"

    ie.processar_fases_2_3_4_hias(str(limpo), str(base), str(final),
                                  str(tmp_path), str(tmp_path), str(wpd))

    # backup automático
    assert len(list(tmp_path.glob("BACKUP_Hias_*.xlsx"))) == 1
    # o final abre em leitura (gate)
    from openpyxl import load_workbook
    wb = load_workbook(final, read_only=True)
    # BD1: 1 existente + 2 novas (o 117129 foi deduplicado)
    bd1 = wb["BD1"]
    linhas1 = list(bd1.iter_rows(values_only=True))
    assert len(linhas1) == 4
    assert linhas1[2][0] == 200001
    assert linhas1[3][0] == "200002 (R)"
    # BD2: linha antiga preservada e normalizada + só as linhas novas do
    # bloco anexadas no fim (dedupe-append — a base nunca é substituída)
    bd2 = wb["BD2"]
    linhas2 = list(bd2.iter_rows(values_only=True))
    assert len(linhas2) == 4
    assert linhas2[1][0] == "Convênio Z"
    assert linhas2[2][0] == "Convênio Novo"
    assert linhas2[2][1] == (date(2026, 9, 1) - ie.SERIAL_EPOCA).days
    assert linhas2[2][9] == 1            # J=1
    assert linhas2[3][0] == "Convênio Novo 2"
    assert linhas2[3][9] == 1

    with zipfile.ZipFile(base) as zb, zipfile.ZipFile(final) as zf:
        # partes intocadas preservadas byte a byte
        assert zb.read("xl/styles.xml") == zf.read("xl/styles.xml")
        assert zb.read("customXml/item1.xml") == zf.read("customXml/item1.xml")
        assert zb.read("xl/slicers/slicer1.xml") == zf.read("xl/slicers/slicer1.xml")
        assert 'ref="A1:V4"' in zf.read("xl/tables/table1.xml").decode("utf-8")
        assert 'ref="A1:I4"' in zf.read("xl/tables/table2.xml").decode("utf-8")
        assert 'fullCalcOnLoad="1"' in zf.read("xl/workbook.xml").decode("utf-8")
        assert "'BD1'!$A$1:$V$4" in zf.read("xl/workbook.xml").decode("utf-8")
        assert 'A1:V4' in zf.read("xl/worksheets/sheet5.xml").decode("utf-8")
        assert 'refreshOnLoad' not in zf.read("xl/workbook.xml").decode("utf-8")
        assert set(zf.namelist()) == set(zb.namelist())   # nenhuma parte criada/removida
        # fórmula da V com cache inline (openpyxl devolve a fórmula, não o cache)
        sheet5_final = zf.read("xl/worksheets/sheet5.xml").decode("utf-8")
        assert ('<c r="V3" s="43" t="str"><f>=IF(RIGHT(A3,3)="(R)","Recurso","Comum")</f><v>Comum</v></c>'
                in sheet5_final)
        assert ('<c r="V4" s="43" t="str"><f>=IF(RIGHT(A4,3)="(R)","Recurso","Comum")</f><v>Recurso</v></c>'
                in sheet5_final)

        # ---- FASE 3c: caches regenerados (def1 = BD2, def2 = BD1) ----
        def1 = zf.read("xl/pivotCache/pivotCacheDefinition1.xml").decode("utf-8")
        def2 = zf.read("xl/pivotCache/pivotCacheDefinition2.xml").decode("utf-8")
        rec1 = zf.read("xl/pivotCache/pivotCacheRecords1.xml").decode("utf-8")
        rec2 = zf.read("xl/pivotCache/pivotCacheRecords2.xml").decode("utf-8")

        # BD1: 1 existente + 2 novas; itens novos no fim dos sharedItems
        assert 'recordCount="3"' in def2
        assert 'refreshedBy="Leonardo Martins"' in def2
        assert '<n v="200001"/>' in def2 and '<s v="200002 (R)"/>' in def2
        assert '<s v="OUTRO CONVÊNIO"/>' in def2 and '<s v="TERCEIRO"/>' in def2
        assert rec2.count("<r>") == 3 and 'count="3"' in rec2
        # BD2: 1 história + 2 novas; convênio renormalizado no cache
        assert 'recordCount="3"' in def1
        assert 'ref="A1:I4"' in def1 and 'ref="A1:I2"' not in def1
        assert '<s v="Convênio Z"/>' in def1 and '<s v="Convênio Z "/>' not in def1
        assert '<s v="Convênio Novo"/>' in def1 and '<s v="Convênio Novo 2"/>' in def1
        assert rec1.count("<r>") == 3 and 'count="3"' in rec1
        # refreshOnLoad removido dos caches e das pivôs
        for parte in ("xl/pivotCache/pivotCacheDefinition1.xml",
                      "xl/pivotCache/pivotCacheDefinition2.xml"):
            assert "refreshOnLoad" not in zf.read(parte).decode("utf-8")
        for i in range(1, 5):
            p = zf.read(f"xl/pivotTables/pivotTable{i}.xml").decode("utf-8")
            assert "refreshOnLoad" not in p

        # timeline "Entrega" e slicer "Tipo de remessa" PRESERVADOS do arquivo
        # do usuário — sem janela de fechamento forçada e sem restrição "só
        # Comum" (as baixas e os recursos têm de aparecer no relatório)
        assert zb.read("xl/timelineCaches/timelineCache1.xml") == \
            zf.read("xl/timelineCaches/timelineCache1.xml")
        assert zb.read("xl/slicerCaches/slicerCache3.xml") == \
            zf.read("xl/slicerCaches/slicerCache3.xml")
        # slicers Convênio: novos convênios entram marcados (BD1 tabs 3/6/11,
        # BD2 tab 8 — índices 1 e 2 do cache de cada BD)
        for n in ("slicerCache1.xml", "slicerCache2.xml", "slicerCache5.xml",
                  "slicerCache7.xml"):
            sc = zf.read(f"xl/slicerCaches/{n}").decode("utf-8")
            assert 'count="3"' in sc
            assert '<i x="1" s="1"/>' in sc and '<i x="2" s="1"/>' in sc

        # pivôs 1–3: itens novos anexados; convênios colapsados (sd="0");
        # campo 21 (Tipo de remessa) SEM itens ocultos — Recurso fica visível
        p1 = zf.read("xl/pivotTables/pivotTable1.xml").decode("utf-8")
        assert '<item x="1" h="1"/>' not in p1
        assert '<item m="1" x="2" h="1"/>' not in p1
        assert '<item x="0" sd="0"/>' in p1         # convênio colapsado
        assert '<item x="1" sd="0"/>' in p1         # convênio novo colapsado
        assert '<item x="1"/>' in p1                # remessa/protocolo novos visíveis
        for i in (2, 3):
            p = zf.read(f"xl/pivotTables/pivotTable{i}.xml").decode("utf-8")
            assert 'h="1"' not in p                 # h só na pivô 1 (como no real)
            assert '<item x="1" sd="0"/>' in p
        # pivô 4 (À Quitar, cache BD2): convênios colapsados, datas visíveis
        p4 = zf.read("xl/pivotTables/pivotTable4.xml").decode("utf-8")
        assert '<item x="1" sd="0"/>' in p4
        assert '<item x="1"/>' in p4                # data nova visível


def test_processamento_aborta_se_dimension_bd2_faltar(tmp_path):
    """BD2 sem <dimension> não pode ter a dimension reescrita — o motor deve
    abortar (RuntimeError) em vez de gravar uma saída silenciosamente errada."""
    base = _criar_base(tmp_path, sem_dimension_bd2=True)
    wpd = _criar_wpd(tmp_path)
    limpo = _criar_limpo(tmp_path)
    final = tmp_path / "final.xlsx"

    with pytest.raises(RuntimeError, match="dimension da BD2"):
        ie.processar_fases_2_3_4_hias(str(limpo), str(base), str(final),
                                      str(tmp_path), str(tmp_path), str(wpd))


def test_limpo_none_integra_so_bd1(tmp_path):
    base = _criar_base(tmp_path)
    wpd = _criar_wpd(tmp_path)
    final = tmp_path / "final.xlsx"

    ie.processar_fases_2_3_4_hias(None, str(base), str(final),
                                  str(tmp_path), str(tmp_path), str(wpd))

    from openpyxl import load_workbook
    wb = load_workbook(final, read_only=True)
    linhas1 = list(wb["BD1"].iter_rows(values_only=True))
    assert len(linhas1) == 4
    # BD2 intocada (só cabeçalho + 1 linha antiga, ainda com o espaço)
    linhas2 = list(wb["BD2"].iter_rows(values_only=True))
    assert len(linhas2) == 2
    assert linhas2[1][0] == "Convênio Z "
    with zipfile.ZipFile(base) as zb, zipfile.ZipFile(final) as zf:
        assert zb.read("xl/slicers/slicer1.xml") == zf.read("xl/slicers/slicer1.xml")
        # cache da BD1 regenerado com as novas; cache da BD2 INTOCADO
        def1 = zf.read("xl/pivotCache/pivotCacheDefinition1.xml").decode("utf-8")
        def2 = zf.read("xl/pivotCache/pivotCacheDefinition2.xml").decode("utf-8")
        assert 'recordCount="3"' in def2
        assert 'recordCount="1"' in def1
        assert 'ref="A1:I2"' in def1
        assert '<s v="Convênio Z "/>' in def1    # sem normalização (BD2 intocada)
        # timeline/slicer preservados do arquivo do usuário (a BD1 mudou, mas
        # sem filtros forçados no relatório)
        assert zb.read("xl/timelineCaches/timelineCache1.xml") == \
            zf.read("xl/timelineCaches/timelineCache1.xml")
        assert zb.read("xl/slicerCaches/slicerCache3.xml") == \
            zf.read("xl/slicerCaches/slicerCache3.xml")
        for i in range(1, 5):
            assert "refreshOnLoad" not in zf.read(
                f"xl/pivotTables/pivotTable{i}.xml").decode("utf-8")
        # tabelas da BD2 sem alteração; a da BD1 cresceu
        assert 'ref="A1:I2"' in zf.read("xl/tables/table2.xml").decode("utf-8")
        assert 'ref="A1:V4"' in zf.read("xl/tables/table1.xml").decode("utf-8")


def _trocar_caches(tmp_path, base):
    """Reescreve a base com as partes de pivot cache RENUMERADAS (1↔2),
    como o Excel fez no arquivo real de 02/09/2026: cacheDefinition1 passa a
    ser o cache da BD1 (fonte = tabela BD_1, por nome) e o da BD2
    (worksheetSource com ref A1:I) vai para cacheDefinition2. Defs, records e
    rels trocam JUNTOS para manter cada cache íntegro."""
    with zipfile.ZipFile(base) as z:
        partes = {n: z.read(n) for n in z.namelist()}
    for a, b in [("xl/pivotCache/pivotCacheDefinition1.xml",
                  "xl/pivotCache/pivotCacheDefinition2.xml"),
                 ("xl/pivotCache/pivotCacheRecords1.xml",
                  "xl/pivotCache/pivotCacheRecords2.xml"),
                 ("xl/pivotCache/_rels/pivotCacheDefinition1.xml.rels",
                  "xl/pivotCache/_rels/pivotCacheDefinition2.xml.rels")]:
        partes[a], partes[b] = partes[b], partes[a]
    caminho = tmp_path / "base_trocado.xlsx"
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, conteudo in partes.items():
            z.writestr(nome, conteudo)
    return caminho


def test_cache_bd2_renumerado_pelo_excel(tmp_path):
    """O Excel pode renumerar as partes de pivot cache ao salvar (caso real de
    02/09/2026). O motor deve achar o cache da BD2 PELO CONTEÚDO e atualizar
    o ref na parte certa — regenerando cada cache na sua parte renumerada."""
    base = _criar_base(tmp_path)
    base_trocado = _trocar_caches(tmp_path, base)
    wpd = _criar_wpd(tmp_path)
    limpo = _criar_limpo(tmp_path)
    final = tmp_path / "final_trocado.xlsx"

    ie.processar_fases_2_3_4_hias(str(limpo), str(base_trocado), str(final),
                                  str(tmp_path), str(tmp_path), str(wpd))

    with zipfile.ZipFile(final) as zf:
        cache1 = zf.read("xl/pivotCache/pivotCacheDefinition1.xml").decode("utf-8")
        cache2 = zf.read("xl/pivotCache/pivotCacheDefinition2.xml").decode("utf-8")
        rec1 = zf.read("xl/pivotCache/pivotCacheRecords1.xml").decode("utf-8")
        rec2 = zf.read("xl/pivotCache/pivotCacheRecords2.xml").decode("utf-8")
    assert 'name="BD_1"' in cache1            # cache da BD1 na parte renumerada
    assert 'recordCount="3"' in cache1        # ... e regenerado com as novas
    assert rec1.count("<r>") == 3
    assert 'ref="A1:I4"' in cache2            # ref da BD2 atualizado na parte certa
    assert 'ref="A1:I2"' not in cache2
    assert 'recordCount="3"' in cache2        # BD2: 1 história + 2 do bloco
    assert rec2.count("<r>") == 3


def test_parte_cache_bd2_seleciona_por_conteudo():
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    cache_bd1 = (DECL + f'<pivotCacheDefinition {ns}>'
                 + '<cacheSource type="worksheet"><worksheetSource name="BD_1"/></cacheSource>'
                 + '</pivotCacheDefinition>')
    cache_bd2 = (DECL + f'<pivotCacheDefinition {ns}>'
                 + '<cacheSource type="worksheet"><worksheetSource ref="A1:I1020" sheet="BD2"/></cacheSource>'
                 + '</pivotCacheDefinition>')
    partes = {
        "xl/pivotCache/pivotCacheDefinition1.xml": cache_bd1,
        "xl/pivotCache/pivotCacheDefinition2.xml": cache_bd2,
    }
    assert ie._parte_cache_bd2(partes) == "xl/pivotCache/pivotCacheDefinition2.xml"
    so_bd1 = {"xl/pivotCache/pivotCacheDefinition1.xml": cache_bd1}
    assert ie._parte_cache_bd2(so_bd1) is None
