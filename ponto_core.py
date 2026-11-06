"""
==============================================================================
PONTO — REGRAS DE CÁLCULO E LEITURA DA PLANILHA
Módulo sem Streamlit: funções puras, testáveis isoladamente.
==============================================================================
"""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import openpyxl
import xlrd

JORNADA_SEG_QUI = 600
JORNADA_SEXTA = 540
TAMANHO_MAXIMO = 5 * 1024 * 1024
ASSINATURA_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

TIPOS_ESPECIAIS = ("ferias", "feriado", "atestado")

ROTULOS_TIPO = {
    "trabalho": "Trabalho",
    "ferias": "Férias",
    "feriado": "Feriado",
    "atestado": "Atestado",
    "outro": "Outro",
}

ROTULOS_SITUACAO = {
    "positivo": "Positivo",
    "trabalhado": "Trabalhado",
    "negativo": "Negativo",
    "extra": "Extra",
    "ferias": "Férias",
    "feriado": "Feriado",
    "atestado": "Atestado",
    "falta": "Falta",
    "hoje": "Hoje",
    "pendente": "Pendente",
    "futuro": "Futuro",
    "fim_de_semana": "Fim de semana",
    "outro": "Outro",
}


class PontoError(Exception):
    """Erro de leitura ou validação da planilha, com mensagem para a tela."""


@dataclass(frozen=True)
class DiaCalculado:
    data: date
    entrada: int | None
    saida: int | None
    tipo: str
    observacao: str | None
    origem: str
    situacao: str
    jornada: int
    trabalhados: int
    atraso: int
    saldo: int
    saldo_acumulado: int
    computado: bool


def normalizar_texto(valor) -> str:
    """Texto sem acento, sem espaços nas pontas e em minúsculas."""
    texto = "" if valor is None else str(valor)
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return sem_acento.strip().lower()


def tipo_especial(texto):
    """'Férias'/'feriado'/'atestado' (sem caixa/acento) -> tipo; senão None."""
    normalizado = normalizar_texto(texto)
    return normalizado if normalizado in TIPOS_ESPECIAIS else None


_RE_HORA = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")


def minutos_de(valor):
    """Converte time/datetime/fração do dia/texto HH:MM em minutos.

    Devolve None para vazio ou para texto que não é hora (ex.: 'Férias').
    """
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.hour * 60 + valor.minute
    if isinstance(valor, time):
        return valor.hour * 60 + valor.minute
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        fracao = float(valor) % 1
        return int(round(fracao * 24 * 60)) % (24 * 60)
    if isinstance(valor, str):
        achado = _RE_HORA.match(valor.strip())
        if not achado:
            return None
        horas, minutos = int(achado.group(1)), int(achado.group(2))
        if horas > 23 or minutos > 59:
            return None
        return horas * 60 + minutos
    return None


def minutos_para_hhmm(minutos):
    """Minutos -> 'HH:MM' (com sinal, se negativo); None -> '—'."""
    if minutos is None:
        return "—"
    sinal = "-" if minutos < 0 else ""
    total = abs(int(minutos))
    return f"{sinal}{total // 60:02d}:{total % 60:02d}"


def formatar_horas(minutos):
    """Minutos -> horas no padrão da planilha: 1102*60+37 -> '1.102:37'."""
    if minutos is None:
        return "—"
    sinal = "-" if minutos < 0 else ""
    total = abs(int(minutos))
    horas, mins = divmod(total, 60)
    return f"{sinal}{horas:,}".replace(",", ".") + f":{mins:02d}"


def jornada_do_dia(dia, tipo="trabalho"):
    """Jornada em minutos: 10h seg–qui, 9h sex, 0 sáb/dom e tipos especiais."""
    if normalizar_texto(tipo) in TIPOS_ESPECIAIS:
        return 0
    if dia.weekday() >= 5:
        return 0
    if dia.weekday() == 4:
        return JORNADA_SEXTA
    return JORNADA_SEG_QUI


def classificar(dia, entrada, saida, tipo="trabalho", hoje=None):
    """Situação do dia, na precedência do spec (seções 6.1 e 6.3).

    'outro' é texto não reconhecido: conta como pendência (6.1) e por isso
    não vira falta. Data futura nunca entra no saldo (6.3), mesmo com batida
    completa — por isso o futuro é checado antes das situações de batida.
    """
    hoje = hoje or date.today()
    tipo_normalizado = normalizar_texto(tipo)
    if tipo_normalizado in TIPOS_ESPECIAIS:
        return tipo_normalizado
    if tipo_normalizado == "outro":
        return "outro"
    if entrada is not None and saida is not None:
        if dia > hoje:
            return "futuro"
        if saida <= entrada:
            return "pendente"
        if dia.weekday() >= 5:
            return "extra"
        saldo = (saida - entrada) - jornada_do_dia(dia)
        if saldo > 0:
            return "positivo"
        if saldo < 0:
            return "negativo"
        return "trabalhado"
    if entrada is not None or saida is not None:
        return "pendente"
    if dia > hoje:
        return "futuro"
    if dia == hoje:
        return "hoje"
    if dia.weekday() >= 5:
        return "fim_de_semana"
    return "falta"


def calcular_dias(registros, hoje=None, preencher_lacunas=True):
    """Calcula cada dia e o saldo acumulado, em ordem de data.

    Com preencher_lacunas=True, datas sem registro entre a primeira e a
    última são tratadas como dia de trabalho sem batida — é o que faz um
    dia excluído voltar a contar como falta. A planilha completa não tem
    lacunas, então os números de referência não mudam.
    """
    hoje = hoje or date.today()
    por_data = {registro["data"]: dict(registro) for registro in registros}
    if preencher_lacunas and por_data:
        cursor = min(por_data)
        fim = max(por_data)
        while cursor <= fim:
            if cursor not in por_data:
                por_data[cursor] = {
                    "data": cursor, "entrada": None, "saida": None,
                    "tipo": "trabalho", "observacao": None,
                    "origem": "calculado"}
            cursor += timedelta(days=1)

    dias = []
    acumulado = 0
    for registro in (por_data[chave] for chave in sorted(por_data)):
        dia = registro["data"]
        entrada = minutos_de(registro.get("entrada"))
        saida = minutos_de(registro.get("saida"))
        tipo = normalizar_texto(registro.get("tipo") or "trabalho")
        situacao = classificar(dia, entrada, saida, tipo, hoje)
        jornada = jornada_do_dia(dia, tipo)

        tem_batida = (entrada is not None and saida is not None
                      and saida > entrada)
        if tem_batida and situacao in ("positivo", "trabalhado", "negativo", "extra"):
            trabalhados = saida - entrada
            atraso = max(0, entrada - 8 * 60)
        else:
            trabalhados = 0
            atraso = 0

        if situacao in ("positivo", "trabalhado", "negativo", "extra"):
            saldo = trabalhados - jornada
            computado = True
        elif situacao == "falta":
            saldo = -jornada
            computado = True
        else:
            saldo = 0
            computado = False

        if computado:
            acumulado += saldo

        dias.append(DiaCalculado(
            data=dia, entrada=entrada, saida=saida, tipo=tipo,
            observacao=registro.get("observacao"), origem=registro.get("origem", "upload"),
            situacao=situacao, jornada=jornada, trabalhados=trabalhados,
            atraso=atraso, saldo=saldo, saldo_acumulado=acumulado,
            computado=computado))
    return dias


def filtrar_periodo(dias, de=None, ate=None):
    """Dias no intervalo [de, ate], inclusive; None significa sem limite."""
    return [dia for dia in dias
            if (de is None or dia.data >= de) and (ate is None or dia.data <= ate)]


def totais_periodo(dias, de=None, ate=None, hoje=None):
    """Totais do período; o saldo é o acumulado até o fim (limitado a hoje)."""
    hoje = hoje or date.today()
    no_periodo = filtrar_periodo(dias, de, ate)
    limite = min(ate, hoje) if ate else hoje
    saldo = 0
    for dia in dias:
        if dia.data <= limite:
            saldo = dia.saldo_acumulado
        else:
            break
    return {
        "trabalhados": sum(d.trabalhados for d in no_periodo if d.computado),
        "jornada": sum(d.jornada for d in no_periodo if d.computado),
        "atraso": sum(d.atraso for d in no_periodo),
        "faltas": sum(1 for d in no_periodo if d.situacao == "falta"),
        "pendencias": sum(1 for d in no_periodo
                          if d.situacao in ("pendente", "outro")),
        "dias_trabalhados": sum(1 for d in no_periodo if d.computado
                                and d.situacao != "falta"),
        "saldo": saldo,
    }


def saldo_por_mes(dias, hoje=None):
    """Saldo de cada mês até hoje.

    Entram os meses com pelo menos um registro de tipo 'trabalho' (mesmo que
    o saldo seja 0, como novembro); meses só de férias/feriado/atestado
    ficam de fora (como maio).
    """
    hoje = hoje or date.today()
    meses = {}
    for dia in dias:
        if dia.data > hoje:
            continue
        chave = f"{dia.data.year:04d}-{dia.data.month:02d}"
        if dia.tipo == "trabalho":
            meses.setdefault(chave, 0)
        if dia.computado:
            meses[chave] = meses.get(chave, 0) + dia.saldo
    return sorted(meses.items())


def evolucao_saldo(dias, ate=None, hoje=None):
    """(data, saldo do dia, saldo acumulado) dos dias computados até o limite."""
    hoje = hoje or date.today()
    limite = min(ate, hoje) if ate else hoje
    return [(dia.data, dia.saldo, dia.saldo_acumulado)
            for dia in dias if dia.data <= limite and dia.computado]


def rotulo_situacao(situacao):
    return ROTULOS_SITUACAO.get(situacao, situacao)


def rotulo_tipo(tipo):
    return ROTULOS_TIPO.get(tipo, tipo)


@dataclass
class LeituraPlanilha:
    registros: list
    avisos: list
    periodo_de: date
    periodo_ate: date
    linhas: int


def _celula(linha, indice):
    if indice is None or indice >= len(linha):
        return None
    return linha[indice]


def _mapear_colunas(cabecalho):
    """Índices das colunas; prefere 'Data' a 'Dia' (o 'Dia' da planilha é o
    nome do dia da semana, mas no formato antigo DIA é a própria data)."""
    colunas = {"data": None, "entrada": None, "saida": None,
               "status": None, "jornada": None}
    for indice, nome in enumerate(cabecalho):
        if nome == "data":
            colunas["data"] = indice
            break
    if colunas["data"] is None:
        for indice, nome in enumerate(cabecalho):
            if nome == "dia":
                colunas["data"] = indice
                break
    for indice, nome in enumerate(cabecalho):
        if nome == "entrada":
            colunas["entrada"] = indice
        elif nome in ("saida",):
            colunas["saida"] = indice
        elif nome == "status":
            colunas["status"] = indice
        elif nome == "jornada":
            colunas["jornada"] = indice
    return colunas


def _data_de(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()
        for formato in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(texto, formato).date()
            except ValueError:
                continue
    return None


def _texto(valor):
    if valor is None:
        return None
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip() or None


def _interpretar_batidas(aba, numero, bruto_entrada, bruto_saida,
                         status, avisos):
    """Devolve (tipo, entrada_min, saida_min, observacao).

    Texto especial em Entrada/Saída define o tipo e descarta horários.
    Texto desconhecido vira 'outro' (pendência) e gera aviso.
    """
    especial = None
    texto_desconhecido = False
    for bruto in (bruto_entrada, bruto_saida):
        if isinstance(bruto, str) and bruto.strip():
            achado = tipo_especial(bruto)
            if achado:
                especial = achado
            elif minutos_de(bruto) is None:
                texto_desconhecido = True

    if especial:
        if minutos_de(bruto_entrada) is not None or minutos_de(bruto_saida) is not None:
            avisos.append(
                f"Aba '{aba}', linha {numero}: horário ignorado — o dia está "
                f"marcado como {ROTULOS_TIPO[especial]}.")
        return especial, None, None, status
    if texto_desconhecido:
        avisos.append(
            f"Aba '{aba}', linha {numero}: texto não reconhecido em "
            "Entrada/Saída; conta como pendência.")
        return "outro", None, None, status

    entrada = minutos_de(bruto_entrada)
    saida = minutos_de(bruto_saida)
    if (entrada is None and saida is None and status
            and tipo_especial(status)):
        return tipo_especial(status), None, None, status
    return "trabalho", entrada, saida, status


def _aba_tem_dados(linhas, colunas):
    for linha in linhas[1:]:
        for chave in ("entrada", "saida", "status"):
            if _celula(linha, colunas[chave]) not in (None, ""):
                return True
    return False


def _processar_aba(aba, linhas, vistos):
    if not linhas:
        return [], [f"Aba '{aba}' ignorada: sem dados."]
    cabecalho = [normalizar_texto(c) for c in linhas[0]]
    colunas = _mapear_colunas(cabecalho)
    if (colunas["data"] is None
            or (colunas["entrada"] is None and colunas["saida"] is None
                and colunas["status"] is None)):
        return [], [f"Aba '{aba}' ignorada: cabeçalho não reconhecido "
                    "(esperado Data, Entrada, Saída e Status)."]
    if not _aba_tem_dados(linhas, colunas):
        return [], [f"Aba '{aba}' ignorada: sem dados."]

    registros = []
    avisos = []
    for numero, linha in enumerate(linhas[1:], start=2):
        bruto_data = _celula(linha, colunas["data"])
        if bruto_data in (None, ""):
            if any(_celula(linha, colunas[chave]) not in (None, "")
                   for chave in ("entrada", "saida", "status")):
                avisos.append(f"Aba '{aba}', linha {numero}: linha sem data "
                              "ignorada.")
            continue
        dia = _data_de(bruto_data)
        if dia is None:
            avisos.append(f"Aba '{aba}', linha {numero}: data "
                          f"'{bruto_data}' não reconhecida; linha ignorada.")
            continue
        if dia in vistos:
            raise PontoError(
                f"A data {dia:%d/%m/%Y} aparece mais de uma vez na planilha.")
        vistos.add(dia)

        status = _texto(_celula(linha, colunas["status"]))
        tipo, entrada, saida, observacao = _interpretar_batidas(
            aba, numero, _celula(linha, colunas["entrada"]),
            _celula(linha, colunas["saida"]), status, avisos)

        if (colunas["jornada"] is not None and tipo == "trabalho"
                and entrada is not None and saida is not None and saida > entrada
                and dia.weekday() < 5):
            jornada_planilha = minutos_de(_celula(linha, colunas["jornada"]))
            jornada_regra = jornada_do_dia(dia)
            if (jornada_planilha is not None
                    and jornada_planilha != jornada_regra):
                avisos.append(
                    f"Aba '{aba}', linha {numero}: jornada de "
                    f"{minutos_para_hhmm(jornada_planilha)} difere da regra "
                    f"({minutos_para_hhmm(jornada_regra)}); vale a regra do "
                    "sistema.")

        registros.append({
            "data": dia,
            "entrada": minutos_para_hhmm(entrada) if entrada is not None else None,
            "saida": minutos_para_hhmm(saida) if saida is not None else None,
            "tipo": tipo,
            "observacao": observacao,
        })
    return registros, avisos


def _linhas_xls(aba, datemode):
    linhas = []
    for numero in range(aba.nrows):
        linha = []
        for coluna in range(aba.ncols):
            celula = aba.cell(numero, coluna)
            valor = celula.value
            if celula.ctype == xlrd.XL_CELL_DATE:
                valor = xlrd.xldate_as_datetime(valor, datemode)
            linha.append(valor)
        linhas.append(linha)
    return linhas


def ler_planilha(conteudo, nome_arquivo=""):
    """Lê .xlsx/.xls e devolve LeituraPlanilha; nada é gravado.

    Rejeita arquivo protegido, formato inválido, data duplicada e planilha
    sem nenhuma aba no formato esperado.
    """
    if not conteudo:
        raise PontoError("O arquivo está vazio.")
    if len(conteudo) > TAMANHO_MAXIMO:
        raise PontoError("O arquivo tem mais de 5 MB. Envie uma planilha menor.")

    if conteudo.startswith(ASSINATURA_OLE2):
        if "EncryptedPackage".encode("utf-16le") in conteudo:
            raise PontoError(
                "Este arquivo está protegido por senha. Abra no Excel, salve "
                "uma cópia sem senha e envie a cópia.")
        try:
            livro = xlrd.open_workbook(file_contents=conteudo)
        except Exception as erro:
            raise PontoError(f"Não foi possível abrir o arquivo .xls: {erro}") from erro
        abas = [(aba.name, _linhas_xls(aba, livro.datemode))
                for aba in livro.sheets()]
    elif conteudo[:2] == b"PK":
        try:
            livro = openpyxl.load_workbook(io.BytesIO(conteudo),
                                           data_only=True, read_only=True)
        except Exception as erro:
            raise PontoError(f"Não foi possível abrir o arquivo .xlsx: {erro}") from erro
        try:
            abas = [(aba.title,
                     [list(linha) for linha in aba.iter_rows(values_only=True)])
                    for aba in livro.worksheets]
        finally:
            livro.close()
    else:
        raise PontoError("Formato não reconhecido. Envie um arquivo .xlsx ou .xls.")

    resultados = []
    for nome, linhas in abas:
        registros_aba, avisos_aba = _processar_aba(nome, linhas, set())
        resultados.append((nome, registros_aba, avisos_aba))

    if not any(registros_aba for _, registros_aba, _ in resultados):
        raise PontoError(
            "Nenhuma aba com o formato esperado foi encontrada. A planilha "
            "precisa das colunas Data, Entrada, Saída e Status.")

    ano_recente = max(r["data"].year
                      for _, registros_aba, _ in resultados
                      for r in registros_aba)

    registros = []
    avisos = []
    for nome, registros_aba, avisos_aba in resultados:
        if not registros_aba:
            avisos.extend(avisos_aba)
            continue
        if max(r["data"].year for r in registros_aba) < ano_recente:
            avisos.append(
                f"Aba '{nome}' ignorada: vale a aba do ano mais recente "
                f"({ano_recente}).")
            continue
        registros.extend(registros_aba)
        avisos.extend(avisos_aba)

    vistos = set()
    for registro in registros:
        if registro["data"] in vistos:
            raise PontoError(
                f"A data {registro['data']:%d/%m/%Y} aparece mais de uma vez "
                "na planilha.")
        vistos.add(registro["data"])

    incompletas = sum(1 for r in registros
                      if bool(r["entrada"]) != bool(r["saida"]))
    if incompletas:
        avisos.append(f"{incompletas} batida(s) incompleta(s) encontrada(s).")

    registros.sort(key=lambda r: r["data"])
    return LeituraPlanilha(
        registros=registros, avisos=avisos,
        periodo_de=registros[0]["data"], periodo_ate=registros[-1]["data"],
        linhas=len(registros))
