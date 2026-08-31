"""Gera as variáveis seguras de acesso para uma instância individual."""

import argparse
import base64
from getpass import getpass
import hashlib
import secrets


ITERATIONS = 600_000


def encode_password(password, pepper):
    salt = secrets.token_bytes(24)
    digest = hashlib.pbkdf2_hmac(
        "sha256", (password + pepper).encode(), salt, ITERATIONS
    )
    salt_text = base64.urlsafe_b64encode(salt).decode()
    digest_text = base64.urlsafe_b64encode(digest).decode()
    return f"pbkdf2_sha256${ITERATIONS}${salt_text}${digest_text}"


def main():
    parser = argparse.ArgumentParser(description="Cria o login do piloto da agenda.")
    parser.add_argument("--username", required=True, help="Usuário usado na tela de login")
    parser.add_argument("--name", required=True, help="Nome exibido na agenda")
    parser.add_argument("--role", choices=["seller", "manager"], default="seller")
    args = parser.parse_args()

    password = getpass("Senha: ")
    confirmation = getpass("Repita a senha: ")
    if password != confirmation:
        raise SystemExit("As senhas não coincidem.")
    if len(password) < 12:
        raise SystemExit("Use uma senha com pelo menos 12 caracteres.")

    pepper = secrets.token_urlsafe(32)
    encoded_hash = encode_password(password, pepper)
    print("\nCopie estas variáveis para o serviço publicado:\n")
    print("AGENDA_AUTH_REQUIRED=1")
    print(f"AGENDA_USERNAME={args.username.strip()}")
    print(f"AGENDA_PASSWORD_HASH={encoded_hash}")
    print(f"AGENDA_AUTH_PEPPER={pepper}")
    print(f"AGENDA_USER_NAME={args.name.strip()}")
    print(f"AGENDA_ROLE={args.role}")
    print("AGENDA_SEED_DEMO=0")


if __name__ == "__main__":
    main()
