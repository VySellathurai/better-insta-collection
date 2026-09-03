"""Point d'entrée du script console `reels-api` — lance uvicorn.

    reels-api                       # 127.0.0.1:8000
    REELS_API_PORT=9000 reels-api

Se lie à localhost par défaut : ce service n'a pas d'authentification (voir
le docstring du paquet)."""

from __future__ import annotations

import logging
import os


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    import uvicorn

    uvicorn.run(
        "reels_pipeline.api.app:app",
        host=os.environ.get("REELS_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("REELS_API_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
