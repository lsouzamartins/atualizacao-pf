import io
import os

import pytest
from PIL import Image

import fotos


def _png_bytes(cor=(10, 20, 30), tamanho=(8, 8)):
    buf = io.BytesIO()
    Image.new("RGB", tamanho, cor).save(buf, "PNG")
    return buf.getvalue()


def test_valida_foto_aceita_png_valido():
    ok, erro = fotos.validar_foto(_png_bytes(), "foto.png")
    assert ok and not erro


def test_valida_foto_rejeita_extensao_nao_permitida():
    ok, erro = fotos.validar_foto(_png_bytes(), "foto.gif")
    assert not ok and "PNG" in erro


def test_valida_foto_rejeita_arquivo_grande():
    ok, erro = fotos.validar_foto(b"0" * (fotos.TAMANHO_MAXIMO_BYTES + 1), "foto.png")
    assert not ok and "2 MB" in erro


def test_valida_foto_rejeita_conteudo_que_nao_e_imagem():
    ok, erro = fotos.validar_foto(b"isto nao e uma imagem", "foto.png")
    assert not ok


def test_salvar_foto_grava_png_e_substitui(tmp_path):
    destino = fotos.salvar_foto(str(tmp_path), "leo", _png_bytes((1, 2, 3)), "eu.png")
    assert os.path.exists(destino) and destino.endswith("leo.png")
    with Image.open(destino) as img:
        assert img.getpixel((0, 0)) == (1, 2, 3)
    # segunda gravação substitui a primeira
    fotos.salvar_foto(str(tmp_path), "leo", _png_bytes((9, 9, 9)), "eu2.jpg")
    with Image.open(destino) as img:
        assert img.getpixel((0, 0)) == (9, 9, 9)


def test_salvar_foto_rejeita_conteudo_invalido(tmp_path):
    with pytest.raises(ValueError):
        fotos.salvar_foto(str(tmp_path), "leo", b"nao-imagem", "foto.png")


def test_foto_base64_devolve_none_sem_foto(tmp_path):
    assert fotos.foto_base64(str(tmp_path), "leo") is None
    fotos.salvar_foto(str(tmp_path), "leo", _png_bytes(), "foto.png")
    assert fotos.foto_base64(str(tmp_path), "leo").startswith("data:image/png;base64,")


def test_tem_foto_e_remover_foto(tmp_path):
    assert fotos.tem_foto(str(tmp_path), "leo") is False
    fotos.salvar_foto(str(tmp_path), "leo", _png_bytes(), "foto.png")
    assert fotos.tem_foto(str(tmp_path), "leo") is True
    assert fotos.remover_foto(str(tmp_path), "leo") is True
    assert fotos.remover_foto(str(tmp_path), "leo") is False


def test_login_com_barra_e_rejeitado(tmp_path):
    # proteção contra path traversal no nome do arquivo
    with pytest.raises(ValueError):
        fotos.salvar_foto(str(tmp_path), "../etc/passwd", _png_bytes(), "foto.png")
    with pytest.raises(ValueError):
        fotos.tem_foto(str(tmp_path), "..\\..\\x")
