"""Testes do banco do Contas a Receber (dacm_glosas.db) — em tmp_path."""
from datetime import date

import pandas as pd
import pytest

import banco_glosas


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    c = banco_glosas.conectar(str(tmp_path / "teste.db"))
    banco_glosas.inicializar_banco(c)
    monkeypatch.setattr(banco_glosas, "PASTA_UPLOADS", str(tmp_path / "uploads"))
    yield c
    c.close()


def _parsed(guias):
    """Dict parseado fake no formato do parser_dacm."""
    return {
        "metadados": {"num_dacm": "14880859", "operadora": "Porto Seguro - Seguro Saude S.A.",
                      "registro_ans": "000582", "cnpj": "04540010000170",
                      "data_emissao": "2026-07-16"},
        "guias": guias,
        "avisos": [],
    }


def _guia(guia="25489130", glosa=0.24, itens=None):
    return {
        "lote": "272327", "protocolo": "20274355", "data_protocolo": "2026-06-12",
        "cod_situacao_protocolo": "6", "guia_prestador": guia, "guia_operadora": "12474769",
        "senha": "", "beneficiario": "JEFERSON PASSOS PEREIRA", "nome_social": "JEFERSON",
        "carteira": "2234973211568118", "data_inicio_fat": "", "data_fim_fat": "",
        "cod_situacao_guia": "6", "vl_informado": 50.52, "vl_processado": 50.52,
        "vl_liberado": 50.52 - glosa, "vl_glosa": glosa,
        "itens": itens if itens is not None else [
            {"data_realizacao": "2026-05-18", "tabela": "22", "cod_procedimento": "10101039",
             "descricao": "CONSULTA EM PRONTO SOCORRO", "grau_participacao": "08",
             "quantidade": 1, "vl_informado": 44.22, "vl_processado": 44.22,
             "vl_liberado": 44.22, "vl_glosa": 0, "cod_glosa": ""},
            {"data_realizacao": "2026-05-18", "tabela": "22", "cod_procedimento": "40302040",
             "descricao": "GLICOSE - PESQUISA E/OU DOSAGEM", "grau_participacao": "",
             "quantidade": 1, "vl_informado": 6.3, "vl_processado": 6.3,
             "vl_liberado": 6.06, "vl_glosa": glosa, "cod_glosa": "1714"},
        ],
    }


def test_inicializa_e_importa_guia_nova_com_status_inicial(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"conteudo")
    r = banco_glosas.importar_dacm(conn, _parsed([_guia()]), "Porto Saúde",
                                   "lsmartins", str(arquivo))
    assert r == {"novas": 1, "atualizadas": 0, "avisos_glosa_zerada": 0, "upload_id": 1}
    guias = banco_glosas.guias_filtradas(conn)
    assert len(guias) == 1
    assert guias[0]["status_recurso"] == "A iniciar recurso"
    assert guias[0]["data_inicio"] == "2026-05-18"
    # convênio criado com os dados do arquivo
    convenios = banco_glosas.listar_convenios(conn)
    assert [c["nome"] for c in convenios] == ["Porto Saúde"]
    assert convenios[0]["registro_ans"] == "000582"


def test_importa_guia_sem_glosa_como_livre(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia(glosa=0)]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    assert banco_glosas.guias_filtradas(conn)[0]["status_recurso"] == "Livre de Glosa"


def test_reenvio_atualiza_sem_duplicar_e_mantem_status(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia()]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    guia_id = banco_glosas.guias_filtradas(conn)[0]["guia_id"]
    banco_glosas.registrar_status(conn, guia_id, "Em análise", usuario="lsmartins")
    # reenvio com valor de glosa DIFERENTE (arquivo corrigido)
    guia2 = _guia(glosa=5.0)
    r = banco_glosas.importar_dacm(conn, _parsed([guia2]), "Porto Saúde",
                                   "lsmartins", str(arquivo))
    assert r["novas"] == 0 and r["atualizadas"] == 1
    assert len(banco_glosas.guias_filtradas(conn)) == 1  # sem duplicar
    guia = banco_glosas.guias_filtradas(conn)[0]
    assert guia["vl_glosa"] == 5.0
    assert guia["status_recurso"] == "Em análise"  # status manual preservado


def test_reenvio_com_glosa_zerada_gera_aviso_sem_mudar_status(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia(glosa=10.0)]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    r = banco_glosas.importar_dacm(conn, _parsed([_guia(glosa=0)]), "Porto Saúde",
                                   "lsmartins", str(arquivo))
    assert r["avisos_glosa_zerada"] == 1
    guia = banco_glosas.guias_filtradas(conn)[0]
    assert guia["aviso_glosa_zerada"] == 1
    assert guia["status_recurso"] == "A iniciar recurso"  # nada muda sozinho
    assert len(banco_glosas.avisos_glosa_zerada(conn)) == 1


def test_confirmar_glosa_recebida_um_clique(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia(glosa=0.24)]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    banco_glosas.importar_dacm(conn, _parsed([_guia(glosa=0)]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    guia_id = banco_glosas.guias_filtradas(conn)[0]["guia_id"]
    banco_glosas.confirmar_glosa_recebida(conn, guia_id, usuario="lsmartins")
    guia = banco_glosas.guias_filtradas(conn)[0]
    assert guia["status_recurso"] == "Glosa Recebida"
    assert guia["vl_recuperado"] == 0.24  # default = valor da glosa
    assert guia["aviso_glosa_zerada"] == 0
    hist = banco_glosas.historico_status(conn, guia_id)
    assert [h["status_para"] for h in hist] == ["A iniciar recurso", "Glosa Recebida"]


def test_registrar_status_rejeita_status_invalido(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia()]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    guia_id = banco_glosas.guias_filtradas(conn)[0]["guia_id"]
    with pytest.raises(ValueError, match="Status inválido"):
        banco_glosas.registrar_status(conn, guia_id, "Status que não existe")


def test_motivo_glosado_concatena_descricoes(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia(glosa=0.24)]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    guia_id = banco_glosas.guias_filtradas(conn)[0]["guia_id"]
    assert banco_glosas.motivo_glosado(conn, guia_id) == \
        "GLICOSE - PESQUISA E/OU DOSAGEM [1714]"


def test_resumo_kpis_e_taxas(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia(glosa=10.0)]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    guia_id = banco_glosas.guias_filtradas(conn)[0]["guia_id"]
    banco_glosas.registrar_status(conn, guia_id, "Glosa Recebida", vl_recuperado=10.0)
    kpis = banco_glosas.resumo_kpis(conn)
    assert kpis["glosado"] == 10.0
    assert kpis["recuperado"] == 10.0
    assert kpis["taxa_recuperacao"] == 100.0
    assert kpis["em_recurso"] == 0.0


def test_alertas_aging_so_para_convenios_com_prazo(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia()]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    # sem prazo cadastrado -> nenhum alerta
    assert banco_glosas.alertas_aging(conn, hoje=date(2026, 9, 6)) == []
    convenio_id = banco_glosas.listar_convenios(conn)[0]["id"]
    banco_glosas.definir_prazo_convenio(conn, convenio_id, 30)
    # protocolo de 12/06: 86 dias até 06/09 -> estourado
    alertas = banco_glosas.alertas_aging(conn, hoje=date(2026, 9, 6))
    assert len(alertas) == 1
    assert alertas[0]["dias"] == 86 and alertas[0]["prazo"] == 30
    # dentro do prazo -> sem alerta
    assert banco_glosas.alertas_aging(conn, hoje=date(2026, 7, 1)) == []


def test_diff_guias_editadas_so_devolve_o_que_mudou():
    antes = pd.DataFrame([
        {"guia_id": 1, "status": "A iniciar recurso", "vl_recuperado": 0.0, "observacao": ""},
        {"guia_id": 2, "status": "Livre de Glosa", "vl_recuperado": 0.0, "observacao": ""},
    ])
    depois = pd.DataFrame([
        {"guia_id": 1, "status": "Em análise", "vl_recuperado": 5.0, "observacao": "ok"},
        {"guia_id": 2, "status": "Livre de Glosa", "vl_recuperado": 0.0, "observacao": ""},
    ])
    alteradas = banco_glosas.diff_guias_editadas(antes, depois)
    assert alteradas == [{"guia_id": 1, "status": "Em análise", "vl_recuperado": 5.0,
                          "observacao": "ok"}]


def test_nome_de_arquivo_seguro_nunca_escapa_da_pasta(conn, tmp_path):
    arquivo = tmp_path / ".._etc_passwd.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia()]), "Porto Saúde",
                               "lsmartins", str(arquivo))
    upload = banco_glosas.listar_uploads(conn)[0]
    assert ".." not in upload["nome_arquivo"]
    import os
    salvo = os.path.join(banco_glosas.PASTA_UPLOADS, upload["nome_arquivo"])
    assert os.path.exists(salvo)


def test_reenvio_zerado_depois_da_confirmacao_nao_reavisa(conn, tmp_path):
    arquivo = tmp_path / "dacm.xls"; arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(conn, _parsed([_guia(glosa=10.0)]), "Porto Saúde", "lsmartins", str(arquivo))
    banco_glosas.importar_dacm(conn, _parsed([_guia(glosa=0)]), "Porto Saúde", "lsmartins", str(arquivo))
    guia_id = banco_glosas.guias_filtradas(conn)[0]["guia_id"]
    banco_glosas.confirmar_glosa_recebida(conn, guia_id, usuario="lsmartins")
    assert banco_glosas.guias_filtradas(conn)[0]["vl_glosa"] == 0
    r = banco_glosas.importar_dacm(conn, _parsed([_guia(glosa=0)]), "Porto Saúde", "lsmartins", str(arquivo))
    assert r["avisos_glosa_zerada"] == 0
    assert banco_glosas.guias_filtradas(conn)[0]["aviso_glosa_zerada"] == 0


def test_diff_guias_editadas_celulas_limpas_nao_quebram():
    """Célula limpa no data_editor chega como None/NaN — não pode quebrar o diff
    e sai como None para registrar_status manter o valor atual."""
    import pandas as pd
    antes = pd.DataFrame([
        {"guia_id": 1, "status": "Em análise", "vl_recuperado": 0.0,
         "observacao": ""}])
    depois = pd.DataFrame([
        {"guia_id": 1, "status": "Em análise", "vl_recuperado": None,
         "observacao": None}])
    assert banco_glosas.diff_guias_editadas(antes, depois) == []
    depois2 = pd.DataFrame([
        {"guia_id": 1, "status": "Glosa Recebida", "vl_recuperado": None,
         "observacao": None}])
    assert banco_glosas.diff_guias_editadas(antes, depois2) == [
        {"guia_id": 1, "status": "Glosa Recebida",
         "vl_recuperado": None, "observacao": None}]


# ==============================================================================
# CONSULTAS DO DASHBOARD (visual v1.0 — filtros por status/motivo e resumos)
# ==============================================================================
def _item(descricao, glosa, cod="99"):
    return {"data_realizacao": "2026-05-18", "tabela": "22", "cod_procedimento": "1",
            "descricao": descricao, "grau_participacao": "", "quantidade": 1,
            "vl_informado": 10.0, "vl_processado": 10.0, "vl_liberado": 10.0 - glosa,
            "vl_glosa": glosa, "cod_glosa": cod}


def _importar_duas(conn, tmp_path, glosa_a=1.0, glosa_b=1.0, itens_a=None, itens_b=None):
    """Importa duas guias em convênios A e B e devolve o caminho do arquivo."""
    arquivo = tmp_path / "dacm.xls"
    arquivo.write_bytes(b"x")
    banco_glosas.importar_dacm(
        conn, _parsed([_guia("1", glosa=glosa_a, itens=itens_a)]), "Conv A",
        "lsmartins", str(arquivo))
    banco_glosas.importar_dacm(
        conn, _parsed([_guia("2", glosa=glosa_b, itens=itens_b)]), "Conv B",
        "lsmartins", str(arquivo))
    return arquivo


def test_guias_filtradas_por_motivo(conn, tmp_path):
    _importar_duas(conn, tmp_path,
                   itens_a=[_item("MATERIAL X", 1.0)],
                   itens_b=[_item("MATERIAL Y", 1.0)])
    so_x = banco_glosas.guias_filtradas(conn, motivo="MATERIAL X [99]")
    assert [g["guia_prestador"] for g in so_x] == ["1"]


def test_listar_motivos_distintos_em_ordem(conn, tmp_path):
    _importar_duas(conn, tmp_path,
                   itens_a=[_item("BETA", 1.0)],
                   itens_b=[_item("ALFA", 1.0)])
    assert banco_glosas.listar_motivos(conn) == ["ALFA [99]", "BETA [99]"]


def test_resumo_por_status_soma_glosa_por_status_na_ordem_canonica(conn, tmp_path):
    _importar_duas(conn, tmp_path, glosa_a=10.0, glosa_b=0.0)
    guia_b = [g for g in banco_glosas.guias_filtradas(conn)
              if g["guia_prestador"] == "2"][0]
    banco_glosas.registrar_status(conn, guia_b["guia_id"], "Recurso Negado")
    df = banco_glosas.resumo_por_status(conn)
    assert df["status"].tolist() == ["A iniciar recurso", "Recurso Negado"]
    assert dict(zip(df["status"], df["total"])) == {
        "A iniciar recurso": 10.0, "Recurso Negado": 0.0}


def test_resumo_por_convenio_status_linhas_por_convenio_e_status(conn, tmp_path):
    _importar_duas(conn, tmp_path, glosa_a=10.0, glosa_b=5.0)
    df = banco_glosas.resumo_por_convenio_status(conn)
    linhas = {(r["convenio"], r["status"]): r["total"] for r in df.to_dict("records")}
    assert linhas[("Conv A", "A iniciar recurso")] == 10.0
    assert linhas[("Conv B", "A iniciar recurso")] == 5.0


def test_resumo_por_convenio_status_dataframe_vazio_sem_guias(conn):
    """Sem guias, devolve DataFrame vazio (não quebra no groupby)."""
    assert banco_glosas.resumo_por_convenio_status(conn).empty


def test_resumo_por_status_dataframe_vazio_sem_guias(conn):
    """Sem guias, devolve DataFrame vazio (não quebra no groupby)."""
    assert banco_glosas.resumo_por_status(conn).empty


def test_resumo_kpis_filtra_por_status_e_motivo(conn, tmp_path):
    _importar_duas(conn, tmp_path, glosa_a=10.0, glosa_b=4.0,
                   itens_a=[_item("ALFA", 10.0)], itens_b=[_item("BETA", 4.0)])
    assert banco_glosas.resumo_kpis(conn, motivo="ALFA [99]")["glosado"] == 10.0
    assert banco_glosas.resumo_kpis(conn, status="A iniciar recurso")["glosado"] == 14.0
    guia_b = [g for g in banco_glosas.guias_filtradas(conn)
              if g["guia_prestador"] == "2"][0]
    banco_glosas.registrar_status(conn, guia_b["guia_id"], "Recurso Negado")
    assert banco_glosas.resumo_kpis(conn, status="A iniciar recurso")["glosado"] == 10.0


def test_evolucao_mensal_filtra_por_status(conn, tmp_path):
    _importar_duas(conn, tmp_path, glosa_a=10.0, glosa_b=5.0)
    guia_b = [g for g in banco_glosas.guias_filtradas(conn)
              if g["guia_prestador"] == "2"][0]
    banco_glosas.registrar_status(conn, guia_b["guia_id"], "Recurso Negado")
    df = banco_glosas.evolucao_mensal(conn, status="A iniciar recurso")
    assert float(df["glosado"].sum()) == 10.0
    assert float(df["recuperado"].sum()) == 0.0
