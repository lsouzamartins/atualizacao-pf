# -*- coding: utf-8 -*-
"""
==============================================================================
BASE DA POSIÇÃO FINANCEIRA — PERSISTÊNCIA NO SITE
==============================================================================
Gerencia a Posição Financeira Hias.xlsx mestra em dados/base_pf/:
- consultar se existe e metadados (tamanho, data de modificação);
- salvar uma base nova enviada pelo usuário (com backup da anterior);
- atualizar a base ao fim de cada processamento (cópia do resultado final).

A lógica das fases 0–4 continua intocável em core.py — aqui só há caminhos
e cópia de arquivos.

Revisão: Claude Code (Anthropic) · 15/09/2026
==============================================================================
"""
import os
import shutil
from datetime import datetime

from core import criar_backup_hias


PASTA_RAIZ = os.path.dirname(os.path.abspath(__file__))
NOME_BASE = "Posição Financeira Hias.xlsx"


def caminho_base(pasta_raiz=None) -> str:
    """Caminho da base mestra no site: <raiz>/dados/base_pf/<NOME_BASE>."""
    raiz = pasta_raiz or PASTA_RAIZ
    return os.path.join(raiz, "dados", "base_pf", NOME_BASE)


def garantir_pasta(pasta_raiz=None) -> str:
    """Cria dados/base_pf/ se necessário e devolve o caminho da pasta."""
    pasta = os.path.dirname(caminho_base(pasta_raiz))
    os.makedirs(pasta, exist_ok=True)
    return pasta


def base_existe(pasta_raiz=None) -> bool:
    """True se o site já tem uma base da Posição Financeira cadastrada."""
    return os.path.isfile(caminho_base(pasta_raiz))


def info_base(pasta_raiz=None) -> dict:
    """Metadados da base atual (dict vazio se não existir)."""
    caminho = caminho_base(pasta_raiz)
    if not os.path.isfile(caminho):
        return {}
    stat = os.stat(caminho)
    return {
        "nome": NOME_BASE,
        "caminho": caminho,
        "tamanho": stat.st_size,
        "modificado": datetime.fromtimestamp(stat.st_mtime),
    }


def salvar_base(conteudo: bytes, pasta_raiz=None, pasta_backup=None) -> str:
    """Grava a base enviada pelo usuário. Se já existir uma base, a anterior
    é copiada para pasta_backup (BACKUP_Hias_<timestamp>.xlsx) antes de ser
    sobrescrita. Retorna o caminho da base salva."""
    garantir_pasta(pasta_raiz)
    caminho = caminho_base(pasta_raiz)
    if os.path.isfile(caminho) and pasta_backup:
        os.makedirs(pasta_backup, exist_ok=True)
        criar_backup_hias(caminho, pasta_backup)
    with open(caminho, "wb") as f:
        f.write(conteudo)
    return caminho


def atualizar_base(caminho_final: str, pasta_raiz=None) -> str:
    """Substitui a base mestra pelo resultado de um processamento concluído.
    Retorna o caminho da base atualizada."""
    garantir_pasta(pasta_raiz)
    caminho = caminho_base(pasta_raiz)
    shutil.copy2(caminho_final, caminho)
    return caminho
