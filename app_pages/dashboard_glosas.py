"""PÁGINA: DASHBOARD DE RECURSO DE GLOSAS — visual do modelo v1.0 (index.html):
filtros (convênio/motivo/status/período), 5 KPI cards, 4 gráficos (Pareto,
empilhado por convênio, evolução, rosca), alertas de prazo e exportação CSV.

Rulings de design (aprovados com o Leonardo em 06/09):
- O Pareto e o empilhado/rosca por status IGNORAM os filtros de status/motivo
  (filtrar um ranking de motivos ou uma distribuição por status deixaria o
  gráfico com uma única barra/fatia); aplicam convênio e período.
- KPIs, evolução e tabela de guias aplicam todos os filtros.
- Alertas de prazo são globais (não somem com filtros do dashboard).
"""
import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import banco_glosas
from ui_comum import (CORES_STATUS, icone, formatar_brl, formatar_data_br, VERSAO)

# ---- CABEÇALHO ----
c_tit, c_btn = st.columns([4, 1], vertical_alignment="center")
c_tit.markdown(f"### {icone('hand-coins', 20, '#1C5A8A')} Dashboard de Recurso "
               f"de Glosas", unsafe_allow_html=True)
c_tit.caption("Monitoramento de glosas e recuperação financeira")
with c_btn:
    st.page_link("app_pages/upload_dacm.py", label="Upload DACM",
                 icon=":material/upload:")

conn = banco_glosas.conectar()
banco_glosas.inicializar_banco(conn)

# ---- FILTROS ----
convenios = banco_glosas.listar_convenios(conn)
opcoes = {"Todos": None} | {c["nome"]: c["id"] for c in convenios}
motivos = banco_glosas.listar_motivos(conn)
datas_inicio = [r["data_inicio"] for r in conn.execute(
    "SELECT DISTINCT data_inicio FROM guias WHERE data_inicio != '' "
    "ORDER BY data_inicio").fetchall()]
f1, f2, f3, f4, f5 = st.columns(5)
convenio_sel = f1.selectbox("Convênio", list(opcoes), key="f_convenio")
motivo_sel = f2.selectbox("Motivo da glosa", ["Todos"] + motivos, key="f_motivo")
status_sel = f3.selectbox("Status do recurso", ["Todos"] + banco_glosas.STATUS,
                          key="f_status")
if datas_inicio:
    de = f4.selectbox("Período (de)", datas_inicio, index=0,
                      format_func=formatar_data_br, key="f_de")
    ate = f5.selectbox("até", list(reversed(datas_inicio)), index=0,
                       format_func=formatar_data_br, key="f_ate")
else:
    de = ate = None
convenio_id = opcoes[convenio_sel]
motivo = None if motivo_sel == "Todos" else motivo_sel
status = None if status_sel == "Todos" else status_sel

# ---- KPI CARDS ----
kpis = banco_glosas.resumo_kpis(conn, convenio_id=convenio_id, status=status,
                                motivo=motivo, de=de, ate=ate)


def _card_kpi(label, valor, cor, nome_icone):
    return (f'<div class="kpi-card"><div class="kpi-top">'
            f'<span class="kpi-label">{label}</span>'
            f'{icone(nome_icone, 20, cor)}'
            f'</div><div class="kpi-value" style="color:{cor}">{valor}</div></div>')


k1, k2, k3, k4, k5 = st.columns(5)
k1.markdown(_card_kpi("Total Glosado", f"R$ {formatar_brl(kpis['glosado'])}",
                      "#dc2626", "triangle-alert"), unsafe_allow_html=True)
k2.markdown(_card_kpi("Taxa de Glosa", f"{kpis['taxa_glosa']:.1f}%",
                      "#ca8a04", "percent"), unsafe_allow_html=True)
k3.markdown(_card_kpi("Total em Recurso", f"R$ {formatar_brl(kpis['em_recurso'])}",
                      "#2563eb", "clock"), unsafe_allow_html=True)
k4.markdown(_card_kpi("Taxa de Recuperação",
                      f"{kpis['taxa_recuperacao']:.1f}%",
                      "#059669", "trending-up"), unsafe_allow_html=True)
k5.markdown(_card_kpi("Perda Real", f"R$ {formatar_brl(kpis['perda_real'])}",
                      "#6b7280", "circle-minus"), unsafe_allow_html=True)

st.divider()

# ---- GRÁFICOS 2×2 ----
g1, g2 = st.columns(2)
g3, g4 = st.columns(2)

# 1. PARETO DE MOTIVOS (ignora filtros de status/motivo)
with g1:
    st.markdown(f"#### {icone('chart-column', 16, '#2563eb')} Motivos de Glosa "
                f"(Pareto)", unsafe_allow_html=True)
    df_motivos = banco_glosas.ranking_motivos(conn, convenio_id=convenio_id,
                                              de=de, ate=ate)
    if not df_motivos.empty:
        rotulos = [f"{d} [{c}]" if c else d
                   for d, c in zip(df_motivos["descricao"], df_motivos["cod_glosa"])]
        rotulos = [r[:28] + "…" if len(r) > 30 else r for r in rotulos]
        degradê = ["#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe", "#dbeafe", "#eff6ff"]
        cores = [degradê[i % len(degradê)] for i in range(len(df_motivos))]
        fig1 = go.Figure(go.Bar(x=rotulos, y=df_motivos["total"], marker_color=cores))
        fig1.update_xaxes(tickangle=25)
        fig1.update_layout(height=300, margin=dict(t=10, b=60),
                           yaxis_title="Valor glosado (R$)")
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("Sem glosas no período.")

# 2. STATUS DOS RECURSOS POR CONVÊNIO (empilhado; ignora filtro de status)
with g2:
    st.markdown(f"#### {icone('building-2', 16, '#2563eb')} Status dos Recursos "
                f"por Convênio", unsafe_allow_html=True)
    df_cs = banco_glosas.resumo_por_convenio_status(conn, convenio_id=convenio_id,
                                                    motivo=motivo, de=de, ate=ate)
    if not df_cs.empty:
        pivot = df_cs.pivot(index="convenio", columns="status",
                            values="total").fillna(0)
        fig2 = go.Figure()
        for st_col in banco_glosas.STATUS:
            if st_col in pivot.columns:
                fig2.add_bar(x=pivot.index, y=pivot[st_col], name=st_col,
                             marker_color=CORES_STATUS.get(st_col, "#94a3b8"))
        fig2.update_layout(barmode="stack", height=300, margin=dict(t=10, b=10),
                           legend=dict(orientation="h", y=-0.3))
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Sem dados para o período.")

# 3. EVOLUÇÃO GLOSADO × RECUPERADO (aplica todos os filtros)
with g3:
    st.markdown(f"#### {icone('trending-up', 16, '#2563eb')} Evolução: Glosado × "
                f"Recuperado", unsafe_allow_html=True)
    df_mes = banco_glosas.evolucao_mensal(conn, convenio_id=convenio_id,
                                          status=status, motivo=motivo,
                                          de=de, ate=ate)
    if not df_mes.empty:
        fig3 = go.Figure()
        fig3.add_scatter(x=df_mes["mes"], y=df_mes["glosado"], name="Glosado",
                         line=dict(color="#ef4444", width=2), fill="tozeroy",
                         fillcolor="rgba(239,68,68,0.1)")
        fig3.add_scatter(x=df_mes["mes"], y=df_mes["recuperado"],
                         name="Recuperado", line=dict(color="#10b981", width=2),
                         fill="tozeroy", fillcolor="rgba(16,185,129,0.1)")
        fig3.update_layout(height=300, margin=dict(t=10, b=10),
                           legend=dict(orientation="h", y=-0.3))
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("Sem dados para o período.")

# 4. ROSCA DE DISTRIBUIÇÃO POR STATUS (ignora filtro de status)
with g4:
    st.markdown(f"#### {icone('chart-column', 16, '#2563eb')} Distribuição da "
                f"Glosa por Status", unsafe_allow_html=True)
    df_status = banco_glosas.resumo_por_status(conn, convenio_id=convenio_id,
                                               motivo=motivo, de=de, ate=ate)
    if not df_status.empty and df_status["total"].sum() > 0:
        fig4 = go.Figure(go.Pie(
            labels=df_status["status"], values=df_status["total"], hole=0.6,
            sort=False,
            marker=dict(colors=[CORES_STATUS.get(s, "#94a3b8")
                                for s in df_status["status"]])))
        fig4.update_layout(height=300, margin=dict(t=10, b=10),
                           legend=dict(orientation="h", y=-0.3))
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("Sem glosa no período.")

st.divider()

# ---- ALERTAS DE PRAZO (globais) ----
alertas = banco_glosas.alertas_aging(conn)
st.markdown(f"#### {icone('bell-ring', 16, '#C0392B')} Alertas de Prazo — "
            f"recursos estourados ({len(alertas)})", unsafe_allow_html=True)
if alertas:
    def _criticidade(a):
        excedido = a["dias"] - a["prazo"]
        if a["vl_glosa"] > 10000 or excedido >= 15:
            return ("Crítico", "#ef4444")
        if a["vl_glosa"] > 5000 or excedido >= 7:
            return ("Médio", "#f59e0b")
        return ("Baixo", "#22c55e")

    linhas_html = "".join(
        f"<tr><td>{html.escape(a['beneficiario'])}</td>"
        f"<td>{html.escape(a['convenio'])}</td>"
        f"<td style='text-align:right'>R$ {formatar_brl(a['vl_glosa'])}</td>"
        f"<td style='text-align:center'>{a['dias']} dias</td>"
        f"<td><span class='badge-crit' style='background:{cor}1a;color:{cor};'>"
        f"{texto}</span></td></tr>"
        for a in alertas
        for texto, cor in [_criticidade(a)])
    st.markdown(
        "<table class='tabela-alertas'><thead><tr>"
        "<th>Beneficiário</th><th>Convênio</th>"
        "<th style='text-align:right'>Valor Glosado</th>"
        "<th style='text-align:center'>Dias</th><th>Criticidade</th>"
        f"</tr></thead><tbody>{linhas_html}</tbody></table>",
        unsafe_allow_html=True)
else:
    st.info("Nenhum alerta no momento. Os prazos de recurso são cadastrados por "
            "convênio na página Recursos de Glosa (Administração).")

# ---- AVISOS DE GLOSA ZERADA ----
avisos = banco_glosas.avisos_glosa_zerada(conn)
if avisos:
    st.markdown(f"#### {icone('bell-ring', 16, '#1C5A8A')} Glosa zerada no "
                f"reenvio ({len(avisos)}) — confirme na página Recursos de Glosa",
                unsafe_allow_html=True)
    st.page_link("app_pages/recursos_glosa.py", label="Abrir Recursos de Glosa")

st.divider()

# ---- TABELA DE GUIAS + EXPORTAÇÃO CSV ----
st.markdown(f"#### {icone('scroll-text', 16, '#1C5A8A')} Guias do período",
            unsafe_allow_html=True)
guias = banco_glosas.guias_filtradas(conn, convenio_id=convenio_id, status=status,
                                     motivo=motivo, de=de, ate=ate)
if guias:
    df_guias = pd.DataFrame([
        {"Guia": g["guia_prestador"], "Beneficiário": g["beneficiario"],
         "Protocolo": g["protocolo"], "Data": formatar_data_br(g["data_protocolo"]),
         "Glosa": f"R$ {formatar_brl(g['vl_glosa'])}", "Motivo": g["motivo"] or "—",
         "Status": g["status_recurso"],
         "Recuperado": f"R$ {formatar_brl(g['vl_recuperado'])}"}
        for g in guias])
    st.dataframe(df_guias, hide_index=True, height=360)
    c1, c2 = st.columns(2)
    c1.page_link("app_pages/recursos_glosa.py",
                 label="Gerenciar recursos (status, valores e avisos)")
    csv = df_guias.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig")
    c2.download_button("Exportar CSV", data=csv,
                       file_name=f"glosas_{convenio_sel.replace(' ', '_')}.csv",
                       mime="text/csv", icon=":material/download:")
else:
    st.info("Nenhuma guia no período.")

conn.close()
st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)
