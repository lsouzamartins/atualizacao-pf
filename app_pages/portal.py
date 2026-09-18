"""PÁGINA: INÍCIO — portal com os sistemas disponíveis ao usuário."""
import streamlit as st

from ui_comum import icone, VERSAO

st.markdown(f"### {icone('home', 20, '#1C5A8A')} SISTEMAS INTEGRADOS", unsafe_allow_html=True)
st.caption("Você tem acesso a mais de um sistema. Selecione onde quer trabalhar.")

c1, c2 = st.columns(2)
with c1:
    with st.container(border=True):
        st.markdown(f"{icone('play-circle', 22, '#1C5A8A')} **Atualização da Posição Financeira**",
                    unsafe_allow_html=True)
        st.caption("Integração automática WPD-26 + Não Identificado.")
        st.page_link("app_pages/processamento.py", label="Abrir Atualização PF")
with c2:
    with st.container(border=True):
        st.markdown(f"{icone('file-spreadsheet', 22, '#1C5A8A')} **DACM × FATURAMENTO**",
                    unsafe_allow_html=True)
        st.caption("Conferência de guias entre os DACMs e o faturamento.")
        st.link_button(label="Abrir DACM × FATURAMENTO",
                       url="https://pf.lsm.ia.br/dacm/", type="tertiary")

st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)
