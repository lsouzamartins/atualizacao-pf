"""Função pura que transforma o df_ni da Fase 1 nos resumos diários do banco."""
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app_pages import processamento

def test_agregar_para_banco():
    df_ni = pd.DataFrame({
        "Convênio": ["BRADESCO", "BRADESCO", "GEAP"],
        "Data": pd.to_datetime(["2026-09-01", "2026-09-01", "2026-09-01"], dayfirst=True),
        "Depósito Bruto": [100.0, 50.0, 200.0],
        "Depósito Liq.": [90.0, 45.0, 180.0],
        "Quitação": [0.0, 0.0, 0.0],
        "Não Identificado": [10.0, 5.0, 20.0],
    })
    df = processamento.agregar_para_banco(df_ni)
    assert list(df.columns) == ["data", "convenio", "vlr_bruto",
                                "vlr_liquido", "quitado", "nao_identificado"]
    assert df.loc[df["convenio"] == "BRADESCO", "vlr_bruto"].iloc[0] == 150.0
    assert len(df) == 2
