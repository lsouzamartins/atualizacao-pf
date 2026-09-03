"""Compara o Hias final gerado pela versão COM (Windows) com o da versão cirúrgica (nuvem).

Uso (no Windows):
    python tests/paridade/comparar_versoes.py "saida_com\\Hias_final.xlsx" "saida_cirurgica\\Hias_final.xlsx"
"""
import sys
import zipfile

import openpyxl


def _valores(caminho):
    """Valores de todas as abas (data_only=True — fórmulas viram cache)."""
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    out = {}
    for ws in wb.worksheets:
        out[ws.title] = [[c for c in row] for row in ws.iter_rows(values_only=True)]
    return out


def _formatos(caminho, abas_linhas):
    """number_format das células alvo (data da BD2, moedas etc.)."""
    wb = openpyxl.load_workbook(caminho, read_only=True)
    out = {}
    for aba, linhas in abas_linhas.items():
        ws = wb[aba]
        out[aba] = {}
        for linha in linhas:
            for fila in ws[linha]:      # tupla de tuplas: intervalo de linhas inteiras
                for cel in fila:        # cada célula da fila
                    if cel.value is not None:
                        out[aba][cel.coordinate] = cel.number_format
    return out


def _pivots(caminho):
    """Partes internas de pivô/slicer/cache (nomes + bytes) dos dois arquivos."""
    with zipfile.ZipFile(caminho) as z:
        return {n: z.read(n) for n in z.namelist()
                if "pivotCache" in n or "slicer" in n.lower() or "pivotTable" in n}


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
                    print(f"    linha {i+1}: COM={str(ra)[:4]}... cirúrgico={str(rb)[:4]}...")
                    if i > 20:
                        break
    print("abas:", list(va), "| abas com diferenças de valores:", n_dif)
    # Formatos: coluna B (data) e C-I (moeda) da BD2, A-Q da BD1
    alvos = {"BD2": ["1:10"], "BD1": ["1:10"]}
    fa, fb = _formatos(a, alvos), _formatos(b, alvos)
    for aba in alvos:
        dif = {k: (fa[aba].get(k), fb[aba].get(k))
               for k in fa[aba] if fa[aba].get(k) != fb[aba].get(k)}
        print(f"  formatos dif {aba}: {dif}")
    pa, pb = _pivots(a), _pivots(b)
    print("pivot parts COM:", sorted(pa), "| cirúrgico:", sorted(pb))
    print("RESULTADO:", "OK — idêntico" if n_dif == 0 else "REVISAR diferenças")


if __name__ == "__main__":
    main()
