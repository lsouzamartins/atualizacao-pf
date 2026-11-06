"""Testes das regras de cálculo do ponto (sem Streamlit)."""
from datetime import date, datetime, time

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
