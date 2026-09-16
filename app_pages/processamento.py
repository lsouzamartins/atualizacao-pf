"""
==============================================================================
PÁGINA: PROCESSAMENTO — ATUALIZAÇÃO PF · HIAS
Execução das fases 0–4 (lógica intocável em core.py).

Revisão: Claude Code (Anthropic) · 28/07/2026 · migrada para app_pages/ em 19/08/2026
· 01/09/2026 · uploads por sessão (file_uploader), gravação no banco e downloads
· 15/09/2026 · base da Posição Financeira persistente no site (dados/base_pf/):
  a execução pede só os 2 relatórios, faz backup e atualiza a própria base
==============================================================================
"""
import os
import io
import shutil
from uuid import uuid4
from datetime import datetime
from contextlib import redirect_stdout, redirect_stderr

import pandas as pd
import streamlit as st

import banco
import base_pf

from ui_comum import icone, pastas, VERSAO
from core import (
    salvar_log_erro,
    salvar_log_execucao,
    gerar_resumo,
    criar_backup_hias,
    processar_fase_0_wpd,
    processar_fase_1_nao_identificado,
    processar_fases_2_3_4_hias,
)


def agregar_para_banco(df_ni: pd.DataFrame) -> pd.DataFrame:
    """Agrega o df_ni da Fase 1 em resumos diários por convênio (mesmas regras
    de limpeza da página Resumo do dia)."""
    df = df_ni.copy()
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce", dayfirst=True).dt.date
    df = df.dropna(subset=["Data"])
    df = df[df[["Depósito Bruto", "Depósito Liq.", "Quitação",
                "Não Identificado"]].sum(axis=1) != 0.0]
    return (
        df.groupby(["Data", "Convênio"], as_index=False)
          .agg(vlr_bruto=("Depósito Bruto", "sum"),
               vlr_liquido=("Depósito Liq.", "sum"),
               quitado=("Quitação", "sum"),
               nao_identificado=("Não Identificado", "sum"))
          .rename(columns={"Data": "data", "Convênio": "convenio"})
    )


# ==============================================================================
# RESOLUÇÃO DE CAMINHOS
# ==============================================================================
_caminhos = pastas()
PASTA_RAIZ = _caminhos["raiz"]
PASTA_RELATORIOS = _caminhos["relatorios"]
PASTA_SAIDA = _caminhos["saida"]
PASTA_ERROS = _caminhos["erros"]
PASTA_LOGS = _caminhos["logs"]
PASTA_UPLOADS = os.path.join(PASTA_RAIZ, "uploads")
XLSX_HIAS_BASE = base_pf.caminho_base()


# ==============================================================================
# INTERFACE STREAMLIT
# ==============================================================================

# Inicialização de session_state
defaults = {
    "ultimo_log": "", "ultimo_sucesso": None,
    "ultima_execucao": None, "em_andamento": False,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ---- BASE DA POSIÇÃO FINANCEIRA (persistente no site) ----
st.markdown(f"### {icone('database', 20, '#1C5A8A')} Base da Posição Financeira", unsafe_allow_html=True)
info_base = base_pf.info_base()
col_base_info, col_base_baixar, col_base_trocar = st.columns([2, 1, 1], gap="large")

with col_base_info:
    if info_base:
        st.markdown(f"""
        <div class="info-card">
            <p>{icone('database', 16, '#1C5A8A')} <b>Base no site:</b> atualizada em
            {info_base['modificado'].strftime('%d/%m/%Y %H:%M')} ·
            {info_base['tamanho'] / (1024 * 1024):.1f} MB</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("Nenhuma base cadastrada no site. Envie o arquivo abaixo para "
                   "liberar o processamento.")

with col_base_baixar:
    if info_base:
        with open(info_base["caminho"], "rb") as f:
            st.download_button("Baixar base",
                               data=f.read(),
                               file_name=base_pf.NOME_BASE,
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with col_base_trocar:
    up_base = st.file_uploader("Substituir base (.xlsx)", type=["xlsx"], key="up_base")
    if up_base is not None and st.button("Salvar base no site", type="primary"):
        base_pf.salvar_base(up_base.getvalue(), pasta_backup=PASTA_SAIDA)
        st.success("Base salva no site. A anterior ficou em backup na pasta de saída.")
        st.rerun()

st.divider()


# ---- LAYOUT PRINCIPAL ----
col_acoes, col_status = st.columns([1.5, 1], gap="large")

with col_acoes:
    st.markdown(f"### {icone('play', 20, '#1C5A8A')} Executar Processamento", unsafe_allow_html=True)

    st.markdown("### 📂 Arquivos do dia")
    col1, col2 = st.columns(2)
    arquivos = {
        "WPD-26.xls": col1.file_uploader("WPD-26 (.xls)", type=["xls"], key="up_wpd"),
        "Não_Identificado.xls": col2.file_uploader("Não Identificado (.xls)", type=["xls"], key="up_ni"),
    }
    btn_desabilitado = (not all(arquivos.values())
                        or st.session_state.em_andamento
                        or not base_pf.base_existe())

    executar = st.button(
        "Atualizar posição financeira",
        type="primary",
        icon=":material/play_arrow:",
        disabled=btn_desabilitado,
        width="stretch",
    )

with col_status:
    st.markdown(f"### {icone('activity', 20, '#1C5A8A')} Status", unsafe_allow_html=True)
    if st.session_state.ultimo_sucesso is True:
        st.success(f"**Última execução:** Sucesso — {st.session_state.ultima_execucao or '—'}")
    elif st.session_state.ultimo_sucesso is False:
        st.error(f"**Última execução:** Falha — {st.session_state.ultima_execucao or '—'}")
    else:
        st.info("Nenhuma execução registrada nesta sessão.")
    if os.path.exists(PASTA_SAIDA):
        arquivos_xlsx = sorted(
            [f for f in os.listdir(PASTA_SAIDA) if f.startswith("Posição Financeira Hias") and f.endswith(".xlsx")],
            reverse=True
        )
        if arquivos_xlsx:
            st.caption(f"Último output: `{arquivos_xlsx[0]}`")


# ---- ÁREA DE EXECUÇÃO E LOG ----
if executar and not st.session_state.em_andamento:
    st.session_state.em_andamento = True

    st.divider()
    st.markdown(f"### {icone('scroll-text', 20, '#1C5A8A')} Log de Execução", unsafe_allow_html=True)

    progress_bar = st.progress(0, text="Iniciando...")
    log_buffer = io.StringIO()

    # Sessão de uploads desta execução (apagada ao final, com sucesso ou erro)
    pasta_sessao = os.path.join(PASTA_UPLOADS, uuid4().hex)

    xls_wpd = os.path.join(pasta_sessao, "WPD-26.xls")
    xls_nao_identificado = os.path.join(pasta_sessao, "Não_Identificado.xls")
    xlsx_hias_base = XLSX_HIAS_BASE
    xlsx_wpd_limpo = os.path.join(PASTA_SAIDA, "WPD-26_Extraido.xlsx")
    xlsx_nao_identificado_limpo = os.path.join(PASTA_SAIDA, "Não_Identificado_Extraido.xlsx")
    data_hoje = datetime.now().strftime("%d.%m.%y")
    xlsx_hias_final = os.path.join(PASTA_SAIDA, f"Posição Financeira Hias_{data_hoje}.xlsx")

    # Rastreabilidade: a execução é gravada no banco DESDE O INÍCIO
    # (status 'em_andamento') — se o processo morrer no meio, fica o registro.
    conn = None
    execucao_id = None
    fase_atual = "Preparação"
    log_erro_path = None
    sucesso = False
    try:
        conn = banco.conectar()
        banco.inicializar_banco(conn)
        execucao_id = banco.iniciar_execucao(conn, st.session_state["usuario"]["login"])

        os.makedirs(pasta_sessao, exist_ok=True)
        for nome, upload in arquivos.items():
            with open(os.path.join(pasta_sessao, nome), "wb") as f:
                f.write(upload.getbuffer())

        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            # Limpeza de Excel residual
            print("🧹 Preparando ambiente...")

            # FASE 0 (0% → 33%)
            fase_atual = "Fase 0 (WPD-26)"
            progress_bar.progress(5, text="[Fase 0/4] Processando WPD-26...")
            df_wpd = processar_fase_0_wpd(xls_wpd, xlsx_wpd_limpo)
            progress_bar.progress(33, text="[Fase 0/4] WPD-26 ✓")

            # FASE 1 (33% → 66%)
            fase_atual = "Fase 1 (Não Identificado)"
            progress_bar.progress(38, text="[Fase 1/4] Processando Não Identificado...")
            df_ni = processar_fase_1_nao_identificado(xls_nao_identificado, xlsx_nao_identificado_limpo)
            progress_bar.progress(66, text="[Fase 1/4] Não Identificado ✓")

            # FASES 2-4 (66% → 100%)
            fase_atual = "Fases 2-4 (Integração Hias)"
            progress_bar.progress(71, text="[Fases 2-4/4] Integrando ao Hias...")
            print("💾 Backup da base atual do site...")
            criar_backup_hias(xlsx_hias_base, PASTA_SAIDA)
            processar_fases_2_3_4_hias(
                xlsx_nao_identificado_limpo, xlsx_hias_base, xlsx_hias_final,
                PASTA_RAIZ, PASTA_SAIDA, xlsx_wpd_limpo
            )

            # Resumo
            gerar_resumo(df_ni, df_wpd, xlsx_wpd_limpo, xlsx_nao_identificado_limpo)

            progress_bar.progress(100, text="Concluído com sucesso!")
            sucesso = True

    except Exception as e:
        print(f"\n[CRÍTICO] Erro na {fase_atual}: {type(e).__name__}: {e}")
        if conn is not None:
            try:
                banco.finalizar_execucao(conn, execucao_id, "falha", str(e)[:500], [])
            except Exception as e_reg:
                print(f"[AVISO] Não foi possível registrar a falha no banco: {e_reg}")
        try:
            log_erro_path = salvar_log_erro(
                PASTA_ERROS, e, log_execucao=log_buffer.getvalue(), fase=fase_atual)
            print(f"Diagnóstico salvo em: {log_erro_path}")
        except Exception:
            pass
        progress_bar.progress(100, text="Erro na execução!")
        sucesso = False

    finally:
        shutil.rmtree(pasta_sessao, ignore_errors=True)
        st.session_state.em_andamento = False

    if sucesso:
        try:
            base_pf.atualizar_base(xlsx_hias_final)
            print("✅ Base da Posição Financeira atualizada no site.")
        except Exception as e:
            print(f"[AVISO] Processamento OK, mas falha ao atualizar a base no site: {e}")
            st.warning(f"Processamento OK, mas falha ao atualizar a base no site: {e}")
        try:
            df_resumos = agregar_para_banco(df_ni)
            arquivos_gerados = [os.path.basename(xlsx_hias_final),
                                os.path.basename(xlsx_wpd_limpo),
                                os.path.basename(xlsx_nao_identificado_limpo)]
            # grava com a conexão AINDA ABERTA (bug da execução 20: o close
            # acontecia no finally, antes desta gravação)
            banco.concluir_sucesso(conn, execucao_id, arquivos_gerados, df_resumos)
        except Exception as e:
            print(f"[AVISO] Processamento OK, mas falha ao gravar no banco: {e}")
            st.warning(f"Processamento OK, mas falha ao gravar no banco: {e}")

    # A conexão só é fechada aqui, DEPOIS da gravação do resultado
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass

    log_texto = log_buffer.getvalue()
    if execucao_id is not None:
        try:
            salvar_log_execucao(PASTA_LOGS, execucao_id, log_texto)
        except Exception as e:
            print(f"[AVISO] Não foi possível salvar o log da execução: {e}")
    st.session_state.ultimo_log = log_texto
    st.session_state.ultimo_sucesso = sucesso
    st.session_state.ultima_execucao = datetime.now().strftime("%d/%m/%Y %H:%M")

    if sucesso:
        st.toast("Concluído com sucesso!", icon=":material/check_circle:")
    else:
        st.toast("Erro na execução. Diagnóstico salvo — consulte o Histórico.",
                 icon=":material/error:")
        if log_erro_path:
            trecho = f" (Execução {execucao_id})" if execucao_id is not None else ""
            st.error(
                f"O processamento parou na **{fase_atual}**.\n\n"
                f"Diagnóstico completo salvo em `{os.path.basename(log_erro_path)}`"
                f" (pasta 'logo de erro').\n\n"
                f"Na página **Histórico** você vê o log completo desta execução{trecho}."
            )

    with st.container(height=450, border=True):
        st.code(log_texto, language=None, line_numbers=False)

    st.download_button("Baixar log da execução",
                       data=log_texto,
                       file_name=f"log_execucao_{datetime.now().strftime('%Y%m%d')}.txt",
                       mime="text/plain")

    if sucesso and os.path.exists(xlsx_hias_final):
        with open(xlsx_hias_final, "rb") as f:
            st.download_button("Baixar Posição Financeira atualizada",
                               data=f.read(),
                               file_name=os.path.basename(xlsx_hias_final),
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               type="primary")
    st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)

elif st.session_state.ultimo_log:
    st.divider()
    st.markdown(f"### {icone('scroll-text', 20, '#1C5A8A')} Log da Última Execução", unsafe_allow_html=True)
    if st.session_state.ultimo_sucesso:
        st.success("Última execução concluída com sucesso.")
    else:
        st.error("Última execução concluída com erro.")
    with st.container(height=450, border=True):
        st.code(st.session_state.ultimo_log, language=None, line_numbers=False)
    st.download_button("Baixar log da execução",
                       data=st.session_state.ultimo_log,
                       file_name=f"log_execucao_{datetime.now().strftime('%Y%m%d')}.txt",
                       mime="text/plain")
    st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)

else:
    st.divider()
    st.markdown(f"### {icone('scroll-text', 20, '#1C5A8A')} Log de Execução", unsafe_allow_html=True)
    st.info("Clique em **Atualizar posição financeira** para iniciar o processamento.")
    st.markdown(f"""
    <div class="info-card">
        <h4>{icone('info', 18, '#1C5A8A')} O que este script faz:</h4>
        <ol>
            <li><b>Fase 0:</b> Extrai e limpa dados do arquivo <code>WPD-26.xls</code></li>
            <li><b>Fase 1:</b> Extrai e limpa dados do arquivo <code>Não_Identificado.xls</code></li>
            <li><b>Fase 2-3:</b> Abre o Excel Hias e injeta os dados processados na aba <code>BD2</code></li>
            <li><b>Fase 4:</b> Salva uma nova versão datada do arquivo Hias</li>
        </ol>
        <p>A base da Posição Financeira fica salva no site: você envia só os
        2 relatórios e o site atualiza a própria base (com backup automático).
        Use o botão de substituir base apenas quando fizer correções manuais
        na planilha.</p>
        <p class="info-paths">
            {icone('folder-output', 14, '#64748B')} Saída: <code>{PASTA_SAIDA}</code>
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)
