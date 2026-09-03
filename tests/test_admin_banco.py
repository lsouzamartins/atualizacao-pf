"""Testes das funções de administração: redefinir_senha e remover_usuario."""
import banco


def _conn(tmp_path):
    conn = banco.conectar(str(tmp_path / "pf.db"))
    banco.inicializar_banco(conn)
    return conn


def test_redefinir_senha_autentica_com_a_nova(tmp_path):
    conn = _conn(tmp_path)
    banco.criar_usuario(conn, "colega", "Colega", "senhaAntiga1")
    # bloqueia o usuário antes, para provar que a redefinição zera falhas/bloqueio
    agora = "2026-09-01T10:00:00"
    for _ in range(5):
        banco.registrar_falha(conn, "colega", agora=agora)
    res = banco.redefinir_senha(conn, "colega", "novaSenha99")
    assert res == {"ok": True}
    assert banco.autenticar(conn, "colega", "senhaAntiga1") is None
    usuario = banco.autenticar(conn, "colega", "novaSenha99")
    assert usuario is not None and usuario["login"] == "colega"
    assert usuario["falhas_seguidas"] == 0 and usuario["bloqueado_ate"] is None
    conn.close()


def test_redefinir_senha_curta_rejeitada(tmp_path):
    conn = _conn(tmp_path)
    banco.criar_usuario(conn, "colega", "Colega", "senhaAntiga1")
    res = banco.redefinir_senha(conn, "colega", "curta")
    assert res["ok"] is False and "8 caracteres" in res["erro"]
    conn.close()


def test_redefinir_usuario_inexistente(tmp_path):
    conn = _conn(tmp_path)
    res = banco.redefinir_senha(conn, "fantasma", "senhaNova123")
    assert res["ok"] is False and "Usuário não encontrado" in res["erro"]
    conn.close()


def test_remover_usuario_comum(tmp_path):
    conn = _conn(tmp_path)
    banco.criar_usuario(conn, "admin", "Admin", "senhaAdmin1", admin=True)
    uid = banco.criar_usuario(conn, "comum", "Comum", "senhaComum1")
    assert [r["login"] for r in banco.listar_usuarios(conn)] == ["admin", "comum"]
    res = banco.remover_usuario(conn, "comum", "admin")
    assert res == {"ok": True}
    assert conn.execute("SELECT id FROM usuarios WHERE id=?", (uid,)).fetchone() is None
    conn.close()


def test_remover_o_proprio_admin_negado(tmp_path):
    conn = _conn(tmp_path)
    banco.criar_usuario(conn, "admin", "Admin", "senhaAdmin1", admin=True)
    res = banco.remover_usuario(conn, "admin", "admin")
    assert res["ok"] is False and "próprio usuário" in res["erro"]
    assert banco.autenticar(conn, "admin", "senhaAdmin1") is not None
    conn.close()


def test_remover_ultimo_admin_negado(tmp_path):
    conn = _conn(tmp_path)
    banco.criar_usuario(conn, "admin", "Admin", "senhaAdmin1", admin=True)
    banco.criar_usuario(conn, "comum", "Comum", "senhaComum1")
    # o operador "comum" não é o alvo; o alvo é o único admin
    res = banco.remover_usuario(conn, "admin", "comum")
    assert res["ok"] is False and "último administrador" in res["erro"]
    conn.close()


def test_remover_usuario_inexistente(tmp_path):
    conn = _conn(tmp_path)
    banco.criar_usuario(conn, "admin", "Admin", "senhaAdmin1", admin=True)
    res = banco.remover_usuario(conn, "fantasma", "admin")
    assert res["ok"] is False and "Usuário não encontrado" in res["erro"]
    conn.close()
