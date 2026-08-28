"""Utilitaires de nommage partagés entre les phases (Collect, Graph)."""

from __future__ import annotations

import re


def identifiant(lien: str) -> str:
    """Un identifiant court et sûr, dérivé de l'URL — sert de clé primaire
    (posts.id) pour l'upsert en base : doit donc être déterministe.

    Retourne "" si l'URL ne produit aucun segment exploitable ; à l'appelant
    de sauter l'entrée dans ce cas plutôt que de retomber sur hash(), qui est
    randomisé par process Python (PYTHONHASHSEED) et donnerait un id
    différent à chaque exécution — inutilisable comme clé d'upsert stable.
    """
    fin = lien.rstrip("/").split("/")[-1].split("?")[0]
    fin = re.sub(r"[^A-Za-z0-9_-]", "", fin)[:40]
    return f"insta_{fin}" if fin else ""
