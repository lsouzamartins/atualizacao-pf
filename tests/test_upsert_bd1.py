"""Testes do upsert da BD1 (baixas/valores de remessas JÁ existentes).

Histórico: a Fase 3a só ANEXA remessas novas — baixa de remessa existente
nunca era aplicada (comportamento herdado do motor COM). Bug de 09/09/2026:
as baixas de 02/09 das remessas 138055 (F=31/03 antiga, Pago parcial) e
146283 (R) (F vazio, Pago=0) não apareciam no site.

Convenções do arquivo real (levantadas em 09/09/2026):
- célula F COM data usa s="57" (100% das 5.633 ocorrências); F vazio usa s="58";
- o record do cache é localizado pelo x-ref da Remessa (entrada 0), NÃO pela
  posição — o cache da base vem dessincronizado das linhas em trechos antigos.
"""
import re
from datetime import date, datetime

import pandas as pd
import pytest

import integracao_excel as ie
import pivot_cache as pc

DECL = ie._DECL

SER_02SET = (date(2026, 9, 2) - ie.SERIAL_EPOCA).days       # 46267
SER_31MAR = (date(2026, 3, 31) - ie.SERIAL_EPOCA).days      # 46112
SER_28JAN = (date(2026, 1, 28) - ie.SERIAL_EPOCA).days
SER_13MAR = (date(2026, 3, 13) - ie.SERIAL_EPOCA).days
SER_30JAN = (date(2026, 1, 30) - ie.SERIAL_EPOCA).days


def _sst(textos):
    sis = "".join(f"<si><t>{t}</t></si>" for t in textos)
    return (DECL
            + '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
              f'count="9" uniqueCount="{len(textos)}">{sis}</sst>')


def _strings():
    """SST sintético alinhado com a _sheet5_minima: as células t="s" usam os
    índices 22 (H2) e 23 (A3) — o SST do arquivo real tem milhares de <si>."""
    textos = [f"pre{i}" for i in range(24)]
    textos[22] = "HOSPITAL ABC"
    textos[23] = "146283 (R)"
    return ie._StringsCompartilhadas(_sst(textos))


def _sheet5_minima():
    """BD1 sintética: header + 2 linhas de dados (138055 numérica com F vazio;
    146283 (R) string com F=31/03 e Pago parcial)."""
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    cab = ["Remessa", "Protocolo", "Emissão", "Vencimento", "Entrega",
           "Baixa", "Nota Fiscal", "Convênio", "Faturado", "Valor Pago",
           "Valor ISS", "Vlr Guia", "% Pré-glosa", "Valor Glosa", "% Glosa",
           "Atraso", "Faturas", "R", "S", "T", "U", "V"]
    header = "".join(f'<c r="{c}1" t="s"><v>{i}</v></c>'
                     for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUV"))
    row2 = ('<row r="2">'
            '<c r="A2"><v>138055</v></c>'
            '<c r="B2"><v>331224784456</v></c>'
            f'<c r="C2" s="57"><v>{SER_28JAN}</v></c>'
            f'<c r="D2" s="57"><v>{SER_13MAR}</v></c>'
            f'<c r="E2" s="57"><v>{SER_30JAN}</v></c>'
            '<c r="F2" s="58"/>'
            '<c r="G2" s="43"/>'
            '<c r="H2" t="s"><v>22</v></c>'          # HOSPITAL ABC
            '<c r="I2"><v>6997.92</v></c><c r="J2"><v>0</v></c><c r="K2"><v>0</v></c>'
            '<c r="L2"><v>6997.92</v></c><c r="M2"><v>0</v></c><c r="N2"><v>0</v></c>'
            '<c r="O2"><v>0</v></c><c r="P2"><v>0</v></c><c r="Q2"><v>1</v></c>'
            '</row>')
    row3 = ('<row r="3">'
            '<c r="A3" s="54" t="s"><v>23</v></c>'    # 146283 (R)
            '<c r="B3"><v>17099679</v></c>'
            f'<c r="C3" s="57"><v>{SER_28JAN}</v></c>'
            f'<c r="D3" s="57"><v>{SER_13MAR}</v></c>'
            f'<c r="E3" s="57"><v>{SER_30JAN}</v></c>'
            f'<c r="F3" s="57"><v>{SER_31MAR}</v></c>'
            '<c r="G3" s="43"/>'
            '<c r="H3" t="s"><v>22</v></c>'
            '<c r="I3"><v>5360.22</v></c><c r="J3"><v>1637.7</v></c><c r="K3"><v>0</v></c>'
            '<c r="L3"><v>5360.22</v></c><c r="M3"><v>0</v></c><c r="N3"><v>0</v></c>'
            '<c r="O3"><v>0</v></c><c r="P3"><v>0</v></c><c r="Q3"><v>1</v></c>'
            '</row>')
    return (DECL + f'<worksheet {ns}><dimension ref="A1:V3"/><sheetData>'
            + f'<row r="1">{header}</row>{row2}{row3}</sheetData></worksheet>')


def _wpd_com_baixas():
    return pd.DataFrame({
        "Remessa": [138055, "146283 (R)"],
        "Protocolo": [331224784456, 17099679],
        "Emissão": [datetime(2026, 1, 28), datetime(2026, 6, 25)],
        "Vencimento": [datetime(2026, 3, 13), datetime(2026, 8, 13)],
        "Entrega": [datetime(2026, 1, 30), datetime(2026, 6, 25)],
        "Baixa": [datetime(2026, 9, 2), datetime(2026, 9, 2)],
        "Nota Fiscal": [None, None],
        "Convênio": ["HOSPITAL ABC", "HOSPITAL ABC"],
        "Faturado": [6997.92, 5360.22],
        "Valor Pago": [6997.92, 5360.22],
        "Valor ISS": [0.0, 0.0],
        "Vlr Guia": [6997.92, 5360.22],
        "% Pré-glosa": [0.0, 0.0],
        "Valor Glosa": [0.0, 0.0],
        "% Glosa": [0.0, 0.0],
        "Atraso": [0.0, 0.0],
        "Faturas": [1.0, 1.0],
    })


# ==============================================================================
# Upsert na planilha (sheet5.xml)
# ==============================================================================
def test_upsert_bd1_preenche_baixa_vazia_e_atualiza_pago():
    strings = _strings()
    xml = _sheet5_minima()
    resultado = ie._upsert_bd1(xml, _wpd_com_baixas(),
                               {"138055", "146283 (R)"}, strings)
    assert resultado is not None
    xml_novo, mudancas, n_celulas = resultado
    assert n_celulas == 4                      # F2, J2, F3, J3
    assert '<c r="F2" s="57"><v>46267</v></c>' in xml_novo   # vazio -> data s=57
    assert '<c r="J2"><v>6997.92</v></c>' in xml_novo
    assert f'<c r="F3" s="57"><v>{SER_02SET}</v></c>' in xml_novo  # estilo mantido
    assert '<c r="J3"><v>5360.22</v></c>' in xml_novo
    assert {m["remessa_norm"] for m in mudancas} == {"138055", "146283 (R)"}
    assert all({"Baixa", "Valor Pago"} <= set(m["campos"]) for m in mudancas)


def test_upsert_bd1_nao_reescreve_celula_igual_nem_campos_estruturais():
    strings = _strings()
    xml = _sheet5_minima()
    xml_novo, mudancas, _ = ie._upsert_bd1(xml, _wpd_com_baixas(),
                                            {"138055", "146283 (R)"}, strings)
    # I (Faturado) idêntico ao WPD: célula preservada byte a byte
    assert '<c r="I2"><v>6997.92</v></c>' in xml_novo
    # B (Protocolo), C/D/E (datas), H (Convênio) intocados
    assert '<c r="B2"><v>331224784456</v></c>' in xml_novo
    assert f'<c r="C2" s="57"><v>{SER_28JAN}</v></c>' in xml_novo
    assert '<c r="H2" t="s"><v>22</v></c>' in xml_novo


def test_upsert_bd1_sem_mudanca_devolve_none():
    strings = _strings()
    xml = _sheet5_minima()
    wpd = _wpd_com_baixas()
    wpd["Baixa"] = [None, None]
    wpd["Valor Pago"] = [0.0, 1637.7]
    assert ie._upsert_bd1(xml, wpd, {"138055", "146283 (R)"}, strings) is None


def test_upsert_bd1_baixa_nula_no_wpd_nao_desfaz_baixa_existente():
    strings = _strings()
    xml = _sheet5_minima()
    wpd = _wpd_com_baixas()
    wpd["Baixa"] = [None, None]               # WPD sem baixa
    wpd["Valor Pago"] = [0.0, 9999.0]         # mas valores mudaram
    xml_novo, mudancas, _ = ie._upsert_bd1(xml, wpd,
                                            {"138055", "146283 (R)"}, strings)
    assert f'<c r="F3" s="57"><v>{SER_31MAR}</v></c>' in xml_novo  # F3 intacta
    assert '<c r="J3"><v>9999</v></c>' in xml_novo
    assert all("Baixa" not in m["campos"] for m in mudancas)


# ==============================================================================
# Records do cache (pivotCacheRecords) — localização pela remessa
# ==============================================================================
def _cache_bd1_sintetico():
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    ns_r = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    campos = [
        '<cacheField name="Remessa" numFmtId="0"><sharedItems count="2">'
        '<n v="138055"/><s v="146283 (R)"/></sharedItems></cacheField>',
        '<cacheField name="Protocolo" numFmtId="0"><sharedItems count="1">'
        '<n v="331224784456"/></sharedItems></cacheField>',
        '<cacheField name="Emissão" numFmtId="14"/>',
        '<cacheField name="Vencimento" numFmtId="14"><sharedItems count="1">'
        '<d v="2026-03-13T00:00:00"/></sharedItems></cacheField>',
        '<cacheField name="Entrega" numFmtId="14"><sharedItems count="1">'
        '<d v="2026-01-30T00:00:00"/></sharedItems></cacheField>',
        '<cacheField name="Baixa" numFmtId="14"><sharedItems count="2">'
        '<m/><d v="2026-08-31T00:00:00"/></sharedItems></cacheField>',
        '<cacheField name="Nota Fiscal" numFmtId="0"/>',
        '<cacheField name="Convênio" numFmtId="0"><sharedItems count="1">'
        '<s v="HOSPITAL ABC"/></sharedItems></cacheField>',
    ] + [f'<cacheField name="{n}" numFmtId="0"/>' for n in (
        "Faturado", "Valor Pago", "Valor ISS", "Vlr Guia", "% Pré-glosa",
        "Valor Glosa", "% Glosa", "Atraso", "Faturas",
        "Atrasado", "A vencer", "Recurso", "Recurso pago")] + [
        '<cacheField name="Tipo de remessa" numFmtId="0">'
        '<sharedItems count="3"><s v="Comum"/><s v="Recurso"/><m/></sharedItems></cacheField>',
    ]
    def_xml = (DECL + f'<pivotCacheDefinition {ns} {ns_r} '
               + 'refreshedBy="Sistema" refreshedDate="46200.0" recordCount="2" '
               + 'createdVersion="7" refreshedVersion="7" refreshOnLoad="1">'
               + '<cacheSource type="worksheet">'
               + '<worksheetSource name="BD_1" ref="A1:V3" sheet="BD1"/>'
               + '</cacheSource><cacheFields count="22">'
               + "".join(campos) + '</cacheFields></pivotCacheDefinition>')
    # record 0 = 138055 (baixa vazia, pago 0, atrasado = guia); record 1 = 146283 (R)
    rec_xml = (DECL
               + '<pivotCacheRecords xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
               + 'count="2">'
               + '<r><x v="0"/><x v="0"/><d v="2026-01-28T00:00:00"/>'
               + '<x v="0"/><x v="0"/><m/><m/><x v="0"/>'
               + '<n v="6997.92"/><n v="0"/><n v="0"/><n v="6997.92"/><n v="0"/>'
               + '<n v="0"/><n v="0"/><n v="0"/><n v="1"/>'
               + '<n v="6997.92"/><n v="0"/><n v="0"/><n v="0"/><x v="0"/></r>'
               + '<r><x v="1"/><x v="0"/><d v="2026-06-25T00:00:00"/>'
               + '<x v="0"/><x v="0"/><x v="1"/><m/><x v="0"/>'
               + '<n v="5360.22"/><n v="1637.7"/><n v="0"/><n v="5360.22"/><n v="0"/>'
               + '<n v="0"/><n v="0"/><n v="0"/><n v="1"/>'
               + '<n v="5360.22"/><n v="0"/><n v="0"/><n v="0"/><x v="0"/></r>'
               + '</pivotCacheRecords>')
    return def_xml, rec_xml


def _entradas(bloco):
    return re.findall(r'<(?:x|n|s|d|m)\b[^>]*/>', bloco)


def test_atualizar_records_bd1_por_remessa_atualiza_baixa_pago_e_calculados():
    def_xml, rec_xml = _cache_bd1_sintetico()
    cache = pc.CachePivot(def_xml, rec_xml)
    dados = ie._converter_linha_wpd(_wpd_com_baixas().iloc[0])
    mudancas = [{"remessa_norm": "138055", "num_linha": 2,
                 "dados": dados, "campos": ["Baixa", "Valor Pago"]}]
    ie._atualizar_records_bd1(cache, mudancas, date(2026, 9, 9))

    definicao, registros = cache.para_xml()
    # item novo de data no sharedItems do campo Baixa (índice 2)
    assert '<d v="2026-09-02T00:00:00"/>' in definicao
    assert 'maxDate="2026-09-02T00:00:00"' in definicao
    blocos = re.findall(r'<r>.*?</r>', registros, re.S)
    assert len(blocos) == 2                       # nenhum record criado/removido
    alvo = [b for b in blocos if b.startswith('<r><x v="0"/>')][0]
    ent = _entradas(alvo)
    assert ent[5] == '<x v="2"/>'                 # baixa -> novo item de data
    assert ent[9] == '<n v="6997.92"/>'           # valor pago atualizado
    assert ent[17] == '<n v="0"/>'                # Atrasado zera com a baixa
    assert ent[0] == '<x v="0"/>'                 # Remessa/Protocolo preservados
    assert ent[1] == '<x v="0"/>'
    outro = [b for b in blocos if b.startswith('<r><x v="1"/>')][0]
    assert _entradas(outro)[5] == '<x v="1"/>'    # record vizinho intocado


def test_atualizar_records_bd1_falha_se_remessa_nao_localizada():
    def_xml, rec_xml = _cache_bd1_sintetico()
    cache = pc.CachePivot(def_xml, rec_xml)
    dados = ie._converter_linha_wpd(_wpd_com_baixas().iloc[0])
    mudancas = [{"remessa_norm": "999999", "num_linha": 2,
                 "dados": dados, "campos": ["Baixa"]}]
    with pytest.raises(RuntimeError, match="não localiz"):
        ie._atualizar_records_bd1(cache, mudancas, date(2026, 9, 9))
