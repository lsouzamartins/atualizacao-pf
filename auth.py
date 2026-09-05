"""
==============================================================================
AUTENTICAÇÃO — ATUALIZAÇÃO PF · NUVEM
Contas individuais (bcrypt), sessão por aba (st.session_state),
5 falhas → bloqueio de 5 minutos (persistido no banco).
==============================================================================
"""
import streamlit as st

import banco
from ui_comum import injetar_css_login


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


def exigir_login():
    """Gate de todas as páginas. Sem usuário autenticado, só o formulário renderiza.

    Tela de login: título no topo centralizado, cartão branco com o formulário
    no centro da página. A lógica de autenticação é a mesma da versão anterior
    (bloqueio de 5 minutos, sessão por aba).
    """
    if st.session_state.get("autenticado"):
        return
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
                pode, _ = banco.pode_tentar(conn, login.strip())
                if not pode:
                    st.error("Muitas tentativas erradas. Aguarde 5 minutos e tente de novo.")
                else:
                    usuario = banco.autenticar(conn, login.strip(), senha)
                    if usuario is not None:
                        st.session_state["autenticado"] = True
                        st.session_state["usuario"] = {"login": login.strip(),
                                                       "admin": bool(usuario["admin"])}
                        st.rerun()
                    else:
                        banco.registrar_falha(conn, login.strip())
                        st.error("Usuário ou senha incorretos.")
            finally:
                conn.close()
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()


def sair():
    if st.session_state.get("autenticado"):
        st.button("Sair", on_click=lambda: st.session_state.clear())
