"""
Testes da tela de login (CSS e requisitos de identidade).

Cobre os artefatos de ui_comum usados por auth.exigir_login():
LOGIN_CSS (estrutura centralizada) e a regra de sistema particular —
nenhum logotipo ou nome do hospital na interface. A lógica de
autenticação em si é coberta por tests/test_auth.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ui_comum

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_login_css_tem_estrutura_centralizada():
    # Streamlit 1.60 renderiza st.container(border=True) como stLayoutWrapper >
    # stVerticalBlock (sem o testid stVerticalBlockBorderWrapper de versões novas).
    assert "stLayoutWrapper" in ui_comum.LOGIN_CSS
    assert ".login-titulo-pagina" in ui_comum.LOGIN_CSS
    assert "stTextInput" in ui_comum.LOGIN_CSS
    assert "linear-gradient" in ui_comum.LOGIN_CSS


def test_exigir_login_cartao_usado_com_container_com_borda():
    """O cartão deve envolver os widgets de verdade (padrão do portal.py),
    não uma div aberta/fechada em markdowns separados (nunca aninha)."""
    import auth
    with open(auth.__file__, encoding="utf-8") as f:
        src = f.read()
    assert "st.container(border=True)" in src
    assert '<div class="login-card">' not in src


def test_login_css_nao_cita_o_hospital():
    assert "Hospital" not in ui_comum.LOGIN_CSS
    assert "Hias" not in ui_comum.LOGIN_CSS


def test_login_css_cartao_470px_altura_natural():
    """Cartão de 470px de largura com ALTURA NATURAL (13/09, a pedido —
    'alarga mais um pouco o quadrado branco'): o min-height 440px forçava
    um quadrado com ~70px de vazio no rodapé. Sem min-height, o cartão
    abraça o conteúdo; 470px fica na faixa boa de 380–500px das telas de
    login modernas (pesquisa web 13/09)."""
    css = ui_comum.LOGIN_CSS
    assert "width: 470px" in css        # largura pedida ('um pouco mais')
    assert "min-height: 440px" not in css  # altura natural, sem quadrado oco
    assert "width: 88px" in css         # avatar proporcional ao cartão maior
    assert "min-height: 44px" in css    # campos no alvo mínimo de toque (WCAG)


def test_login_css_sem_titulo_interno_no_cartao():
    """O título saiu de dentro do cartão (13/09): agora é o título da página
    ('Acesso ao sistema'), no alto — a regra .login-card-titulo vira CSS
    morto e é removida."""
    css = ui_comum.LOGIN_CSS
    assert ".login-card-titulo" not in css


def test_login_css_escopo_do_cartao_com_filhos_diretos():
    """As regras do cartão usam combinador de filho direto (stColumn >
    stVerticalBlock > stLayoutWrapper): sem ele, o stLayoutWrapper das
    colunas INTERNAS do cartão (linha Lembrar de mim + Esqueceu a senha?)
    herdava o width: 470px (medido via Playwright)."""
    css = ui_comum.LOGIN_CSS
    assert ('div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > '
            'div[data-testid="stLayoutWrapper"]') in css


def test_exigir_login_linha_lembrar_de_mim_esqueceu_a_senha():
    """Padrão clássico das telas de login: 'Lembrar de mim' à esquerda e
    'Esqueceu a senha?' à direita na MESMA linha (st.columns), acima do Entrar."""
    import auth
    with open(auth.__file__, encoding="utf-8") as f:
        src = f.read()
    assert 'st.columns(' in src
    assert src.index("login_lembrar") < src.index("login_esqueceu") < src.index("login_entrar")


def test_login_css_espacamento_entre_informacoes():
    """Espaçamento entre as informações do cartão (13/09, a pedido —
    'aumenta o espaço entre as informações'): margens nominais compensam
    a força de ~-16px que o Streamlit aplica entre elementos consecutivos.
    Alvo visual: 16–24px entre avatar/campos/linha/Entrar (pesquisa web)."""
    css = ui_comum.LOGIN_CSS
    assert "margin: 0 auto 2rem auto" in css   # avatar -> campos (~18px visuais)
    assert "margin-bottom: 1.25rem" in css     # entre campos (~18px visuais)
    assert "margin: 0 0 .75rem 0" in css       # linha -> Entrar (~20px visuais)


def test_login_css_centralizacao_nao_atinge_colunas_internas():
    """A regra de centralização vertical (min-height no stHorizontalBlock)
    deve excluir blocos ANINHADOS — o st.columns interno do cartão (linha
    Lembrar de mim + Esqueceu a senha?) também é um stHorizontalBlock e,
    sem o :not(... *), herdava o min-height de 100vh e criava um vão de
    ~424px entre a Senha e o checkbox (medido via Playwright)."""
    css = ui_comum.LOGIN_CSS
    assert 'div[data-testid="stHorizontalBlock"]:not(div[data-testid="stHorizontalBlock"] *)' in css


def test_nenhum_logo_do_hospital_na_interface():
    """Sistema particular: nada de logotipos do hospital na UI do app."""
    with open(ui_comum.__file__, encoding="utf-8") as f:
        src_ui = f.read()
    assert "Logo_Hias" not in src_ui
    assert "logo_topo_Israelita" not in src_ui
    with open(os.path.join(RAIZ, "app_streamlit.py"), encoding="utf-8") as f:
        src_app = f.read()
    assert "🏥" not in src_app


def test_exigir_login_tem_titulo_cartao_e_mesma_logica():
    import auth
    with open(auth.__file__, encoding="utf-8") as f:
        src = f.read()
    # 13/09, a pedido: o título grande da página passou a ser
    # 'Acesso ao sistema' (antes 'Atualização da Posição Financeira') e o
    # título interno do cartão foi removido (evita duplicar o nome).
    assert "Atualização da Posição Financeira" not in src
    assert "Acesso ao sistema" in src
    assert 'class="login-card-titulo"' not in src  # sem título dentro do cartão
    assert "banco.pode_tentar" in src
    assert "banco.autenticar" in src
    assert "banco.registrar_falha" in src
    assert "st.stop()" in src


def test_login_css_tem_fundo_navy_liso():
    """Fundo da tela de login (24/09, a pedido — o desenho de setas foi
    removido): azul-marinho liso, sem imagem embutida."""
    css = ui_comum.LOGIN_CSS
    assert "data:image/jpeg;base64" not in css  # sem imagem de fundo
    assert "#131A3D" in css                     # navy liso


def test_exigir_login_tem_login_senha_entrar_em_portugues():
    """Estrutura do EPS: campo Login, 'Lembrar de mim', Entrar e 'Esqueceu a senha?'."""
    import auth
    with open(auth.__file__, encoding="utf-8") as f:
        src = f.read()
    assert 'st.text_input("Login"' in src
    assert "Digite seu login" in src
    assert "Digite seu usuário" not in src
    assert '"Lembrar de mim"' in src
    assert '"Esqueceu a senha?"' in src
    assert "Fale com o administrador" in src
    assert 'st.button("Entrar"' in src
    # Subtítulo removido a pedido do usuário (12/09): só o título no cartão.
    assert "Entre com suas credenciais" not in src


def test_exigir_login_tem_rodape_desenvolvedor():
    """Rodapé da tela de login: mesmo crédito padrão do app
    (13/09, a pedido — 'deixa todas iguais'). O texto completo fica em
    ui_comum.VERSAO (teste de igualdade em test_ui_comum); aqui o markdown
    é montado em literais de várias linhas, então confiro os pedaços."""
    import auth
    with open(auth.__file__, encoding="utf-8") as f:
        src = f.read()
    assert "Desenvolvedor: Leonardo Martins" in src
    assert "Revisado por Claude Code (Anthropic)" in src
    assert "V 4.2026.0913" in src
    assert "Streamlit + Lucide" in src
    assert ".login-rodape" in ui_comum.LOGIN_CSS
