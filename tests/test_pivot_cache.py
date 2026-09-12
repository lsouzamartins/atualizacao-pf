"""Testes unitários do editor cirúrgico de caches/slicers/pivôs
(pivot_cache.py)."""
import re

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


# ==============================================================================
# CachePivot — atualizar_registro (upsert do NI editado)
# ==============================================================================
def test_atualizar_registro_substitui_valores_no_indice():
    campos = ['<cacheField name="Convênio" numFmtId="0"><sharedItems count="1">'
              '<s v="HOSPITAL ABC"/></sharedItems></cacheField>']
    cache = pc.CachePivot(
        _def(campos),
        _records(['<x v="0"/><n v="1"/><n v="2"/><n v="3"/>',
                  '<x v="0"/><n v="4"/><n v="5"/><n v="6"/>']))
    cache.atualizar_registro(1, ["40", "50", "60"], ["4", "5", "6"])
    _, registros = cache.para_xml()
    assert '<r><x v="0"/><n v="40"/><n v="50"/><n v="60"/></r>' in registros
    assert '<r><x v="0"/><n v="1"/><n v="2"/><n v="3"/></r>' in registros
    assert 'count="2"' in registros


def test_atualizar_registro_sem_mudanca_nao_altera_nada():
    cache = pc.CachePivot(_def([]), _records(['<n v="1"/>', '<n v="2"/>']))
    reg_antes, def_antes = cache._reg, cache._def
    cache.atualizar_registro(0, ["1"], ["1"])
    # nada é gravado — para_xml() não entra na conta (sempre regrava
    # refreshedDate com o horário atual)
    assert cache._reg == reg_antes and cache._def == def_antes


def test_atualizar_registro_valores_antigos_divergentes_localiza_por_valor():
    """Se o ordinal não aponta para o record esperado, o método localiza o
    record pelos valores antigos e atualiza ESSE (defesa de desalinhamento
    linha <-> record)."""
    cache = pc.CachePivot(
        _def([]),
        _records(['<n v="1"/><n v="9"/>', '<n v="4"/><n v="5"/><n v="6"/>']))
    cache.atualizar_registro(0, ["40", "50", "60"], ["4", "5", "6"])
    _, registros = cache.para_xml()
    assert '<r><n v="1"/><n v="9"/></r>' in registros
    assert '<r><n v="40"/><n v="50"/><n v="60"/></r>' in registros


def test_atualizar_registro_valores_antigos_inexistentes_aborta():
    cache = pc.CachePivot(_def([]), _records(['<n v="1"/>', '<n v="2"/>']))
    with pytest.raises(RuntimeError, match="registro"):
        cache.atualizar_registro(0, ["9"], ["7"])


def test_atualizar_registro_none_preserva_posicao():
    """None na posição preserva o valor atual (coluna sem dado no NI)."""
    cache = pc.CachePivot(_def([]), _records(['<n v="1"/><n v="2"/><n v="3"/>']))
    cache.atualizar_registro(0, ["10", None, "30"], ["1", "2", "3"])
    _, registros = cache.para_xml()
    assert '<r><n v="10"/><n v="2"/><n v="30"/></r>' in registros


def test_atualizar_registro_substitui_blank_por_numero():
    """<m/> ganha <n> quando o bloco traz valor naquela posição."""
    cache = pc.CachePivot(_def([]), _records(['<n v="1"/><m/>']))
    cache.atualizar_registro(0, ["9", "8"], ["1", None])
    _, registros = cache.para_xml()
    assert '<r><n v="9"/><n v="8"/></r>' in registros


def test_atualizar_registro_record_parcial_omite_blank_final():
    """Record sem os <m/> finais (forma compacta do Excel) localiza e
    atualiza pelas posições presentes — cauda None não contradiz."""
    cache = pc.CachePivot(_def([]), _records(['<n v="1"/><n v="2"/><n v="3"/>']))
    cache.atualizar_registro(0, ["10", None, None, None, None, None, None],
                             ["1", "2", "3", None, None, None, None])
    _, registros = cache.para_xml()
    assert '<r><n v="10"/><n v="2"/><n v="3"/></r>' in registros


def test_atualizar_registro_valor_alem_do_record_aborta():
    cache = pc.CachePivot(_def([]), _records(['<n v="1"/>']))
    with pytest.raises(RuntimeError, match="além"):
        cache.atualizar_registro(0, ["9", "8"], ["1"])


def test_atualizar_registro_preserva_string_e_wildcard():
    """<s> (string histórica da base) é preservada quando o valor novo é None;
    None em valores_antigos é wildcard (posições não comparadas)."""
    cache = pc.CachePivot(_def([]), _records(
        ['<n v="21.87"/><s v="              "/><n v="0"/>']))
    cache.atualizar_registro(0, ["50000", None, None], ["21.87", None, None])
    _, registros = cache.para_xml()
    assert '<r><n v="50000"/><s v="              "/><n v="0"/></r>' in registros


def test_atualizar_registro_converte_string_em_numero_quando_valor_novo():
    """<s> com valor novo (≠ None) vira <n> — a célula correspondente foi
    convertida na planilha (quitação do NI); o record acompanha a planilha."""
    cache = pc.CachePivot(_def([]), _records(
        ['<n v="21.87"/><s v="              "/><n v="0"/>']))
    cache.atualizar_registro(0, ["50000", "10.69", None],
                             ["21.87", None, None])
    _, registros = cache.para_xml()
    assert '<r><n v="50000"/><n v="10.69"/><n v="0"/></r>' in registros


def test_inserir_registros_posiciona_no_meio():
    """Linhas novas da BD2 entram ORDENADAS no meio do cache: inserir antes
    do record de índice `posicao` (0-based)."""
    cache = pc.CachePivot(_def([]), _records(['<n v="1"/>', '<n v="3"/>']))
    cache.inserir_registros(1, ['<r><n v="2"/></r>'])
    _, registros = cache.para_xml()
    assert '<r><n v="1"/></r><r><n v="2"/></r><r><n v="3"/></r>' in registros
    assert cache.n_registros == 3


def test_inserir_registros_posicao_invalida_aborta():
    cache = pc.CachePivot(_def([]), _records(['<n v="1"/>']))
    with pytest.raises(RuntimeError, match="posição"):
        cache.inserir_registros(5, ['<r><n v="2"/></r>'])


def test_atualizar_registro_dois_records_candidatos_aborta_por_ambiguidade():
    cache = pc.CachePivot(_def([]), _records(
        ['<n v="1"/><n v="1"/>', '<n v="2"/><n v="2"/>', '<n v="2"/><n v="2"/>']))
    with pytest.raises(RuntimeError, match="único"):
        cache.atualizar_registro(0, ["9", "9"], ["2", "2"])


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


def test_para_xml_preserva_contains_string_zero_em_campo_de_data():
    """O Excel grava containsString="0" nos campos de data (Vencimento,
    Entrega, Baixa) e NÃO abre o arquivo sem o atributo — causa raiz do
    aviso de reparo de 09/09. O recálculo não pode removê-lo."""
    campos = ['<cacheField name="Vencimento" numFmtId="14"><sharedItems '
              'containsSemiMixedTypes="0" containsNonDate="0" containsDate="1" '
              'containsString="0" minDate="2024-01-16T00:00:00" '
              'maxDate="2065-02-16T00:00:00" count="2">'
              '<d v="2024-01-16T00:00:00"/><d v="2065-02-15T00:00:00"/>'
              '</sharedItems></cacheField>']
    cache = pc.CachePivot(_def(campos), _records(['<x v="0"/>']))
    cache.obter_indice("Vencimento", "d", "2026-10-29T00:00:00")
    definicao, _ = cache.para_xml()
    assert 'containsString="0"' in definicao


def test_para_xml_nao_marca_misto_por_causa_de_blank():
    """O <m/> é blank (containsBlank), não um tipo de valor — um campo só de
    datas com blank não pode ganhar containsMixedTypes="1" (o Excel original
    não grava o atributo nesse caso)."""
    campos = ['<cacheField name="Baixa" numFmtId="0"><sharedItems '
              'containsNonDate="0" containsDate="1" containsString="0" '
              'containsBlank="1" count="2">'
              '<d v="2026-07-17T00:00:00"/><m/></sharedItems></cacheField>']
    cache = pc.CachePivot(_def(campos), _records(['<x v="0"/>']))
    cache.obter_indice("Baixa", "d", "2026-09-02T00:00:00")
    definicao, _ = cache.para_xml()
    assert 'containsMixedTypes="1"' not in definicao
    assert 'containsBlank="1"' in definicao
    assert 'containsString="0"' in definicao


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
# Slicers
# ==============================================================================
SLICER_TIPO = (DECL
               + '<slicerCache xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" '
               + 'sourceName="Tipo de remessa" name="SegmentaçãoDeDados3">'
               + '<pivotTables><pivotTable tabId="3" name="Pivot3"/></pivotTables>'
               + '<items count="3"><i x="0" s="1"/><i x="1" s="1"/><i x="2" nd="1"/></items>'
               + '</slicerCache>')


def test_anexar_itens_slicer():
    saida = pc.anexar_itens_slicer(SLICER_TIPO, [3, 4])
    assert 'count="5"' in saida
    assert '<i x="3" s="1"/>' in saida and '<i x="4" s="1"/>' in saida
    assert '<i x="0" s="1"/>' in saida            # itens antigos intactos


def test_slicer_sem_items_levanta():
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


def test_anexar_itens_pivot_mantem_default_como_ultimo():
    """O Excel exige <item t="default"/> como ÚLTIMO item do <items>;
    os novos itens entram ANTES dele (regressão do aviso de reparo)."""
    saida = pc.anexar_itens_pivot(PIVOT, 2, [3, 4])
    assert '<items count="6">' in saida
    assert '<item x="3"/><item x="4"/><item t="default"/>' in saida
    assert '<item x="0"/><item x="1"/><item m="1" x="2"/>' in saida  # intactos


def test_anexar_itens_pivot_default_com_sd_continua_ultimo():
    piv_sd = PIVOT.replace('<item t="default"/>', '<item t="default" sd="0"/>')
    saida = pc.anexar_itens_pivot(piv_sd, 2, [7], com_sd=True)
    assert '<items count="5">' in saida
    assert '<item x="7" sd="0"/><item t="default" sd="0"/>' in saida


def test_anexar_itens_pivot_sem_items_levanta():
    with pytest.raises(RuntimeError, match="sem <items>"):
        pc.anexar_itens_pivot(PIVOT, 0, [1])


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
        pc.nome_da_rel({}, "xl/pivotCache/pivotCacheDefinition1.xml")
