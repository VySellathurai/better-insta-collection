#!/usr/bin/env python3
"""
cli.py — le pipeline complet, 4 étapes, une seule commande.

Pour chaque lien Instagram :
  1. collect   — métadonnées, téléchargement audio/vidéo (ou carrousel),
                 transcription faster-whisper
  2. images    — extraction de 3 captures de la vidéo (no-op pour un carrousel,
                 déjà téléchargé en étape 1)
  3. enrich    — 3 tags + résumé via un modèle Ollama local
  4. publish   — upsert asynchrone dans Postgres (asyncpg)

Plus de fiche Markdown intermédiaire, plus d'index.md : chaque lien traité
avec succès finit directement en base. Le script reprend là où il s'est
arrêté — la reprise se fait désormais par une requête en base (les liens déjà
dans `posts` sont sautés), plus par un fichier journal.json.

Usage :
    reels-pipeline mes_liens.txt
    reels-pipeline saved_posts.json --cookies firefox
    reels-pipeline liens.txt --limite 20        (pour tester sur 20 vidéos)
    reels-pipeline liens.txt --dry-run           (étapes 1-3, rien écrit en base)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path
from typing import Any

from . import collect, enrich, extract_images, publish
from ._ollama import DEFAULT_LLM_MODEL, verifier_ollama

VAULT = Path.home() / "vault"  # modifiable avec --vault
WHISPER_MODEL = "small"  # tiny / base / small / medium
PAUSE_ENTRE_VIDEOS = 3  # secondes, pour ne pas se faire bloquer

MOTIF_LIEN = re.compile(r"https?://(?:www\.)?instagram\.com/[^\s\"'<>,\)\]]+")

logger = logging.getLogger(__name__)


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


async def traiter_un_lien(
    lien: str,
    dossier_temp: Path,
    dossier_images: Path,
    args: argparse.Namespace,
    modele: Any,
) -> Any | None:
    """Exécute les étapes 1-3 pour un lien (dans un thread, ce sont des
    appels bloquants : subprocess yt-dlp/ffmpeg, faster-whisper, requests
    vers Ollama). Retourne l'item prêt à publier, ou None en cas d'échec
    (déjà loggé) — le lien sera retenté au prochain lancement puisqu'il
    n'atteint jamais la base."""
    try:
        item, video = await asyncio.to_thread(
            collect.run,
            lien,
            dossier_temp,
            dossier_images,
            args.cookies,
            modele,
            args.collection,
        )
        await asyncio.to_thread(extract_images.run, item, video, dossier_images)
        await asyncio.to_thread(enrich.run, item, args.llm_model)
        return item
    except Exception as erreur:  # noqa: BLE001 — on continue quoi qu'il arrive
        logger.warning("échec : %s", erreur)
        return None


async def main_async(args: argparse.Namespace) -> None:
    collect.verifier_outils()

    vault = Path(args.vault)
    dossier_images = vault / "images"
    dossier_temp = vault / ".temp"
    for d in (dossier_images, dossier_temp):
        d.mkdir(parents=True, exist_ok=True)

    database_url = publish.resoudre_database_url(vault, args.database_url)
    pool = await publish.creer_pool(database_url)

    try:
        deja = await publish.deja_publies(pool)

        liens = extraire_liens(args.fichier)
        a_faire = [u for u in liens if u not in deja]
        if args.limite:
            a_faire = a_faire[: args.limite]

        logger.info("%d liens trouvés, %d à traiter.", len(liens), len(a_faire))
        if not a_faire:
            return

        verifier_ollama(args.llm_model)

        logger.info("Chargement du modèle Whisper « %s » (long la 1re fois)...", args.whisper_model)
        from faster_whisper import WhisperModel

        modele = WhisperModel(args.whisper_model, device="cpu", compute_type="int8")

        pending_publishes: list[asyncio.Task[None]] = []
        reussites = echecs = 0
        for numero, lien in enumerate(a_faire, 1):
            logger.info("[%d/%d] %s", numero, len(a_faire), lien)
            item = await traiter_un_lien(lien, dossier_temp, dossier_images, args, modele)
            if item is None:
                echecs += 1
            else:
                reussites += 1
                if not args.dry_run:
                    pending_publishes.append(
                        asyncio.create_task(publish.publish_item(pool, item, dossier_images))
                    )
                else:
                    logger.info("  [DRY RUN] %s — titre=%r tags=%r", item.id, item.title, item.tags)

            await asyncio.sleep(PAUSE_ENTRE_VIDEOS)

        if pending_publishes:
            await asyncio.gather(*pending_publishes)

        logger.info("Terminé — %d réussites, %d échecs.", reussites, echecs)
        if echecs:
            logger.info("Relance le script pour retenter uniquement les échecs.")
    finally:
        await pool.close()


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
        "--limite", type=int, default=0, help="ne traiter que les N premiers liens"
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
        help="nom de la collection Instagram source (optionnel, écrit en base)",
    )
    parseur.add_argument(
        "--llm-model",
        dest="llm_model",
        default=DEFAULT_LLM_MODEL,
        help=f"modèle Ollama pour l'étape 3 (défaut: {DEFAULT_LLM_MODEL})",
    )
    parseur.add_argument(
        "--database-url",
        dest="database_url",
        default=None,
        help="URL Postgres (défaut: variable DATABASE_URL, ou <vault>/.env)",
    )
    parseur.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="exécute les étapes 1-3 normalement, mais n'écrit rien en base (étape 4 sautée)",
    )
    args = parseur.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
