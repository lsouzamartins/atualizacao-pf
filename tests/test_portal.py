"""Testes da página portal (Início) — verificação de fonte, porque o AppTest
não executa o portal isolado (st.page_link falha fora do app completo)."""
from pathlib import Path

FONTE = (Path(__file__).resolve().parents[1] / "app_pages" / "portal.py") \
    .read_text(encoding="utf-8")


def test_portal_titulo_sistemas_integrados():
    assert "SISTEMAS INTEGRADOS" in FONTE


def test_portal_card_pf_com_titulo_e_caption_novos():
    assert "Atualização da Posição Financeira" in FONTE
    assert "Integração automática WPD-26 + Não Identificado." in FONTE


def test_portal_link_dacm_externo_sem_borda():
    assert "https://pf.lsm.ia.br/dacm/" in FONTE
    assert 'type="tertiary"' in FONTE


def test_portal_css_caixas_com_mesma_altura():
    """Regressão: o CSS de equalização das caixas precisa estar presente —
    sem ele uma caixa pode renderizar mais baixa que a outra."""
    assert "stColumn" in FONTE and "height: 100%;" in FONTE
