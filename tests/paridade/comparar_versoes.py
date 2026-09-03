"""Compara o Hias final gerado pela versão COM (Windows) com o da versão cirúrgica (nuvem).

O que entra no veredito:
  - conjunto de abas (diferente -> exit 2);
  - VALORES das células — fórmulas comparadas como fórmulas (data_only=False):
    o cirúrgico não grava caches de fórmula por design (R24), então o valor
    calculado fica para a validação visual no Excel;
  - formatos (number_format) das células-alvo de BD1/BD2;
  - conjuntos de partes internas de pivô/slicer/tabela, com bytes comparados
    apenas nas partes que o cirúrgico NÃO edita por design nem o Excel
    recalcula ao salvar (slicers e tabelas).

Uso (no Windows):
    python tests/paridade/comparar_versoes.py "saida_com\\Hias_final.xlsx" "saida_cirurgica\\Hias_final.xlsx"
"""
import sys
import zipfile

import openpyxl

# Prefixos cujos bytes diferem LEGITIMAMENTE entre COM e cirúrgico:
# pivotTable* (refreshOnLoad do cirúrgico) e pivotCache* (Excel recalcula ao salvar).
PREFIXOS_FORA = ("pivotTable", "pivotCache")


def _valores(caminho):
    """Células de todas as abas; fórmulas vêm como fórmula (data_only=False)."""
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=False)
    out = {}
    for ws in wb.worksheets:
        out[ws.title] = [[c for c in row] for row in ws.iter_rows(values_only=True)]
    return out


def _formatos(caminho, abas_linhas):
    """number_format das células alvo (data da BD2, moedas etc.)."""
    wb = openpyxl.load_workbook(caminho, read_only=True)
    out = {}
    for aba, linhas in abas_linhas.items():
        if aba not in wb.sheetnames:
            continue  # arquivo sem a aba: o veredito de valores já cobre
        ws = wb[aba]
        out[aba] = {}
        for linha in linhas:
            for fila in ws[linha]:      # tupla de tuplas: intervalo de linhas inteiras
                for cel in fila:        # cada célula da fila
                    if cel.value is not None:
                        out[aba][cel.coordinate] = cel.number_format
    return out


def _partes_internas(caminho):
    """Partes de pivô/slicer/tabela: {nome: bytes}."""
    with zipfile.ZipFile(caminho) as z:
        return {n: z.read(n) for n in z.namelist()
                if ("pivotCache" in n or "pivotTable" in n or "slicer" in n.lower()
                    or "table" in n)}


def main():
    a, b = sys.argv[1], sys.argv[2]
    va, vb = _valores(a), _valores(b)
    if va.keys() != vb.keys():
        print("ABAS DIFERENTES:", set(va) ^ set(vb))
        sys.exit(2)
    n_dif = 0
    for aba in va:
        if va[aba] != vb[aba]:
            n_dif += 1
            print(f"  [DIF VALORES] aba {aba}")
            for i, (ra, rb) in enumerate(zip(va[aba], vb[aba])):
                if ra != rb:
                    print(f"    linha {i+1}: COM={str(ra)[:40]}... cirúrgico={str(rb)[:40]}...")
                    if i > 20:
                        break
    # Formatos: coluna B (data) e C-I (moeda) da BD2, A-Q da BD1
    alvos = {"BD2": ["1:10"], "BD1": ["1:10"]}
    fa, fb = _formatos(a, alvos), _formatos(b, alvos)
    difs_fmt = 0
    for aba in alvos:
        f_aba = fa.get(aba, {})
        g_aba = fb.get(aba, {})
        dif = {k: (f_aba.get(k), g_aba.get(k))
               for k in set(f_aba) | set(g_aba)
               if f_aba.get(k) != g_aba.get(k)}
        if dif:
            difs_fmt += len(dif)
            print(f"  formatos dif {aba}: {dif}")
    pa, pb = _partes_internas(a), _partes_internas(b)
    print("pivot/tabela parts COM:", sorted(pa), "| cirúrgico:", sorted(pb))
    so_preservadas = [n for n in pa if n in pb
                      and not n.startswith(PREFIXOS_FORA)
                      and pa[n] != pb[n]]
    print("  partes com bytes diferentes (fora das editadas por design):", so_preservadas)
    ok = (n_dif == 0 and difs_fmt == 0
          and set(pa) == set(pb) and not so_preservadas)
    print("RESULTADO:", "OK — idêntico" if ok else "REVISAR diferenças")


if __name__ == "__main__":
    main()
