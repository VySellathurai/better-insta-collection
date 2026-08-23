# Schéma du projet Reels Vault

## Vue d'ensemble du workflow

```mermaid
flowchart TD
    %% ── Sources d'entrée ──────────────────────────────────────────
    subgraph SOURCES["📥  Sources d'entrée"]
        IG_EXPORT["Export Instagram\nsaved_posts.json"]
        IPHONE["iPhone\nPartager un Reel / TikTok"]
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

    %% ── Scripts Python ────────────────────────────────────────────
    subgraph SCRIPTS["🐍  Scripts Python (.venv)"]
        TELEGRAM_INBOX["telegram_inbox.py\nrécupère les URLs du bot"]
        INGEST["ingest.py\nrécolte + transcription"]
        GENERATE["generate_vault.py\nrelit index.md → vault.html"]
        GRAPHE["graphe.py\najoute les liens Obsidian"]
    end

    %% ── Outils externes ───────────────────────────────────────────
    subgraph TOOLS["🔧  Outils externes"]
        YTDLP["yt-dlp\nmétadonnées + audio + vidéo"]
        WHISPER["faster-whisper\ntranscription locale"]
        GALLERYDL["gallery-dl\ncarrousels Instagram"]
        FFMPEG["ffmpeg\nextraction d'images"]
    end

    %% ── Vault (stockage local) ────────────────────────────────────
    subgraph VAULT["📂  Vault/  (stockage local)"]
        RAW["raw/\nfiches .md brutes\n(1 fichier par vidéo)"]
        IMAGES["images/\ncaptures extraites"]
        INDEX["index.md\nrésumés + thèmes"]
        JOURNAL["journal.json\nsuivi des vidéos traitées"]
        PROGRESSION["progression.txt\nsuivi de l'indexation Cowork"]
    end

    %% ── Consultation ──────────────────────────────────────────────
    subgraph OUTPUT["🖥️  Consultation"]
        VAULT_HTML["vault.html\nrecherche + filtres hors ligne"]
        OBSIDIAN["Obsidian\ngraphe des thèmes"]
        COWORK["Claude Cowork\nquestions en langage naturel"]
        GDRIVE["Google Drive\n+ app Claude mobile"]
    end

    %% ── Flux principal ────────────────────────────────────────────

    %% Voie 1 : import en masse depuis l'export Instagram
    IG_EXPORT -->|"chemin du fichier"| INGEST

    %% Voie 2 : envoi depuis le téléphone via Telegram
    IPHONE -->|"Partager → Envoyer au Vault\n(Raccourci iPhone)"| BOT
    BOT -->|"getUpdates API"| TELEGRAM_INBOX
    TELEGRAM_INBOX -->|"lit / met à jour"| OFFSET
    TELEGRAM_INBOX -->|"URLs extraites\n(fichier temp)"| INGEST

    %% Automatisation
    LAUNCHD -->|"déclenche"| INBOX_SH
    INBOX_SH -->|"appelle"| TELEGRAM_INBOX

    %% ingest.py → outils
    INGEST -->|"métadonnées"| YTDLP
    INGEST -->|"audio .m4a"| WHISPER
    INGEST -->|"carrousels /p/"| GALLERYDL
    INGEST -->|"captures vidéo"| FFMPEG

    %% ingest.py → stockage
    YTDLP --> INGEST
    WHISPER --> INGEST
    GALLERYDL --> INGEST
    FFMPEG --> INGEST
    INGEST -->|"écrit fiche .md"| RAW
    INGEST -->|"sauve avancement"| JOURNAL
    FFMPEG -->|"images .jpg"| IMAGES

    %% Indexation par Cowork (manuelle / tâche récurrente 8h)
    RAW -->|"lit les fiches brutes"| COWORK
    COWORK -->|"résumés + thèmes\n(lots de 25)"| INDEX
    COWORK -->|"met à jour"| PROGRESSION

    %% Génération de la page web
    INDEX -->|"parse"| GENERATE
    GENERATE -->|"injecte JSON"| VAULT_HTML

    %% Graphe Obsidian
    INDEX -->|"lit les thèmes"| GRAPHE
    GRAPHE -->|"ajoute liens [[Thème]]"| RAW
    RAW -->|"ouvre comme coffre"| OBSIDIAN

    %% Consultation
    VAULT_HTML -->|"double-clic Finder"| OUTPUT
    INDEX -->|"dépose sur Drive"| GDRIVE
    VAULT_HTML -->|"dépose sur Drive"| GDRIVE
```

---

## Cycle de vie d'une vidéo

```mermaid
sequenceDiagram
    actor U as Utilisateur (iPhone)
    participant TG as Telegram Bot
    participant MAC as Mac (launchd 18h)
    participant TI as telegram_inbox.py
    participant IN as ingest.py
    participant CW as Claude Cowork (8h)
    participant GV as generate_vault.py

    U->>TG: Partager un Reel → "Envoyer au Vault"
    Note over TG: URL stockée côté Telegram<br/>même si le Mac est éteint

    MAC->>TI: inbox.sh (déclenchement quotidien)
    TI->>TG: getUpdates (offset)
    TG-->>TI: URLs en attente
    TI->>IN: fichier temporaire d'URLs
    IN->>IN: yt-dlp / whisper / ffmpeg
    IN-->>MAC: fiche .md dans Vault/raw/
    TI->>MAC: met à jour telegram_offset.txt

    CW->>MAC: tâche récurrente 8h
    CW->>MAC: lit raw/, repère nouveautés
    CW->>MAC: résume → ajoute à index.md
    CW->>GV: déclenche generate_vault.py
    GV-->>MAC: Vault/vault.html régénéré

    U->>MAC: ouvre vault.html (Finder)
    Note over U,MAC: recherche instantanée,<br/>filtres par thème, hors ligne
```

---

## Structure des fichiers

```
reels-vault/                    ← racine du projet
├── ingest.py                   ← récolte + transcription
├── telegram_inbox.py           ← pont Telegram → ingest.py
├── generate_vault.py           ← index.md → vault.html
├── graphe.py                   ← index.md → liens Obsidian
├── requirements.txt            ← dépendances pip
├── .env                        ← TOKEN + CHAT_ID (ignoré par git)
├── .env.example                ← modèle à copier
├── .gitignore
│
└── Vault/                      ← données (ignoré par git)
    ├── raw/                    ← fiches .md brutes (1 par vidéo)
    ├── images/                 ← captures extraites des vidéos
    ├── themes/                 ← notes de thèmes pour Obsidian
    ├── index.md                ← index résumé par Cowork
    ├── vault.html              ← page de consultation hors ligne
    ├── journal.json            ← vidéos déjà traitées par ingest.py
    ├── progression.txt         ← dernière fiche indexée par Cowork
    └── telegram_offset.txt     ← dernier message Telegram lu
```
