"""Conferência pós-execução da Atualização PF — 11/11/2026.

Três frentes, todas em forma de aviso (nada aqui altera a planilha):
1. validações de sanidade dos relatórios do dia (WPD-26 e Não Identificado);
2. comparação opcional com a PF do Manual do Lameirão (só no Manual, só no
   site, baixas/valores divergentes e totais por vencimento);
3. conciliação depósito × baixas por convênio, acumulada no ano: a Quitação
   da BD2 (depósito casado) tem de bater com o Valor Pago das baixas da BD1.
   A BD1 usa nomes curtos ("GEAP SAUDE", "BRADESCO SEGURO") e a BD2 os nomes
   completos do Não Identificado — o ALIAS_CONVENIOS faz a ponte; pares que
   não existem no mapa são apontados para conferência, nunca adivinhados.
"""
from datetime import date, datetime

import openpyxl
import pandas as pd

# BD1 (WPD/faturamento) → BD2 (Não Identificado). Chaves normalizadas
# (maiúsculas, espaços colapsados). Confirmado nos dados de 11/11/2026:
# com este mapa os convênios de 2026 fecham na conciliação ao centavo.
ALIAS_CONVENIOS = {
    "AMIL": "AMIL ASSIST MEDICA INTERNAC",
    "ASSIM SAUDE": "ASSIM",
    "BNDES - FAPES": "FAPES FUND ASSIST PREVI SOC BN",
    "BRADESCO OPERAD": "BRADESCO OPERADORA PLANO",
    "BRADESCO SEGURO": "BRADESCO SEGUROS",
    "CABERJ SAUDE": "CABERJ",
    "CAMPERJ": "CAMPERJ CX MIN PUBL RJ",
    "CAPESAUDE": "CAPESAUDE",
    "CARE PLUS": "CARE PLUS MEDICINA ASSIST",
    "CASSI": "CASSI CX ASSIST FUNC BB",
    "ELETROS - HIAS": "FUND ELETROBRAS SEG SOC - ELETROS",
    "FACHESF": "FACHESF",
    "FUNDACAO ITAU": "FUNDACAO SAUDE ITAU",
    "GEAP SAUDE": "GEAP",
    "GNDI": "NOTRE DAME",
    "LEVE SAUDE": "LEVE SAUDE",
    "MEDISERVICE": "MEDISERVICE ADM DE PLANOS DE SAUDE",
    "OMINT GTS -HIAS": "OMINT ASSISTENCIAL SERVICOS SAUDE",
    "OMINT-SKILL": "OMINT ASSISTENCIAL SERVICOS SAUDE",
    "PETROBRAS AMS": "PETROLEO BRASILEIRO S/A",
    "PORTO SEGURO": "PORTO SEGURO SAUDE",
    "POSTAL SAUDE": "POSTAL SAUDE",
    "REAL GRANDEZA": "REAL GRANDEZA FUND PREV ASSIST SOC",
    "SELECT": "SELECT OPERADORA DE PLANO DE SAUDE",
    "SUL AMERICA": "SUL AMERICA SEGUROS SAUDE",
    "UNIMED FERJ": "UNIMED FERJ",
    "UNIMED INTERCAM": "UNIMED INTERCAMBIO",
}

CAMPOS_VALOR_BD1 = ("Faturado", "Valor Pago", "Valor Glosa")
CAMPOS_TEXTO_BD1 = ("Convênio", "Vencimento", "Baixa", "Nota Fiscal")
CAMPOS_BD2 = ("Depósito Liq.", "Depósito Bruto", "Quitação",
              "Não Identificado", "Acordos", "Glosa Aceita")
TOLERANCIA = 0.01


def _norm(valor) -> str:
    """Nome de convênio sem padding nem espaços repetidos."""
    if valor is None:
        return ""
    return " ".join(str(valor).split())


def _chave(valor) -> str:
    return _norm(valor).upper()


def _num(valor) -> float:
    try:
        if valor is None or isinstance(valor, bool):
            return 0.0
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def _data(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return None


def _brl(valor: float) -> str:
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def _data_br(valor) -> str:
    d = _data(valor)
    return d.strftime("%d/%m/%Y") if d else ""


def _exemplos(valores, limite: int = 5) -> str:
    itens = [str(v) for v in list(valores)[:limite]]
    resto = len(valores) - limite
    texto = ", ".join(itens)
    return f"{texto} e mais {resto}" if resto > 0 else texto


def _coluna(df, nome: str):
    """Coluna do DataFrame ou série nula — validação nunca quebra por
    relatório com coluna faltando."""
    if nome in df.columns:
        return df[nome]
    return pd.Series([None] * len(df), index=df.index)


# ==============================================================================
# 1) Validações dos relatórios do dia
# ==============================================================================
def validar_wpd(df_wpd, ano: int | None = None) -> list[str]:
    """Alertas do WPD-26: vencimento fora da janela plausível, remessa sem
    convênio, valores negativos e remessa repetida. Devolve frases prontas."""
    if df_wpd is None or len(df_wpd) == 0:
        return ["WPD-26 veio vazio — confira o relatório do dia."]
    ano = ano or date.today().year
    limite = ano + 5
    alertas = []

    if "Vencimento" in df_wpd.columns:
        datas = pd.to_datetime(df_wpd["Vencimento"], errors="coerce")
        mask = datas.dt.year.lt(2020) | datas.dt.year.gt(limite)
        if mask.any():
            remessas = _coluna(df_wpd, "Remessa")
            exemplos = [
                f"{remessas.loc[i]} ({_data_br(datas.loc[i])})"
                for i in df_wpd.index[mask][:5]]
            alertas.append(
                f"{int(mask.sum())} remessa(s) com vencimento fora da janela "
                f"2020–{limite}: {_exemplos(exemplos)}")

    if "Convênio" in df_wpd.columns:
        vazio = df_wpd["Convênio"].isna() | (
            df_wpd["Convênio"].astype(str).str.strip() == "")
        if vazio.any():
            alertas.append(
                f"{int(vazio.sum())} remessa(s) sem convênio: "
                f"{_exemplos(_coluna(df_wpd, 'Remessa')[vazio])}")

    for coluna in ("Faturado", "Valor Pago", "Vlr Guia"):
        if coluna in df_wpd.columns:
            valores = pd.to_numeric(df_wpd[coluna], errors="coerce")
            negativo = valores < 0
            if negativo.any():
                alertas.append(
                    f"{int(negativo.sum())} remessa(s) com {coluna} negativo: "
                    f"{_exemplos(_coluna(df_wpd, 'Remessa')[negativo])}")

    if "Remessa" in df_wpd.columns:
        chaves = df_wpd["Remessa"].astype(str).str.strip()
        duplicadas = chaves[chaves.duplicated(keep=False)]
        if len(duplicadas):
            alertas.append(
                f"{len(duplicadas)} linha(s) com remessa repetida no WPD: "
                f"{_exemplos(sorted(set(duplicadas)))}")

    return alertas


def validar_ni(df_ni) -> list[str]:
    """Alertas do Não Identificado: convênio/data ausentes, valores negativos
    e depósito que não fecha (Bruto ≠ Quitação + NI + Acordos + Glosa)."""
    if df_ni is None or len(df_ni) == 0:
        return ["Não Identificado veio vazio — confira o relatório do dia."]
    alertas = []

    if "Convênio" in df_ni.columns:
        vazio = df_ni["Convênio"].isna() | (
            df_ni["Convênio"].astype(str).str.strip() == "")
        if vazio.any():
            alertas.append(f"{int(vazio.sum())} linha(s) do NI sem convênio.")

    if "Data" in df_ni.columns:
        sem_data = pd.to_datetime(df_ni["Data"], errors="coerce").isna()
        if sem_data.any():
            alertas.append(f"{int(sem_data.sum())} linha(s) do NI sem data.")

    # Não Identificado negativo é estorno legítimo (Quitação > Bruto) e existe
    # no histórico inteiro — só depósito negativo configura erro.
    for coluna in ("Depósito Bruto", "Depósito Liq."):
        if coluna in df_ni.columns:
            valores = pd.to_numeric(df_ni[coluna], errors="coerce")
            negativo = valores < 0
            if negativo.any():
                alertas.append(
                    f"{int(negativo.sum())} linha(s) do NI com {coluna} negativo.")

    if "Depósito Bruto" in df_ni.columns:
        colunas = [c for c in ("Quitação", "Não Identificado", "Acordos",
                               "Glosa Aceita") if c in df_ni.columns]
        bruto = pd.to_numeric(df_ni["Depósito Bruto"], errors="coerce").fillna(0)
        soma = sum(pd.to_numeric(df_ni[c], errors="coerce").fillna(0)
                   for c in colunas)
        desbalanceadas = (bruto - soma).abs() > TOLERANCIA
        if desbalanceadas.any():
            convenios = _coluna(df_ni, "Convênio")
            datas_ni = _coluna(df_ni, "Data")
            exemplos = [
                f"{_norm(convenios.loc[i])} {_data_br(datas_ni.loc[i])}"
                f" (bruto {_brl(_num(df_ni.loc[i, 'Depósito Bruto']))}, "
                f"soma {_brl(_num(soma.loc[i]))})"
                for i in df_ni.index[desbalanceadas][:5]]
            alertas.append(
                f"{int(desbalanceadas.sum())} linha(s) do NI em que o depósito "
                f"não fecha com quitação + não identificado + acordos + glosa: "
                f"{_exemplos(exemplos)}")

    return alertas


# ==============================================================================
# 2) Comparação com a PF do Manual (opcional)
# ==============================================================================
def _ler_aba(caminho: str, aba: str, colunas) -> list[dict]:
    livro = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    try:
        if aba not in livro.sheetnames:
            raise ValueError(f'aba "{aba}" não encontrada em {caminho}')
        linhas = livro[aba].iter_rows(values_only=True)
        cabecalho = next(linhas, None) or []
        nomes = [str(c).strip() if c is not None else "" for c in cabecalho]
        indice = {n: i for i, n in enumerate(nomes)}
        faltando = [c for c in colunas if c not in indice]
        if faltando:
            raise ValueError(
                f'coluna(s) {faltando} não encontrada(s) na aba "{aba}"')
        saida = []
        for linha in linhas:
            if not any(v is not None for v in linha):
                continue
            saida.append({c: linha[indice[c]] if indice[c] < len(linha) else None
                          for c in colunas})
        return saida
    finally:
        livro.close()


def _normalizar_bd1(valor) -> str:
    if valor is None:
        return ""
    data = _data(valor)
    if data is not None:
        return data.strftime("%d/%m/%Y")
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def comparar_bd1(xlsx_site: str, xlsx_manual: str) -> dict:
    """BD1 do site × BD1 do Manual por Remessa: exclusivas de cada lado,
    divergências de texto/valor e Faturado por mês de vencimento."""
    colunas = ["Remessa", "Convênio", "Vencimento", "Baixa", "Nota Fiscal",
               "Faturado", "Valor Pago", "Valor Glosa"]
    site = _ler_aba(xlsx_site, "BD1", colunas)
    manual = _ler_aba(xlsx_manual, "BD1", colunas)

    def indexar(linhas):
        saida = {}
        for linha in linhas:
            remessa = _normalizar_bd1(linha["Remessa"])
            if remessa:
                saida[remessa] = linha
        return saida

    idx_site, idx_manual = indexar(site), indexar(manual)

    def resumo(linha):
        return {
            "remessa": _normalizar_bd1(linha["Remessa"]),
            "convenio": _norm(linha["Convênio"]),
            "vencimento": _normalizar_bd1(linha["Vencimento"]),
            "faturado": _num(linha["Faturado"]),
            "baixa": _normalizar_bd1(linha["Baixa"]),
        }

    so_manual = [resumo(idx_manual[r]) for r in sorted(set(idx_manual) - set(idx_site))]
    so_site = [resumo(idx_site[r]) for r in sorted(set(idx_site) - set(idx_manual))]

    divergencias = []
    for remessa in sorted(set(idx_site) & set(idx_manual)):
        s, m = idx_site[remessa], idx_manual[remessa]
        difs = []
        for campo in CAMPOS_TEXTO_BD1:
            v_site = _normalizar_bd1(s[campo])
            v_manual = _normalizar_bd1(m[campo])
            if v_site != v_manual:
                difs.append(f"{campo}: site={v_site!r} manual={v_manual!r}")
        for campo in CAMPOS_VALOR_BD1:
            if abs(_num(s[campo]) - _num(m[campo])) > TOLERANCIA:
                difs.append(f"{campo}: site={_brl(_num(s[campo]))} "
                            f"manual={_brl(_num(m[campo]))}")
        if difs:
            divergencias.append({"remessa": remessa, "difs": difs})

    totais = {}
    for lado, idx in (("site", idx_site), ("manual", idx_manual)):
        for linha in idx.values():
            d = _data(linha["Vencimento"])
            if d is None:
                continue
            chave = (d.year, d.month)
            totais.setdefault(chave, {"site": 0.0, "manual": 0.0})[lado] += _num(
                linha["Faturado"])
    totais_mes = [
        {"ano": a, "mes": m, "site": v["site"], "manual": v["manual"]}
        for (a, m), v in sorted(totais.items())]

    return {"site": len(idx_site), "manual": len(idx_manual),
            "so_manual": so_manual, "so_site": so_site,
            "divergencias": divergencias, "totais_mes": totais_mes}


def comparar_bd2(xlsx_site: str, xlsx_manual: str) -> dict:
    """BD2 do site × BD2 do Manual pela chave (Convênio, Data)."""
    colunas = ["Convênio", "Data"]
    site = _ler_aba(xlsx_site, "BD2", colunas)
    manual = _ler_aba(xlsx_manual, "BD2", colunas)

    def chaves(linhas):
        saida = set()
        for linha in linhas:
            conv = _chave(linha["Convênio"])
            data = _data(linha["Data"])
            if conv and data is not None:
                saida.add((conv, data))
        return saida

    chaves_site, chaves_manual = chaves(site), chaves(manual)

    def listar(chaves):
        return [{"convenio": c, "data": d} for c, d in sorted(chaves)]

    return {"site": len(chaves_site), "manual": len(chaves_manual),
            "so_manual": listar(chaves_manual - chaves_site),
            "so_site": listar(chaves_site - chaves_manual)}


# ==============================================================================
# 3) Conciliação depósito × baixas por convênio
# ==============================================================================
def conciliar_convenios(xlsx_final: str, ano: int | None = None,
                        alias: dict | None = None,
                        tolerancia: float = TOLERANCIA) -> dict:
    """Por convênio e acumulado no ano: Quitação da BD2 (depósito casado) ×
    Valor Pago das baixas da BD1. Situações: ok, divergente, sem_baixas
    (depósito sem baixa correspondente) e sem_deposito (baixa sem depósito)."""
    ano = ano or date.today().year
    mapa = {_chave(k): _norm(v)
            for k, v in (ALIAS_CONVENIOS if alias is None else alias).items()}
    bd2 = _ler_aba(xlsx_final, "BD2", ["Convênio", "Data", "Quitação"])
    bd1 = _ler_aba(xlsx_final, "BD1", ["Convênio", "Baixa", "Valor Pago"])

    depositos: dict[str, float] = {}
    nomes_bd2: dict[str, str] = {}
    for linha in bd2:
        d = _data(linha["Data"])
        conv = _chave(linha["Convênio"])
        if d is None or d.year != ano or not conv:
            continue
        depositos[conv] = depositos.get(conv, 0.0) + _num(linha["Quitação"])
        nomes_bd2.setdefault(conv, _norm(linha["Convênio"]))

    baixas: dict[str, float] = {}
    sem_mapa = set()
    for linha in bd1:
        d = _data(linha["Baixa"])
        conv_bruto = _chave(linha["Convênio"])
        if d is None or d.year != ano or not conv_bruto:
            continue
        canon = mapa.get(conv_bruto)
        if canon is None:
            canon = _norm(linha["Convênio"])
            sem_mapa.add(canon)
        chave = _chave(canon)
        baixas[chave] = baixas.get(chave, 0.0) + _num(linha["Valor Pago"])

    sem_correspondencia = sorted(
        nome for nome in sem_mapa if _chave(nome) not in depositos)

    linhas = []
    for chave in set(depositos) | set(baixas):
        dep = depositos.get(chave, 0.0)
        bai = baixas.get(chave, 0.0)
        if abs(dep) <= tolerancia and abs(bai) <= tolerancia:
            continue
        diferenca = dep - bai
        if abs(dep) > tolerancia and abs(bai) <= tolerancia:
            situacao = "sem_baixas"
        elif abs(bai) > tolerancia and abs(dep) <= tolerancia:
            situacao = "sem_deposito"
        elif abs(diferenca) > tolerancia:
            situacao = "divergente"
        else:
            situacao = "ok"
        linhas.append({
            "convenio": nomes_bd2.get(chave) or chave,
            "depositos": dep, "baixas": bai, "diferenca": diferenca,
            "situacao": situacao})

    linhas.sort(key=lambda r: (-abs(r["diferenca"]), r["convenio"]))
    return {"ano": ano, "linhas": linhas,
            "sem_correspondencia": sem_correspondencia,
            "tolerancia": tolerancia}


# ==============================================================================
# Relatório em texto
# ==============================================================================
def gerar_conferencia(xlsx_final: str, df_wpd=None, df_ni=None,
                      xlsx_manual: str | None = None,
                      ano: int | None = None,
                      alias: dict | None = None) -> str:
    """Texto do relatório exibido/baixado após cada atualização."""
    ano = ano or date.today().year
    hoje = date.today()
    linhas: list[str] = []

    def add(texto: str = "") -> None:
        linhas.append(texto)

    add("=" * 64)
    add(f"  CONFERÊNCIA DA POSIÇÃO FINANCEIRA — {hoje.strftime('%d/%m/%Y')}")
    add("=" * 64)

    add()
    add("1) VALIDAÇÕES DOS RELATÓRIOS DO DIA")
    if df_wpd is None and df_ni is None:
        add("   Relatórios do dia não informados nesta execução.")
    else:
        alertas = []
        if df_wpd is not None:
            alertas += validar_wpd(df_wpd, ano=ano)
        if df_ni is not None:
            alertas += validar_ni(df_ni)
        if alertas:
            for alerta in alertas:
                add(f"   • {alerta}")
        else:
            add("   OK — WPD-26 e Não Identificado sem alertas.")

    add()
    add("2) COMPARAÇÃO COM A PF DO MANUAL")
    if not xlsx_manual:
        add("   Manual não enviado nesta execução (opcional).")
    else:
        bd1 = comparar_bd1(xlsx_final, xlsx_manual)
        add(f"   BD1: site {bd1['site']} × manual {bd1['manual']} remessas")
        if bd1["so_manual"]:
            add(f"   Só no Manual ({len(bd1['so_manual'])}):")
            for r in bd1["so_manual"][:20]:
                add(f"     {r['remessa']} · {r['convenio']} · venc "
                    f"{r['vencimento']} · {_brl(r['faturado'])} · "
                    f"baixa {r['baixa'] or '—'}")
            if len(bd1["so_manual"]) > 20:
                add(f"     ... e mais {len(bd1['so_manual']) - 20}")
        if bd1["so_site"]:
            add(f"   Só no site ({len(bd1['so_site'])}):")
            for r in bd1["so_site"][:20]:
                add(f"     {r['remessa']} · {r['convenio']} · venc "
                    f"{r['vencimento']} · {_brl(r['faturado'])} · "
                    f"baixa {r['baixa'] or '—'}")
            if len(bd1["so_site"]) > 20:
                add(f"     ... e mais {len(bd1['so_site']) - 20}")
        if bd1["divergencias"]:
            add(f"   Remessas com divergência ({len(bd1['divergencias'])}):")
            for r in bd1["divergencias"][:20]:
                add(f"     {r['remessa']}: " + " | ".join(r["difs"]))
            if len(bd1["divergencias"]) > 20:
                add(f"     ... e mais {len(bd1['divergencias']) - 20}")
        if not (bd1["so_manual"] or bd1["so_site"] or bd1["divergencias"]):
            add("   BD1 idêntica à do Manual.")
        add("   Faturado por vencimento (site × manual):")
        for t in bd1["totais_mes"]:
            dif = t["site"] - t["manual"]
            marca = "" if abs(dif) <= TOLERANCIA else "  ← diferença"
            add(f"     {t['mes']:02d}/{t['ano']}: {_brl(t['site'])} × "
                f"{_brl(t['manual'])} (dif {_brl(dif)}){marca}")

        bd2 = comparar_bd2(xlsx_final, xlsx_manual)
        add(f"   BD2: site {bd2['site']} × manual {bd2['manual']} chaves")
        if bd2["so_manual"]:
            add(f"   Só no Manual ({len(bd2['so_manual'])}):")
            for r in bd2["so_manual"][:20]:
                add(f"     {r['convenio']} · {_data_br(r['data'])}")
        if bd2["so_site"]:
            add(f"   Só no site ({len(bd2['so_site'])}):")
            for r in bd2["so_site"][:20]:
                add(f"     {r['convenio']} · {_data_br(r['data'])}")
        if not (bd2["so_manual"] or bd2["so_site"]):
            add("   BD2 idêntica à do Manual.")

    add()
    add(f"3) CONCILIAÇÃO DEPÓSITO × BAIXAS POR CONVÊNIO ({ano})")
    conc = conciliar_convenios(xlsx_final, ano=ano, alias=alias)
    ok = sum(1 for r in conc["linhas"] if r["situacao"] == "ok")
    add(f"   {ok} convênio(s) fecharam ao centavo "
        f"(tolerância {_brl(conc['tolerancia'])}).")
    problemas = [r for r in conc["linhas"] if r["situacao"] != "ok"]
    if problemas:
        add(f"   {len(problemas)} convênio(s) para conferir:")
        for r in problemas[:25]:
            if r["situacao"] == "sem_baixas":
                texto = (f"depósito de {_brl(r['depositos'])} sem baixa "
                         f"correspondente")
            elif r["situacao"] == "sem_deposito":
                texto = (f"baixas de {_brl(r['baixas'])} sem depósito "
                         f"correspondente no NI")
            else:
                texto = (f"depósito {_brl(r['depositos'])} × baixas "
                         f"{_brl(r['baixas'])} (diferença {_brl(r['diferenca'])})")
            add(f"     {r['convenio']}: {texto}")
        if len(problemas) > 25:
            add(f"     ... e mais {len(problemas) - 25}")
    else:
        add("   Todos os convênios fecharam.")
    if conc["sem_correspondencia"]:
        add("   Sem correspondência de nome (confira o mapa BD1→BD2): "
            + ", ".join(conc["sem_correspondencia"]))

    add()
    add("=" * 64)
    return "\n".join(linhas)
