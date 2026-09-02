"""
==============================================================================
PÁGINA: RESUMO DO DIA — ATUALIZAÇÃO PF · HIAS
Valores diários por convênio: Vlr Bruto, Vlr Líquido, Quitado e Não Identificado.

Fonte: relatórios/Não_Identificado.xls (somente leitura — core.py não é alterado).
Data exibida: hoje; sem lançamentos de hoje, usa a data mais recente disponível.

Revisão: Claude Code (Anthropic) · 19/08/2026
==============================================================================
"""
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from ui_comum import icone, pastas, formatar_brl, VERSAO
from core import encontrar_arquivo_entrada, limpar_numero

# ---------------------------------------------------------------------------
# MAPEAMENTO DAS COLUNAS DO ARQUIVO → RÓTULOS DA TELA
# ---------------------------------------------------------------------------
COLUNAS = {
    "Depósito Bruto": "Vlr Bruto",
    "Depósito Liq.": "Vlr Líquido",
    "Quitação": "Quitado",
    "Não Identificado": "Não Identificado",
}


@st.cache_data(ttl="1m")
def carregar_dados_diarios(caminho: str) -> pd.DataFrame:
    """Lê e limpa o Não_Identificado.xls (mesma regra da Fase 1 do core.py)."""
    df = pd.read_excel(caminho, engine="xlrd", skiprows=4)
    df.columns = df.columns.str.strip()

    df = df[["Convênio", "Data", *COLUNAS.keys()]].copy()
    df["Convênio"] = df["Convênio"].astype(str).str.strip()

    df_limpo = df[
        (~df["Convênio"].str.contains("TOTAL DO CONVÊNIO", na=False)) &
        (~df["Convênio"].str.contains("TOTAL GERAL", na=False)) &
        (~df["Convênio"].str.contains("SALDO ANT.", na=False)) &
        (~df["Convênio"].str.contains("SALDO POS.", na=False)) &
        (~df["Data"].astype(str).str.contains("SALDO ANT.", na=False)) &
        (df["Convênio"] != "") & (df["Convênio"] != "nan") &
        (df["Data"].notna()) & (df["Data"].astype(str).str.strip() != "")
    ].copy()

    df_limpo["Data"] = pd.to_datetime(df_limpo["Data"], errors="coerce", dayfirst=True).dt.date
    df_limpo = df_limpo.dropna(subset=["Data"])

    for coluna in COLUNAS:
        df_limpo[coluna] = df_limpo[coluna].apply(limpar_numero)

    # Descarta linhas em que todas as colunas financeiras são zero (regra da Fase 1)
    df_limpo = df_limpo[df_limpo[list(COLUNAS)].sum(axis=1) != 0.0].copy()
    return df_limpo.reset_index(drop=True)


# ==============================================================================
# INTERFACE STREAMLIT
# ==============================================================================
try:
    caminho_ni = encontrar_arquivo_entrada(pastas()["raiz"], "Não_Identificado.xls")
except FileNotFoundError as erro:
    st.error(str(erro))
    st.stop()

df_diario = carregar_dados_diarios(caminho_ni)

if df_diario.empty:
    st.info("O arquivo Não_Identificado.xls não possui lançamentos diários no momento.")
    st.stop()

# ---- DATA EXIBIDA: hoje, com fallback para a mais recente disponível ----
hoje = datetime.now().date()
datas_disponiveis = sorted(df_diario["Data"].unique())
data_exibida = hoje if hoje in datas_disponiveis else datas_disponiveis[-1]

st.markdown(f"### {icone('calendar', 20, '#1C5A8A')} Resumo do dia", unsafe_allow_html=True)

if data_exibida != hoje:
    st.warning(
        f"Sem lançamentos de hoje ({hoje.strftime('%d/%m/%Y')}) no arquivo. "
        f"Exibindo a data mais recente disponível: **{data_exibida.strftime('%d/%m/%Y')}**."
    )

arquivo_atualizado = datetime.fromtimestamp(os.path.getmtime(caminho_ni))
st.caption(
    f"Data dos valores: **{data_exibida.strftime('%d/%m/%Y')}** · "
    f"Arquivo atualizado em **{arquivo_atualizado.strftime('%d/%m/%Y %H:%M')}** "
    f"(`relatórios/Não_Identificado.xls`)"
)

# ---- TOTAIS DO DIA ----
df_dia = df_diario[df_diario["Data"] == data_exibida]
df_por_convenio = (
    df_dia.groupby("Convênio", as_index=False)[list(COLUNAS)]
    .sum()
    .sort_values("Depósito Bruto", ascending=False)
    .reset_index(drop=True)
)

totais = {rotulo: float(df_por_convenio[coluna].sum()) for coluna, rotulo in COLUNAS.items()}

with st.container(horizontal=True):
    st.metric("Vlr Bruto", f"R$ {formatar_brl(totais['Vlr Bruto'])}", border=True)
    st.metric("Vlr Líquido", f"R$ {formatar_brl(totais['Vlr Líquido'])}", border=True)
    st.metric("Quitado", f"R$ {formatar_brl(totais['Quitado'])}", border=True)
    st.metric("Não Identificado", f"R$ {formatar_brl(totais['Não Identificado'])}", border=True)

# ---- TABELA POR CONVÊNIO ----
st.divider()
st.markdown(f"#### {icone('building-2', 18, '#1C5A8A')} Valores por convênio", unsafe_allow_html=True)

df_exibicao = df_por_convenio.rename(columns=COLUNAS).copy()
linha_total = pd.DataFrame(
    [["TOTAL", *[formatar_brl(totais[rotulo]) for rotulo in COLUNAS.values()]]],
    columns=df_exibicao.columns,
)
df_exibicao = pd.concat([df_exibicao, linha_total], ignore_index=True)

for rotulo in COLUNAS.values():
    df_exibicao[rotulo] = df_exibicao[rotulo].apply(
        lambda v: v if isinstance(v, str) else formatar_brl(v)
    )


def _destacar_linha_total(linha):
    """Realça a linha TOTAL com fonte 700 e fundo de superfície."""
    return ["font-weight: 700; background-color: #F8FAFC;"] * len(linha)


indice_total = df_exibicao[df_exibicao["Convênio"] == "TOTAL"].index
tabela = df_exibicao.style.apply(_destacar_linha_total, subset=pd.IndexSlice[indice_total, :])
st.dataframe(tabela, hide_index=True)
num_convenios = len(df_por_convenio)
st.caption(f"{num_convenios} convênio{'s' if num_convenios != 1 else ''} com lançamentos no dia.")

st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)
