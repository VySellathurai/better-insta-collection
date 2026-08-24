#!/usr/bin/env python3
"""
telegram.py — récupère les URLs envoyées au bot Telegram et déclenche Collect.

Fonctionnement :
  1. lit TELEGRAM_TOKEN et TELEGRAM_CHAT_ID dans .env (à la racine du Vault)
  2. récupère les messages non lus via l'API Telegram
  3. extrait les URLs Instagram
  4. passe le fichier temporaire à reels-collect
  5. marque les messages comme lus (via l'offset) pour ne pas les retraiter

Usage :
    reels-telegram --vault "$HOME/Vault" --cookies firefox
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

CONFIG_FILE = ".env"
OFFSET_FILE = "telegram_offset.txt"


def lire_config(vault: Path) -> tuple[str, str]:
    """Lit TELEGRAM_TOKEN et TELEGRAM_CHAT_ID depuis .env ou variables d'environnement."""
    token = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    config_path = vault / CONFIG_FILE
    if config_path.exists():
        for line in config_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key == "TELEGRAM_TOKEN" and not token:
                token = value
            elif key == "TELEGRAM_CHAT_ID" and not chat_id:
                chat_id = value

    if not token or not chat_id:
        print("ERREUR : TELEGRAM_TOKEN et TELEGRAM_CHAT_ID manquants.")
        print(f"Crée le fichier {config_path} avec ce contenu :")
        print("  TELEGRAM_TOKEN=123456789:ABCdef...")
        print("  TELEGRAM_CHAT_ID=123456789")
        sys.exit(1)

    return token, chat_id


def lire_offset(vault: Path) -> int:
    offset_path = vault / OFFSET_FILE
    if offset_path.exists():
        try:
            return int(offset_path.read_text().strip())
        except ValueError:
            pass
    return 0


def sauver_offset(vault: Path, offset: int) -> None:
    (vault / OFFSET_FILE).write_text(str(offset), encoding="utf-8")


def recuperer_urls(token: str, chat_id: str, offset: int) -> tuple[list[str], int]:
    """Interroge l'API Telegram, filtre les URLs Instagram.

    Retourne (liste_urls, nouvel_offset).
    """
    params = {"timeout": 10}
    if offset:
        params["offset"] = offset

    try:
        r = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params=params,
            timeout=15,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"ERREUR réseau Telegram : {e}")
        sys.exit(1)

    data = r.json()
    if not data.get("ok"):
        print(f"ERREUR API Telegram : {data.get('description')}")
        sys.exit(1)

    urls = []
    last_update_id = None

    for update in data["result"]:
        update_id = update["update_id"]
        if last_update_id is None or update_id > last_update_id:
            last_update_id = update_id

        msg = update.get("message") or update.get("channel_post") or {}
        if str(msg.get("chat", {}).get("id")) != str(chat_id):
            continue

        text = (msg.get("text") or msg.get("caption") or "").strip()

        # Préfère extraire depuis les entités Telegram (plus fiable)
        extracted = None
        for entity in msg.get("entities", []):
            if entity["type"] == "url":
                start = entity["offset"]
                end = start + entity["length"]
                extracted = text[start:end]
                break
            if entity["type"] == "text_link":
                extracted = entity.get("url", "")
                break

        url = extracted or (text if text.startswith("http") else "")
        if url and "instagram.com" in url:
            urls.append(url)

    new_offset = (last_update_id + 1) if last_update_id is not None else offset
    return urls, new_offset


def _resoudre_reels_collect() -> str:
    """Chemin du script console reels-collect installé dans le même venv que
    l'interpréteur courant (sys.executable)."""
    candidat = Path(sys.executable).parent / "reels-collect"
    if candidat.exists():
        return str(candidat)
    return "reels-collect"  # repli : espère le trouver sur le PATH


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Récupère les URLs Telegram et déclenche Collect sur le Vault."
    )
    parser.add_argument("--vault", default=str(Path.home() / "Vault"))
    parser.add_argument(
        "--cookies",
        default=None,
        help="navigateur pour les cookies (firefox, chrome…)",
    )
    parser.add_argument(
        "--whisper-model",
        dest="whisper_model",
        default=None,
        help="modèle faster-whisper (tiny/small…)",
    )
    parser.add_argument("--limite", type=int, default=0)
    args = parser.parse_args()

    vault = Path(args.vault)

    token, chat_id = lire_config(vault)
    offset = lire_offset(vault)

    urls, new_offset = recuperer_urls(token, chat_id, offset)

    if not urls:
        print("Aucune nouvelle URL dans la boîte Telegram.")
        sauver_offset(vault, new_offset)
        return

    print(f"{len(urls)} URL(s) trouvée(s) — lancement de Collect.")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("\n".join(urls))
        tmp_path = f.name

    try:
        cmd = [
            _resoudre_reels_collect(),
            tmp_path,
            "--vault",
            str(vault),
        ]
        if args.cookies:
            cmd += ["--cookies", args.cookies]
        if args.whisper_model:
            cmd += ["--whisper-model", args.whisper_model]
        if args.limite:
            cmd += ["--limite", str(args.limite)]

        subprocess.run(cmd, check=False)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # Marque les messages comme lus seulement après une ingestion réussie
    sauver_offset(vault, new_offset)


if __name__ == "__main__":
    main()
