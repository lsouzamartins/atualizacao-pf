"""Testes das tabelas e funções de ponto no banco."""
import sqlite3
from datetime import date

import banco


def _conn(tmp_path):
    conn = banco.conectar(str(tmp_path / "pf.db"))
    banco.inicializar_banco(conn)
    return conn


def _registro(dia, entrada="08:00", saida="18:00", tipo="trabalho",
              observacao=None):
    return {"data": dia, "entrada": entrada, "saida": saida,
            "tipo": tipo, "observacao": observacao}


def test_cria_tabelas_de_ponto(tmp_path):
    conn = _conn(tmp_path)
    tabelas = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"ponto_uploads", "ponto_registros"} <= tabelas
    conn.close()


def test_migracao_acesso_ponto_em_banco_antigo(tmp_path):
    db = str(tmp_path / "antigo.db")
    antigo = sqlite3.connect(db)
    antigo.execute("""CREATE TABLE usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login TEXT UNIQUE NOT NULL,
        nome TEXT NOT NULL,
        senha_hash TEXT NOT NULL,
        admin INTEGER NOT NULL DEFAULT 0,
        falhas_seguidas INTEGER NOT NULL DEFAULT 0,
        bloqueado_ate TEXT,
        criado_em TEXT NOT NULL)""")
    antigo.commit()
    antigo.close()

    conn = banco.conectar(db)
    banco.inicializar_banco(conn)
    banco.inicializar_banco(conn)
    colunas = [r["name"] for r in conn.execute("PRAGMA table_info(usuarios)")]
    assert "acesso_ponto" in colunas
    conn.close()


def test_definir_acesso_ponto_e_listar(tmp_path):
    conn = _conn(tmp_path)
    banco.criar_usuario(conn, "leo", "Leo", "senha12345")
    assert [r["acesso_ponto"] for r in banco.listar_usuarios(conn)
            if r["login"] == "leo"] == [0]
    banco.definir_acesso_ponto(conn, "leo", True)
    assert [r["acesso_ponto"] for r in banco.listar_usuarios(conn)
            if r["login"] == "leo"] == [1]
    banco.definir_acesso_ponto(conn, "leo", False)
    assert [r["acesso_ponto"] for r in banco.listar_usuarios(conn)
            if r["login"] == "leo"] == [0]
    conn.close()


def test_importacao_grava_upload_e_registros(tmp_path):
    conn = _conn(tmp_path)
    registros = [
        _registro(date(2026, 11, 3)),
        _registro(date(2026, 11, 4), "08:00", None, "trabalho", "x"),
    ]
    upload_id = banco.salvar_importacao_ponto(
        conn, "leo", "ponto.xlsx", registros,
        date(2026, 11, 3), date(2026, 11, 4), ["aviso"],
        agora="2026-11-06T10:00:00")
    assert upload_id
    upload = banco.ultimo_upload_ponto(conn)
    assert upload["nome_arquivo"] == "ponto.xlsx"
    assert upload["linhas"] == 2
    assert upload["periodo_de"] == "2026-11-03"
    registros_banco = banco.registros_ponto(conn)
    assert [r["data"] for r in registros_banco] == \
        [date(2026, 11, 3), date(2026, 11, 4)]
    conn.close()


def test_reimportacao_nao_duplica_e_nao_toca_fora_do_arquivo(tmp_path):
    conn = _conn(tmp_path)
    banco.salvar_importacao_ponto(
        conn, "leo", "a.xlsx",
        [_registro(date(2026, 11, 3), "08:00", "18:00"),
         _registro(date(2026, 11, 4), "08:00", "18:00")],
        date(2026, 11, 3), date(2026, 11, 4), [])
    banco.salvar_importacao_ponto(
        conn, "leo", "b.xlsx", [_registro(date(2026, 11, 3), "09:00", "19:00")],
        date(2026, 11, 3), date(2026, 11, 3), [])
    registros = {r["data"]: r for r in banco.registros_ponto(conn)}
    assert len(registros) == 2
    assert registros[date(2026, 11, 3)]["entrada"] == "09:00"
    assert registros[date(2026, 11, 4)]["entrada"] == "08:00"
    conn.close()


def test_importacao_preserva_manual_por_padrao(tmp_path):
    conn = _conn(tmp_path)
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "09:00", "18:00",
                                 "trabalho", "manual", "leo")
    banco.salvar_importacao_ponto(
        conn, "leo", "ponto.xlsx",
        [_registro(date(2026, 11, 3)), _registro(date(2026, 11, 4))],
        date(2026, 11, 3), date(2026, 11, 4), [])
    registros = {r["data"]: r for r in banco.registros_ponto(conn)}
    assert registros[date(2026, 11, 3)]["entrada"] == "09:00"
    assert registros[date(2026, 11, 3)]["origem"] == "manual"
    assert registros[date(2026, 11, 4)]["origem"] == "upload"
    conn.close()


def test_importacao_sobrescreve_manual_quando_pedido(tmp_path):
    conn = _conn(tmp_path)
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "09:00", "18:00",
                                 "trabalho", None, "leo")
    banco.salvar_importacao_ponto(
        conn, "leo", "ponto.xlsx", [_registro(date(2026, 11, 3))],
        date(2026, 11, 3), date(2026, 11, 3), [],
        sobrescrever_manuais=True)
    registro = banco.registros_ponto(conn)[0]
    assert registro["entrada"] == "08:00"
    assert registro["origem"] == "upload"
    conn.close()


def test_salvar_registro_manual_cria_e_atualiza(tmp_path):
    conn = _conn(tmp_path)
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "08:00", "17:00",
                                 "trabalho", None, "leo",
                                 agora="2026-11-06T10:00:00")
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "09:00", "19:00",
                                 "trabalho", "obs", "ana",
                                 agora="2026-11-06T11:00:00", dono="leo")
    registro = banco.registros_ponto(conn)[0]
    assert registro["entrada"] == "09:00"
    assert registro["origem"] == "manual"
    assert registro["atualizado_por"] == "ana"
    assert registro["atualizado_em"] == "2026-11-06T11:00:00"
    conn.close()


def test_excluir_registro_ponto(tmp_path):
    conn = _conn(tmp_path)
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "08:00", "17:00",
                                 "trabalho", None, "leo")
    assert banco.excluir_registro_ponto(conn, "leo", date(2026, 11, 3)) == 1
    assert banco.registros_ponto(conn) == []
    conn.close()


def test_pontos_de_usuarios_diferentes_nao_se_misturam(tmp_path):
    """09/11/2026: cada usuário alimenta o próprio ponto; o mesmo dia pode
    existir para pessoas diferentes sem uma sobrescrever a outra."""
    conn = _conn(tmp_path)
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "08:00", "17:00",
                                 "trabalho", None, "leo")
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "10:00", "19:00",
                                 "trabalho", None, "ana")
    assert [r["entrada"] for r in banco.registros_ponto(conn, "leo")] == ["08:00"]
    assert [r["entrada"] for r in banco.registros_ponto(conn, "ana")] == ["10:00"]
    assert len(banco.registros_ponto(conn)) == 2
    conn.close()


def test_importacao_de_um_dono_nao_toca_no_ponto_do_outro(tmp_path):
    conn = _conn(tmp_path)
    banco.salvar_importacao_ponto(
        conn, "leo", "leo.xlsx",
        [_registro(date(2026, 11, 3), "08:00", "18:00")],
        date(2026, 11, 3), date(2026, 11, 3), [])
    banco.salvar_importacao_ponto(
        conn, "ana", "ana.xlsx",
        [_registro(date(2026, 11, 3), "10:00", "19:00")],
        date(2026, 11, 3), date(2026, 11, 3), [])
    assert banco.registros_ponto(conn, "leo")[0]["entrada"] == "08:00"
    assert banco.registros_ponto(conn, "ana")[0]["entrada"] == "10:00"
    assert [u["nome_arquivo"] for u in banco.listar_uploads_ponto(conn, "leo")] \
        == ["leo.xlsx"]
    assert [u["nome_arquivo"] for u in banco.listar_uploads_ponto(conn, "ana")] \
        == ["ana.xlsx"]
    conn.close()


def test_excluir_apaga_apenas_o_dia_do_dono(tmp_path):
    conn = _conn(tmp_path)
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "08:00", "17:00",
                                 "trabalho", None, "leo")
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "10:00", "19:00",
                                 "trabalho", None, "ana")
    assert banco.excluir_registro_ponto(conn, "leo", date(2026, 11, 3)) == 1
    assert banco.registros_ponto(conn, "leo") == []
    assert len(banco.registros_ponto(conn, "ana")) == 1
    conn.close()


def test_historico_de_uploads(tmp_path):
    conn = _conn(tmp_path)
    banco.salvar_importacao_ponto(
        conn, "leo", "a.xlsx", [_registro(date(2026, 11, 3))],
        date(2026, 11, 3), date(2026, 11, 3), [])
    banco.salvar_importacao_ponto(
        conn, "ana", "b.xlsx", [_registro(date(2026, 11, 4))],
        date(2026, 11, 4), date(2026, 11, 4), [])
    uploads = banco.listar_uploads_ponto(conn)
    assert [u["nome_arquivo"] for u in uploads] == ["b.xlsx", "a.xlsx"]
    conn.close()


def test_migracao_separa_ponto_antigo_por_dono(tmp_path):
    """Banco anterior a 09/11/2026 tem UNIQUE(data) e nenhum dono: a migração
    precisa atribuir cada dia ao usuário do upload que o gravou (ou ao último
    editor, ou ao primeiro admin) e recriar a tabela com UNIQUE(dono, data)."""
    db = str(tmp_path / "antigo.db")
    antigo = sqlite3.connect(db)
    antigo.executescript("""
        CREATE TABLE usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            senha_hash TEXT NOT NULL,
            admin INTEGER NOT NULL DEFAULT 0,
            falhas_seguidas INTEGER NOT NULL DEFAULT 0,
            bloqueado_ate TEXT,
            criado_em TEXT NOT NULL);
        CREATE TABLE ponto_uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            nome_arquivo TEXT NOT NULL,
            enviado_em TEXT NOT NULL,
            periodo_de TEXT NOT NULL,
            periodo_ate TEXT NOT NULL,
            linhas INTEGER NOT NULL,
            avisos TEXT);
        CREATE TABLE ponto_registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER REFERENCES ponto_uploads(id),
            data TEXT NOT NULL,
            entrada TEXT,
            saida TEXT,
            tipo TEXT NOT NULL DEFAULT 'trabalho',
            observacao TEXT,
            origem TEXT NOT NULL DEFAULT 'upload',
            atualizado_em TEXT,
            atualizado_por TEXT,
            UNIQUE(data));
    """)
    antigo.execute("INSERT INTO usuarios (login, nome, senha_hash, admin, "
                   "criado_em) VALUES ('leo', 'Leo', 'x', 0, '2026-11-01')")
    antigo.execute("INSERT INTO usuarios (login, nome, senha_hash, admin, "
                   "criado_em) VALUES ('ana', 'Ana', 'x', 1, '2026-11-01')")
    antigo.execute("INSERT INTO ponto_uploads (usuario, nome_arquivo, "
                   "enviado_em, periodo_de, periodo_ate, linhas) VALUES "
                   "('leo', 'leo.xlsx', '2026-11-01T10:00:00', '2026-11-03', "
                   "'2026-11-05', 2)")
    antigo.execute("INSERT INTO ponto_registros (upload_id, data, entrada, "
                   "saida) VALUES (1, '2026-11-03', '08:00', '18:00')")
    antigo.execute("INSERT INTO ponto_registros (upload_id, data, entrada, "
                   "saida, origem, atualizado_por) VALUES (NULL, '2026-11-04', "
                   "'09:00', '19:00', 'manual', 'ana')")
    antigo.execute("INSERT INTO ponto_registros (data, entrada, saida) "
                   "VALUES ('2026-11-05', '08:00', '18:00')")
    antigo.commit()
    antigo.close()

    conn = banco.conectar(db)
    banco.inicializar_banco(conn)
    banco.inicializar_banco(conn)  # idempotente
    leo = banco.registros_ponto(conn, "leo")
    ana = banco.registros_ponto(conn, "ana")
    assert [r["data"] for r in leo] == [date(2026, 11, 3)]
    assert [r["data"] for r in ana] == [date(2026, 11, 4), date(2026, 11, 5)]
    assert banco.listar_uploads_ponto(conn, "leo")[0]["nome_arquivo"] == "leo.xlsx"

    # Depois da migração, o mesmo dia coexiste para donos diferentes.
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "10:00", "19:00",
                                 "trabalho", None, "ana")
    assert len(banco.registros_ponto(conn, "leo")) == 1
    assert len(banco.registros_ponto(conn, "ana")) == 3
    conn.close()


def test_mover_ponto_move_registros_e_uploads(tmp_path):
    """10/11/2026: o ponto importado com o login errado pode ser reatribuído
    por inteiro (dias + envios) para o dono correto."""
    conn = _conn(tmp_path)
    banco.salvar_importacao_ponto(
        conn, "leo", "lameirao.xlsx",
        [_registro(date(2026, 11, 3)), _registro(date(2026, 11, 4))],
        date(2026, 11, 3), date(2026, 11, 4), [])
    banco.salvar_registro_manual(conn, date(2026, 11, 5), "08:00", "17:00",
                                 "trabalho", None, "leo")
    resultado = banco.mover_ponto(conn, "leo", "lameirao")
    assert resultado["registros"] == 3
    assert resultado["uploads"] == 1
    assert resultado["ignorados"] == []
    assert banco.registros_ponto(conn, "leo") == []
    assert [r["data"] for r in banco.registros_ponto(conn, "lameirao")] == \
        [date(2026, 11, 3), date(2026, 11, 4), date(2026, 11, 5)]
    assert [u["nome_arquivo"] for u in
            banco.listar_uploads_ponto(conn, "lameirao")] == ["lameirao.xlsx"]
    conn.close()


def test_mover_ponto_destino_vence_e_origem_fica_vazia(tmp_path):
    """Por padrão o destino vence: o dia repetido é preservado no destino e
    removido da origem (a origem não fica com sobras); os demais dias vão
    para o destino."""
    conn = _conn(tmp_path)
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "08:00", "17:00",
                                 "trabalho", None, "leo")
    banco.salvar_registro_manual(conn, date(2026, 11, 4), "08:00", "17:00",
                                 "trabalho", None, "leo")
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "10:00", "19:00",
                                 "trabalho", None, "ana")
    resultado = banco.mover_ponto(conn, "leo", "ana")
    assert resultado["registros"] == 1
    assert resultado["ignorados"] == ["2026-11-03"]
    assert banco.registros_ponto(conn, "leo") == []  # origem esvaziada
    ana = {r["data"]: r for r in banco.registros_ponto(conn, "ana")}
    assert ana[date(2026, 11, 3)]["entrada"] == "10:00"  # destino preservado
    assert ana[date(2026, 11, 4)]["entrada"] == "08:00"  # veio da origem
    conn.close()


def test_mover_ponto_sobrescreve_quando_pedido(tmp_path):
    """Com sobrescrever=True o conteúdo da origem vence as datas repetidas."""
    conn = _conn(tmp_path)
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "08:00", "17:00",
                                 "trabalho", None, "leo")
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "10:00", "19:00",
                                 "trabalho", None, "ana")
    resultado = banco.mover_ponto(conn, "leo", "ana", sobrescrever=True)
    assert resultado["sobrescritos"] == 1
    assert resultado["ignorados"] == []
    assert banco.registros_ponto(conn, "leo") == []
    ana = banco.registros_ponto(conn, "ana")
    assert len(ana) == 1 and ana[0]["entrada"] == "08:00"
    conn.close()


def test_mover_ponto_nao_toca_em_terceiros(tmp_path):
    conn = _conn(tmp_path)
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "08:00", "17:00",
                                 "trabalho", None, "leo")
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "10:00", "19:00",
                                 "trabalho", None, "bia")
    banco.mover_ponto(conn, "leo", "ana")
    assert len(banco.registros_ponto(conn, "bia")) == 1
    assert len(banco.registros_ponto(conn, "ana")) == 1
    conn.close()


def test_mover_ponto_exige_origem_e_destino_diferentes(tmp_path):
    conn = _conn(tmp_path)
    try:
        banco.mover_ponto(conn, "leo", "leo")
    except ValueError:
        pass
    else:
        raise AssertionError("esperava ValueError")
    conn.close()


def test_salvar_periodo_manual_cria_dias_especiais(tmp_path):
    """10/11/2026: o mês de férias pode ser lançado de uma vez, sem horário."""
    conn = _conn(tmp_path)
    dias = [date(2026, 11, 2), date(2026, 11, 3), date(2026, 11, 4)]
    resultado = banco.salvar_periodo_manual(
        conn, dias, "ferias", "Férias de novembro", "leo")
    assert resultado == {"criados": 3, "substituidos": 0, "preservados": 0}
    registros = banco.registros_ponto(conn, "leo")
    assert [r["data"] for r in registros] == dias
    assert all(r["tipo"] == "ferias" for r in registros)
    assert all(r["entrada"] is None and r["saida"] is None
               for r in registros)
    assert all(r["origem"] == "manual" for r in registros)
    assert all(r["observacao"] == "Férias de novembro" for r in registros)
    conn.close()


def test_salvar_periodo_manual_preserva_registros_existentes(tmp_path):
    """Por padrão, dia que já tem registro fica como está."""
    conn = _conn(tmp_path)
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "08:00", "17:00",
                                 "trabalho", None, "leo")
    resultado = banco.salvar_periodo_manual(
        conn, [date(2026, 11, 2), date(2026, 11, 3)], "ferias", None, "leo")
    assert resultado == {"criados": 1, "substituidos": 0, "preservados": 1}
    registros = {r["data"]: r for r in banco.registros_ponto(conn, "leo")}
    assert registros[date(2026, 11, 3)]["tipo"] == "trabalho"
    assert registros[date(2026, 11, 3)]["entrada"] == "08:00"
    assert registros[date(2026, 11, 2)]["tipo"] == "ferias"
    conn.close()


def test_salvar_periodo_manual_substitui_quando_pedido(tmp_path):
    """Com substituir=True o período vence os dias que já têm registro."""
    conn = _conn(tmp_path)
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "08:00", "17:00",
                                 "trabalho", None, "leo")
    resultado = banco.salvar_periodo_manual(
        conn, [date(2026, 11, 2), date(2026, 11, 3)], "ferias", None,
        "leo", substituir=True)
    assert resultado == {"criados": 1, "substituidos": 1, "preservados": 0}
    registros = {r["data"]: r for r in banco.registros_ponto(conn, "leo")}
    assert registros[date(2026, 11, 3)]["tipo"] == "ferias"
    assert registros[date(2026, 11, 3)]["entrada"] is None
    assert registros[date(2026, 11, 2)]["tipo"] == "ferias"
    conn.close()


def test_salvar_periodo_manual_nao_toca_em_terceiros(tmp_path):
    conn = _conn(tmp_path)
    banco.salvar_registro_manual(conn, date(2026, 11, 3), "08:00", "17:00",
                                 "trabalho", None, "ana")
    banco.salvar_periodo_manual(
        conn, [date(2026, 11, 2), date(2026, 11, 3)], "ferias", None, "leo")
    assert banco.registros_ponto(conn, "ana")[0]["tipo"] == "trabalho"
    assert len(banco.registros_ponto(conn, "leo")) == 2
    conn.close()
