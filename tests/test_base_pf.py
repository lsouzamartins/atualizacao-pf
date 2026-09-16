"""Testes da base persistente da Posição Financeira (dados/base_pf/).

A base mestra do site é gerenciada por base_pf.py: salvar (com backup da
anterior), atualizar ao fim do processamento, consultar metadados.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import base_pf


def test_caminho_base_aponta_para_dados_base_pf(tmp_path):
    caminho = base_pf.caminho_base(str(tmp_path))
    assert caminho.endswith(os.path.join("dados", "base_pf", base_pf.NOME_BASE))


def test_base_existe_falso_antes_de_salvar(tmp_path):
    assert base_pf.base_existe(str(tmp_path)) is False


def test_salvar_base_cria_pasta_e_arquivo(tmp_path):
    caminho = base_pf.salvar_base(b"conteudo", pasta_raiz=str(tmp_path))
    assert os.path.isfile(caminho)
    with open(caminho, "rb") as f:
        assert f.read() == b"conteudo"


def test_salvar_base_sobrescrevendo_faz_backup(tmp_path):
    base_pf.salvar_base(b"v1", pasta_raiz=str(tmp_path))
    pasta_backup = str(tmp_path / "saida")
    base_pf.salvar_base(b"v2", pasta_raiz=str(tmp_path), pasta_backup=pasta_backup)

    with open(base_pf.caminho_base(str(tmp_path)), "rb") as f:
        assert f.read() == b"v2"
    backups = [n for n in os.listdir(pasta_backup) if n.startswith("BACKUP_Hias_")]
    assert len(backups) == 1
    with open(os.path.join(pasta_backup, backups[0]), "rb") as f:
        assert f.read() == b"v1"


def test_atualizar_base_substitui_pela_versao_final(tmp_path):
    final = tmp_path / "Posição Financeira Hias_15.09.26.xlsx"
    final.write_bytes(b"final")
    base_pf.atualizar_base(str(final), pasta_raiz=str(tmp_path))
    with open(base_pf.caminho_base(str(tmp_path)), "rb") as f:
        assert f.read() == b"final"


def test_info_base_retorna_metadados(tmp_path):
    base_pf.salvar_base(b"conteudo", pasta_raiz=str(tmp_path))
    info = base_pf.info_base(str(tmp_path))
    assert info["nome"] == base_pf.NOME_BASE
    assert info["tamanho"] == 8
    assert info["modificado"] is not None


def test_info_base_vazia_quando_nao_existe(tmp_path):
    assert base_pf.info_base(str(tmp_path)) == {}
