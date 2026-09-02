import os, sys, json
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