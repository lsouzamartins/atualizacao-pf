"""PÁGINA: UPLOAD DACM — envio do DACM (Excel ANS) com prévia e importação."""
import os
import tempfile

import pandas as pd
import streamlit as st

import banco_glosas
import parser_dacm
from ui_comum import icone, formatar_brl, formatar_data_br, VERSAO

st.markdown(f"### {icone('upload', 20, '#1C5A8A')} Upload DACM", unsafe_allow_html=True)
st.caption("Envie o DACM do convênio (Excel .xls ou .xlsx, formato ANS). "
           "Reenviar o mesmo arquivo atualiza as guias — nada é duplicado.")

conn = banco_glosas.conectar()
banco_glosas.inicializar_banco(conn)

arquivo = st.file_uploader("Arquivo do DACM", type=["xls", "xlsx"], key="up_dacm")

if arquivo is not None and ("dacm_parsed" not in st.session_state
                            or st.session_state.get("arquivo_id_upado") != arquivo.file_id):
    sufixo = os.path.splitext(arquivo.name)[1].lower()
    tmp = tempfile.NamedTemporaryFile(suffix=sufixo, delete=False)
    tmp.write(arquivo.getvalue())
    tmp.close()
    st.session_state["caminho_temp"] = tmp.name
    st.session_state["nome_arquivo_upado"] = arquivo.name
    st.session_state["arquivo_id_upado"] = arquivo.file_id
    st.session_state.pop("dacm_parsed", None)
    st.session_state.pop("erro_parse", None)
    try:
        st.session_state["dacm_parsed"] = parser_dacm.parse_dacm_ans(tmp.name)
    except ValueError as e:
        st.session_state["erro_parse"] = str(e)

if st.session_state.get("erro_parse"):
    st.error(st.session_state["erro_parse"])

parsed = st.session_state.get("dacm_parsed")
if parsed:
    meta = parsed["metadados"]
    guias = parsed["guias"]
    st.markdown("#### Prévia do arquivo")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Convênio detectado", meta["operadora"] or "—")
    c2.metric("Nº do DACM", meta["num_dacm"] or "—")
    c3.metric("Data de emissão", formatar_data_br(meta["data_emissao"]))
    c4.metric("Guias", len(guias))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Guias com glosa", sum(1 for g in guias if g["vl_glosa"] > 0))
    c2.metric("Total processado", f"R$ {formatar_brl(meta['tot_geral_processado'])}")
    c3.metric("Total liberado", f"R$ {formatar_brl(meta['tot_geral_liberado'])}")
    c4.metric("Total glosado", f"R$ {formatar_brl(meta['tot_geral_glosa'])}")

    soma_processado = sum(g["vl_processado"] for g in guias)
    if abs(soma_processado - meta["tot_geral_processado"]) > 0.01:
        st.warning("Conferência: a soma das guias difere do total geral do arquivo. "
                   "Confira o arquivo antes de importar.")
    if parsed["avisos"]:
        with st.expander("Avisos do parser"):
            for aviso in parsed["avisos"]:
                st.write(f"- {aviso}")

    nomes_convenios = [c["nome"] for c in banco_glosas.listar_convenios(conn)]
    padrao = nomes_convenios[0] if nomes_convenios else meta["operadora"]
    nome_convenio = st.text_input("Nome do convênio (como aparecerá no dashboard)",
                                  value=padrao, key="nome_convenio")
    if st.button("Importar DACM", type="primary"):
        try:
            resultado = banco_glosas.importar_dacm(
                conn, parsed, nome_convenio.strip(),
                st.session_state["usuario"]["login"],
                st.session_state["caminho_temp"])
            st.success(f"Importação concluída: {resultado['novas']} guia(s) nova(s), "
                       f"{resultado['atualizadas']} atualizada(s), "
                       f"{resultado['avisos_glosa_zerada']} aviso(s) de glosa zerada.")
            for chave in ("dacm_parsed", "caminho_temp", "nome_arquivo_upado", "arquivo_id_upado", "erro_parse"):
                st.session_state.pop(chave, None)
            st.rerun()
        except Exception as e:
            st.error(f"Não foi possível importar: {e}")

st.divider()
st.markdown(f"#### {icone('history', 18, '#1C5A8A')} Últimos uploads", unsafe_allow_html=True)
uploads = banco_glosas.listar_uploads(conn, limite=10)
if uploads:
    df = pd.DataFrame([
        {"Data": formatar_data_br(u["criado_em"][:10]), "Usuário": u["usuario"],
         "Convênio": u["convenio"], "Arquivo": u["nome_arquivo"],
         "Nº DACM": u["num_dacm"], "Novas": u["guias_novas"],
         "Atualizadas": u["guias_atualizadas"]}
        for u in uploads])
    st.dataframe(df, hide_index=True)
else:
    st.info("Nenhum upload ainda.")

conn.close()
st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)
