#!/usr/bin/env python3
"""
index_agent.py — Étape 5 automatisée : transforme les fiches raw/ en entrées index.md
via un modèle local Ollama (qwen2.5:7b par défaut).

Prérequis :
    brew install ollama
    ollama pull qwen2.5:7b      # ou qwen2.5:3b pour aller plus vite
    ollama serve                 # à laisser tourner en arrière-plan

Usage :
    python3 index_agent.py                          # traite jusqu'à 25 fiches
    python3 index_agent.py --batch 5                # teste sur 5 fiches
    python3 index_agent.py --dry-run                # aperçu sans écrire
    python3 index_agent.py --model qwen2.5:3b       # modèle plus léger
    python3 index_agent.py --vault ~/MonVault       # vault alternatif
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "qwen2.5:7b"
DEFAULT_BATCH = 25

logger = logging.getLogger(__name__)

# ── Few-shot examples tirés d'index.md (fixes, haute qualité) ────────────────

FEW_SHOT = """
=== EXEMPLE 1 — fiche riche ===
FICHE :
---
source: https://www.instagram.com/reel/DY2KpCZDBmw/
auteur: Louis Matys
---
## Description
Ce qu'on ne vous dit pas concernant la réduction des alloc chomage…!

## Transcription audio
On va parler de la réduction des allocations chômage. L'objectif de cette loi c'est de réduire de 3 mois la durée maximale pour les moins de 55 ans et de 7 mois pour les plus de 55 ans. La justification officielle c'est de faire économiser 1 milliard d'euros à l'UNEDIC. Entre 2023 et 2026, l'État a tapé 12 milliards dans les caisses de l'UNEDIC. Si l'État n'avait pas tapé dans les caisses, on serait en excédent de 2 milliards. Les députés qui ont voté ça touchent 6 000€ nets, 7 000€ de dotation, 11 000€ de crédit collaborateur soit 25 000€/mois, avec 15 à 20 semaines de vacances par an contre 5 pour le privé.

RÉPONSE :
{"titre": "La réduction des allocations chômage et les chiffres cachés de l'UNEDIC", "auteur": "Louis Matys", "themes": "politique française, économie", "contenu": "Dénonce la loi réduisant la durée d'allocation chômage (-3 mois pour les moins de 55 ans, -7 mois pour les plus de 55 ans), censée économiser 1 milliard € à l'UNEDIC. Affirme que l'État a prélevé 12 milliards € dans les caisses de l'UNEDIC entre 2023 et 2026, ce qui aurait généré un excédent de 2 milliards sans ce prélèvement. Les députés ayant voté la loi touchent 25 000€/mois et 15 à 20 semaines de vacances par an contre 5 pour le privé."}

=== EXEMPLE 2 — fiche pauvre ===
FICHE :
---
source: https://www.instagram.com/reel/DZ6_kSAPJ45/
auteur: Kaan aktas
---
## Description
Such a long awaited journey bro

## Transcription audio
(pas d'audio exploitable)

RÉPONSE :
{"titre": "Vidéo sans contenu exploitable (Kaan aktas)", "auteur": "Kaan aktas", "themes": "(aucun thème identifiable)", "contenu": "Fiche trop pauvre pour un résumé concret : pas d'audio exploitable, description limitée à 'Such a long awaited journey bro' sans détail sur le lieu ou l'événement."}
"""

SYSTEM_PROMPT = """Tu es un assistant qui indexe des fiches de vidéos sociales en français.
Pour chaque fiche, tu extrais exactement 4 champs et réponds UNIQUEMENT avec du JSON valide.

RÈGLES STRICTES :
- titre : court, concret, descriptif — JAMAIS générique ("Cette vidéo parle de…" est interdit)
- auteur : copie exactement le champ "auteur" du frontmatter de la fiche
- themes : 1 à 3 thèmes séparés par des virgules ; si le contenu est trop pauvre : "(aucun thème identifiable)"
- contenu : 2 à 4 lignes avec des FAITS CONCRETS (chiffres, noms, lieux, prix, adresses, horaires)
  → Si transcription vide ou trop vague : "Fiche trop pauvre pour un résumé concret : [raison précise]"

FORMAT DE RÉPONSE (JSON uniquement, aucun texte avant ou après) :
{"titre": "...", "auteur": "...", "themes": "...", "contenu": "..."}"""


# ── Parsing ────────────────────────────────────────────────────────────────────

def lire_frontmatter(texte: str) -> dict[str, str]:
    """Extrait les champs clé: valeur du bloc frontmatter YAML (entre --- )."""
    parties = texte.split("---", 2)
    if len(parties) < 3:
        return {}
    champs: dict[str, str] = {}
    for ligne in parties[1].splitlines():
        if ":" in ligne:
            cle, _, valeur = ligne.partition(":")
            champs[cle.strip()] = valeur.strip()
    return champs


def lire_urls_indexees(index_path: Path) -> set[str]:
    """Retourne l'ensemble des URLs déjà présentes dans index.md."""
    if not index_path.exists():
        return set()
    urls: set[str] = set()
    for ligne in index_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^-\s*lien\s*:\s*(\S+)", ligne)
        if m:
            urls.add(m.group(1).rstrip(".,;"))
    return urls


def lire_fiches_raw(dossier_raw: Path) -> list[dict[str, Any]]:
    """Retourne toutes les fiches raw/ avec leur frontmatter et contenu."""
    fiches = []
    for fichier in sorted(dossier_raw.glob("*.md")):
        texte = fichier.read_text(encoding="utf-8", errors="ignore")
        meta = lire_frontmatter(texte)
        if not meta.get("source"):
            continue
        fiches.append({
            "fichier": fichier,
            "url": meta["source"],
            "auteur": meta.get("auteur", "inconnu"),
            "traite_le": meta.get("traite_le", ""),
            "texte": texte,
        })
    return sorted(fiches, key=lambda f: f["traite_le"])


# ── Ollama ─────────────────────────────────────────────────────────────────────

def verifier_ollama(model: str) -> None:
    """Vérifie qu'Ollama tourne et que le modèle est disponible."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        r.raise_for_status()
    except requests.RequestException:
        logger.error(
            "Ollama ne répond pas sur localhost:11434.\n"
            "Lance-le avec : ollama serve"
        )
        sys.exit(1)

    modeles_dispos = [m["name"] for m in r.json().get("models", [])]
    # Vérifie correspondance partielle (qwen2.5:7b == qwen2.5:7b ou qwen2.5:7b-instruct-q4...)
    if not any(model in m or m.startswith(model.split(":")[0]) for m in modeles_dispos):
        logger.error(
            "Modèle '%s' introuvable. Modèles disponibles : %s\n"
            "Installe-le avec : ollama pull %s",
            model, ", ".join(modeles_dispos) or "(aucun)", model,
        )
        sys.exit(1)


def appeler_ollama(fiche_texte: str, model: str) -> dict[str, str]:
    """Envoie la fiche au modèle local et retourne le dict JSON parsé."""
    prompt_user = f"{FEW_SHOT}\n\n=== FICHE À ANALYSER ===\n{fiche_texte}\n\nRÉPONSE :"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_user},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
    }

    r = requests.post(OLLAMA_URL, json=payload, timeout=180)
    r.raise_for_status()

    contenu_brut = r.json()["message"]["content"]
    try:
        return json.loads(contenu_brut)  # type: ignore[no-any-return]
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Réponse non-JSON du modèle : {contenu_brut[:200]}") from e


# ── Formatage ─────────────────────────────────────────────────────────────────

def formater_entree(url: str, champs: dict[str, str]) -> str:
    """Formate une entrée index.md à partir des champs extraits."""
    titre = champs.get("titre", "Sans titre").strip()
    auteur = champs.get("auteur", "inconnu").strip()
    themes = champs.get("themes", "(aucun thème identifiable)").strip()
    contenu = champs.get("contenu", "").strip()
    return (
        f"\n### {titre}\n"
        f"- lien : {url}\n"
        f"- auteur : {auteur}\n"
        f"- thèmes : {themes}\n"
        f"- contenu : {contenu}\n"
    )


# ── Programme principal ────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

    parseur = argparse.ArgumentParser(
        description="Indexe automatiquement les fiches raw/ via un modèle Ollama local."
    )
    parseur.add_argument("--vault", default="./Vault", help="dossier vault (défaut: ./Vault)")
    parseur.add_argument("--model", default=DEFAULT_MODEL, help=f"modèle Ollama (défaut: {DEFAULT_MODEL})")
    parseur.add_argument("--batch", type=int, default=DEFAULT_BATCH, help=f"fiches par session (défaut: {DEFAULT_BATCH})")
    parseur.add_argument("--dry-run", action="store_true", help="aperçu sans écrire dans index.md")
    args = parseur.parse_args()

    vault = Path(args.vault)
    index_path = vault / "index.md"
    dossier_raw = vault / "raw"
    progression_path = vault / "progression.txt"

    if not dossier_raw.exists():
        logger.error("Dossier raw introuvable : %s", dossier_raw)
        sys.exit(1)

    if not args.dry_run:
        verifier_ollama(args.model)

    # Charger l'état actuel
    urls_indexees = lire_urls_indexees(index_path)
    toutes_fiches = lire_fiches_raw(dossier_raw)

    # Filtrer les non-traitées
    a_traiter = [f for f in toutes_fiches if f["url"] not in urls_indexees]

    logger.info(
        "%d fiches raw, %d déjà indexées, %d à traiter.",
        len(toutes_fiches), len(urls_indexees), len(a_traiter),
    )

    if not a_traiter:
        logger.info("Tout est déjà indexé — rien à faire.")
        return

    batch = a_traiter[: args.batch]
    logger.info(
        "Traitement de %d fiche(s) avec le modèle '%s'%s.",
        len(batch), args.model,
        " [DRY RUN — aucune écriture]" if args.dry_run else "",
    )

    reussites = echecs = 0
    for i, fiche in enumerate(batch, 1):
        nom = fiche["fichier"].name
        logger.info("[%d/%d] %s", i, len(batch), nom)

        if args.dry_run:
            logger.info("  → %s (dry-run, ignoré)", fiche["url"])
            continue

        try:
            champs = appeler_ollama(fiche["texte"], args.model)

            # Garantir que l'auteur correspond au frontmatter si le modèle l'a raté
            if not champs.get("auteur") or champs["auteur"] in ("inconnu", ""):
                champs["auteur"] = fiche["auteur"]

            entree = formater_entree(fiche["url"], champs)
            logger.info("  → %s", champs.get("titre", "?"))

            # Écriture dans index.md (append)
            with index_path.open("a", encoding="utf-8") as f:
                f.write(entree)

            # Mise à jour de progression.txt
            progression_path.write_text(nom, encoding="utf-8")

            reussites += 1

        except Exception as err:  # noqa: BLE001
            logger.warning("  échec : %s", err)
            echecs += 1

    if not args.dry_run:
        logger.info("Terminé — %d réussites, %d échecs.", reussites, echecs)
        restantes = len(a_traiter) - len(batch)
        if restantes > 0:
            logger.info("%d fiche(s) restante(s). Relance le script pour continuer.", restantes)


if __name__ == "__main__":
    main()
