"""Étape 3 du pipeline — enrichissement via un modèle local Ollama
(qwen2.5:7b par défaut) : génère 3 tags de catégorisation ET un résumé
(titre, auteur, contenu), à partir d'un PipelineItem en mémoire (voir
models.py) — aucune fiche Markdown sur disque.

Prérequis :
    brew install ollama
    ollama pull qwen2.5:7b      # ou qwen2.5:3b pour aller plus vite
    ollama serve                 # à laisser tourner en arrière-plan
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import requests

from ._ollama import appeler_ollama

if TYPE_CHECKING:
    from .models import PipelineItem

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


def _fiche_texte(item: PipelineItem) -> str:
    """Reconstruit, uniquement pour le prompt, le texte minimal sur lequel
    les exemples FEW_SHOT ont été calibrés — plus aucune fiche n'est écrite
    sur disque, mais le format d'entrée du prompt reste identique."""
    transcript = item.transcript or "(pas d'audio exploitable)"
    return (
        "---\n"
        f"source: {item.url}\n"
        f"auteur: {item.author}\n"
        "---\n"
        "## Description\n"
        f"{item.description or '(vide)'}\n\n"
        "## Transcription audio\n"
        f"{transcript}\n"
    )


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


def run(item: PipelineItem, llm_model: str) -> None:
    """Complète item.tags/title/summary en place."""
    item.tags = extraire_tags(item.transcript or "", item.description or "", llm_model)

    champs = resumer_fiche(_fiche_texte(item), llm_model)
    titre = " ".join((champs.get("titre") or "").split()) or item.url
    auteur = (champs.get("auteur") or "").strip()
    contenu = " ".join((champs.get("contenu") or "").split())

    item.title = titre
    # Garantir que l'auteur correspond au frontmatter si le modèle l'a raté.
    if auteur and auteur != "inconnu":
        item.author = auteur
    item.summary = contenu
