"""
==============================================================================
NÚCLEO DE PROCESSAMENTO — ATUALIZAÇÃO DA POSIÇÃO FINANCEIRA
Hospital Israelita Albert Sabin

Módulo centralizado com toda a lógica de extração, limpeza e integração.
Importado por todas as interfaces (Streamlit, Flet, Tkinter).

Revisão: Claude Code (Anthropic) · 28/07/2026
==============================================================================
"""
import os
import sys
import re
import shutil
import subprocess
import traceback
import json
from datetime import datetime

import pandas as pd
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter


# ==============================================================================
# RESOLUÇÃO DINÂMICA DE CAMINHOS
# ==============================================================================
def obter_pasta_raiz():
    """Detecta automaticamente a pasta raiz da aplicação."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        # Sobe um nível se for importado de outro arquivo
        caller = sys._getframe(1).f_globals.get('__file__', __file__)
        return os.path.dirname(os.path.abspath(caller))


def encontrar_arquivo_entrada(pasta_raiz: str, nome: str) -> str:
    """Procura arquivo em relatórios/ e na raiz. Retorna caminho ou levanta FileNotFoundError."""
    caminho_relatorios = os.path.join(pasta_raiz, "relatórios", nome)
    caminho_raiz = os.path.join(pasta_raiz, nome)
    if os.path.exists(caminho_relatorios):
        return caminho_relatorios
    if os.path.exists(caminho_raiz):
        return caminho_raiz
    raise FileNotFoundError(
        f"Arquivo '{nome}' não encontrado.\n"
        f"Procurado em:\n"
        f"  - {caminho_relatorios}\n"
        f"  - {caminho_raiz}"
    )


def garantir_pastas(pasta_raiz: str):
    """Cria pastas de saída, erros, logs e fotos se não existirem."""
    os.makedirs(os.path.join(pasta_raiz, "saída"), exist_ok=True)
    os.makedirs(os.path.join(pasta_raiz, "logo de erro"), exist_ok=True)
    os.makedirs(os.path.join(pasta_raiz, "logs"), exist_ok=True)
    os.makedirs(os.path.join(pasta_raiz, "dados", "fotos"), exist_ok=True)


# ==============================================================================
# FUNÇÕES DE LIMPEZA DE DADOS
# ==============================================================================
def extrair_data(valor):
    """
    Extrai dd/mm (com ou sem ano) e retorna datetime com ano correto.
    Usa o ano atual dinamicamente — sem valores hardcoded.
    """
    try:
        if pd.isna(valor) or valor in ["", "nan", "None"]:
            return pd.NaT
        valor_str = str(valor).strip()
        match = re.search(r'(\d{1,2})/(\d{1,2})(?:/(\d{4}))?', valor_str)
        if not match:
            return pd.NaT
        dia = int(match.group(1))
        mes = int(match.group(2))
        ano_str = match.group(3)
        if ano_str:
            ano = int(ano_str)
        else:
            hoje = datetime.now()
            # Se o mês é maior que o mês atual, é do ano passado
            ano = hoje.year if mes <= hoje.month else hoje.year - 1
        return pd.Timestamp(f"{ano}-{mes:02d}-{dia:02d}")
    except Exception:
        return pd.NaT


def converter_baixa(valor):
    """Tenta converter a coluna Baixa para datetime."""
    try:
        if pd.isna(valor) or valor in ["", "nan", "None"]:
            return pd.NaT
        dt = pd.to_datetime(valor, errors='coerce')
        if pd.notna(dt):
            return dt
        return extrair_data(valor)
    except Exception:
        return pd.NaT


def limpar_numero(valor):
    """Converte string com vírgula e ponto para float."""
    try:
        if pd.isna(valor):
            return 0.0
        if isinstance(valor, (int, float)):
            return float(valor)
        valor_str = str(valor).strip()
        if valor_str in ["", "-", "nan", "0", "0.0"]:
            return 0.0
        if "," in valor_str and "." in valor_str:
            valor_str = valor_str.replace(".", "").replace(",", ".")
        elif "," in valor_str:
            valor_str = valor_str.replace(",", ".")
        return float(valor_str)
    except Exception:
        return 0.0


def converter_inteiro(valor):
    """Converte para inteiro."""
    try:
        if pd.isna(valor):
            return 0
        return int(float(str(valor).strip()))
    except Exception:
        return 0


# ==============================================================================
# LOG DE ERROS COM ROTAÇÃO (mantém os últimos 5)
# ==============================================================================
MAX_LOGS_ERRO = 5
MAX_LOGS_EXECUCAO = 20


def salvar_log_erro(pasta_erros: str, exception: Exception,
                    log_execucao=None, fase=None, agora=None):
    """Salva o log de erro com rotação (últimos 5 logs preservados).

    log_execucao: log completo da execução até o erro (o "antes").
    fase: em qual fase do processamento o erro ocorreu.
    """
    now = agora or datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    log_arquivo = os.path.join(pasta_erros, f"erro_{timestamp}.txt")

    with open(log_arquivo, "w", encoding="utf-8") as f:
        f.write("=== LOG DE ERRO ===\n")
        f.write(f"Data/Hora: {now.strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write(f"Tipo: {type(exception).__name__}\n")
        f.write(f"Mensagem: {str(exception)}\n")
        if fase:
            f.write(f"Fase: {fase}\n")
        f.write("\n")
        if log_execucao:
            f.write("=== LOG DA EXECUÇÃO (o que aconteceu antes do erro) ===\n")
            f.write(log_execucao.rstrip() + "\n\n")
        f.write("=== RASTREAMENTO DO ERRO ===\n")
        f.write(traceback.format_exc())

    # Rotação: mantém só os 5 mais recentes
    logs = sorted(
        [f for f in os.listdir(pasta_erros) if f.startswith("erro_") and f.endswith(".txt")],
        reverse=True
    )
    for log_antigo in logs[MAX_LOGS_ERRO:]:
        try:
            os.remove(os.path.join(pasta_erros, log_antigo))
        except Exception:
            pass

    return log_arquivo


def salvar_log_execucao(pasta_logs: str, execucao_id: int, texto: str) -> str:
    """Guarda o log completo de uma execução (execucao_<id>.txt) com rotação
    (mantém as últimas 20 execuções). Devolve o caminho do arquivo."""
    os.makedirs(pasta_logs, exist_ok=True)
    log_arquivo = os.path.join(pasta_logs, f"execucao_{execucao_id}.txt")
    with open(log_arquivo, "w", encoding="utf-8") as f:
        f.write(texto)

    # Rotação: mantém só as 20 execuções de maior id
    ids = []
    for nome in os.listdir(pasta_logs):
        m = re.match(r"execucao_(\d+)\.txt$", nome)
        if m:
            ids.append((int(m.group(1)), nome))
    if len(ids) > MAX_LOGS_EXECUCAO:
        ids.sort(reverse=True)
        for _, nome in ids[MAX_LOGS_EXECUCAO:]:
            try:
                os.remove(os.path.join(pasta_logs, nome))
            except Exception:
                pass

    return log_arquivo


# ==============================================================================
# BACKUP AUTOMÁTICO DO ARQUIVO HIAS BASE
# ==============================================================================
def criar_backup_hias(xlsx_hias_base: str, pasta_saida: str) -> str:
    """
    Cria uma cópia de segurança do arquivo Hias base antes de modificá-lo.
    Retorna o caminho do backup.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_backup = f"BACKUP_Hias_{timestamp}.xlsx"
    caminho_backup = os.path.join(pasta_saida, nome_backup)
    shutil.copy2(xlsx_hias_base, caminho_backup)
    return caminho_backup


# ==============================================================================
# RESUMO PÓS-PROCESSAMENTO
# ==============================================================================
def gerar_resumo(df_ni_final, df_wpd_filtrado, xlsx_wpd_limpo, xlsx_nao_identificado_limpo):
    """Gera e imprime um resumo amigável do processamento."""
    num_linhas_ni = len(df_ni_final)
    num_linhas_wpd = len(df_wpd_filtrado)
    num_convenios = df_ni_final["Convênio"].nunique() if "Convênio" in df_ni_final.columns else 0

    # Soma de depósitos (coluna Depósito Bruto, índice 3)
    total_depositos = 0.0
    if "Depósito Bruto" in df_ni_final.columns:
        total_depositos = df_ni_final["Depósito Bruto"].sum()

    print("\n" + "─" * 50)
    print("  📊 RESUMO DO PROCESSAMENTO")
    print("─" * 50)
    print(f"  • Arquivo WPD-26 salvo em: {os.path.basename(xlsx_wpd_limpo)}")
    print(f"  • Arquivo Não Identificado salvo em: {os.path.basename(xlsx_nao_identificado_limpo)}")
    print(f"  • Linhas processadas (WPD-26): {num_linhas_wpd}")
    print(f"  • Linhas processadas (Não Identificado): {num_linhas_ni}")
    print(f"  • Convênios distintos: {num_convenios}")
    if total_depositos != 0:
        print(f"  • Total em depósitos brutos: R$ {total_depositos:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    print("─" * 50)


# ==============================================================================
# PROCESSAMENTO — FASE 0: WPD-26
# ==============================================================================
def _filtrar_linhas_lixo(df_wpd: pd.DataFrame) -> pd.DataFrame:
    """Remove linhas de cabeçalho/totalizadores do WPD (convênio OU remessa
    com termo-lixo). "0"/"0.0" valem apenas como valor EXATO da célula — como
    substring, o "0" descartaria toda remessa contendo o dígito (regressão de
    09/09/2026: 138055 e todas as 150xxx eram perdidas aqui)."""
    termos_lixo = [
        "PARÂMETROS", "PERÍODO DE ENTREGA", "APENAS DA UNIDADE", "REMESSAS:",
        "TODOS OS CONVÊNIOS", "TODAS REMESSA", "TOTALIZA OS PAGAMENTOS", "TOTAL", "GERAL",
        "ABERTO:", "CONVÊNIO:", "L.MARTINS", "REMESSA", "(VAZIAS)", "NAN",
        "SOC. BENEFICENTE", "ISRAELITA", "BENEFICENTE"
    ]
    padrao_lixo = '|'.join(re.escape(t) for t in termos_lixo)
    padrao_zero = r'^(?:0|0\.0)$'
    return df_wpd[
        (~df_wpd["Convênio"].str.upper().str.contains(padrao_lixo, na=False)) &
        (~df_wpd["Remessa"].str.upper().str.contains(padrao_lixo, na=False)) &
        (~df_wpd["Convênio"].str.upper().str.contains(padrao_zero, na=False)) &
        (~df_wpd["Remessa"].str.upper().str.contains(padrao_zero, na=False)) &
        (df_wpd["Convênio"] != "") & (df_wpd["Convênio"] != "nan") &
        (df_wpd["Remessa"] != "") & (df_wpd["Remessa"] != "nan")
    ].copy()


def processar_fase_0_wpd(xls_wpd: str, xlsx_wpd_limpo: str):
    """
    Processa WPD-26: extrai, limpa e salva.
    Retorna o DataFrame processado.
    """
    print("\n" + "=" * 60)
    print("[FASE 0] Processando WPD-26...")
    print("=" * 60)

    df_wpd = pd.read_excel(xls_wpd, engine="xlrd", skiprows=4, dtype=str)
    df_wpd.columns = df_wpd.columns.str.strip()

    colunas_wpd = [
        "Remessa", "Protocolo", "Emissão", "Vencimento", "Entrega", "Baixa",
        "Nota Fiscal", "Convênio", "Faturado", "Valor Pago", "Valor ISS",
        "Vlr Guia", "% Pré-glosa", "Valor Glosa", "% Glosa", "Atraso", "Faturas"
    ]
    colunas_faltantes = [col for col in colunas_wpd if col not in df_wpd.columns]
    if colunas_faltantes:
        raise KeyError(f"Colunas faltantes no WPD-26: {colunas_faltantes}")

    df_wpd = df_wpd[colunas_wpd].copy()
    df_wpd = df_wpd.dropna(subset=["Remessa", "Convênio"], how="any")
    df_wpd["Convênio"] = df_wpd["Convênio"].astype(str).str.strip()
    df_wpd["Remessa"] = df_wpd["Remessa"].astype(str).str.strip()

    df_wpd_filtrado = _filtrar_linhas_lixo(df_wpd)

    colunas_datas = ["Emissão", "Vencimento", "Entrega"]
    for col in colunas_datas:
        df_wpd_filtrado[col] = df_wpd_filtrado[col].apply(extrair_data)
    df_wpd_filtrado["Baixa"] = df_wpd_filtrado["Baixa"].apply(converter_baixa)

    colunas_valores = ["Faturado", "Valor Pago", "Valor ISS", "Vlr Guia", "% Pré-glosa", "Valor Glosa"]
    for col in colunas_valores:
        df_wpd_filtrado[col] = df_wpd_filtrado[col].apply(limpar_numero)

    df_wpd_filtrado["% Glosa"] = df_wpd_filtrado.apply(
        lambda row: row["Valor Glosa"] / row["Faturado"] if row["Faturado"] != 0 else 0.0, axis=1
    )
    df_wpd_filtrado["% Pré-glosa"] = df_wpd_filtrado["% Pré-glosa"].apply(lambda x: x / 100.0 if x > 1 else x)
    df_wpd_filtrado["Atraso"] = df_wpd_filtrado["Atraso"].apply(converter_inteiro)
    df_wpd_filtrado["Faturas"] = df_wpd_filtrado["Faturas"].apply(converter_inteiro)

    with pd.ExcelWriter(xlsx_wpd_limpo, engine="openpyxl") as writer:
        df_wpd_filtrado.to_excel(writer, sheet_name="WPD-26 Extraído", index=False)
        ws = writer.sheets["WPD-26 Extraído"]
        ws.sheet_view.showGridLines = False
        for r_idx, row in enumerate(ws.iter_rows(values_only=False), start=1):
            for cell in row:
                cell.border = Border(left=Side(style="thin"), right=Side(style="thin"),
                                     top=Side(style="thin"), bottom=Side(style="thin"))
                cell.font = Font(name="Arial", size=10, bold=(r_idx == 1))
        for col_idx in range(1, ws.max_column + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 15

    print(f"[FASE 0 OK] WPD-26 processado: {xlsx_wpd_limpo}")
    return df_wpd_filtrado


# ==============================================================================
# PROCESSAMENTO — FASE 1: NÃO IDENTIFICADO
# ==============================================================================
def processar_fase_1_nao_identificado(xls_nao_identificado: str, xlsx_nao_identificado_limpo: str):
    """
    Processa Não_Identificado: extrai, limpa e salva.
    Retorna o DataFrame processado.
    """
    print("\n" + "=" * 60)
    print("[FASE 1] Processando Não_Identificado...")
    print("=" * 60)

    df_ni = pd.read_excel(xls_nao_identificado, engine="xlrd", skiprows=4)
    df_ni.columns = df_ni.columns.str.strip()

    print(f"[DEBUG] Colunas encontradas no arquivo ({len(df_ni.columns)}):")
    for i, c in enumerate(df_ni.columns):
        print(f"  [{i}] = {repr(c)}")

    colunas_ni = [
        "Convênio", "Data", "Depósito Liq.", "Depósito Bruto", "Quitação",
        "Não Identificado", "Acordos", "Glosa Aceita", "Não Identificado Real"
    ]
    colunas_faltantes = [col for col in colunas_ni if col not in df_ni.columns]
    if colunas_faltantes:
        raise KeyError(f"Colunas faltantes no Não_Identificado: {colunas_faltantes}")

    df_ni = df_ni[colunas_ni].copy()
    df_ni["Convênio"] = df_ni["Convênio"].astype(str).str.strip()
    df_ni_limpo = df_ni[
        (~df_ni["Convênio"].str.contains("TOTAL DO CONVÊNIO", na=False)) &
        (~df_ni["Convênio"].str.contains("TOTAL GERAL", na=False)) &
        (~df_ni["Convênio"].str.contains("SALDO ANT.", na=False)) &
        (~df_ni["Convênio"].str.contains("SALDO POS.", na=False)) &
        (~df_ni["Data"].astype(str).str.contains("SALDO ANT.", na=False)) &
        (df_ni["Convênio"] != "") & (df_ni["Convênio"] != "nan") &
        (df_ni["Data"].notna()) & (df_ni["Data"].astype(str).str.strip() != "")
    ].copy()
    df_ni_limpo["Data"] = pd.to_datetime(df_ni_limpo["Data"], errors="coerce", dayfirst=True).dt.date
    colunas_financeiras = colunas_ni[2:]
    for col in colunas_financeiras:
        df_ni_limpo[col] = df_ni_limpo[col].apply(limpar_numero)
    df_ni_final = df_ni_limpo[df_ni_limpo[colunas_financeiras].sum(axis=1) != 0.0].copy()

    with pd.ExcelWriter(xlsx_nao_identificado_limpo, engine="openpyxl") as writer:
        df_ni_final.to_excel(writer, sheet_name="Dados Extraídos", index=False)
        ws = writer.sheets["Dados Extraídos"]
        ws.sheet_view.showGridLines = False
        for r_idx, row in enumerate(ws.iter_rows(values_only=False), start=1):
            for cell in row:
                cell.border = Border(left=Side(style="thin"), right=Side(style="thin"),
                                     top=Side(style="thin"), bottom=Side(style="thin"))
                cell.font = Font(name="Arial", size=10, bold=(r_idx == 1))
        for col_idx in range(1, ws.max_column + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 15

    print(f"[FASE 1 OK] Não_Identificado processado: {xlsx_nao_identificado_limpo}")
    return df_ni_final


# ==============================================================================
# ANEXO DE NOVAS EMISSÕES À ABA BD1
# ==============================================================================
def _normalizar_remessa(valor) -> str:
    """
    Normaliza a remessa para comparação: o Excel COM devolve números como
    117129.0, o WPD os traz como '117129' — ambos viram '117129'.
    """
    if isinstance(valor, float):
        return str(int(valor)) if valor.is_integer() else str(valor)
    if isinstance(valor, int):
        return str(valor)
    return str(valor).strip()


def identificar_linhas_novas_bd1(df_wpd: pd.DataFrame, remessas_existentes: set) -> pd.DataFrame:
    """
    Retorna as linhas do WPD cuja Remessa ainda não existe na BD1,
    ordenadas por Emissão (para anexar ao fim mantendo a ordem histórica).
    """
    df = df_wpd.copy()
    df["Remessa"] = df["Remessa"].map(_normalizar_remessa)
    novas = df[~df["Remessa"].isin(remessas_existentes)].copy()
    return novas.sort_values("Emissão").reset_index(drop=True)


# ==============================================================================
# PROCESSAMENTO — FASES 2, 3 E 4: INTEGRAÇÃO COM O HIAS VIA EXCEL
# ==============================================================================
def processar_fases_2_3_4_hias(
        xlsx_nao_identificado_limpo: str,
        xlsx_hias_base: str,
        xlsx_hias_final: str,
        pasta_raiz: str,
        pasta_saida: str,
        xlsx_wpd_limpo: str,
):
    """Executa a integração Excel em subprocesso isolado — editor cirúrgico do
    .xlsx (integração por XML) com crash seguro."""
    payload = json.dumps({
        "limpo": xlsx_nao_identificado_limpo, "base": xlsx_hias_base,
        "final": xlsx_hias_final, "raiz": pasta_raiz,
        "saida": pasta_saida, "wpd": xlsx_wpd_limpo,
    })
    proc = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "integracao_runner.py"), payload],
        capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    if proc.returncode != 0:
        raise RuntimeError(f"Integração Excel falhou (código {proc.returncode})")


# ==============================================================================
# ORQUESTRADOR PRINCIPAL
# ==============================================================================
def executar_processo_completo(pasta_raiz: str = None):
    """
    Orquestra todo o fluxo: Fase 0 → Fase 1 → Fases 2-4.
    Se pasta_raiz for None, detecta automaticamente.

    Retorna (sucesso: bool, mensagem: str).
    """
    if pasta_raiz is None:
        pasta_raiz = obter_pasta_raiz()

    pasta_relatorios = os.path.join(pasta_raiz, "relatórios")
    pasta_saida = os.path.join(pasta_raiz, "saída")
    pasta_erros = os.path.join(pasta_raiz, "logo de erro")
    garantir_pastas(pasta_raiz)

    # Arquivos de entrada
    xls_wpd = encontrar_arquivo_entrada(pasta_raiz, "WPD-26.xls")
    xls_nao_identificado = encontrar_arquivo_entrada(pasta_raiz, "Não_Identificado.xls")
    xlsx_hias_base = encontrar_arquivo_entrada(pasta_raiz, "Posição Financeira Hias.xlsx")

    # Arquivos de saída
    xlsx_wpd_limpo = os.path.join(pasta_saida, "WPD-26_Extraido.xlsx")
    xlsx_nao_identificado_limpo = os.path.join(pasta_saida, "Não_Identificado_Extraido.xlsx")
    data_hoje = datetime.now().strftime("%d.%m.%y")
    xlsx_hias_final = os.path.join(pasta_saida, f"Posição Financeira Hias_{data_hoje}.xlsx")

    print("🧹 Verificando arquivos de execuções anteriores...")

    # Fase 0: WPD-26
    df_wpd = processar_fase_0_wpd(xls_wpd, xlsx_wpd_limpo)

    # Fase 1: Não Identificado
    df_ni = processar_fase_1_nao_identificado(xls_nao_identificado, xlsx_nao_identificado_limpo)

    # Fases 2-4: Integração Hias
    processar_fases_2_3_4_hias(
        xlsx_nao_identificado_limpo, xlsx_hias_base, xlsx_hias_final,
        pasta_raiz, pasta_saida, xlsx_wpd_limpo
    )

    # Resumo final
    gerar_resumo(df_ni, df_wpd, xlsx_wpd_limpo, xlsx_nao_identificado_limpo)

    return True, xlsx_hias_final
