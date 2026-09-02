"""
==============================================================================
AUTENTICAÇÃO — ATUALIZAÇÃO PF · NUVEM
Contas individuais (bcrypt), sessão por aba (st.session_state),
5 falhas → bloqueio de 5 minutos (persistido no banco).
==============================================================================
"""
import streamlit as st

import banco


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
    """Gate de todas as páginas. Sem usuário autenticado, só o formulário renderiza."""
    if st.session_state.get("autenticado"):
        return
    st.markdown("### Atualização da Posição Financeira")
    st.caption("Entre com suas credenciais para continuar.")
    login = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar", type="primary", width="stretch"):
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
    st.stop()


def sair():
    if st.session_state.get("autenticado"):
        st.button("Sair", on_click=lambda: st.session_state.clear())
