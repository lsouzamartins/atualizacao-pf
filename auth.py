"""
==============================================================================
AUTENTICAÇÃO — ATUALIZAÇÃO PF · NUVEM
Contas individuais (bcrypt), sessão por aba (st.session_state),
5 falhas → bloqueio de 5 minutos (persistido no banco).
"Manter conectado": cookie pf_sessao (token de 7 dias, só hash no banco).
==============================================================================
"""
import streamlit as st

import banco
import fotos
from ui_comum import injetar_css_login, PASTA_FOTOS

NOME_COOKIE = "pf_sessao"


def _conexao():
    return banco.conectar()


def verificar_credenciais(conn, login, senha):
    return banco.autenticar(conn, login, senha) is not None


def trocar_senha(conn, login, senha_antiga, senha_nova):
    if len(senha_nova) < 8:
        return False
    if not verificar_credenciais(conn, login, senha_antiga):
        return False
    novo_hash = banco._hash_senha(senha_nova)
    conn.execute("UPDATE usuarios SET senha_hash=? WHERE login=?",
                 (novo_hash, login))
    conn.commit()
    return True


def usuario_atual():
    return st.session_state.get("usuario")


def _avatar_login(login_digitado):
    """HTML do avatar do cartão de login: foto do usuário (se existir) ou
    círculo padrão com a inicial / ícone de pessoa."""
    login_digitado = (login_digitado or "").strip()
    if login_digitado:
        try:
            conn = _conexao()
            try:
                banco.inicializar_banco(conn)
                existe = banco.login_existe(conn, login_digitado)
            finally:
                conn.close()
            if existe:
                foto = fotos.foto_base64(PASTA_FOTOS, login_digitado)
                if foto:
                    return (f'<img class="login-avatar" src="{foto}" '
                            f'alt="Foto de {login_digitado}">')
        except Exception:
            pass  # login fora do padrão seguro → avatar padrão
        inicial = login_digitado[:1].upper()
        return f'<div class="login-avatar-padrao">{inicial}</div>'
    return (
        '<div class="login-avatar-padrao">'
        '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48"'
        ' viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/></svg>'
        '</div>'
    )


def _restaurar_sessao(token):
    """Loga automaticamente se o token do cookie for válido (máx. 7 dias)."""
    conn = _conexao()
    try:
        banco.inicializar_banco(conn)
        usuario = banco.validar_token_sessao(conn, token)
    finally:
        conn.close()
    if usuario is None:
        return False
    st.session_state["autenticado"] = True
    st.session_state["usuario"] = {"login": usuario["login"],
                                   "admin": bool(usuario["admin"]),
                                   "acesso_contas_receber":
                                       bool(usuario["acesso_contas_receber"])}
    st.session_state["token_sessao"] = token
    st.session_state["lembrar_sessao"] = True  # sessão veio do cookie: mantém
    return True


def exigir_login():
    """Gate de todas as páginas. Sem usuário autenticado, só o formulário renderiza.

    Tela de login: título no topo centralizado, cartão branco com o formulário
    no centro da página. A lógica de autenticação é a mesma da versão anterior
    (bloqueio de 5 minutos, sessão por aba) + "manter conectado" por 7 dias.
    """
    if st.session_state.get("autenticado"):
        return
    # "Manter conectado": cookie gravado pelo navegador → login automático
    token = st.context.cookies.get(NOME_COOKIE)
    if token and _restaurar_sessao(token):
        st.rerun()
    injetar_css_login()
    # Título da página (13/09, a pedido): 'Acesso ao sistema' no alto,
    # no lugar do nome antigo do app.
    st.markdown('<div class="login-titulo-pagina">Acesso ao sistema</div>',
                unsafe_allow_html=True)
    _, col_centro, _ = st.columns([1, 2, 1], vertical_alignment="center")
    with col_centro:
        # Cartão do login: st.container(border=True) é o único wrapper que de
        # fato envolve os widgets. Uma <div> aberta num markdown e fechada em
        # outro não aninha — o HTML de cada elemento é um fragmento separado
        # (a div fecha sozinha e o cartão renderizava vazio, como um quadrado
        # branco acima do formulário). O LOGIN_CSS mira este container via
        # div[data-testid="stVerticalBlockBorderWrapper"].
        with st.container(border=True):
            # (13/09: o título 'Acesso ao sistema' saiu do cartão — agora é o
            # título da página, no alto, e evita duplicar com o cartão.)
            # Avatar do usuário digitado: foto cadastrada, inicial ou ícone padrão.
            # O empty() reserva o espaço no topo do cartão; o markdown o preenche a
            # cada rerun (o on_change do campo dispara rerun a cada tecla digitada).
            slot_avatar = st.empty()
            login = st.text_input("Login", placeholder="Digite seu login",
                                  label_visibility="collapsed", key="login_usuario",
                                  on_change=lambda: None)
            senha = st.text_input("Senha", type="password", placeholder="Digite sua senha",
                                  label_visibility="collapsed", key="login_senha")
            slot_avatar.markdown(_avatar_login(login), unsafe_allow_html=True)
            # Padrão clássico das telas de login: 'Lembrar de mim' à esquerda e
            # 'Esqueceu a senha?' à direita, na mesma linha, acima do Entrar.
            mostrar_recuperacao = False
            col_lembrar, col_esqueceu = st.columns([1, 1], vertical_alignment="center")
            with col_lembrar:
                lembrar = st.checkbox("Lembrar de mim", key="login_lembrar")
            with col_esqueceu:
                # Estrutura do EPS: link de recuperação. Sem e-mail no sistema,
                # o caminho real é o administrador redefinir na Administração.
                if st.button("Esqueceu a senha?", type="tertiary", key="login_esqueceu"):
                    mostrar_recuperacao = True
            if st.button("Entrar", type="primary", width="stretch", key="login_entrar"):
                conn = _conexao()
                try:
                    banco.inicializar_banco(conn)  # garante as tabelas (inclusive sessoes)
                    pode, _ = banco.pode_tentar(conn, login.strip())
                    if not pode:
                        st.error("Muitas tentativas erradas. Aguarde 5 minutos e tente de novo.")
                    else:
                        usuario = banco.autenticar(conn, login.strip(), senha)
                        if usuario is not None:
                            token = banco.criar_sessao(conn, login.strip())
                            st.session_state["autenticado"] = True
                            st.session_state["usuario"] = {"login": login.strip(),
                                                           "admin": bool(usuario["admin"]),
                                                           "acesso_contas_receber":
                                                               bool(usuario["acesso_contas_receber"])}
                            st.session_state["token_sessao"] = token
                            st.session_state["lembrar_sessao"] = bool(lembrar)
                            st.rerun()
                        else:
                            banco.registrar_falha(conn, login.strip())
                            st.error("Usuário ou senha incorretos.")
                finally:
                    conn.close()
            # Aviso do link de recuperação, abaixo do Entrar (fora da linha).
            if mostrar_recuperacao:
                st.info("Esqueceu a senha? Fale com o administrador do sistema "
                        "para redefini-la.")
    # Rodapé da tela de login (a pedido): crédito do desenvolvedor e do vetor
    # de fundo (atribuição exigida pela licença gratuita do Freepik).
    st.markdown(
        '<div class="login-rodape">Desenvolvedor: Leonardo Martins · 09/2026 · '
        'Desenvolvido com Claude Code · Fundo: Freepik</div>',
        unsafe_allow_html=True,
    )
    st.stop()


def script_cookie_sessao(token):
    """JS que grava (token) ou apaga (None) o cookie 'pf_sessao' no navegador."""
    if token:
        return (f'document.cookie = "{NOME_COOKIE}={token}; max-age=604800; '
                'path=/; SameSite=Lax; Secure";')
    return (f'document.cookie = "{NOME_COOKIE}=; max-age=0; '
            'path=/; SameSite=Lax; Secure";')


def manter_cookie_sessao():
    """Grava ou apaga o cookie 'pf_sessao' conforme a escolha 'Lembrar de mim'.

    Marcado: cookie de 7 dias (sessão restaurada nas próximas visitas).
    Desmarcado: apaga cookie antigo, se houver (sessão só nesta aba).
    O Streamlit 1.60 não tem API de escrita de cookies (st.cookies só chega
    em versões posteriores); o JS do iframe grava document.cookie (mesma
    origem, permitido pelo sandbox) e o st.context.cookies o lê na próxima
    carga da página.
    """
    token = st.session_state.get("token_sessao")
    if not token:
        return
    lembrar = st.session_state.get("lembrar_sessao", False)
    st.components.v1.html(
        f"<script>{script_cookie_sessao(token if lembrar else None)}</script>",
        height=0, width=0,
    )


def sair():
    if not st.session_state.get("autenticado"):
        return

    def _sair():
        # Invalida a sessão no banco (o cookie restante no navegador vira
        # token morto) e limpa a sessão da aba.
        token = st.session_state.get("token_sessao")
        if token:
            try:
                conn = banco.conectar()
                banco.inicializar_banco(conn)
                banco.remover_sessao(conn, token)
                conn.close()
            except Exception:
                pass
        st.session_state.clear()

    st.button("Sair", on_click=_sair)
