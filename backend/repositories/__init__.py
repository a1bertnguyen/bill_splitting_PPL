"""Data access repositories (MySQL 9.4 + SQLite test fallback with RLS & Fernet AES)."""

from backend.repositories.database import Database

__all__ = ["Database"]
