"""PÁGINA: ADMINISTRAÇÃO — só para admins: usuários, senhas, backup, fotos."""
import os
from datetime import datetime

import streamlit as st

import banco
import fotos
from ui_comum import icone, VERSAO, pastas, formatar_data_br

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
           "Conciliador de Convênios · Recursos de Glosa · Cobrança · "
           "Controle de Ponto. "
           "Caixinha marcada = o usuário vê a plataforma no portal "
           "(a Cobrança também usa esta marca no próprio login). "
           "O DACM e o Conciliador têm login próprio por CPF — a marca "
           "fica guardada aqui para o futuro. O PF é de todo usuário com login.")
with st.form("acessos_plataformas"):
    cab = st.columns([2.4, 1, 1, 1.2, 1, 1.2, 1])
    for col, titulo in zip(cab, ["Usuário", "PF", "DACM", "Conciliador",
                                 "Glosa", "Cobrança", "Ponto"]):
        col.markdown(f"**{titulo}**")
    acessos = {}
    for row in banco.listar_usuarios(conn):
        login = row["login"]
        eh_admin = bool(row["admin"])
        u, pf, dacm, conc, glosa, cob, ponto = st.columns(
            [2.4, 1, 1, 1.2, 1, 1.2, 1])
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
            "ponto": ponto.checkbox("Ponto",
                                    value=True if eh_admin else bool(row["acesso_ponto"]),
                                    disabled=eh_admin, key=f"ac_{login}_ponto",
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
            banco.definir_acesso_ponto(conn, row["login"], m["ponto"])
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

st.markdown(f"#### {icone('arrow-left-right', 18)} Mover ponto entre usuários",
            unsafe_allow_html=True)
st.caption("Move todos os dias e envios de Controle de Ponto de um usuário "
           "para outro. Datas que já existem no destino ficam com o conteúdo "
           "do destino (o dia repetido sai da origem), salvo se você marcar "
           "para sobrescrever com o conteúdo da origem. O banco é copiado "
           "antes da alteração.")
flash_ponto = st.session_state.pop("mover_ponto_flash", None)
if flash_ponto:
    st.success(flash_ponto)

col_origem, col_destino = st.columns(2)
origem_ponto = col_origem.selectbox("De (origem)", logins,
                                    key="ponto_mover_de")
destino_ponto = col_destino.selectbox("Para (destino)", logins,
                                      key="ponto_mover_para")
registros_origem = banco.registros_ponto(conn, origem_ponto)
registros_destino = banco.registros_ponto(conn, destino_ponto)
total_uploads = conn.execute(
    "SELECT COUNT(*) FROM ponto_uploads WHERE dono=?",
    (origem_ponto,)).fetchone()[0]
conflitos = sorted(r["data"] for r in registros_origem
                   if r["data"] in {d["data"] for d in registros_destino})
st.write(f"**{origem_ponto}**: {len(registros_origem)} dia(s) e "
         f"{total_uploads} envio(s) de planilha.")
ultimos_uploads = banco.listar_uploads_ponto(conn, origem_ponto, limite=5)
if ultimos_uploads:
    st.caption("Envios: " + " · ".join(
        f"{u['nome_arquivo']} ({formatar_data_br(u['periodo_de'])} a "
        f"{formatar_data_br(u['periodo_ate'])})" for u in ultimos_uploads))
sobrescrever_ponto = False
if conflitos:
    amostra = ", ".join(formatar_data_br(d.isoformat()) for d in conflitos[:10])
    if len(conflitos) > 10:
        amostra += f" … (+{len(conflitos) - 10})"
    st.warning(f"{len(conflitos)} data(s) já existem em {destino_ponto} e "
               f"ficarão com o conteúdo do destino (o dia repetido sai de "
               f"{origem_ponto}): {amostra}. "
               "Marque abaixo para sobrescrever o destino com o conteúdo "
               "da origem.")
    sobrescrever_ponto = st.checkbox(
        "Sobrescrever as datas repetidas com o conteúdo da origem",
        key=f"ponto_mover_sobrescrever_{origem_ponto}_{destino_ponto}")
confirmar_mover = st.checkbox(
    f"Confirmo mover o ponto de {origem_ponto} para {destino_ponto}",
    key=f"ponto_mover_confirmar_{origem_ponto}_{destino_ponto}")
if st.button("Mover ponto", type="primary", key="ponto_mover_botao"):
    if origem_ponto == destino_ponto:
        st.error("Escolha usuários diferentes para origem e destino.")
    elif not confirmar_mover:
        st.warning("Marque a confirmação para mover o ponto.")
    else:
        try:
            pasta_backup = os.path.join(
                os.path.dirname(banco.CAMINHO_PADRAO), "backups")
            os.makedirs(pasta_backup, exist_ok=True)
            caminho_backup = os.path.join(
                pasta_backup,
                f"pf-antes-mover-ponto-{datetime.now():%Y%m%d-%H%M%S}.db")
            banco.backup_banco(banco.CAMINHO_PADRAO, caminho_backup)
            resultado = banco.mover_ponto(
                conn, origem_ponto, destino_ponto,
                sobrescrever=sobrescrever_ponto)
        except Exception as erro:
            st.error(f"Não foi possível mover o ponto: {erro}")
        else:
            texto = (f"Movidos {resultado['registros']} dia(s) e "
                     f"{resultado['uploads']} envio(s) de {origem_ponto} "
                     f"para {destino_ponto}. Backup: {caminho_backup}")
            if resultado["ignorados"]:
                texto += (f" {len(resultado['ignorados'])} data(s) repetida(s) "
                          "ficaram com o conteúdo do destino.")
            st.session_state["mover_ponto_flash"] = texto
            st.rerun()

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
