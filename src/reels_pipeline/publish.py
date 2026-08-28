"""Étape 4 — publication asynchrone en base Postgres.

Cible le schéma défini et migré par src/backoffice/db/schema.ts : Drizzle/
drizzle-kit reste l'autorité du schéma (migrations), ce module ne fait que du
DML (SELECT/INSERT/UPDATE/DELETE), jamais de DDL.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import asyncpg

if TYPE_CHECKING:
    from pathlib import Path

    from .models import PipelineItem

# Doit rester en phase avec MAX_IMAGES_PER_POST dans src/backoffice/db/schema.ts
# (contrainte CHECK post_images_position_check).
MAX_IMAGES_PER_POST = 3

logger = logging.getLogger(__name__)


def resoudre_database_url(vault: Path, override: str | None) -> str:
    """--database-url > variable d'environnement DATABASE_URL > <vault>/.env
    (même convention de repli que telegram.py's lire_config())."""
    if override:
        return override
    url = os.environ.get("DATABASE_URL", "")
    if url:
        return url

    config_path = vault / ".env"
    if config_path.exists():
        for ligne in config_path.read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip()
            if ligne.startswith("#") or "=" not in ligne:
                continue
            cle, _, valeur = ligne.partition("=")
            if cle.strip() == "DATABASE_URL":
                return valeur.strip()

    raise RuntimeError(
        "DATABASE_URL introuvable — passe --database-url, exporte la variable "
        f"d'environnement, ou ajoute-la à {config_path}."
    )


async def creer_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(database_url)


async def deja_publies(pool: asyncpg.Pool) -> set[str]:
    """Les source_url déjà présentes en base — remplace journal.json comme
    mécanisme de reprise/dédoublonnage : un lien qui a échoué avant l'étape 4
    n'apparaît jamais ici et sera donc retenté au prochain lancement."""
    lignes = await pool.fetch("SELECT source_url FROM posts")
    return {ligne["source_url"] for ligne in lignes}


async def publish_item(pool: asyncpg.Pool, item: PipelineItem, dossier_images: Path) -> None:
    """Upsert atomique d'un item complet (post + thèmes + images) dans une
    seule transaction. Contrairement à l'ancien scripts/seed.ts (TypeScript),
    qui videait puis rechargeait les 4 tables en entier à chaque exécution,
    ceci n'affecte que les lignes de CET item."""
    images_relatives: list[str] = []
    for chemin in item.images[:MAX_IMAGES_PER_POST]:
        try:
            images_relatives.append(chemin.relative_to(dossier_images).as_posix())
        except ValueError:
            images_relatives.append(chemin.name)
    if len(item.images) > MAX_IMAGES_PER_POST:
        logger.warning(
            "  %d images tronquées à %d pour %s", len(item.images), MAX_IMAGES_PER_POST, item.id
        )

    async with pool.acquire() as conn, conn.transaction():
        await conn.execute(
            """
            INSERT INTO posts (id, source_url, platform, genre, author, author_handle,
                                duration_s, processed_at, status, title, summary,
                                description, transcript, collection)
            VALUES ($1, $2, 'Instagram', $3, $4, $5, $6, $7, 'publie', $8, $9, $10, $11, $12)
            ON CONFLICT (id) DO UPDATE SET
                source_url = excluded.source_url, genre = excluded.genre,
                author = excluded.author, author_handle = excluded.author_handle,
                duration_s = excluded.duration_s, processed_at = excluded.processed_at,
                title = excluded.title, summary = excluded.summary,
                description = excluded.description, transcript = excluded.transcript,
                collection = excluded.collection
            """,
            item.id,
            item.url,
            item.genre,
            item.author,
            item.author_handle,
            item.duration_s,
            item.processed_at,
            item.title,
            item.summary,
            item.description,
            item.transcript,
            item.collection,
        )

        await conn.execute("DELETE FROM post_themes WHERE post_id = $1", item.id)
        for tag in item.tags:
            slug = tag.strip().lower().replace(" ", "-")
            if not slug:
                continue
            theme_id = await conn.fetchval(
                """
                INSERT INTO themes (slug, name) VALUES ($1, $2)
                ON CONFLICT (slug) DO UPDATE SET name = excluded.name
                RETURNING id
                """,
                slug,
                tag,
            )
            await conn.execute(
                "INSERT INTO post_themes (post_id, theme_id) VALUES ($1, $2)",
                item.id,
                theme_id,
            )

        await conn.execute("DELETE FROM post_images WHERE post_id = $1", item.id)
        for position, file_name in enumerate(images_relatives, start=1):
            await conn.execute(
                "INSERT INTO post_images (post_id, position, file_name) VALUES ($1, $2, $3)",
                item.id,
                position,
                file_name,
            )

    logger.info("  publié en base : %s", item.id)
