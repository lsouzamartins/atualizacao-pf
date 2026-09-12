"""==============================================================================
PIVÔS — CACHES EMBUTIDOS, TIMELINE E SLICERS (editor cirúrgico)
==============================================================================
Regenera os caches embutidos dos pivôs (pivotCacheDefinition + records) com os
dados finais e grava os estados de timeline/slicer, reproduzindo o que o Excel
gravava no fluxo do pendrive (arquivo de referência de 03/09/2026):

- itens novos entram APENAS como acréscimo no fim dos sharedItems — a mesma
  convenção do Excel observada no arquivo real (ordem de primeira aparição,
  sem reordenar nem remover itens antigos);
- timeline "Entrega" e slicers do arquivo do usuário são PRESERVADOS byte a
  byte (sem filtros forçados — filtros do mês de fechamento ou "só Comum"
  escondiam baixas e recursos no relatório);
- refreshOnLoad é REMOVIDO das pivôs e dos caches (as pivôs renderizam dos
  caches, de forma determinística, sem recalcular ao abrir).

Toda a edição é por ancoragem textual (regex) sobre as partes XML — nenhuma
parte é reescrita por parser, preservando atributos e estrutura byte a byte.

Referência da anatomia: .superpowers/sdd/2026-09-01-atualizacao-pf-nuvem/
task-4-investigacao.md + inspeções de 03–04/09/2026.
=============================================================================="""
import posixpath
import re
from datetime import datetime
from xml.sax.saxutils import escape, unescape

# ------------------------------------------------------------------------------
# Constantes
# ------------------------------------------------------------------------------
RE_DEF_CACHE = re.compile(r"xl/pivotCache/pivotCacheDefinition\d+\.xml$")
RE_RELS_DEF = re.compile(r"xl/pivotCache/_rels/pivotCacheDefinition\d+\.xml\.rels$")
RE_RECORDS = re.compile(r"xl/pivotCache/pivotCacheRecords\d+\.xml$")
RE_SLICER = re.compile(r"xl/slicerCaches/slicerCache\d+\.xml$")

# cacheField com corpo (pode ter sharedItems) OU auto-contido (<cacheField .../>)
# — ambos contam para a ordem posicional dos campos. O ramo AUTO-CONTIDO vem
# PRIMEIRO: se o ramo com corpo vier antes, (?P<attrs>[^>]*) absorve a "/" do
# campo auto-contido e o corpo .*? engole o campo seguinte inteiro.
_RE_CAMPO = re.compile(
    r'<cacheField name="(?P<nome2>[^"]+)"[^>]*/>'
    r'|<cacheField name="(?P<nome>[^"]+)"(?P<attrs>[^>]*)>(?P<corpo>.*?)</cacheField>',
    re.S)
_RE_SHARED = re.compile(r'<sharedItems\b(?P<attrs>[^>]*)>(?P<filhos>.*?)</sharedItems>', re.S)
_RE_ITEM = re.compile(r'<(?P<t>[nsdm])\b(?P<a>[^>]*)/>')
_RE_R = re.compile(r"<r>.*?</r>", re.S)
# entradas C-I do record: <n v="..."/>, <s v="..."/> (string histórica da
# base) ou <m/> (vazio)
_RE_ENTRADA_NM = re.compile(r'<n v="([^"]*)"/>|<s v="([^"]*)"/>|<m/>')
_RE_PIVOT_FIELD = re.compile(r"<pivotField\b[^>]*?/>|<pivotField\b.*?</pivotField>", re.S)
_RE_ITEMS_SLICER = re.compile(r"(<items\b[^>]*>)(.*?)(</items>)", re.S)
_RE_ITEMS_PIVOT = re.compile(r"(<items\b[^>]*>)(.*?)(</items>)", re.S)

NOME_USUARIO = "Leonardo Martins"

# atributos de sharedItems recalculados a cada acréscimo
_ATTRS_RECALC = ("count", "minValue", "maxValue", "minDate", "maxDate",
                 "containsString", "containsNumber", "containsInteger",
                 "containsDate", "containsBlank", "containsMixedTypes")
_RE_ATTRS_RECALC = re.compile(r'\s+(?:' + "|".join(_ATTRS_RECALC) + r')="[^"]*"')


def _numero(valor):
    """Número na forma canônica do XML (sem .0 espúrio) — espelha o motor."""
    if isinstance(valor, bool):
        return "1" if valor else "0"
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    if isinstance(valor, int):
        return str(valor)
    return repr(float(valor))


def _escape_attr(texto: str) -> str:
    """Escapa um valor para atributo XML (inclui aspas — o Excel usa &quot;)."""
    return escape(texto, {'"': "&quot;"})


# ==============================================================================
# CachePivot — sharedItems + records de um pivotCacheDefinition
# ==============================================================================
class CachePivot:
    """Edita um cache embutido: acrescenta itens aos sharedItems (no fim) e
    registros ao fim (ou remove o bloco final), mantendo índices antigos."""

    def __init__(self, xml_def: str, xml_reg: str):
        self._def = xml_def
        self._reg = xml_reg
        self._campos = {}
        for m in _RE_CAMPO.finditer(xml_def):
            nome = m.group("nome") or m.group("nome2")
            corpo = m.group("corpo") or ""
            sh = _RE_SHARED.search(corpo)
            self._campos[nome] = _Campo(corpo, sh)
        m = re.search(r'<pivotCacheRecords\b[^>]*\bcount="(\d+)"', xml_reg)
        if not m:
            raise RuntimeError("count dos records não encontrado no cache")
        self._n_registros = int(m.group(1))

    @property
    def n_registros(self) -> int:
        """Nº de registros do cache (espelha o count do pivotCacheRecords)."""
        return self._n_registros

    # -- campos ---------------------------------------------------------------
    def campos_ordenados(self) -> list[str]:
        """Nomes dos cacheFields em ordem de documento (= posição nos records)."""
        return list(self._campos.keys())

    def tem_blank(self, campo: str) -> bool:
        """O sharedItems do campo tem item em branco (<m/>)."""
        return any(t == "m" for t, _ in self._campos[campo].itens)

    def obter_indice(self, campo: str, tipo: str, valor: str | None) -> int:
        """Índice (base 0) do item no sharedItems do campo; acrescenta no fim
        se ainda não existe. tipo ∈ {'n', 's', 'd', 'm'} (m → valor None)."""
        return self._campos[campo].obter(tipo, valor)

    def indice_existente(self, campo: str, tipo: str, valor) -> int | None:
        """Índice do item no sharedItems do campo SEM acrescentar (None se
        não existe). Usado para LOCALIZAR um record já gravado."""
        for i, (t, v) in enumerate(self._campos[campo].itens):
            if t == tipo and v == valor:
                return i
        return None

    def indices_por_valor(self, campo: str) -> dict[tuple[str, str | None], int]:
        """{(tipo, valor): índice} de todos os itens do campo — para N buscas
        em uma passada (indice_existente repetido seria O(n²))."""
        return {(t, v): i for i, (t, v) in enumerate(self._campos[campo].itens)}

    def novos_indices(self, campo: str) -> list[int]:
        """Índices dos itens ACRESCENTADOS ao campo (para a pivô e slicers)."""
        return list(self._campos[campo]._novos_indices)

    def novos_por_campo(self) -> dict:
        """{nome do campo: [índices novos]} — só campos com acréscimos."""
        return {n: c._novos_indices for n, c in self._campos.items() if c._novos_indices}

    def substituir_strings(self, campo: str, mapeamento: dict) -> bool:
        """Reescreve <s v="..."/> no LUGAR (índices estáveis — os records não
        mudam). Usado quando a planilha normaliza nomes (ex.: tira espaços).
        Se o valor novo já existir em OUTRO item do campo (ex.: item não usado
        u="1" herdado da base), a entrada é pulada — o Excel repara caches com
        valores duplicados no sharedItems, mas tolera padding."""
        mudou = False
        itens_campo = self._campos[campo].itens
        for antigo, novo in mapeamento.items():
            if novo == antigo:
                continue
            if any(t == "s" and v == novo and v != antigo for t, v in itens_campo):
                continue  # preserva a unicidade: duplicata quebraria o cache
            antigo_x = _escape_attr(antigo)
            novo_x = _escape_attr(novo)
            m = re.search(r'<cacheField name="' + re.escape(campo) + r'"[^>]*>.*?</cacheField>',
                          self._def, re.S)
            if not m:
                continue
            bloco, bloco_novo = m.group(0), m.group(0).replace(
                f'v="{antigo_x}"', f'v="{novo_x}"')
            if bloco_novo != bloco:
                self._def = self._def[:m.start()] + bloco_novo + self._def[m.end():]
                mudou = True
                for i, (t, v) in enumerate(itens_campo):
                    if t == "s" and v == antigo:
                        itens_campo[i] = (t, novo)
        return mudou

    # -- records --------------------------------------------------------------
    def anexar_registros(self, blocos: list[str]) -> None:
        if not blocos:
            return
        idx = self._reg.rindex("</pivotCacheRecords>")
        self._reg = self._reg[:idx] + "".join(blocos) + self._reg[idx:]
        self._n_registros += len(blocos)

    def inserir_registros(self, posicao: int, blocos: list[str]) -> None:
        """Insere `blocos` ANTES do record de índice `posicao` (0-based) —
        linhas novas da BD2 entram ORDENADAS no meio do cache, na mesma
        posição das linhas da planilha (record i = linha i+2)."""
        if not blocos:
            return
        idx_fim = self._reg.rindex("</pivotCacheRecords>")
        cabeca = self._reg[:idx_fim]
        primeiro = cabeca.index("<r>")
        prefixo = cabeca[:primeiro]
        existentes = _RE_R.findall(cabeca[primeiro:])
        if not 0 <= posicao <= len(existentes):
            raise RuntimeError(
                f"inserir_registros: posição {posicao} inválida "
                f"({len(existentes)} records)")
        self._reg = (prefixo + "".join(existentes[:posicao]) + "".join(blocos)
                     + "".join(existentes[posicao:]) + self._reg[idx_fim:])
        self._n_registros += len(blocos)

    def blocos(self) -> list[str]:
        """Os records <r> em ordem, para leitura."""
        idx_fim = self._reg.rindex("</pivotCacheRecords>")
        cabeca = self._reg[:idx_fim]
        primeiro = cabeca.index("<r>")
        return _RE_R.findall(cabeca[primeiro:])

    def substituir_record(self, indice: int, novo: str) -> None:
        """Substitui o record da posição `indice` por `novo` (o nº de records
        não muda)."""
        idx_fim = self._reg.rindex("</pivotCacheRecords>")
        cabeca = self._reg[:idx_fim]
        primeiro = cabeca.index("<r>")
        prefixo = cabeca[:primeiro]
        blocos = _RE_R.findall(cabeca[primeiro:])
        if not (0 <= indice < len(blocos)):
            raise RuntimeError(
                f"substituir_record: índice {indice} fora de [0, {len(blocos)})")
        self._reg = (prefixo + "".join(novo if i == indice else b
                                       for i, b in enumerate(blocos))
                     + self._reg[idx_fim:])

    def substituir_records(self, mapa: dict[int, str]) -> None:
        """Substitui vários records ({índice: novo}) numa única reescrita —
        chamadas repetidas de substituir_record seriam O(n²)."""
        if not mapa:
            return
        idx_fim = self._reg.rindex("</pivotCacheRecords>")
        cabeca = self._reg[:idx_fim]
        primeiro = cabeca.index("<r>")
        prefixo = cabeca[:primeiro]
        blocos = _RE_R.findall(cabeca[primeiro:])
        for i, novo in mapa.items():
            if not (0 <= i < len(blocos)):
                raise RuntimeError(
                    f"substituir_records: índice {i} fora de [0, {len(blocos)})")
            blocos[i] = novo
        self._reg = prefixo + "".join(blocos) + self._reg[idx_fim:]

    def remover_registros_finais(self, n: int) -> None:
        """Remove os N últimos registros (bloco obsoleto da BD2)."""
        if n <= 0:
            return
        idx_fim = self._reg.rindex("</pivotCacheRecords>")
        cabeca = self._reg[:idx_fim]
        primeiro = cabeca.index("<r>")
        prefixo = cabeca[:primeiro]
        blocos = _RE_R.findall(cabeca[primeiro:])
        if len(blocos) < n:
            raise RuntimeError(
                f"cache com {len(blocos)} registros não tem {n} finais para remover")
        self._reg = prefixo + "".join(blocos[:-n]) + self._reg[idx_fim:]
        self._n_registros -= n

    def atualizar_registro(self, indice: int, valores: list,
                           valores_antigos: list) -> None:
        """Upsert posicional do record `indice` (entradas C-I): `valores[i]` é
        a string canônica nova ou None (preserva a posição). `valores_antigos`
        é a rede de segurança: o valor atual esperado, posição a posição —
        None é wildcard (posição string ou ausente, não comparada). Se o
        record do índice não bater, é localizado pelos valores antigos —
        linha da BD2 <-> record andam juntos e uma divergência aqui é sinal de
        bug, nunca de gravação cega. Entrada <s> com valor novo chega a ser
        convertida em <n> (a célula correspondente foi convertida na planilha
        — quitação do NI); com valor None é preservada."""
        if valores == valores_antigos:
            return  # sem mudança
        idx_fim = self._reg.rindex("</pivotCacheRecords>")
        cabeca = self._reg[:idx_fim]
        primeiro = cabeca.index("<r>")
        prefixo = cabeca[:primeiro]
        blocos = _RE_R.findall(cabeca[primeiro:])

        def _atuais(bloco: str) -> list:
            return [m.group(1) or m.group(2) for m in _RE_ENTRADA_NM.finditer(bloco)]

        def _bate(bloco: str) -> bool:
            """O record bate com os valores antigos se as posições comparáveis
            casarem (None em valores_antigos é wildcard); entradas ausentes no
            fim do record equivalem a None (o Excel omite os <m/> finais em
            records parcialmente vazios)."""
            atuais = _atuais(bloco)
            if len(atuais) < len(valores_antigos):
                if not all(v is None for v in valores_antigos[len(atuais):]):
                    return False
            n = min(len(atuais), len(valores_antigos))
            return all(valores_antigos[i] is None or atuais[i] == valores_antigos[i]
                       for i in range(n))

        alvo = None
        if 0 <= indice < len(blocos) and _bate(blocos[indice]):
            alvo = indice
        if alvo is None:
            candidatos = [i for i, b in enumerate(blocos) if _bate(b)]
            if len(candidatos) != 1:
                raise RuntimeError(
                    f"atualizar_registro: valores antigos {valores_antigos} não "
                    f"localizam um único record (índice {indice}, candidatos "
                    f"{candidatos})")
            alvo = candidatos[0]
        atuais = _atuais(blocos[alvo])
        for i, v in enumerate(valores):
            if v is not None and i >= len(atuais):
                raise RuntimeError(
                    f"atualizar_registro: valor novo na posição {i} além do "
                    f"record {alvo} ({len(atuais)} entradas C-I)")
        if not any(v is not None and v != atuais[i] for i, v in enumerate(valores)):
            return  # nada muda de fato
        contador = [0]

        def _troca(m):
            i = contador[0]
            contador[0] += 1
            novo = valores[i] if i < len(valores) else None
            atual = m.group(1) or m.group(2)   # <n> ou <s>
            if novo is None or novo == atual:
                return m.group(0)
            return f'<n v="{novo}"/>'

        novo_bloco = _RE_ENTRADA_NM.sub(_troca, blocos[alvo])
        self._reg = prefixo + "".join(
            novo_bloco if i == alvo else b for i, b in enumerate(blocos)) + self._reg[idx_fim:]

    # -- serialização ---------------------------------------------------------
    def para_xml(self) -> tuple[str, str]:
        definicao = self._def
        for nome, campo in self._campos.items():
            if campo._novos:
                definicao = campo.aplicar(definicao, nome)
        definicao = re.sub(r'\s+refreshOnLoad="\d"', "", definicao, count=1)
        definicao = re.sub(r'recordCount="\d+"',
                           f'recordCount="{self._n_registros}"', definicao, count=1)
        agora = datetime.now()
        serial = (agora - datetime(1899, 12, 30)).total_seconds() / 86400
        definicao = re.sub(r'refreshedBy="[^"]*"',
                           f'refreshedBy="{NOME_USUARIO}"', definicao, count=1)
        serial_str = repr(serial)  # repr de float já é decimal puro (sem aspas)
        definicao = re.sub(r'refreshedDate="[^"]*"',
                           f'refreshedDate="{serial_str}"', definicao, count=1)
        registros = re.sub(r'(<pivotCacheRecords\b[^>]*\bcount=")(\d+)(")',
                           lambda m: f'{m.group(1)}{self._n_registros}{m.group(3)}',
                           self._reg, count=1)
        return definicao, registros


class _Campo:
    """Um cacheField: lista de itens do sharedItems + acréscimos pendentes."""

    def __init__(self, corpo: str, sh):
        self._corpo = corpo
        self._sh = sh
        self.itens = []            # [(tipo, valor|None)] existentes, em ordem
        self._novos = []           # [(tipo, valor|None)] a acrescentar no fim
        self._novos_indices = []
        if sh is not None:
            for m in _RE_ITEM.finditer(sh.group("filhos")):
                t = m.group("t")
                v = None
                vm = re.search(r'\bv="([^"]*)"', m.group("a"))
                if vm:
                    v = unescape(vm.group(1))
                self.itens.append((t, v))

    def obter(self, tipo: str, valor: str | None) -> int:
        for i, (t, v) in enumerate(self.itens):
            if t == tipo and v == valor:
                return i
        # já acrescentado nesta rodada? reaproveita o índice pendente — sem
        # duplicar o sharedItem quando valores se repetem entre os registros
        # novos (convênio/data/vencimento iguais em linhas diferentes)
        for j, (t, v) in enumerate(self._novos):
            if t == tipo and v == valor:
                return len(self.itens) + j
        # não existe → acrescenta no fim (convenção do Excel: 1ª aparição)
        indice = len(self.itens) + len(self._novos)
        self._novos.append((tipo, valor))
        self._novos_indices.append(indice)
        return indice

    def aplicar(self, xml_def: str, nome: str) -> str:
        """Insere os itens novos antes de </sharedItems> e atualiza os
        atributos (count/min/max/contains*) do campo, ancorado pelo NOME."""
        m = re.search(r'(<cacheField name="' + re.escape(nome) + r'"[^>]*>.*?'
                      r'<sharedItems\b)([^>]*)(>)(.*?)(</sharedItems>)',
                      xml_def, re.S)
        if not m:
            raise RuntimeError(
                f"sharedItems do campo {nome} não localizado para acrescentar itens")
        prefixo, attrs, fechadura, filhos, sufixo = m.groups()
        novos_xml = "".join(_item_xml(t, v) for t, v in self._novos)
        novos_attrs = _recalcular_attrs(attrs, self.itens + self._novos)
        return (xml_def[:m.start()] + prefixo + novos_attrs + fechadura
                + filhos + novos_xml + sufixo + xml_def[m.end():])


def _item_xml(tipo: str, valor) -> str:
    if tipo == "n":
        return f'<n v="{valor}"/>'
    if tipo == "s":
        return f'<s v="{_escape_attr(valor)}"/>'
    if tipo == "d":
        return f'<d v="{valor}"/>'
    if tipo == "m":
        return "<m/>"
    raise RuntimeError(f"tipo de item inesperado: {tipo}")


def _recalcular_attrs(attrs: str, itens) -> str:
    """Reescreve count/minValue/maxValue/minDate/maxDate/contains* com base
    na lista final; os demais atributos (containsSemiMixedTypes, containsNonDate…)
    permanecem como estavam. Os contains*="0" originais são preservados quando o
    tipo continua ausente — o Excel não abre o arquivo sem eles (ex.:
    containsString="0" nos campos de data; causa do reparo de 09/09)."""
    tipos = {t for t, _ in itens}
    originais = dict(re.findall(r'(\w+)="([^"]*)"', attrs))
    novos_attr = {"count": str(len(itens))}
    numeros = [float(v) for t, v in itens if t == "n"]
    if numeros:
        inteiro = all(x.is_integer() for x in numeros)
        novos_attr["minValue"] = _numero(min(numeros))
        novos_attr["maxValue"] = _numero(max(numeros))
        novos_attr["containsNumber"] = "1"
        if inteiro:
            novos_attr["containsInteger"] = "1"
    datas = [v for t, v in itens if t == "d" and v]
    if datas:
        novos_attr["minDate"] = min(datas)
        novos_attr["maxDate"] = max(datas)
    for tipo, chave in (("s", "containsString"), ("n", "containsNumber"),
                        ("d", "containsDate"), ("m", "containsBlank")):
        if tipo in tipos:
            novos_attr[chave] = "1"
        elif originais.get(chave) == "0":
            novos_attr[chave] = "0"  # preserva o "0" explícito do Excel
    tipos_valor = {t for t in tipos if t in ("s", "n", "d")}
    if len(tipos_valor) > 1:
        novos_attr["containsMixedTypes"] = "1"
    restantes = _RE_ATTRS_RECALC.sub("", attrs)
    return restantes + "".join(f' {k}="{v}"' for k, v in novos_attr.items())


# ==============================================================================
# Edição da pivô (pivotTableN.xml)
# ==============================================================================
def _campo_da_pivot(xml: str, indice: int):
    ms = list(_RE_PIVOT_FIELD.finditer(xml))
    if indice >= len(ms):
        raise RuntimeError(f"pivô tem {len(ms)} pivotFields — não existe o {indice}")
    return ms[indice]


def campo_tem_itens(xml: str, indice: int) -> bool:
    return "<items" in _campo_da_pivot(xml, indice).group(0)


def _anexar_itens(xml: str, indice: int, novos: list[int], com_sd: bool) -> str:
    m = _campo_da_pivot(xml, indice)
    bloco = m.group(0)

    def _editar(cm):
        it = re.search(r"(<items\b[^>]*>)(.*?)(</items>)", cm, re.S)
        if not it:
            raise RuntimeError(f"pivotField {indice} sem <items> — nada a anexar")
        abertura = re.sub(r'\bcount="(\d+)"',
                          lambda mm: f'count="{int(mm.group(1)) + len(novos)}"',
                          it.group(1), count=1)
        extras = "".join(f'<item x="{x}" sd="0"/>' if com_sd else f'<item x="{x}"/>'
                         for x in novos)
        corpo = it.group(2)
        dm = re.search(r'<item t="default"[^>]*/>\s*$', corpo)
        if dm:
            # O Excel exige <item t="default".../> como ÚLTIMO item do <items>;
            # os novos itens entram ANTES dele.
            corpo = corpo[:dm.start()] + extras + dm.group(0)
        else:
            corpo += extras
        return (cm[:it.start()] + abertura + corpo + it.group(3)
                + cm[it.end():])
    return xml[:m.start()] + _editar(bloco) + xml[m.end():]


def anexar_itens_pivot(xml: str, indice: int, novos: list[int],
                       com_sd: bool = False) -> str:
    """Acrescenta <item x="N"/> (ou sd="0") ao <items> do campo, antes do
    <item t="default".../> final quando houver (o Excel exige que o default
    seja o último item)."""
    return _anexar_itens(xml, indice, novos, com_sd)


def colapsar_itens_pivot(xml: str, indice: int) -> str:
    """Marca sd="0" em TODOS os <item x="N"/> do campo (estado colapsado do
    arquivo de referência: convênios das pivôs 1–3 e da aba À Quitar)."""
    m = _campo_da_pivot(xml, indice)
    bloco = m.group(0)

    def _colapsar(mm):
        item = mm.group(0)
        if 'x="' not in item or 'sd="0"' in item:
            return item
        return re.sub(r"/>$", ' sd="0"/>', item, count=1)
    bloco = re.sub(r"<item\b[^>]*/>", _colapsar, bloco)
    return xml[:m.start()] + bloco + xml[m.end():]


def remover_refresh_on_load(xml: str) -> str:
    """Remove refreshOnLoad="1" da raiz (não recalcular pivô ao abrir)."""
    return re.sub(r'\s+refreshOnLoad="\d"', "", xml, count=1)


def anexar_itens_slicer(xml: str, novos: list[int]) -> str:
    """Acrescenta <i x="N" s="1"/> ao slicer (novos convênios entram marcados)."""
    def _editar(m):
        abertura = re.sub(r'\bcount="(\d+)"',
                          lambda mm: f'count="{int(mm.group(1)) + len(novos)}"',
                          m.group(1), count=1)
        extras = "".join(f'<i x="{x}" s="1"/>' for x in novos)
        return abertura + m.group(2) + extras + m.group(3)
    novo, n = re.subn(_RE_ITEMS_SLICER, _editar, xml, count=1)
    if n == 0:
        raise RuntimeError("bloco <items> não encontrado no slicer")
    return novo


# ==============================================================================
# Seleção de partes pelo conteúdo (o Excel pode renumerar as partes ao salvar)
# ==============================================================================
def nome_da_rel(partes: dict, nome_def: str) -> str:
    """Parte de records apontada pelo .rels da definition (Target relativo a
    xl/pivotCache/)."""
    nome_rels = nome_def.replace("xl/pivotCache/", "xl/pivotCache/_rels/") + ".rels"
    if nome_rels not in partes:
        raise RuntimeError(f"rels do cache não encontrado: {nome_rels}")
    m = re.search(r'Target="([^"]+)"', partes[nome_rels])
    if not m:
        raise RuntimeError(f"Target não encontrado em {nome_rels}")
    alvo = posixpath.normpath(posixpath.join("xl/pivotCache", m.group(1)))
    if alvo not in partes:
        raise RuntimeError(f"records do cache não encontrado: {alvo}")
    return alvo


def parte_cache_bd1(partes: dict) -> str:
    """Definition cuja fonte é a tabela BD_1 (worksheetSource name="BD_1")."""
    for nome in sorted(partes):
        if RE_DEF_CACHE.match(nome) and re.search(
                r'<worksheetSource[^>]*\bname="BD_1"', partes[nome]):
            return nome
    raise RuntimeError("cache da BD1 (fonte name=BD_1) não encontrado")


def parte_cache_bd2(partes: dict) -> str:
    """Definition cuja fonte é a BD2 (worksheetSource com ref="A1:I...")."""
    for nome in sorted(partes):
        if RE_DEF_CACHE.match(nome) and re.search(
                r'<worksheetSource[^>]*\bref="A1:I\d+"', partes[nome]):
            return nome
    raise RuntimeError("cache da BD2 (worksheetSource ref A1:I) não encontrado")


def partes_slicer_convenio(partes: dict, tab_ids) -> list[str]:
    """Slicers 'Convênio' ligados às pivôs com os tabIds dados."""
    achados = []
    for nome in sorted(partes):
        if not RE_SLICER.match(nome):
            continue
        texto = partes[nome]
        if 'sourceName="Convênio"' not in texto:
            continue
        for tab in tab_ids:
            if f'<pivotTable tabId="{tab}"' in texto:
                achados.append(nome)
                break
    return achados
