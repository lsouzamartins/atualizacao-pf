"""Cria o banco e o usuário admin inicial (rodar UMA vez no VPS, via SSH)."""
import getpass
import os
import sys

# Garante que o diretório do repo está no path (o script vive em scripts/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import banco

conn = banco.conectar()
banco.inicializar_banco(conn)
login = input("Login do admin: ").strip()
nome = input("Nome: ").strip()
senha = getpass.getpass("Senha (mín. 8): ")
banco.criar_usuario(conn, login, nome, senha, admin=True)
print(f"Admin '{login}' criado.")
conn.close()
