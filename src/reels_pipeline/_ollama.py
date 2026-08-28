"""Client Ollama partagé entre les phases (Digest utilise ceci pour les tags et le résumé)."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_LLM_MODEL = "qwen2.5:7b"

logger = logging.getLogger(__name__)


def verifier_ollama(model: str) -> None:
    """Vérifie qu'Ollama tourne et que le modèle est disponible."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        r.raise_for_status()
    except requests.RequestException:
        logger.error("Ollama ne répond pas sur localhost:11434.\n" "Lance-le avec : ollama serve")
        sys.exit(1)

    modeles_dispos = [m["name"] for m in r.json().get("models", [])]
    # Vérifie correspondance exacte ou variante taguée (qwen2.5:7b == qwen2.5:7b-instruct-q4...)
    if not any(m == model or m.startswith(model + "-") for m in modeles_dispos):
        logger.error(
            "Modèle '%s' introuvable. Modèles disponibles : %s\n"
            "Installe-le avec : ollama pull %s",
            model,
            ", ".join(modeles_dispos) or "(aucun)",
            model,
        )
        sys.exit(1)


def appeler_ollama(
    messages: list[dict[str, str]], model: str, timeout: int = 120
) -> dict[str, Any]:
    """Envoie des messages à Ollama (format JSON forcé) et retourne le dict JSON parsé
    de la réponse. Lève une exception en cas d'échec réseau ou de JSON invalide —
    à l'appelant de décider comment gérer l'échec."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
    }

    r = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
    r.raise_for_status()

    contenu_brut = r.json()["message"]["content"]
    try:
        data = json.loads(contenu_brut)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Réponse non-JSON du modèle : {contenu_brut[:200]}") from e
    if not isinstance(data, dict):
        raise RuntimeError(f"Réponse JSON inattendue (pas un objet) : {contenu_brut[:200]}")
    return data
