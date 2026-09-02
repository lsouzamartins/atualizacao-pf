"""PÁGINA: HISTÓRICO — consulta dos resumos diários salvos no banco."""
from datetime import datetime
import streamlit as st
import banco
from ui_comum import icone, formatar_brl, VERSAO

st.markdown(f"### {icone('calendar', 20, '#1C5A8A')} Histórico")

conn = banco.conectar()
banco.inicializar_banco(conn)
datas = banco.resumos_disponiveis(conn)
if not datas:
    conn.close()
    st.info("Nenhum processamento registrado ainda."); st.stop()

c1, c2 = st.columns(2)
de = c1.selectbox("De", datas, index=len(datas) - 1)
ate = c2.selectbox("Até", datas, index=0)
df = banco.historico(conn, de=de, ate=ate)
conn.close()

if df.empty:
    st.info("Sem registros no período.")
else:
    df_exib = df.rename(columns={
        "data": "Data", "convenio": "Convênio", "usuario": "Usuário",
        "status": "Status", "vlr_bruto": "Vlr Bruto", "vlr_liquido": "Vlr Líquido",
        "quitado": "Quitado", "nao_identificado": "Não Identificado"})
    for col in ("Vlr Bruto", "Vlr Líquido", "Quitado", "Não Identificado"):
        df_exib[col] = df_exib[col].apply(formatar_brl)
    st.dataframe(df_exib, hide_index=True)
st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)
