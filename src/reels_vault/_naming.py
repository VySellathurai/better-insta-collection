"""Utilitaires de nommage partagés entre les phases (Collect, Graph)."""

from __future__ import annotations

import re


def identifiant(lien: str) -> str:
    """Un nom de fichier court et sûr, dérivé de l'URL."""
    fin = lien.rstrip("/").split("/")[-1].split("?")[0]
    fin = re.sub(r"[^A-Za-z0-9_-]", "", fin)[:40]
    return f"insta_{fin or str(abs(hash(lien)))[:10]}"
