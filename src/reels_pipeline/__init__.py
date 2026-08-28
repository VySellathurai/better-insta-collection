"""Le pipeline en 4 étapes : collect (métadonnées + audio + transcription),
extract_images (extraction d'images), enrich (tags + résumé via Ollama), et
publish (publication asynchrone en base Postgres). Voir cli.py pour
l'orchestrateur et le point d'entrée reels-pipeline."""

__version__ = "0.1.0"
