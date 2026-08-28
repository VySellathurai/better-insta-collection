#!/usr/bin/env python3
"""
list_collections.py — outil dev : liste les collections Instagram enregistrées
(et leur nombre de liens) trouvées dans un export saved_collections.json.

Pratique pour trouver le nom exact à passer à `reels-pipeline --collection`
(les noms ont parfois un espace final dans l'export, ex: "Comprendre ") sans
avoir à ouvrir le JSON à la main.

Usage :
    reels-collections
    reels-collections chemin/vers/saved_collections.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ._collections import est_export_collections, lister_collections

FICHIER_PAR_DEFAUT = "your_instagram_activity/saved/saved_collections.json"


def main() -> None:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument(
        "fichier",
        nargs="?",
        default=FICHIER_PAR_DEFAUT,
        help=f"export saved_collections.json (défaut: {FICHIER_PAR_DEFAUT})",
    )
    args = parseur.parse_args()

    chemin = Path(args.fichier)
    if not chemin.exists():
        print(f"Fichier introuvable : {chemin}", file=sys.stderr)
        print(
            "Exporte tes données Instagram (Paramètres > Vos informations > "
            "Télécharger vos informations) et place saved_collections.json à cet endroit, "
            "ou passe le chemin en argument.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not est_export_collections(chemin):
        print(f"{chemin} ne ressemble pas à un export de collections Instagram.", file=sys.stderr)
        sys.exit(1)

    collections = sorted(lister_collections(chemin), key=lambda c: c[1], reverse=True)
    if not collections:
        print("Aucune collection trouvée.")
        return

    largeur = max(len(nom) for nom, _ in collections)
    for nom, nb_liens in collections:
        print(f"{nom:<{largeur}}  {nb_liens}")


if __name__ == "__main__":
    main()
