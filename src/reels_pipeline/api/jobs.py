"""Exécution du pipeline en tâche de fond, déclenchée par l'API.

Même approche que `src/collections-studio/lib/job-runner.ts` et `telegram.py` :
on ne réimplémente pas le pipeline, on lance le script console `reels-pipeline`
en sous-processus et on streame sa sortie dans le journal du job. Un seul job
actif à la fois — garde-fou contre le rate-limiting d'Instagram.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ..cli import VAULT
from ..telegram import _resoudre_reels_pipeline

if TYPE_CHECKING:
    from .schemas import IngestRequest, JobPhase

logger = logging.getLogger(__name__)

# ── Constantes ──────────────────────────────────────────────────────────────
# src/reels_pipeline/api/jobs.py → parents[3] == racine du dépôt.
REPO_ROOT = Path(__file__).resolve().parents[3]

# Configuration verrouillée du mm-pipeline — reprend le Makefile
# (MEME_MUSEUM_*), chaque valeur surchargeable par variable d'environnement.
MM_COLLECTION = "Musée des Mêmes"
MM_VAULT = Path(os.environ.get("MEME_MUSEUM_VAULT", str(REPO_ROOT / "src/meme-museum/vault")))
MM_SAVED_COLLECTIONS = Path(
    os.environ.get(
        "MEME_MUSEUM_SAVED_COLLECTIONS",
        str(REPO_ROOT / "your_instagram_activity/saved/saved_collections.json"),
    )
)
MM_DATABASE_URL = os.environ.get(
    "MEME_MUSEUM_DATABASE_URL",
    "postgres://meme_museum:changeme@localhost:5434/meme_museum",
)

# Plafond de sécurité, toujours ré-appliqué ici quel que soit ce que demande
# l'appelant (même logique que collections-studio/types/job.ts).
MAX_LIMIT = 50
MAX_LOG_LINES = 500


@dataclass
class Job:
    id: str
    phase: JobPhase = "queued"
    params: dict[str, object] = field(default_factory=dict)
    argv: list[str] = field(default_factory=list)
    started_at: float | None = None
    finished_at: float | None = None
    exit_code: int | None = None
    logs: list[str] = field(default_factory=list)
    error: str | None = None

    def log(self, ligne: str) -> None:
        self.logs.append(ligne)
        if len(self.logs) > MAX_LOG_LINES:
            del self.logs[: len(self.logs) - MAX_LOG_LINES]


class JobBusyError(RuntimeError):
    """Levé quand un job est déjà en cours — l'appelant renvoie un 409."""


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._active: str | None = None

    def create(self, req: IngestRequest) -> Job:
        if self._active is not None:
            actif = self._jobs[self._active]
            if actif.phase in ("queued", "running"):
                raise JobBusyError(f"Un job est déjà en cours ({actif.id}).")
        job = Job(id=uuid.uuid4().hex, params=req.model_dump(exclude_none=True))
        self._jobs[job.id] = job
        self._active = job.id
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        return sorted(
            self._jobs.values(),
            key=lambda j: j.started_at or 0.0,
            reverse=True,
        )


store = JobStore()


def _construire_argv(req: IngestRequest, fichier: str) -> list[str]:
    """Traduit la requête en ligne de commande `reels-pipeline`."""
    mode_verrouille = req.urls is None and req.source_file is None

    vault = req.vault or (str(MM_VAULT) if mode_verrouille else str(VAULT))
    argv = [_resoudre_reels_pipeline(), fichier, "--vault", vault]

    database_url = req.database_url or (MM_DATABASE_URL if mode_verrouille else None)
    if database_url:
        argv += ["--database-url", database_url]

    collection = req.collection or (MM_COLLECTION if mode_verrouille else None)
    if collection:
        argv += ["--collection", collection]

    if req.cookies:
        argv += ["--cookies", req.cookies]
    # `limit` est obligatoire côté schéma — toujours passé, toujours replafonné.
    argv += ["--limite", str(min(req.limit, MAX_LIMIT))]
    if req.whisper_model:
        argv += ["--whisper-model", req.whisper_model]
    if req.llm_model:
        argv += ["--llm-model", req.llm_model]
    if req.dry_run:
        argv.append("--dry-run")
    return argv


def _preparer_fichier(req: IngestRequest) -> tuple[str, bool]:
    """Retourne (chemin_fichier_liens, à_supprimer_après). Pour `urls`, écrit
    un fichier temporaire (comme telegram.py) ; sinon renvoie le chemin fourni
    ou celui, verrouillé, du mm-pipeline."""
    if req.urls is not None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("\n".join(u.strip() for u in req.urls))
        return f.name, True
    if req.source_file is not None:
        return req.source_file, False
    return str(MM_SAVED_COLLECTIONS), False


async def run_ingest_job(job: Job, req: IngestRequest) -> None:
    job.phase = "running"
    job.started_at = time.time()
    fichier, temporaire = _preparer_fichier(req)
    try:
        job.argv = _construire_argv(req, fichier)
        job.log(f"$ {' '.join(job.argv)}")
        proc = await asyncio.create_subprocess_exec(
            *job.argv,
            cwd=str(REPO_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert proc.stdout is not None
        async for brute in proc.stdout:
            ligne = brute.decode("utf-8", errors="replace").rstrip()
            if ligne:
                job.log(ligne)
        job.exit_code = await proc.wait()
        if job.exit_code == 0:
            job.phase = "done"
        else:
            job.phase = "error"
            job.error = f"reels-pipeline a terminé avec le code {job.exit_code} (voir logs)."
    except Exception as erreur:  # noqa: BLE001 — tout échec doit finir dans le job
        job.phase = "error"
        job.error = str(erreur)
        job.log(f"ERREUR : {erreur}")
        logger.exception("job %s échoué", job.id)
    finally:
        job.finished_at = time.time()
        if temporaire:
            Path(fichier).unlink(missing_ok=True)
