"""PÁGINA: HISTÓRICO — consulta dos resumos diários salvos no banco."""
import os
import streamlit as st
import banco
from ui_comum import icone, formatar_brl, pastas, VERSAO

st.markdown(f"### {icone('calendar', 20, '#1C5A8A')} Histórico")

conn = banco.conectar()
banco.inicializar_banco(conn)
datas = banco.resumos_disponiveis(conn)
if not datas:
    conn.close()
    st.info("Nenhum processamento registrado ainda."); st.stop()

convenios = banco.convenios_disponiveis(conn)

c1, c2 = st.columns(2)
de = c1.selectbox("De", datas, index=len(datas) - 1)
ate = c2.selectbox("Até", datas, index=0)
filtro = st.selectbox("Convênio", ["Todos"] + convenios)
df = banco.historico(conn, de=de, ate=ate,
                     convenio=None if filtro == "Todos" else filtro)
# Arquivos retidos por execução exibida (JSON gravado no banco)
arquivos_por_execucao = {
    eid: banco.arquivos_da_execucao(conn, eid)
    for eid in df["execucao_id"].unique()
}
conn.close()

PASTA_SAIDA = pastas()["saida"]

if df.empty:
    st.info("Sem registros no período.")
else:
    # Totais por dia: agregação dos dados já carregados (fiel à tabela exibida)
    totais = (df.groupby("data", as_index=False)
                .agg(vlr_bruto=("vlr_bruto", "sum"),
                     vlr_liquido=("vlr_liquido", "sum"),
                     quitado=("quitado", "sum"),
                     nao_identificado=("nao_identificado", "sum"))
                .rename(columns={
                    "data": "Data", "vlr_bruto": "Vlr Bruto",
                    "vlr_liquido": "Vlr Líquido", "quitado": "Quitado",
                    "nao_identificado": "Não Identificado"})
                .sort_values("Data", ascending=False))
    for col in ("Vlr Bruto", "Vlr Líquido", "Quitado", "Não Identificado"):
        totais[col] = totais[col].apply(formatar_brl)
    st.markdown("#### Totais por dia")
    st.dataframe(totais, hide_index=True)

    df_exib = df.drop(columns=["execucao_id"]).rename(columns={
        "data": "Data", "convenio": "Convênio", "usuario": "Usuário",
        "status": "Status", "vlr_bruto": "Vlr Bruto", "vlr_liquido": "Vlr Líquido",
        "quitado": "Quitado", "nao_identificado": "Não Identificado"})
    for col in ("Vlr Bruto", "Vlr Líquido", "Quitado", "Não Identificado"):
        df_exib[col] = df_exib[col].apply(formatar_brl)
    st.dataframe(df_exib, hide_index=True)

    # Download dos XLSX retidos em saída/: o nome vem do banco e passa sempre
    # por os.path.basename antes de compor o caminho (sem entrada do usuário)
    baixaveis = [
        (eid, nome)
        for eid, nomes in arquivos_por_execucao.items()
        for nome in nomes
        if os.path.exists(os.path.join(PASTA_SAIDA, os.path.basename(nome)))
    ]
    if baixaveis:
        st.markdown("#### Download dos arquivos retidos")
        for eid, nome in baixaveis:
            caminho = os.path.join(PASTA_SAIDA, os.path.basename(nome))
            with open(caminho, "rb") as f:
                dados = f.read()
            st.download_button(
                f"Baixar {nome}",
                data=dados,
                file_name=os.path.basename(nome),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_{eid}_{nome}")

st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)
