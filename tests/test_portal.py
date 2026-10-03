"""Testes da página portal (Início) — verificação de fonte, porque o AppTest
não executa o portal isolado (st.page_link falha fora do app completo)."""
from pathlib import Path

FONTE = (Path(__file__).resolve().parents[1] / "app_pages" / "portal.py") \
    .read_text(encoding="utf-8")


def test_portal_titulo_sistemas_integrados():
    assert "SISTEMAS INTEGRADOS" in FONTE
    assert "Sua rotina de tarefa" not in FONTE


def test_portal_card_pf_mantem_titulo_e_caption():
    assert "Atualização da Posição Financeira" in FONTE
    assert "Integração automática WPD-26 + Não Identificado." in FONTE


def test_portal_link_dacm_externo_sem_borda():
    assert "https://pf.lsm.ia.br/dacm/" in FONTE
    assert 'type="tertiary"' in FONTE


def test_portal_css_sem_esticamento_das_caixas():
    """Pedido do Leonardo (03/10): cards no tamanho natural, sem esticar —
    o CSS de equalização (height: 100%) esticava os cards sozinhos das
    colunas 2 e 3, que ficavam maiores que os do PF e Glosa."""
    assert "height: 100%" not in FONTE


def test_portal_card_recursos_glosa_condicionado_abaixo_do_pf():
    """Pedido do Leonardo (02/10): card do Recursos de Glosa visível só para
    quem tem o acesso marcado (ou admin), na coluna do card do PF (abaixo)."""
    assert "Recursos de Glosa" in FONTE
    assert "https://pf.lsm.ia.br/glosa/" in FONTE
    assert 'usuario.get("admin")' in FONTE
    assert 'usuario.get("acesso_glosa")' in FONTE
    assert FONTE.index("Abrir Atualização PF") < FONTE.index("Abrir Recursos de Glosa")


def test_portal_admin_ve_todas_as_plataformas():
    """Pedido do Leonardo (02/10): o usuário admin vê TODAS as plataformas do
    portal — PF, DACM × FATURAMENTO, Conciliador e Recursos de Glosa.
    Pedido do Leonardo (03/10): o Pediu Chegou NÃO fica no portal (não estava
    lá antes) — nem card, nem link, nem flag de acesso."""
    assert "Pediu Chegou" not in FONTE
    assert "https://pediuchegou.ia.br" not in FONTE
    assert 'usuario.get("admin")' in FONTE
    assert 'usuario.get("acesso_pediu_chegou")' not in FONTE
    assert "Atualização da Posição Financeira" in FONTE
    assert "DACM × FATURAMENTO" in FONTE
    assert "Conciliador de Convênios" in FONTE
    assert "Recursos de Glosa" in FONTE
