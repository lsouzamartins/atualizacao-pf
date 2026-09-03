"""Testes do comparador de paridade COM vs cirúrgico (fixtures sintéticas).

O comparador compara arquivos, não engines: fixtures geradas com openpyxl
são suficientes (o Hias real nunca é tocado aqui — regra global: só leitura).
"""
import subprocess
import sys

from openpyxl import Workbook


def _criar(tmp_path, nome, abas, formato_bd2=None):
    caminho = tmp_path / nome
    wb = Workbook()
    wb.remove(wb.active)
    for titulo, linhas in abas.items():
        ws = wb.create_sheet(titulo)
        for linha in linhas:
            ws.append(linha)
    if formato_bd2 and "BD2" in abas:
        for cel in wb["BD2"][1]:        # coluna B (data) com formato divergente
            cel.number_format = formato_bd2
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


def test_formula_igual_nao_conta_como_dif(tmp_path):
    # o cirúrgico grava fórmulas sem cache — comparar como fórmula dá OK
    abas = {"BD1": [["=B1*2", 2], [3, "b"]], "BD2": [[3.0, "c"]]}
    a = _criar(tmp_path, "com.xlsx", abas)
    b = _criar(tmp_path, "cirurgico.xlsx", abas)
    proc = _rodar(a, b)
    assert "RESULTADO: OK — idêntico" in proc.stdout


def test_formula_diferente_reporta(tmp_path):
    a = _criar(tmp_path, "com.xlsx", {"BD1": [["=B1*2", 2]], "BD2": [[3.0, "c"]]})
    b = _criar(tmp_path, "cirurgico.xlsx", {"BD1": [["=B1*3", 2]], "BD2": [[3.0, "c"]]})
    proc = _rodar(a, b)
    assert "RESULTADO: REVISAR diferenças" in proc.stdout


def test_formato_divergente_entra_no_veredito(tmp_path):
    abas = {"BD1": [[1, "a"]], "BD2": [[3.0, "c"]]}
    a = _criar(tmp_path, "com.xlsx", abas)
    b = _criar(tmp_path, "cirurgico.xlsx", abas, formato_bd2="dd/mm/yyyy")
    proc = _rodar(a, b)
    assert "formatos dif BD2" in proc.stdout
    assert "RESULTADO: REVISAR diferenças" in proc.stdout


def test_sem_bd2_nao_crasha(tmp_path):
    abas = {"BD1": [[1, "a"]]}
    a = _criar(tmp_path, "com.xlsx", abas)
    b = _criar(tmp_path, "cirurgico.xlsx", abas)
    proc = _rodar(a, b)
    assert proc.returncode == 0
    assert "RESULTADO:" in proc.stdout
