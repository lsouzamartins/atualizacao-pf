"""==============================================================================
INTEGRAÇÃO CIRÚRGICA DO EXCEL — ATUALIZAÇÃO PF · NUVEM
==============================================================================
Substitui o motor COM (Windows) e o motor UNO (reprovado no spike — R24):
edita apenas as partes XML de BD1/BD2 dentro do .xlsx (que é um zip),
preservando pivôs/slicers/timelines byte a byte, e regenera os caches
embutidos das pivôs (pivot_cache.py) com os dados finais + os estados de
timeline/slicer do arquivo de referência — SEM refreshOnLoad (as pivôs
renderizam dos caches, de forma determinística, como no pendrive).

O arquivo Hias NUNCA é salvo pelo openpyxl (isso destruiria pivôs/slicers —
ver notas-spike-libreoffice.md). O openpyxl aqui só LÊ (gate de validação).

Referência da anatomia do arquivo: .superpowers/sdd/2026-09-01-atualizacao-pf-nuvem/task-4-investigacao.md

Contrato público (consumido por integracao_runner.py):
    processar_fases_2_3_4_hias(xlsx_nao_identificado_limpo, xlsx_hias_base,
                               xlsx_hias_final, pasta_raiz, pasta_saida,
                               xlsx_wpd_limpo) -> None
=============================================================================="""
import calendar
import numbers
import os
import re
import shutil
import zipfile
from datetime import date, datetime, timedelta, timezone
from xml.etree import ElementTree as ET

import pandas as pd

import pivot_cache as pc

# ------------------------------------------------------------------------------
# Constantes da anatomia do arquivo Hias (task-4-investigacao.md)
# ------------------------------------------------------------------------------
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
        # de 02/09/2026: definition1↔definition2) — inclui todas as famílias de
        # pivô para a seleção por conteúdo (FASE 3c / pivot_cache.py)
        familias = [r"xl/pivotCache/pivotCacheDefinition\d+\.xml",
                    r"xl/pivotCache/pivotCacheRecords\d+\.xml",
                    r"xl/pivotCache/_rels/pivotCacheDefinition\d+\.xml\.rels",
                    r"xl/timelineCaches/timelineCache\d+\.xml",
                    r"xl/slicerCaches/slicerCache\d+\.xml"]
        partes.update({n: z.read(n).decode("utf-8") for n in nomes
                       if any(re.fullmatch(f, n) for f in familias)})
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
    """Uma <row> da BD2: A string s=34, B data s=16 (mm-dd-yy, igual às linhas
    existentes), C–I números s=53, J =1 s=17 (J=1 mantém a formatação
    condicional $J2=1/$J2=2 — recomendação da investigação)."""
    cels = [_celula(f"A{num_linha}", 34, str(strings.obter_indice(convenio)), tipo="s"),
            _celula(f"B{num_linha}", 16, str(data_serial))]
    for i, v in enumerate(valores):  # C..I
        cels.append(_celula(f"{chr(ord('C') + i)}{num_linha}", 53, _numero(v)))
    cels.append(_celula(f"J{num_linha}", 17, "1"))
    return f'<row r="{num_linha}">{"".join(cels)}</row>'


_RE_CEL_CI = re.compile(r'<c r="([C-I])(\d+)"([^>]*)>(?:(?:<v>([^<]*)</v>)?</c>|/>)')
_COLS_CI = ["C", "D", "E", "F", "G", "H", "I"]


def _float_iguais(a, b) -> bool:
    """Mesmo número: `a` é a string bruta do XML (ou None), `b` a canônica.
    Igualdade NUMÉRICA — '610.41999999999996' == '610.42' (repr do Excel)."""
    if a is None or b is None:
        return a is None and b is None
    try:
        return float(a) == float(b)
    except ValueError:
        return a == b


def _valores_c_i(corpo: str) -> dict:
    """{coluna C-I: (valor bruto do <v>, é string t='s')} de uma row da BD2 —
    célula ausente ou <v> vazio → (None, False)."""
    return {m.group(1): (m.group(4) or None, 't="s"' in (m.group(3) or ""))
            for m in _RE_CEL_CI.finditer(corpo)}


def _upsert_c_i(corpo: str, linha: int, novos: list) -> str:
    """Atualiza/injeta as células C-I de uma row: `novos[i]` é o valor
    canônico novo (None preserva a posição). Só células NUMÉRICAS com valor
    numericamente diferente são reescritas (preservando o estilo original);
    células t='s' (strings históricas) e reprs de float equivalentes são
    intocadas; células que faltam são criadas antes de </row>."""
    def _troca(m):
        col, attrs, atual = m.group(1), m.group(3) or "", m.group(4)
        i = ord(col) - ord("C")
        novo = novos[i] if i < len(novos) else None
        if novo is None or 't="s"' in attrs or _float_iguais(atual, novo):
            return m.group(0)
        if m.group(4) is None:  # célula sem <v>
            if m.group(0).endswith("/>"):
                return m.group(0)[:-2] + f'><v>{novo}</v></c>'
            return m.group(0).replace("</c>", f"<v>{novo}</v></c>", 1)
        return m.group(0).replace(f"<v>{m.group(4)}</v>", f"<v>{novo}</v>", 1)
    corpo_novo = _RE_CEL_CI.sub(_troca, corpo)
    presentes = {m.group(1) for m in _RE_CEL_CI.finditer(corpo_novo)}
    criadas = [f'<c r="{_COLS_CI[i]}{linha}" s="49"><v>{novo}</v></c>'
               for i, novo in enumerate(novos)
               if novo is not None and _COLS_CI[i] not in presentes]
    return corpo_novo + "".join(criadas)


def _editar_bd2(xml_bd2: str, bloco: list[dict] | None, strings) -> tuple[str | None, int | None, int, dict, list, list]:
    """(1) normaliza a coluna A (tira o preenchimento de espaços,
    sincronizando sharedStrings); (2) UPSERT das linhas do bloco pela chave
    (Convênio, Data): chave nova anexa no fim; chave existente com valores
    iguais é pulada (dedupe); chave existente com valores diferentes ATUALIZA
    as células C-I da linha existente — a edição do usuário no NI prevalece
    sem reescrever o restante da base (a BD2 é o histórico curado, nunca
    regenerado do WPD); (3) atualiza a dimension.
    Retorna (xml_novo, fim_novo, células t="s" novas, mapeamento da
    normalização, linhas novas do bloco, atualizações) ou (None, None, 0,
    {}, [], []). O mapeamento {original: limpo} permite à FASE 3c
    renormalizar o cache embutido da BD2 no lugar; as linhas novas alimentam
    os records novos do cache (mesma ordem das linhas da planilha) e as
    atualizações são {linha, record, valores, valores_antigos} posicionais
    C-I (None preserva a posição) para o upsert do record correspondente."""
    fim_atual = _ultima_linha(xml_bd2)
    mudou = False
    mapeamento = {}

    # chaves já presentes: (Convênio sem padding, serial da data em B) -> (linha, corpo)
    existentes: dict[tuple, tuple[int, str]] = {}
    for m in re.finditer(r'<row r="(\d+)"[^>]*>(.*?)</row>', xml_bd2, flags=re.DOTALL):
        num = int(m.group(1))
        if num < 2:
            continue
        corpo = m.group(2)
        convenio = None
        ca = re.search(r'<c r="A\d+"[^>]*?>(?:<v>([^<]*)</v>|<t[^>]*>([^<]*)</t>)?</c>', corpo)
        if ca and ca.group(1) is not None and 't="s"' in ca.group(0):
            convenio = strings.texto_de_indice(int(ca.group(1))).strip()
        elif ca and ca.group(2) is not None:
            convenio = ca.group(2).strip()
        cb = re.search(r'<c r="B\d+"[^>]*?><v>([^<]*)</v></c>', corpo)
        serial = None if cb is None else cb.group(1)
        if convenio is not None:
            existentes.setdefault((convenio, serial), (num, corpo))

    novas: list[dict] = []
    atualizacoes: list[dict] = []
    if bloco:
        vistos = set()
        for b in bloco:
            chave = (b["convenio"], str(b["data"]))
            if chave in vistos:
                continue  # duplicata dentro do próprio bloco
            vistos.add(chave)
            if chave in existentes:
                linha, corpo = existentes[chave]
                novos_vals = [None if v is None else _numero(v) for v in b["valores"]]
                atuais = _valores_c_i(corpo)
                vals, antigos = [], []
                for i, novo in enumerate(novos_vals):
                    v_bruto, eh_str = atuais.get(_COLS_CI[i], (None, False))
                    if eh_str or _float_iguais(v_bruto, novo):
                        # string histórica intocada; mesmo número não reescreve
                        vals.append(None)
                        antigos.append(None)
                        continue
                    vals.append(novo)
                    antigos.append(v_bruto)
                if any(v is not None for v in vals):
                    atualizacoes.append({
                        "linha": linha,
                        "record": linha - 2,  # records ordenados: record_idx = linha - 2
                        "valores": vals,
                        "valores_antigos": antigos,
                    })
                continue
            novas.append(b)

    def _normalizar_coluna_a(m):
        nonlocal mudou
        num = int(m.group(1))
        if num < 2:
            return m.group(0)
        cel = re.search(r'<c r="A\d+"[^>]*?><v>(\d+)</v></c>', m.group(3))
        if not cel or 't="s"' not in cel.group(0):
            return m.group(0)
        original = strings.texto_de_indice(int(cel.group(1)))
        limpo = original.strip()
        if limpo == original:
            return m.group(0)
        novo = strings.obter_indice(limpo)
        mapeamento[original] = limpo
        cel_nova = cel.group(0).replace(f"<v>{cel.group(1)}</v>", f"<v>{novo}</v>")
        mudou = True
        return f'<row r="{num}"{m.group(2)}>{m.group(3).replace(cel.group(0), cel_nova, 1)}</row>'

    texto = re.sub(r'<row r="(\d+)"([^>]*)>(.*?)</row>', _normalizar_coluna_a, xml_bd2, flags=re.DOTALL)

    if atualizacoes:
        mudou = True
        for att in atualizacoes:
            linha, vals = att["linha"], att["valores"]

            def _troca_row(m):
                return f'<row r="{linha}"{m.group(1)}>{_upsert_c_i(m.group(2), linha, vals)}</row>'
            texto, n = re.subn(rf'<row r="{linha}"([^>]*)>(.*?)</row>', _troca_row,
                               texto, count=1, flags=re.DOTALL)
            if n != 1:
                raise RuntimeError(f"upsert: linha {linha} da BD2 não localizada")

    novas_celulas = 0
    if novas:
        mudou = True
        linhas = "".join(_linha_bd2(fim_atual + 1 + i, b["convenio"], b["data"],
                                    b["valores"], strings)
                         for i, b in enumerate(novas))
        novas_celulas = len(novas)
        idx = texto.rfind("</sheetData>")
        texto = texto[:idx] + linhas + texto[idx:]
        novo_fim = fim_atual + len(novas)
    else:
        novo_fim = fim_atual

    if not mudou:
        return None, None, 0, {}, [], []
    texto = _substituir_ou_falhar(
        r'<dimension ref="A1:J(\d+)"/>',
        f'<dimension ref="A1:J{novo_fim}"/>', texto, "dimension da BD2")
    return texto, novo_fim, novas_celulas, mapeamento, novas, atualizacoes


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


# ==============================================================================
# FASE 3c — caches embutidos + timeline + slicers (pivot_cache.py)
# ==============================================================================
def _janela_entrega(hoje: date | None = None) -> tuple[date, date]:
    """Janela da timeline "Entrega": o mês de FECHAMENTO (mês anterior ao da
    geração). O arquivo de referência de 03/09/2026 usa agosto/2026 mesmo
    contendo entregas de 01–03/09 — a janela segue o calendário, não os dados."""
    hoje = hoje or date.today()
    if hoje.month > 1:
        ano, mes = hoje.year, hoje.month - 1
    else:
        ano, mes = hoje.year - 1, 12
    return date(ano, mes, 1), date(ano, mes, calendar.monthrange(ano, mes)[1])


def _iso_cache(v: date | None) -> str | None:
    """Data no formato dos <d v> dos caches (ISO + T00:00:00)."""
    return f"{v.isoformat()}T00:00:00" if v is not None else None


def _x_ref(cache: pc.CachePivot, campo: str, tipo: str, valor) -> str:
    return f'<x v="{cache.obter_indice(campo, tipo, valor)}"/>'


def _x_ref_ou_blank(cache: pc.CachePivot, campo: str, tipo: str, valor) -> str:
    """valor None → x-ref do item em branco (se o campo o tiver) ou <m/> inline."""
    if valor is None:
        if cache.tem_blank(campo):
            return f'<x v="{cache.obter_indice(campo, "m", None)}"/>'
        return "<m/>"
    return _x_ref(cache, campo, tipo, valor)


def _n_inline(v) -> str:
    return f'<n v="{_numero(v)}"/>' if v is not None else "<m/>"


def _d_inline(v: date | None) -> str:
    return f'<d v="{_iso_cache(v)}"/>' if v is not None else "<m/>"


def _record_bd1(dados: dict, cache: pc.CachePivot, hoje: date) -> str:
    """Um <r> de 22 entradas para o cache da BD1, no formato exato do Excel
    (referência 03/09): Remessa/Protocolo/Vencimento/Entrega/Baixa/Convênio/
    Tipo x-ref; Emissão <d> inline; NF <m/>; demais <n> inline. Os campos
    calculados (17–20) são avaliados aqui com TODAY() = data de geração."""
    remessa = dados["Remessa"]
    recurso = str(remessa).strip().endswith("(R)")
    if pd.api.types.is_number(remessa):
        numero = int(remessa) if float(remessa).is_integer() else float(remessa)
        e_remessa = _x_ref(cache, "Remessa", "n", _numero(numero))
    else:
        e_remessa = _x_ref(cache, "Remessa", "s", str(remessa))
    protocolo = dados["Protocolo"]
    e_protocolo = (_x_ref(cache, "Protocolo", "s", protocolo)
                   if isinstance(protocolo, str)
                   else _x_ref_ou_blank(cache, "Protocolo", "n", _numero(protocolo)))
    convenio = "" if dados["Convênio"] is None else str(dados["Convênio"])
    vlr_guia = dados["Vlr Guia"]
    vencimento = dados["Vencimento"]
    baixa = dados["Baixa"]
    # fórmulas R–V da planilha, avaliadas para o record do cache:
    atrasado = ((vlr_guia or 0) if (vencimento is not None and vencimento < hoje
                                    and baixa is None) else 0)
    a_vencer = ((vlr_guia or 0) if (vencimento is not None and vencimento > hoje
                                    and baixa is None) else 0)
    recurso_v = (vlr_guia or 0) if recurso else 0
    recurso_pago = (dados["Valor Pago"] or 0) if recurso_v != 0 else 0
    entradas = [
        e_remessa,                                                             # 0
        e_protocolo,                                                           # 1
        _d_inline(dados["Emissão"]),                                           # 2
        _x_ref_ou_blank(cache, "Vencimento", "d", _iso_cache(vencimento)),     # 3
        _x_ref_ou_blank(cache, "Entrega", "d", _iso_cache(dados["Entrega"])),  # 4
        _x_ref_ou_blank(cache, "Baixa", "d", _iso_cache(baixa)),               # 5
        "<m/>",                                                                # 6 NF
        _x_ref(cache, "Convênio", "s", convenio),                              # 7
        _n_inline(dados["Faturado"]),                                          # 8
        _n_inline(dados["Valor Pago"]),                                        # 9
        _n_inline(dados["Valor ISS"]),                                         # 10
        _n_inline(vlr_guia),                                                   # 11
        _n_inline(dados["% Pré-glosa"]),                                       # 12
        _n_inline(dados["Valor Glosa"]),                                       # 13
        _n_inline(dados["% Glosa"]),                                           # 14
        _n_inline(dados["Atraso"]),                                            # 15
        _n_inline(dados["Faturas"]),                                           # 16
        _n_inline(atrasado),                                                   # 17
        _n_inline(a_vencer),                                                   # 18
        _n_inline(recurso_v),                                                  # 19
        _n_inline(recurso_pago),                                               # 20
        _x_ref(cache, "Tipo de remessa", "s",
               "Recurso" if recurso else "Comum"),                             # 21
    ]
    return "<r>" + "".join(entradas) + "</r>"


def _record_bd2(item: dict, cache: pc.CachePivot) -> str:
    """Um <r> de 9 entradas para o cache da BD2: Convênio/Data x-ref,
    valores <n> inline (formato do Excel na referência 03/09)."""
    data_iso = (SERIAL_EPOCA + timedelta(days=item["data"])).isoformat() + "T00:00:00"
    entradas = [
        _x_ref(cache, "Convênio", "s", item["convenio"]),
        _x_ref(cache, "Data", "d", data_iso),
    ] + [_n_inline(v) for v in item["valores"]]
    return "<r>" + "".join(entradas) + "</r>"


def _fase_3c(partes: dict, substituicoes: dict, novas: pd.DataFrame,
             bloco: list[dict] | None, mapeamento_bd2: dict,
             fim_bd1_novo: int | None, fim_bd2_novo: int | None,
             novas_bd2: list, atualizacoes_bd2: list) -> None:
    """Regenera os caches embutidos (BD1/BD2) com os dados finais e grava os
    estados de timeline/slicer/pivô do arquivo de referência — determinístico
    a cada rodada (sem depender de o Excel recalcular ao abrir)."""
    hoje = date.today()
    nome_def_bd1 = pc.parte_cache_bd1(partes)
    nome_def_bd2 = pc.parte_cache_bd2(partes)
    nome_rec_bd1 = pc.nome_da_rel(partes, nome_def_bd1)
    nome_rec_bd2 = pc.nome_da_rel(partes, nome_def_bd2)
    cache_bd1 = pc.CachePivot(partes[nome_def_bd1], partes[nome_rec_bd1])
    # a FASE 3b pode já ter atualizado o worksheetSource do def da BD2
    cache_bd2 = pc.CachePivot(substituicoes.get(nome_def_bd2, partes[nome_def_bd2]),
                              partes[nome_rec_bd2])
    n_inicial_bd2 = cache_bd2.n_registros

    # -- BD1: um record por remessa nova (mesma ordem das linhas da planilha) --
    if novas is not None and len(novas):
        cache_bd1.anexar_registros(
            [_record_bd1(_converter_linha_wpd(linha), cache_bd1, hoje)
             for _, linha in novas.iterrows()])

    # -- BD2: records das linhas novas + normalização dos convênios + upsert
    # das linhas editadas — as demais linhas da base permanecem intactas na
    # planilha e no cache; entram só as linhas do bloco sem chave repetida
    # (mesma ordem das linhas da planilha) e as atualizações pontuais (edição
    # do usuário no NI prevalece sobre o valor antigo).
    if fim_bd2_novo is not None:
        if mapeamento_bd2:
            cache_bd2.substituir_strings("Convênio", mapeamento_bd2)
        if atualizacoes_bd2:
            for att in atualizacoes_bd2:
                cache_bd2.atualizar_registro(att["record"], att["valores"],
                                             att["valores_antigos"])
        if novas_bd2:
            cache_bd2.anexar_registros([_record_bd2(b, cache_bd2) for b in novas_bd2])

    # -- timeline "Entrega" = mês de fechamento --
    inicio, fim = _janela_entrega(hoje)
    nome_timeline = pc.parte_timeline_entrega(partes)
    substituicoes[nome_timeline] = pc.editar_timeline(partes[nome_timeline], inicio, fim)

    # -- slicer "Tipo de remessa" (Data Entrega) = só Comum --
    nome_slicer_tipo = pc.parte_slicer_tipo_data_entrega(partes)
    substituicoes[nome_slicer_tipo] = pc.selecionar_slicer_tipo_remessa(
        partes[nome_slicer_tipo])

    # -- slicers "Convênio": novos itens entram marcados (BD1→tabs 3/6/11; BD2→tab 8) --
    novos_conv_bd1 = cache_bd1.novos_indices("Convênio")
    novos_conv_bd2 = cache_bd2.novos_indices("Convênio")
    for nome in pc.partes_slicer_convenio(partes, [3, 6, 11]):
        if novos_conv_bd1:
            substituicoes[nome] = pc.anexar_itens_slicer(partes[nome], novos_conv_bd1)
    for nome in pc.partes_slicer_convenio(partes, [8]):
        if novos_conv_bd2:
            substituicoes[nome] = pc.anexar_itens_slicer(partes[nome], novos_conv_bd2)

    # -- pivôs 1–3 (cache BD1): itens novos por campo; convênios colapsados --
    novos_por_campo_bd1 = cache_bd1.novos_por_campo()
    for i in (1, 2, 3):
        nome = f"xl/pivotTables/pivotTable{i}.xml"
        xml = pc.remover_refresh_on_load(partes[nome])
        for idx, nome_campo in enumerate(cache_bd1.campos_ordenados()):
            if nome_campo not in novos_por_campo_bd1 or not pc.campo_tem_itens(xml, idx):
                continue
            com_sd = nome_campo == "Convênio"
            xml = pc.anexar_itens_pivot(xml, idx, novos_por_campo_bd1[nome_campo],
                                        com_sd=com_sd)
            if com_sd:
                xml = pc.colapsar_itens_pivot(xml, idx)
        substituicoes[nome] = xml

    # -- pivot1: esconde Recurso (x=1) e vazio (x=2) no campo 21 (Tipo) --
    nome_p1 = "xl/pivotTables/pivotTable1.xml"
    xml_p1 = substituicoes[nome_p1]
    if pc.campo_tem_itens(xml_p1, 21):
        substituicoes[nome_p1] = pc.esconder_itens_pivot(xml_p1, 21, [1, 2])

    # -- pivô 4 (À Quitar, cache BD2): campos 0 (Convênio) e 1 (Data) --
    nome_p4 = "xl/pivotTables/pivotTable4.xml"
    xml_p4 = pc.remover_refresh_on_load(partes[nome_p4])
    novos_por_campo_bd2 = cache_bd2.novos_por_campo()
    for idx, nome_campo in enumerate(cache_bd2.campos_ordenados()):
        if nome_campo not in novos_por_campo_bd2 or not pc.campo_tem_itens(xml_p4, idx):
            continue
        com_sd = nome_campo == "Convênio"
        xml_p4 = pc.anexar_itens_pivot(xml_p4, idx, novos_por_campo_bd2[nome_campo],
                                       com_sd=com_sd)
        if com_sd:
            xml_p4 = pc.colapsar_itens_pivot(xml_p4, idx)
    substituicoes[nome_p4] = xml_p4

    # -- grava os caches regenerados --
    substituicoes[nome_def_bd1], substituicoes[nome_rec_bd1] = cache_bd1.para_xml()
    substituicoes[nome_def_bd2], substituicoes[nome_rec_bd2] = cache_bd2.para_xml()

    esperado_bd2 = (n_inicial_bd2 + len(novas_bd2)
                    if fim_bd2_novo is not None else None)
    _validar_pivos(substituicoes, partes, cache_bd1, cache_bd2,
                   fim_bd1_novo, esperado_bd2)


def _validar_pivos(substituicoes: dict, partes: dict, cache_bd1: pc.CachePivot,
                   cache_bd2: pc.CachePivot, fim_bd1_novo: int | None,
                   esperado_bd2: int | None) -> None:
    """Gate pré-gravação: os estados críticos têm de estar como o esperado —
    aborta ANTES de escrever uma saída errada."""
    erros = []
    for i in (1, 2, 3, 4):
        xml = substituicoes.get(f"xl/pivotTables/pivotTable{i}.xml")
        if xml is not None and "refreshOnLoad" in xml:
            erros.append(f"pivotTable{i} ainda contém refreshOnLoad")
    tl = substituicoes.get(pc.parte_timeline_entrega(partes))
    if tl is not None and ('filterType="dateBetween"' not in tl or "<selection" not in tl):
        erros.append("timeline Entrega sem dateBetween/selection")
    st = substituicoes.get(pc.parte_slicer_tipo_data_entrega(partes))
    if st is not None:
        selecionados = re.findall(r'<i x="(\d+)" s="1"', st)
        if selecionados != ["0"]:
            erros.append(f"slicer Tipo de remessa com seleção inesperada: {selecionados}")
    if fim_bd1_novo is not None and cache_bd1.n_registros != fim_bd1_novo - 1:
        erros.append(f"cache BD1 com {cache_bd1.n_registros} records ≠ planilha "
                     f"({fim_bd1_novo - 1} linhas de dados)")
    if esperado_bd2 is not None and cache_bd2.n_registros != esperado_bd2:
        erros.append(f"cache BD2 com {cache_bd2.n_registros} records ≠ esperado "
                     f"({esperado_bd2} = inicial + linhas novas)")
    if erros:
        raise RuntimeError("Falha no gate dos pivôs: " + "; ".join(erros))


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
    bloco = None
    mapeamento_bd2 = {}
    fim_bd2_novo = None
    novas_bd2: list = []
    atualizacoes_bd2: list = []
    if xlsx_nao_identificado_limpo is not None:
        bloco = _bloco_bd2(xlsx_nao_identificado_limpo)
        resultado = _editar_bd2(partes["xl/worksheets/sheet6.xml"], bloco, strings)
        if resultado[0] is not None:
            xml_bd2, fim_bd2_novo, refs, mapeamento_bd2, novas_bd2, atualizacoes_bd2 = resultado
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
            print(f"[FASE 3] BD2: {len(novas_bd2)} linha(s) nova(s), "
                  f"{len(atualizacoes_bd2)} atualizada(s) — fim {fim_bd2_novo}.")
        else:
            print("[FASE 3] BD2: nada a mudar.")
    else:
        print("[FASE 3] BD2: integração pulada (limpo não informado).")

    # ---- FASE 3c: caches embutidos + timeline + slicers ----
    mudou_alguma_coisa = ("xl/worksheets/sheet5.xml" in substituicoes
                          or "xl/worksheets/sheet6.xml" in substituicoes)
    if mudou_alguma_coisa:
        _fase_3c(partes, substituicoes, novas, bloco, mapeamento_bd2,
                 fim_bd1_novo, fim_bd2_novo, novas_bd2, atualizacoes_bd2)

    # ---- FASE 4: gravação ----
    if mudou_alguma_coisa:
        substituicoes["docProps/core.xml"] = _ajustar_core(partes["docProps/core.xml"])
        substituicoes["xl/sharedStrings.xml"] = strings.para_xml(novas_celulas=novas_celulas)
    if houve_mudanca_bd1:
        substituicoes["xl/workbook.xml"] = _ajustar_workbook(
            partes["xl/workbook.xml"], fim_bd1_novo, calc_completo=True)
    _gravar_zip_cirurgico(xlsx_hias_base, xlsx_hias_final, substituicoes)
    print(f"[FASE 4] Arquivo final gravado: {xlsx_hias_final}")
    if mudou_alguma_coisa:
        _validar_saida(xlsx_hias_final)
