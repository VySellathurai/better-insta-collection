"""Lecture de your_instagram_activity/saved/saved_collections.json (l'export
Meta des collections enregistrées) — utilisé par cli.py pour filtrer les
liens d'une collection, et par list_collections.py pour les lister.

Porté depuis src/collections-studio/lib/collections.ts — même structure,
mêmes correctifs (mojibake, nom tronqué)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


def _corriger_mojibake(s: str) -> str:
    """L'export Meta double-encode l'UTF-8 en Latin-1 ("Ã©" au lieu de "é").
    Re-décoder chaque valeur récupère le texte d'origine — vérifié sur des
    données réelles : "Par dÃ©faut" -> "Par défaut". Appliqué
    inconditionnellement (même à du pur ASCII, qui fait l'aller-retour sans
    changement) plutôt que sur heuristique, une heuristique fausse ici
    corromprait tous les noms de collection/légendes en français."""
    try:
        return s.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _nom(label_values: list[dict[str, Any]]) -> str:
    """Extrait le nom de la collection depuis label_values.

    .strip() est indispensable : "Comprendre " / "Cuisiner " ont un espace
    final dans l'export source. Utiliser le nom non-trimmé comme valeur
    --collection ferait silencieusement diverger l'écriture (publish.py) et
    la lecture (ce module) — trimmer une seule fois ici garde l'identifiant
    identique partout où il est utilisé."""
    for entree in label_values:
        if entree.get("label") == "Nom":
            return _corriger_mojibake(str(entree.get("value") or "")).strip()
    return ""


def _bloc_publications(label_values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """La liste des publications est la seule entrée de label_values qui a
    une clé "dict" mais pas de clé "label" — recherchée structurellement
    plutôt que par un index fixe, au cas où l'ordre varie d'un export à
    l'autre."""
    for entree in label_values:
        if "dict" in entree and "label" not in entree:
            resultat = entree.get("dict")
            return resultat if isinstance(resultat, list) else []
    return []


def _charger(chemin: Path) -> list[dict[str, Any]]:
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return donnees if isinstance(donnees, list) else []


def est_export_collections(chemin: Path) -> bool:
    """Vérifie structurellement qu'il s'agit bien d'un export de collections
    Meta (liste d'objets ayant chacun un label_values), pas un simple
    fichier texte de liens."""
    donnees = _charger(chemin)
    return bool(donnees) and all(
        isinstance(c, dict) and isinstance(c.get("label_values"), list) for c in donnees
    )


def lister_collections(chemin: Path) -> list[tuple[str, int]]:
    """Retourne (nom, nombre_de_liens) pour chaque collection de l'export,
    dans l'ordre du fichier."""
    resultat = []
    for collection in _charger(chemin):
        label_values = collection.get("label_values") or []
        nom = _nom(label_values)
        nb_liens = len(_bloc_publications(label_values))
        resultat.append((nom, nb_liens))
    return resultat


def liens_collection(chemin: Path, nom: str) -> list[str]:
    """Retourne la liste ordonnée des URLs d'une collection, comparée sur le
    nom trimmé. Liste vide si aucune collection ne correspond."""
    nom = nom.strip()
    for collection in _charger(chemin):
        label_values = collection.get("label_values") or []
        if _nom(label_values) != nom:
            continue
        liens = []
        for publication in _bloc_publications(label_values):
            for champ in publication.get("dict") or []:
                if champ.get("label") == "URL" and champ.get("value"):
                    liens.append(str(champ["value"]))
                    break
        return liens
    return []
