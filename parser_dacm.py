"""
==============================================================================
PARSER DO DACM (FORMATO ANS) — CONTAS A RECEBER
Lê DACMs exportados do site dos convênios (Excel .xls/.xlsx) e devolve uma
estrutura única: metadados + guias + itens. Leitura SEMPRE somente-leitura.

Formato ANS (campos numerados 1-48): cada aba = 1 guia de um protocolo;
guias grandes são quebradas em abas consecutivas (mesma guia, itens
continuados) — o parser concatena. Campos localizados por RÓTULO de linha
(tolera deslocamentos); abas sem guia são ignoradas com aviso.
==============================================================================
"""
import os
import re

_RE_DATA_BR = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


def parsear_data_br(texto):
    """'16/07/2026' -> '2026-07-16'. Entrada que não é dd/mm/aaaa volta como está."""
    texto = (texto or "").strip()
    m = _RE_DATA_BR.match(texto)
    if m:
        dia, mes, ano = m.groups()
        return f"{ano}-{mes}-{dia}"
    return texto


class _Folha:
    """Abstração de uma aba: matriz de células [linha][coluna] -> valor."""

    def __init__(self, nome, matriz):
        self.nome = nome
        self.matriz = matriz

    def cel(self, lin, col):
        try:
            return self.matriz[lin][col]
        except IndexError:
            return ""


def _ler_livro(caminho):
    """Lê o arquivo (.xls via xlrd; .xlsx via openpyxl) -> lista de _Folha."""
    ext = os.path.splitext(caminho)[1].lower()
    if ext == ".xls":
        import xlrd
        wb = xlrd.open_workbook(caminho)
        folhas = []
        for nome in wb.sheet_names():
            sh = wb.sheet_by_name(nome)
            folhas.append(_Folha(nome, [sh.row_values(i) for i in range(sh.nrows)]))
        return folhas
    if ext == ".xlsx":
        import openpyxl
        from datetime import date, datetime
        folhas = []
        for ws in openpyxl.load_workbook(caminho, data_only=True).worksheets:
            matriz = []
            for linha in ws.iter_rows(values_only=True):
                valores = []
                for v in linha:
                    if isinstance(v, (datetime, date)):
                        valores.append(v.strftime("%d/%m/%Y"))
                    else:
                        valores.append(v)
                matriz.append(valores)
            folhas.append(_Folha(ws.title, matriz))
        return folhas
    raise ValueError("Formato não suportado. Envie um arquivo .xls ou .xlsx.")


def _linha_do_rotulo(folha, rotulo, col=1):
    """Linha da folha cuja célula (lin, col) contém o rótulo; None se não há."""
    for i in range(200):  # cabeçalhos ficam no topo da folha
        if rotulo in str(folha.cel(i, col) or ""):
            return i
    return None


def _valor(folha, rotulo, col=1, desloc=1, col_valor=None):
    """Valor da célula logo abaixo do rótulo (ou na mesma linha, se desloc=0)."""
    lin = _linha_do_rotulo(folha, rotulo, col)
    if lin is None:
        return ""
    col_alvo = col if col_valor is None else col_valor
    valor = folha.cel(lin + desloc, col_alvo)
    if isinstance(valor, float):
        return valor
    return str(valor or "").strip()


def _numero(valor):
    """float do valor (float direto ou texto '1.234,56'/'0.24'); None se vazio."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip()
    if not texto:
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def _num_dacm(folha):
    """'2-Nº' fica na mesma linha do rótulo, na coluna seguinte."""
    lin = _linha_do_rotulo(folha, "2-Nº", 22)
    if lin is None:
        return ""
    return str(folha.cel(lin, 23) or "").strip()


def _extrair_folha(folha):
    """Guia da folha (dict) ou None se a folha não tiver guia do prestador."""
    guia_prestador = _valor(folha, "14 - NÚMERO DA GUIA DO PRESTADOR", 1)
    if not guia_prestador:
        return None
    itens = []
    lin_itens = _linha_do_rotulo(folha, "25 - DATA DE REALIZAÇÃO", 1)
    if lin_itens is not None:
        for lin in range(lin_itens + 1, 200):
            if str(folha.cel(lin, 1) or "").strip().startswith("TOTAL"):
                break
            desc = str(folha.cel(lin, 8) or "").strip()
            if not desc:
                break
            itens.append({
                "data_realizacao": parsear_data_br(str(folha.cel(lin, 1) or "").strip()),
                "tabela": str(folha.cel(lin, 3) or "").strip(),
                "cod_procedimento": str(folha.cel(lin, 4) or "").strip(),
                "descricao": desc,
                "grau_participacao": str(folha.cel(lin, 11) or "").strip(),
                "quantidade": _numero(folha.cel(lin, 15)) or 0,
                "vl_informado": _numero(folha.cel(lin, 13)) or 0,
                "vl_processado": _numero(folha.cel(lin, 16)) or 0,
                "vl_liberado": _numero(folha.cel(lin, 19)) or 0,
                "vl_glosa": _numero(folha.cel(lin, 24)) or 0,
                "cod_glosa": str(folha.cel(lin, 26) or "").strip(),
            })
    return {
        "lote": _valor(folha, "9 -  NÚMERO DO LOTE", 1),
        "protocolo": _valor(folha, "10 - NÚMERO DO PROTOCOLO", 4),
        "data_protocolo": parsear_data_br(_valor(folha, "11 - DATA DO PROTOCOLO", 8)),
        "cod_situacao_protocolo": _valor(folha, "13 - CÓDIGO DA SITUAÇÃO DO PROTOCOLO", 17),
        "guia_prestador": guia_prestador,
        "guia_operadora": _valor(folha, "15 - NÚMERO DA GUIA ATRIBUÍDO PELA OPERADORA", 10),
        "senha": _valor(folha, "16 - SENHA", 16),
        "beneficiario": _valor(folha, "17 - NOME DO BENEFICIÁRIO", 1),
        "nome_social": _valor(folha, "48 - NOME SOCIAL DO BENEFICIÁRIO", 1),
        "carteira": _valor(folha, "18 - NÚMERO DA CARTEIRA", 16),
        "data_inicio_fat": parsear_data_br(_valor(folha, "19 - DATA DO  INÍCIO DO FATURAMENTO", 1)),
        "data_fim_fat": parsear_data_br(_valor(folha, "21 - DATA DO FIM DO FATURAMENTO", 9)),
        "cod_situacao_guia": _valor(folha, "24 - CÓDIGO DA SITUAÇÃO DA GUIA", 21),
        "vl_informado": _numero(_valor(folha, "36 - VALOR INFORMADO DA GUIA(R$)", 1)) or 0,
        "vl_processado": _numero(_valor(folha, "37 - VALOR PROCESSADO DA GUIA(R$)", 8)) or 0,
        "vl_liberado": _numero(_valor(folha, "38 - VALOR LIBERADO DA GUIA(R$)", 11)) or 0,
        "vl_glosa": _numero(_valor(folha, "39 - VALOR GLOSA DA GUIA(R$)", 16)) or 0,
        "itens": itens,
    }


def _metadados(livro):
    """Metadados do arquivo, lidos da primeira folha com conteúdo."""
    folha = livro[0]
    return {
        "num_dacm": _num_dacm(folha),
        "operadora": _valor(folha, "3 - NOME DA OPERADORA", 4),
        "registro_ans": _valor(folha, "1 - REGISTRO ANS", 1),
        "cnpj": _valor(folha, "4 - CNPJ DA OPERADORA", 17),
        "data_emissao": parsear_data_br(_valor(folha, "5 - DATA DE EMISSÃO", 24)),
        "codigo_na_operadora": _valor(folha, "6 - CÓDIGO NA OPERADORA", 1),
        "contratado": _valor(folha, "7 - NOME DO CONTRATADO", 4),
        "cnes": _valor(folha, "8 - CÓDIGO CNES", 24),
        "tot_geral_informado": _numero(_valor(folha, "44 - VALOR INFORMADO GERAL(R$)", 1)) or 0,
        "tot_geral_processado": _numero(_valor(folha, "45 - VALOR PROCESSADO GERAL(R$)", 8)) or 0,
        "tot_geral_liberado": _numero(_valor(folha, "46 - VALOR LIBERADO GERAL(R$)", 11)) or 0,
        "tot_geral_glosa": _numero(_valor(folha, "47 - VALOR GLOSA GERAL(R$)", 16)) or 0,
    }


def extrair_dacm(livro):
    """Núcleo do parser: folhas -> {metadados, guias, avisos}. ValueError se
    nenhuma guia for encontrada."""
    avisos = []
    guias = []
    for folha in livro:
        guia = _extrair_folha(folha)
        if guia is None:
            avisos.append(f"{folha.nome}: ignorada (sem guia)")
            continue
        chave = (guia["lote"], guia["protocolo"], guia["guia_prestador"])
        anterior = next((g for g in guias
                         if (g["lote"], g["protocolo"], g["guia_prestador"]) == chave),
                        None)
        if anterior is not None:
            # abas consecutivas da mesma guia: concatena itens e usa os
            # totais da última aba (idênticos em todas)
            anterior["itens"].extend(guia["itens"])
            anterior["vl_informado"] = guia["vl_informado"]
            anterior["vl_processado"] = guia["vl_processado"]
            anterior["vl_liberado"] = guia["vl_liberado"]
            anterior["vl_glosa"] = guia["vl_glosa"]
        else:
            guias.append(guia)
    if not guias:
        raise ValueError("Nenhuma guia encontrada neste arquivo. "
                         "Confira se é um DACM no formato ANS (Excel).")
    return {"metadados": _metadados(livro), "guias": guias, "avisos": avisos}


def parse_dacm_ans(caminho):
    """Lê o arquivo do DACM ANS e devolve {metadados, guias, avisos}."""
    return extrair_dacm(_ler_livro(caminho))
