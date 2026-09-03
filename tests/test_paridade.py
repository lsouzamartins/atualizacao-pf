"""Testes do comparador de paridade COM vs cirúrgico (fixtures sintéticas).

O comparador compara arquivos, não engines: fixtures geradas com openpyxl
são suficientes (o Hias real nunca é tocado aqui — regra global: só leitura).
"""
import subprocess
import sys

from openpyxl import Workbook


def _criar(tmp_path, nome, abas):
    caminho = tmp_path / nome
    wb = Workbook()
    wb.remove(wb.active)
    for titulo, linhas in abas.items():
        ws = wb.create_sheet(titulo)
        for linha in linhas:
            ws.append(linha)
    wb.save(caminho)
    return caminho


def _rodar(a, b):
    return subprocess.run([sys.executable, "tests/paridade/comparar_versoes.py",
                           str(a), str(b)], capture_output=True, text=True)


def test_arquivos_identicos(tmp_path):
    abas = {"BD1": [[1, "a"], [2, "b"]], "BD2": [[3.0, "c"]], "À Quitar": [["x"]]}
    a = _criar(tmp_path, "com.xlsx", abas)
    b = _criar(tmp_path, "cirurgico.xlsx", abas)
    proc = _rodar(a, b)
    assert proc.returncode == 0
    assert "RESULTADO: OK — idêntico" in proc.stdout


def test_diferenca_de_valores_reporta(tmp_path):
    a = _criar(tmp_path, "com.xlsx", {"BD1": [[1, "a"], [2, "b"]], "BD2": [[3.0, "c"]]})
    b = _criar(tmp_path, "cirurgico.xlsx", {"BD1": [[1, "a"], [2, "X"]], "BD2": [[3.0, "c"]]})
    proc = _rodar(a, b)
    assert "RESULTADO: REVISAR diferenças" in proc.stdout
    assert "[DIF VALORES] aba BD1" in proc.stdout


def test_abas_diferentes_sai_com_2(tmp_path):
    a = _criar(tmp_path, "com.xlsx", {"BD1": [[1, "a"]], "BD2": [[3.0, "c"]]})
    b = _criar(tmp_path, "cirurgico.xlsx", {"BD1": [[1, "a"]]})
    proc = _rodar(a, b)
    assert proc.returncode == 2
    assert "ABAS DIFERENTES" in proc.stdout
