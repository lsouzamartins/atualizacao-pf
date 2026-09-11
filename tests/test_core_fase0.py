"""Testes do filtro de linhas-lixo da Fase 0 (core.py).

Regressão de 09/09/2026: o termo "0" da lista de termos-lixo era casado como
substring — qualquer remessa CONTENDO o dígito 0 era descartada do WPD limpo
(ex.: 138055, todas as 150xxx). O filtro deve tratar "0"/"0.0" apenas como
valor EXATO da célula (linha de totalizador), preservando remessas legítimas.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core


def test_filtro_lixo_preserva_remessas_com_digito_zero():
    df = pd.DataFrame({
        "Remessa": ["138055", "150148", "149990", "150233 (R)"],
        "Convênio": ["BRADESCO OPERAD"] * 4,
    })
    filtrado = core._filtrar_linhas_lixo(df)
    assert set(filtrado["Remessa"]) == {"138055", "150148", "149990", "150233 (R)"}


def test_filtro_lixo_remove_total_exato_zero_nas_duas_colunas():
    df = pd.DataFrame({
        "Remessa": ["0", "0.0", "138055", "150148"],
        "Convênio": ["BRADESCO OPERAD", "BRADESCO OPERAD", "0", "BRADESCO OPERAD"],
    })
    filtrado = core._filtrar_linhas_lixo(df)
    # "0"/"0.0" exatos saem (remessa OU convênio); remessas legítimas ficam
    assert list(filtrado["Remessa"]) == ["150148"]


def test_filtro_lixo_continua_removendo_os_termos_de_cabecalho():
    df = pd.DataFrame({
        "Remessa": ["TOTAL", "GERAL", "REMESSA", "PARÂMETROS", "REMESSAS: 10",
                    "138055"],
        "Convênio": ["BRADESCO OPERAD"] * 6,
    })
    filtrado = core._filtrar_linhas_lixo(df)
    assert list(filtrado["Remessa"]) == ["138055"]
