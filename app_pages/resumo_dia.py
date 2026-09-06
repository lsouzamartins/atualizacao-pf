"""
==============================================================================
PÁGINA: RESUMO DO DIA — ATUALIZAÇÃO PF · HIAS
Valores diários por convênio: Vlr Bruto, Vlr Líquido, Quitado e Não Identificado.

Fonte: banco SQLite (resumos gravados ao fim do processamento), com seleção por data.

Revisão: Claude Code (Anthropic) · 19/08/2026 · 01/09/2026 · leitura pelo banco
==============================================================================
"""
import pandas as pd
import streamlit as st

import banco

from ui_comum import icone, formatar_brl, formatar_data_br, VERSAO

# ---------------------------------------------------------------------------
# MAPEAMENTO DAS COLUNAS DO BANCO → RÓTULOS DA TELA
# ---------------------------------------------------------------------------
COLUNAS = {
    "vlr_bruto": "Vlr Bruto",
    "vlr_liquido": "Vlr Líquido",
    "quitado": "Quitado",
    "nao_identificado": "Não Identificado",
}


# ==============================================================================
# LEITURA DO BANCO
# ==============================================================================
conn = banco.conectar()
banco.inicializar_banco(conn)
datas = banco.resumos_disponiveis(conn)
if not datas:
    st.info("Nenhum processamento registrado ainda.")
    conn.close()
    st.stop()
data_exibida = st.selectbox("Data", datas, index=0, format_func=formatar_data_br)
df_por_convenio = banco.resumos_do_dia(conn, data_exibida)
conn.close()

df_por_convenio = df_por_convenio.rename(
    columns={"convenio": "Convênio", **COLUNAS}
)
df_por_convenio = df_por_convenio.sort_values("Vlr Bruto", ascending=False).reset_index(drop=True)


# ==============================================================================
# INTERFACE STREAMLIT
# ==============================================================================
st.markdown(f"### {icone('calendar', 20, '#1C5A8A')} Resumo do dia", unsafe_allow_html=True)

# ---- TOTAIS DO DIA ----
totais = {rotulo: float(df_por_convenio[rotulo].sum()) for rotulo in COLUNAS.values()}

with st.container(horizontal=True):
    st.metric("Vlr Bruto", f"R$ {formatar_brl(totais['Vlr Bruto'])}", border=True)
    st.metric("Vlr Líquido", f"R$ {formatar_brl(totais['Vlr Líquido'])}", border=True)
    st.metric("Quitado", f"R$ {formatar_brl(totais['Quitado'])}", border=True)
    st.metric("Não Identificado", f"R$ {formatar_brl(totais['Não Identificado'])}", border=True)

# ---- TABELA POR CONVÊNIO ----
st.divider()
st.markdown(f"#### {icone('building-2', 18, '#1C5A8A')} Valores por convênio", unsafe_allow_html=True)

df_exibicao = df_por_convenio.copy()
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
