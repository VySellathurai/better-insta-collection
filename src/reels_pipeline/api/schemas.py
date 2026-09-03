"""Modèles Pydantic pour l'API — corps de requête `/content/ingestor` et
vues de job renvoyées à l'appelant."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ..cli import MOTIF_LIEN

JobPhase = Literal["queued", "running", "done", "error"]


class IngestRequest(BaseModel):
    """`limit` est le seul champ obligatoire — les autres reprennent un à un les
    options de `reels-pipeline` (voir `cli.py`). Trois modes d'entrée :

    * `urls` renseigné       → traite ces liens directement ;
    * `source_file` renseigné → chemin d'un fichier de liens ou d'un export
      `saved_collections.json` (filtré par `collection` le cas échéant) ;
    * ni l'un ni l'autre     → rejoue la configuration verrouillée du
      mm-pipeline (collection « Musée des Mêmes »).
    """

    # `extra="forbid"` : un champ mal orthographié renvoie 422 au lieu d'être
    # silencieusement ignoré. `limit` est obligatoire : jamais de run sans borne
    # (un run non borné = collection entière = quota Instagram cramé).
    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [
                {
                    "urls": ["https://www.instagram.com/reel/ABC123/"],
                    "limit": 1,
                    "dry_run": True,
                },
                {
                    "source_file": "your_instagram_activity/saved/saved_collections.json",
                    "collection": "Comprendre",
                    "cookies": "firefox",
                    "limit": 10,
                },
                {"limit": 10, "cookies": "firefox"},
            ]
        },
    }

    limit: int = Field(
        ge=1,
        description="Nombre max de liens traités — OBLIGATOIRE (replafonné à 50 "
        "côté serveur). Empêche tout run non borné.",
    )
    urls: list[str] | None = Field(
        default=None,
        description="Liens Instagram à traiter directement (reel/post/tv). "
        "Exclusif avec `source_file`.",
    )
    source_file: str | None = Field(
        default=None,
        description="Chemin d'un fichier de liens ou d'un export "
        "`saved_collections.json` (relatif à la racine du dépôt).",
    )
    collection: str | None = Field(
        default=None,
        description="Ne garder que cette collection quand `source_file` est un "
        "export `saved_collections.json`.",
    )
    cookies: str | None = Field(
        default=None,
        description="Navigateur (`firefox`, `chrome`, …) ou chemin d'un "
        "cookies.txt, passé tel quel à `--cookies`.",
    )
    whisper_model: str | None = Field(
        default=None, description="Modèle faster-whisper pour la transcription."
    )
    llm_model: str | None = Field(default=None, description="Modèle Ollama pour l'enrichissement.")
    database_url: str | None = Field(
        default=None,
        description="URL Postgres cible. Par défaut : env / `<vault>/.env` "
        "(ou la base mm en mode verrouillé).",
    )
    vault: str | None = Field(default=None, description="Dossier vault de destination des images.")
    dry_run: bool = Field(default=False, description="Tout exécuter sauf l'écriture en base.")

    @model_validator(mode="after")
    def _verifier_entree(self) -> IngestRequest:
        if self.urls is not None and self.source_file is not None:
            raise ValueError("Passe soit `urls`, soit `source_file`, pas les deux.")
        if self.urls is not None:
            if not self.urls:
                raise ValueError("`urls` ne doit pas être une liste vide.")
            mauvais = [u for u in self.urls if not MOTIF_LIEN.fullmatch(u.strip())]
            if mauvais:
                raise ValueError(f"URL(s) Instagram invalide(s) : {mauvais}")
        return self


class JobSummary(BaseModel):
    """Vue courte d'un job (liste)."""

    id: str
    phase: JobPhase = Field(description="queued → running → done | error")
    started_at: float | None = Field(description="Timestamp epoch du démarrage.")
    finished_at: float | None = Field(description="Timestamp epoch de fin.")
    exit_code: int | None = Field(description="Code de sortie de `reels-pipeline`.")


class JobDetail(JobSummary):
    """Vue complète d'un job (état + journal)."""

    params: dict[str, object] = Field(description="Requête reçue (champs non nuls).")
    argv: list[str] = Field(description="Ligne de commande `reels-pipeline` lancée.")
    logs: list[str] = Field(description="Sortie du sous-processus (500 dernières lignes).")
    error: str | None = Field(description="Message d'erreur si `phase == error`.")
    status_url: str = Field(description="URL à interroger pour suivre ce job.")
