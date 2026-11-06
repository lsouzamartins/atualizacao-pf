"""Testes das regras de cálculo do ponto (sem Streamlit)."""
import io
from datetime import date, datetime, time

import pytest
from openpyxl import Workbook

import ponto_core


def _dia(data, entrada=None, saida=None, tipo="trabalho",
         observacao=None, origem="upload"):
    return {"data": data, "entrada": entrada, "saida": saida,
            "tipo": tipo, "observacao": observacao, "origem": origem}


def test_normalizar_texto_remove_acento_e_caixa():
    assert ponto_core.normalizar_texto("FÉRIAS") == "ferias"
    assert ponto_core.normalizar_texto("Feriado") == "feriado"
    assert ponto_core.normalizar_texto("  atestado ") == "atestado"


def test_minutos_de_aceita_time_datetime_texto_e_fracao():
    assert ponto_core.minutos_de(time(8, 30)) == 510
    assert ponto_core.minutos_de(datetime(2026, 11, 6, 18, 15)) == 1095
    assert ponto_core.minutos_de("08:30") == 510
    assert ponto_core.minutos_de(0.5) == 720
    assert ponto_core.minutos_de(None) is None
    assert ponto_core.minutos_de("Férias") is None


def test_formatar_horas():
    assert ponto_core.formatar_horas(0) == "0:00"
    assert ponto_core.formatar_horas(60) == "1:00"
    assert ponto_core.formatar_horas(660) == "11:00"
    assert ponto_core.formatar_horas(1102 * 60 + 37) == "1.102:37"
    assert ponto_core.formatar_horas(-(43 * 60 + 23)) == "-43:23"
    assert ponto_core.formatar_horas(None) == "—"


def test_minutos_para_hhmm():
    assert ponto_core.minutos_para_hhmm(480) == "08:00"
    assert ponto_core.minutos_para_hhmm(0) == "00:00"
    assert ponto_core.minutos_para_hhmm(-60) == "-01:00"
    assert ponto_core.minutos_para_hhmm(None) == "—"


def test_jornada_por_dia_da_semana():
    assert ponto_core.jornada_do_dia(date(2026, 11, 2)) == 600   # segunda
    assert ponto_core.jornada_do_dia(date(2026, 11, 5)) == 600   # quinta
    assert ponto_core.jornada_do_dia(date(2026, 11, 6)) == 540   # sexta
    assert ponto_core.jornada_do_dia(date(2026, 11, 7)) == 0     # sábado
    assert ponto_core.jornada_do_dia(date(2026, 11, 8)) == 0     # domingo
    assert ponto_core.jornada_do_dia(date(2026, 11, 2), "feriado") == 0
    assert ponto_core.jornada_do_dia(date(2026, 11, 2), "ferias") == 0
    assert ponto_core.jornada_do_dia(date(2026, 11, 2), "atestado") == 0


def test_classifica_positivo_trabalhado_negativo():
    hoje = date(2026, 11, 6)
    assert ponto_core.classificar(date(2026, 11, 3), 480, 1140, "trabalho", hoje) == "positivo"
    assert ponto_core.classificar(date(2026, 11, 3), 480, 1080, "trabalho", hoje) == "trabalhado"
    assert ponto_core.classificar(date(2026, 11, 3), 540, 1080, "trabalho", hoje) == "negativo"


def test_classifica_extra_no_fim_de_semana():
    assert ponto_core.classificar(date(2026, 11, 7), 480, 720, "trabalho",
                                  date(2026, 11, 7)) == "extra"


def test_sabado_trabalhado_gera_saldo_integral():
    registros = [_dia(date(2026, 11, 7), "08:00", "12:00")]
    dia = ponto_core.calcular_dias(registros, hoje=date(2026, 11, 7))[0]
    assert dia.situacao == "extra"
    assert dia.jornada == 0
    assert dia.saldo == 240
    assert dia.saldo_acumulado == 240


def test_classifica_pendente():
    hoje = date(2026, 11, 6)
    assert ponto_core.classificar(date(2026, 11, 5), 480, None, "trabalho", hoje) == "pendente"
    assert ponto_core.classificar(date(2026, 11, 5), None, 1080, "trabalho", hoje) == "pendente"
    assert ponto_core.classificar(date(2026, 11, 5), 1080, 480, "trabalho", hoje) == "pendente"


def test_classifica_situacoes_sem_batida():
    assert ponto_core.classificar(date(2026, 11, 5), None, None, "trabalho",
                                  date(2026, 11, 6)) == "falta"
    assert ponto_core.classificar(date(2026, 11, 6), None, None, "trabalho",
                                  date(2026, 11, 6)) == "hoje"
    assert ponto_core.classificar(date(2026, 11, 9), None, None, "trabalho",
                                  date(2026, 11, 6)) == "futuro"
    assert ponto_core.classificar(date(2026, 11, 7), None, None, "trabalho",
                                  date(2026, 11, 9)) == "fim_de_semana"
    assert ponto_core.classificar(date(2026, 11, 7), None, None, "trabalho",
                                  date(2026, 11, 6)) == "futuro"


def test_classifica_especiais_e_outro():
    hoje = date(2026, 11, 6)
    for tipo in ("ferias", "feriado", "atestado"):
        assert ponto_core.classificar(date(2026, 11, 5), None, None, tipo, hoje) == tipo
    assert ponto_core.classificar(date(2026, 11, 5), None, None, "outro", hoje) == "outro"


def test_calcular_dias_atraso_nao_entra_no_saldo():
    registros = [_dia(date(2026, 11, 5), "09:00", "18:00")]
    dia = ponto_core.calcular_dias(registros, hoje=date(2026, 11, 6))[0]
    assert dia.situacao == "negativo"
    assert dia.atraso == 60
    assert dia.saldo == -60          # e não -120
    assert dia.saldo_acumulado == -60


def test_calcular_dias_falta_desconta_jornada():
    registros = [_dia(date(2026, 11, 5))]
    dia = ponto_core.calcular_dias(registros, hoje=date(2026, 11, 6))[0]
    assert dia.situacao == "falta"
    assert dia.saldo == -600
    assert dia.computado is True


def test_calcular_dias_pendente_nao_entra_no_saldo():
    registros = [_dia(date(2026, 11, 5), "08:00", None)]
    dia = ponto_core.calcular_dias(registros, hoje=date(2026, 11, 6))[0]
    assert dia.situacao == "pendente"
    assert dia.saldo == 0
    assert dia.computado is False


def test_calcular_dias_futuro_e_hoje_nao_contam():
    registros = [_dia(date(2026, 11, 6)), _dia(date(2026, 11, 9))]
    dias = ponto_core.calcular_dias(registros, hoje=date(2026, 11, 6),
                                    preencher_lacunas=False)
    assert [d.situacao for d in dias] == ["hoje", "futuro"]
    assert all(d.saldo == 0 for d in dias)


def test_data_futura_com_batida_nao_entra_no_saldo():
    registros = [_dia(date(2026, 11, 9), "08:00", "18:00")]
    dia = ponto_core.calcular_dias(registros, hoje=date(2026, 11, 6))[0]
    assert dia.situacao == "futuro"
    assert dia.saldo == 0
    assert dia.computado is False


def test_calcular_dias_acumulado_na_ordem():
    registros = [
        _dia(date(2026, 10, 26), "08:00", "19:00"),  # +60
        _dia(date(2026, 10, 27), "08:00", "18:00"),  # 0
        _dia(date(2026, 10, 28), "09:00", "18:00"),  # -60
        _dia(date(2026, 10, 29)),                    # falta -600
    ]
    dias = ponto_core.calcular_dias(registros, hoje=date(2026, 11, 6))
    assert [d.saldo_acumulado for d in dias] == [60, 60, 0, -600]


def test_calcular_dias_preenche_lacuna_como_falta():
    registros = [
        _dia(date(2026, 11, 3), "08:00", "18:00"),
        _dia(date(2026, 11, 5), "08:00", "18:00"),
    ]
    dias = ponto_core.calcular_dias(registros, hoje=date(2026, 11, 6))
    assert [d.situacao for d in dias] == ["trabalhado", "falta", "trabalhado"]
    assert dias[1].origem == "calculado"


def test_totais_periodo():
    registros = [
        _dia(date(2026, 10, 26), "08:00", "19:00"),
        _dia(date(2026, 10, 27), "08:00", "18:00"),
        _dia(date(2026, 10, 28), "09:00", "18:00"),
        _dia(date(2026, 10, 29)),
    ]
    dias = ponto_core.calcular_dias(registros, hoje=date(2026, 11, 6))
    totais = ponto_core.totais_periodo(
        dias, date(2026, 10, 26), date(2026, 10, 29), hoje=date(2026, 11, 6))
    assert totais["trabalhados"] == 660 + 600 + 540
    assert totais["atraso"] == 60
    assert totais["faltas"] == 1
    assert totais["pendencias"] == 0
    assert totais["saldo"] == -600


def test_saldo_por_mes_omite_mes_so_de_ferias():
    registros = [
        _dia(date(2026, 5, 4), tipo="ferias"),
        _dia(date(2026, 5, 5), tipo="ferias"),
        _dia(date(2026, 10, 28), "08:00", "18:00"),
        _dia(date(2026, 10, 29), "08:00", "18:00"),
        _dia(date(2026, 11, 3), "08:00", None),
    ]
    dias = ponto_core.calcular_dias(registros, hoje=date(2026, 11, 6),
                                    preencher_lacunas=False)
    assert ponto_core.saldo_por_mes(dias, hoje=date(2026, 11, 6)) == [
        ("2026-10", 0), ("2026-11", 0)]


def test_evolucao_saldo():
    registros = [
        _dia(date(2026, 10, 26), "08:00", "19:00"),
        _dia(date(2026, 10, 27), "08:00", "18:00"),
        _dia(date(2026, 10, 28), "09:00", "18:00"),
    ]
    dias = ponto_core.calcular_dias(registros, hoje=date(2026, 11, 6))
    assert ponto_core.evolucao_saldo(dias, ate=date(2026, 10, 28),
                                     hoje=date(2026, 11, 6)) == [
        (date(2026, 10, 26), 60, 60),
        (date(2026, 10, 27), 0, 60),
        (date(2026, 10, 28), -60, 0),
    ]


def test_rotulos():
    assert ponto_core.rotulo_situacao("positivo") == "Positivo"
    assert ponto_core.rotulo_situacao("fim_de_semana") == "Fim de semana"
    assert ponto_core.rotulo_tipo("ferias") == "Férias"


def _xlsx(linhas, titulo="2026"):
    wb = Workbook()
    ws = wb.active
    ws.title = titulo
    for linha in linhas:
        ws.append(linha)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _xlsx_abas(abas):
    wb = Workbook()
    wb.remove(wb.active)
    for titulo, linhas in abas:
        ws = wb.create_sheet(titulo)
        for linha in linhas:
            ws.append(linha)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_ler_planilha_basica():
    conteudo = _xlsx([
        ["Data", "Dia", "Entrada", "Saída", "Jornada", "Status"],
        [date(2026, 11, 3), "ter", time(8, 0), time(18, 0), time(10, 0), ""],
        [date(2026, 11, 4), "qua", "Férias", "", "", ""],
        [date(2026, 11, 5), "qui", "08:00", "", "", ""],
    ])
    leitura = ponto_core.ler_planilha(conteudo, "ponto.xlsx")
    assert leitura.linhas == 3
    assert leitura.periodo_de == date(2026, 11, 3)
    assert leitura.periodo_ate == date(2026, 11, 5)
    assert leitura.registros[0]["entrada"] == "08:00"
    assert leitura.registros[0]["saida"] == "18:00"
    assert leitura.registros[1]["tipo"] == "ferias"
    assert leitura.registros[1]["entrada"] is None
    assert leitura.registros[2]["saida"] is None
    assert any("incompleta" in aviso for aviso in leitura.avisos)


def test_ler_especiais_e_texto_desconhecido():
    conteudo = _xlsx([
        ["Data", "Entrada", "Saída", "Status"],
        [date(2026, 11, 3), "Férias", "", ""],
        [date(2026, 11, 4), "Feriado", "", ""],
        [date(2026, 11, 5), "atestado", "", ""],
        [date(2026, 11, 6), "Plantão", "", ""],
    ])
    leitura = ponto_core.ler_planilha(conteudo)
    assert [r["tipo"] for r in leitura.registros] == \
        ["ferias", "feriado", "atestado", "outro"]
    assert any("texto não reconhecido" in aviso.lower() for aviso in leitura.avisos)


def test_cabecalho_antigo_dia_funciona():
    conteudo = _xlsx([
        ["DIA", "ENTRADA", "SAIDA", "Status"],
        [date(2026, 11, 3), time(8, 0), time(18, 0), ""],
    ])
    leitura = ponto_core.ler_planilha(conteudo)
    assert leitura.registros[0]["data"] == date(2026, 11, 3)


def test_prefere_coluna_data_quando_existe_dia():
    conteudo = _xlsx([
        ["Data", "Dia", "Entrada", "Saída"],
        [date(2026, 11, 3), "ter", time(8, 0), time(18, 0)],
    ])
    leitura = ponto_core.ler_planilha(conteudo)
    assert leitura.registros[0]["data"] == date(2026, 11, 3)


def test_linha_sem_data_gera_aviso():
    conteudo = _xlsx([
        ["Data", "Entrada", "Saída"],
        ["", time(8, 0), time(18, 0)],
        [date(2026, 11, 3), time(8, 0), time(18, 0)],
    ])
    leitura = ponto_core.ler_planilha(conteudo)
    assert leitura.linhas == 1
    assert any("sem data" in aviso for aviso in leitura.avisos)


def test_aba_vazia_e_ignorada_com_aviso():
    conteudo = _xlsx_abas([
        ("2025", [["DIA", "ENTRADA", "SAIDA", "Status"]]),
        ("2026", [["Data", "Entrada", "Saída", "Status"],
                  [date(2026, 11, 3), time(8, 0), time(18, 0), ""]]),
    ])
    leitura = ponto_core.ler_planilha(conteudo)
    assert len(leitura.registros) == 1
    assert any("Aba '2025' ignorada" in aviso for aviso in leitura.avisos)


def test_nenhuma_aba_valida_gera_erro():
    conteudo = _xlsx_abas([("Planilha1", [["foo", "bar"], [1, 2]])])
    with pytest.raises(ponto_core.PontoError, match="formato esperado"):
        ponto_core.ler_planilha(conteudo)


def test_data_duplicada_recusa_importacao():
    conteudo = _xlsx([
        ["Data", "Entrada", "Saída"],
        [date(2026, 11, 3), time(8, 0), time(18, 0)],
        [date(2026, 11, 3), time(8, 0), time(18, 0)],
    ])
    with pytest.raises(ponto_core.PontoError, match="aparece mais de uma vez"):
        ponto_core.ler_planilha(conteudo)


def test_arquivo_protegido_orienta_salvar_copia():
    conteudo = (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 512
                + "EncryptedPackage".encode("utf-16le"))
    with pytest.raises(ponto_core.PontoError, match="protegido por senha"):
        ponto_core.ler_planilha(conteudo)


def test_formato_invalido_gera_erro():
    with pytest.raises(ponto_core.PontoError, match="Formato não reconhecido"):
        ponto_core.ler_planilha(b"texto qualquer")


def test_jornada_divergente_gera_aviso():
    conteudo = _xlsx([
        ["Data", "Entrada", "Saída", "Jornada"],
        [date(2026, 11, 3), time(8, 0), time(18, 0), time(9, 0)],
    ])
    leitura = ponto_core.ler_planilha(conteudo)
    assert any("jornada" in aviso.lower() for aviso in leitura.avisos)
