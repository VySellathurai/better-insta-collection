"""Le porteur d'état en mémoire qui remplace la fiche Markdown entre les
étapes du pipeline — plus aucune écriture intermédiaire sur disque."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path


@dataclass
class PipelineItem:
    """Rempli progressivement par les étapes 1 à 3, puis consommé tel quel
    par l'étape 4 (publication en base). `id` est la clé primaire d'upsert —
    voir _naming.identifiant()."""

    url: str
    id: str
    collection: str | None
    genre: str  # "video" | "carrousel"
    author: str
    author_handle: str | None
    duration_s: float | None
    processed_at: date
    description: str | None

    # Renseigné par l'étape 1 (audio) — None si pas d'audio exploitable.
    transcript: str | None = None

    # Renseigné par l'étape 2 — chemins absolus vers les fichiers extraits/
    # téléchargés ; l'étape 4 les convertit en chemins relatifs à
    # <vault>/images/ pour la colonne post_images.file_name.
    images: list[Path] = field(default_factory=list)

    # Renseigné par l'étape 3 (Ollama).
    tags: list[str] = field(default_factory=list)
    title: str = ""
    summary: str = ""
