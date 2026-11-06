"""PÁGINA: PONTO — banco de horas pessoal (dashboard e lançamento manual)."""
from datetime import date, time, timedelta

import pandas as pd
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


def _salvar_manual(dia, tipo, entrada, saida, observacao, login):
    if tipo != "trabalho":
        entrada = saida = None  # férias/feriado/atestado não guardam horário
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
