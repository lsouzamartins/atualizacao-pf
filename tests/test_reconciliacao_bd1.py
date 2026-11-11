"""Reconciliação BD1 × WPD (11/11/2026).

A base do site é encadeada e o upsert só toca as remessas que estão no WPD do
dia — a que sai do relatório ficava na base para sempre (62 guias de
out–dez/2026, R$ 265.040,35 na Posição de 11/11). A reconciliação remove a
remessa ausente do WPD, SEM baixa e com vencimento a partir de 01/09/2026.
"""
import re
from datetime import date

import pandas as pd
import pytest

import integracao_excel as ie
import pivot_cache as pc

DECL = ie._DECL
NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
NS_R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def _sst(textos):
    sis = "".join(f"<si><t>{t}</t></si>" for t in textos)
    return (DECL
            + '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
              f'count="9" uniqueCount="{len(textos)}">{sis}</sst>')


def _serial(d):
    return (d - ie.SERIAL_EPOCA).days


def _row(n, remessa, conv_idx, venc, baixa=None):
    """Linha da BD1 com o essencial: A remessa, C emissão, D vencimento,
    F baixa (vazia quando None), H convênio e as fórmulas R/V."""
    cel_baixa = (f'<c r="F{n}" s="56"><v>{_serial(baixa)}</v></c>'
                 if baixa is not None else f'<c r="F{n}" s="39"/>')
    return (f'<row r="{n}">'
            f'<c r="A{n}"><v>{remessa}</v></c>'
            f'<c r="B{n}" s="55"><v>1</v></c>'
            f'<c r="C{n}" s="56"><v>{_serial(date(2026, 8, 1))}</v></c>'
            f'<c r="D{n}" s="56"><v>{_serial(venc)}</v></c>'
            + cel_baixa
            + f'<c r="H{n}" s="14" t="s"><v>{conv_idx}</v></c>'
            f'<c r="R{n}" s="32"><f>SUMIFS(L{n},D{n},"&lt;"&amp;TODAY(),F{n},"")</f><v>0</v></c>'
            f'<c r="V{n}" s="34" t="str"><f>IF(RIGHT(A{n},3)="(R)","Recurso","Comum")</f>'
            '<v>Comum</v></c>'
            '</row>')


def _xml_bd1(rows):
    return (DECL
            + f'<worksheet {NS}>'
            + f'<dimension ref="A1:V{len(rows) + 1}"/>'
            + '<sheetData>'
            + '<row r="1"><c r="A1" t="s"><v>0</v></c></row>'
            + "".join(rows)
            + '</sheetData></worksheet>')


def _wpd(remessas):
    return pd.DataFrame({"Remessa": remessas})


def test_remove_ausente_sem_baixa_a_partir_do_corte():
    """Remove só a remessa que saiu do WPD, não tem Baixa e vence a partir de
    01/09/2026; a com baixa, a de vencimento antigo e a presente ficam. As
    rows seguintes são renumeradas — refs E fórmulas R–V acompanham."""
    strings = ie._StringsCompartilhadas(_sst(["Remessa", "AMIL"]))
    xml = _xml_bd1([
        _row(2, 900001, 1, date(2026, 11, 20)),                        # REMOVE
        _row(3, 900002, 1, date(2026, 11, 20), baixa=date(2026, 11, 10)),
        _row(4, 900003, 1, date(2026, 2, 10)),                         # antes do corte
        _row(5, 900004, 1, date(2026, 11, 20)),                        # está no WPD
    ])
    resultado = ie._remover_ausentes_bd1(xml, _wpd([900004]), strings)
    assert resultado is not None
    texto, fim, removidas = resultado
    assert removidas == ["900001"]
    assert fim == 4
    assert '<dimension ref="A1:V4"/>' in texto
    nums = [int(n) for n in re.findall(r'<row r="(\d+)"', texto)]
    assert nums == [1, 2, 3, 4]
    assert "900001" not in texto
    # a antiga linha 4 (900003) virou 3, com as fórmulas renumeradas
    assert '<c r="A3"><v>900003</v></c>' in texto
    assert 'SUMIFS(L3,D3' in texto
    assert 'IF(RIGHT(A3,3)' in texto
    # a antiga linha 5 virou 4
    assert '<c r="A4"><v>900004</v></c>' in texto


def test_sem_ausentes_devolve_none():
    strings = ie._StringsCompartilhadas(_sst(["Remessa"]))
    xml = _xml_bd1([_row(2, 900001, 0, date(2026, 11, 20))])
    assert ie._remover_ausentes_bd1(xml, _wpd([900001]), strings) is None


def test_ausente_com_baixa_ou_vencimento_antigo_fica():
    """A regra do corte preserva o histórico: baixa preenchida no meio do
    período e as remessas de jan–mar/2026 da base de origem."""
    strings = ie._StringsCompartilhadas(_sst(["Remessa"]))
    xml = _xml_bd1([
        _row(2, 900001, 0, date(2026, 10, 5), baixa=date(2026, 10, 1)),
        _row(3, 900002, 0, date(2026, 3, 10)),
    ])
    assert ie._remover_ausentes_bd1(xml, _wpd([]), strings) is None


def _cache_bd1(remessas, indices):
    campos = ('<cacheField name="Remessa" numFmtId="0"><sharedItems '
              f'count="{len(remessas)}">'
              + "".join(f'<n v="{r}"/>' for r in remessas)
              + '</sharedItems></cacheField>')
    definicao = (DECL
                 + f'<pivotCacheDefinition {NS} {NS_R} recordCount="{len(indices)}">'
                 + '<cacheSource type="worksheet"><worksheetSource name="BD_1"/></cacheSource>'
                 + f'<cacheFields count="1">{campos}</cacheFields>'
                 + '</pivotCacheDefinition>')
    registros = (DECL
                 + f'<pivotCacheRecords {NS} {NS_R} count="{len(indices)}">'
                 + "".join(f'<r><x v="{i}"/></r>' for i in indices)
                 + '</pivotCacheRecords>')
    return pc.CachePivot(definicao, registros)


def test_remover_records_bd1_pela_chave_da_remessa():
    cache = _cache_bd1(["900001", "900002", "900003"], [0, 1, 2])
    ie._remover_records_bd1(cache, ["900002"])
    assert cache.n_registros == 2
    _, registros = cache.para_xml()
    assert '<r><x v="0"/></r>' in registros
    assert '<r><x v="2"/></r>' in registros
    assert '<r><x v="1"/></r>' not in registros
    ie._remover_records_bd1(cache, [])  # lista vazia: não altera
    assert cache.n_registros == 2


def test_remover_records_bd1_remessa_ausente_levanta():
    cache = _cache_bd1(["900001"], [0])
    with pytest.raises(RuntimeError, match="não localizada"):
        ie._remover_records_bd1(cache, ["999999"])


def test_remover_records_bd1_aceita_remessa_gravada_como_texto():
    """O mesmo número pode estar no sharedItems como <n> (117129) ou como
    <s> ("117129"); o record pode apontar para qualquer um dos dois."""
    campos = ('<cacheField name="Remessa" numFmtId="0"><sharedItems count="1">'
              '<s v="150803"/></sharedItems></cacheField>')
    definicao = (DECL
                 + f'<pivotCacheDefinition {NS} {NS_R} recordCount="1">'
                 + '<cacheSource type="worksheet"><worksheetSource name="BD_1"/></cacheSource>'
                 + f'<cacheFields count="1">{campos}</cacheFields>'
                 + '</pivotCacheDefinition>')
    registros = (DECL
                 + f'<pivotCacheRecords {NS} {NS_R} count="1">'
                 '<r><x v="0"/></r></pivotCacheRecords>')
    cache = pc.CachePivot(definicao, registros)
    ie._remover_records_bd1(cache, ["150803"])
    assert cache.n_registros == 0
