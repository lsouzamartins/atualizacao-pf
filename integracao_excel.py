"""==============================================================================
INTEGRAÇÃO CIRÚRGICA DO EXCEL — ATUALIZAÇÃO PF · NUVEM
==============================================================================
Substitui o motor COM (Windows) e o motor UNO (reprovado no spike — R24):
edita apenas as partes XML de BD1/BD2 dentro do .xlsx (que é um zip),
preservando pivôs/slicers/timelines byte a byte, e marca as 4 pivôs com
refreshOnLoad="1" para o Excel atualizá-las ao abrir o arquivo.

O arquivo Hias NUNCA é salvo pelo openpyxl (isso destruiria pivôs/slicers —
ver notas-spike-libreoffice.md). O openpyxl aqui só LÊ (gate de validação).

Referência da anatomia do arquivo: .superpowers/sdd/2026-09-01-atualizacao-pf-nuvem/task-4-investigacao.md

Contrato público (consumido por integracao_runner.py):
    processar_fases_2_3_4_hias(xlsx_nao_identificado_limpo, xlsx_hias_base,
                               xlsx_hias_final, pasta_raiz, pasta_saida,
                               xlsx_wpd_limpo) -> None
=============================================================================="""
import numbers
import os
import re
import shutil
import zipfile
from datetime import date, datetime, timezone
from xml.etree import ElementTree as ET

import pandas as pd

# ------------------------------------------------------------------------------
# Constantes da anatomia do arquivo Hias (task-4-investigacao.md)
# ------------------------------------------------------------------------------
LINHA_CORTE_BD2 = 806          # linhas >= 806 da BD2 são o bloco obsoleto
SERIAL_EPOCA = date(1899, 12, 30)  # serial do Excel = dias desde 1899-12-30
_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

# Sem isto, o ElementTree serializa o namespace padrão como prefixo "ns0:".
ET.register_namespace("", _NS)

COLUNAS_WPD = ["Remessa", "Protocolo", "Emissão", "Vencimento", "Entrega", "Baixa",
               "Nota Fiscal", "Convênio", "Faturado", "Valor Pago", "Valor ISS",
               "Vlr Guia", "% Pré-glosa", "Valor Glosa", "% Glosa", "Atraso", "Faturas"]
COLUNAS_DATA = {"Emissão", "Vencimento", "Entrega", "Baixa"}

# Partes que o motor pode reescrever (as demais são copiadas byte a byte).
NOMES_PARTES = [
    "xl/worksheets/sheet5.xml",           # BD1
    "xl/worksheets/sheet6.xml",           # BD2
    "xl/sharedStrings.xml",
    "xl/tables/table1.xml",               # tabela BD_1 (BD1)
    "xl/tables/table2.xml",               # tabela Tabela1 (BD2)
    "xl/workbook.xml",
    "xl/pivotTables/pivotTable1.xml",
    "xl/pivotTables/pivotTable2.xml",
    "xl/pivotTables/pivotTable3.xml",
    "xl/pivotTables/pivotTable4.xml",
    "xl/pivotCache/pivotCacheDefinition1.xml",
    "docProps/core.xml",
]

_RE_LINHA = re.compile(r'<row r="(\d+)"[^>]*>.*?</row>', re.DOTALL)


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
# Utilitários de XML
# ==============================================================================
def _escapar_xml(texto: str) -> str:
    """Escapa os caracteres reservados do XML em conteúdo de elemento
    (fórmulas e valores inline). Aspas ficam literais — como o Excel grava."""
    return (texto.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _celula(ref: str, estilo: int, valor=None, tipo: str | None = None) -> str:
    """Uma <c> de string compartilhada (tipo="s"), inline (tipo="str") ou numérica."""
    if valor is None:
        return f'<c r="{ref}" s="{estilo}"/>'
    if tipo == "s":
        return f'<c r="{ref}" s="{estilo}" t="s"><v>{valor}</v></c>'
    if tipo == "str":
        return f'<c r="{ref}" s="{estilo}" t="str"><v>{_escapar_xml(str(valor))}</v></c>'
    return f'<c r="{ref}" s="{estilo}"><v>{_escapar_xml(str(valor))}</v></c>'


def _celula_formula(ref: str, estilo: int, formula: str,
                    valor_cache: str | None = None, tipo: str | None = None) -> str:
    """Uma <c> com <f>. Coluna V leva cache inline (obrigatório para t="str")."""
    abertura = f'<c r="{ref}" s="{estilo}"' + (' t="str"' if tipo == "str" else "") + ">"
    fim = f"<v>{_escapar_xml(valor_cache)}</v>" if valor_cache is not None else ""
    return abertura + f"<f>{_escapar_xml(formula)}</f>" + fim + "</c>"


def _numero(valor) -> str | None:
    """Converte número para a forma canônica do XML (sem .0 espúrio)."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, numbers.Real):
        return str(int(valor)) if float(valor).is_integer() else repr(float(valor))
    return str(valor)


def _substituir_ou_falhar(padrao, novo, texto, contexto):
    """Aplica re.sub e falha alto se o padrão não casar — evita gravar saída silenciosamente errada."""
    resultado, n = re.subn(padrao, novo, texto, count=1)
    if n == 0:
        raise RuntimeError(
            f"Padrão não encontrado em {contexto} — abortando para não gravar uma saída incorreta."
        )
    return resultado


# ==============================================================================
# sharedStrings: leitura preservando a ordem dos <si>; acréscimos no fim
# ==============================================================================
class _StringsCompartilhadas:
    """Lê/reescreve xl/sharedStrings.xml sem reordenar os <si> existentes."""

    def __init__(self, texto: str):
        texto = texto.lstrip("\ufeff")
        if texto.startswith("<?xml"):
            texto = texto[texto.index("?>") + 2:]
        self._raiz = ET.fromstring(texto.encode("utf-8"))
        self._textos = []
        for si in self._raiz.findall(f"{{{_NS}}}si"):
            self._textos.append(self._texto_de_si(si))

    @staticmethod
    def _texto_de_si(si) -> str:
        return "".join(t.text or "" for t in si.iter(f"{{{_NS}}}t"))

    def obter_indice(self, texto: str) -> int:
        """Índice (base 0) de `texto`, acrescentando um <si> novo ao fim se preciso."""
        if texto not in self._textos:
            si = ET.SubElement(self._raiz, f"{{{_NS}}}si")
            t = ET.SubElement(si, f"{{{_NS}}}t")
            t.text = texto
            self._textos.append(texto)
        return self._textos.index(texto)

    def texto_de_indice(self, indice: int) -> str:
        return self._textos[indice]

    def para_xml(self, novas_celulas: int = 0) -> str:
        """count cresce com as células t="s" novas; uniqueCount = si únicos."""
        self._raiz.set("count", str(int(self._raiz.get("count", "0")) + novas_celulas))
        self._raiz.set("uniqueCount", str(len(set(self._textos))))
        return _DECL + ET.tostring(self._raiz, encoding="unicode")


# ==============================================================================
# Lógica herdada do core.py (verbatim — ver "G:\Atualização PF\core.py")
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


def _linhas_novas_originais(df_wpd: pd.DataFrame, remessas_existentes: set) -> pd.DataFrame:
    """Mesma filtragem de identificar_linhas_novas_bd1, mas preservando o valor
    original da Remessa (o COM gravava números como células numéricas)."""
    df = df_wpd.copy()
    df["__rem_norm"] = df["Remessa"].map(_normalizar_remessa)
    novas = df[~df["__rem_norm"].isin(remessas_existentes)].copy()
    novas = novas.sort_values("Emissão").reset_index(drop=True)
    return novas.drop(columns=["__rem_norm"])


# ==============================================================================
# Leitura das partes
# ==============================================================================
def _partes_de(caminho: str) -> dict[str, str]:
    with zipfile.ZipFile(caminho, "r") as z:
        nomes = set(z.namelist())
        partes = {n: z.read(n).decode("utf-8") for n in NOMES_PARTES if n in nomes}
        # o Excel pode renumerar as partes de pivot cache ao salvar (caso real
        # de 02/09/2026: definition1↔definition2) — inclui todas as existentes
        # para a seleção por conteúdo em _parte_cache_bd2
        partes.update({n: z.read(n).decode("utf-8") for n in nomes
                       if re.fullmatch(r"xl/pivotCache/pivotCacheDefinition\d+\.xml", n)})
        return partes


def _ultima_linha(xml: str) -> int:
    numeros = [int(m.group(1)) for m in _RE_LINHA.finditer(xml)]
    return max(numeros) if numeros else 1


# ==============================================================================
# BD1 — remessas existentes e anexo das novas (espelha _anexar_emissoes_bd1)
# ==============================================================================
def _remessas_bd1(xml_bd1: str, strings) -> set:
    """Set das remessas já presentes na coluna A da BD1 (normalizadas)."""
    remessas = set()
    for m in re.finditer(r'<c r="A\d+"([^>]*)>(?:<v>(.*?)</v>)?</c>', xml_bd1):
        attrs, v = m.group(1), m.group(2)
        if 't="s"' in attrs and v is not None:
            remessas.add(_normalizar_remessa(strings.texto_de_indice(int(v))))
        elif 't="str"' in attrs and v is not None:
            remessas.add(_normalizar_remessa(v))
        elif v is not None:
            try:
                remessas.add(_normalizar_remessa(float(v)))
            except ValueError:
                remessas.add(_normalizar_remessa(int(v)))
    return remessas


def _converter_linha_wpd(linha) -> dict:
    """Converte uma linha do WPD para o formato das células da BD1
    (espelha _anexar_emissoes_bd1: NaN->None, Protocolo->int/str, datas)."""
    dados = {}
    for col in COLUNAS_WPD:
        v = linha[col]
        if pd.isna(v) or (isinstance(v, str) and v.strip() == ""):
            dados[col] = None
        elif col in COLUNAS_DATA:
            dados[col] = pd.Timestamp(v).to_pydatetime().date()
        elif col == "Protocolo":
            try:
                dados[col] = int(float(str(v).strip()))
            except (ValueError, TypeError):
                dados[col] = str(v).strip()
        else:
            dados[col] = v
    return dados


def _linha_bd1_nova(num_linha: int, dados: dict, strings) -> tuple[str, int]:
    """Uma <row> nova da BD1 com os estilos da última linha existente
    (mapa de estilos da investigação) e fórmulas R–V sem grupo compartilhado.
    Retorna (xml_da_linha, nº de células t="s" novas)."""
    refs = 0
    remessa = dados["Remessa"]
    recurso = str(remessa).strip().endswith("(R)")
    if pd.api.types.is_number(remessa):
        numero = int(remessa) if float(remessa).is_integer() else float(remessa)
        cel_a = _celula(f"A{num_linha}", 36, _numero(numero))
    else:
        refs += 1
        cel_a = _celula(f"A{num_linha}", 36, str(strings.obter_indice(str(remessa))), tipo="s")
    protocolo = dados["Protocolo"]
    cel_b = (_celula(f"B{num_linha}", 45, protocolo, tipo="str")
             if isinstance(protocolo, str)
             else _celula(f"B{num_linha}", 45, _numero(protocolo)))
    convenio = dados["Convênio"]
    refs += 1
    cel_h = _celula(f"H{num_linha}", 14,
                    str(strings.obter_indice("" if convenio is None else str(convenio))), tipo="s")

    def data_serial(v):
        return None if v is None else (v - SERIAL_EPOCA).days

    cels = [cel_a, cel_b,
            _celula(f"C{num_linha}", 46, _numero(data_serial(dados["Emissão"]))),
            _celula(f"D{num_linha}", 46, _numero(data_serial(dados["Vencimento"]))),
            _celula(f"E{num_linha}", 46, _numero(data_serial(dados["Entrega"]))),
            _celula(f"F{num_linha}", 57 if dados["Baixa"] is None else 46,
                    _numero(data_serial(dados["Baixa"]))),
            _celula(f"G{num_linha}", 14, None),
            cel_h,
            _celula(f"I{num_linha}", 15, _numero(dados["Faturado"])),
            _celula(f"J{num_linha}", 15, _numero(dados["Valor Pago"])),
            _celula(f"K{num_linha}", 15, _numero(dados["Valor ISS"])),
            _celula(f"L{num_linha}", 15, _numero(dados["Vlr Guia"])),
            _celula(f"M{num_linha}", 38, _numero(dados["% Pré-glosa"])),
            _celula(f"N{num_linha}", 15, _numero(dados["Valor Glosa"])),
            _celula(f"O{num_linha}", 38, _numero(dados["% Glosa"])),
            _celula(f"P{num_linha}", 39, _numero(dados["Atraso"])),
            _celula(f"Q{num_linha}", 39, _numero(dados["Faturas"])),
            _celula_formula(f"R{num_linha}", 41,
                            f'=SUMIFS(L{num_linha},D{num_linha},"<"&TODAY(),F{num_linha},"")'),
            _celula_formula(f"S{num_linha}", 41,
                            f'=SUMIFS(L{num_linha},D{num_linha},">"&TODAY(),F{num_linha},"")'),
            _celula_formula(f"T{num_linha}", 41,
                            f'=IF(RIGHT(A{num_linha},3)="(R)",L{num_linha},0)'),
            _celula_formula(f"U{num_linha}", 41,
                            f'=IF(T{num_linha}=0,0,J{num_linha})'),
            _celula_formula(f"V{num_linha}", 43,
                            f'=IF(RIGHT(A{num_linha},3)="(R)","Recurso","Comum")',
                            valor_cache="Recurso" if recurso else "Comum", tipo="str"),
            ]
    return f'<row r="{num_linha}">{"".join(cels)}</row>', refs


def _editar_bd1(xml_bd1: str, novas: pd.DataFrame, strings) -> tuple[str, int, int] | None:
    """Anexa as remessas novas antes de </sheetData> e atualiza a dimension.
    Retorna (xml_novo, fim_novo, células t="s" novas) ou None se nada mudou."""
    if novas is None or len(novas) == 0:
        return None
    fim = _ultima_linha(xml_bd1)
    linhas_xml, refs = [], 0
    for i, (_, linha) in enumerate(novas.iterrows()):
        dados = _converter_linha_wpd(linha)
        xml_linha, n = _linha_bd1_nova(fim + 1 + i, dados, strings)
        linhas_xml.append(xml_linha)
        refs += n
    bloco = "".join(linhas_xml)
    idx = xml_bd1.rfind("</sheetData>")
    novo = xml_bd1[:idx] + bloco + xml_bd1[idx:]
    fim_novo = fim + len(novas)
    novo = _substituir_ou_falhar(
        r'<dimension ref="A1:V(\d+)"/>',
        f'<dimension ref="A1:V{fim_novo}"/>', novo, "dimension da BD1")
    return novo, fim_novo, refs


# ==============================================================================
# BD2 — bloco obsoleto, normalização da coluna A e bloco novo
# ==============================================================================
def _bloco_bd2(xlsx_limpo: str) -> list[dict] | None:
    """Lê as colunas A–I do 'Não Identificado limpo' a partir da linha 2
    (equivale ao End(xlUp) na coluna A do motor COM)."""
    df = pd.read_excel(xlsx_limpo, sheet_name=0, header=None)
    col_a = df.iloc[:, 0]
    ultima = col_a.last_valid_index()
    if ultima is None or ultima < 1:
        return None
    bloco = []
    for i in range(1, ultima + 1):
        linha = df.iloc[i, 0:9]
        conv = linha.iloc[0]
        convenio = "" if pd.isna(conv) else str(conv).strip()  # sem preenchimento de 35 chars
        data_v = linha.iloc[1]
        if pd.isna(data_v):
            continue  # linha sem data não entra no bloco
        valores = [None if pd.isna(v) else float(v) for v in linha.iloc[2:9]]
        bloco.append({"convenio": convenio,
                      "data": (pd.Timestamp(data_v).date() - SERIAL_EPOCA).days,
                      "valores": valores})
    return bloco if bloco else None


def _linha_bd2(num_linha: int, convenio: str, data_serial: int,
               valores: list, strings) -> str:
    """Uma <row> da BD2: A string s=34, B data s=35, C–I números s=53, J =1 s=17
    (J=1 mantém a formatação condicional $J2=1/$J2=2 — recomendação da investigação)."""
    cels = [_celula(f"A{num_linha}", 34, str(strings.obter_indice(convenio)), tipo="s"),
            _celula(f"B{num_linha}", 35, str(data_serial))]
    for i, v in enumerate(valores):  # C..I
        cels.append(_celula(f"{chr(ord('C') + i)}{num_linha}", 53, _numero(v)))
    cels.append(_celula(f"J{num_linha}", 17, "1"))
    return f'<row r="{num_linha}">{"".join(cels)}</row>'


def _editar_bd2(xml_bd2: str, bloco: list[dict] | None, strings) -> tuple[str | None, int | None, int]:
    """(1) deleta as linhas >= 806 (bloco obsoleto); (2) normaliza a coluna A
    (tira o preenchimento de espaços, sincronizando sharedStrings); (3) anexa o
    bloco novo a partir da linha 806; (4) atualiza a dimension.
    Retorna (xml_novo, fim_novo, células t="s" novas) ou (None, None, 0)."""
    fim_atual = _ultima_linha(xml_bd2)
    fim_util = min(fim_atual, LINHA_CORTE_BD2 - 1)
    mudou = False

    def _remover_obsoletas(m):
        nonlocal mudou
        if int(m.group(1)) >= LINHA_CORTE_BD2:
            mudou = True
            return ""
        return m.group(0)

    texto = re.sub(r'<row r="(\d+)"[^>]*>.*?</row>', _remover_obsoletas, xml_bd2, flags=re.DOTALL)

    def _normalizar_coluna_a(m):
        nonlocal mudou
        num = int(m.group(1))
        if not (2 <= num <= fim_util):
            return m.group(0)
        cel = re.search(r'<c r="A\d+"[^>]*?><v>(\d+)</v></c>', m.group(3))
        if not cel or 't="s"' not in cel.group(0):
            return m.group(0)
        original = strings.texto_de_indice(int(cel.group(1)))
        limpo = original.strip()
        if limpo == original:
            return m.group(0)
        novo = strings.obter_indice(limpo)
        cel_nova = cel.group(0).replace(f"<v>{cel.group(1)}</v>", f"<v>{novo}</v>")
        mudou = True
        return f'<row r="{num}"{m.group(2)}>{m.group(3).replace(cel.group(0), cel_nova, 1)}</row>'

    texto = re.sub(r'<row r="(\d+)"([^>]*)>(.*?)</row>', _normalizar_coluna_a, texto, flags=re.DOTALL)

    novas_celulas = 0
    if bloco:
        mudou = True
        linhas = "".join(_linha_bd2(LINHA_CORTE_BD2 + i, b["convenio"], b["data"],
                                    b["valores"], strings)
                         for i, b in enumerate(bloco))
        novas_celulas = len(bloco)
        idx = texto.rfind("</sheetData>")
        texto = texto[:idx] + linhas + texto[idx:]
        novo_fim = LINHA_CORTE_BD2 + len(bloco) - 1
    else:
        novo_fim = fim_util

    if not mudou:
        return None, None, 0
    texto = _substituir_ou_falhar(
        r'<dimension ref="A1:J(\d+)"/>',
        f'<dimension ref="A1:J{novo_fim}"/>', texto, "dimension da BD2")
    return texto, novo_fim, novas_celulas


# ==============================================================================
# Ajustes das partes auxiliares
# ==============================================================================
def _ajustar_tabela(xml: str, prefixo: str, novo_fim: int) -> str:
    """Atualiza ref/autoFilter de uma tabela (table1.xml: 'A1:V'; table2.xml: 'A1:I')."""
    return re.sub(rf'ref="{re.escape(prefixo)}(\d+)"',
                  lambda m: f'ref="{prefixo}{novo_fim}"', xml)


def _ajustar_cache1(xml: str, novo_fim: int) -> str:
    """Atualiza o ref do cache da BD2 (worksheetSource com ref="A1:I...")."""
    return _substituir_ou_falhar(
        r'(worksheetSource[^>]*?\bref="A1:I)(\d+)(")',
        lambda m: f'{m.group(1)}{novo_fim}{m.group(3)}', xml,
        "worksheetSource do cache da BD2")


def _parte_cache_bd2(partes: dict) -> str | None:
    """Nome da parte de pivot cache cuja fonte é a BD2 (worksheetSource com
    ref="A1:I..."). O Excel pode renumerar as partes ao salvar (caso real de
    02/09/2026: cacheDefinition 1↔2) — a seleção é pelo conteúdo, não pelo
    nome do arquivo."""
    for nome in sorted(partes):
        if re.fullmatch(r"xl/pivotCache/pivotCacheDefinition\d+\.xml", nome):
            if re.search(r'worksheetSource[^>]*\bref="A1:I\d+"', partes[nome]):
                return nome
    return None


def _marcar_refresh_on_load(xml: str) -> str:
    """Marca refreshOnLoad="1" na raiz de uma pivotTableDefinition
    (o Excel atualiza a pivô ao abrir; não pode duplicar o atributo)."""
    if "refreshOnLoad" in xml:
        raise ValueError("refreshOnLoad já presente — não deve duplicar")
    return re.sub(r'(<pivotTableDefinition\b[^>]*?)(/?>)',
                  r'\1 refreshOnLoad="1"\2', xml, count=1)


def _ajustar_workbook(xml: str, fim_bd1_novo: int | None, calc_completo: bool) -> str:
    """fullCalcOnLoad (recalcula BD1 ao abrir) e o nome definido _FilterDatabase da BD1."""
    if calc_completo and "fullCalcOnLoad" not in xml:
        xml = _substituir_ou_falhar(
            r'(<calcPr\b[^>]*?)(/?>)',
            r'\1 fullCalcOnLoad="1"\2', xml, "calcPr do workbook")
    if fim_bd1_novo is not None:
        xml = _substituir_ou_falhar(
            r"(definedName[^>]*>'BD1'!\$A\$1:\$V\$)(\d+)",
            lambda m: m.group(1) + str(fim_bd1_novo), xml,
            "definedName do workbook")
    return xml


def _ajustar_core(xml: str) -> str:
    """Atualiza o carimbo dcterms:modified do docProps/core.xml."""
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return re.sub(r"<dcterms:modified([^>]*)>[^<]*</dcterms:modified>",
                  lambda m: f"<dcterms:modified{m.group(1)}>{agora}</dcterms:modified>",
                  xml, count=1)


# ==============================================================================
# Gravação cirúrgica e gate de validação
# ==============================================================================
def _gravar_zip_cirurgico(caminho_origem: str, caminho_destino: str,
                          substituicoes: dict[str, str]) -> None:
    """Copia o zip parte por parte preservando ordem/metadados; as partes em
    `substituicoes` entram com o novo conteúdo. [Content_Types].xml e .rels
    NUNCA são tocados (nenhuma parte é criada ou removida)."""
    with zipfile.ZipFile(caminho_origem, "r") as zin, \
         zipfile.ZipFile(caminho_destino, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            dados = substituicoes.get(item.filename)
            if dados is None:
                dados = zin.read(item.filename)
            else:
                dados = dados.encode("utf-8")
            zout.writestr(item, dados)


def _validar_saida(caminho: str) -> None:
    """Gate leve: zip íntegro + openpyxl abre em modo LEITURA
    (o openpyxl jamais grava o Hias — só lê, respeitando a restrição global)."""
    ruim = zipfile.ZipFile(caminho).testzip()
    if ruim is not None:
        raise RuntimeError(f"Zip corrompido na parte {ruim}")
    from openpyxl import load_workbook  # import tardio: só o gate exige
    load_workbook(caminho, read_only=True)
    print("[GATE] Arquivo final validado (zip íntegro + openpyxl read-only OK).")


# ==============================================================================
# FLUXO PRINCIPAL — espelha as fases 2–4 do motor COM original
# ==============================================================================
def processar_fases_2_3_4_hias(xlsx_nao_identificado_limpo, xlsx_hias_base,
                               xlsx_hias_final, pasta_raiz, pasta_saida,
                               xlsx_wpd_limpo) -> None:
    """
    Integra os dados do dia no arquivo Hias sem tocar pivôs/slicers.

    pasta_raiz é mantida por compatibilidade com o contrato do runner
    (integracao_runner.py) — não é usada aqui.
    """
    backup = criar_backup_hias(xlsx_hias_base, pasta_saida)
    print(f"[FASE 2] Backup criado: {backup}")

    partes = _partes_de(xlsx_hias_base)
    strings = _StringsCompartilhadas(partes["xl/sharedStrings.xml"])

    substituicoes = {}
    novas_celulas = 0
    fim_bd1_novo = None
    houve_mudanca_bd1 = False

    # ---- FASE 3a: BD1 — anexa as remessas novas do WPD ----
    remessas_existentes = _remessas_bd1(partes["xl/worksheets/sheet5.xml"], strings)
    df_wpd = pd.read_excel(xlsx_wpd_limpo)
    novas = _linhas_novas_originais(df_wpd, remessas_existentes)
    if len(novas) == 0:
        print("[FASE 3] BD1: nenhuma remessa nova no WPD — nada a anexar.")
    else:
        resultado = _editar_bd1(partes["xl/worksheets/sheet5.xml"], novas, strings)
        xml_bd1, fim_bd1_novo, refs = resultado
        substituicoes["xl/worksheets/sheet5.xml"] = xml_bd1
        novas_celulas += refs
        houve_mudanca_bd1 = True
        substituicoes["xl/tables/table1.xml"] = _ajustar_tabela(
            partes["xl/tables/table1.xml"], "A1:V", fim_bd1_novo)
        print(f"[FASE 3] BD1: {len(novas)} remessa(s) anexada(s) — fim {fim_bd1_novo}.")

    # ---- FASE 3b: BD2 — bloco novo do Não Identificado (R5: tolera limpo=None) ----
    if xlsx_nao_identificado_limpo is not None:
        bloco = _bloco_bd2(xlsx_nao_identificado_limpo)
        resultado = _editar_bd2(partes["xl/worksheets/sheet6.xml"], bloco, strings)
        if resultado[0] is not None:
            xml_bd2, fim_bd2_novo, refs = resultado
            substituicoes["xl/worksheets/sheet6.xml"] = xml_bd2
            novas_celulas += refs
            substituicoes["xl/tables/table2.xml"] = _ajustar_tabela(
                partes["xl/tables/table2.xml"], "A1:I", fim_bd2_novo)
            parte_cache_bd2 = _parte_cache_bd2(partes)
            if parte_cache_bd2 is None:
                raise RuntimeError(
                    "Cache da BD2 não encontrado (nenhum pivot cache com "
                    "worksheetSource ref A1:I) — abortando para não gravar "
                    "uma saída incorreta.")
            substituicoes[parte_cache_bd2] = _ajustar_cache1(
                partes[parte_cache_bd2], fim_bd2_novo)
            print(f"[FASE 3] BD2: bloco atualizado — fim {fim_bd2_novo}.")
        else:
            print("[FASE 3] BD2: nada a mudar.")
    else:
        print("[FASE 3] BD2: integração pulada (limpo não informado).")

    # ---- FASE 4: gravação ----
    mudou_alguma_coisa = ("xl/worksheets/sheet5.xml" in substituicoes
                          or "xl/worksheets/sheet6.xml" in substituicoes)
    if mudou_alguma_coisa:
        for i in range(1, 5):
            nome = f"xl/pivotTables/pivotTable{i}.xml"
            if nome in partes:
                substituicoes[nome] = _marcar_refresh_on_load(partes[nome])
        substituicoes["docProps/core.xml"] = _ajustar_core(partes["docProps/core.xml"])
        substituicoes["xl/sharedStrings.xml"] = strings.para_xml(novas_celulas=novas_celulas)
    if houve_mudanca_bd1:
        substituicoes["xl/workbook.xml"] = _ajustar_workbook(
            partes["xl/workbook.xml"], fim_bd1_novo, calc_completo=True)
    _gravar_zip_cirurgico(xlsx_hias_base, xlsx_hias_final, substituicoes)
    print(f"[FASE 4] Arquivo final gravado: {xlsx_hias_final}")
    if mudou_alguma_coisa:
        _validar_saida(xlsx_hias_final)
