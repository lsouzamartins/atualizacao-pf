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
from ui_comum import injetar_css_login

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
                                   "admin": bool(usuario["admin"])}
    st.session_state["token_sessao"] = token
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
    st.markdown('<div class="login-titulo-pagina">Atualização da Posição Financeira</div>',
                unsafe_allow_html=True)
    _, col_centro, _ = st.columns([1, 2, 1], vertical_alignment="center")
    with col_centro:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="login-card-titulo">Acesso ao sistema</div>'
            '<div class="login-card-sub">Entre com suas credenciais para continuar.</div>',
            unsafe_allow_html=True,
        )
        login = st.text_input("Usuário", placeholder="Digite seu usuário",
                              label_visibility="collapsed", key="login_usuario")
        senha = st.text_input("Senha", type="password", placeholder="Digite sua senha",
                              label_visibility="collapsed", key="login_senha")
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
                                                       "admin": bool(usuario["admin"])}
                        st.session_state["token_sessao"] = token
                        st.rerun()
                    else:
                        banco.registrar_falha(conn, login.strip())
                        st.error("Usuário ou senha incorretos.")
            finally:
                conn.close()
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()


def manter_cookie_sessao():
    """Grava o cookie 'pf_sessao' no navegador via componente invisível.

    O Streamlit 1.60 não tem API de escrita de cookies (st.cookies só chega
    em versões posteriores); o JS do iframe grava document.cookie (mesma
    origem, permitido pelo sandbox) e o st.context.cookies o lê na próxima
    carga da página.
    """
    token = st.session_state.get("token_sessao")
    if not token:
        return
    st.components.v1.html(
        "<script>"
        f"document.cookie = \"{NOME_COOKIE}={token}; max-age=604800; path=/; SameSite=Lax; Secure\";"
        "</script>",
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
