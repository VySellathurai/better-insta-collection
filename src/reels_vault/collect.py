#!/usr/bin/env python3
"""
collect.py — transforme une liste de liens Instagram en fiches Markdown.

Pour chaque vidéo :
  1. récupère les métadonnées (titre, description, auteur, hashtags)
  2. télécharge l'audio et le transcrit en local avec faster-whisper
  3. extrait 3 images de la vidéo (pour le texte incrusté à l'écran)
  4. écrit une fiche Markdown dans vault/raw/

Étape purement mécanique : aucune dépendance à un LLM. Les tags et le résumé
sont ajoutés ensuite par la phase Digest (`reels-digest`).

Le script reprend là où il s'est arrêté : on peut le couper (Ctrl+C) et le
relancer sans retraiter ce qui est déjà fait.

Usage :
    reels-collect mes_liens.txt
    reels-collect saved_posts.json --cookies firefox
    reels-collect liens.txt --limite 20        (pour tester sur 20 vidéos)
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ._naming import identifiant

# ---------------------------------------------------------------- configuration

VAULT = Path.home() / "vault"  # modifiable avec --vault
WHISPER_MODEL = "small"  # tiny / base / small / medium
PAUSE_ENTRE_VIDEOS = 3  # secondes, pour ne pas se faire bloquer
NB_IMAGES = 3

YTDLP = [sys.executable, "-m", "yt_dlp"]
GALLERYDL = [sys.executable, "-m", "gallery_dl"]

MOTIF_LIEN = re.compile(
    r"https?://(?:www\.)?instagram\.com/[^\s\"'<>,\)\]]+"
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- utilitaires


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


def extraire_liens(chemin: str | Path) -> list[str]:
    """Récupère toutes les URLs Instagram d'un fichier, quel que soit
    son format (txt, csv, json d'export). Les doublons sont supprimés."""
    texte = Path(chemin).read_text(encoding="utf-8", errors="ignore")
    liens: list[str] = []
    vus: set[str] = set()
    for lien in MOTIF_LIEN.findall(texte):
        lien = lien.rstrip(".,;")
        if lien not in vus:
            vus.add(lien)
            liens.append(lien)
    return liens


def options_cookies(cookies: str | None) -> list[str]:
    """--cookies accepte soit un nom de navigateur (firefox, edge...),
    soit le chemin d'un fichier cookies.txt exporte depuis le navigateur."""
    if not cookies:
        return []
    if Path(cookies).exists():
        return ["--cookies", str(Path(cookies).resolve())]
    return ["--cookies-from-browser", cookies]


def charger_journal(chemin: Path) -> dict[str, Any]:
    if chemin.exists():
        return json.loads(chemin.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    return {}


def sauver_journal(chemin: Path, journal: dict[str, Any]) -> None:
    chemin.write_text(json.dumps(journal, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- étapes


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


def transcrire(audio: Path | None, modele: Any) -> str:
    if audio is None:
        logger.debug("Pas de fichier audio — transcription ignorée.")
        return ""
    logger.info("  Transcription de %s...", audio.name)
    segments, info = modele.transcribe(str(audio), vad_filter=True)
    texte = " ".join(s.text.strip() for s in segments).strip()
    logger.info(
        "  Transcription terminée — langue : %s (%.0f%%), %d caractères.",
        info.language,
        info.language_probability * 100,
        len(texte),
    )
    return texte


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


def extraire_images(
    video: Path | None, dossier_images: Path, nom: str, duree: float | None
) -> list[Path]:
    """Prend NB_IMAGES captures réparties dans la vidéo."""
    if video is None or not duree:
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


def ecrire_fiche(
    dossier: Path,
    vault: Path,
    nom: str,
    lien: str,
    meta: dict[str, Any],
    transcription: str,
    images: list[Path],
    genre: str,
    collection: str | None = None,
) -> None:
    liens_images = []
    for p in images:
        try:
            liens_images.append(f"- {p.relative_to(vault).as_posix()}")
        except ValueError:
            liens_images.append(f"- {p.name}")

    ligne_collection = f"collection: {collection}\n" if collection else ""
    contenu = f"""---
source: {lien}
plateforme: Instagram
{ligne_collection}genre: {genre}
auteur: {meta.get("uploader") or meta.get("channel") or "inconnu"}
duree_s: {meta.get("duration") or ""}
traite_le: {datetime.now():%Y-%m-%d}
statut: brut
tags:
---

# {(meta.get("title") or nom)[:120]}

## Tags
(non généré)

## Description
{(meta.get("description") or "").strip() or "(vide)"}

## Transcription audio
{transcription or "(pas d'audio exploitable)"}

## Images
{chr(10).join(liens_images) or "(aucune)"}
"""
    fiche_path = dossier / f"{nom}.md"
    fiche_path.write_text(contenu, encoding="utf-8")
    logger.info("  Fiche écrite : %s", fiche_path.name)


# ---------------------------------------------------------------- programme


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

    parseur = argparse.ArgumentParser()
    parseur.add_argument("fichier", help="fichier contenant les liens")
    parseur.add_argument("--vault", default=str(VAULT))
    parseur.add_argument(
        "--cookies", default=None, help="navigateur pour les cookies (chrome, firefox, edge)"
    )
    parseur.add_argument(
        "--limite", type=int, default=0, help="ne traiter que les N premières vidéos"
    )
    parseur.add_argument(
        "--whisper-model",
        dest="whisper_model",
        default=WHISPER_MODEL,
        help="modèle faster-whisper (tiny/base/small/medium)",
    )
    parseur.add_argument(
        "--collection",
        default=None,
        help="nom de la collection Instagram source (optionnel, écrit dans le frontmatter)",
    )
    args = parseur.parse_args()

    verifier_outils()

    vault = Path(args.vault)
    dossier_raw = vault / "raw"
    dossier_images = vault / "images"
    dossier_temp = vault / ".temp"
    for d in (dossier_raw, dossier_images, dossier_temp):
        d.mkdir(parents=True, exist_ok=True)

    chemin_journal = vault / "journal.json"
    journal = charger_journal(chemin_journal)

    liens = extraire_liens(args.fichier)
    a_faire = [l for l in liens if journal.get(l, {}).get("statut") != "ok"]
    if args.limite:
        a_faire = a_faire[: args.limite]

    logger.info("%d liens trouvés, %d à traiter.", len(liens), len(a_faire))
    if not a_faire:
        return

    logger.info("Chargement du modèle Whisper « %s » (long la 1re fois)...", args.whisper_model)
    from faster_whisper import WhisperModel

    modele = WhisperModel(args.whisper_model, device="cpu", compute_type="int8")

    reussites = echecs = 0
    for numero, lien in enumerate(a_faire, 1):
        nom = identifiant(lien)
        logger.info("[%d/%d] %s", numero, len(a_faire), lien)
        try:
            erreur_meta = ""
            try:
                meta = recuperer_metadonnees(lien, args.cookies)
            except Exception as e:
                meta = {}  # carrousel, ou probleme d'acces
                erreur_meta = str(e).replace("\n", " ")[:300]

            audio = video = None
            images: list[Path] = []
            transcription = ""
            genre = "carrousel"

            if meta:
                # yt-dlp a extrait des métadonnées : c'est presque toujours une
                # vidéo (son extracteur Instagram ne gère pas les carrousels
                # multi-images, il échoue dessus — d'où le bloc except
                # ci-dessus). Le champ "duration" n'est pas toujours renseigné
                # par Instagram/yt-dlp même quand il y a bien un flux vidéo :
                # on télécharge donc la vidéo puis on mesure sa durée nous-
                # mêmes via ffprobe si besoin, plutôt que de se fier
                # uniquement à ce champ pour décider du genre.
                audio, video = telecharger_media(lien, dossier_temp, nom, args.cookies)

            if video is not None:
                genre = "video"
                duree = meta.get("duration") or mesurer_duree(video)
                meta["duration"] = duree
                transcription = transcrire(audio, modele)
                images = extraire_images(video, dossier_images, nom, duree)
            else:
                images, legende = telecharger_carrousel(lien, dossier_images, nom, args.cookies)
                if not images:
                    raise RuntimeError(
                        "ni vidéo ni image récupérée | yt-dlp : " + (erreur_meta or "aucun message")
                    )
                if legende and not meta.get("description"):
                    meta["description"] = legende

            ecrire_fiche(
                dossier_raw, vault, nom, lien, meta, transcription, images, genre, args.collection
            )

            for fichier in (audio, video):
                if fichier and fichier.exists():
                    fichier.unlink()

            journal[lien] = {"statut": "ok", "fiche": f"{nom}.md"}
            reussites += 1
        except Exception as erreur:  # noqa: BLE001 — on continue quoi qu'il arrive
            logger.warning("échec : %s", erreur)
            journal[lien] = {"statut": "echec", "erreur": str(erreur)[:300]}
            echecs += 1

        sauver_journal(chemin_journal, journal)
        time.sleep(PAUSE_ENTRE_VIDEOS)

    logger.info("Terminé — %d réussites, %d échecs.", reussites, echecs)
    logger.info("Fiches disponibles dans : %s", dossier_raw)
    if echecs:
        logger.info("Relance le script pour retenter uniquement les échecs.")


if __name__ == "__main__":
    main()
