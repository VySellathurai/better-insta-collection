"""L'application FastAPI et ses routes.

POST /content/ingestor           — démarre un run du pipeline (tâche de fond)
GET  /content/ingestor           — liste les jobs (plus récent d'abord)
GET  /content/ingestor/{id}      — état + journal d'un job
GET  /content/ingestor/{id}/logs — journal d'un job en texte brut
GET  /health                     — sonde de vie
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse

from .jobs import Job, JobBusyError, run_ingest_job, store
from .schemas import IngestRequest, JobDetail, JobSummary

app = FastAPI(
    title="reels-vault API",
    summary="Déclenche le pipeline reels-vault (collect → images → enrich → publish).",
    description=(
        "Un seul point d'entrée utile : `POST /content/ingestor`, qui fait le "
        "même travail que le script `reels-pipeline` mais en **tâche de fond**. "
        "L'appel renvoie un id de job (202) ; on suit ensuite sa `phase` "
        "(`queued → running → done | error`) et son journal via "
        "`GET /content/ingestor/{id}`.\n\n"
        "`limit` (nombre max de liens) est **obligatoire** : une requête sans "
        "`limit` est rejetée en **422**, pour qu'aucun run ne parte sans borne.\n\n"
        "Un seul job à la fois — un `POST` pendant qu'un job tourne renvoie "
        "**409**. Les jobs vivent en mémoire et disparaissent au redémarrage.\n\n"
        "Service local : lié à `127.0.0.1`, **sans authentification**."
    ),
    openapi_tags=[
        {"name": "ingestor", "description": "Lancer et suivre un run du pipeline."},
        {"name": "health", "description": "Sonde de vie."},
    ],
)

_409: dict[int | str, dict[str, Any]] = {409: {"description": "Un job est déjà en cours."}}
_404: dict[int | str, dict[str, Any]] = {404: {"description": "Job inconnu."}}

# Références fortes vers les tâches de fond en vol : sans ça, asyncio ne garde
# qu'une weakref et le GC peut annuler le run en cours de route.
_EN_COURS: set[asyncio.Task[None]] = set()


def _detail(job: Job) -> JobDetail:
    return JobDetail(
        id=job.id,
        phase=job.phase,
        started_at=job.started_at,
        finished_at=job.finished_at,
        exit_code=job.exit_code,
        params=job.params,
        argv=job.argv,
        logs=job.logs,
        error=job.error,
        status_url=f"/content/ingestor/{job.id}",
    )


@app.get("/health", tags=["health"], summary="Sonde de vie")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/content/ingestor",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobDetail,
    tags=["ingestor"],
    summary="Démarrer un run du pipeline",
    responses=_409,
)
async def demarrer_ingestion(req: IngestRequest, response: Response) -> JobDetail:
    """Même travail que `reels_pipeline/cli.py` `main()`, en tâche de fond.

    `limit` est obligatoire (422 sinon) — aucun run n'est lancé sans borne.
    Sans `urls` ni `source_file` → configuration verrouillée du mm-pipeline.
    """
    try:
        job = store.create(req)
    except JobBusyError as erreur:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erreur)) from erreur

    task = asyncio.create_task(run_ingest_job(job, req))
    # Garde une référence le temps du run pour que le GC ne l'annule pas.
    _EN_COURS.add(task)
    task.add_done_callback(_EN_COURS.discard)

    response.headers["Location"] = f"/content/ingestor/{job.id}"
    return _detail(job)


@app.get(
    "/content/ingestor",
    response_model=list[JobSummary],
    tags=["ingestor"],
    summary="Lister les jobs (plus récent d'abord)",
)
def lister_jobs() -> list[JobSummary]:
    return [
        JobSummary(
            id=j.id,
            phase=j.phase,
            started_at=j.started_at,
            finished_at=j.finished_at,
            exit_code=j.exit_code,
        )
        for j in store.list()
    ]


@app.get(
    "/content/ingestor/{job_id}",
    response_model=JobDetail,
    tags=["ingestor"],
    summary="État + journal d'un job",
    responses=_404,
)
def etat_job(
    job_id: str,
    tail: int | None = Query(
        default=None, ge=1, description="Ne renvoyer que les N dernières lignes de log."
    ),
) -> JobDetail:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Job inconnu : {job_id}")
    detail = _detail(job)
    if tail is not None:
        detail.logs = detail.logs[-tail:]
    return detail


@app.get(
    "/content/ingestor/{job_id}/logs",
    response_class=PlainTextResponse,
    tags=["ingestor"],
    summary="Journal d'un job (texte brut)",
    responses=_404,
)
def journal_job(
    job_id: str,
    tail: int | None = Query(
        default=None, ge=1, description="Ne renvoyer que les N dernières lignes de log."
    ),
) -> PlainTextResponse:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Job inconnu : {job_id}")
    lignes = job.logs[-tail:] if tail is not None else job.logs
    return PlainTextResponse(
        "\n".join(lignes),
        headers={
            "X-Job-Phase": job.phase,
            "X-Job-Exit-Code": "" if job.exit_code is None else str(job.exit_code),
        },
    )
