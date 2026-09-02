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
from datetime import datetime

import pandas as pd
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter
import win32com.client as win32
import pythoncom


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
    """Cria pastas de saída e erros se não existirem."""
    os.makedirs(os.path.join(pasta_raiz, "saída"), exist_ok=True)
    os.makedirs(os.path.join(pasta_raiz, "logo de erro"), exist_ok=True)


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


def salvar_log_erro(pasta_erros: str, exception: Exception):
    """Salva o log de erro com rotação (últimos 5 logs preservados)."""
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    log_arquivo = os.path.join(pasta_erros, f"erro_{timestamp}.txt")

    with open(log_arquivo, "w", encoding="utf-8") as f:
        f.write("=== LOG DE ERRO ===\n")
        f.write(f"Data/Hora: {now.strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write(f"Tipo: {type(exception).__name__}\n")
        f.write(f"Mensagem: {str(exception)}\n\n")
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

    termos_lixo = [
        "PARÂMETROS", "PERÍODO DE ENTREGA", "APENAS DA UNIDADE", "REMESSAS:",
        "TODOS OS CONVÊNIOS", "TODAS REMESSA", "TOTALIZA OS PAGAMENTOS", "TOTAL", "GERAL",
        "ABERTO:", "CONVÊNIO:", "L.MARTINS", "REMESSA", "(VAZIAS)", "NAN", "0.0", "0",
        "SOC. BENEFICENTE", "ISRAELITA", "BENEFICENTE"
    ]
    padrao_lixo = '|'.join(re.escape(t) for t in termos_lixo)
    df_wpd_filtrado = df_wpd[
        (~df_wpd["Convênio"].str.upper().str.contains(padrao_lixo, na=False)) &
        (~df_wpd["Remessa"].str.upper().str.contains(padrao_lixo, na=False)) &
        (df_wpd["Convênio"] != "") & (df_wpd["Convênio"] != "nan") &
        (df_wpd["Remessa"] != "") & (df_wpd["Remessa"] != "nan")
    ].copy()

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


def _anexar_emissoes_bd1(excel, workbook_hias, xlsx_wpd_limpo: str):
    """
    Anexa ao fim da aba BD1 as remessas do WPD-26 que ainda não existem lá
    (dedup por Remessa), herdando o estilo da última linha, aplicando as
    fórmulas das colunas R–V e redimensionando a tabela BD_1.
    """
    print("\n[FASE 3b] Anexando novas emissões à aba BD1...")
    ws_bd1 = workbook_hias.Sheets("BD1")

    # Remessas já presentes na BD1 (coluna A)
    fim_bd1 = ws_bd1.Cells(ws_bd1.Rows.Count, 1).End(-4162).Row
    if fim_bd1 < 2:
        print("   BD1 vazia — nada a deduplicar; anexando todo o WPD.")
        remessas_existentes = set()
    else:
        valores_col_a = ws_bd1.Range(ws_bd1.Cells(2, 1), ws_bd1.Cells(fim_bd1, 1)).Value
        if isinstance(valores_col_a, tuple):
            valores_col_a = [linha[0] for linha in valores_col_a]
        else:
            valores_col_a = [valores_col_a]
        remessas_existentes = {_normalizar_remessa(v) for v in valores_col_a if v is not None}

    # Linhas novas (dedup por Remessa, ordenadas por Emissão)
    df_wpd = pd.read_excel(xlsx_wpd_limpo)
    novas = identificar_linhas_novas_bd1(df_wpd, remessas_existentes)
    if novas.empty:
        print("   Nenhuma emissão nova para anexar à BD1.")
        return

    n = len(novas)
    linha_destino = fim_bd1 + 1
    print(f"   {n} emissões novas detectadas "
          f"(Remessa {novas['Remessa'].iloc[0]} ... {novas['Remessa'].iloc[-1]}).")

    # Estilo: herda da última linha existente da BD1 (bordas, fonte e formatos)
    ws_bd1.Range(ws_bd1.Cells(fim_bd1, 1), ws_bd1.Cells(fim_bd1, 22)).Copy()
    ws_bd1.Range(
        ws_bd1.Cells(linha_destino, 1), ws_bd1.Cells(linha_destino + n - 1, 22)
    ).PasteSpecial(Paste=-4122)  # xlPasteFormats
    excel.CutCopyMode = False

    # Valores das colunas A–Q (mesma ordem do WPD extraído)
    colunas_wpd = [
        "Remessa", "Protocolo", "Emissão", "Vencimento", "Entrega", "Baixa",
        "Nota Fiscal", "Convênio", "Faturado", "Valor Pago", "Valor ISS",
        "Vlr Guia", "% Pré-glosa", "Valor Glosa", "% Glosa", "Atraso", "Faturas"
    ]
    colunas_data = {"Emissão", "Vencimento", "Entrega", "Baixa"}
    matriz = []
    for _, linha in novas.iterrows():
        celulas = []
        for col in colunas_wpd:
            valor = linha[col]
            if pd.isna(valor):
                celulas.append(None)
            elif col == "Protocolo":
                try:
                    celulas.append(int(float(str(valor).strip())))
                except (TypeError, ValueError):
                    celulas.append(str(valor).strip())
            elif col in colunas_data:
                celulas.append(valor.to_pydatetime())
            else:
                celulas.append(valor)
        matriz.append(celulas)

    ws_bd1.Range(
        ws_bd1.Cells(linha_destino, 1), ws_bd1.Cells(linha_destino + n - 1, 17)
    ).Value = matriz

    # Fórmulas das colunas R–V (Atrasado, A vencer, Recurso, Recurso pago, Tipo de remessa).
    # Sintaxe EN via .Formula: funciona em qualquer Excel, independente do
    # separador de lista regional (o .FormulaLocal falha quando o Windows usa ';').
    # Escritas por coluna (matriz) em 5 chamadas COM, em vez de célula a célula.
    linhas = range(linha_destino, linha_destino + n)
    formulas_por_coluna = {
        18: [f'=SUMIFS(L{r},D{r},"<"&TODAY(),F{r},"")' for r in linhas],
        19: [f'=SUMIFS(L{r},D{r},">"&TODAY(),F{r},"")' for r in linhas],
        20: [f'=IF(RIGHT(A{r},3)="(R)",L{r},0)' for r in linhas],
        21: [f'=IF(T{r}=0,0,J{r})' for r in linhas],
        22: [f'=IF(RIGHT(A{r},3)="(R)","Recurso","Comum")' for r in linhas],
    }
    for col, formulas in formulas_por_coluna.items():
        ws_bd1.Range(
            ws_bd1.Cells(linha_destino, col), ws_bd1.Cells(linha_destino + n - 1, col)
        ).Formula = [[f] for f in formulas]

    # Redimensiona a tabela estruturada BD_1 para incluir as novas linhas
    for tabela in ws_bd1.ListObjects:
        if tabela.Name == "BD_1":
            tabela.Resize(ws_bd1.Range(f"A1:V{linha_destino + n - 1}"))
            print(f"   Tabela 'BD_1' redimensionada para A1:V{linha_destino + n - 1}.")

    print(f"   BD1 atualizada: linhas {linha_destino} a {linha_destino + n - 1} anexadas.")


def _normalizar_aba_a_quitar(excel, workbook_hias):
    """Normaliza a aba À Quitar antes de salvar o arquivo final.

    O bloco histórico da BD2 grava os nomes de convênio com largura fixa de 35
    caracteres ('BRADESCO SEGUROS' + espaços à direita); o bloco novo do Não
    Identificado grava sem os espaços. A pivot da aba À Quitar tratava cada
    grafia como um convênio diferente — abrindo DOIS botões para o mesmo
    convênio (um com as datas antigas, outro com as novas). Aqui:
      1. remove os espaços de todos os nomes de convênio na coluna A da BD2;
      2. atualiza a pivot (cache + tabela);
      3. recolhe os itens de convênio (ShowDetail=False) — os itens novos
         nascem expandidos quando a pivot é atualizada após a injeção.
    """
    ws_hias = workbook_hias.Sheets("BD2")
    fim = ws_hias.Cells(ws_hias.Rows.Count, 1).End(-4162).Row
    if fim < 2:
        return

    # 1) Remove espaços à esquerda/direita de todos os convênios (coluna A)
    valores = ws_hias.Range(ws_hias.Cells(2, 1), ws_hias.Cells(fim, 1)).Value
    linhas = list(valores) if isinstance(valores, tuple) else [[valores]]
    normalizados = []
    for linha in linhas:
        v = linha[0] if isinstance(linha, tuple) else linha
        normalizados.append([v.strip()] if isinstance(v, str) else [v])
    ws_hias.Range(ws_hias.Cells(2, 1), ws_hias.Cells(fim, 1)).Value = normalizados
    print("   Nomes de convênio da BD2 normalizados (sem espaços à direita).")

    # 2) Atualiza a pivot da aba À Quitar e recolhe os convênios
    try:
        ws_a_quitar = workbook_hias.Sheets("À Quitar")
    except Exception:
        return  # aba inexistente — nada a normalizar

    for pt in ws_a_quitar.PivotTables():
        try:
            pt.PivotCache().Refresh()
        except Exception:
            pass  # cache já atualizado — o RefreshTable abaixo cobre
        pt.RefreshTable()

        try:
            campo = pt.PivotFields("Convênio")
        except Exception:
            continue
        for i in range(1, campo.PivotItems().Count + 1):
            item = campo.PivotItems(i)
            try:
                item.ShowDetail = False
            except Exception:
                pass  # item sem dados ou travado pela timeline — nada a recolher
    print("   Aba À Quitar normalizada: um item por convênio, todos recolhidos.")


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
    """
    Integração Excel COM:
      Fase 2: Abre Excel e prepara ambiente
      Fase 3: Injeta dados processados na aba BD2
      Fase 4: Salva arquivo final com formatação Brasil
    """
    pythoncom.CoInitialize()
    try:
        print("\n" + "=" * 60)
        print("[FASE 2] Integrando dados ao Hias via Excel...")
        print("=" * 60)

        # Backup automático antes de modificar
        print("📦 Criando backup de segurança do Hias base...")
        caminho_backup = criar_backup_hias(xlsx_hias_base, pasta_saida)
        print(f"   Backup salvo em: {os.path.basename(caminho_backup)}")

        excel = win32.gencache.EnsureDispatch('Excel.Application')
        excel.Visible = False
        excel.DisplayAlerts = False

        workbook_limpo = None
        workbook_hias = None

        try:
            workbook_limpo = excel.Workbooks.Open(xlsx_nao_identificado_limpo)
            workbook_hias = excel.Workbooks.Open(xlsx_hias_base)

            nomes_abas = [sheet.Name for sheet in workbook_hias.Sheets]
            if "BD2" not in nomes_abas:
                raise KeyError(
                    f"Aba 'BD2' não encontrada no arquivo Hias.\n"
                    f"Abas disponíveis: {nomes_abas}\n"
                    f"Arquivo: {xlsx_hias_base}"
                )

            excel.ScreenUpdating = False
            excel.EnableEvents = False
            excel.Calculation = -4135  # xlCalculationManual

            ws_limpo = workbook_limpo.Sheets("Dados Extraídos")
            ws_hias = workbook_hias.Sheets("BD2")

            fim_dados_limpos = ws_limpo.Cells(ws_limpo.Rows.Count, 1).End(-4162).Row
            fim_atual_hias = ws_hias.Cells(ws_hias.Rows.Count, 1).End(-4162).Row
            linha_corte = 806

            if fim_atual_hias >= linha_corte:
                print(f"Deletando bloco de linhas obsoleto de {linha_corte} até {fim_atual_hias}")
                ws_hias.Rows(f"{linha_corte}:{fim_atual_hias}").Delete()

            print("[FASE 3] Clonando e injetando layout...")
            if fim_dados_limpos >= 2:
                linha_final_inserida = linha_corte + (fim_dados_limpos - 2)

                origem_intervalo = ws_limpo.Range(ws_limpo.Cells(2, 1), ws_limpo.Cells(fim_dados_limpos, 9))
                origem_intervalo.Copy()
                destino_intervalo = ws_hias.Cells(linha_corte, 1)
                destino_intervalo.PasteSpecial(Paste=-4163)  # xlPasteValues
                destino_intervalo.PasteSpecial(Paste=-4122)  # xlPasteFormats
                excel.CutCopyMode = False

                # Formata coluna de data (B) como dd/mm/aaaa
                coluna_data = ws_hias.Range(
                    ws_hias.Cells(linha_corte, 2), ws_hias.Cells(linha_final_inserida, 2)
                )
                coluna_data.NumberFormatLocal = "dd/mm/aaaa"

                # Formata colunas financeiras (C-I) como moeda Brasil sem R$
                coluna_financeira = ws_hias.Range(
                    ws_hias.Cells(linha_corte, 3), ws_hias.Cells(linha_final_inserida, 9)
                )
                coluna_financeira.NumberFormat = "#.##0,00"

                if ws_hias.ListObjects.Count > 0:
                    for tabela in ws_hias.ListObjects:
                        print(f"Redimensionando Tabela '{tabela.Name}'...")
                        tabela.Resize(ws_hias.Range(f"A1:I{linha_final_inserida}"))
                print(f"Intervalo (A806:I{linha_final_inserida}) integrado.")
                print("Colunas financeiras formatadas como moeda Brasil (#.##0,00).")
            else:
                print("Nenhum dado novo para processar.")

            # Anexa as novas emissões do WPD-26 à aba BD1 (antes de salvar)
            _anexar_emissoes_bd1(excel, workbook_hias, xlsx_wpd_limpo)

            # Normaliza a aba À Quitar: um item por convênio e tudo recolhido
            _normalizar_aba_a_quitar(excel, workbook_hias)

            print(f"\n[FASE 4] Salvando: {xlsx_hias_final}")
            workbook_hias.SaveAs(xlsx_hias_final)

        finally:
            excel.ScreenUpdating = True
            excel.EnableEvents = True
            excel.Calculation = -4105
            if workbook_limpo is not None:
                workbook_limpo.Close(SaveChanges=False)
            if workbook_hias is not None:
                workbook_hias.Close(SaveChanges=False)
            excel.Quit()

        print("\n" + "=" * 60)
        print("[FLUXO CONCLUÍDO COM 100% DE SUCESSO]")
        print("=" * 60)

        dashboard_path = os.path.join(pasta_raiz, "dashboard.html")
        if os.path.exists(dashboard_path):
            import webbrowser
            webbrowser.open(dashboard_path)
            print("\nDashboard aberto no navegador.")

    finally:
        pythoncom.CoUninitialize()


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

    # Mata instâncias residuais do Excel
    print("🧹 Verificando e liberando arquivos de execuções anteriores...")
    try:
        subprocess.run(
            ["taskkill", "/f", "/im", "EXCEL.EXE"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print("   OK — processos do Excel liberados.\n")
    except Exception:
        pass

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
