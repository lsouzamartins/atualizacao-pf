"""Conferência pós-execução: validações do dia, comparação com o Manual e
conciliação depósito × baixas por convênio (opções 1–3 de 11/11/2026)."""
from datetime import date

import openpyxl
import pandas as pd

import conferencia
from conferencia import (comparar_bd1, comparar_bd2, conciliar_convenios,
                         gerar_conferencia, validar_ni, validar_wpd)

COLS_BD1 = ["Remessa", "Protocolo", "Emissão", "Vencimento", "Entrega",
            "Baixa", "Nota Fiscal", "Convênio", "Faturado", "Valor Pago",
            "Valor ISS", "Vlr Guia", "% Pré-glosa", "Valor Glosa",
            "% Glosa", "Atraso", "Faturas"]
COLS_BD2 = ["Convênio", "Data", "Depósito Liq.", "Depósito Bruto",
            "Quitação", "Não Identificado", "Acordos", "Glosa Aceita",
            "Não Identificado Real", "Coluna1"]


def _criar_xlsx(caminho, bd1=None, bd2=None):
    livro = openpyxl.Workbook()
    padrao = livro.active
    livro.remove(padrao)

    aba1 = livro.create_sheet("BD1")
    aba1.append(COLS_BD1)
    for linha in bd1 or []:
        aba1.append([linha.get(c) for c in COLS_BD1])

    aba2 = livro.create_sheet("BD2")
    aba2.append(COLS_BD2)
    for linha in bd2 or []:
        aba2.append([linha.get(c) for c in COLS_BD2])

    livro.save(caminho)


def _bd1(remessa, convenio="BRADESCO SEGURO", venc=date(2026, 11, 10),
         baixa=None, faturado=1000.0, pago=0.0, glosa=0.0, nf=None):
    return {"Remessa": remessa, "Convênio": convenio, "Vencimento": venc,
            "Baixa": baixa, "Faturado": faturado, "Valor Pago": pago,
            "Valor Glosa": glosa, "Nota Fiscal": nf}


def _bd2(convenio, data, quitacao=0.0):
    return {"Convênio": convenio, "Data": data, "Depósito Bruto": quitacao,
            "Quitação": quitacao}


# ---------------------------------------------------------------- validar_wpd
def test_validar_wpd_aponta_vencimento_2065():
    df = pd.DataFrame([_bd1("139137", venc=date(2065, 1, 10)),
                       _bd1("135444", venc=date(2026, 12, 2))])
    alertas = validar_wpd(df, ano=2026)
    assert any("fora da janela" in a and "139137" in a for a in alertas)
    assert not any("135444" in a for a in alertas)


def test_validar_wpd_aponta_repetida_sem_convenio_e_negativo():
    df = pd.DataFrame([
        _bd1("100"),
        _bd1("100"),
        _bd1("200", convenio=None),
        _bd1("300", faturado=-50.0),
    ])
    alertas = validar_wpd(df, ano=2026)
    assert any("repetida" in a and "100" in a for a in alertas)
    assert any("sem convênio" in a and "200" in a for a in alertas)
    assert any("Faturado negativo" in a and "300" in a for a in alertas)


def test_validar_wpd_sem_problemas_devolve_lista_vazia():
    df = pd.DataFrame([_bd1("1"), _bd1("2")])
    assert validar_wpd(df, ano=2026) == []


def test_validar_wpd_vazio_avisa():
    assert validar_wpd(pd.DataFrame(), ano=2026)
    assert validar_wpd(None, ano=2026)


# ----------------------------------------------------------------- validar_ni
def _ni(convenio="GEAP", data=date(2026, 11, 4), bruto=100.0,
        quitacao=100.0, nao_id=0.0, acordos=0.0, glosa=0.0):
    return {"Convênio": convenio, "Data": data, "Depósito Bruto": bruto,
            "Quitação": quitacao, "Não Identificado": nao_id,
            "Acordos": acordos, "Glosa Aceita": glosa}


def test_validar_ni_aponta_deposito_que_nao_fecha():
    df = pd.DataFrame([_ni(convenio="GEAP", bruto=100.0, quitacao=60.0,
                           nao_id=30.0)])
    alertas = validar_ni(df)
    assert any("não fecha" in a and "GEAP" in a for a in alertas)


def test_validar_ni_identidade_fecha_sem_alerta():
    df = pd.DataFrame([_ni(bruto=100.0, quitacao=60.0, nao_id=30.0,
                           acordos=5.0, glosa=5.0)])
    assert validar_ni(df) == []


def test_validar_ni_negativo_e_estorno_legitimo_e_deposito_negativo_nao():
    estorno = pd.DataFrame([_ni(bruto=100.0, quitacao=120.0, nao_id=-20.0)])
    assert validar_ni(estorno) == []

    deposito = pd.DataFrame([_ni(bruto=-100.0, quitacao=-100.0)])
    alertas = validar_ni(deposito)
    assert any("Depósito Bruto negativo" in a for a in alertas)


# ---------------------------------------------------------------- comparar_bd1
def test_comparar_bd1_exclusivas_divergencias_e_totais(tmp_path):
    site = tmp_path / "site.xlsx"
    manual = tmp_path / "manual.xlsx"
    _criar_xlsx(
        site,
        bd1=[_bd1("1", baixa=date(2026, 11, 5), pago=100.0),
             _bd1("2", baixa=None),
             _bd1("3", venc=date(2026, 12, 2), faturado=5100.0)])
    _criar_xlsx(
        manual,
        bd1=[_bd1("1", baixa=None, pago=0.0),
             _bd1("2", baixa=None),
             _bd1("4", venc=date(2026, 11, 20), faturado=1700.0)])

    resultado = comparar_bd1(str(site), str(manual))

    assert resultado["site"] == 3 and resultado["manual"] == 3
    assert [r["remessa"] for r in resultado["so_manual"]] == ["4"]
    assert [r["remessa"] for r in resultado["so_site"]] == ["3"]
    assert [r["remessa"] for r in resultado["divergencias"]] == ["1"]
    assert "Baixa" in resultado["divergencias"][0]["difs"][0]

    nov = next(t for t in resultado["totais_mes"]
               if (t["ano"], t["mes"]) == (2026, 11))
    assert nov["site"] == 2000.0 and nov["manual"] == 3700.0
    dez = next(t for t in resultado["totais_mes"]
               if (t["ano"], t["mes"]) == (2026, 12))
    assert dez["site"] == 5100.0 and dez["manual"] == 0.0


# ---------------------------------------------------------------- comparar_bd2
def test_comparar_bd2_por_convenio_e_data(tmp_path):
    site = tmp_path / "site.xlsx"
    manual = tmp_path / "manual.xlsx"
    _criar_xlsx(site, bd2=[_bd2("GEAP", date(2026, 11, 4)),
                           _bd2("AMIL  ASSIST MEDICA INTERNAC",
                                date(2026, 11, 4))])
    _criar_xlsx(manual, bd2=[_bd2("GEAP", date(2026, 11, 4)),
                             _bd2("LEVE SAUDE", date(2026, 10, 2))])

    resultado = comparar_bd2(str(site), str(manual))

    assert resultado["site"] == 2 and resultado["manual"] == 2
    assert [(r["convenio"], r["data"]) for r in resultado["so_manual"]] == [
        ("LEVE SAUDE", date(2026, 10, 2))]
    assert [(r["convenio"], r["data"]) for r in resultado["so_site"]] == [
        ("AMIL ASSIST MEDICA INTERNAC", date(2026, 11, 4))]


# ---------------------------------------------------------- conciliar_convenios
def test_conciliar_usa_alias_e_fecha(tmp_path):
    arquivo = tmp_path / "final.xlsx"
    _criar_xlsx(
        arquivo,
        bd1=[_bd1("1", convenio="BRADESCO SEGURO",
                  baixa=date(2026, 11, 5), pago=1637.71)],
        bd2=[_bd2("BRADESCO SEGUROS", date(2026, 11, 4), quitacao=1637.71)])

    resultado = conciliar_convenios(str(arquivo), ano=2026)

    assert [r["situacao"] for r in resultado["linhas"]] == ["ok"]
    assert resultado["linhas"][0]["diferenca"] == 0.0
    assert resultado["sem_correspondencia"] == []


def test_conciliar_sem_alias_mostra_deposito_sem_baixa(tmp_path):
    arquivo = tmp_path / "final.xlsx"
    _criar_xlsx(
        arquivo,
        bd1=[_bd1("1", convenio="BRADESCO SEGURO",
                  baixa=date(2026, 11, 5), pago=1637.71)],
        bd2=[_bd2("BRADESCO SEGUROS", date(2026, 11, 4), quitacao=1637.71)])

    resultado = conciliar_convenios(str(arquivo), ano=2026, alias={})
    situacoes = sorted(r["situacao"] for r in resultado["linhas"])

    assert situacoes == ["sem_baixas", "sem_deposito"]
    assert "BRADESCO SEGURO" in resultado["sem_correspondencia"]


def test_conciliar_divergencia_e_baixa_sem_deposito(tmp_path):
    arquivo = tmp_path / "final.xlsx"
    _criar_xlsx(
        arquivo,
        bd1=[_bd1("1", convenio="GEAP SAUDE", baixa=date(2026, 11, 5),
                  pago=900.0),
             _bd1("2", convenio="INTEGRAL SAUDE", baixa=date(2026, 5, 5),
                  pago=713762.61)],
        bd2=[_bd2("GEAP", date(2026, 11, 4), quitacao=1000.0)])

    resultado = conciliar_convenios(str(arquivo), ano=2026)
    por_convenio = {r["convenio"]: r for r in resultado["linhas"]}

    assert por_convenio["GEAP"]["situacao"] == "divergente"
    assert por_convenio["GEAP"]["diferenca"] == 100.0
    assert por_convenio["INTEGRAL SAUDE"]["situacao"] == "sem_deposito"
    assert resultado["sem_correspondencia"] == ["INTEGRAL SAUDE"]


def test_conciliar_ignora_outros_anos(tmp_path):
    arquivo = tmp_path / "final.xlsx"
    _criar_xlsx(
        arquivo,
        bd1=[_bd1("1", baixa=date(2025, 11, 5), pago=100.0)],
        bd2=[_bd2("BRADESCO SEGUROS", date(2025, 11, 4), quitacao=100.0)])

    assert conciliar_convenios(str(arquivo), ano=2026)["linhas"] == []


# ------------------------------------------------------------ gerar_conferencia
def test_gerar_conferencia_traz_as_tres_secoes(tmp_path):
    final = tmp_path / "final.xlsx"
    manual = tmp_path / "manual.xlsx"
    _criar_xlsx(
        final,
        bd1=[_bd1("1", convenio="GEAP SAUDE", baixa=date(2026, 11, 5),
                  pago=1000.0),
             _bd1("2", venc=date(2065, 1, 10), faturado=1700.0)],
        bd2=[_bd2("GEAP", date(2026, 11, 4), quitacao=1000.0)])
    _criar_xlsx(
        manual,
        bd1=[_bd1("1", convenio="GEAP SAUDE", baixa=date(2026, 11, 5),
                  pago=1000.0)],
        bd2=[_bd2("GEAP", date(2026, 11, 4), quitacao=1000.0)])

    df_wpd = pd.DataFrame([
        _bd1("1", convenio="GEAP SAUDE", baixa=date(2026, 11, 5), pago=1000.0),
        _bd1("2", venc=date(2065, 1, 10), faturado=1700.0),
    ])
    df_ni = pd.DataFrame([_ni()])

    texto = gerar_conferencia(str(final), df_wpd=df_wpd, df_ni=df_ni,
                              xlsx_manual=str(manual), ano=2026)

    assert "CONFERÊNCIA DA POSIÇÃO FINANCEIRA" in texto
    assert "1) VALIDAÇÕES DOS RELATÓRIOS DO DIA" in texto
    assert "fora da janela" in texto
    assert "2) COMPARAÇÃO COM A PF DO MANUAL" in texto
    assert "Só no site" in texto
    assert "3) CONCILIAÇÃO DEPÓSITO × BAIXAS POR CONVÊNIO (2026)" in texto
    assert "fecharam ao centavo" in texto


def test_gerar_conferencia_sem_manual_e_sem_alertas(tmp_path):
    final = tmp_path / "final.xlsx"
    _criar_xlsx(final,
                bd1=[_bd1("1", baixa=date(2026, 11, 5), pago=1000.0)],
                bd2=[_bd2("BRADESCO SEGUROS", date(2026, 11, 4),
                          quitacao=1000.0)])

    texto = gerar_conferencia(str(final), ano=2026)

    assert "Manual não enviado" in texto
    assert "Relatórios do dia não informados" in texto


def test_alias_cobre_os_pares_validados():
    esperados = {
        "BRADESCO SEGURO": "BRADESCO SEGUROS",
        "BRADESCO OPERAD": "BRADESCO OPERADORA PLANO",
        "GEAP SAUDE": "GEAP",
        "PETROBRAS AMS": "PETROLEO BRASILEIRO S/A",
        "CABERJ SAUDE": "CABERJ",
        "GNDI": "NOTRE DAME",
        "SUL AMERICA": "SUL AMERICA SEGUROS SAUDE",
        "UNIMED INTERCAM": "UNIMED INTERCAMBIO",
    }
    for origem, destino in esperados.items():
        assert conferencia.ALIAS_CONVENIOS[origem] == destino
    assert len(conferencia.ALIAS_CONVENIOS) == 27
