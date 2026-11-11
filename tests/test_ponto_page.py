"""Testes da página Ponto — fonte e fumaça com AppTest."""
from datetime import date, time
from pathlib import Path

import banco
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
FONTE = (RAIZ / "app_pages" / "ponto.py").read_text(encoding="utf-8")


def _escolher_data(at, chave, dia, mes, ano):
    """Preenche os três seletores de data em português."""
    at.selectbox(key=f"{chave}_dia").set_value(dia)
    at.selectbox(key=f"{chave}_mes").set_value(mes)
    at.selectbox(key=f"{chave}_ano").set_value(ano)
    at.run()


def _app(tmp_path, monkeypatch, usuario=None, registros=(), usuarios=()):
    caminho = str(tmp_path / "pf.db")
    monkeypatch.setattr(banco, "CAMINHO_PADRAO", caminho)
    conn = banco.conectar(caminho)
    banco.inicializar_banco(conn)
    for dados in usuarios:
        banco.criar_usuario(conn, dados["login"],
                            dados.get("nome", dados["login"]),
                            "senha12345", admin=dados.get("admin", False))
        if dados.get("acesso_ponto"):
            banco.definir_acesso_ponto(conn, dados["login"], True)
    for registro in registros:
        banco.salvar_registro_manual(
            conn, registro["data"], registro.get("entrada"),
            registro.get("saida"), registro.get("tipo", "trabalho"),
            registro.get("observacao"), "leo",
            dono=registro.get("dono", "leo"))
    conn.close()
    at = AppTest.from_file(str(RAIZ / "app_pages" / "ponto.py"),
                           default_timeout=30)
    at.session_state["usuario"] = usuario or {
        "login": "leo", "admin": True, "acesso_ponto": True}
    return at


def test_pagina_exige_permissao(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch,
              usuario={"login": "leo", "admin": False, "acesso_ponto": False})
    at.run()
    assert not at.exception
    assert any("Acesso restrito ao Controle de Ponto" in e.value
               for e in at.error)


def test_pagina_sem_dados_mostra_estado_vazio(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    at.run()
    assert not at.exception
    assert any("Nenhum ponto registrado" in i.value for i in at.info)


def test_pagina_com_dados_mostra_kpis(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch, registros=[
        {"data": date(2026, 11, 3), "entrada": "08:00", "saida": "18:00"},
    ])
    at.run()
    assert not at.exception
    texto = " ".join(m.value for m in at.markdown)
    texto += " ".join(c.value for c in at.caption)
    assert "Saldo acumulado" in texto
    assert "Horas no período" in texto


def test_fonte_tem_botoes_compactos():
    """06/11, a pedido: os botões da página Ponto usam caixa menor."""
    assert "BOTOES_CSS" in FONTE
    assert "min-height: 2.1rem" in FONTE
    assert "st.markdown(BOTOES_CSS" in FONTE


def test_fonte_tem_formulario_manual():
    assert "Lançar/editar ponto" in FONTE
    assert "Excluir dia" in FONTE
    assert "salvar_registro_manual" in FONTE
    assert "excluir_registro_ponto" in FONTE


def test_trocar_data_reseta_confirmacao_de_exclusao(tmp_path, monkeypatch):
    """A confirmação de exclusão vale para a data em que foi marcada: marcar
    "Confirmo excluir" em 03/11 e trocar para 04/11 não pode deixar o
    "Excluir dia" habilitado para 04/11 sem nova confirmação."""
    at = _app(tmp_path, monkeypatch, registros=[
        {"data": date(2026, 11, 3), "entrada": "08:00", "saida": "18:00"},
        {"data": date(2026, 11, 4), "entrada": "08:00", "saida": "18:00"},
    ])
    at.run()
    assert not at.exception
    _escolher_data(at, "ponto_form_data", 3, "Novembro", 2026)
    at.checkbox(key="ponto_excluir_confirmar").check()
    at.run()
    assert at.checkbox(key="ponto_excluir_confirmar").value is True
    _escolher_data(at, "ponto_form_data", 4, "Novembro", 2026)
    assert not at.exception
    assert at.checkbox(key="ponto_excluir_confirmar").value is False


def test_salvar_dia_especial_zera_horarios_do_formulario(tmp_path, monkeypatch):
    """Salvar Férias/Feriado/Atestado grava o dia sem horário no banco; o
    rerun precisa recarregar o formulário (entrada/saída vazias) em vez de
    manter os horários antigos nos time_inputs desabilitados."""
    at = _app(tmp_path, monkeypatch, registros=[
        {"data": date(2026, 11, 3), "entrada": "08:00", "saida": "18:00"},
    ])
    at.run()
    assert not at.exception
    _escolher_data(at, "ponto_form_data", 3, "Novembro", 2026)
    # O sync carregou os horários do banco para os time_inputs.
    assert at.time_input(key="ponto_form_entrada").value == time(8, 0)
    at.selectbox(key="ponto_form_tipo").select("Férias")
    at.run()
    salvar = next(b for b in at.button if b.label == "Salvar")
    salvar.click()
    at.run()
    assert not at.exception
    assert any("salvo" in s.value for s in at.success)
    assert at.selectbox(key="ponto_form_tipo").value == "Férias"
    assert at.time_input(key="ponto_form_entrada").value is None
    assert at.time_input(key="ponto_form_saida").value is None


def test_pagina_com_dados_mostra_calendario(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch, registros=[
        {"data": date(2026, 11, 3), "entrada": "08:00", "saida": "18:00"},
    ])
    at.run()
    assert not at.exception
    assert any("ponto-grade" in m.value for m in at.markdown)


def test_calendario_escapa_observacao(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch, registros=[
        {"data": date(2026, 11, 3), "entrada": "08:00", "saida": "18:00",
         "observacao": '<script>alert("x")</script>'},
    ])
    at.run()
    assert not at.exception
    html = " ".join(m.value for m in at.markdown if "ponto-grade" in m.value)
    assert "ponto-grade" in html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_fonte_tem_graficos_e_calendario():
    assert "Evolução do saldo acumulado" in FONTE
    assert "Saldo por mês" in FONTE
    assert "_calendario_html" in FONTE


def test_pagina_sem_dados_abre_importacao(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    at.run()
    assert not at.exception
    assert at.file_uploader


def test_fonte_tem_importacao():
    assert "Importar nova planilha" in FONTE
    assert "Sobrescrever também os dias editados manualmente" in FONTE
    assert "ponto_core.ler_planilha" in FONTE
    assert "salvar_importacao_ponto" in FONTE


def test_usuario_comum_ve_so_o_proprio_ponto_sem_seletor(tmp_path, monkeypatch):
    """09/11/2026: cada usuário alimenta e vê o próprio ponto; o seletor de
    pessoa é exclusivo do admin."""
    at = _app(tmp_path, monkeypatch,
              usuario={"login": "ana", "admin": False, "acesso_ponto": True},
              registros=[
                  {"data": date(2026, 11, 3), "entrada": "08:00",
                   "saida": "18:00", "dono": "leo"},
                  {"data": date(2026, 11, 3), "entrada": "10:00",
                   "saida": "19:00", "dono": "ana"},
              ])
    at.run()
    assert not at.exception
    assert not [s for s in at.selectbox if s.key == "ponto_pessoa"]
    assert at.dataframe[0].value["Entrada"].tolist() == ["10:00"]


def test_admin_escolhe_pessoa_e_ve_o_ponto_dela(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch,
              usuario={"login": "leo", "admin": True, "acesso_ponto": True},
              usuarios=[{"login": "leo", "nome": "Leonardo", "admin": True},
                        {"login": "ana", "nome": "Ana", "acesso_ponto": True}],
              registros=[
                  {"data": date(2026, 11, 3), "entrada": "08:00",
                   "saida": "18:00", "dono": "leo"},
                  {"data": date(2026, 11, 3), "entrada": "10:00",
                   "saida": "19:00", "dono": "ana"},
              ])
    at.run()
    assert not at.exception
    seletor = at.selectbox(key="ponto_pessoa")
    assert seletor.value == "leo"
    assert at.dataframe[0].value["Entrada"].tolist() == ["08:00"]
    seletor.set_value("ana")
    at.run()
    assert not at.exception
    assert at.dataframe[0].value["Entrada"].tolist() == ["10:00"]


def test_admin_salva_dia_no_ponto_da_pessoa_escolhida(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch,
              usuario={"login": "leo", "admin": True, "acesso_ponto": True},
              usuarios=[{"login": "leo", "nome": "Leonardo", "admin": True},
                        {"login": "ana", "nome": "Ana", "acesso_ponto": True}])
    at.run()
    at.selectbox(key="ponto_pessoa").set_value("ana")
    at.run()
    _escolher_data(at, "ponto_form_data", 3, "Novembro", 2026)
    at.time_input(key="ponto_form_entrada").set_value(time(8, 0))
    at.time_input(key="ponto_form_saida").set_value(time(17, 0))
    at.run()
    next(b for b in at.button if b.label == "Salvar").click()
    at.run()
    assert not at.exception
    conn = banco.conectar(str(tmp_path / "pf.db"))
    try:
        assert [r["data"] for r in banco.registros_ponto(conn, "ana")] == \
            [date(2026, 11, 3)]
        assert banco.registros_ponto(conn, "leo") == []
    finally:
        conn.close()


def test_fonte_importa_e_edita_no_dono_exibido():
    assert "banco.registros_ponto(conn, dono)" in FONTE
    assert "banco.listar_uploads_ponto(conn, dono, limite=20)" in FONTE
    assert "sobrescrever_manuais=sobrescrever, dono=dono" in FONTE
    assert "banco.excluir_registro_ponto(conn, dono, dia)" in FONTE


def test_fonte_tem_seletores_de_data_em_portugues():
    """10/11/2026 (a pedido): o calendário do st.date_input é fixo em inglês;
    a página passou a usar Dia/Mês/Ano com os meses em português."""
    assert "MESES_NOMES" in FONTE
    for mes in ("Janeiro", "Fevereiro", "Março", "Dezembro"):
        assert mes in FONTE
    assert "st.date_input(" not in FONTE


def test_lancar_periodo_marca_dias_uteis_de_ferias(tmp_path, monkeypatch):
    """10/11/2026: o mês de férias é lançado de uma vez, só nos dias úteis."""
    at = _app(tmp_path, monkeypatch)
    at.run()
    assert not at.exception
    _escolher_data(at, "ponto_periodo_de", 1, "Novembro", 2026)
    _escolher_data(at, "ponto_periodo_ate", 30, "Novembro", 2026)
    next(b for b in at.button if b.label == "Lançar período").click()
    at.run()
    assert not at.exception
    conn = banco.conectar(str(tmp_path / "pf.db"))
    try:
        registros = banco.registros_ponto(conn, "leo")
    finally:
        conn.close()
    assert len(registros) == 21  # dias úteis de novembro/2026
    assert all(r["tipo"] == "ferias" for r in registros)
    assert all(r["data"].weekday() < 5 for r in registros)
