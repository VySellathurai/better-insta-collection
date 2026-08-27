#!/usr/bin/env python3
"""
digest.py — enrichit les fiches raw/ via un modèle local Ollama (qwen2.5:7b par défaut) :
pour chaque fiche, génère 3 tags de catégorisation ET un résumé (titre, auteur,
thèmes, contenu), patche les tags dans la fiche brute, et ajoute une entrée
dans index.md.

Prérequis :
    brew install ollama
    ollama pull qwen2.5:7b      # ou qwen2.5:3b pour aller plus vite
    ollama serve                 # à laisser tourner en arrière-plan

Usage :
    reels-digest                          # traite jusqu'à 25 fiches
    reels-digest --batch 5                # teste sur 5 fiches
    reels-digest --dry-run                # aperçu sans écrire
    reels-digest --llm-model qwen2.5:3b   # modèle plus léger
    reels-digest --vault ~/MonVault       # vault alternatif
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Any

import requests

from ._ollama import DEFAULT_LLM_MODEL, appeler_ollama, verifier_ollama

DEFAULT_BATCH = 25

logger = logging.getLogger(__name__)

# ── Tags (Ollama, prompt court, sans few-shot) ───────────────────────────────

PROMPT_TAGS = (
    "Identifie exactement 3 tags courts en français qui catégorisent le mieux "
    "ce contenu. Les tags doivent être généraux et réutilisables (ex: cuisine, "
    "politique, voyage, finance, sport, technologie, humour...). "
    'Réponds UNIQUEMENT avec du JSON valide : {"tags": ["tag1", "tag2", "tag3"]}\n\n'
    "Contenu :\n"
)

# ── Résumé (Ollama, few-shot) — tirés d'index.md (fixes, haute qualité) ──────

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
{"titre": "La réduction des allocations chômage et les chiffres cachés de l'UNEDIC", "auteur": "Louis Matys", "contenu": "Dénonce la loi réduisant la durée d'allocation chômage (-3 mois pour les moins de 55 ans, -7 mois pour les plus de 55 ans), censée économiser 1 milliard € à l'UNEDIC. Affirme que l'État a prélevé 12 milliards € dans les caisses de l'UNEDIC entre 2023 et 2026, ce qui aurait généré un excédent de 2 milliards sans ce prélèvement. Les députés ayant voté la loi touchent 25 000€/mois et 15 à 20 semaines de vacances par an contre 5 pour le privé."}

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
{"titre": "Vidéo sans contenu exploitable (Kaan aktas)", "auteur": "Kaan aktas", "contenu": "Fiche trop pauvre pour un résumé concret : pas d'audio exploitable, description limitée à 'Such a long awaited journey bro' sans détail sur le lieu ou l'événement."}
"""

SYSTEM_PROMPT = """Tu es un assistant qui indexe des fiches de vidéos sociales en français.
Pour chaque fiche, tu extrais exactement 3 champs et réponds UNIQUEMENT avec du JSON valide.

RÈGLES STRICTES :
- titre : court, concret, descriptif — JAMAIS générique ("Cette vidéo parle de…" est interdit)
- auteur : copie exactement le champ "auteur" du frontmatter de la fiche
- contenu : 2 à 4 lignes avec des FAITS CONCRETS (chiffres, noms, lieux, prix, adresses, horaires)
  → Si transcription vide ou trop vague : "Fiche trop pauvre pour un résumé concret : [raison précise]"

FORMAT DE RÉPONSE (JSON uniquement, aucun texte avant ou après) :
{"titre": "...", "auteur": "...", "contenu": "..."}"""


# ── Ollama ─────────────────────────────────────────────────────────────────────


def extraire_tags(transcription: str, description: str, model: str) -> list[str]:
    """Identifie 3 tags majeurs via Ollama à partir de la transcription (ou
    description si pas de transcription). Retourne une liste vide si Ollama
    n'est pas disponible ou si le contenu est trop pauvre."""
    texte = transcription.strip() or description.strip()
    if not texte:
        return []

    prompt = PROMPT_TAGS + texte[:1500]

    try:
        data = appeler_ollama([{"role": "user", "content": prompt}], model)
        tags = data.get("tags", [])
        if not isinstance(tags, list):
            return []
        return [t.strip().lower() for t in tags[:3] if isinstance(t, str) and t.strip()]
    except requests.RequestException as e:
        logger.warning("  Ollama indisponible, tags ignorés : %s", e)
        return []
    except (KeyError, TypeError, RuntimeError) as e:
        logger.warning("  Réponse LLM invalide pour les tags : %s", e)
        return []


def resumer_fiche(fiche_texte: str, model: str) -> dict[str, str]:
    """Envoie la fiche au modèle local et retourne {titre, auteur, contenu}."""
    prompt_user = f"{FEW_SHOT}\n\n=== FICHE À ANALYSER ===\n{fiche_texte}\n\nRÉPONSE :"
    return appeler_ollama(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_user},
        ],
        model,
        timeout=180,
    )


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
        fiches.append(
            {
                "fichier": fichier,
                "url": meta["source"],
                "auteur": meta.get("auteur", "inconnu"),
                "traite_le": meta.get("traite_le", ""),
                "tags": meta.get("tags", ""),
                "collection": meta.get("collection", ""),
                "texte": texte,
            }
        )
    return sorted(fiches, key=lambda f: f["traite_le"])


def mettre_a_jour_tags_fiche(fiche_path: Path, tags: list[str]) -> None:
    """Patche la fiche brute in place : frontmatter `tags:` et section `## Tags`."""
    texte = fiche_path.read_text(encoding="utf-8")
    tags_frontmatter = ", ".join(tags) if tags else ""
    tags_ligne = ", ".join(f"#{t.replace(' ', '-')}" for t in tags) if tags else "(non généré)"
    texte = re.sub(r"(?m)^tags:.*$", lambda _m: f"tags: {tags_frontmatter}", texte, count=1)
    texte = re.sub(r"(?m)^## Tags\n.*$", lambda _m: f"## Tags\n{tags_ligne}", texte, count=1)
    fiche_path.write_text(texte, encoding="utf-8")


# ── Formatage ─────────────────────────────────────────────────────────────────


def _une_ligne(texte: str) -> str:
    """Aplati un texte multi-lignes (le LLM peut renvoyer des \\n malgré le prompt)
    pour rester compatible avec le format 1-ligne-par-champ d'index.md."""
    return " ".join(texte.split())


def formater_entree(url: str, champs: dict[str, str], tags: str) -> str:
    """Formate une entrée index.md à partir des champs extraits et des tags de la fiche."""
    titre = _une_ligne(champs.get("titre", "Sans titre"))
    auteur = champs.get("auteur", "inconnu").strip()
    themes = tags.strip() or "(aucun thème identifiable)"
    contenu = _une_ligne(champs.get("contenu", ""))
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
        description="Enrichit les fiches raw/ (tags + résumé) via un modèle Ollama local."
    )
    parseur.add_argument("--vault", default="./Vault", help="dossier vault (défaut: ./Vault)")
    parseur.add_argument(
        "--llm-model",
        dest="llm_model",
        default=DEFAULT_LLM_MODEL,
        help=f"modèle Ollama (défaut: {DEFAULT_LLM_MODEL})",
    )
    parseur.add_argument(
        "--batch",
        type=int,
        default=DEFAULT_BATCH,
        help=f"fiches par session (défaut: {DEFAULT_BATCH})",
    )
    parseur.add_argument(
        "--collection",
        default=None,
        help="ne traiter que les fiches de cette collection (optionnel)",
    )
    parseur.add_argument("--dry-run", action="store_true", help="aperçu sans écrire dans index.md")
    args = parseur.parse_args()

    vault = Path(args.vault)
    index_path = vault / "index.md"
    dossier_raw = vault / "raw"

    if not dossier_raw.exists():
        logger.error("Dossier raw introuvable : %s", dossier_raw)
        sys.exit(1)

    if not args.dry_run:
        verifier_ollama(args.llm_model)

    # Charger l'état actuel
    urls_indexees = lire_urls_indexees(index_path)
    toutes_fiches = lire_fiches_raw(dossier_raw)

    # Filtrer les non-traitées
    a_traiter = [f for f in toutes_fiches if f["url"] not in urls_indexees]
    if args.collection:
        a_traiter = [f for f in a_traiter if f["collection"] == args.collection]

    logger.info(
        "%d fiches raw, %d déjà indexées, %d à traiter.",
        len(toutes_fiches),
        len(urls_indexees),
        len(a_traiter),
    )

    if not a_traiter:
        logger.info("Tout est déjà indexé — rien à faire.")
        return

    batch = a_traiter[: args.batch]
    logger.info(
        "Traitement de %d fiche(s) avec le modèle '%s'%s.",
        len(batch),
        args.llm_model,
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
            tags = [t.strip() for t in fiche["tags"].split(",") if t.strip()]
            if not tags:
                transcription_m = re.search(
                    r"(?ms)^## Transcription audio\n(.*?)(?:\n## |\Z)", fiche["texte"]
                )
                description_m = re.search(
                    r"(?ms)^## Description\n(.*?)(?:\n## |\Z)", fiche["texte"]
                )
                tags = extraire_tags(
                    transcription_m.group(1).strip() if transcription_m else "",
                    description_m.group(1).strip() if description_m else "",
                    args.llm_model,
                )
                mettre_a_jour_tags_fiche(fiche["fichier"], tags)

            champs = resumer_fiche(fiche["texte"], args.llm_model)

            # Garantir que l'auteur correspond au frontmatter si le modèle l'a raté
            if not champs.get("auteur") or champs["auteur"] in ("inconnu", ""):
                champs["auteur"] = fiche["auteur"]

            entree = formater_entree(fiche["url"], champs, ", ".join(tags))
            logger.info("  → %s", champs.get("titre", "?"))

            # Écriture dans index.md (append)
            with index_path.open("a", encoding="utf-8") as f:
                f.write(entree)

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
