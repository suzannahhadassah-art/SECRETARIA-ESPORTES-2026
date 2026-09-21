"""Recuperação de acesso: redefine a senha da conta de administrador direto no banco.

Use quando ninguém mais conseguir entrar no sistema. Rode com Python a partir
desta mesma pasta:  python reset_senha.py
"""
import sqlite3
from werkzeug.security import generate_password_hash

import config

NOVA_SENHA = "esportes2026"

conn = sqlite3.connect(config.DB_PATH)
conn.row_factory = sqlite3.Row

admins = conn.execute("SELECT id, nome, email FROM usuarios WHERE cargo='admin'").fetchall()

if not admins:
    print("Nenhuma conta de administrador encontrada no banco.")
else:
    conn.execute(
        "UPDATE usuarios SET senha_hash=? WHERE cargo='admin'",
        (generate_password_hash(NOVA_SENHA),),
    )
    conn.commit()
    print("Senha redefinida para as seguintes contas de administrador:")
    for a in admins:
        print(f"  - {a['nome']} ({a['email']})")
    print(f"\nNova senha: {NOVA_SENHA}")
    print("Troque essa senha assim que entrar no sistema (Usuários > editar).")

conn.close()
