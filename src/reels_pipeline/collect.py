"""Étape 1 du pipeline — métadonnées, téléchargement audio/vidéo (ou
carrousel), et transcription faster-whisper. Aucune écriture de fiche
Markdown : produit un PipelineItem en mémoire, plus le chemin de la vidéo
téléchargée (si vidéo) pour l'étape 2 (extract_images)."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

from ._naming import identifiant
from .models import PipelineItem

YTDLP = [sys.executable, "-m", "yt_dlp"]
GALLERYDL = [sys.executable, "-m", "gallery_dl"]

logger = logging.getLogger(__name__)


def verifier_outils() -> None:
    """Verifie que yt-dlp et ffmpeg repondent avant de commencer."""
    manquants = []

    try:
        subprocess.run(YTDLP + ["--version"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        manquants.append("yt-dlp  ->  pip install yt-dlp")

    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        manquants.append("ffmpeg  ->  brew install ffmpeg")

    if manquants:
        logger.error("outil(s) manquant(s)")
        for m in manquants:
            logger.error("   %s", m)
        sys.exit(1)


def options_cookies(cookies: str | None) -> list[str]:
    """--cookies accepte soit un nom de navigateur (firefox, edge...),
    soit le chemin d'un fichier cookies.txt exporte depuis le navigateur."""
    if not cookies:
        return []
    if Path(cookies).exists():
        return ["--cookies", str(Path(cookies).resolve())]
    return ["--cookies-from-browser", cookies]


def recuperer_metadonnees(lien: str, cookies: str | None) -> dict[str, Any]:
    commande = YTDLP + ["--dump-json", "--no-warnings", "--skip-download"]
    commande += options_cookies(cookies)
    commande.append(lien)
    resultat = subprocess.run(commande, capture_output=True, text=True, timeout=120)
    if resultat.returncode != 0:
        raise RuntimeError((resultat.stderr or "yt-dlp a échoué").strip()[:300])
    return json.loads(resultat.stdout.splitlines()[0])  # type: ignore[no-any-return]


def telecharger_media(
    lien: str, dossier: Path, nom: str, cookies: str | None
) -> tuple[Path | None, Path | None]:
    """Télécharge l'audio (m4a) et la vidéo en basse qualité (pour les images)."""
    audio = dossier / f"{nom}.m4a"
    video = dossier / f"{nom}.mp4"

    base = YTDLP + ["--no-warnings", "--quiet"] + options_cookies(cookies)

    subprocess.run(
        base
        + [
            "-f",
            "bestaudio",
            "-x",
            "--audio-format",
            "m4a",
            "-o",
            str(dossier / f"{nom}.%(ext)s"),
            lien,
        ],
        capture_output=True,
        timeout=300,
    )
    subprocess.run(
        base + ["-f", "worstvideo[height>=480]/worst", "-o", str(video), lien],
        capture_output=True,
        timeout=300,
    )
    return (audio if audio.exists() else None, video if video.exists() else None)


def transcrire(audio: Path | None, modele: Any) -> str | None:
    if audio is None:
        logger.debug("Pas de fichier audio — transcription ignorée.")
        return None
    logger.info("  Transcription de %s...", audio.name)
    segments, info = modele.transcribe(str(audio), vad_filter=True)
    texte = " ".join(s.text.strip() for s in segments).strip()
    logger.info(
        "  Transcription terminée — langue : %s (%.0f%%), %d caractères.",
        info.language,
        info.language_probability * 100,
        len(texte),
    )
    return texte or None


def telecharger_carrousel(
    lien: str, dossier_images: Path, nom: str, cookies: str | None
) -> tuple[list[Path], str]:
    """Post Instagram sans vidéo : on télécharge les images du carrousel.

    Sur un carrousel, ce sont les images QUI SONT le contenu (les slides
    "10 meilleurs restos de Lisbonne"). On récupère aussi la légende, que
    yt-dlp ne sait pas lire sur ce type de post.
    """
    cible = dossier_images / nom
    cible.mkdir(parents=True, exist_ok=True)

    commande = GALLERYDL + ["--write-metadata", "-D", str(cible)]
    commande += options_cookies(cookies)
    commande.append(lien)
    subprocess.run(commande, capture_output=True, timeout=300)

    images = sorted(
        p for p in cible.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
    )

    legende = ""
    for fichier_meta in sorted(cible.glob("*.json")):
        try:
            donnees = json.loads(fichier_meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        legende = donnees.get("description") or donnees.get("caption") or ""
        if legende:
            break

    return images, legende


def mesurer_duree(video: Path) -> float | None:
    """Mesure la durée d'une vidéo via ffprobe.

    Sert de filet de sécurité quand yt-dlp ne renseigne pas le champ
    "duration" dans ses métadonnées (arrive pour certains reels malgré des
    flux vidéo bien présents) : on télécharge quand même la vidéo, puis on
    mesure sa durée directement sur le fichier plutôt que de se fier au seul
    champ yt-dlp pour décider s'il s'agit d'une vidéo.
    """
    try:
        resultat = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(video),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return float(resultat.stdout.strip())
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


def run(
    lien: str,
    dossier_temp: Path,
    dossier_images: Path,
    cookies: str | None,
    modele: Any,
    collection: str | None,
) -> tuple[PipelineItem, Path | None]:
    """Exécute l'étape 1 pour une URL : métadonnées, téléchargement,
    transcription. Retourne l'item (encore sans images/tags/résumé) et,
    s'il s'agit d'une vidéo, le chemin du fichier téléchargé — à passer à
    l'étape 2 pour l'extraction des frames. Pour un carrousel, les images
    sont déjà dans item.images et le second élément est None.

    Lève une exception si ni vidéo ni image n'a pu être récupérée — à
    l'appelant (pipeline/run.py) de logger et passer au lien suivant.
    """
    nom = identifiant(lien)
    if not nom:
        raise RuntimeError(f"URL sans segment exploitable pour un identifiant : {lien}")

    erreur_meta = ""
    try:
        meta = recuperer_metadonnees(lien, cookies)
    except Exception as e:  # noqa: BLE001 — carrousel, ou probleme d'acces
        meta = {}
        erreur_meta = str(e).replace("\n", " ")[:300]

    audio = video = None
    if meta:
        # yt-dlp a extrait des métadonnées : c'est presque toujours une
        # vidéo (son extracteur Instagram ne gère pas les carrousels
        # multi-images, il échoue dessus — d'où le bloc except ci-dessus).
        audio, video = telecharger_media(lien, dossier_temp, nom, cookies)

    if video is not None:
        genre = "video"
        # Le champ "duration" n'est pas toujours renseigné par Instagram/
        # yt-dlp même quand il y a bien un flux vidéo : on mesure la durée
        # nous-mêmes via ffprobe si besoin, plutôt que de s'y fier seul.
        duree = meta.get("duration") or mesurer_duree(video)
        transcript = transcrire(audio, modele)
        if audio is not None and audio.exists():
            audio.unlink()  # plus besoin une fois transcrit
        item = PipelineItem(
            url=lien,
            id=nom,
            collection=collection,
            genre=genre,
            author=meta.get("uploader") or meta.get("channel") or "inconnu",
            author_handle=meta.get("uploader_id") or meta.get("channel_id"),
            duration_s=duree,
            processed_at=date.today(),
            description=(meta.get("description") or "").strip() or None,
            transcript=transcript,
        )
        return item, video

    images, legende = telecharger_carrousel(lien, dossier_images, nom, cookies)
    if not images:
        raise RuntimeError(
            "ni vidéo ni image récupérée | yt-dlp : " + (erreur_meta or "aucun message")
        )
    description = (meta.get("description") or "").strip() or legende.strip() or None
    item = PipelineItem(
        url=lien,
        id=nom,
        collection=collection,
        genre="carrousel",
        author=meta.get("uploader") or meta.get("channel") or "inconnu",
        author_handle=meta.get("uploader_id") or meta.get("channel_id"),
        duration_s=None,
        processed_at=date.today(),
        description=description,
    )
    item.images = images
    return item, None
