"""Reconciliação BD2 × NI (11/11/2026).

A BD2 é upsert por (Convênio, Data): quando o faturamento lança o depósito no
convênio errado e corrige depois, o site anexa a chave nova e a antiga fica
para sempre na base — caso real de 04/11/2026: BRADESCO SEGUROS R$ 1.637,71
(ao lado da BRADESCO OPERADORA PLANO correta, já quitada), que a aba À Quitar
continuava exibindo. A reconciliação remove a linha órfã: Não Identificado > 0,
sem quitação, fora do NI do dia e com a contrapartida quitada no mesmo dia.
"""
import re
from datetime import date

import pytest

import integracao_excel as ie

DECL = ie._DECL
NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'

DATA = date(2026, 11, 4)
CORRETO = [1637.71, 1637.71, 1637.71, 0, 0, 0, 0]      # C..I: dep liq, dep bruto,
ORFAO = [1637.71, 1637.71, 0, 1637.71, 0, 0, 1637.71]  # quitação, não id, ...
AMIL = [100.0, 100.0, 0, 100.0, 0, 0, 100.0]


def _sst(textos):
    sis = "".join(f"<si><t>{t}</t></si>" for t in textos)
    return (DECL
            + '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
              f'count="9" uniqueCount="{len(textos)}">{sis}</sst>')


def _serial(d):
    return (d - ie.SERIAL_EPOCA).days


def _row(n, conv_idx, valores, data=DATA, flag=1):
    """Linha da BD2: A convênio (shared string), B data serial, C–I valores,
    J flag."""
    cels = [f'<c r="A{n}" s="5" t="s"><v>{conv_idx}</v></c>',
            f'<c r="B{n}" s="15"><v>{_serial(data)}</v></c>']
    for letra, v in zip("CDEFGHI", valores):
        cels.append(f'<c r="{letra}{n}" s="43"><v>{v}</v></c>')
    cels.append(f'<c r="J{n}" s="53"><v>{flag}</v></c>')
    return f'<row r="{n}">{"".join(cels)}</row>'


def _xml_bd2(rows):
    return (DECL
            + f'<worksheet {NS}>'
            + f'<dimension ref="A1:J{len(rows) + 1}"/>'
            + '<sheetData>'
            + '<row r="1"><c r="A1" t="s"><v>0</v></c></row>'
            + "".join(rows)
            + '</sheetData></worksheet>')


def _bloco(linhas):
    """linhas = [(convenio, data, valores C..I)] → bloco do NI como o motor vê."""
    return [{"convenio": conv, "data": _serial(d), "valores": vals}
            for conv, d, vals in linhas]


STRINGS = ("Convênio", "BRADESCO OPERADORA PLANO", "BRADESCO SEGUROS", "AMIL")


def test_remove_orfao_com_contrapartida_e_renumera():
    """A linha BRADESCO SEGUROS (não identificada, sem quitação, fora do NI)
    sai porque o mesmo valor está quitado na BRADESCO OPERADORA PLANO; a AMIL
    (sem contrapartida) fica e a row seguinte é renumerada com a dimension."""
    strings = ie._StringsCompartilhadas(_sst(STRINGS))
    xml = _xml_bd2([
        _row(2, 1, CORRETO),
        _row(3, 2, ORFAO),   # REMOVE
        _row(4, 3, AMIL),    # sem contrapartida → fica
    ])
    bloco = _bloco([("BRADESCO OPERADORA PLANO", DATA, CORRETO)])
    resultado = ie._remover_orfaos_bd2(xml, bloco, strings)
    assert resultado is not None
    texto, fim, removidas = resultado
    assert [r["linha"] for r in removidas] == [3]
    assert removidas[0]["convenio"] == "BRADESCO SEGUROS"
    assert removidas[0]["valor"] == pytest.approx(1637.71)
    assert fim == 3
    assert '<dimension ref="A1:J3"/>' in texto
    assert [int(n) for n in re.findall(r'<row r="(\d+)"', texto)] == [1, 2, 3]
    # a AMIL (linha 4) virou 3
    assert '<c r="A3" s="5" t="s"><v>3</v></c>' in texto
    assert '<row r="4"' not in texto


def test_orfao_sem_contrapartida_fica_e_avisa(capsys):
    """Sem par quitado no mesmo dia não há prova de reclassificação — a linha
    fica e o processamento registra o aviso."""
    strings = ie._StringsCompartilhadas(_sst(STRINGS))
    xml = _xml_bd2([_row(2, 2, ORFAO)])
    bloco = _bloco([("BRADESCO OPERADORA PLANO", DATA, [50, 50, 50, 0, 0, 0, 0])])
    assert ie._remover_orfaos_bd2(xml, bloco, strings) is None
    saida = capsys.readouterr().out
    assert "sem contrapartida" in saida
    assert "BRADESCO SEGUROS" in saida


def test_orfao_fora_do_periodo_do_ni_fica():
    """Linha de 2025 (fora do período coberto pelo NI de hoje) nunca é alvo —
    o histórico antigo da BD2 é preservado."""
    strings = ie._StringsCompartilhadas(_sst(STRINGS))
    xml = _xml_bd2([_row(2, 1, ORFAO, data=date(2025, 1, 1))])
    bloco = _bloco([("BRADESCO OPERADORA PLANO", DATA, CORRETO)])
    assert ie._remover_orfaos_bd2(xml, bloco, strings) is None


def test_orfao_com_quitacao_parcial_fica():
    """Depósito parcialmente quitado não é linha órfã de reclassificação:
    remover apagaria o histórico de uma quitação real."""
    strings = ie._StringsCompartilhadas(_sst(STRINGS))
    parcial = [1637.71, 1637.71, 100.0, 1537.71, 0, 0, 1537.71]
    xml = _xml_bd2([_row(2, 1, CORRETO), _row(3, 2, parcial)])
    bloco = _bloco([("BRADESCO OPERADORA PLANO", DATA, CORRETO)])
    assert ie._remover_orfaos_bd2(xml, bloco, strings) is None


def test_chave_confirmada_pelo_ni_fica():
    """Se o NI ainda lista a chave, o item continua em aberto de verdade."""
    strings = ie._StringsCompartilhadas(_sst(STRINGS))
    xml = _xml_bd2([_row(2, 1, CORRETO), _row(3, 2, ORFAO)])
    bloco = _bloco([("BRADESCO OPERADORA PLANO", DATA, CORRETO),
                    ("BRADESCO SEGUROS", DATA, ORFAO)])
    assert ie._remover_orfaos_bd2(xml, bloco, strings) is None


def test_remove_duas_linhas_orfas():
    strings = ie._StringsCompartilhadas(
        _sst(("Convênio", "CONV A", "CONV B", "CONV C", "CONV D")))
    correta_a = [1000.0, 1000.0, 1000.0, 0, 0, 0, 0]
    orfa_b = [1000.0, 1000.0, 0, 1000.0, 0, 0, 1000.0]
    correta_c = [500.0, 500.0, 500.0, 0, 0, 0, 0]
    orfa_d = [500.0, 500.0, 0, 500.0, 0, 0, 500.0]
    xml = _xml_bd2([
        _row(2, 1, correta_a),
        _row(3, 2, orfa_b),   # REMOVE
        _row(4, 3, correta_c),
        _row(5, 4, orfa_d),   # REMOVE
    ])
    bloco = _bloco([("CONV A", DATA, correta_a), ("CONV C", DATA, correta_c)])
    resultado = ie._remover_orfaos_bd2(xml, bloco, strings)
    assert resultado is not None
    texto, fim, removidas = resultado
    assert [r["linha"] for r in removidas] == [3, 5]
    assert fim == 3
    assert [int(n) for n in re.findall(r'<row r="(\d+)"', texto)] == [1, 2, 3]
    assert '<c r="A3" s="5" t="s"><v>3</v></c>' in texto  # CONV C virou linha 3


def test_quitacao_em_texto_de_espacos_conta_como_zero():
    """Células históricas de quitação são strings de espaços — contam como
    zero (o depósito nunca foi casado), não como número."""
    strings = ie._StringsCompartilhadas(_sst(STRINGS + ("   ",)))
    espacos = len(STRINGS)
    xml = _xml_bd2([
        _row(2, 1, CORRETO),
        _row(3, 2, ORFAO).replace(
            f'<c r="E3" s="43"><v>0</v></c>',
            f'<c r="E3" s="43" t="s"><v>{espacos}</v></c>'),
    ])
    bloco = _bloco([("BRADESCO OPERADORA PLANO", DATA, CORRETO)])
    resultado = ie._remover_orfaos_bd2(xml, bloco, strings)
    assert resultado is not None
    assert [r["linha"] for r in resultado[2]] == [3]
