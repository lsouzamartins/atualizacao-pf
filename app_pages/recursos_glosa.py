"""PÁGINA: RECURSOS DE GLOSA — status por guia (linha e lote), avisos e prazos."""
import pandas as pd
import streamlit as st

import banco_glosas
from ui_comum import icone, formatar_brl, formatar_data_br, VERSAO

st.markdown(f"### {icone('scroll-text', 20, '#1C5A8A')} Recursos de Glosa",
            unsafe_allow_html=True)

conn = banco_glosas.conectar()
banco_glosas.inicializar_banco(conn)
usuario_login = st.session_state["usuario"]["login"]

convenios = banco_glosas.listar_convenios(conn)
opcoes = {"Todos": None} | {c["nome"]: c["id"] for c in convenios}
f1, f2, f3, f4 = st.columns([2, 2, 2, 1])
convenio_sel = f1.selectbox("Convênio", list(opcoes), key="r_convenio")
status_sel = f2.selectbox("Status", ["Todos"] + banco_glosas.STATUS, key="r_status")
busca = f3.text_input("Buscar guia ou beneficiário", key="r_busca")
somente_avisos = f4.checkbox("Avisos", key="r_avisos")

guias = banco_glosas.guias_filtradas(
    conn, convenio_id=opcoes[convenio_sel],
    status=None if status_sel == "Todos" else status_sel,
    busca=busca.strip() or None, somente_avisos=somente_avisos)

if guias:
    df = pd.DataFrame([
        {"selecionar": False, "guia_id": g["guia_id"], "Guia": g["guia_prestador"],
         "Beneficiário": g["beneficiario"], "Convênio": g["convenio"],
         "Glosa": g["vl_glosa"], "Motivo": g["motivo"] or "—",
         "status": g["status_recurso"], "vl_recuperado": g["vl_recuperado"],
         "observacao": g["observacao"], "Aviso": bool(g["aviso_glosa_zerada"])}
        for g in guias])
    if "snapshot_recursos" not in st.session_state:
        st.session_state["snapshot_recursos"] = df.copy()
    editado = st.data_editor(
        df, hide_index=True, key="ed_recursos", num_rows="fixed",
        column_config={
            "guia_id": None,
            "selecionar": st.column_config.CheckboxColumn("Selecionar", default=False),
            "Glosa": st.column_config.NumberColumn("Glosa", format="R$ %.2f", disabled=True),
            "Aviso": st.column_config.CheckboxColumn("Glosa zerada", disabled=True),
            "status": st.column_config.SelectboxColumn(
                "Status", options=banco_glosas.STATUS, required=True),
            "vl_recuperado": st.column_config.NumberColumn("Vl. Recuperado", format="R$ %.2f"),
            "observacao": st.column_config.TextColumn("Observação"),
        })
    if st.button("Salvar alterações", type="primary"):
        alteradas = banco_glosas.diff_guias_editadas(
            st.session_state["snapshot_recursos"], editado)
        for a in alteradas:
            banco_glosas.registrar_status(
                conn, a["guia_id"], a["status"],
                vl_recuperado=a["vl_recuperado"], observacao=a["observacao"],
                usuario=usuario_login)
        st.success(f"{len(alteradas)} guia(s) atualizada(s).")
        st.session_state.pop("snapshot_recursos", None)
        st.rerun()

    selecionadas = editado[editado["selecionar"]]["guia_id"].tolist()
    with st.form("lote_recursos"):
        st.markdown(f"**Edição em lote** — {len(selecionadas)} guia(s) selecionada(s)")
        status_lote = st.selectbox("Novo status", banco_glosas.STATUS, key="lote_status")
        vl_lote = st.number_input("Valor recuperado (0 = mantém o atual)",
                                  min_value=0.0, format="%.2f", key="lote_vl")
        if st.form_submit_button("Aplicar em lote", type="primary",
                                 disabled=not selecionadas):
            for gid in selecionadas:
                banco_glosas.registrar_status(
                    conn, int(gid), status_lote,
                    vl_recuperado=vl_lote if vl_lote > 0 else None,
                    usuario=usuario_login)
            st.success(f"Status '{status_lote}' aplicado a {len(selecionadas)} guia(s).")
            st.session_state.pop("snapshot_recursos", None)
            st.rerun()
else:
    st.info("Nenhuma guia com os filtros escolhidos.")

# ---- AVISOS DE GLOSA ZERADA (confirmação de 1 clique) ----
avisos = banco_glosas.avisos_glosa_zerada(conn)
if avisos:
    st.divider()
    st.markdown(f"#### {icone('bell-ring', 18, '#1C5A8A')} Glosa zerada no reenvio "
                f"({len(avisos)})", unsafe_allow_html=True)
    st.caption("Essas guias tinham glosa e chegaram sem glosa no último upload. "
               "Confirme se o recurso foi ganho.")
    for a in avisos:
        c1, c2 = st.columns([4, 1])
        c1.write(f"- Guia {a['guia_prestador']} · {a['beneficiario']} "
                 f"({a['convenio']}) — {a['motivo'] or 'sem motivo registrado'}")
        if c2.button("Confirmar", key=f"conf_{a['id']}"):
            banco_glosas.confirmar_glosa_recebida(conn, a["id"], usuario=usuario_login)
            st.rerun()
    if st.button("Confirmar todas como Glosa Recebida"):
        for a in avisos:
            banco_glosas.confirmar_glosa_recebida(conn, a["id"], usuario=usuario_login)
        st.rerun()

# ---- HISTÓRICO DE UMA GUIA ----
st.divider()
st.markdown(f"#### {icone('history', 18, '#1C5A8A')} Histórico de uma guia",
            unsafe_allow_html=True)
todas = banco_glosas.guias_filtradas(conn)
if todas:
    alvo_hist = st.selectbox(
        "Guia", todas,
        format_func=lambda g: f"{g['guia_prestador']} · {g['beneficiario']} "
                              f"({g['convenio']})", key="hist_guia")
    hist = banco_glosas.historico_status(conn, alvo_hist["guia_id"])
    if hist:
        st.dataframe(pd.DataFrame([
            {"Data": formatar_data_br(h["atualizado_em"][:10]), "De": h["status_de"],
             "Para": h["status_para"], "Recuperado": f"R$ {formatar_brl(h['vl_recuperado'])}",
             "Obs": h["observacao"], "Usuário": h["usuario"]}
            for h in hist]), hide_index=True)
    else:
        st.info("Sem mudanças registradas.")

# ---- PRAZOS POR CONVÊNIO (ADMIN) ----
if st.session_state["usuario"]["admin"]:
    with st.expander(f"{icone('alarm-clock', 18)} Prazos por convênio (alertas)",
                     unsafe_allow_html=True):
        for c in convenios:
            c1, c2 = st.columns([3, 1])
            atual = c["prazo_recurso_dias"]
            c1.write(f"**{c['nome']}** — prazo atual: "
                     f"{atual if atual else 'não cadastrado'}")
            dias = c2.number_input("Dias", min_value=0, step=5, value=int(atual or 0),
                                   key=f"prazo_{c['id']}")
            if c2.button("Salvar", key=f"salvar_prazo_{c['id']}"):
                banco_glosas.definir_prazo_convenio(conn, c["id"], dias if dias > 0 else None)
                st.rerun()

conn.close()
st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)
