"""
==============================================================================
PÁGINA: PROCESSAMENTO — ATUALIZAÇÃO PF · HIAS
Execução das fases 0–4 (lógica intocável em core.py).

Revisão: Claude Code (Anthropic) · 28/07/2026 · migrada para app_pages/ em 19/08/2026
==============================================================================
"""
import os
import io
import subprocess
from datetime import datetime
from contextlib import redirect_stdout, redirect_stderr

import streamlit as st

from ui_comum import icone, pastas, VERSAO
from core import (
    encontrar_arquivo_entrada,
    salvar_log_erro,
    gerar_resumo,
    processar_fase_0_wpd,
    processar_fase_1_nao_identificado,
    processar_fases_2_3_4_hias,
)


# ==============================================================================
# RESOLUÇÃO DE CAMINHOS
# ==============================================================================
_caminhos = pastas()
PASTA_RAIZ = _caminhos["raiz"]
PASTA_RELATORIOS = _caminhos["relatorios"]
PASTA_SAIDA = _caminhos["saida"]
PASTA_ERROS = _caminhos["erros"]


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


# ---- LAYOUT PRINCIPAL ----
col_acoes, col_status = st.columns([1.5, 1], gap="large")

with col_acoes:
    st.markdown(f"### {icone('play', 20, '#1C5A8A')} Executar Processamento", unsafe_allow_html=True)

    try:
        arquivos_necessarios = [
            encontrar_arquivo_entrada(PASTA_RAIZ, "WPD-26.xls"),
            encontrar_arquivo_entrada(PASTA_RAIZ, "Não_Identificado.xls"),
            encontrar_arquivo_entrada(PASTA_RAIZ, "Posição Financeira Hias.xlsx"),
        ]
        arquivos_faltando = [arq for arq in arquivos_necessarios if not os.path.exists(arq)]
    except FileNotFoundError as e:
        arquivos_faltando = [str(e)]

    if arquivos_faltando:
        st.error("**Arquivos necessários não encontrados:**")
        for arq in arquivos_faltando:
            st.write(f"- `{arq}`")
        st.info(f"Pasta raiz: `{PASTA_RAIZ}`")
        btn_desabilitado = True
    else:
        btn_desabilitado = False
        with st.expander("Arquivos de entrada encontrados", icon=":material/task_alt:", expanded=False):
            for arq in arquivos_necessarios:
                tamanho = os.path.getsize(arq)
                st.write(f"- ✅ `{os.path.basename(arq)}` ({tamanho / 1024:.1f} KB)")

    btn_col1, btn_col2 = st.columns([1, 1], gap="small")
    with btn_col1:
        executar = st.button(
            "Atualizar posição financeira",
            type="primary",
            icon=":material/play_arrow:",
            disabled=btn_desabilitado or st.session_state.em_andamento,
            width="stretch",
        )
    with btn_col2:
        abrir_pasta = st.button("Abrir pasta de saída", type="secondary", icon=":material/folder_open:", width="stretch")
        if abrir_pasta:
            if os.path.exists(PASTA_SAIDA):
                subprocess.Popen(['explorer', PASTA_SAIDA])
            else:
                st.warning("A pasta de saída ainda não existe. Execute primeiro.")

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

    # Prepara caminhos
    xls_wpd = encontrar_arquivo_entrada(PASTA_RAIZ, "WPD-26.xls")
    xls_nao_identificado = encontrar_arquivo_entrada(PASTA_RAIZ, "Não_Identificado.xls")
    xlsx_hias_base = encontrar_arquivo_entrada(PASTA_RAIZ, "Posição Financeira Hias.xlsx")
    xlsx_wpd_limpo = os.path.join(PASTA_SAIDA, "WPD-26_Extraido.xlsx")
    xlsx_nao_identificado_limpo = os.path.join(PASTA_SAIDA, "Não_Identificado_Extraido.xlsx")
    data_hoje = datetime.now().strftime("%d.%m.%y")
    xlsx_hias_final = os.path.join(PASTA_SAIDA, f"Posição Financeira Hias_{data_hoje}.xlsx")

    sucesso = False
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            # Limpeza de Excel residual
            print("🧹 Verificando e liberando arquivos de execuções anteriores...")
            try:
                subprocess.run(["taskkill", "/f", "/im", "EXCEL.EXE"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("   OK — processos do Excel liberados.\n")
            except Exception:
                pass

            # FASE 0 (0% → 33%)
            progress_bar.progress(5, text="[Fase 0/4] Processando WPD-26...")
            df_wpd = processar_fase_0_wpd(xls_wpd, xlsx_wpd_limpo)
            progress_bar.progress(33, text="[Fase 0/4] WPD-26 ✓")

            # FASE 1 (33% → 66%)
            progress_bar.progress(38, text="[Fase 1/4] Processando Não Identificado...")
            df_ni = processar_fase_1_nao_identificado(xls_nao_identificado, xlsx_nao_identificado_limpo)
            progress_bar.progress(66, text="[Fase 1/4] Não Identificado ✓")

            # FASES 2-4 (66% → 100%)
            progress_bar.progress(71, text="[Fases 2-4/4] Integrando ao Hias...")
            processar_fases_2_3_4_hias(
                xlsx_nao_identificado_limpo, xlsx_hias_base, xlsx_hias_final,
                PASTA_RAIZ, PASTA_SAIDA, xlsx_wpd_limpo
            )

            # Resumo
            gerar_resumo(df_ni, df_wpd, xlsx_wpd_limpo, xlsx_nao_identificado_limpo)

            progress_bar.progress(100, text="Concluído com sucesso!")
            sucesso = True

    except Exception as e:
        print(f"\n[CRÍTICO] Ocorreu um erro: {type(e).__name__}: {e}")
        try:
            log_path = salvar_log_erro(PASTA_ERROS, e)
            print(f"Diagnóstico salvo em: {log_path}")
        except Exception:
            pass
        progress_bar.progress(100, text="Erro na execução!")
        sucesso = False

    finally:
        st.session_state.em_andamento = False

    log_texto = log_buffer.getvalue()
    st.session_state.ultimo_log = log_texto
    st.session_state.ultimo_sucesso = sucesso
    st.session_state.ultima_execucao = datetime.now().strftime("%d/%m/%Y %H:%M")

    if sucesso:
        st.toast("Concluído com sucesso!", icon=":material/check_circle:")
    else:
        st.toast("Erro na execução. Verifique o log.", icon=":material/error:")

    with st.container(height=450, border=True):
        st.code(log_texto, language=None, line_numbers=False)
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
        <p class="info-paths">
            {icone('folder', 14, '#64748B')} Entrada: <code>{PASTA_RELATORIOS}</code>&nbsp;&nbsp;
            {icone('folder-output', 14, '#64748B')} Saída: <code>{PASTA_SAIDA}</code>
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)
