"""PÁGINA: DASHBOARD DE GLOSAS — KPIs, 4 blocos e alertas de decisão."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import banco_glosas
from ui_comum import icone, formatar_brl, formatar_data_br, VERSAO

st.markdown(f"### {icone('chart-column', 20, '#1C5A8A')} Dashboard de Glosas",
            unsafe_allow_html=True)

conn = banco_glosas.conectar()
banco_glosas.inicializar_banco(conn)

convenios = banco_glosas.listar_convenios(conn)
opcoes = {"Todos": None} | {c["nome"]: c["id"] for c in convenios}
f1, f2, f3 = st.columns(3)
convenio_sel = f1.selectbox("Convênio", list(opcoes), key="f_convenio")
datas_inicio = [r["data_inicio"] for r in conn.execute(
    "SELECT DISTINCT data_inicio FROM guias WHERE data_inicio != '' "
    "ORDER BY data_inicio").fetchall()]
if datas_inicio:
    de = f2.selectbox("De", datas_inicio, index=0, format_func=formatar_data_br, key="f_de")
    ate = f3.selectbox("Até", list(reversed(datas_inicio)), index=0,
                       format_func=formatar_data_br, key="f_ate")
else:
    de = ate = None
convenio_id = opcoes[convenio_sel]

# ---- KPI CARDS ----
kpis = banco_glosas.resumo_kpis(conn, convenio_id=convenio_id, de=de, ate=ate)
c = st.container(horizontal=True)
c.metric("Total Processado", f"R$ {formatar_brl(kpis['processado'])}")
c.metric("Total Liberado", f"R$ {formatar_brl(kpis['liberado'])}")
c.metric("Total Glosado", f"R$ {formatar_brl(kpis['glosado'])}")
c.metric("Taxa de Glosa", f"{kpis['taxa_glosa']:.2f}%")
c2 = st.container(horizontal=True)
c2.metric("Em Recurso", f"R$ {formatar_brl(kpis['em_recurso'])}")
c2.metric("Taxa de Recuperação", f"{kpis['taxa_recuperacao']:.2f}%")
c2.metric("Perda Real", f"R$ {formatar_brl(kpis['perda_real'])}")

# ---- ALERTAS ----
alertas = banco_glosas.alertas_aging(conn)
avisos = banco_glosas.avisos_glosa_zerada(conn)
if alertas:
    st.markdown(f"#### {icone('alarm-clock', 18, '#C0392B')} Recursos estourados "
                f"({len(alertas)})", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame([
        {"Convênio": a["convenio"], "Guia": a["guia"], "Beneficiário": a["beneficiario"],
         "Protocolo": a["protocolo"], "Dias": a["dias"], "Prazo (dias)": a["prazo"],
         "Glosa": f"R$ {formatar_brl(a['vl_glosa'])}"} for a in alertas]), hide_index=True)
if avisos:
    st.markdown(f"#### {icone('bell-ring', 18, '#1C5A8A')} Glosa zerada no reenvio "
                f"({len(avisos)}) — confirme na página Recursos de Glosa",
                unsafe_allow_html=True)
    st.page_link("app_pages/recursos_glosa.py", label="Abrir Recursos de Glosa")

st.divider()

# ---- BLOCO 1: GLOSA POR CONVÊNIO ----
st.markdown(f"#### {icone('building-2', 18, '#1C5A8A')} Glosa por convênio",
            unsafe_allow_html=True)
df_conv = banco_glosas.agrupado_por_convenio(conn, de=de, ate=ate)
if not df_conv.empty:
    fig1 = go.Figure()
    fig1.add_bar(x=df_conv["convenio"], y=df_conv["processado"], name="Processado",
                 marker_color="#1C5A8A")
    fig1.add_bar(x=df_conv["convenio"], y=df_conv["liberado"], name="Liberado",
                 marker_color="#22c55e")
    fig1.add_bar(x=df_conv["convenio"], y=df_conv["glosado"], name="Glosado",
                 marker_color="#ef4444")
    fig1.update_layout(barmode="group", height=320, margin=dict(t=10, b=10))
    st.plotly_chart(fig1, use_container_width=True)
else:
    st.info("Sem dados para o período.")

# ---- BLOCO 2: EVOLUÇÃO MENSAL ----
st.markdown(f"#### {icone('trending-up', 18, '#1C5A8A')} Evolução mensal — "
            f"glosado × recuperado", unsafe_allow_html=True)
df_mes = banco_glosas.evolucao_mensal(conn, convenio_id=convenio_id, de=de, ate=ate)
if not df_mes.empty:
    fig2 = go.Figure()
    fig2.add_scatter(x=df_mes["mes"], y=df_mes["glosado"], name="Glosado",
                     line=dict(color="#ef4444", width=2.5))
    fig2.add_scatter(x=df_mes["mes"], y=df_mes["recuperado"], name="Recuperado",
                     line=dict(color="#22c55e", width=2.5))
    fig2.update_layout(height=300, margin=dict(t=10, b=10))
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("Sem dados para o período.")

# ---- BLOCO 3: PAINEL DE RECURSOS (RESUMO) ----
st.markdown(f"#### {icone('scroll-text', 18, '#1C5A8A')} Painel de recursos por guia",
            unsafe_allow_html=True)
guias = banco_glosas.guias_filtradas(conn, convenio_id=convenio_id, de=de, ate=ate)
if guias:
    df_guias = pd.DataFrame([
        {"Guia": g["guia_prestador"], "Beneficiário": g["beneficiario"],
         "Protocolo": g["protocolo"], "Data": formatar_data_br(g["data_protocolo"]),
         "Glosa": f"R$ {formatar_brl(g['vl_glosa'])}", "Motivo": g["motivo"] or "—",
         "Status": g["status_recurso"], "Recuperado": f"R$ {formatar_brl(g['vl_recuperado'])}"}
        for g in guias])
    st.dataframe(df_guias, hide_index=True, height=360)
    st.page_link("app_pages/recursos_glosa.py",
                 label="Gerenciar recursos (status, valores e avisos)")
else:
    st.info("Nenhuma guia no período.")

# ---- BLOCO 4: MOTIVOS DE GLOSA ----
st.markdown(f"#### {icone('list', 18, '#1C5A8A')} Motivos de glosa",
            unsafe_allow_html=True)
df_motivos = banco_glosas.ranking_motivos(conn, convenio_id=convenio_id, de=de, ate=ate)
if not df_motivos.empty:
    df_top = df_motivos.head(10).iloc[::-1]
    rotulos = [f"{d} [{c}]" if c else d
               for d, c in zip(df_top["descricao"], df_top["cod_glosa"])]
    fig4 = go.Figure(go.Bar(x=df_top["total"], y=rotulos, orientation="h",
                            marker_color="#ef4444"))
    fig4.update_layout(height=max(260, 40 * len(df_top)), margin=dict(t=10, b=10))
    st.plotly_chart(fig4, use_container_width=True)
else:
    st.info("Sem glosas no período.")

conn.close()
st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)
