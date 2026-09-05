"""Testes unitários do editor cirúrgico de caches/timeline/slicers/pivôs
(pivot_cache.py)."""
import re
from datetime import date

import pytest

import pivot_cache as pc

DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
NS_R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def _def(campos, record_count=1, refresh_on_load=True):
    rol = ' refreshOnLoad="1"' if refresh_on_load else ""
    return (DECL
            + f'<pivotCacheDefinition {NS} {NS_R} '
            + 'refreshedBy="Sistema" refreshedDate="46200.0" '
            + f'recordCount="{record_count}" createdVersion="7" refreshedVersion="7"{rol}>'
            + '<cacheSource type="worksheet"><worksheetSource name="BD_1"/></cacheSource>'
            + f'<cacheFields count="{len(campos)}">{"".join(campos)}</cacheFields>'
            + '</pivotCacheDefinition>')


def _records(bodies, count=None):
    n = count if count is not None else len(bodies)
    corpo = "".join(f"<r>{b}</r>" for b in bodies)
    return (DECL + f'<pivotCacheRecords {NS} {NS_R} count="{n}">{corpo}'
            + '</pivotCacheRecords>')


# ==============================================================================
# CachePivot — leitura e índices
# ==============================================================================
def test_cache_pivot_parse_ordem_e_blank():
    campos = [
        '<cacheField name="Remessa" numFmtId="0"><sharedItems count="1"><n v="117129"/></sharedItems></cacheField>',
        '<cacheField name="Emissão" numFmtId="14"/>',  # auto-contido conta na ordem
        '<cacheField name="Convênio" numFmtId="0"><sharedItems count="2"><s v="HOSPITAL ABC"/><m/></sharedItems></cacheField>',
    ]
    cache = pc.CachePivot(
        _def(campos),
        _records(['<x v="0"/><d v="2026-08-31T00:00:00"/><x v="0"/>']))
    assert cache.n_registros == 1
    assert cache.campos_ordenados() == ["Remessa", "Emissão", "Convênio"]
    assert not cache.tem_blank("Remessa")
    assert cache.tem_blank("Convênio")


def test_cache_pivot_sem_count_nos_records_levanta():
    xml = DECL + f'<pivotCacheRecords {NS} {NS_R}><r><n v="1"/></r></pivotCacheRecords>'
    with pytest.raises(RuntimeError, match="count dos records"):
        pc.CachePivot(_def([]), xml)


def test_obter_indice_existente_e_novo():
    campos = ['<cacheField name="Convênio" numFmtId="0"><sharedItems count="2">'
              '<s v="HOSPITAL ABC"/><s v="SANTA CASA"/></sharedItems></cacheField>']
    cache = pc.CachePivot(_def(campos), _records(['<x v="0"/>']))
    assert cache.obter_indice("Convênio", "s", "HOSPITAL ABC") == 0
    assert cache.obter_indice("Convênio", "s", "OUTRO") == 2
    assert cache.novos_indices("Convênio") == [2]
    assert cache.novos_por_campo() == {"Convênio": [2]}


def test_obter_indice_repetido_entre_novos_nao_duplica():
    """Duas linhas novas com o mesmo valor (convênio/data repetidos) devem
    referenciar o MESMO índice — sem duplicar o sharedItem (bug do dedup
    pendente)."""
    campos = ['<cacheField name="Convênio" numFmtId="0"><sharedItems count="1">'
              '<s v="HOSPITAL ABC"/></sharedItems></cacheField>']
    cache = pc.CachePivot(_def(campos), _records(['<x v="0"/>']))
    assert cache.obter_indice("Convênio", "s", "OUTRO") == 1
    assert cache.obter_indice("Convênio", "s", "OUTRO") == 1
    assert cache.novos_indices("Convênio") == [1]
    definicao, _ = cache.para_xml()
    assert definicao.count('<s v="OUTRO"/>') == 1


# ==============================================================================
# CachePivot — records e serialização
# ==============================================================================
def test_anexar_e_remover_registros():
    cache = pc.CachePivot(
        _def([]),
        _records(['<n v="1"/>', '<n v="2"/>', '<n v="3"/>']))
    assert cache.n_registros == 3
    cache.anexar_registros(['<r><n v="4"/></r>', '<r><n v="5"/></r>'])
    assert cache.n_registros == 5
    _, registros = cache.para_xml()
    assert registros.count("<r>") == 5 and 'count="5"' in registros
    cache.remover_registros_finais(2)
    assert cache.n_registros == 3
    _, registros = cache.para_xml()
    assert registros.count("<r>") == 3
    with pytest.raises(RuntimeError):
        cache.remover_registros_finais(5)


def test_para_xml_anexa_itens_e_atualiza_metadados():
    campos = ['<cacheField name="Convênio" numFmtId="0"><sharedItems containsString="1" count="1">'
              '<s v="HOSPITAL ABC"/></sharedItems></cacheField>']
    cache = pc.CachePivot(_def(campos), _records(['<x v="0"/>']))
    cache.obter_indice("Convênio", "s", "OUTRO")
    cache.anexar_registros(['<r><x v="1"/></r>'])
    definicao, registros = cache.para_xml()
    assert '<s v="HOSPITAL ABC"/><s v="OUTRO"/>' in definicao
    assert '<sharedItems count="2" containsString="1">' in definicao
    assert 'numFmtId="0"' in definicao            # atributos não recalculados ficam
    assert 'recordCount="2"' in definicao
    assert 'refreshedBy="Leonardo Martins"' in definicao
    assert 'refreshedDate="46200.0"' not in definicao
    assert "refreshOnLoad" not in definicao
    # o def reescrito continua XML bem formado (atributos íntegros)
    import xml.etree.ElementTree as ET
    raiz = ET.fromstring(definicao)
    assert re.fullmatch(r"46\d+\.\d+", raiz.attrib["refreshedDate"])
    assert 'count="2"' in registros and registros.count("<r>") == 2


def test_para_xml_recalcula_min_max_numerico():
    campos = ['<cacheField name="Remessa" numFmtId="0"><sharedItems count="1" '
              'minValue="117129" maxValue="117129" containsNumber="1" '
              'containsInteger="1"><n v="117129"/></sharedItems></cacheField>']
    cache = pc.CachePivot(_def(campos), _records(['<x v="0"/>']))
    cache.obter_indice("Remessa", "n", "200001")
    definicao, _ = cache.para_xml()
    assert 'minValue="117129"' in definicao
    assert 'maxValue="200001"' in definicao
    assert 'count="2"' in definicao and 'containsInteger="1"' in definicao


def test_substituir_strings_no_lugar_indices_estaveis():
    campos = ['<cacheField name="Convênio" numFmtId="0"><sharedItems count="1">'
              '<s v="Convênio Z "/></sharedItems></cacheField>']
    cache = pc.CachePivot(_def(campos), _records(['<x v="0"/>']))
    assert cache.substituir_strings("Convênio", {"Convênio Z ": "Convênio Z"})
    definicao, registros = cache.para_xml()
    assert '<s v="Convênio Z"/>' in definicao
    assert '<s v="Convênio Z "/>' not in definicao
    assert '<x v="0"/>' in registros            # record intocado (índice estável)
    assert 'recordCount="1"' in definicao


def test_substituir_strings_preserva_unicidade_contra_item_nao_usado():
    """Anatomia real do cache BD2: item usado com padding e item não usado
    (u="1") com o MESMO nome sem padding. A substituição não pode tornar os
    valores idênticos — o Excel repara caches com valores duplicados no
    sharedItems (causa raiz do aviso de reparo de 05/09)."""
    com_padding = "AMAFRERJ" + " " * 35
    campos = ['<cacheField name="Convênio" numFmtId="0"><sharedItems count="2">'
              f'<s v="{com_padding}"/><s v="AMAFRERJ" u="1"/></sharedItems></cacheField>']
    cache = pc.CachePivot(_def(campos), _records(['<x v="0"/>']))
    cache.substituir_strings("Convênio", {com_padding: "AMAFRERJ"})
    definicao, registros = cache.para_xml()
    valores = re.findall(r'<s v="([^"]*)"', definicao)
    assert len(valores) == len(set(valores))    # unicidade preservada
    assert '<x v="0"/>' in registros            # índice estável


# ==============================================================================
# Timeline "Entrega"
# ==============================================================================
def _timeline(estado):
    return (DECL
            + '<timelineCache xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" '
            + 'sourceName="Entrega" name="TimelineEntrega1">'
            + estado + '</timelineCache>')


def test_editar_timeline_com_bounds():
    estado = ('<state filterType="unknown" startDate="2024-01-01T00:00:00" '
              'endDate="2027-01-01T00:00:00">'
              '<bounds startDate="2024-01-01T00:00:00" endDate="2027-01-01T00:00:00"/>'
              '</state>')
    saida = pc.editar_timeline(_timeline(estado), date(2026, 8, 1), date(2026, 8, 31))
    assert 'filterType="dateBetween"' in saida
    assert ('<selection startDate="2026-08-01T00:00:00" '
            'endDate="2026-08-31T00:00:00"/>') in saida
    assert saida.index("<selection") < saida.index("<bounds")
    assert 'startDate="2024-01-01T00:00:00"' in saida   # atributos preservados


def test_editar_timeline_state_autocontido():
    estado = ('<state filterType="unknown" startDate="2024-01-01T00:00:00" '
              'endDate="2027-01-01T00:00:00"/>')
    saida = pc.editar_timeline(_timeline(estado), date(2026, 8, 1), date(2026, 8, 31))
    assert 'filterType="dateBetween"' in saida
    assert '<selection ' in saida and saida.rstrip().endswith("</state></timelineCache>")


def test_editar_timeline_sem_state_levanta():
    with pytest.raises(RuntimeError, match="state"):
        pc.editar_timeline("<timelineCache/>", date(2026, 8, 1), date(2026, 8, 31))


# ==============================================================================
# Slicers
# ==============================================================================
SLICER_TIPO = (DECL
               + '<slicerCache xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" '
               + 'sourceName="Tipo de remessa" name="SegmentaçãoDeDados3">'
               + '<pivotTables><pivotTable tabId="3" name="Pivot3"/></pivotTables>'
               + '<items count="3"><i x="0" s="1"/><i x="1" s="1"/><i x="2" nd="1"/></items>'
               + '</slicerCache>')


def test_selecionar_slicer_tipo_remessa():
    saida = pc.selecionar_slicer_tipo_remessa(SLICER_TIPO)
    assert re.findall(r'<i x="(\d+)" s="1"', saida) == ["0"]
    assert '<i x="2" nd="1"/>' in saida           # nd preservado
    assert '<i x="1"/>' in saida                  # desselecionado


def test_anexar_itens_slicer():
    saida = pc.anexar_itens_slicer(SLICER_TIPO, [3, 4])
    assert 'count="5"' in saida
    assert '<i x="3" s="1"/>' in saida and '<i x="4" s="1"/>' in saida
    assert '<i x="0" s="1"/>' in saida            # itens antigos intactos


def test_slicer_sem_items_levanta():
    with pytest.raises(RuntimeError):
        pc.selecionar_slicer_tipo_remessa("<slicerCache/>")
    with pytest.raises(RuntimeError):
        pc.anexar_itens_slicer("<slicerCache/>", [1])


# ==============================================================================
# Pivô (pivotTableN.xml)
# ==============================================================================
PIVOT = (DECL + f'<pivotTableDefinition {NS} name="Tabela dinâmica1" cacheId="1" '
         + 'refreshOnLoad="1">'
         + '<pivotFields count="3">'
         + '<pivotField showAll="0"/>'
         + '<pivotField axis="axisRow" showAll="0"><items count="1"><item x="0"/></items></pivotField>'
         + '<pivotField axis="axisRow" showAll="0"><items count="4"><item x="0"/><item x="1"/>'
         + '<item m="1" x="2"/><item t="default"/></items></pivotField>'
         + '</pivotFields></pivotTableDefinition>')


def test_anexar_itens_pivot_com_e_sem_sd():
    saida = pc.anexar_itens_pivot(PIVOT, 1, [1, 2], com_sd=True)
    assert '<items count="3">' in saida
    assert '<item x="1" sd="0"/>' in saida and '<item x="2" sd="0"/>' in saida
    sem_sd = pc.anexar_itens_pivot(PIVOT, 1, [1])
    assert '<item x="1"/>' in sem_sd
    assert '<item x="1" sd="0"/>' not in sem_sd


def test_anexar_itens_pivot_sem_items_levanta():
    with pytest.raises(RuntimeError, match="sem <items>"):
        pc.anexar_itens_pivot(PIVOT, 0, [1])


def test_esconder_itens_pivot():
    saida = pc.esconder_itens_pivot(PIVOT, 2, [1, 2])
    assert '<item x="1" h="1"/>' in saida
    assert '<item m="1" x="2" h="1"/>' in saida
    assert '<item x="0"/>' in saida
    # idempotente — não duplica o atributo
    de_novo = pc.esconder_itens_pivot(saida, 2, [1, 2])
    assert de_novo.count('h="1"') == 2


def test_colapsar_itens_pivot():
    saida = pc.colapsar_itens_pivot(PIVOT, 1)
    assert '<item x="0" sd="0"/>' in saida
    saida2 = pc.colapsar_itens_pivot(PIVOT, 2)
    assert '<item x="0" sd="0"/>' in saida2
    assert '<item x="1" sd="0"/>' in saida2
    assert '<item m="1" x="2" sd="0"/>' in saida2
    assert '<item t="default"/>' in saida2      # default não tem x — intocado


def test_remover_refresh_on_load_e_campo_tem_itens():
    assert "refreshOnLoad" not in pc.remover_refresh_on_load(PIVOT)
    assert pc.campo_tem_itens(PIVOT, 1)
    assert not pc.campo_tem_itens(PIVOT, 0)
    with pytest.raises(RuntimeError):
        pc.campo_tem_itens(PIVOT, 9)


# ==============================================================================
# Seletores de partes pelo conteúdo
# ==============================================================================
def test_seletores_de_partes():
    partes = {
        "xl/pivotCache/pivotCacheDefinition1.xml":
            '<pivotCacheDefinition><cacheSource type="worksheet">'
            '<worksheetSource name="BD_1"/></cacheSource></pivotCacheDefinition>',
        "xl/pivotCache/pivotCacheDefinition2.xml":
            '<pivotCacheDefinition><cacheSource type="worksheet">'
            '<worksheetSource ref="A1:I1073" sheet="BD2"/></cacheSource></pivotCacheDefinition>',
        "xl/pivotCache/_rels/pivotCacheDefinition1.xml.rels":
            '<Relationship Id="rId1" Target="pivotCacheRecords1.xml"/>',
        "xl/pivotCache/_rels/pivotCacheDefinition2.xml.rels":
            '<Relationship Id="rId1" Target="pivotCacheRecords2.xml"/>',
        "xl/pivotCache/pivotCacheRecords1.xml": "<records/>",
        "xl/pivotCache/pivotCacheRecords2.xml": "<records/>",
        "xl/timelineCaches/timelineCache1.xml":
            '<timelineCache sourceName="Entrega" name="TimelineEntrega1"/>',
        "xl/slicerCaches/slicerCache1.xml":
            '<slicerCache sourceName="Convênio" name="S1">'
            '<pivotTables><pivotTable tabId="3" name="Pivot3"/></pivotTables></slicerCache>',
        "xl/slicerCaches/slicerCache3.xml":
            '<slicerCache sourceName="Tipo de remessa" name="S3">'
            '<pivotTables><pivotTable tabId="3" name="Pivot3"/></pivotTables></slicerCache>',
        "xl/slicerCaches/slicerCache4.xml":
            '<slicerCache sourceName="Tipo de remessa" name="S4">'
            '<pivotTables><pivotTable tabId="11" name="Pivot11"/></pivotTables></slicerCache>',
        "xl/slicerCaches/slicerCache5.xml":
            '<slicerCache sourceName="Convênio" name="S5">'
            '<pivotTables><pivotTable tabId="11" name="Pivot11"/></pivotTables></slicerCache>',
        "xl/slicerCaches/slicerCache7.xml":
            '<slicerCache sourceName="Convênio" name="S7">'
            '<pivotTables><pivotTable tabId="8" name="Pivot8"/></pivotTables></slicerCache>',
    }
    assert pc.parte_cache_bd1(partes) == "xl/pivotCache/pivotCacheDefinition1.xml"
    assert pc.parte_cache_bd2(partes) == "xl/pivotCache/pivotCacheDefinition2.xml"
    # Target relativo ao diretório do .rels (xl/pivotCache/_rels/)
    assert pc.nome_da_rel(partes, "xl/pivotCache/pivotCacheDefinition2.xml") == \
        "xl/pivotCache/pivotCacheRecords2.xml"
    # Target com ../ resolve para fora de xl/pivotCache/ (parte renumerada)
    com_subida = dict(partes)
    com_subida["xl/pivotCache/_rels/pivotCacheDefinition2.xml.rels"] = \
        '<Relationship Id="rId1" Target="../pivotCacheRecords2.xml"/>'
    com_subida["xl/pivotCacheRecords2.xml"] = "<records/>"
    assert pc.nome_da_rel(com_subida, "xl/pivotCache/pivotCacheDefinition2.xml") == \
        "xl/pivotCacheRecords2.xml"
    assert pc.parte_timeline_entrega(partes) == "xl/timelineCaches/timelineCache1.xml"
    assert pc.parte_slicer_tipo_data_entrega(partes) == "xl/slicerCaches/slicerCache3.xml"
    assert pc.partes_slicer_convenio(partes, [3, 6, 11]) == [
        "xl/slicerCaches/slicerCache1.xml", "xl/slicerCaches/slicerCache5.xml"]
    assert pc.partes_slicer_convenio(partes, [8]) == ["xl/slicerCaches/slicerCache7.xml"]
    assert pc.partes_slicer_convenio(partes, [99]) == []


def test_seletores_levantam_quando_nao_acham():
    with pytest.raises(RuntimeError):
        pc.parte_cache_bd1({})
    with pytest.raises(RuntimeError):
        pc.parte_cache_bd2({})
    with pytest.raises(RuntimeError):
        pc.parte_timeline_entrega({})
    with pytest.raises(RuntimeError):
        pc.parte_slicer_tipo_data_entrega({})
    with pytest.raises(RuntimeError):
        pc.nome_da_rel({}, "xl/pivotCache/pivotCacheDefinition1.xml")
