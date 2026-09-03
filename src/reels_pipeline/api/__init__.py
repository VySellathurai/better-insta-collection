"""API HTTP (FastAPI) qui expose le pipeline reels-vault.

Une seule route utile — `POST /content/ingestor` — qui fait le même travail
que `reels_pipeline/cli.py` `main()` (collect → images → enrich → publish),
lancé en tâche de fond et suivi par un identifiant de job. Voir `app.py`.

Le service se lie à 127.0.0.1 par défaut et n'a pas d'authentification : il
shelle vers `reels-pipeline` avec des chemins fournis par l'appelant, dans la
même logique « outil local » que le reste du dépôt. L'exposer au réseau ou
ajouter de l'auth est hors périmètre.
"""
