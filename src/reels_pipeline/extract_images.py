"""Étape 2 du pipeline — extraction de NB_IMAGES captures réparties dans la
vidéo (via ffmpeg). Pour un carrousel, les images ont déjà été téléchargées
à l'étape 1 (collect.py, via gallery-dl) et cette étape est un no-op."""

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from .models import PipelineItem

NB_IMAGES = 3

logger = logging.getLogger(__name__)


def extraire_images(video: Path, dossier_images: Path, nom: str, duree: float | None) -> list[Path]:
    """Prend NB_IMAGES captures réparties dans la vidéo."""
    if not duree:
        return []
    chemins = []
    for i in range(NB_IMAGES):
        instant = duree * (i + 1) / (NB_IMAGES + 1)
        sortie = dossier_images / f"{nom}_{i + 1}.jpg"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-ss",
                f"{instant:.1f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-vf",
                "scale=720:-1",
                str(sortie),
            ],
            capture_output=True,
            timeout=90,
        )
        if sortie.exists():
            chemins.append(sortie)
            logger.info("  Image extraite : %s", sortie.name)
    return chemins


def run(item: PipelineItem, video: Path | None, dossier_images: Path) -> None:
    """Complète item.images en place. Pas d'effet pour un carrousel (video
    est None — les images y ont déjà été téléchargées à l'étape 1)."""
    if video is None:
        return
    try:
        item.images = extraire_images(video, dossier_images, item.id, item.duration_s)
    finally:
        if video.exists():
            video.unlink()  # plus besoin une fois les frames extraites
