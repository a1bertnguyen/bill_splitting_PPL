"""
Generate cryptographically strong server-side secrets for `.env` (never committed to Git).

Usage:
    python scripts/generate_secrets.py
"""

import secrets
from cryptography.fernet import Fernet


def main() -> None:
    print("# Paste these generated secrets into your local `.env` (NEVER commit `.env`!):")
    print(f"SECRET_KEY={secrets.token_hex(32)}")
    print(f"DATA_ENCRYPTION_KEY={Fernet.generate_key().decode('ascii')}")


if __name__ == "__main__":
    main()
