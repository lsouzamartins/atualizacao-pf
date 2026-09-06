# Dashboard de Glosas (Contas a Receber) — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir o sistema "Contas a Receber" dentro do app Atualização PF: parser do DACM ANS (Excel), banco separado, portal pós-login, upload com prévia, dashboard com 4 blocos e painel de recursos de glosa.

**Architecture:** Módulos novos `parser_dacm.py` (leitura somente-leitura do DACM ANS) e `banco_glosas.py` (SQLite `dados/dacm_glosas.db`) testados com TDD; páginas Streamlit finas em `app_pages/`; navegação condicional por `usuarios.acesso_contas_receber`.

**Tech Stack:** Python 3.14, Streamlit 1.60.0, SQLite (WAL), xlrd 2.0.2 (já no requirements), openpyxl 3.1.5 (já), pandas 3.0.3 (já), **plotly>=6.0 (NOVO)**, pytest.

**Spec:** `docs/superpowers/specs/2026-09-06-dashboard-glosas-design.md` — o plano argumenta a partir da spec; conflitos resolvem contra ela.

## Global Constraints

- Pt-br com acentuação correta em comentários, docstrings e textos de tela.
- R17: a senha root do VPS NUNCA aparece em arquivo do repo (nem neste plano) — o valor é fornecido pelo Leonardo na mensagem de autorização do deploy, em script temporário fora do repo, apagado após uso.
- `G:\Atualização PF` (pendrive) e `G:\Posição Financeira` nunca são editados; o DACM `G:\Dashboard - Contas a Receber\...\DACM _PORTO_SAÚDE_15.07.26.xls` é SOMENTE LEITURA (testes nunca o reescrevem).
- Banco CR em `dados/dacm_glosas.db` — SEPARADO do `dados/pf.db`. Conexão com `row_factory=sqlite3.Row`, `PRAGMA journal_mode=WAL`, `foreign_keys=ON` (padrão de `banco.py`).
- Status (strings EXATAS, ordem de exibição): `"A iniciar recurso"`, `"Em análise"`, `"Glosa Recebida"`, `"Recurso Negado"`, `"Livre de Glosa"`.
- Cores dos status: A iniciar recurso `#3b82f6` · Em análise `#f59e0b` · Glosa Recebida `#22c55e` · Recurso Negado `#ef4444` · Livre de Glosa `#94a3b8`.
- Status inicial de guia nova: `vl_glosa > 0` → `"A iniciar recurso"`; senão `"Livre de Glosa"`.
- Reenvio (chave `UNIQUE(convenio_id, guia_prestador)`): atualiza valores e itens, **mantém** `status_recurso`/`vl_recuperado`/`observacao`; se glosa anterior `> 0.005` e nova `== 0` → `aviso_glosa_zerada=1`. Toda mudança de status grava em `recursos_hist`.
- Datas ISO (`aaaa-mm-dd`) no banco; exibição via `formatar_data_br` do `ui_comum.py`.
- Nome do sistema na tela: **"Contas a Receber"**; nav usa prefixos "PF ·" e "CR ·" quando o acesso CR está ativo; sem acesso, nav e títulos ficam EXATAMENTE como hoje.
- Páginas CR entram no nav somente se `st.session_state["usuario"]["acesso_contas_receber"]` for verdadeiro.
- Nomes de arquivo upados: sanitizados (regex + `urllib.parse.quote`), nunca escapam de `dados/uploads_dacm/`.
- Padrões do app: `icone(nome, tamanho, cor)` para títulos, rodapé `<div class="app-footer">{VERSAO}</div>` em toda página nova, `injetar_css()` global.
- Testes: pytest em `tests/`, comando `python -m pytest tests/<arquivo> -v` a partir de `G:/Atualização PF Nuvem`.

---

### Task 1: Parser do DACM ANS (`parser_dacm.py`)

**Files:**
- Create: `parser_dacm.py`
- Test: `tests/test_parser_dacm.py`

**Interfaces:**
- Produces: `parse_dacm_ans(caminho) -> dict` com `{metadados, guias, avisos}` (usado pelas Tasks 2 e 7); `extrair_dacm(livro)` (núcleo testável); `parsear_data_br(texto)` (reusado nos testes).

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_parser_dacm.py`:

```python
"""Testes do parser do DACM ANS (formato das abas do arquivo da Porto Saúde)."""
import os

import pytest

import parser_dacm
from parser_dacm import _Folha, extrair_dacm, parse_dacm_ans, parsear_data_br

CAMINHO_PORTO = (r"G:\Dashboard - Contas a Receber\Convênios\Porto Saúde"
                 r"\DACM _PORTO_SAÚDE_15.07.26.xls")


def _folha_ans(nome, linhas):
    """Folha fake a partir de lista de linhas (listas de 27 colunas completadas com '')."""
    matriz = []
    for linha in linhas:
        matriz.append(list(linha) + [""] * (27 - len(linha)))
    return _Folha(nome, matriz)


def _cabecalho_fake(prot="20274355", lote="272327", guia="25489130",
                    op="12474769", benef="JEFERSON PASSOS PEREIRA"):
    return [
        ["", "", "", "", "", "", "DEMONSTRATIVO DE ANÁLISE DE CONTA",
         "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "2-Nº", "14880859"],
        ["", "1 - REGISTRO ANS", "", "", "3 - NOME DA OPERADORA", "", "", "", "", "",
         "", "", "", "", "", "", "", "4 - CNPJ DA OPERADORA", "", "", "", "", "",
         "5 - DATA DE EMISSÃO"],
        ["", "000582", "", "", "Porto Seguro - Seguro Saude S.A.", "", "", "", "",
         "", "", "", "", "", "", "", "04540010000170", "", "", "", "", "", "16/07/2026"],
        ["", "9 -  NÚMERO DO LOTE", "", "", "10 - NÚMERO DO PROTOCOLO", "", "", "",
         "11 - DATA DO PROTOCOLO", "", "", "12 - CÓDIGO DA GLOSA DO PROTOCOLO",
         "", "", "", "", "13 - CÓDIGO DA SITUAÇÃO DO PROTOCOLO"],
        ["", lote, "", "", prot, "", "", "", "12/06/2026", "", "", "", "", "", "",
         "", "6"],
        ["", "14 - NÚMERO DA GUIA DO PRESTADOR", "", "", "", "", "", "", "", "",
         "15 - NÚMERO DA GUIA ATRIBUÍDO PELA OPERADORA", "", "", "", "", "",
         "16 - SENHA"],
        ["", guia, "", "", "", "", "", "", "", "", op, "", "", "", "", "", ""],
        ["", "17 - NOME DO BENEFICIÁRIO", "", "", "", "", "", "", "", "", "", "",
         "", "", "", "", "18 - NÚMERO DA CARTEIRA"],
        ["", benef, "", "", "", "", "", "", "", "", "", "", "", "", "", "",
         "2234973211568118"],
        ["", "19 - DATA DO  INÍCIO DO FATURAMENTO", "", "", "", "", "", "20 - HORA",
         "", "21 - DATA DO FIM DO FATURAMENTO", "", "22 - HORA", "", "", "",
         "23 - CÓDIGO DA GLOSA DA GUIA", "", "", "", "", "24 - CÓDIGO DA SITUAÇÃO DA GUIA"],
        ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
         "", "", "", "6"],
        ["", "25 - DATA DE REALIZAÇÃO", "", "26 - TABELA", "27 - CÓDIGO DO PROCEDIMENTO",
         "", "", "", "28 - DESCRIÇÃO", "", "", "29 - GRAU DE PARTICIPAÇÃO", "",
         "30 - VALOR INFORMADO", "", "31 - QUANT. EXECUTADA", "32 - VALOR PROCESSADO",
         "", "", "33 - VALOR\nLIBERADO", "", "", "", "34 - VALOR GLOSA", "",
         "35 - CÓDIGO DA \nGLOSA"],
        ["", "18/05/2026", "", "22", "10101039", "", "", "", "CONSULTA EM PRONTO SOCORRO",
         "", "", "08", "", 44.22, "", 1.0, 44.22, "", "", 44.22, "", "", "", ""],
        ["", "18/05/2026", "", "22", "40302040", "", "", "", "GLICOSE - PESQUISA E/OU DOSAGEM",
         "", "", "", "", 6.3, "", 1.0, 6.3, "", "", 6.06, "", "", "", 0.24, "", "1714"],
        ["", "TOTAL DA GUIA"],
        ["", "36 - VALOR INFORMADO DA GUIA(R$)", "", "", "", "", "", "", "37 - VALOR PROCESSADO DA GUIA(R$)",
         "", "", "38 - VALOR LIBERADO DA GUIA(R$)", "", "", "", "39 - VALOR GLOSA DA GUIA(R$)"],
        ["", 50.52, "", "", "", "", "", "", 50.52, "", "", 50.28, "", "", "", 0.24],
        ["", "TOTAL DO PROTOCOLO"],
        ["", "40 - VALOR INFORMADO DO PROTOCOLO(R$)", "", "", "", "", "", "", "41 - VALOR PROCESSADO DO PROTOCOLO(R$)",
         "", "", "42 - VALOR LIBERADO DO PROTOCOLO(R$)", "", "", "", "43 - VALOR GLOSA DO PROTOCOLO(R$)"],
        ["", 1978.97, "", "", "", "", "", "", 1978.97, "", "", 1943.05, "", "", "", 35.92],
        ["", "TOTAL GERAL"],
        ["", "44 - VALOR INFORMADO GERAL(R$)", "", "", "", "", "", "", "45 - VALOR PROCESSADO GERAL(R$)",
         "", "", "46 - VALOR LIBERADO GERAL(R$)", "", "", "", "47 - VALOR GLOSA GERAL(R$)"],
        ["", 25276.6, "", "", "", "", "", "", 25276.6, "", "", 24613.4, "", "", "", 663.2],
    ]


def _livro_com_duas_folhas_da_mesma_guia():
    folha1 = _folha_ans("Sheet1", _cabecalho_fake())
    # segunda aba da MESMA guia: só os itens continuados + totais repetidos
    linhas2 = _cabecalho_fake()[:12] + [
        ["", "18/05/2026", "", "20", "0000075456", "", "", "", "AGUA DESTILADA 10ML AMP",
         "", "", "", "", 0.77, "", 1.0, 0.77, "", "", 0.77, "", "", "", ""],
        ["", "TOTAL DA GUIA"],
        ["", "36 - VALOR INFORMADO DA GUIA(R$)", "", "", "", "", "", "", "37 - VALOR PROCESSADO DA GUIA(R$)",
         "", "", "38 - VALOR LIBERADO DA GUIA(R$)", "", "", "", "39 - VALOR GLOSA DA GUIA(R$)"],
        ["", 51.29, "", "", "", "", "", "", 51.29, "", "", 51.05, "", "", "", 0.24],
    ] + _cabecalho_fake()[18:]
    folha2 = _folha_ans("Sheet2", linhas2)
    return [_Folha("Sheet3", [["sem conteúdo"]]), folha1, folha2]


def test_parsear_data_br_converte_e_preserva_nao_iso():
    assert parsear_data_br("16/07/2026") == "2026-07-16"
    assert parsear_data_br("2026-07-16") == "2026-07-16"
    assert parsear_data_br("") == ""


def test_extrai_guia_com_itens_e_totais():
    livro = [_folha_ans("Sheet1", _cabecalho_fake())]
    parsed = extrair_dacm(livro)
    assert parsed["metadados"]["num_dacm"] == "14880859"
    assert parsed["metadados"]["operadora"] == "Porto Seguro - Seguro Saude S.A."
    assert parsed["metadados"]["data_emissao"] == "2026-07-16"
    assert parsed["metadados"]["tot_geral_glosa"] == 663.2
    assert len(parsed["guias"]) == 1
    guia = parsed["guias"][0]
    assert guia["guia_prestador"] == "25489130"
    assert guia["guia_operadora"] == "12474769"
    assert guia["beneficiario"] == "JEFERSON PASSOS PEREIRA"
    assert guia["data_protocolo"] == "2026-06-12"
    assert guia["cod_situacao_guia"] == "6"
    assert guia["vl_glosa"] == 0.24
    assert len(guia["itens"]) == 2
    glosado = [i for i in guia["itens"] if i["vl_glosa"] > 0]
    assert len(glosado) == 1
    assert glosado[0]["cod_glosa"] == "1714"
    assert glosado[0]["descricao"] == "GLICOSE - PESQUISA E/OU DOSAGEM"


def test_concatena_abas_consecutivas_da_mesma_guia():
    livro = _livro_com_duas_folhas_da_mesma_guia()
    parsed = extrair_dacm(livro)
    assert len(parsed["guias"]) == 1
    guia = parsed["guias"][0]
    assert len(guia["itens"]) == 3  # 2 + 1 continuados
    # totais vêm da ÚLTIMA aba da guia
    assert guia["vl_informado"] == 51.29


def test_folha_sem_guia_vira_aviso():
    livro = _livro_com_duas_folhas_da_mesma_guia()
    parsed = extrair_dacm(livro)
    assert any("Sheet3" in a for a in parsed["avisos"])


def test_sem_nenhuma_guia_levanta_erro_claro():
    livro = [_folha_ans("Sheet1", [["vazia"]])]
    with pytest.raises(ValueError, match="Nenhuma guia encontrada"):
        extrair_dacm(livro)


def test_integracao_xlsx_ans(tmp_path):
    """Caminho completo: .xlsx real (openpyxl) -> parse_dacm_ans."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    for linha in _cabecalho_fake():
        ws.append(linha)
    ws2 = wb.create_sheet("Sheet2")
    for linha in _cabecalho_fake()[:12] + [["", "TOTAL DA GUIA"]]:
        ws2.append(linha)
    caminho = tmp_path / "dacm_teste.xlsx"
    wb.save(caminho)
    parsed = parse_dacm_ans(str(caminho))
    assert len(parsed["guias"]) == 1
    assert parsed["metadados"]["num_dacm"] == "14880859"


@pytest.mark.skipif(not os.path.exists(CAMINHO_PORTO),
                    reason="pendrive com o DACM da Porto Saúde não está conectado")
def test_arquivo_real_porto_saude():
    """Valida o parser contra o DACM real da Porto Saúde (somente leitura)."""
    parsed = parse_dacm_ans(CAMINHO_PORTO)
    assert parsed["metadados"]["num_dacm"] == "14880859"
    assert parsed["metadados"]["operadora"] == "Porto Seguro - Seguro Saude S.A."
    assert parsed["metadados"]["tot_geral_glosa"] == 663.2
    # 66 abas; guias quebradas concatenam (73685102 = 5 abas, 74698014 = 5 abas)
    assert 55 <= len(parsed["guias"]) <= 60
    vanessa = next(g for g in parsed["guias"] if g["guia_prestador"] == "73685102")
    assert len(vanessa["itens"]) == 82
    maria = next(g for g in parsed["guias"] if g["guia_prestador"] == "74698014")
    assert len(maria["itens"]) == 71
    # nenhum item com descrição vazia entre as guias
    assert all(i["descricao"] for g in parsed["guias"] for i in g["itens"])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_parser_dacm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'parser_dacm'`

- [ ] **Step 3: Implementar o parser**

Criar `parser_dacm.py`:

```python
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_parser_dacm.py -v`
Expected: PASS (incluindo `test_arquivo_real_porto_saude` se o pendrive G: estiver conectado; senão 1 skip)

- [ ] **Step 5: Commit**

```bash
git add parser_dacm.py tests/test_parser_dacm.py
git commit -m "feat: parser do DACM ANS (Excel) com concatenação de guias quebradas"
```

---

### Task 2: Banco do Contas a Receber (`banco_glosas.py`)

**Files:**
- Create: `banco_glosas.py`
- Test: `tests/test_banco_glosas.py`

**Interfaces:**
- Consumes: `parse_dacm_ans` da Task 1 (formato do dict `parsed`).
- Produces (usados pelas Tasks 7, 8, 9): `STATUS`, `conectar`, `inicializar_banco`, `listar_convenios`, `criar_ou_obter_convenio`, `definir_prazo_convenio`, `importar_dacm(conn, parsed, convenio_nome, usuario, caminho_arquivo)`, `registrar_status(conn, guia_id, status_novo, vl_recuperado=None, observacao=None, usuario="")`, `confirmar_glosa_recebida(conn, guia_id, usuario="")`, `motivo_glosado(conn, guia_id)`, `guias_filtradas(conn, convenio_id=None, status=None, busca=None, de=None, ate=None, somente_avisos=False)`, `resumo_kpis(conn, convenio_id=None, de=None, ate=None)`, `agrupado_por_convenio(conn, de=None, ate=None)`, `evolucao_mensal(conn, convenio_id=None, de=None, ate=None)`, `ranking_motivos(conn, convenio_id=None, de=None, ate=None)`, `alertas_aging(conn, hoje=None)`, `avisos_glosa_zerada(conn)`, `listar_uploads(conn, limite=10)`, `historico_status(conn, guia_id)`, `diff_guias_editadas(antes, depois)`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_banco_glosas.py`:

```python
"""Testes do banco do Contas a Receber (dacm_glosas.db) — em tmp_path."""
from datetime import date

import pandas as pd
import pytest

import banco_glosas


@pytest.fixture()
def conn(tmp_path):
    c = banco_glosas.conectar(str(tmp_path / "teste.db"))
    banco_glosas.inicializar_banco(c)
    yield c
    c.close()


def _parsed(guias):
    """Dict parseado fake no formato do parser_dacm."""
    return {
        "metadados": {"num_dacm": "14880859", "operadora": "Porto Seguro - Seguro Saude S.A.",
                      "registro_ans": "000582", "cnpj": "04540010000170",
                      "data_emissao": "2026-07-16"},
        "guias": guias,
        "avisos": [],
    }


def _guia(guia="25489130", glosa=0.24, itens=None):
    return {
        "lote": "272327", "protocolo": "20274355", "data_protocolo": "2026-06-12",
        "cod_situacao_protocolo": "6", "guia_prestador": guia, "guia_operadora": "12474769",
        "senha": "", "beneficiario": "JEFERSON PASSOS PEREIRA", "nome_social": "JEFERSON",
        "carteira": "2234973211568118", "data_inicio_fat": "", "data_fim_fat": "",
        "cod_situacao_guia": "6", "vl_informado": 50.52, "vl_processado": 50.52,
        "vl_liberado": 50.52 - glosa, "vl_glosa": glosa,
        "itens": itens if itens is not None else [
            {"data_realizacao": "2026-05-18", "tabela": "22", "cod_procedimento": "10101039",
             "descricao": "CONSULTA EM PRONTO SOCORRO", "grau_participacao": "08",
             "quantidade": 1, "vl_informado": 44.22, "vl_processado": 44.22,
             "vl_liberado": 44.22, "vl_glosa": 0, "cod_glosa": ""},
            {"data_realizacao": "2026-05-18", "tabela": "22", "cod_procedimento": "40302040",
             "descricao": "GLICOSE - PESQUISA E/OU DOSAGEM", "grau_participacao": "",
             "quantidade": 1, "vl_informado": 6.3, "vl_processado": 6.3,
             "vl_liberado": 6.06, "vl_glosa": glosa, "cod_glosa": "1714"},
        ],
    }


def test_inicializa_e_importa_guia_nova_com_status_inicial(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"conteudo")
    r = banco_glosas.importar_dacm(conn, _parsed([_guia()]), "Porto Saúde",
                                   "lsmartins", str(arquivo))
    assert r == {"novas": 1, "atualizadas": 0, "avisos_glosa_zerada": 0, "upload_id": 1}
    guias = banco_glosas.guias_filtradas(conn)
    assert len(guias) == 1
    assert guias[0]["status_recurso"] == "A iniciar recurso"
    assert guias[0]["data_inicio"] == "2026-05-18"
    # convênio criado com os dados do arquivo
    convenios = banco_glosas.listar_convenios(conn)
    assert [c["nome"] for c in convenios] == ["Porto Saúde"]
    assert convenios[0]["registro_ans"] == "000582"


def test_importa_guia_sem_glosa_como_livre(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia(glosa=0)]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    assert banco_glosas.guias_filtradas(conn)[0]["status_recurso"] == "Livre de Glosa"


def test_reenvio_atualiza_sem_duplicar_e_mantem_status(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia()]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    guia_id = banco_glosas.guias_filtradas(conn)[0]["guia_id"]
    banco_glosas.registrar_status(conn, guia_id, "Em análise", usuario="lsmartins")
    # reenvio com valor de glosa DIFERENTE (arquivo corrigido)
    guia2 = _guia(glosa=5.0)
    r = banco_glosas.importar_dacm(conn, _parsed([guia2]), "Porto Saúde",
                                   "lsmartins", str(arquivo))
    assert r["novas"] == 0 and r["atualizadas"] == 1
    assert len(banco_glosas.guias_filtradas(conn)) == 1  # sem duplicar
    guia = banco_glosas.guias_filtradas(conn)[0]
    assert guia["vl_glosa"] == 5.0
    assert guia["status_recurso"] == "Em análise"  # status manual preservado


def test_reenvio_com_glosa_zerada_gera_aviso_sem_mudar_status(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia(glosa=10.0)]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    r = banco_glosas.importar_dacm(conn, _parsed([_guia(glosa=0)]), "Porto Saúde",
                                   "lsmartins", str(arquivo))
    assert r["avisos_glosa_zerada"] == 1
    guia = banco_glosas.guias_filtradas(conn)[0]
    assert guia["aviso_glosa_zerada"] == 1
    assert guia["status_recurso"] == "A iniciar recurso"  # nada muda sozinho
    assert len(banco_glosas.avisos_glosa_zerada(conn)) == 1


def test_confirmar_glosa_recebida_um_clique(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia(glosa=0.24)]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    banco_glosas.importar_dacm(conn, _parsed([_guia(glosa=0)]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    guia_id = banco_glosas.guias_filtradas(conn)[0]["guia_id"]
    banco_glosas.confirmar_glosa_recebida(conn, guia_id, usuario="lsmartins")
    guia = banco_glosas.guias_filtradas(conn)[0]
    assert guia["status_recurso"] == "Glosa Recebida"
    assert guia["vl_recuperado"] == 0.24  # default = valor da glosa
    assert guia["aviso_glosa_zerada"] == 0
    hist = banco_glosas.historico_status(conn, guia_id)
    assert [h["status_para"] for h in hist] == ["A iniciar recurso", "Glosa Recebida"]


def test_registrar_status_rejeita_status_invalido(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia()]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    guia_id = banco_glosas.guias_filtradas(conn)[0]["guia_id"]
    with pytest.raises(ValueError, match="Status inválido"):
        banco_glosas.registrar_status(conn, guia_id, "Status que não existe")


def test_motivo_glosado_concatena_descricoes(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia(glosa=0.24)]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    guia_id = banco_glosas.guias_filtradas(conn)[0]["guia_id"]
    assert banco_glosas.motivo_glosado(conn, guia_id) == \
        "GLICOSE - PESQUISA E/OU DOSAGEM [1714]"


def test_resumo_kpis_e_taxas(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia(glosa=10.0)]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    guia_id = banco_glosas.guias_filtradas(conn)[0]["guia_id"]
    banco_glosas.registrar_status(conn, guia_id, "Glosa Recebida", vl_recuperado=10.0)
    kpis = banco_glosas.resumo_kpis(conn)
    assert kpis["glosado"] == 10.0
    assert kpis["recuperado"] == 10.0
    assert kpis["taxa_recuperacao"] == 100.0
    assert kpis["em_recurso"] == 0.0


def test_alertas_aging_so_para_convenios_com_prazo(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia()]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    # sem prazo cadastrado -> nenhum alerta
    assert banco_glosas.alertas_aging(conn, hoje=date(2026, 9, 6)) == []
    convenio_id = banco_glosas.listar_convenios(conn)[0]["id"]
    banco_glosas.definir_prazo_convenio(conn, convenio_id, 30)
    # protocolo de 12/06: 86 dias até 06/09 -> estourado
    alertas = banco_glosas.alertas_aging(conn, hoje=date(2026, 9, 6))
    assert len(alertas) == 1
    assert alertas[0]["dias"] == 86 and alertas[0]["prazo"] == 30
    # dentro do prazo -> sem alerta
    assert banco_glosas.alertas_aging(conn, hoje=date(2026, 7, 1)) == []


def test_diff_guias_editadas_so_devolve_o_que_mudou():
    antes = pd.DataFrame([
        {"guia_id": 1, "status": "A iniciar recurso", "vl_recuperado": 0.0, "observacao": ""},
        {"guia_id": 2, "status": "Livre de Glosa", "vl_recuperado": 0.0, "observacao": ""},
    ])
    depois = pd.DataFrame([
        {"guia_id": 1, "status": "Em análise", "vl_recuperado": 5.0, "observacao": "ok"},
        {"guia_id": 2, "status": "Livre de Glosa", "vl_recuperado": 0.0, "observacao": ""},
    ])
    alteradas = banco_glosas.diff_guias_editadas(antes, depois)
    assert alteradas == [{"guia_id": 1, "status": "Em análise", "vl_recuperado": 5.0,
                          "observacao": "ok"}]


def test_nome_de_arquivo_seguro_nunca_escapa_da_pasta(conn, tmp_path):
    arquivo = tmp_path / ".._etc_passwd.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia()]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    upload = banco_glosas.listar_uploads(conn)[0]
    assert ".." not in upload["nome_arquivo"]
    import os
    salvo = os.path.join(banco_glosas.PASTA_UPLOADS, upload["nome_arquivo"])
    assert os.path.exists(salvo)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_banco_glosas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'banco_glosas'`

- [ ] **Step 3: Implementar o banco**

Criar `banco_glosas.py`:

```python
"""
==============================================================================
BANCO DE DADOS — CONTAS A RECEBER (DASHBOARD DE GLOSAS)
SQLite (WAL) em dados/dacm_glosas.db — SEPARADO do banco do PF.
Uma conexão por operação; nunca compartilhada.
==============================================================================
"""
import os
import re
import shutil
import time
import urllib.parse
from datetime import datetime

import pandas as pd
import sqlite3

CAMINHO_PADRAO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "dacm_glosas.db")
PASTA_UPLOADS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "uploads_dacm")

STATUS = ["A iniciar recurso", "Em análise", "Glosa Recebida", "Recurso Negado", "Livre de Glosa"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS convenios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT UNIQUE NOT NULL,
  registro_ans TEXT NOT NULL DEFAULT '',
  cnpj TEXT NOT NULL DEFAULT '',
  prazo_recurso_dias INTEGER,
  criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS uploads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  convenio_id INTEGER NOT NULL REFERENCES convenios(id),
  nome_arquivo TEXT NOT NULL,
  num_dacm TEXT NOT NULL DEFAULT '',
  data_emissao TEXT NOT NULL DEFAULT '',
  guias_novas INTEGER NOT NULL DEFAULT 0,
  guias_atualizadas INTEGER NOT NULL DEFAULT 0,
  usuario TEXT NOT NULL,
  criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS guias (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  convenio_id INTEGER NOT NULL REFERENCES convenios(id),
  upload_id INTEGER NOT NULL REFERENCES uploads(id),
  guia_prestador TEXT NOT NULL,
  guia_operadora TEXT NOT NULL DEFAULT '',
  senha TEXT NOT NULL DEFAULT '',
  lote TEXT NOT NULL DEFAULT '',
  protocolo TEXT NOT NULL DEFAULT '',
  data_protocolo TEXT NOT NULL DEFAULT '',
  beneficiario TEXT NOT NULL DEFAULT '',
  nome_social TEXT NOT NULL DEFAULT '',
  carteira TEXT NOT NULL DEFAULT '',
  data_inicio TEXT NOT NULL DEFAULT '',
  data_fim TEXT NOT NULL DEFAULT '',
  cod_situacao_guia TEXT NOT NULL DEFAULT '',
  vl_informado REAL NOT NULL DEFAULT 0,
  vl_processado REAL NOT NULL DEFAULT 0,
  vl_liberado REAL NOT NULL DEFAULT 0,
  vl_glosa REAL NOT NULL DEFAULT 0,
  status_recurso TEXT NOT NULL DEFAULT '',
  vl_recuperado REAL NOT NULL DEFAULT 0,
  observacao TEXT NOT NULL DEFAULT '',
  aviso_glosa_zerada INTEGER NOT NULL DEFAULT 0,
  atualizado_em TEXT NOT NULL,
  UNIQUE(convenio_id, guia_prestador)
);
CREATE INDEX IF NOT EXISTS idx_guias_status ON guias(status_recurso);
CREATE TABLE IF NOT EXISTS itens_guia (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  guia_id INTEGER NOT NULL REFERENCES guias(id),
  data_realizacao TEXT NOT NULL DEFAULT '',
  tabela TEXT NOT NULL DEFAULT '',
  cod_procedimento TEXT NOT NULL DEFAULT '',
  descricao TEXT NOT NULL DEFAULT '',
  grau_participacao TEXT NOT NULL DEFAULT '',
  quantidade REAL NOT NULL DEFAULT 0,
  vl_informado REAL NOT NULL DEFAULT 0,
  vl_processado REAL NOT NULL DEFAULT 0,
  vl_liberado REAL NOT NULL DEFAULT 0,
  vl_glosa REAL NOT NULL DEFAULT 0,
  cod_glosa TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_itens_guia ON itens_guia(guia_id);
CREATE TABLE IF NOT EXISTS recursos_hist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  guia_id INTEGER NOT NULL REFERENCES guias(id),
  status_de TEXT NOT NULL DEFAULT '',
  status_para TEXT NOT NULL,
  vl_recuperado REAL NOT NULL DEFAULT 0,
  observacao TEXT NOT NULL DEFAULT '',
  usuario TEXT NOT NULL DEFAULT '',
  atualizado_em TEXT NOT NULL
);
"""


def conectar(caminho=None):
    caminho = caminho or CAMINHO_PADRAO
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def inicializar_banco(conn):
    conn.executescript(SCHEMA)
    conn.commit()


# ==============================================================================
# CONVÊNIOS
# ==============================================================================
def listar_convenios(conn):
    """Convênios ordenados por nome (rows com id, nome, registro_ans, cnpj, prazo)."""
    return conn.execute("SELECT * FROM convenios ORDER BY nome").fetchall()


def criar_ou_obter_convenio(conn, nome, registro_ans="", cnpj=""):
    """Devolve o convênio com este nome; cria se não existir."""
    row = conn.execute("SELECT * FROM convenios WHERE nome=?", (nome,)).fetchone()
    if row:
        return dict(row)
    cur = conn.execute(
        "INSERT INTO convenios (nome, registro_ans, cnpj, criado_em) VALUES (?,?,?,?)",
        (nome, registro_ans or "", cnpj or "", datetime.now().isoformat()))
    conn.commit()
    return dict(conn.execute("SELECT * FROM convenios WHERE id=?", (cur.lastrowid,)).fetchone())


def definir_prazo_convenio(conn, convenio_id, dias):
    """Define (ou limpa, com dias=None) o prazo de recurso do convênio."""
    conn.execute("UPDATE convenios SET prazo_recurso_dias=? WHERE id=?",
                 (None if dias is None else int(dias), convenio_id))
    conn.commit()


# ==============================================================================
# IMPORTACAO
# ==============================================================================
_RE_NOME_SEGURO = re.compile(r"^[\w.-]{1,64}$")


def _nome_arquivo_seguro(nome):
    """Nome de arquivo seguro para guardar em uploads_dacm (nunca escapa da pasta)."""
    nome = os.path.basename(nome or "").strip()
    if not nome:
        raise ValueError("Arquivo sem nome válido.")
    if _RE_NOME_SEGURO.match(nome):
        return nome
    return urllib.parse.quote(nome, safe="")[:64]


def _copiar_arquivo_original(caminho):
    """Copia o arquivo do upload para dados/uploads_dacm/ e devolve o nome guardado."""
    os.makedirs(PASTA_UPLOADS, exist_ok=True)
    nome = _nome_arquivo_seguro(os.path.basename(caminho))
    destino = os.path.join(PASTA_UPLOADS, nome)
    if os.path.exists(destino):
        base, ext = os.path.splitext(nome)
        nome = f"{base}_{int(time.time())}{ext}"
        destino = os.path.join(PASTA_UPLOADS, nome)
    shutil.copy2(caminho, destino)
    return nome


def importar_dacm(conn, parsed, convenio_nome, usuario, caminho_arquivo):
    """Importa o DACM parseado. Guias já existentes no convênio (mesma guia do
    prestador) são ATUALIZADAS (status do recurso é preservado); guias novas
    entram com status inicial. O arquivo original é copiado para
    dados/uploads_dacm/. Devolve {novas, atualizadas, avisos_glosa_zerada, upload_id}."""
    metadados = parsed["metadados"]
    nome = (convenio_nome or metadados.get("operadora") or "").strip()
    if not nome:
        raise ValueError("Informe o nome do convênio.")
    convenio = criar_ou_obter_convenio(
        conn, nome, metadados.get("registro_ans", ""), metadados.get("cnpj", ""))
    nome_arquivo = _copiar_arquivo_original(caminho_arquivo)
    agora = datetime.now().isoformat()
    cur = conn.execute(
        "INSERT INTO uploads (convenio_id, nome_arquivo, num_dacm, data_emissao, "
        "usuario, criado_em) VALUES (?, ?, ?, ?, ?, ?)",
        (convenio["id"], nome_arquivo, metadados.get("num_dacm", ""),
         metadados.get("data_emissao", ""), usuario, agora))
    upload_id = cur.lastrowid
    novas = atualizadas = avisos = 0
    for g in parsed["guias"]:
        existente = conn.execute(
            "SELECT * FROM guias WHERE convenio_id=? AND guia_prestador=?",
            (convenio["id"], g["guia_prestador"])).fetchone()
        data_inicio = min((i["data_realizacao"] for i in g["itens"]
                           if i["data_realizacao"]), default="")
        if existente is None:
            status_inicial = "A iniciar recurso" if g["vl_glosa"] > 0 else "Livre de Glosa"
            cur = conn.execute(
                "INSERT INTO guias (convenio_id, upload_id, guia_prestador, guia_operadora, "
                "senha, lote, protocolo, data_protocolo, beneficiario, nome_social, carteira, "
                "data_inicio, data_fim, cod_situacao_guia, vl_informado, vl_processado, "
                "vl_liberado, vl_glosa, status_recurso, atualizado_em) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (convenio["id"], upload_id, g["guia_prestador"], g["guia_operadora"],
                 g["senha"], g["lote"], g["protocolo"], g["data_protocolo"],
                 g["beneficiario"], g["nome_social"], g["carteira"],
                 data_inicio, g["data_fim_fat"], g["cod_situacao_guia"],
                 g["vl_informado"], g["vl_processado"], g["vl_liberado"], g["vl_glosa"],
                 status_inicial, agora))
            guia_id = cur.lastrowid
            conn.execute(
                "INSERT INTO recursos_hist (guia_id, status_de, status_para, usuario, "
                "atualizado_em) VALUES (?, '', ?, ?, ?)",
                (guia_id, status_inicial, usuario, agora))
            novas += 1
        else:
            novo_aviso = 0
            if existente["vl_glosa"] > 0.005 and g["vl_glosa"] == 0:
                novo_aviso = 1
                avisos += 1
            conn.execute(
                "UPDATE guias SET upload_id=?, guia_operadora=?, senha=?, lote=?, protocolo=?, "
                "data_protocolo=?, beneficiario=?, nome_social=?, carteira=?, data_inicio=?, "
                "data_fim=?, cod_situacao_guia=?, vl_informado=?, vl_processado=?, "
                "vl_liberado=?, vl_glosa=?, aviso_glosa_zerada=?, atualizado_em=? WHERE id=?",
                (upload_id, g["guia_operadora"], g["senha"], g["lote"], g["protocolo"],
                 g["data_protocolo"], g["beneficiario"], g["nome_social"], g["carteira"],
                 data_inicio, g["data_fim_fat"], g["cod_situacao_guia"],
                 g["vl_informado"], g["vl_processado"], g["vl_liberado"], g["vl_glosa"],
                 novo_aviso, agora, existente["id"]))
            guia_id = existente["id"]
            conn.execute("DELETE FROM itens_guia WHERE guia_id=?", (guia_id,))
            atualizadas += 1
        conn.executemany(
            "INSERT INTO itens_guia (guia_id, data_realizacao, tabela, cod_procedimento, "
            "descricao, grau_participacao, quantidade, vl_informado, vl_processado, "
            "vl_liberado, vl_glosa, cod_glosa) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [(guia_id, i["data_realizacao"], i["tabela"], i["cod_procedimento"],
              i["descricao"], i["grau_participacao"], i["quantidade"],
              i["vl_informado"], i["vl_processado"], i["vl_liberado"], i["vl_glosa"],
              i["cod_glosa"]) for i in g["itens"]])
    conn.execute("UPDATE uploads SET guias_novas=?, guias_atualizadas=? WHERE id=?",
                 (novas, atualizadas, upload_id))
    conn.commit()
    return {"novas": novas, "atualizadas": atualizadas,
            "avisos_glosa_zerada": avisos, "upload_id": upload_id}


# ==============================================================================
# RECURSOS (STATUS)
# ==============================================================================
def registrar_status(conn, guia_id, status_novo, vl_recuperado=None, observacao=None,
                     usuario=""):
    """Muda o status do recurso da guia e registra a mudança em recursos_hist.
    vl_recuperado/observacao None mantêm o valor atual."""
    if status_novo not in STATUS:
        raise ValueError(f"Status inválido: {status_novo}")
    guia = conn.execute("SELECT * FROM guias WHERE id=?", (guia_id,)).fetchone()
    if guia is None:
        raise ValueError("Guia não encontrada.")
    novo_vl = guia["vl_recuperado"] if vl_recuperado is None else float(vl_recuperado)
    nova_obs = guia["observacao"] if observacao is None else str(observacao)
    agora = datetime.now().isoformat()
    conn.execute(
        "UPDATE guias SET status_recurso=?, vl_recuperado=?, observacao=?, "
        "aviso_glosa_zerada=0, atualizado_em=? WHERE id=?",
        (status_novo, novo_vl, nova_obs, agora, guia_id))
    conn.execute(
        "INSERT INTO recursos_hist (guia_id, status_de, status_para, vl_recuperado, "
        "observacao, usuario, atualizado_em) VALUES (?,?,?,?,?,?,?)",
        (guia_id, guia["status_recurso"], status_novo, novo_vl, nova_obs, usuario, agora))
    conn.commit()


def confirmar_glosa_recebida(conn, guia_id, usuario=""):
    """Botão de 1 clique do aviso: status vira 'Glosa Recebida' e o valor
    recuperado assume o valor da glosa (se ainda for 0)."""
    guia = conn.execute("SELECT * FROM guias WHERE id=?", (guia_id,)).fetchone()
    if guia is None:
        raise ValueError("Guia não encontrada.")
    vl = guia["vl_recuperado"] if guia["vl_recuperado"] > 0 else guia["vl_glosa"]
    registrar_status(conn, guia_id, "Glosa Recebida", vl_recuperado=vl, usuario=usuario)


def historico_status(conn, guia_id):
    return conn.execute(
        "SELECT * FROM recursos_hist WHERE guia_id=? ORDER BY id", (guia_id,)).fetchall()


def diff_guias_editadas(antes, depois):
    """Linhas alteradas entre o snapshot e o data_editor: [{guia_id, status,
    vl_recuperado, observacao}] só com o que mudou."""
    indices = set(antes["guia_id"]) & set(depois["guia_id"])
    alteradas = []
    for gid in indices:
        a = antes[antes["guia_id"] == gid].iloc[0]
        d = depois[depois["guia_id"] == gid].iloc[0]
        if (a["status"] != d["status"]
                or float(a["vl_recuperado"]) != float(d["vl_recuperado"])
                or str(a["observacao"]) != str(d["observacao"])):
            alteradas.append({"guia_id": int(gid), "status": d["status"],
                              "vl_recuperado": float(d["vl_recuperado"]),
                              "observacao": str(d["observacao"])})
    return alteradas


# ==============================================================================
# CONSULTAS DO DASHBOARD
# ==============================================================================
def motivo_glosado(conn, guia_id):
    """Descrição dos itens com glosa da guia: 'DESC [código] · DESC [código]'."""
    itens = conn.execute(
        "SELECT descricao, cod_glosa FROM itens_guia WHERE guia_id=? AND vl_glosa > 0",
        (guia_id,)).fetchall()
    partes = []
    for i in itens:
        if i["cod_glosa"]:
            partes.append(f"{i['descricao']} [{i['cod_glosa']}]")
        else:
            partes.append(i["descricao"])
    return " · ".join(partes)


def guias_filtradas(conn, convenio_id=None, status=None, busca=None, de=None, ate=None,
                    somente_avisos=False):
    """Guias como dicts (inclui guia_id, convenio e motivo glosado)."""
    sql = ("SELECT g.id AS guia_id, g.*, c.nome AS convenio "
           "FROM guias g JOIN convenios c ON c.id = g.convenio_id WHERE 1=1")
    params = []
    if convenio_id:
        sql += " AND g.convenio_id = ?"; params.append(convenio_id)
    if status:
        sql += " AND g.status_recurso = ?"; params.append(status)
    if busca:
        sql += " AND (g.guia_prestador LIKE ? OR g.beneficiario LIKE ?)"
        params += [f"%{busca}%", f"%{busca}%"]
    if de:
        sql += " AND g.data_inicio >= ?"; params.append(de)
    if ate:
        sql += " AND g.data_inicio <= ?"; params.append(ate)
    if somente_avisos:
        sql += " AND g.aviso_glosa_zerada = 1"
    sql += " ORDER BY g.data_inicio DESC, g.guia_prestador"
    linhas = [dict(r) for r in conn.execute(sql, params).fetchall()]
    for linha in linhas:
        linha["motivo"] = motivo_glosado(conn, linha["guia_id"])
    return linhas


def resumo_kpis(conn, convenio_id=None, de=None, ate=None):
    """Totais + taxas para os KPI cards. Valores float."""
    linhas = guias_filtradas(conn, convenio_id=convenio_id, de=de, ate=ate)
    processado = sum(g["vl_processado"] for g in linhas)
    liberado = sum(g["vl_liberado"] for g in linhas)
    glosado = sum(g["vl_glosa"] for g in linhas)
    em_recurso = sum(g["vl_glosa"] for g in linhas
                     if g["status_recurso"] in ("A iniciar recurso", "Em análise"))
    recuperado = sum(g["vl_recuperado"] for g in linhas)
    perda_real = sum(g["vl_glosa"] for g in linhas if g["status_recurso"] == "Recurso Negado")
    return {
        "processado": processado, "liberado": liberado, "glosado": glosado,
        "em_recurso": em_recurso, "recuperado": recuperado, "perda_real": perda_real,
        "taxa_glosa": (glosado / processado * 100) if processado > 0 else 0.0,
        "taxa_recuperacao": (recuperado / glosado * 100) if glosado > 0 else 0.0,
    }


def agrupado_por_convenio(conn, de=None, ate=None):
    """DataFrame por convênio: convenio_id, convenio, processado, liberado, glosado, pct_glosa."""
    sql = ("SELECT c.id AS convenio_id, c.nome AS convenio, "
           "SUM(g.vl_processado) AS processado, SUM(g.vl_liberado) AS liberado, "
           "SUM(g.vl_glosa) AS glosado "
           "FROM guias g JOIN convenios c ON c.id=g.convenio_id WHERE 1=1")
    params = []
    if de:
        sql += " AND g.data_inicio >= ?"; params.append(de)
    if ate:
        sql += " AND g.data_inicio <= ?"; params.append(ate)
    sql += " GROUP BY c.id, c.nome ORDER BY glosado DESC"
    df = pd.read_sql_query(sql, conn, params=params)
    df["pct_glosa"] = df.apply(
        lambda r: r["glosado"] / r["processado"] * 100 if r["processado"] > 0 else 0.0,
        axis=1)
    return df


def evolucao_mensal(conn, convenio_id=None, de=None, ate=None):
    """DataFrame mensal (mes, glosado, recuperado) por mês de data_inicio."""
    sql = ("SELECT substr(g.data_inicio, 1, 7) AS mes, SUM(g.vl_glosa) AS glosado, "
           "SUM(g.vl_recuperado) AS recuperado "
           "FROM guias g WHERE g.data_inicio != ''")
    params = []
    if convenio_id:
        sql += " AND g.convenio_id = ?"; params.append(convenio_id)
    if de:
        sql += " AND g.data_inicio >= ?"; params.append(de)
    if ate:
        sql += " AND g.data_inicio <= ?"; params.append(ate)
    sql += " GROUP BY mes ORDER BY mes"
    return pd.read_sql_query(sql, conn, params=params)


def ranking_motivos(conn, convenio_id=None, de=None, ate=None):
    """Ranking de motivos de glosa (descrição + código), por valor total glosado."""
    sql = ("SELECT i.descricao, i.cod_glosa, SUM(i.vl_glosa) AS total "
           "FROM itens_guia i JOIN guias g ON g.id = i.guia_id "
           "WHERE i.vl_glosa > 0")
    params = []
    if convenio_id:
        sql += " AND g.convenio_id = ?"; params.append(convenio_id)
    if de:
        sql += " AND g.data_inicio >= ?"; params.append(de)
    if ate:
        sql += " AND g.data_inicio <= ?"; params.append(ate)
    sql += " GROUP BY i.descricao, i.cod_glosa ORDER BY total DESC"
    return pd.read_sql_query(sql, conn, params=params)


def alertas_aging(conn, hoje=None):
    """Guias 'A iniciar recurso' estouradas além do prazo do convênio.
    [{convenio, guia, beneficiario, protocolo, dias, prazo, vl_glosa}] por dias desc."""
    hoje = hoje or datetime.now().date()
    linhas = conn.execute(
        "SELECT g.guia_prestador AS guia, g.beneficiario, g.protocolo, "
        "g.data_protocolo, g.vl_glosa, c.nome AS convenio, c.prazo_recurso_dias AS prazo "
        "FROM guias g JOIN convenios c ON c.id=g.convenio_id "
        "WHERE g.status_recurso='A iniciar recurso' AND c.prazo_recurso_dias IS NOT NULL "
        "AND g.data_protocolo != ''").fetchall()
    alertas = []
    for r in linhas:
        try:
            dt = datetime.fromisoformat(r["data_protocolo"]).date()
        except ValueError:
            continue
        dias = (hoje - dt).days
        if dias > r["prazo"]:
            alertas.append({"convenio": r["convenio"], "guia": r["guia"],
                            "beneficiario": r["beneficiario"], "protocolo": r["protocolo"],
                            "dias": dias, "prazo": r["prazo"], "vl_glosa": r["vl_glosa"]})
    return sorted(alertas, key=lambda a: a["dias"], reverse=True)


def avisos_glosa_zerada(conn):
    """Guias com aviso de glosa zerada no reenvio (para o botão de 1 clique)."""
    linhas = [dict(r) for r in conn.execute(
        "SELECT g.*, c.nome AS convenio FROM guias g JOIN convenios c ON c.id=g.convenio_id "
        "WHERE g.aviso_glosa_zerada=1").fetchall()]
    for linha in linhas:
        linha["motivo"] = motivo_glosado(conn, linha["id"])
    return linhas


def listar_uploads(conn, limite=10):
    return conn.execute(
        "SELECT u.*, c.nome AS convenio FROM uploads u JOIN convenios c ON c.id=u.convenio_id "
        "ORDER BY u.id DESC LIMIT ?", (limite,)).fetchall()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_banco_glosas.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add banco_glosas.py tests/test_banco_glosas.py
git commit -m "feat: banco do Contas a Receber com importação, dedup por guia e avisos"
```

---

### Task 3: Flag de acesso no PF (`banco.py`, `auth.py`)

**Files:**
- Modify: `banco.py` (SCHEMA, `inicializar_banco`, `listar_usuarios`, nova `definir_acesso_contas_receber`)
- Modify: `auth.py` (sessão inclui `acesso_contas_receber`)
- Test: `tests/test_banco.py` (adicionar 3 testes no fim do arquivo)

**Interfaces:**
- Produces: `banco.definir_acesso_contas_receber(conn, login, valor)`; `listar_usuarios` passa a incluir `acesso_contas_receber` (usado pela Task 6); `st.session_state["usuario"]["acesso_contas_receber"]` (usado pelas Tasks 5-9).

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao fim de `tests/test_banco.py` (o arquivo já existe; NÃO tem fixture `conn` — os testes dele criam a conexão inline a partir de `tmp_path`. Seguir exatamente esse padrão):

```python
def test_migracao_acesso_contas_receber_banca_antigo_sem_coluna(tmp_path):
    """Banco criado ANTES da feature ganha a coluna ao inicializar."""
    db = str(tmp_path / "pf_antigo.db")
    conn_antigo = sqlite3.connect(db)
    conn_antigo.execute("""CREATE TABLE usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login TEXT UNIQUE NOT NULL,
        nome TEXT NOT NULL,
        senha_hash TEXT NOT NULL,
        admin INTEGER NOT NULL DEFAULT 0,
        falhas_seguidas INTEGER NOT NULL DEFAULT 0,
        bloqueado_ate TEXT,
        criado_em TEXT NOT NULL
    )""")
    conn_antigo.commit()
    conn_antigo.close()

    conn = banco.conectar(db)
    banco.inicializar_banco(conn)  # não pode quebrar
    banco.inicializar_banco(conn)  # idempotente
    colunas = [r["name"] for r in conn.execute("PRAGMA table_info(usuarios)").fetchall()]
    assert "acesso_contas_receber" in colunas
    conn.close()


def test_definir_acesso_contas_receber_e_listar(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    login = "alguem_cr"
    banco.criar_usuario(conn, login, "Alguém", "senha12345")
    assert [r["acesso_contas_receber"] for r in banco.listar_usuarios(conn)
            if r["login"] == login] == [0]
    banco.definir_acesso_contas_receber(conn, login, True)
    assert [r["acesso_contas_receber"] for r in banco.listar_usuarios(conn)
            if r["login"] == login] == [1]
    banco.definir_acesso_contas_receber(conn, login, False)
    assert [r["acesso_contas_receber"] for r in banco.listar_usuarios(conn)
            if r["login"] == login] == [0]
    conn.close()


def test_autenticar_devolve_acesso_contas_receber(tmp_path):
    db = str(tmp_path / "pf.db")
    conn = banco.conectar(db); banco.inicializar_banco(conn)
    login = "com_acesso"
    banco.criar_usuario(conn, login, "Com Acesso", "senha12345")
    banco.definir_acesso_contas_receber(conn, login, True)
    usuario = banco.autenticar(conn, login, "senha12345")
    assert usuario is not None and usuario["acesso_contas_receber"] == 1
    conn.close()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_banco.py -v`
Expected: FAIL — os 3 novos testes falham (coluna não existe / funções ausentes)

- [ ] **Step 3: Implementar**

Em `banco.py`:
1. No `SCHEMA`, na tabela `usuarios`, adicionar após `admin INTEGER NOT NULL DEFAULT 0,`:
```sql
  acesso_contas_receber INTEGER NOT NULL DEFAULT 0,
```
2. Nova função:
```python
def _migrar_acesso_contas_receber(conn):
    """Garante usuarios.acesso_contas_receber (bancos criados antes da feature)."""
    colunas = [r["name"] for r in conn.execute("PRAGMA table_info(usuarios)").fetchall()]
    if "acesso_contas_receber" not in colunas:
        conn.execute("ALTER TABLE usuarios ADD COLUMN acesso_contas_receber "
                     "INTEGER NOT NULL DEFAULT 0")
```
3. `inicializar_banco` passa a ser:
```python
def inicializar_banco(conn):
    conn.executescript(SCHEMA)
    _migrar_acesso_contas_receber(conn)
    conn.commit()
```
4. `listar_usuarios` passa a selecionar:
```python
    return conn.execute(
        "SELECT id, login, nome, admin, acesso_contas_receber "
        "FROM usuarios ORDER BY login").fetchall()
```
5. Nova função:
```python
def definir_acesso_contas_receber(conn, login, valor):
    """Liga/desliga o acesso ao sistema Contas a Receber para o usuário."""
    conn.execute("UPDATE usuarios SET acesso_contas_receber=? WHERE login=?",
                 (1 if valor else 0, login))
    conn.commit()
```

Em `auth.py`:
1. Em `_restaurar_sessao` (linha ~85):
```python
    st.session_state["usuario"] = {"login": usuario["login"],
                                   "admin": bool(usuario["admin"]),
                                   "acesso_contas_receber":
                                       bool(usuario["acesso_contas_receber"])}
```
2. Em `exigir_login` (bloco do botão Entrar, linha ~135):
```python
                        st.session_state["usuario"] = {"login": login.strip(),
                                                       "admin": bool(usuario["admin"]),
                                                       "acesso_contas_receber":
                                                           bool(usuario["acesso_contas_receber"])}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_banco.py -v`
Expected: PASS (todos, antigos + novos)

- [ ] **Step 5: Commit**

```bash
git add banco.py auth.py tests/test_banco.py
git commit -m "feat: flag acesso_contas_receber por usuário (migração tolerante)"
```

---

### Task 4: Visual — badges de status e CSS (`ui_comum.py`)

**Files:**
- Modify: `ui_comum.py`
- Test: `tests/test_ui_comum.py` (adicionar teste)

**Interfaces:**
- Produces: `CORES_STATUS` (dict) e `badge_status(status) -> str` (usados pelas Tasks 8-9); CSS novo em `injetar_css()`.

- [ ] **Step 1: Escrever o teste que falha**

Adicionar a `tests/test_ui_comum.py`:

```python
def test_badge_status_contem_rotulo_e_cor():
    from ui_comum import badge_status
    html = badge_status("A iniciar recurso")
    assert "A iniciar recurso" in html
    assert "#3b82f6" in html
    assert 'class="badge-status"' in html
    html2 = badge_status("Status desconhecido")
    assert "Status desconhecido" in html2  # cai no cinza padrão
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_ui_comum.py -v`
Expected: FAIL — `ImportError: cannot import name 'badge_status'`

- [ ] **Step 3: Implementar**

Em `ui_comum.py`, após `formatar_data_br` (final do arquivo):

```python
# ==============================================================================
# CONTAS A RECEBER — BADGES DE STATUS DO RECURSO
# ==============================================================================
CORES_STATUS = {
    "A iniciar recurso": "#3b82f6",
    "Em análise": "#f59e0b",
    "Glosa Recebida": "#22c55e",
    "Recurso Negado": "#ef4444",
    "Livre de Glosa": "#94a3b8",
}


def badge_status(status: str) -> str:
    """HTML do badge colorido do status do recurso (padrão do dashboard de glosas)."""
    cor = CORES_STATUS.get(status, "#94a3b8")
    return (f'<span class="badge-status" style="background:{cor}1a;color:{cor};">'
            f'<span class="dot" style="background:{cor};"></span>{status}</span>')
```

Em `injetar_css()`, adicionar ao bloco de estilos:

```css
/* Badges de status do recurso (Contas a Receber) */
.badge-status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    white-space: nowrap;
}
.badge-status .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    display: inline-block;
    flex-shrink: 0;
}
```

E atualizar `VERSAO` para `"Criado por Leonardo Martins · Revisado por Claude Code (Anthropic) · V 4.2026.0906 · Streamlit + Lucide"`.

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_ui_comum.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui_comum.py tests/test_ui_comum.py
git commit -m "feat: badges coloridos de status do recurso no ui_comum"
```

---

### Task 5: Navegação condicional + Portal (`navegacao.py`, `app_pages/portal.py`, `app_streamlit.py`)

**Files:**
- Create: `navegacao.py`
- Create: `app_pages/portal.py`
- Modify: `app_streamlit.py`
- Test: `tests/test_navegacao.py`

**Interfaces:**
- Consumes: `st.session_state["usuario"]["acesso_contas_receber"]` (Task 3).
- Produces: `navegacao.montar_paginas(acesso_cr) -> list[dict]` com chaves `path/titulo/icone/default` (usado por `app_streamlit.py`).

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_navegacao.py`:

```python
"""Testes da montagem de páginas do nav (sem tocar no Streamlit)."""
import navegacao


def test_sem_acesso_cr_nav_fica_como_hoje():
    paginas = navegacao.montar_paginas(False)
    assert [p["titulo"] for p in paginas] == \
        ["Processamento", "Resumo do dia", "Histórico", "Administração"]
    assert paginas[0]["default"] is True
    assert all(not p["titulo"].startswith(("PF ·", "CR ·")) for p in paginas)


def test_com_acesso_cr_portal_e_default_e_prefixos():
    paginas = navegacao.montar_paginas(True)
    titulos = [p["titulo"] for p in paginas]
    assert titulos[0] == "Início" and paginas[0]["default"] is True
    assert "PF · Processamento" in titulos
    assert "CR · Dashboard" in titulos
    assert "CR · Upload DACM" in titulos
    assert "CR · Recursos de Glosa" in titulos
    assert len(paginas) == 8
    assert all(not p["default"] for p in paginas[1:])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_navegacao.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'navegacao'`

- [ ] **Step 3: Implementar**

Criar `navegacao.py`:

```python
"""
==============================================================================
NAVEGAÇÃO — CONTAS A RECEBER
Monta a lista de páginas do st.navigation. Sem o acesso ao Contas a Receber,
o nav é EXATAMENTE o de hoje; com acesso, ganha o portal (default) e as
páginas do CR, com prefixos 'PF ·' e 'CR ·' nos títulos.
==============================================================================
"""


def montar_paginas(acesso_cr):
    """Lista de páginas [{path, titulo, icone, default}] para o st.navigation."""
    base_pf = [
        {"path": "app_pages/processamento.py", "titulo": "Processamento",
         "icone": ":material/play_circle:", "default": not acesso_cr},
        {"path": "app_pages/resumo_dia.py", "titulo": "Resumo do dia",
         "icone": ":material/calendar_today:", "default": False},
        {"path": "app_pages/historico.py", "titulo": "Histórico",
         "icone": ":material/history:", "default": False},
        {"path": "app_pages/administracao.py", "titulo": "Administração",
         "icone": ":material/settings:", "default": False},
    ]
    if not acesso_cr:
        return base_pf
    pf = [{**p, "titulo": f"PF · {p['titulo']}", "default": False} for p in base_pf]
    portal = {"path": "app_pages/portal.py", "titulo": "Início",
              "icone": ":material/home:", "default": True}
    cr = [
        {"path": "app_pages/dashboard_glosas.py", "titulo": "CR · Dashboard",
         "icone": ":material/monitoring:", "default": False},
        {"path": "app_pages/upload_dacm.py", "titulo": "CR · Upload DACM",
         "icone": ":material/upload_file:", "default": False},
        {"path": "app_pages/recursos_glosa.py", "titulo": "CR · Recursos de Glosa",
         "icone": ":material/assignment:", "default": False},
    ]
    return [portal] + pf + cr
```

Criar `app_pages/portal.py`:

```python
"""PÁGINA: INÍCIO — portal com os sistemas disponíveis ao usuário."""
import streamlit as st

from ui_comum import icone, VERSAO

st.markdown(f"### {icone('home', 20, '#1C5A8A')} Escolha o sistema", unsafe_allow_html=True)
st.caption("Você tem acesso a mais de um sistema. Selecione onde quer trabalhar.")

c1, c2 = st.columns(2)
with c1:
    with st.container(border=True):
        st.markdown(f"{icone('play-circle', 22, '#1C5A8A')} **Atualização PF**",
                    unsafe_allow_html=True)
        st.caption("Processamento da posição financeira, resumo do dia e histórico.")
        st.page_link("app_pages/processamento.py", label="Abrir Atualização PF")
with c2:
    with st.container(border=True):
        st.markdown(f"{icone('hand-coins', 22, '#1C5A8A')} **Contas a Receber**",
                    unsafe_allow_html=True)
        st.caption("Dashboard de glosas e recursos dos DACMs dos convênios.")
        st.page_link("app_pages/dashboard_glosas.py", label="Abrir Contas a Receber")

st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)
```

Em `app_streamlit.py`, substituir o bloco de navegação (linhas 60-86) por:

```python
import navegacao

paginas = [
    st.Page(p["path"], title=p["titulo"], icon=p["icone"], default=p["default"])
    for p in navegacao.montar_paginas(
        st.session_state.get("usuario", {}).get("acesso_contas_receber", False))
]
pagina = st.navigation(paginas, position="top")
pagina.run()
```

(Ajustar o `import` de `navegacao` para o topo do arquivo, junto dos demais.)

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_navegacao.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add navegacao.py app_pages/portal.py app_streamlit.py tests/test_navegacao.py
git commit -m "feat: portal pós-login e navegação condicional ao Contas a Receber"
```

---

### Task 6: Checkbox de acesso na Administração (`app_pages/administracao.py`)

**Files:**
- Modify: `app_pages/administracao.py`

**Interfaces:**
- Consumes: `banco.listar_usuarios` (com `acesso_contas_receber`, Task 3) e `banco.definir_acesso_contas_receber` (Task 3).

- [ ] **Step 1: Implementar** (página existente; sem teste automatizado — a lógica já está coberta na Task 3)

Adicionar após o bloco `remover_usuario` (antes da seção de fotos, linha ~71):

```python
st.markdown(f"#### {icone('layout-dashboard', 18)} Acesso ao Contas a Receber",
            unsafe_allow_html=True)
st.caption("Usuários marcados veem o portal e as páginas do dashboard de glosas.")
with st.form("acesso_contas_receber"):
    acessos = {}
    for row in banco.listar_usuarios(conn):
        acessos[row["login"]] = st.checkbox(
            f"{row['login']} ({row['nome']})", value=bool(row["acesso_contas_receber"]))
    if st.form_submit_button("Salvar acessos", type="primary"):
        for login, valor in acessos.items():
            banco.definir_acesso_contas_receber(conn, login, valor)
        st.success("Acessos atualizados.")
        st.rerun()
```

- [ ] **Step 2: Verificar sintaxe**

Run: `python -m py_compile app_pages/administracao.py`
Expected: sem saída (OK)

- [ ] **Step 3: Commit**

```bash
git add app_pages/administracao.py
git commit -m "feat: checkbox de acesso ao Contas a Receber na Administração"
```

---

### Task 7: Página Upload DACM (`app_pages/upload_dacm.py`)

**Files:**
- Create: `app_pages/upload_dacm.py`

**Interfaces:**
- Consumes: `parser_dacm.parse_dacm_ans`, `banco_glosas.*`, `ui_comum.icone/formatar_brl/formatar_data_br/VERSAO`.

- [ ] **Step 1: Implementar** (página fina — a lógica está toda testada nas Tasks 1-2)

```python
"""PÁGINA: UPLOAD DACM — envio do DACM (Excel ANS) com prévia e importação."""
import os
import tempfile

import pandas as pd
import streamlit as st

import banco_glosas
import parser_dacm
from ui_comum import icone, formatar_brl, formatar_data_br, VERSAO

st.markdown(f"### {icone('upload', 20, '#1C5A8A')} Upload DACM", unsafe_allow_html=True)
st.caption("Envie o DACM do convênio (Excel .xls ou .xlsx, formato ANS). "
           "Reenviar o mesmo arquivo atualiza as guias — nada é duplicado.")

conn = banco_glosas.conectar()
banco_glosas.inicializar_banco(conn)

arquivo = st.file_uploader("Arquivo do DACM", type=["xls", "xlsx"], key="up_dacm")

if arquivo is not None and ("dacm_parsed" not in st.session_state
                            or st.session_state.get("nome_arquivo_upado") != arquivo.name):
    sufixo = os.path.splitext(arquivo.name)[1].lower()
    tmp = tempfile.NamedTemporaryFile(suffix=sufixo, delete=False)
    tmp.write(arquivo.getvalue())
    tmp.close()
    st.session_state["caminho_temp"] = tmp.name
    st.session_state["nome_arquivo_upado"] = arquivo.name
    st.session_state.pop("dacm_parsed", None)
    st.session_state.pop("erro_parse", None)
    try:
        st.session_state["dacm_parsed"] = parser_dacm.parse_dacm_ans(tmp.name)
    except ValueError as e:
        st.session_state["erro_parse"] = str(e)

if st.session_state.get("erro_parse"):
    st.error(st.session_state["erro_parse"])

parsed = st.session_state.get("dacm_parsed")
if parsed:
    meta = parsed["metadados"]
    guias = parsed["guias"]
    st.markdown("#### Prévia do arquivo")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Convênio detectado", meta["operadora"] or "—")
    c2.metric("Nº do DACM", meta["num_dacm"] or "—")
    c3.metric("Data de emissão", formatar_data_br(meta["data_emissao"]))
    c4.metric("Guias", len(guias))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Guias com glosa", sum(1 for g in guias if g["vl_glosa"] > 0))
    c2.metric("Total processado", f"R$ {formatar_brl(meta['tot_geral_processado'])}")
    c3.metric("Total liberado", f"R$ {formatar_brl(meta['tot_geral_liberado'])}")
    c4.metric("Total glosado", f"R$ {formatar_brl(meta['tot_geral_glosa'])}")

    soma_processado = sum(g["vl_processado"] for g in guias)
    if abs(soma_processado - meta["tot_geral_processado"]) > 0.01:
        st.warning("Conferência: a soma das guias difere do total geral do arquivo. "
                   "Confira o arquivo antes de importar.")
    if parsed["avisos"]:
        with st.expander("Avisos do parser"):
            for aviso in parsed["avisos"]:
                st.write(f"- {aviso}")

    nomes_convenios = [c["nome"] for c in banco_glosas.listar_convenios(conn)]
    padrao = nomes_convenios[0] if nomes_convenios else meta["operadora"]
    nome_convenio = st.text_input("Nome do convênio (como aparecerá no dashboard)",
                                  value=padrao, key="nome_convenio")
    if st.button("Importar DACM", type="primary"):
        try:
            resultado = banco_glosas.importar_dacm(
                conn, parsed, nome_convenio.strip(),
                st.session_state["usuario"]["login"],
                st.session_state["caminho_temp"])
            st.success(f"Importação concluída: {resultado['novas']} guia(s) nova(s), "
                       f"{resultado['atualizadas']} atualizada(s), "
                       f"{resultado['avisos_glosa_zerada']} aviso(s) de glosa zerada.")
            for chave in ("dacm_parsed", "caminho_temp", "nome_arquivo_upado", "erro_parse"):
                st.session_state.pop(chave, None)
            st.rerun()
        except Exception as e:
            st.error(f"Não foi possível importar: {e}")

st.divider()
st.markdown(f"#### {icone('history', 18, '#1C5A8A')} Últimos uploads", unsafe_allow_html=True)
uploads = banco_glosas.listar_uploads(conn, limite=10)
if uploads:
    df = pd.DataFrame([
        {"Data": formatar_data_br(u["criado_em"][:10]), "Usuário": u["usuario"],
         "Convênio": u["convenio"], "Arquivo": u["nome_arquivo"],
         "Nº DACM": u["num_dacm"], "Novas": u["guias_novas"],
         "Atualizadas": u["guias_atualizadas"]}
        for u in uploads])
    st.dataframe(df, hide_index=True)
else:
    st.info("Nenhum upload ainda.")

conn.close()
st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)
```

- [ ] **Step 2: Verificar sintaxe**

Run: `python -m py_compile app_pages/upload_dacm.py`
Expected: sem saída (OK)

- [ ] **Step 3: Commit**

```bash
git add app_pages/upload_dacm.py
git commit -m "feat: página de upload do DACM com prévia e importação"
```

---

### Task 8: Página Dashboard (`app_pages/dashboard_glosas.py`)

**Files:**
- Create: `app_pages/dashboard_glosas.py`

**Interfaces:**
- Consumes: `banco_glosas.resumo_kpis/agrupado_por_convenio/evolucao_mensal/guias_filtradas/ranking_motivos/alertas_aging/avisos_glosa_zerada` (Task 2); `ui_comum.icone/formatar_brl/formatar_data_br/VERSAO`; `plotly.graph_objects`.

- [ ] **Step 1: Implementar**

```python
"""PÁGINA: DASHBOARD DE GLOSAS — KPIs, 4 blocos e alertas de decisão."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import banco_glosas
from ui_comum import icone, formatar_brl, formatar_data_br, VERSAO

st.markdown(f"### {icone('chart-column', 20, '#1C5A8A')} Dashboard de Glosas",
            unsafe_allow_html=True)

conn = banco_glosas.conectar()
banco_glosas.inicializar_banco(conn)

convenios = banco_glosas.listar_convenios(conn)
opcoes = {"Todos": None} | {c["nome"]: c["id"] for c in convenios}
f1, f2, f3 = st.columns(3)
convenio_sel = f1.selectbox("Convênio", list(opcoes), key="f_convenio")
datas_inicio = [r["data_inicio"] for r in conn.execute(
    "SELECT DISTINCT data_inicio FROM guias WHERE data_inicio != '' "
    "ORDER BY data_inicio").fetchall()]
if datas_inicio:
    de = f2.selectbox("De", datas_inicio, index=0, format_func=formatar_data_br, key="f_de")
    ate = f3.selectbox("Até", list(reversed(datas_inicio)), index=0,
                       format_func=formatar_data_br, key="f_ate")
else:
    de = ate = None
convenio_id = opcoes[convenio_sel]

# ---- KPI CARDS ----
kpis = banco_glosas.resumo_kpis(conn, convenio_id=convenio_id, de=de, ate=ate)
c = st.container(horizontal=True)
c.metric("Total Processado", f"R$ {formatar_brl(kpis['processado'])}")
c.metric("Total Liberado", f"R$ {formatar_brl(kpis['liberado'])}")
c.metric("Total Glosado", f"R$ {formatar_brl(kpis['glosado'])}")
c.metric("Taxa de Glosa", f"{kpis['taxa_glosa']:.2f}%")
c2 = st.container(horizontal=True)
c2.metric("Em Recurso", f"R$ {formatar_brl(kpis['em_recurso'])}")
c2.metric("Taxa de Recuperação", f"{kpis['taxa_recuperacao']:.2f}%")
c2.metric("Perda Real", f"R$ {formatar_brl(kpis['perda_real'])}")

# ---- ALERTAS ----
alertas = banco_glosas.alertas_aging(conn)
avisos = banco_glosas.avisos_glosa_zerada(conn)
if alertas:
    st.markdown(f"#### {icone('alarm-clock', 18, '#C0392B')} Recursos estourados "
                f"({len(alertas)})", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame([
        {"Convênio": a["convenio"], "Guia": a["guia"], "Beneficiário": a["beneficiario"],
         "Protocolo": a["protocolo"], "Dias": a["dias"], "Prazo (dias)": a["prazo"],
         "Glosa": f"R$ {formatar_brl(a['vl_glosa'])}"} for a in alertas]), hide_index=True)
if avisos:
    st.markdown(f"#### {icone('bell-ring', 18, '#1C5A8A')} Glosa zerada no reenvio "
                f"({len(avisos)}) — confirme na página Recursos de Glosa",
                unsafe_allow_html=True)
    st.page_link("app_pages/recursos_glosa.py", label="Abrir Recursos de Glosa")

st.divider()

# ---- BLOCO 1: GLOSA POR CONVÊNIO ----
st.markdown(f"#### {icone('building-2', 18, '#1C5A8A')} Glosa por convênio",
            unsafe_allow_html=True)
df_conv = banco_glosas.agrupado_por_convenio(conn, de=de, ate=ate)
if not df_conv.empty:
    fig1 = go.Figure()
    fig1.add_bar(x=df_conv["convenio"], y=df_conv["processado"], name="Processado",
                 marker_color="#1C5A8A")
    fig1.add_bar(x=df_conv["convenio"], y=df_conv["liberado"], name="Liberado",
                 marker_color="#22c55e")
    fig1.add_bar(x=df_conv["convenio"], y=df_conv["glosado"], name="Glosado",
                 marker_color="#ef4444")
    fig1.update_layout(barmode="group", height=320, margin=dict(t=10, b=10))
    st.plotly_chart(fig1, use_container_width=True)
else:
    st.info("Sem dados para o período.")

# ---- BLOCO 2: EVOLUÇÃO MENSAL ----
st.markdown(f"#### {icone('trending-up', 18, '#1C5A8A')} Evolução mensal — "
            f"glosado × recuperado", unsafe_allow_html=True)
df_mes = banco_glosas.evolucao_mensal(conn, convenio_id=convenio_id, de=de, ate=ate)
if not df_mes.empty:
    fig2 = go.Figure()
    fig2.add_scatter(x=df_mes["mes"], y=df_mes["glosado"], name="Glosado",
                     line=dict(color="#ef4444", width=2.5))
    fig2.add_scatter(x=df_mes["mes"], y=df_mes["recuperado"], name="Recuperado",
                     line=dict(color="#22c55e", width=2.5))
    fig2.update_layout(height=300, margin=dict(t=10, b=10))
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("Sem dados para o período.")

# ---- BLOCO 3: PAINEL DE RECURSOS (RESUMO) ----
st.markdown(f"#### {icone('scroll-text', 18, '#1C5A8A')} Painel de recursos por guia",
            unsafe_allow_html=True)
guias = banco_glosas.guias_filtradas(conn, convenio_id=convenio_id, de=de, ate=ate)
if guias:
    df_guias = pd.DataFrame([
        {"Guia": g["guia_prestador"], "Beneficiário": g["beneficiario"],
         "Protocolo": g["protocolo"], "Data": formatar_data_br(g["data_protocolo"]),
         "Glosa": f"R$ {formatar_brl(g['vl_glosa'])}", "Motivo": g["motivo"] or "—",
         "Status": g["status_recurso"], "Recuperado": f"R$ {formatar_brl(g['vl_recuperado'])}"}
        for g in guias])
    st.dataframe(df_guias, hide_index=True, height=360)
    st.page_link("app_pages/recursos_glosa.py",
                 label="Gerenciar recursos (status, valores e avisos)")
else:
    st.info("Nenhuma guia no período.")

# ---- BLOCO 4: MOTIVOS DE GLOSA ----
st.markdown(f"#### {icone('list', 18, '#1C5A8A')} Motivos de glosa",
            unsafe_allow_html=True)
df_motivos = banco_glosas.ranking_motivos(conn, convenio_id=convenio_id, de=de, ate=ate)
if not df_motivos.empty:
    df_top = df_motivos.head(10).iloc[::-1]
    rotulos = [f"{d} [{c}]" if c else d
               for d, c in zip(df_top["descricao"], df_top["cod_glosa"])]
    fig4 = go.Figure(go.Bar(x=df_top["total"], y=rotulos, orientation="h",
                            marker_color="#ef4444"))
    fig4.update_layout(height=max(260, 40 * len(df_top)), margin=dict(t=10, b=10))
    st.plotly_chart(fig4, use_container_width=True)
else:
    st.info("Sem glosas no período.")

conn.close()
st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)
```

- [ ] **Step 2: Verificar sintaxe**

Run: `python -m py_compile app_pages/dashboard_glosas.py`
Expected: sem saída (OK)

- [ ] **Step 3: Commit**

```bash
git add app_pages/dashboard_glosas.py
git commit -m "feat: dashboard de glosas com KPIs, 4 blocos e alertas"
```

---

### Task 9: Página Recursos de Glosa (`app_pages/recursos_glosa.py`)

**Files:**
- Create: `app_pages/recursos_glosa.py`

**Interfaces:**
- Consumes: `banco_glosas.*` (Task 2) e `ui_comum.*`.

- [ ] **Step 1: Implementar**

```python
"""PÁGINA: RECURSOS DE GLOSA — status por guia (linha e lote), avisos e prazos."""
import pandas as pd
import streamlit as st

import banco_glosas
from ui_comum import icone, formatar_brl, formatar_data_br, VERSAO

st.markdown(f"### {icone('scroll-text', 20, '#1C5A8A')} Recursos de Glosa",
            unsafe_allow_html=True)

conn = banco_glosas.conectar()
banco_glosas.inicializar_banco(conn)
usuario_login = st.session_state["usuario"]["login"]

convenios = banco_glosas.listar_convenios(conn)
opcoes = {"Todos": None} | {c["nome"]: c["id"] for c in convenios}
f1, f2, f3, f4 = st.columns([2, 2, 2, 1])
convenio_sel = f1.selectbox("Convênio", list(opcoes), key="r_convenio")
status_sel = f2.selectbox("Status", ["Todos"] + banco_glosas.STATUS, key="r_status")
busca = f3.text_input("Buscar guia ou beneficiário", key="r_busca")
somente_avisos = f4.checkbox("Avisos", key="r_avisos")

guias = banco_glosas.guias_filtradas(
    conn, convenio_id=opcoes[convenio_sel],
    status=None if status_sel == "Todos" else status_sel,
    busca=busca.strip() or None, somente_avisos=somente_avisos)

if guias:
    df = pd.DataFrame([
        {"selecionar": False, "guia_id": g["guia_id"], "Guia": g["guia_prestador"],
         "Beneficiário": g["beneficiario"], "Convênio": g["convenio"],
         "Glosa": g["vl_glosa"], "Motivo": g["motivo"] or "—",
         "Status": g["status_recurso"], "Vl. Recuperado": g["vl_recuperado"],
         "Observação": g["observacao"], "Aviso": bool(g["aviso_glosa_zerada"])}
        for g in guias])
    if "snapshot_recursos" not in st.session_state:
        st.session_state["snapshot_recursos"] = df.copy()
    editado = st.data_editor(
        df, hide_index=True, key="ed_recursos", num_rows="fixed",
        column_config={
            "guia_id": None,
            "selecionar": st.column_config.CheckboxColumn("Selecionar", default=False),
            "Glosa": st.column_config.NumberColumn("Glosa", format="R$ %.2f", disabled=True),
            "Aviso": st.column_config.CheckboxColumn("Glosa zerada", disabled=True),
            "Status": st.column_config.SelectboxColumn(
                "Status", options=banco_glosas.STATUS, required=True),
            "Vl. Recuperado": st.column_config.NumberColumn("Vl. Recuperado", format="R$ %.2f"),
            "Observação": st.column_config.TextColumn("Observação"),
        })
    if st.button("Salvar alterações", type="primary"):
        alteradas = banco_glosas.diff_guias_editadas(
            st.session_state["snapshot_recursos"], editado)
        for a in alteradas:
            banco_glosas.registrar_status(
                conn, a["guia_id"], a["status"],
                vl_recuperado=a["vl_recuperado"], observacao=a["observacao"],
                usuario=usuario_login)
        st.success(f"{len(alteradas)} guia(s) atualizada(s).")
        st.session_state.pop("snapshot_recursos", None)
        st.rerun()

    selecionadas = editado[editado["selecionar"]]["guia_id"].tolist()
    with st.form("lote_recursos"):
        st.markdown(f"**Edição em lote** — {len(selecionadas)} guia(s) selecionada(s)")
        status_lote = st.selectbox("Novo status", banco_glosas.STATUS, key="lote_status")
        vl_lote = st.number_input("Valor recuperado (0 = mantém o atual)",
                                  min_value=0.0, format="%.2f", key="lote_vl")
        if st.form_submit_button("Aplicar em lote", type="primary",
                                 disabled=not selecionadas):
            for gid in selecionadas:
                banco_glosas.registrar_status(
                    conn, int(gid), status_lote,
                    vl_recuperado=vl_lote if vl_lote > 0 else None,
                    usuario=usuario_login)
            st.success(f"Status '{status_lote}' aplicado a {len(selecionadas)} guia(s).")
            st.session_state.pop("snapshot_recursos", None)
            st.rerun()
else:
    st.info("Nenhuma guia com os filtros escolhidos.")

# ---- AVISOS DE GLOSA ZERADA (confirmação de 1 clique) ----
avisos = banco_glosas.avisos_glosa_zerada(conn)
if avisos:
    st.divider()
    st.markdown(f"#### {icone('bell-ring', 18, '#1C5A8A')} Glosa zerada no reenvio "
                f"({len(avisos)})", unsafe_allow_html=True)
    st.caption("Essas guias tinham glosa e chegaram sem glosa no último upload. "
               "Confirme se o recurso foi ganho.")
    for a in avisos:
        c1, c2 = st.columns([4, 1])
        c1.write(f"- Guia {a['guia_prestador']} · {a['beneficiario']} "
                 f"({a['convenio']}) — {a['motivo'] or 'sem motivo registrado'}")
        if c2.button("Confirmar", key=f"conf_{a['id']}"):
            banco_glosas.confirmar_glosa_recebida(conn, a["id"], usuario=usuario_login)
            st.rerun()
    if st.button("Confirmar todas como Glosa Recebida"):
        for a in avisos:
            banco_glosas.confirmar_glosa_recebida(conn, a["id"], usuario=usuario_login)
        st.rerun()

# ---- HISTÓRICO DE UMA GUIA ----
st.divider()
st.markdown(f"#### {icone('history', 18, '#1C5A8A')} Histórico de uma guia",
            unsafe_allow_html=True)
todas = banco_glosas.guias_filtradas(conn)
if todas:
    alvo_hist = st.selectbox(
        "Guia", todas,
        format_func=lambda g: f"{g['guia_prestador']} · {g['beneficiario']} "
                              f"({g['convenio']})", key="hist_guia")
    hist = banco_glosas.historico_status(conn, alvo_hist["guia_id"])
    if hist:
        st.dataframe(pd.DataFrame([
            {"Data": formatar_data_br(h["atualizado_em"][:10]), "De": h["status_de"],
             "Para": h["status_para"], "Recuperado": f"R$ {formatar_brl(h['vl_recuperado'])}",
             "Obs": h["observacao"], "Usuário": h["usuario"]}
            for h in hist]), hide_index=True)
    else:
        st.info("Sem mudanças registradas.")

# ---- PRAZOS POR CONVÊNIO (ADMIN) ----
if st.session_state["usuario"]["admin"]:
    with st.expander(f"{icone('alarm-clock', 18)} Prazos por convênio (alertas)"):
        for c in convenios:
            c1, c2 = st.columns([3, 1])
            atual = c["prazo_recurso_dias"]
            c1.write(f"**{c['nome']}** — prazo atual: "
                     f"{atual if atual else 'não cadastrado'}")
            dias = c2.number_input("Dias", min_value=0, step=5, value=int(atual or 0),
                                   key=f"prazo_{c['id']}")
            if c2.button("Salvar", key=f"salvar_prazo_{c['id']}"):
                banco_glosas.definir_prazo_convenio(conn, c["id"], dias if dias > 0 else None)
                st.rerun()

conn.close()
st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)
```

- [ ] **Step 2: Verificar sintaxe**

Run: `python -m py_compile app_pages/recursos_glosa.py`
Expected: sem saída (OK)

- [ ] **Step 3: Commit**

```bash
git add app_pages/recursos_glosa.py
git commit -m "feat: painel de recursos de glosa com edição em linha e lote"
```

---

### Task 10: Dependência + suíte completa + smoke local

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Adicionar plotly ao requirements.txt**

`requirements.txt` fica:

```
streamlit==1.60.0
pandas==3.0.3
openpyxl==3.1.5
xlrd==2.0.2
bcrypt>=4.0,<5
plotly>=6.0
```

- [ ] **Step 2: Instalar plotly localmente**

Run: `pip install "plotly>=6.0"`
Expected: instalado sem erro

- [ ] **Step 3: Rodar a suíte completa**

Run: `python -m pytest tests/ -v`
Expected: PASS em tudo (com o skip do pendrive se desconectado)

- [ ] **Step 4: Smoke de importação das páginas novas**

Run: `python -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8')) for p in pathlib.Path('app_pages').glob('*.py')]"`
Expected: sem saída (todos os arquivos de página parseiam)

- [ ] **Step 5: Commit**

```bash
git add requirements.txt
git commit -m "chore: dependência plotly para os gráficos do dashboard"
```

---

### Task 11: Deploy no VPS (com autorização do Leonardo)

**Files:** nenhum no repo — deploy por paramiko com script temporário FORA do repo (apagado após uso).

**Pré-requisito:** mensagem explícita do Leonardo autorizando o deploy (nomeando o host pf.lsm.ia.br / 177.153.35.245 e as operações). Procedimento padrão das sessões anteriores (backup, MD5, py_compile, restart, curl, R17):

- [ ] **Step 1: Verificar como o serviço roda o Python** — `systemctl cat atualizacao-pf` (descobrir o interpretador/venv usado pelo ExecStart) e instalar `plotly>=6.0` NESSE ambiente (`pip install` no venv correto).
- [ ] **Step 2: Backup** — `cp -v` de cada arquivo alterado para `.bak-20260906-glosa` em `/opt/atualizacao-pf/`.
- [ ] **Step 3: Enviar por SFTP os arquivos novos/modificados:** `parser_dacm.py`, `banco_glosas.py`, `navegacao.py`, `app_streamlit.py`, `banco.py`, `auth.py`, `ui_comum.py`, `app_pages/portal.py`, `app_pages/upload_dacm.py`, `app_pages/dashboard_glosas.py`, `app_pages/recursos_glosa.py`, `app_pages/administracao.py`, `requirements.txt`.
- [ ] **Step 4: Conferir MD5** local == remoto de cada arquivo.
- [ ] **Step 5:** `mkdir -p /opt/atualizacao-pf/dados/uploads_dacm` (pasta das cópias dos DACMs).
- [ ] **Step 6:** `python3 -m py_compile` de cada .py enviado (com o interpretador do serviço).
- [ ] **Step 7:** `systemctl restart atualizacao-pf` + `systemctl is-active atualizacao-pf` = `active`.
- [ ] **Step 8:** `curl -s -o /dev/null -w "%{http_code}" https://pf.lsm.ia.br` = 200.
- [ ] **Step 9: R17** — grep recursivo da senha root (valor da mensagem de autorização) em `G:/Atualização PF Nuvem` = zero ocorrências; apagar o script temporário de deploy.
- [ ] **Step 10:** Avisar o Leonardo com o resumo (arquivos, backup, serviço ativo, HTTPS 200) e pedir que ele: habilite o próprio acesso ao Contas a Receber na Administração, suba o DACM da Porto Saúde em "CR · Upload DACM" e confira o dashboard.
