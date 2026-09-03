"""PÁGINA: ADMINISTRAÇÃO — só para admins: usuários, senhas, backup."""
import os
import streamlit as st
import banco
from ui_comum import icone, VERSAO

if not st.session_state.get("usuario", {}).get("admin"):
    st.error("Acesso restrito ao administrador.")
    st.stop()

conn = banco.conectar()
banco.inicializar_banco(conn)

st.markdown(f"### {icone('circle-check', 20, '#1C5A8A')} Usuários")
for row in banco.listar_usuarios(conn):
    papel = "admin" if row["admin"] else "usuário"
    st.write(f"- **{row['login']}** ({row['nome']}) — {papel}")

with st.form("novo_usuario", clear_on_submit=True):
    st.markdown("#### Criar usuário")
    login = st.text_input("Login")
    nome = st.text_input("Nome")
    senha = st.text_input("Senha (mín. 8 caracteres)", type="password")
    admin = st.checkbox("Administrador")
    if st.form_submit_button("Criar", type="primary"):
        try:
            banco.criar_usuario(conn, login.strip(), nome.strip(), senha, admin=admin)
            st.success(f"Usuário {login} criado."); st.rerun()
        except Exception as e:
            st.error(f"Não foi possível criar: {e}")

with st.form("trocar_senha"):
    st.markdown("#### Trocar minha senha")
    atual = st.text_input("Senha atual", type="password")
    nova = st.text_input("Nova senha", type="password")
    if st.form_submit_button("Trocar"):
        import auth
        if auth.trocar_senha(conn, st.session_state["usuario"]["login"], atual, nova):
            st.success("Senha trocada.")
        else:
            st.error("Senha atual incorreta ou nova senha curta demais (mín. 8).")

logins = [r["login"] for r in banco.listar_usuarios(conn)]

with st.form("redefinir_senha"):
    st.markdown("#### Redefinir senha de um usuário")
    alvo = st.selectbox("Usuário", logins)
    nova_senha = st.text_input("Nova senha (mín. 8 caracteres)", type="password")
    if st.form_submit_button("Redefinir"):
        resultado = banco.redefinir_senha(conn, alvo, nova_senha)
        if resultado["ok"]:
            st.success(f"Senha de {alvo} redefinida.")
        else:
            st.error(resultado["erro"])

with st.form("remover_usuario"):
    st.markdown("#### Remover usuário")
    alvo = st.selectbox("Usuário a remover", logins)
    confirmar = st.checkbox("Confirmo que quero remover este usuário")
    if st.form_submit_button("Remover"):
        if not confirmar:
            st.warning("Marque a confirmação para remover o usuário.")
        else:
            resultado = banco.remover_usuario(
                conn, alvo, st.session_state["usuario"]["login"])
            if resultado["ok"]:
                st.success(f"Usuário {alvo} removido.")
            else:
                st.error(resultado["erro"])

st.markdown("#### Backup do banco")
if st.button("Baixar backup (.db)"):
    destino = os.path.join(banco.CAMINHO_PADRAO + ".backup")
    banco.backup_banco(banco.CAMINHO_PADRAO, destino)
    with open(destino, "rb") as f:
        dados = f.read()
    os.remove(destino)
    st.download_button("Baixar agora", data=dados,
                       file_name="pf-backup.db", mime="application/octet-stream")
conn.close()
st.markdown(f'<div class="app-footer">{VERSAO}</div>', unsafe_allow_html=True)
