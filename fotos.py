"""
==============================================================================
FOTOS DE USUÁRIO — ATUALIZAÇÃO PF · NUVEM
Validação, gravação e leitura dos avatares (dados/fotos/<login>.png).

A imagem enviada é guardada SEM cortes nem redimensionamento — a exibição
usa CSS com object-fit: cover, preservando o tamanho original do arquivo.
==============================================================================
"""
import base64
import io
import os
import re

from PIL import Image

EXTENSOES_PERMITIDAS = {".png", ".jpg", ".jpeg"}
TAMANHO_MAXIMO_BYTES = 2 * 1024 * 1024  # 2 MB
# Login seguro para nome de arquivo: letras, números, ponto, traço, sublinhado
_RE_LOGIN_SEGURO = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _login_seguro(login):
    login = (login or "").strip()
    if not _RE_LOGIN_SEGURO.match(login):
        raise ValueError("Login inválido para nome de arquivo.")
    return login


def validar_foto(dados: bytes, nome_original: str = "") -> tuple:
    """(ok, erro). Aceita PNG/JPG de até 2 MB que o PIL consiga abrir."""
    if nome_original:
        ext = os.path.splitext(nome_original)[1].lower()
        if ext not in EXTENSOES_PERMITIDAS:
            return False, "Formato não permitido. Envie uma imagem PNG ou JPG."
    if len(dados) > TAMANHO_MAXIMO_BYTES:
        return False, "Imagem muito grande. Máximo de 2 MB."
    try:
        with Image.open(io.BytesIO(dados)) as img:
            img.load()
            if img.format not in ("PNG", "JPEG"):
                return False, "Formato não reconhecido. Envie uma imagem PNG ou JPG."
    except Exception:
        return False, "Arquivo inválido: não foi possível abrir como imagem."
    return True, ""


def salvar_foto(pasta_fotos: str, login: str, dados: bytes, nome_original: str = "") -> str:
    """Valida, converte para PNG e grava <pasta>/<login>.png (substituição
    atômica). Devolve o caminho gravado; ValueError se a foto for inválida."""
    login = _login_seguro(login)
    ok, erro = validar_foto(dados, nome_original)
    if not ok:
        raise ValueError(erro)
    os.makedirs(pasta_fotos, exist_ok=True)
    with Image.open(io.BytesIO(dados)) as img:
        imagem = img.convert("RGB")
        destino = os.path.join(pasta_fotos, login + ".png")
        temporario = destino + ".tmp"
        imagem.save(temporario, "PNG")
        os.replace(temporario, destino)
    return destino


def remover_foto(pasta_fotos: str, login: str) -> bool:
    """Apaga a foto do usuário; True se havia foto, False se não havia."""
    login = _login_seguro(login)
    caminho = os.path.join(pasta_fotos, login + ".png")
    if os.path.exists(caminho):
        os.remove(caminho)
        return True
    return False


def tem_foto(pasta_fotos: str, login: str) -> bool:
    login = _login_seguro(login)
    return os.path.exists(os.path.join(pasta_fotos, login + ".png"))


def foto_base64(pasta_fotos: str, login: str):
    """Data URI da foto (para <img> no cartão de login) ou None se não houver."""
    login = _login_seguro(login)
    caminho = os.path.join(pasta_fotos, login + ".png")
    if not os.path.exists(caminho):
        return None
    with open(caminho, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
