"""PÁGINA: ADMINISTRAÇÃO — só para admins: usuários, senhas, backup, fotos."""
import os
import streamlit as st
import banco
import fotos
from ui_comum import icone, VERSAO, pastas

if not st.session_state.get("usuario", {}).get("admin"):
    st.error("Acesso restrito ao administrador.")
    st.stop()

conn = banco.conectar()
banco.inicializar_banco(conn)

st.markdown(f"### {icone('circle-check', 20, '#1C5A8A')} Usuários", unsafe_allow_html=True)
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

st.markdown(f"#### {icone('layout-dashboard', 18)} Acessos das plataformas",
            unsafe_allow_html=True)
st.caption("Atualização da Posição Financeira · DACM × FATURAMENTO · "
           "Conciliador de Convênios · Recursos de Glosa · Cobrança. "
           "Caixinha marcada = o usuário vê a plataforma no portal "
           "(a Cobrança também usa esta marca no próprio login). "
           "O DACM e o Conciliador têm login próprio por CPF — a marca "
           "fica guardada aqui para o futuro. O PF é de todo usuário com login.")
with st.form("acessos_plataformas"):
    cab = st.columns([2.4, 1, 1, 1.2, 1, 1.2])
    for col, titulo in zip(cab, ["Usuário", "PF", "DACM", "Conciliador",
                                 "Glosa", "Cobrança"]):
        col.markdown(f"**{titulo}**")
    acessos = {}
    for row in banco.listar_usuarios(conn):
        login = row["login"]
        eh_admin = bool(row["admin"])
        u, pf, dacm, conc, glosa, cob = st.columns([2.4, 1, 1, 1.2, 1, 1.2])
        u.write(f"{login} ({row['nome']})")
        # O PF é de todo usuário com login: caixinha travada e marcada.
        pf.checkbox("PF", value=True, disabled=True,
                    key=f"ac_{login}_pf", label_visibility="collapsed")
        # Admin vê tudo: caixinhas travadas e marcadas (nada é salvo para ele).
        acessos[login] = {
            "dacm": dacm.checkbox("DACM", value=True if eh_admin else bool(row["acesso_dacm"]),
                                  disabled=eh_admin, key=f"ac_{login}_dacm",
                                  label_visibility="collapsed"),
            "conciliador": conc.checkbox("Conciliador",
                                         value=True if eh_admin else bool(row["acesso_conciliador"]),
                                         disabled=eh_admin, key=f"ac_{login}_conciliador",
                                         label_visibility="collapsed"),
            "glosa": glosa.checkbox("Glosa", value=True if eh_admin else bool(row["acesso_glosa"]),
                                    disabled=eh_admin, key=f"ac_{login}_glosa",
                                    label_visibility="collapsed"),
            "cobranca": cob.checkbox("Cobrança",
                                     value=True if eh_admin else bool(row["acesso_contas_receber"]),
                                     disabled=eh_admin, key=f"ac_{login}_cobranca",
                                     label_visibility="collapsed"),
        }
    if st.form_submit_button("Salvar acessos", type="primary"):
        for row in banco.listar_usuarios(conn):
            if row["admin"]:
                continue
            m = acessos[row["login"]]
            banco.definir_acesso_dacm(conn, row["login"], m["dacm"])
            banco.definir_acesso_conciliador(conn, row["login"], m["conciliador"])
            banco.definir_acesso_glosa(conn, row["login"], m["glosa"])
            banco.definir_acesso_contas_receber(conn, row["login"], m["cobranca"])
        st.success("Acessos atualizados.")
        st.rerun()

st.markdown(f"#### {icone('camera', 18)} Foto do usuário (login)", unsafe_allow_html=True)
st.caption("Foto exibida no cartão de login. O arquivo é guardado no tamanho "
           "original, sem cortes (PNG ou JPG, máx. 2 MB).")
alvo_foto = st.selectbox("Usuário", logins, key="foto_alvo")
foto_atual = fotos.foto_base64(pastas()["fotos"], alvo_foto)
if foto_atual:
    st.markdown(f'<img class="foto-admin-preview" src="{foto_atual}" '
                f'alt="Foto atual de {alvo_foto}">', unsafe_allow_html=True)
else:
    st.info("Sem foto cadastrada.")
with st.form("foto_usuario", clear_on_submit=True):
    upload = st.file_uploader("Nova foto (PNG ou JPG, máx. 2 MB)",
                              type=["png", "jpg", "jpeg"], key="up_foto")
    col_salvar, col_remover = st.columns(2)
    with col_salvar:
        botao_salvar = st.form_submit_button("Salvar foto", type="primary")
    with col_remover:
        botao_remover = st.form_submit_button("Remover foto")
    if botao_salvar:
        if upload is None:
            st.warning("Escolha um arquivo de imagem antes de salvar.")
        else:
            try:
                fotos.salvar_foto(pastas()["fotos"], alvo_foto,
                                  upload.getvalue(), upload.name)
                st.success(f"Foto de {alvo_foto} salva.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    if botao_remover:
        if fotos.remover_foto(pastas()["fotos"], alvo_foto):
            st.success(f"Foto de {alvo_foto} removida.")
            st.rerun()
        else:
            st.info(f"{alvo_foto} não tinha foto cadastrada.")

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
