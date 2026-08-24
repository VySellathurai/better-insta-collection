# Schéma du projet Reels Vault

Le projet a deux parties indépendantes qui partagent les mêmes données sur disque (`Vault/`) :

1. **Le pipeline** (`src/reels_vault/`, Python) — collecte, digère et publie les vidéos en fichiers plats.
2. **Le backoffice** (`src/backoffice/`, Next.js + Postgres, optionnel) — recharge ces mêmes fichiers dans une base de données et les sert via une page web et une API JSON.

Le pipeline reste la source de vérité ; le backoffice n'est qu'une vue alternative, rechargeable à tout moment (`make bo-refresh`).

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

    %% ── Package Python (src/reels_vault/) ────────────────────────
    subgraph SCRIPTS["🐍  src/reels_vault/ (.venv, via uv)"]
        REELS_TELEGRAM["reels-telegram\nrécupère les URLs du bot"]
        COLLECT["reels-collect\nrécolte + transcription\n(aucune dépendance LLM)"]
        DIGEST["reels-digest\ntags + résumé\n(Ollama local, une passe)"]
        PUBLISH["reels-publish\nrelit index.md → gallery.html"]
        GRAPH["reels-graph\najoute les liens Obsidian"]
    end

    %% ── Outils externes ───────────────────────────────────────────
    subgraph TOOLS["🔧  Outils externes"]
        YTDLP["yt-dlp\nmétadonnées + audio + vidéo"]
        WHISPER["faster-whisper\ntranscription locale"]
        GALLERYDL["gallery-dl\ncarrousels Instagram"]
        FFMPEG["ffmpeg\nextraction d'images"]
        OLLAMA["Ollama\nqwen2.5:7b (local)"]
    end

    %% ── Vault (stockage local) ────────────────────────────────────
    subgraph VAULT["📂  Vault/  (stockage local, source de vérité)"]
        RAW["raw/\nfiches .md brutes\n(1 fichier par vidéo)"]
        IMAGES["images/\ncaptures extraites"]
        INDEX["index.md\nrésumés + thèmes"]
        JOURNAL["journal.json\nsuivi des vidéos collectées"]
    end

    %% ── Backoffice (src/backoffice/) ───────────────────────────────
    subgraph BACKOFFICE["🗄️  src/backoffice/ (Next.js + Postgres, optionnel)"]
        SEED["scripts/seed.ts\nparse index.md + raw/*.md\ntruncate + reload"]
        POSTGRES[("Postgres\n(Docker Compose)")]
        BOAPI["Route Handlers\n/api/posts, /api/posts/:slug, /api/themes"]
        BOPAGE["Page Next.js\nrecherche + filtres par thème\n(lit Postgres en direct)"]
    end

    %% ── Consultation ──────────────────────────────────────────────
    subgraph OUTPUT["🖥️  Consultation"]
        GALLERY_HTML["gallery.html\nrecherche + filtres hors ligne"]
        OBSIDIAN["Obsidian\ngraphe des thèmes"]
        CLAUDE_QUERY["Claude (Desktop/Cowork)\nquestions en langage naturel"]
        GDRIVE["Google Drive\n+ app Claude mobile"]
        BOBROWSER["Navigateur\nhttp://localhost:3000"]
    end

    %% ── Flux principal ────────────────────────────────────────────

    %% Voie 1 : import en masse depuis l'export Instagram
    IG_EXPORT -->|"chemin du fichier"| COLLECT

    %% Voie 2 : envoi depuis le téléphone via Telegram
    IPHONE -->|"Partager → Envoyer au Vault\n(Raccourci iPhone)"| BOT
    BOT -->|"getUpdates API"| REELS_TELEGRAM
    REELS_TELEGRAM -->|"lit / met à jour"| OFFSET
    REELS_TELEGRAM -->|"URLs extraites\n(fichier temp)"| COLLECT

    %% Automatisation
    LAUNCHD -->|"déclenche"| INBOX_SH
    INBOX_SH -->|"appelle"| REELS_TELEGRAM

    %% reels-collect → outils
    COLLECT -->|"métadonnées"| YTDLP
    COLLECT -->|"audio .m4a"| WHISPER
    COLLECT -->|"carrousels /p/"| GALLERYDL
    COLLECT -->|"captures vidéo"| FFMPEG

    %% reels-collect → stockage
    YTDLP --> COLLECT
    WHISPER --> COLLECT
    GALLERYDL --> COLLECT
    FFMPEG --> COLLECT
    COLLECT -->|"écrit fiche .md (tags vides)"| RAW
    COLLECT -->|"sauve avancement"| JOURNAL
    FFMPEG -->|"images .jpg"| IMAGES

    %% Digest : tags + résumé, un seul passage par fiche, 100% local
    RAW -->|"lit les fiches brutes"| DIGEST
    DIGEST -->|"tags + résumé"| OLLAMA
    OLLAMA --> DIGEST
    DIGEST -->|"patche les tags"| RAW
    DIGEST -->|"ajoute une entrée"| INDEX

    %% Génération de la page web statique
    INDEX -->|"parse"| PUBLISH
    PUBLISH -->|"injecte JSON"| GALLERY_HTML

    %% Graphe Obsidian
    INDEX -->|"lit les thèmes"| GRAPH
    GRAPH -->|"ajoute liens [[Thème]]"| RAW
    RAW -->|"ouvre comme coffre"| OBSIDIAN

    %% Backoffice : même Vault, rechargé dans Postgres
    INDEX -->|"make bo-db-seed"| SEED
    RAW -->|"métadonnées + images"| SEED
    SEED -->|"DELETE puis INSERT (1 transaction)"| POSTGRES
    POSTGRES --> BOAPI
    POSTGRES --> BOPAGE
    IMAGES -.->|"symlink public/images"| BOPAGE
    BOAPI --> BOBROWSER
    BOPAGE --> BOBROWSER

    %% Consultation
    GALLERY_HTML -->|"double-clic Finder"| OUTPUT
    INDEX -->|"dépose sur Drive"| GDRIVE
    GALLERY_HTML -->|"dépose sur Drive"| GDRIVE
```

---

## Cycle de vie d'une vidéo

```mermaid
sequenceDiagram
    actor U as Utilisateur (iPhone)
    participant TG as Telegram Bot
    participant MAC as Mac (launchd 18h)
    participant TI as reels-telegram
    participant IN as reels-collect
    participant DG as reels-digest (Ollama local)
    participant GV as reels-publish
    participant BO as backoffice (make bo-refresh)

    U->>TG: Partager un Reel → "Envoyer au Vault"
    Note over TG: URL stockée côté Telegram<br/>même si le Mac est éteint

    MAC->>TI: inbox.sh (déclenchement quotidien)
    TI->>TG: getUpdates (offset)
    TG-->>TI: URLs en attente
    TI->>IN: fichier temporaire d'URLs
    IN->>IN: yt-dlp / whisper / ffmpeg
    IN-->>MAC: fiche .md dans Vault/raw/ (sans tags)
    TI->>MAC: met à jour telegram_offset.txt

    Note over MAC,GV: Digest tourne périodiquement (manuel,<br/>ou une 2e tâche launchd) — 100% local, sans quota Claude
    MAC->>DG: reels-digest --vault Vault
    DG->>DG: Ollama : tags + résumé, une passe par fiche
    DG-->>MAC: tags patchés dans raw/, entrées ajoutées à index.md
    MAC->>GV: reels-publish --vault Vault
    GV-->>MAC: Vault/gallery.html régénéré

    opt Backoffice installé (optionnel)
        MAC->>BO: make bo-refresh
        BO->>BO: reels-publish, puis scripts/seed.ts
        BO-->>MAC: Postgres à jour (truncate + reload)
    end

    U->>MAC: ouvre gallery.html (Finder)<br/>ou http://localhost:3000 (backoffice)
    Note over U,MAC: recherche instantanée,<br/>filtres par thème, hors ligne ou en direct sur Postgres
```

---

## Modèle de données — Backoffice (Postgres)

`src/backoffice/db/schema.ts` (Drizzle ORM). Rechargé en entier à chaque `make bo-db-seed` — `posts.id` est le slug dérivé de l'URL (`insta_<ID>`), stable d'un rechargement à l'autre.

```mermaid
erDiagram
    posts ||--o{ post_themes : "a des thèmes"
    themes ||--o{ post_themes : "regroupe des posts"
    posts ||--o{ post_images : "a jusqu'à 3 images"

    posts {
        text id PK "insta_<ID>, slug dérivé de l'URL"
        text source_url UK "lien Instagram"
        text platform
        text genre
        text author
        text author_handle
        double duration_s
        date processed_at
        text status
        text title
        text summary "= contenu de index.md"
        text description "caption brute"
        text transcript "null si non exploitable"
        int sort_order "ordre d'apparition dans index.md"
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
        text file_name "insta_<ID>_N.jpg"
    }
```

Servi par `lib/queries.ts` (utilisé à la fois par `app/page.tsx` et par les Route Handlers `app/api/*`), lui-même consommé par :

- **`GET /api/posts`** — liste paginée, filtrable par `theme`/`q`
- **`GET /api/posts/:slug`** — détail d'un post
- **`GET /api/themes`** — thèmes triés par nombre de posts

---

## Structure des fichiers

```
reels-vault/                     ← racine du projet
├── src/
│   ├── reels_vault/              ← package Python (une phase par module)
│   │   ├── collect.py            ← récolte + transcription (aucune dépendance LLM)
│   │   ├── digest.py             ← tags + résumé via Ollama local
│   │   ├── publish.py            ← index.md → gallery.html
│   │   ├── graph.py              ← index.md → liens Obsidian
│   │   ├── telegram.py           ← pont Telegram → collect
│   │   ├── _ollama.py            ← client Ollama partagé (collect n'en dépend pas)
│   │   └── _naming.py            ← dérivation du nom de fiche depuis une URL
│   │
│   └── backoffice/               ← Next.js + Postgres (optionnel, isolé du pipeline Python)
│       ├── app/                  ← pages (App Router) + Route Handlers /api/*
│       ├── components/           ← galerie, recherche, filtres par thème
│       ├── db/                   ← schema.ts (Drizzle) + client Postgres
│       ├── lib/queries.ts        ← requêtes partagées page + API
│       ├── scripts/seed.ts       ← recharge Vault/ dans Postgres
│       ├── drizzle/              ← migrations SQL générées
│       ├── docker-compose.yml    ← Postgres, port 5433
│       └── public/images         ← symlink vers ../../../Vault/images
│
├── pyproject.toml                ← dépendances + entry points reels-* (uv)
├── Makefile                      ← cibles Python (racine) + cibles bo-* (backoffice)
├── .env                          ← TOKEN + CHAT_ID (ignoré par git)
├── .env.example                  ← modèle à copier
├── .gitignore
│
└── Vault/                        ← données (ignoré par git, source de vérité des deux côtés)
    ├── raw/                      ← fiches .md brutes (1 par vidéo)
    ├── images/                   ← captures extraites des vidéos
    ├── themes/                   ← notes de thèmes pour Obsidian
    ├── index.md                  ← index résumé, écrit par Digest
    ├── gallery.html              ← page de consultation hors ligne (pipeline)
    ├── journal.json             ← vidéos déjà collectées
    └── telegram_offset.txt       ← dernier message Telegram lu
```
