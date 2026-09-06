import os, sys, json
from datetime import datetime
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core

def test_processar_fases_2_3_4_hias_chama_runner(tmp_path, monkeypatch, capsys):
    chamadas = []
    class FakeProc:
        returncode = 0
        stdout, stderr = "log do runner\n", ""
    def fake_run(cmd, **kw):
        chamadas.append(cmd)
        return FakeProc()
    monkeypatch.setattr(core.subprocess, "run", fake_run)
    core.processar_fases_2_3_4_hias("l.xlsx", "b.xlsx", "f.xlsx",
                                    str(tmp_path), str(tmp_path), "w.xlsx")
    payload = json.loads(chamadas[0][-1])
    assert payload["limpo"] == "l.xlsx" and payload["final"] == "f.xlsx"
    assert "log do runner" in capsys.readouterr().out

def test_salvar_log_erro_inclui_fase_e_log_da_execucao(tmp_path):
    try:
        raise ValueError("arquivo não encontrado")
    except ValueError as e:
        caminho = core.salvar_log_erro(
            str(tmp_path), e,
            log_execucao="[FASE 2] integrando ao Hias...\n",
            fase="Fases 2-4 (Integração Hias)")
    with open(caminho, encoding="utf-8") as f:
        conteudo = f.read()
    assert "Fase: Fases 2-4 (Integração Hias)" in conteudo
    assert "[FASE 2] integrando ao Hias..." in conteudo
    assert "ValueError: arquivo não encontrado" in conteudo
    assert "Traceback" in conteudo

def test_salvar_log_erro_sem_contexto_continua_funcionando(tmp_path):
    try:
        raise RuntimeError("simples")
    except RuntimeError as e:
        caminho = core.salvar_log_erro(str(tmp_path), e)
    with open(caminho, encoding="utf-8") as f:
        conteudo = f.read()
    assert "RuntimeError: simples" in conteudo
    assert "Fase:" not in conteudo

def test_salvar_log_erro_rotaciona_5(tmp_path):
    for i in range(7):
        try:
            raise RuntimeError(f"erro {i}")
        except RuntimeError as e:
            core.salvar_log_erro(str(tmp_path), e,
                                 agora=datetime(2026, 9, 5, 10, 0, i))
    logs = sorted(f for f in os.listdir(str(tmp_path))
                  if f.startswith("erro_") and f.endswith(".txt"))
    assert len(logs) == 5
    assert logs[0] == "erro_20260905_100002.txt"  # o mais antigo mantido é o erro 2
    assert logs[-1] == "erro_20260905_100006.txt"

def _id_do_arquivo(nome):
    return int(nome[len("execucao_"):-len(".txt")])

def test_salvar_log_execucao_rotaciona_20(tmp_path):
    for i in range(1, 24):
        caminho = core.salvar_log_execucao(str(tmp_path), i, f"log da execução {i}")
    restantes = sorted((f for f in os.listdir(str(tmp_path))
                        if f.startswith("execucao_") and f.endswith(".txt")),
                       key=_id_do_arquivo)
    assert len(restantes) == 20
    assert restantes[0] == "execucao_4.txt"  # os 3 mais antigos foram removidos
    assert restantes[-1] == "execucao_23.txt"
    with open(caminho, encoding="utf-8") as f:
        assert f.read() == "log da execução 23"
