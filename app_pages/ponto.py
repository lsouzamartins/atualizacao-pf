"""PÁGINA: PONTO — banco de horas pessoal (dashboard e lançamento manual)."""
from datetime import date, time, timedelta
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import banco
import ponto_core
from ui_comum import VERSAO, formatar_data_br, formatar_data_hora_br, icone

MESES = ["jan", "fev", "mar", "abr", "mai", "jun",
         "jul", "ago", "set", "out", "nov", "dez"]
DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
ROTULOS_PARA_TIPO = {"Trabalho": "trabalho", "Férias": "ferias",
                     "Feriado": "feriado", "Atestado": "atestado"}
TIPOS_PARA_ROTULO = {valor: rotulo for rotulo, valor in ROTULOS_PARA_TIPO.items()}


def _conexao():
    return banco.conectar()


def _flash(mensagem, tipo="success"):
    st.session_state["ponto_flash"] = (tipo, mensagem)


def _mostrar_flash():
    item = st.session_state.pop("ponto_flash", None)
    if item:
        getattr(st, item[0])(item[1])


def _mes_clave(dia):
    return f"{dia.year:04d}-{dia.month:02d}"


def _mes_rotulo(chave):
    ano, mes = chave.split("-")
    return f"{MESES[int(mes) - 1]}/{ano}"


def _periodo_da_chave(chave):
    ano, mes = map(int, chave.split("-"))
    inicio = date(ano, mes, 1)
    if mes == 12:
        fim = date(ano, 12, 31)
    else:
        fim = date(ano, mes + 1, 1) - timedelta(days=1)
    return inicio, fim


def _mes_padrao(registros, hoje):
    batidas = [r["data"] for r in registros
               if (r["entrada"] or r["saida"]) and r["data"] <= hoje]
    if batidas:
        return _mes_clave(max(batidas))
    passados = [r["data"] for r in registros if r["data"] <= hoje]
    return _mes_clave(max(passados) if passados else hoje)


def _ultima_atualizacao(registros, upload):
    candidatos = []
    if upload:
        candidatos.append((
            upload["enviado_em"],
            f"planilha {upload['nome_arquivo']} · "
            f"{formatar_data_hora_br(upload['enviado_em'])} · {upload['usuario']}"))
    for registro in registros:
        if registro["origem"] == "manual" and registro["atualizado_em"]:
            candidatos.append((
                registro["atualizado_em"],
                f"lançamento manual · "
                f"{formatar_data_hora_br(registro['atualizado_em'])} · "
                f"{registro['atualizado_por']}"))
    return max(candidatos)[1] if candidatos else ""


def _kpi(coluna, rotulo, valor, subtitulo="", cor=None):
    with coluna:
        with st.container(border=True):
            st.caption(rotulo)
            estilo = f"color:{cor};" if cor else ""
            st.markdown(
                f'<div style="font-size:1.65rem;font-weight:700;'
                f'line-height:1.2;{estilo}">{valor}</div>',
                unsafe_allow_html=True)
            if subtitulo:
                st.caption(subtitulo)


def _hora_de(texto):
    if not texto:
        return None
    horas, minutos = texto.split(":")
    return time(int(horas), int(minutos))


def _linhas_tabela(dias, de, ate):
    linhas = []
    for dia in ponto_core.filtrar_periodo(dias, de, ate):
        # Só dia efetivamente computado tem horas/atraso. Data futura com
        # batida completa fica "—": a situação é "futuro" e não entra no saldo.
        tem_batida = dia.situacao in ("positivo", "trabalhado", "negativo", "extra")
        especial = dia.tipo in ponto_core.TIPOS_ESPECIAIS
        linhas.append({
            "Data": formatar_data_br(dia.data.isoformat()),
            "Dia": DIAS_SEMANA[dia.data.weekday()],
            "Entrada": "—" if especial else ponto_core.minutos_para_hhmm(dia.entrada),
            "Saída": "—" if especial else ponto_core.minutos_para_hhmm(dia.saida),
            "Jornada": ponto_core.minutos_para_hhmm(dia.jornada),
            "Horas trabalhadas": (ponto_core.formatar_horas(dia.trabalhados)
                                  if tem_batida else "—"),
            "Atraso": (ponto_core.formatar_horas(dia.atraso)
                       if tem_batida else "—"),
            "Saldo do dia": (ponto_core.formatar_horas(dia.saldo)
                             if dia.computado else "—"),
            "Saldo acumulado": ponto_core.formatar_horas(dia.saldo_acumulado),
            "Situação": ponto_core.rotulo_situacao(dia.situacao),
            "Observação": dia.observacao or "—",
        })
    return linhas


def _csv(tabela):
    return tabela.to_csv(sep=";", index=False).encode("utf-8-sig")


CALENDARIO_CSS = """
<style>
.ponto-grade { display:grid; grid-template-columns:repeat(7,1fr); gap:4px;
               margin-top:8px; }
.ponto-cabecalho { font-size:.75rem; color:#64748B; text-align:center;
                   padding:4px 0; font-weight:600; }
.ponto-celula { min-height:64px; border-radius:8px; padding:6px;
                display:flex; flex-direction:column; gap:2px;
                font-size:.75rem; box-sizing:border-box; }
.ponto-celula.fora { background:#FFFFFF; border:1px solid transparent; }
.ponto-celula.vazia { background:#FFFFFF; border:1px solid #E2E8F0; }
.ponto-num { font-weight:600; font-size:.85rem; }
.ponto-marca { opacity:.9; }
.ponto-legenda { display:flex; flex-wrap:wrap; gap:12px; margin-top:10px;
                 font-size:.75rem; color:#64748B; }
.ponto-legenda span { display:inline-flex; align-items:center; gap:4px; }
.ponto-legenda i { width:10px; height:10px; border-radius:2px;
                   display:inline-block; }
</style>
"""


def _cores_celula(dia):
    mapa = {
        "trabalhado": ("#DBEAFE", "#1C5A8A", "1px solid #DBEAFE"),
        "positivo": ("#DCFCE7", "#15803D", "1px solid #DCFCE7"),
        "negativo": ("#FEE2E2", "#DC2626", "1px solid #FEE2E2"),
        "extra": ("#DCFCE7", "#15803D", "1px solid #DCFCE7"),
        "pendente": ("#FEF3C7", "#B45309", "1px solid #FEF3C7"),
        "outro": ("#FEF3C7", "#B45309", "1px solid #FEF3C7"),
        "falta": ("#FECACA", "#991B1B", "1px solid #FECACA"),
        "ferias": ("#E0F2FE", "#0369A1", "1px solid #E0F2FE"),
        "feriado": ("#F1F5F9", "#64748B", "1px solid #F1F5F9"),
        "atestado": ("#F3E8FF", "#6B21A8", "1px solid #F3E8FF"),
        "futuro": ("#FFFFFF", "#64748B", "1px dashed #E2E8F0"),
        "hoje": ("#FFFFFF", "#1C5A8A", "1px solid #1C5A8A"),
        "fim_de_semana": ("#F8FAFC", "#64748B", "1px solid #F8FAFC"),
    }
    return mapa.get(dia.situacao, ("#FFFFFF", "#64748B", "1px solid #E2E8F0"))


def _marca_celula(dia):
    if dia.situacao in ("positivo", "trabalhado", "negativo", "extra"):
        return ponto_core.formatar_horas(dia.saldo)
    if dia.situacao in ("futuro", "fim_de_semana"):
        return ""
    return ponto_core.rotulo_situacao(dia.situacao)


def _calendario_html(dias, ano, mes):
    por_data = {d.data: d for d in dias
                if d.data.year == ano and d.data.month == mes}
    primeiro = date(ano, mes, 1)
    ultimo = (date(ano, 12, 31) if mes == 12
              else date(ano, mes + 1, 1) - timedelta(days=1))
    partes = ['<div class="ponto-grade">']
    partes.extend(f'<div class="ponto-cabecalho">{nome}</div>'
                  for nome in DIAS_SEMANA)
    for _ in range(primeiro.weekday()):
        partes.append('<div class="ponto-celula fora"></div>')
    cursor = primeiro
    while cursor <= ultimo:
        dia = por_data.get(cursor)
        if dia is None:
            partes.append(
                f'<div class="ponto-celula vazia">'
                f'<span class="ponto-num">{cursor.day}</span></div>')
        else:
            fundo, cor, borda = _cores_celula(dia)
            especial = dia.tipo in ponto_core.TIPOS_ESPECIAIS
            entrada_txt = ("—" if especial
                           else ponto_core.minutos_para_hhmm(dia.entrada))
            saida_txt = ("—" if especial
                         else ponto_core.minutos_para_hhmm(dia.saida))
            horas_txt = ("—" if dia.situacao not in
                         ("positivo", "trabalhado", "negativo", "extra")
                         else ponto_core.formatar_horas(dia.trabalhados))
            saldo_txt = (ponto_core.formatar_horas(dia.saldo)
                         if dia.computado else "—")
            dica = (f"{formatar_data_br(dia.data.isoformat())} · "
                    f"Entrada {entrada_txt} · Saída {saida_txt} · "
                    f"Horas {horas_txt} · Saldo {saldo_txt}")
            if dia.observacao:
                dica += f" · {dia.observacao}"
            partes.append(
                f'<div class="ponto-celula" '
                f'style="background:{fundo};color:{cor};border:{borda}" '
                f'title="{escape(dica)}">'
                f'<span class="ponto-num">{cursor.day}</span>'
                f'<span class="ponto-marca">{escape(_marca_celula(dia))}</span>'
                f'</div>')
        cursor += timedelta(days=1)
    partes.append("</div>")
    return "".join(partes)


def _legenda_calendario():
    itens = [("Trabalhado", "#DBEAFE"), ("Positivo", "#DCFCE7"),
             ("Negativo", "#FEE2E2"), ("Pendente", "#FEF3C7"),
             ("Falta", "#FECACA"), ("Férias", "#E0F2FE"),
             ("Feriado", "#F1F5F9"), ("Atestado", "#F3E8FF"),
             ("Fim de semana", "#F8FAFC")]
    spans = "".join(
        f'<span><i style="background:{cor};border:1px solid #E2E8F0"></i>'
        f'{nome}</span>' for nome, cor in itens)
    return f'<div class="ponto-legenda">{spans}</div>'


def _secao_graficos(dias, de, ate, hoje):
    coluna_linha, coluna_barras = st.columns(2)
    with coluna_linha:
        st.markdown("**Evolução do saldo acumulado**")
        pontos = ponto_core.evolucao_saldo(dias, ate=ate, hoje=hoje)
        if pontos:
            figura = go.Figure(go.Scatter(
                x=[p[0] for p in pontos],
                y=[p[2] / 60 for p in pontos],
                customdata=[p[1] / 60 for p in pontos],
                mode="lines+markers",
                line={"color": "#1C5A8A", "width": 2},
                marker={"size": 4, "color": "#1C5A8A"},
                hovertemplate=("%{x|%d/%m/%Y}<br>Saldo do dia: "
                               "%{customdata:.2f} h<br>Acumulado: "
                               "%{y:.2f} h<extra></extra>")))
            figura.update_layout(
                height=300, margin=dict(l=8, r=8, t=8, b=8),
                yaxis_title="horas",
                plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                font={"family": "Segoe UI", "color": "#0F172A"})
            figura.add_hline(y=0, line_color="#E2E8F0", line_width=1)
            st.plotly_chart(figura, key="ponto_grafico_evolucao",
                            width="stretch")
        else:
            st.caption("Sem dias computados no período.")
    with coluna_barras:
        st.markdown("**Saldo por mês**")
        meses = ponto_core.saldo_por_mes(dias, hoje=hoje)
        if meses:
            cores = ["#15803D" if saldo > 0 else "#DC2626"
                     if saldo < 0 else "#64748B" for _, saldo in meses]
            figura = go.Figure(go.Bar(
                x=[_mes_rotulo(mes) for mes, _ in meses],
                y=[saldo / 60 for _, saldo in meses],
                customdata=[ponto_core.formatar_horas(saldo)
                            for _, saldo in meses],
                marker_color=cores,
                hovertemplate="%{x}<br>Saldo: %{customdata}<extra></extra>"))
            figura.update_layout(
                height=300, margin=dict(l=8, r=8, t=8, b=8),
                yaxis_title="horas",
                plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                font={"family": "Segoe UI", "color": "#0F172A"})
            figura.add_hline(y=0, line_color="#E2E8F0", line_width=1)
            st.plotly_chart(figura, key="ponto_grafico_meses",
                            width="stretch")
        else:
            st.caption("Sem meses para exibir.")


def _salvar_manual(dia, tipo, entrada, saida, observacao, login):
    if tipo != "trabalho":
        entrada = saida = None  # férias/feriado/atestado não guardam horário
        # Força o bloco de sync no rerun: ele recarrega do banco (entrada/
        # saída NULL no dia especial) e zera os horários antes de os widgets
        # serem criados. Atribuir direto a ponto_form_entrada/ponto_form_saida
        # aqui não funciona: os widgets já foram instanciados neste run.
        st.session_state.pop("ponto_form_data_anterior", None)
    conn = _conexao()
    try:
        banco.inicializar_banco(conn)
        banco.salvar_registro_manual(
            conn, dia,
            entrada.strftime("%H:%M") if entrada else None,
            saida.strftime("%H:%M") if saida else None,
            tipo, (observacao or "").strip() or None, login)
    finally:
        conn.close()
    _flash(f"Dia {formatar_data_br(dia.isoformat())} salvo.")
    st.rerun()


def _excluir(dia):
    conn = _conexao()
    try:
        banco.inicializar_banco(conn)
        banco.excluir_registro_ponto(conn, dia)
    finally:
        conn.close()
    for chave in ("ponto_form_data_anterior", "ponto_form_tipo",
                  "ponto_form_entrada", "ponto_form_saida", "ponto_form_obs",
                  "ponto_excluir_confirmar"):
        st.session_state.pop(chave, None)
    _flash(f"Registro de {formatar_data_br(dia.isoformat())} excluído.")
    st.rerun()


usuario = st.session_state.get("usuario", {})
if not (usuario.get("admin") or usuario.get("acesso_ponto")):
    st.error("Acesso restrito ao Controle de Ponto.")
    st.stop()

st.markdown(f"### {icone('clock', 20, '#1C5A8A')} Controle de Ponto",
            unsafe_allow_html=True)
_mostrar_flash()

hoje = date.today()
conn = _conexao()
try:
    banco.inicializar_banco(conn)
    registros = banco.registros_ponto(conn)
    uploads = banco.listar_uploads_ponto(conn, limite=20)
finally:
    conn.close()
dias = ponto_core.calcular_dias(registros, hoje=hoje)

de = ate = None
chave_csv = "tudo"
mes_calendario = _mes_clave(hoje)
if registros:
    meses = sorted({_mes_clave(r["data"]) for r in registros}, reverse=True)
    opcoes = ["Tudo"] + [_mes_rotulo(mes) for mes in meses]
    padrao = _mes_padrao(registros, hoje)
    indice = 1 + meses.index(padrao) if padrao in meses else 0
    escolha = st.selectbox("Período", opcoes, index=indice, key="ponto_periodo")
    if escolha == "Tudo":
        mes_calendario = _mes_padrao(registros, hoje)
    else:
        mes_calendario = meses[opcoes.index(escolha) - 1]
        de, ate = _periodo_da_chave(mes_calendario)
        chave_csv = mes_calendario
    ultima = _ultima_atualizacao(registros, uploads[0] if uploads else None)
    if ultima:
        st.caption(f"Última atualização: {ultima}")
    totais = ponto_core.totais_periodo(dias, de, ate, hoje=hoje)
    c1, c2, c3, c4, c5 = st.columns(5)
    _kpi(c1, "Saldo acumulado", ponto_core.formatar_horas(totais["saldo"]),
         "desde a primeira data importada",
         "#15803D" if totais["saldo"] >= 0 else "#DC2626")
    _kpi(c2, "Horas no período", ponto_core.formatar_horas(totais["trabalhados"]),
         f"{totais['dias_trabalhados']} dias · jornada "
         f"{ponto_core.formatar_horas(totais['jornada'])}")
    _kpi(c3, "Atrasos", ponto_core.formatar_horas(totais["atraso"]), "informativo")
    _kpi(c4, "Faltas", str(totais["faltas"]), "dias no período")
    _kpi(c5, "Pendências", str(totais["pendencias"]), "batidas incompletas")
    _secao_graficos(dias, de, ate, hoje)
    ano_calendario, mes_calendario_num = map(int, mes_calendario.split("-"))
    st.markdown(CALENDARIO_CSS, unsafe_allow_html=True)
    st.markdown(_calendario_html(dias, ano_calendario, mes_calendario_num)
                + _legenda_calendario(), unsafe_allow_html=True)
else:
    st.info("Nenhum ponto registrado ainda. Use o formulário abaixo para "
            "lançar o primeiro dia.")

with st.expander("Lançar/editar ponto", expanded=not registros):
    mapa = {r["data"]: r for r in registros}
    data_escolhida = st.date_input("Data", value=date.today(),
                                   format="DD/MM/YYYY", key="ponto_form_data")
    if st.session_state.get("ponto_form_data_anterior") != data_escolhida:
        registro = mapa.get(data_escolhida) or {}
        st.session_state["ponto_form_tipo"] = TIPOS_PARA_ROTULO.get(
            registro.get("tipo", "trabalho"), "Trabalho")
        st.session_state["ponto_form_entrada"] = _hora_de(registro.get("entrada"))
        st.session_state["ponto_form_saida"] = _hora_de(registro.get("saida"))
        st.session_state["ponto_form_obs"] = registro.get("observacao") or ""
        # Sem esta limpeza, um "Confirmo excluir" marcado na data anterior
        # continuaria valendo para a nova data selecionada.
        st.session_state.pop("ponto_excluir_confirmar", None)
        st.session_state["ponto_form_data_anterior"] = data_escolhida
    if uploads:
        periodo_de_importado = date.fromisoformat(uploads[0]["periodo_de"])
        periodo_ate_importado = date.fromisoformat(uploads[0]["periodo_ate"])
        if not (periodo_de_importado <= data_escolhida <= periodo_ate_importado):
            st.warning("Esta data está fora do período da última planilha "
                       "importada. O lançamento é permitido.")
    # Fora do form: dentro dele os widgets só atualizam ao clicar em Enviar,
    # e o horário precisa desabilitar no mesmo instante em que a situação muda.
    rotulo_tipo = st.selectbox("Situação", list(ROTULOS_PARA_TIPO),
                               key="ponto_form_tipo")
    with st.form("ponto_manual"):
        entrada = st.time_input("Entrada", key="ponto_form_entrada", step=60,
                                disabled=rotulo_tipo != "Trabalho")
        saida = st.time_input("Saída", key="ponto_form_saida", step=60,
                              disabled=rotulo_tipo != "Trabalho")
        observacao = st.text_input("Observação", key="ponto_form_obs")
        salvar = st.form_submit_button("Salvar", type="primary")
    if salvar:
        tipo = ROTULOS_PARA_TIPO[rotulo_tipo]
        if tipo == "trabalho" and entrada is None and saida is None:
            st.error("Informe a entrada e/ou a saída do dia.")
        elif (tipo == "trabalho" and entrada is not None and saida is not None
              and saida <= entrada):
            st.error("A saída deve ser maior que a entrada.")
        else:
            _salvar_manual(data_escolhida, tipo, entrada, saida, observacao,
                           usuario["login"])
    confirmar = st.checkbox("Confirmo excluir o dia selecionado",
                            key="ponto_excluir_confirmar",
                            disabled=data_escolhida not in mapa)
    if st.button("Excluir dia",
                 disabled=not confirmar or data_escolhida not in mapa):
        _excluir(data_escolhida)

if registros:
    linhas = _linhas_tabela(dias, de, ate)
    if linhas:
        tabela = pd.DataFrame(linhas)
        st.dataframe(tabela, hide_index=True, width="stretch", height=420)
        st.download_button("Baixar CSV", data=_csv(tabela),
                           file_name=f"ponto-{chave_csv}.csv", mime="text/csv")
    else:
        st.info("Sem dias no período selecionado. Troque o mês no seletor.")

st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)
