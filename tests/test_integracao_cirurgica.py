"""Testes do motor cirúrgico integracao_excel.py.

A fixture base é um .xlsx SINTÉTICO escrito à mão (partes XML em dict),
reproduzindo a anatomia do arquivo real (sharedStrings + tabelas + calcPr
sem fullCalcOnLoad). O openpyxl nunca grava o Hias real — aqui ele só LÊ
(fixture e gate), e os arquivos WPD/limpo sintéticos podem usar pandas.
"""
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
    s = ie._StringsCompartilhadas(_sst(["ALGUM CONVÊNIO"]))
    linha = ie._linha_bd2(806, "ALGUM CONVÊNIO", 45001,
                          [1.5, 2.0, None, 1000, 0.0, 0.0, 0.0], s)
    assert '<row r="806">' in linha
    assert '<c r="A806" s="34" t="s"><v>0</v></c>' in linha
    assert '<c r="B806" s="35"><v>45001</v></c>' in linha
    assert '<c r="C806" s="53"><v>1.5</v></c>' in linha
    assert '<c r="D806" s="53"><v>2</v></c>' in linha
    assert '<c r="E806" s="53"/>' in linha
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


def test_editar_bd2_deleta_obsoletas_normaliza_e_insere():
    s = ie._StringsCompartilhadas(_sst(["CABEÇALHO", "Convênio ", "OBJETO"]))
    xml, fim, novas_celulas = ie._editar_bd2(
        XML_BD2_MINI,
        [{"convenio": "Convênio", "data": 45001,
          "valores": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]}],
        s)
    assert fim == 806
    assert novas_celulas == 1
    # obsoletas removidas
    assert '<c r="A806" s="5"' not in xml
    assert '<c r="A808"' not in xml
    # coluna A normalizada: "Convênio " -> "Convênio" (si novo = índice 3)
    assert '<c r="A2" s="34" t="s"><v>3</v></c>' in xml
    assert '<c r="A805" s="34" t="s"><v>3</v></c>' in xml
    # bloco novo usa o mesmo si e começa na linha 806
    assert '<c r="A806" s="34" t="s"><v>3</v></c>' in xml
    assert '<c r="B806" s="35"><v>45001</v></c>' in xml
    assert '<c r="J806" s="17"><v>1</v></c>' in xml
    # dimension
    assert 'ref="A1:J806"' in xml
    assert 'ref="A1:J808"' not in xml


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
    xml, fim, n = ie._editar_bd2(xml_limpo, None, s)
    assert xml is None and fim is None and n == 0


# ==============================================================================
# Partes auxiliares
# ==============================================================================
def test_marcar_refresh_on_load_nas_pivots():
    xml = (DECL
           + '<pivotTableDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
           + 'name="Tabela dinâmica1" cacheId="3" applyNumberFormats="0">'
           + '<location ref="A1:B5" firstHeaderRow="1"/></pivotTableDefinition>')
    saida = ie._marcar_refresh_on_load(xml)
    assert 'refreshOnLoad="1"' in saida
    with pytest.raises(ValueError):
        ie._marcar_refresh_on_load(saida)  # não duplicar


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
# Integração completa (fixture sintética escrita à mão)
# ==============================================================================
def _criar_base(tmp_path):
    """Hias sintético mínimo com a anatomia do real: BD1/BD2 + sharedStrings +
    tabelas + calcPr sem fullCalcOnLoad. Escrito à mão porque o openpyxl
    3.1.5 usa strings inline (o motor exige sharedStrings)."""
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
    sheet6 = (DECL + f'<worksheet {ns}><dimension ref="A1:J2"/><sheetData>'
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
    # BD2: linha antiga normalizada + bloco novo em 806/807
    bd2 = wb["BD2"]
    linhas2 = list(bd2.iter_rows(values_only=True))
    assert len(linhas2) == 807
    assert linhas2[1][0] == "Convênio Z"
    assert linhas2[805][0] == "Convênio Novo"
    assert linhas2[805][1] == (date(2026, 9, 1) - ie.SERIAL_EPOCA).days
    assert linhas2[805][9] == 1            # J=1
    assert linhas2[806][0] == "Convênio Novo 2"
    assert linhas2[806][9] == 1
    # partes intocadas preservadas byte a byte
    with zipfile.ZipFile(base) as zb, zipfile.ZipFile(final) as zf:
        assert zb.read("xl/styles.xml") == zf.read("xl/styles.xml")
        assert zb.read("customXml/item1.xml") == zf.read("customXml/item1.xml")
        assert 'ref="A1:V4"' in zf.read("xl/tables/table1.xml").decode("utf-8")
        assert 'ref="A1:I807"' in zf.read("xl/tables/table2.xml").decode("utf-8")
        assert 'fullCalcOnLoad="1"' in zf.read("xl/workbook.xml").decode("utf-8")
        assert "'BD1'!$A$1:$V$4" in zf.read("xl/workbook.xml").decode("utf-8")
        assert 'A1:V4' in zf.read("xl/worksheets/sheet5.xml").decode("utf-8")
        assert 'refreshOnLoad' not in zf.read("xl/workbook.xml").decode("utf-8")
        # fórmula da V com cache inline (openpyxl devolve a fórmula, não o cache)
        sheet5_final = zf.read("xl/worksheets/sheet5.xml").decode("utf-8")
        assert ('<c r="V3" s="43" t="str"><f>=IF(RIGHT(A3,3)="(R)","Recurso","Comum")</f><v>Comum</v></c>'
                in sheet5_final)
        assert ('<c r="V4" s="43" t="str"><f>=IF(RIGHT(A4,3)="(R)","Recurso","Comum")</f><v>Recurso</v></c>'
                in sheet5_final)


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
    # tabelas da BD2 sem alteração; a da BD1 cresceu
    with zipfile.ZipFile(final) as zf:
        assert 'ref="A1:I2"' in zf.read("xl/tables/table2.xml").decode("utf-8")
        assert 'ref="A1:V4"' in zf.read("xl/tables/table1.xml").decode("utf-8")
