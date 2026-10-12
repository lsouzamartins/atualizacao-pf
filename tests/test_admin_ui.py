"""Testes da página Administração — verificação de fonte (UI Streamlit)."""
from pathlib import Path

FONTE = (Path(__file__).resolve().parents[1] / "app_pages" / "administracao.py") \
    .read_text(encoding="utf-8")


def test_admin_criar_usuario_pede_login_sem_cpf():
    """12/10 (a pedido do Leonardo): o login NÃO é mais CPF — o cadastro pede
    "Login" (o 'Login CPF', planejado em 30/09, foi revertido antes de sair)."""
    assert 'st.text_input("Login"' in FONTE
    assert "Login CPF" not in FONTE


def test_admin_e_so_para_administrador():
    """As informações de cadastro só podem ser vistas pelo administrador."""
    assert 'st.session_state.get("usuario", {}).get("admin")' in FONTE
    assert "Acesso restrito ao administrador." in FONTE


def test_admin_acessos_plataformas_secao_unica():
    """12/10 (pedido do Leonardo): UMA seção 'Acessos das plataformas' com as
    5 plataformas — substitui as duas seções separadas de antes."""
    assert "Acessos das plataformas" in FONTE
    assert "Acesso ao portal (Início) e à Cobrança" not in FONTE
    assert "Acesso aos Recursos de Glosa" not in FONTE


def test_admin_acessos_plataformas_lista_as_cinco():
    """A legenda da seção nomeia as 5 plataformas do portal."""
    assert "Atualização da Posição Financeira" in FONTE
    assert "DACM × FATURAMENTO" in FONTE
    assert "Conciliador de Convênios" in FONTE
    assert "Recursos de Glosa" in FONTE
    assert "Cobrança" in FONTE


def test_admin_acessos_plataformas_um_botao_e_flags_novas():
    """Um único 'Salvar acessos' e as marcas de DACM/Conciliador são
    gravadas pelas funções novas do banco; o PF fica travado e marcado."""
    assert 'st.form_submit_button("Salvar acessos"' in FONTE
    assert "definir_acesso_dacm" in FONTE
    assert "definir_acesso_conciliador" in FONTE
    assert "value=True, disabled=True" in FONTE  # PF travado (e admin)
