"""Testes de configuração do app principal (título e ícone da aba do navegador)."""
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fonte():
    with open(os.path.join(RAIZ, "app_streamlit.py"), encoding="utf-8") as f:
        return f.read()


def test_aba_do_site_titulo_sistemas_integrados():
    """A aba do navegador mostra 'Sistemas Integrados' (pedido 19/09)."""
    assert 'page_title="Sistemas Integrados"' in _fonte()


def test_aba_do_site_icone_pecas_integradas():
    """O ícone da aba (favicon) é o emoji de peças integradas 🧩 (pedido 19/09)."""
    assert 'page_icon="🧩"' in _fonte()
