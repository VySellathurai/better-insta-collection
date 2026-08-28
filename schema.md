# Schéma du projet Reels Vault

Le projet a trois parties qui partagent une seule base de données Postgres :

1. **Le pipeline** (`src/reels_pipeline/`, Python) — collecte, transcrit, extrait des images, enrichit (tags + résumé) et **publie directement en base**, en 4 étapes internes (`collect.py` → `extract_images.py` → `enrich.py` → `publish.py`, orchestrées par `cli.py`), une seule commande (`reels-pipeline`).
2. **Le backoffice** (`src/backoffice/`, Next.js + Postgres) — lit cette base en direct et la sert via une page web et une API JSON. Ne fait plus aucun import/seed : la base est déjà à jour dès que le pipeline tourne.
3. **Collections Studio** (`src/collections-studio/`, Next.js) — permet de choisir une collection Instagram sauvegardée et de déclencher `reels-pipeline` dessus (limité, pour ne pas se faire repérer), puis affiche les résultats en lisant la même base.

Postgres est la seule source de vérité pour le contenu digéré. `Vault/` ne contient plus que les images extraites (`Vault/images/`) — plus de fiches `.md`, plus d'`index.md`, plus de `journal.json` (la reprise/dédoublonnage se fait désormais par une requête en base).

**Ce qui disparaît avec ce refacto** : `gallery.html` (page statique hors ligne) et l'intégration Obsidian (`reels-graph`) reposaient toutes les deux sur `index.md`/`raw/*.md` et sont supprimées — le backoffice et Collections Studio sont désormais les seules interfaces de consultation. Le dépôt sur Google Drive pour interroger le Vault depuis Claude mobile n'a plus de fichier à déposer non plus.

## Vue d'ensemble du workflow

```mermaid
flowchart TD
    %% ── Sources d'entrée ──────────────────────────────────────────
    subgraph SOURCES["📥  Sources d'entrée"]
        IG_EXPORT["Export Instagram\nsaved_posts.json"]
        IPHONE["iPhone\nPartager un Reel Instagram"]
    end

    %% ── Telegram ──────────────────────────────────────────────────
    subgraph TELEGRAM["☁️  Telegram (cloud)"]
        BOT["Bot Telegram\n@monvault_bot"]
        OFFSET["telegram_offset.txt\n(marque-page des messages lus)"]
    end

    %% ── Automatisation ────────────────────────────────────────────
    subgraph AUTO["⏰  Automatisation macOS"]
        LAUNCHD["launchd\n(tous les jours à 18h)"]
        INBOX_SH["inbox.sh"]
    end

    %% ── Package Python (src/reels_pipeline/) ────────────────────────
    subgraph SCRIPTS["🐍  src/reels_pipeline/ (.venv, via uv)"]
        REELS_TELEGRAM["reels-telegram\nrécupère les URLs du bot"]
        subgraph PIPELINE["reels-pipeline (une commande, 4 étapes)"]
            STEP1["1· collect\nmétadonnées + audio + transcription"]
            STEP2["2· images\n3 captures (ou carrousel)"]
            STEP3["3· enrich\ntags + résumé (Ollama)"]
            STEP4["4· publish\nupsert asyncpg (async)"]
            STEP1 --> STEP2 --> STEP3 --> STEP4
        end
    end

    %% ── Outils externes ───────────────────────────────────────────
    subgraph TOOLS["🔧  Outils externes"]
        YTDLP["yt-dlp\nmétadonnées + audio + vidéo"]
        WHISPER["faster-whisper\ntranscription locale"]
        GALLERYDL["gallery-dl\ncarrousels Instagram"]
        FFMPEG["ffmpeg\nextraction d'images"]
        OLLAMA["Ollama\nqwen2.5:7b (local)"]
    end

    %% ── Stockage local ──────────────────────────────────────────
    subgraph VAULT["📂  Vault/images/  (seul reliquat sur disque)"]
        IMAGES["images/\ncaptures extraites"]
    end

    POSTGRES[("🗄️  Postgres\n(Docker Compose, source de vérité)")]

    %% ── Backoffice (src/backoffice/) ───────────────────────────────
    subgraph BACKOFFICE["🖥️  src/backoffice/ (Next.js, lecture seule)"]
        BOAPI["Route Handlers\n/api/posts, /api/posts/:slug, /api/themes"]
        BOPAGE["Page Next.js\nrecherche + filtres par thème"]
    end

    %% ── Collections Studio (src/collections-studio/) ───────────────
    subgraph CS["🗂️  src/collections-studio/ (Next.js)"]
        CS_PICKER["Sélecteur de collection\n(lit saved_collections.json)"]
        CS_JOB["Job runner\nspawn reels-pipeline --collection --limite"]
        CS_PAGE["Page résultats\n(lit Postgres, filtré par collection)"]
    end

    %% ── Consultation ──────────────────────────────────────────────
    subgraph OUTPUT["👀  Consultation"]
        BOBROWSER["Navigateur\nhttp://localhost:3000"]
        CSBROWSER["Navigateur\nhttp://localhost:3100"]
    end

    %% ── Flux principal ────────────────────────────────────────────

    %% Voie 1 : import en masse depuis l'export Instagram
    IG_EXPORT -->|"chemin du fichier"| STEP1

    %% Voie 2 : envoi depuis le téléphone via Telegram
    IPHONE -->|"Partager → Envoyer au Vault\n(Raccourci iPhone)"| BOT
    BOT -->|"getUpdates API"| REELS_TELEGRAM
    REELS_TELEGRAM -->|"lit / met à jour"| OFFSET
    REELS_TELEGRAM -->|"URLs extraites\n(fichier temp)"| STEP1

    %% Voie 3 : Collections Studio (portion contrôlée d'une collection)
    CS_PICKER -->|"choix + limite"| CS_JOB
    CS_JOB -->|"URLs de la collection\n(fichier temp)"| STEP1

    %% Automatisation
    LAUNCHD -->|"déclenche"| INBOX_SH
    INBOX_SH -->|"appelle"| REELS_TELEGRAM

    %% étape 1 → outils
    STEP1 -->|"métadonnées"| YTDLP
    STEP1 -->|"audio .m4a"| WHISPER
    STEP1 -->|"carrousels /p/"| GALLERYDL
    YTDLP --> STEP1
    WHISPER --> STEP1
    GALLERYDL --> STEP1

    %% étape 2
    STEP2 -->|"captures vidéo"| FFMPEG
    FFMPEG --> STEP2
    STEP2 -->|"images .jpg"| IMAGES

    %% étape 3
    STEP3 -->|"tags + résumé"| OLLAMA
    OLLAMA --> STEP3

    %% étape 4 : publication directe, asynchrone
    STEP4 -->|"upsert (asyncpg, par item)"| POSTGRES

    %% Lecture
    POSTGRES --> BOAPI
    POSTGRES --> BOPAGE
    POSTGRES --> CS_PAGE
    IMAGES -.->|"symlink public/images"| BOPAGE
    IMAGES -.->|"symlink public/images"| CS_PAGE
    BOAPI --> BOBROWSER
    BOPAGE --> BOBROWSER
    CS_PICKER --> CSBROWSER
    CS_PAGE --> CSBROWSER
```

---

## Cycle de vie d'une vidéo

```mermaid
sequenceDiagram
    actor U as Utilisateur (iPhone)
    participant TG as Telegram Bot
    participant MAC as Mac (launchd 18h)
    participant TI as reels-telegram
    participant PL as reels-pipeline
    participant OL as Ollama (local)
    participant PG as Postgres

    U->>TG: Partager un Reel → "Envoyer au Vault"
    Note over TG: URL stockée côté Telegram<br/>même si le Mac est éteint

    MAC->>TI: inbox.sh (déclenchement quotidien)
    TI->>TG: getUpdates (offset)
    TG-->>TI: URLs en attente
    TI->>PL: fichier temporaire d'URLs
    TI->>MAC: met à jour telegram_offset.txt

    PL->>PG: SELECT source_url (déduplication)
    Note over PL: liens déjà en base sautés —<br/>plus de journal.json

    loop pour chaque lien à traiter
        PL->>PL: 1· collect — yt-dlp / whisper
        PL->>PL: 2· images — ffmpeg (ou carrousel gallery-dl)
        PL->>OL: 3· enrich — tags + résumé
        OL-->>PL: JSON {tags, titre, contenu}
        PL-->>PG: 4· publish — upsert asynchrone (asyncpg)
    end

    PL->>PG: attend la fin de tous les upserts en attente

    U->>MAC: ouvre http://localhost:3000 (backoffice)<br/>ou :3100 (Collections Studio)
    Note over U,PG: lecture directe de Postgres,<br/>toujours à jour dès la fin du pipeline
```

---

## Modèle de données — Postgres

`src/backoffice/db/schema.ts` (Drizzle ORM) est l'autorité du schéma — le pipeline Python (`src/reels_pipeline/publish.py`) ne fait que des upserts dessus, jamais de migration. `posts.id` est le slug déterministe dérivé de l'URL (`insta_<ID>`, voir `_naming.identifiant()`), utilisé comme clé d'upsert.

```mermaid
erDiagram
    posts ||--o{ post_themes : "a des thèmes"
    themes ||--o{ post_themes : "regroupe des posts"
    posts ||--o{ post_images : "a jusqu'à 3 images"

    posts {
        text id PK "insta_<ID>, slug déterministe dérivé de l'URL"
        text source_url UK "lien Instagram"
        text platform
        text genre
        text author
        text author_handle
        double duration_s
        date processed_at
        text status
        text title "généré par l'étape 3 (Ollama)"
        text summary "généré par l'étape 3 (Ollama)"
        text description "caption brute (étape 1)"
        text transcript "null si non exploitable"
        text collection "nom de la collection source, null sinon"
    }

    themes {
        int id PK
        text slug UK "normalisé : trim + minuscule"
        text name "forme d'affichage d'origine"
    }

    post_themes {
        text post_id PK,FK
        int theme_id PK,FK
    }

    post_images {
        text post_id PK,FK
        int position PK "1..3 (CHECK)"
        text file_name "chemin relatif à Vault/images/"
    }
```

Servi par `lib/queries.ts` (backoffice, utilisé à la fois par `app/page.tsx` et par les Route Handlers `app/api/*`) et par `lib/db.ts` (Collections Studio, une requête SQL dédiée filtrée par `collection`) :

- **`GET /api/posts`** — liste paginée, filtrable par `theme`/`q`, triée par `processed_at` décroissant
- **`GET /api/posts/:slug`** — détail d'un post
- **`GET /api/themes`** — thèmes triés par nombre de posts
- **Collections Studio** — mêmes tables, filtrées par `collection`, pas d'API exposée (lecture directe côté serveur)

---

## Structure des fichiers

```
reels-vault/                     ← racine du projet
├── src/
│   ├── reels_pipeline/           ← package Python (une étape par module, à plat)
│   │   ├── models.py             ← PipelineItem (porteur d'état en mémoire)
│   │   ├── collect.py            ← étape 1 : métadonnées + audio + transcription
│   │   ├── extract_images.py     ← étape 2 : extraction de 3 captures (ffmpeg)
│   │   ├── enrich.py             ← étape 3 : tags + résumé via Ollama local
│   │   ├── publish.py            ← étape 4 : upsert asyncpg dans Postgres
│   │   ├── cli.py                ← orchestrateur async, CLI reels-pipeline
│   │   ├── telegram.py           ← pont Telegram → reels-pipeline
│   │   ├── _ollama.py            ← client Ollama partagé
│   │   └── _naming.py            ← dérivation déterministe du slug depuis une URL
│   │
│   ├── backoffice/                ← Next.js + Postgres, lecture seule
│   │   ├── app/                   ← pages (App Router) + Route Handlers /api/*
│   │   ├── components/            ← galerie, recherche, filtres par thème
│   │   ├── db/                    ← schema.ts (Drizzle, autorité du schéma) + client Postgres
│   │   ├── lib/queries.ts         ← requêtes partagées page + API
│   │   ├── drizzle/               ← migrations SQL générées
│   │   ├── docker-compose.yml     ← Postgres, port 5433
│   │   └── public/images          ← symlink vers ../../../Vault/images
│   │
│   └── collections-studio/        ← Next.js, pick + trigger + résultats d'une collection
│       ├── lib/collections.ts     ← parse saved_collections.json
│       ├── lib/job-runner.ts      ← spawn reels-pipeline, job en mémoire
│       ├── lib/db.ts              ← requête SQL dédiée (postgres, sans Drizzle)
│       └── public/images          ← symlink vers ../../../Vault/images
│
├── pyproject.toml                ← dépendances + entry points reels-* (uv)
├── Makefile                      ← cibles Python (racine) + bo-* + cs-*
├── .env                          ← TOKEN + CHAT_ID (ignoré par git)
├── .env.example                  ← modèle à copier
├── .gitignore
│
└── Vault/                        ← ignoré par git
    ├── images/                   ← captures extraites des vidéos (seul contenu restant)
    └── telegram_offset.txt       ← dernier message Telegram lu
```
