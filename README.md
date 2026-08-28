# Transformer ses vidéos Instagram sauvegardées en base de données interrogeable

*Tuto complet, testé sur macOS (Sonoma/Sequoia). Zéro connaissance en code requise. Coût : 0 € si tu as déjà un abonnement Claude.*

---

## Le problème

Tu as des centaines de Reels sauvegardés. Des restos, des adresses, des astuces, des idées de voyage. Et tu ne retrouves jamais rien, parce que tout est enfermé dans des vidéos qu'aucune recherche ne peut lire.

À la fin de ce tuto, tu pourras demander en langage normal : *« je pars au Japon, sors-moi tout ce que j'ai gardé »* — et obtenir la liste, avec les adresses, les horaires et les prix.

Le principe : chaque vidéo est **collectée et transcrite**, ses **images extraites**, **enrichie** (résumée et catégorisée), puis **publiée directement dans une base de données** consultable depuis une page web (le backoffice). Et une fois le système en place, tu partages un Reel depuis ton téléphone et il s'ajoute tout seul pendant la nuit.

---

## Ce que ça coûte vraiment

Le montage d'origine (celui qui a tourné sur X) repose sur un agent nommé Hermes, branché à une clé API facturée au token, sur une machine allumée en permanence.

La version de ce tuto ne coûte **rien de plus** qu'un abonnement Claude Pro — et même sans lui, la collecte et la digestion tournent déjà à 0 € — parce qu'elle remplace chaque brique payante par un équivalent gratuit :

| Le montage d'origine | Ce qu'on utilise à la place | Coût |
|---|---|---|
| Hermes + clé API | **Ollama en local** (`qwen2.5:7b`) pour digérer les fiches | 0 € |
| Agent iMessage 24h/24 | **Un raccourci iPhone + une tâche planifiée (launchd)** | 0 € |
| Serveur allumé en permanence | **Ton Mac, quand il est allumé** | 0 € |
| Transcription par API | **Whisper en local** | 0 € |
| Téléchargement des vidéos | **yt-dlp** | 0 € |

**Le pipeline (collecte, transcription, extraction d'images, enrichissement) ne consomme aucun quota Claude** : tout tourne en local via Whisper et Ollama. Le seul moment où Claude entre en jeu, c'est quand tu **interroges** ta base en langage naturel (Étape 7) — et là, un abonnement Pro (voire le niveau gratuit, pour un usage occasionnel) suffit largement, puisque tu ne fais lire que les résumés condensés, jamais les transcriptions complètes.

---

## Ce qu'il te faut

- Un Mac (Apple Silicon ou Intel)
- Idéalement un abonnement **Claude Pro** (facultatif — seulement pour interroger ta base en langage naturel à l'Étape 7)
- **Homebrew**, le gestionnaire de paquets de macOS
- Un iPhone, pour la partie « envoyer depuis son téléphone » (facultatif)

---

## Installation rapide — tous les outils en une fois

Pressé·e ? Copie ce bloc, il installe tout d'un coup. Chaque outil est réexpliqué (pourquoi, comment vérifier qu'il marche) dans le tutoriel détaillé qui suit — reviens-y si quelque chose coince.

| Outil | Pour quoi | Obligatoire ? |
|---|---|---|
| Homebrew | installe tout le reste | Oui |
| ffmpeg | pipeline — extraction d'images | Oui |
| uv | fait tourner le projet Python | Oui |
| Firefox | pipeline — cookies Instagram | Oui |
| Ollama + `qwen2.5:7b` | pipeline — tags + résumé, en local | Oui |
| Node.js | Backoffice — app Next.js | Oui (c'est la page que tu consultes au quotidien) |
| Docker Desktop | Backoffice — base Postgres | Oui |

```
# Homebrew — si pas déjà installé
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Le pipeline : ffmpeg, le projet Python (uv), les cookies Instagram (Firefox), Ollama
brew install ffmpeg uv ollama
brew install --cask firefox
ollama pull qwen2.5:7b

# Le backoffice : Node.js + Docker (Postgres) — c'est ce que tu ouvres pour consulter ta base
brew install node
brew install --cask docker

# Le projet
cd "$HOME/Documents"
git clone https://github.com/TOI/reels-vault.git   # ou dézippe l'archive téléchargée
cd reels-vault
uv sync
```

Ensuite : ouvre Firefox et connecte-toi à Instagram (Étape 2), lance `ollama serve` avant de lancer le pipeline (Étape 4), et démarre Docker Desktop avant `make bo-setup` (Étape 5).

> **Des lignes rouges pendant `uv sync` ?** Souvent sans conséquence — relance `uv sync`, la deuxième tentative résout la plupart des soucis de cache.

Tout est installé et tu sais ce que tu fais ? Va directement à l'[Étape 2](#étape-2--se-connecter-à-instagram). Sinon, le tutoriel détaillé ci-dessous reprend chaque outil un par un, avec les vérifications.

---

## Étape 1 — Installer les outils

Ouvre **Terminal** (Cmd+Espace, tape « terminal », Entrée).

### 1.1 — Homebrew

Si Homebrew n'est pas déjà installé, colle ceci et suis les instructions à l'écran (il te demandera ton mot de passe Mac) :

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 1.2 — ffmpeg et uv

```
brew install ffmpeg uv
```

**uv** est le gestionnaire de projet Python utilisé ici — il installe Python et toutes les dépendances en une seule commande, sans que tu aies à créer ou activer un environnement virtuel à la main.

### 1.3 — Cloner le projet et installer les dépendances

Clone (ou télécharge) le projet quelque part de durable — pas dans Téléchargements, où il finira par disparaître :

```
cd "$HOME/Documents"
git clone https://github.com/TOI/reels-vault.git   # ou dézippe l'archive téléchargée
cd reels-vault
uv sync
```

`uv sync` télécharge Python si besoin, crée un `.venv` local et installe toutes les dépendances (`yt-dlp`, `faster-whisper`, `gallery-dl`, `requests`). **Toutes les commandes du reste de ce tuto se lancent avec `uv run …` depuis ce dossier** (`$HOME/Documents/reels-vault`) — pas besoin d'activer quoi que ce soit à la main.

> **Des lignes rouges pendant `uv sync` ?** C'est souvent sans conséquence. Si l'installation échoue franchement, relance `uv sync` — la deuxième tentative résout la plupart des soucis de cache.

### 1.4 — Vérification

```
uv run python -m yt_dlp --version
```

```
ffmpeg -version
```

Le premier affiche une date, le second un pavé de texte. Si l'un des deux échoue, l'installation n'est pas passée — reprends-la avant d'aller plus loin.

> **La première fois que tu lances `ffmpeg`, macOS peut afficher une alerte Gatekeeper** (« ne peut pas être ouvert car il provient d'un développeur non identifié »). Comme il vient de Homebrew, ce n'est normalement pas le cas — mais si ça arrive, va dans **Réglages Système → Confidentialité et sécurité** et clique sur « Ouvrir quand même ».

---

## Étape 2 — Se connecter à Instagram

yt-dlp a besoin d'emprunter le cookie de connexion de ton navigateur pour accéder aux Reels.

Sur macOS, **Chrome et Firefox fonctionnent tous les deux**, contrairement à Windows où Chrome est bloqué par un chiffrement (`DPAPI`) que yt-dlp ne sait pas déchiffrer. Ici, le seul inconvénient de Chrome est que **macOS demandera ton mot de passe de session (Trousseau d'accès) à chaque lecture des cookies** — gênant pour un script qui doit tourner seul la nuit.

**Recommandation : utilise Firefox**, qui ne stocke pas ses cookies dans le Trousseau et ne demande donc rien.

```
brew install --cask firefox
```

Ouvre Firefox, va sur **instagram.com**, connecte-toi, puis **ferme complètement Firefox** (Cmd+Q, pas juste la fenêtre) — macOS verrouille le fichier de cookies tant que le navigateur tourne.

Teste avant d'aller plus loin :

```
uv run python -m yt_dlp --cookies-from-browser firefox --dump-json --skip-download "https://www.instagram.com/reel/UN_REEL_QUELCONQUE/"
```

Un déluge de texte illisible = c'est gagné. Une erreur = inutile de continuer, il faut régler ça d'abord.

---

## Étape 3 — Récupérer ses liens

Sur Instagram : **Paramètres → Centre des comptes → Vos informations et autorisations → Télécharger vos informations**. Choisis le format **JSON**. Le fichier arrive par mail, parfois sous 48 h.

Dézippe-le, puis **déplace le dossier dans un endroit sûr** — pas dans Téléchargements, où il finira par disparaître.

Deux fichiers t'intéressent :

- `saved_posts.json` — tes posts sauvegardés
- `saved_collections.json` — tes posts rangés en collections

> Traite les deux, l'un après l'autre. Le pipeline vérifie dans la base ce qui a déjà été publié et ne retraitera jamais deux fois la même vidéo.

---

## Étape 4 — Lancer le pipeline

Une seule commande, `reels-pipeline`, fait tout le travail pour chaque lien, dans l'ordre :

1. récupère la description et les métadonnées via **yt-dlp**, télécharge l'audio et le transcrit en local avec **Whisper**
2. extrait trois images de la vidéo (ou télécharge les images du carrousel s'il n'y a pas de vidéo)
3. génère 3 tags de catégorisation et un résumé concret via un modèle **Ollama en local** (titre, auteur, thèmes, contenu) — **aucune consommation de quota Claude**
4. **publie directement le résultat dans Postgres** (voir [Étape 5](#étape-5--consulter-sa-base--le-backoffice) pour la consulter)

Avant de lancer le pipeline, la base doit exister — fais au moins une fois `make bo-setup` (voir l'étape suivante) pour démarrer Postgres et appliquer les migrations.

**Commence par 10 vidéos**, jamais par la totalité, depuis le dossier du projet :

```
cd "$HOME/Documents/reels-vault"
uv run reels-pipeline "CHEMIN/VERS/saved_posts.json" --vault "./Vault" --cookies firefox --limite 10
```

Le premier lancement télécharge le modèle Whisper (500 Mo, une seule fois) — plusieurs minutes de silence, c'est normal. `ollama serve` doit tourner en arrière-plan (lance-le une fois, il continue ensuite tout seul).

**Se limiter à une seule collection** (`saved_collections.json`, pas `saved_posts.json`) : `--collection "Comprendre"` filtre les liens sur cette collection au lieu de tous les traiter — `reels-collections` (ou `make collections`) liste les noms disponibles et leur nombre de liens.

> **Terminal te demande l'accès à un dossier (Téléchargements, Documents…) ?** C'est la protection « Accès complet au disque » / permissions par dossier de macOS. Autorise l'accès, sinon `reels-pipeline` ne pourra ni lire ton export ni écrire dans `Vault`. Tu peux gérer ça a posteriori dans **Réglages Système → Confidentialité et sécurité → Fichiers et dossiers**.

Ouvre ensuite le backoffice (Étape 5) et **lis le résumé généré pour une des premières vidéos**. C'est le moment décisif :

- **Il est riche et cohérent** → parfait, tout le contenu utile est dans le texte. Tu peux lancer la totalité.
- **Il est vide ou incohérent** → tes Reels sont sur musique de fond, l'information est dans le texte incrusté à l'image. Il faudra faire lire les images extraites par Claude, ce qui consomme beaucoup plus de quota.

Si le test est concluant, lance tout en retirant `--limite 10`. Compter **20 à 40 secondes par vidéo** : environ 1 h 30 pour 200 Reels. Tu peux couper avec `Ctrl+C` et relancer la même commande plus tard, il reprend où il s'était arrêté (les vidéos déjà publiées en base ne sont jamais retraitées).

> **Beaucoup d'échecs sur des liens en `/p/` ?** Ce sont des carrousels (des photos, pas des vidéos) : `gallery-dl` prend le relais, à condition de l'avoir installé à l'étape 1. Et si tes liens en échec commencent par `B5`, `B6`… ce sont des posts de 2019-2020, souvent supprimés depuis. Irrécupérables, et sans grande valeur.

> **Mac avec moins de 16 Go de RAM ?** `--llm-model qwen2.5:3b` (après `ollama pull qwen2.5:3b`) est nettement plus rapide, un peu moins précis sur les résumés longs.

**Ne décide pas des catégories à l'avance.** Le prompt d'enrichissement déduit les thèmes du contenu lui-même plutôt que de piocher dans une liste prédéfinie — tu découvres ce que tu sauvegardes réellement, et c'est rarement ce qu'on croit.

---

## Étape 5 — Consulter sa base : le backoffice

Le pipeline écrit directement dans une base **Postgres** (via Docker) ; le **backoffice**, une petite app **Next.js** dans `src/backoffice/`, la sert avec recherche instantanée, filtres par thème, galerie d'images, et une **API JSON en lecture seule** (`/api/posts`, `/api/posts/:slug`, `/api/themes`) si tu veux brancher un autre outil dessus un jour.

Installe **Node.js** et **Docker Desktop** (gratuits) si ce n'est pas déjà fait, puis lance Docker Desktop une fois pour qu'il tourne en arrière-plan.

```
brew install node
brew install --cask docker
```

Depuis la racine du projet, un seul démarrage suffit (installe les dépendances Node, démarre Postgres, applique les migrations) :

```
make bo-setup
```

Ensuite :

```
make bo-dev
```

Ouvre **http://localhost:3000**. Les nouvelles vidéos apparaissent dès que le pipeline (Étape 4) les a publiées — pas besoin de resynchroniser quoi que ce soit.

> `make bo-db-down` arrête Postgres quand tu as fini — tes données restent sur le disque (volume Docker), rien n'est perdu, `make bo-db-up` les retrouve au prochain démarrage.

---

## Étape 6 — Envoyer une vidéo depuis son téléphone

> ⚠️ `reels-telegram` a été porté vers la nouvelle structure du projet mais pas encore re-testé en conditions réelles. Vérifie qu'il fonctionne chez toi avant de compter dessus au quotidien.

L'idée : tu envoies le lien à un bot Telegram depuis ton téléphone. Quand ton Mac se réveille, il interroge le bot, récupère les URLs en attente et les collecte. Les liens s'accumulent côté Telegram même si ton Mac est éteint plusieurs jours — rien n'est perdu.

### 7.1 — Créer le bot Telegram (5 min, une seule fois)

Dans l'app Telegram, ouvre une conversation avec **@BotFather** et envoie :

```
/newbot
```

Suis les instructions, choisis un nom et un identifiant (ex. `monvault_bot`). BotFather te donne un **token** au format `123456789:ABCdef…` — **note-le**.

Envoie ensuite `/start` à ton nouveau bot pour l'initialiser.

### 7.2 — Récupérer ton chat_id

Depuis n'importe quel navigateur, remplace `<TON_TOKEN>` et ouvre cette URL :

```
https://api.telegram.org/bot<TON_TOKEN>/getUpdates
```

Dans la réponse JSON, trouve `"chat":{"id":XXXXXXXX}` — c'est ton **chat_id**. Si la réponse est vide (`"result":[]`), envoie d'abord un message quelconque à ton bot, puis recharge la page.

### 7.3 — Créer le fichier `.env`

```
cat > "$HOME/Documents/reels-vault/Vault/.env" << 'EOF'
TELEGRAM_TOKEN=REMPLACE_PAR_TON_TOKEN
TELEGRAM_CHAT_ID=REMPLACE_PAR_TON_CHAT_ID
EOF
```

**Remplace les deux valeurs** par ton vrai token et ton vrai chat_id. Ce fichier est lu par `reels-telegram` à chaque exécution.

> **Sécurité :** `.env` est listé dans `.gitignore` (via `Vault/`, entièrement ignoré) — il ne sera jamais poussé sur GitHub. Ne le déplace pas hors du Vault et ne le partage pas. Si le token fuite, régénère-le via `/revoke` chez @BotFather.

### 7.4 — Le raccourci iPhone

Dans l'app **Raccourcis** :

1. **+** en haut à droite
2. Ajoute l'action **« Obtenir le contenu de l'URL »**
3. Dans le champ URL, tape :
   ```
   https://api.telegram.org/bot<TON_TOKEN>/sendMessage
   ```
4. Passe la méthode en **POST**
5. Dans **Corps de la requête**, choisis **JSON** et ajoute deux champs :
   - `chat_id` → ta valeur de chat_id (nombre, sans guillemets)
   - `text` → la variable magique **Entrée du raccourci**
6. Ouvre les détails (**ⓘ**) → active **« Afficher dans la feuille de partage »**, type accepté : **URL**
7. Nomme-le **« Envoyer au Vault »**

À l'usage : sur un Reel, **Partager → Plus → Envoyer au Vault**.

Teste en envoyant un vrai lien depuis ton téléphone, puis vérifie sur Mac :

```
curl "https://api.telegram.org/bot<TON_TOKEN>/getUpdates"
```

Le lien doit apparaître dans `"text"` d'un message.

### 7.5 — L'automatisation

#### `inbox.sh`

Le script `inbox.sh`, à la racine du projet, appelle `reels-telegram` :

```
#!/bin/zsh
cd "$HOME/Documents/reels-vault"
source .venv/bin/activate
uv run reels-telegram --vault "./Vault" --cookies firefox
```

Rends-le exécutable une fois :

```
chmod +x "$HOME/Documents/reels-vault/inbox.sh"
```

#### Utiliser `inbox.sh` manuellement

Tu peux lancer la collecte à tout moment depuis le Terminal :

```
"$HOME/Documents/reels-vault/inbox.sh"
```

Le script affiche une ligne par URL traitée et indique le nombre de réussites/échecs à la fin. Si aucune nouvelle URL n'attend dans Telegram, il s'arrête immédiatement sans rien faire.

#### Automatiser avec launchd

Programme l'exécution tous les jours à 18h :

```
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$HOME/Library/LaunchAgents/com.vault.inbox.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.vault.inbox</string>
    <key>ProgramArguments</key>
    <array>
        <string>$HOME/Documents/reels-vault/inbox.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>18</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$HOME/Documents/reels-vault/inbox.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/Documents/reels-vault/inbox.log</string>
</dict>
</plist>
EOF
```

Puis charge-la :

```
launchctl load "$HOME/Library/LaunchAgents/com.vault.inbox.plist"
```

| Commande | Ce qu'elle fait |
|---|---|
| `launchctl load …plist` | Enregistre la tâche (à faire une seule fois) |
| `launchctl start com.vault.inbox` | Lance immédiatement, sans attendre 18h |
| `launchctl stop com.vault.inbox` | Arrête une exécution en cours |
| `launchctl unload …plist` | Désactive la tâche définitivement |

> `launchd` rattrape les exécutions manquées au prochain démarrage/réveil. Les liens envoyés quand le Mac est éteint ne sont pas perdus — ils attendent côté Telegram.

`reels-telegram` appelle `reels-pipeline` en interne pour chaque URL trouvée — collecte, transcription, images, enrichissement et publication en base se font en une seule passe, sans étape manuelle à relancer derrière.

**La boucle est bouclée** : tu partages depuis ton lit, ton Mac transcrit et publie le soir, la vidéo apparaît directement dans le backoffice au matin.

---

## Étape 7 — Interroger sa base

Ta base vit maintenant dans Postgres, servie par le backoffice (Étape 5) via une **API JSON en lecture seule** — plus de fichier `index.md` à faire lire directement à Claude. Deux façons d'interroger le contenu :

**Avec Claude Code**, depuis le dossier du projet, en laissant `make bo-dev` tourner dans un autre onglet : crée un fichier `CLAUDE.md` à la racine du projet pour qu'il sache où chercher :

```
- Ce projet gère une base de vidéos Instagram que j'ai sauvegardées, servie par
  le backoffice Next.js sur http://localhost:3000.
- Pour toute question sur mon contenu, interroge l'API en lecture seule :
  GET /api/posts?q=...&theme=...  et  GET /api/themes.
  Utilise q/theme pour filtrer côté serveur plutôt que de tout récupérer.
- Ne mentionne jamais un lieu, un titre ou un conseil qui ne vient pas d'un post
  renvoyé par l'API. Si je n'ai rien sur un sujet, dis-le simplement.
- Réponds en français.
```

Tu peux alors demander directement :

> Je pars 7 jours au Japon. Organise-moi un circuit avec tout ce que j'ai gardé — lieux, restaurants, adresses. Dis-moi ce que tu écartes et pourquoi.

> Qu'est-ce que je sauvegarde le plus sans jamais l'utiliser ?

> Ressors-moi les pâtisseries parisiennes, classées par arrondissement.

**Directement dans le backoffice**, sans passer par Claude : la recherche et les filtres par thème (http://localhost:3000) couvrent déjà la plupart des questions ponctuelles.

> **Ce qui change par rapport à l'ancienne version de ce tuto** : sans fichier statique (`index.md`/`gallery.html`) à déposer sur Google Drive, interroger sa base **depuis son téléphone** demande maintenant soit une session Claude Code à distance, soit d'ouvrir directement `http://localhost:3000` depuis le Mac. Si ce cas d'usage te manque, `GET /api/posts` reste une API HTTP classique — n'importe quel outil qui sait faire une requête peut la lire.

---

## Bonus — Collections Studio

Envie de ne relancer le pipeline que sur **une collection Instagram précise** (celles que tu t'es fabriquées dans l'app, pas tous tes posts sauvegardés d'un coup), avec un nombre de vidéos borné à chaque clic pour ne pas se faire repérer par Instagram ? `src/collections-studio/`, une autre petite app Next.js, ajoute cette UI par-dessus le même pipeline et la même base Postgres.

```
make cs-setup
make cs-dev
```

Ouvre **http://localhost:3100** — choisis une collection, clique, regarde les résultats apparaître au fur et à mesure. Détails dans `src/collections-studio/README.md`.

---

## Les cinq pièges, résumés

1. **Chrome demande le Trousseau d'accès à chaque lecture des cookies.** Gênant pour l'automatisation : utilise Firefox, plus simple pour un script qui tourne seul.
2. **Ferme complètement ton navigateur (Cmd+Q)** avant de lancer le script. macOS verrouille le fichier de cookies tant qu'il tourne.
3. **Ne partage jamais ton token Telegram.** Il donne le contrôle total de ton bot. Ne le mets pas dans un dépôt Git. Si tu le perds ou le divulgues, régénère-le via `/revoke` chez BotFather.
4. **`launchd` ne réveille pas ton Mac tout seul.** Programme un réveil automatique si l'heure prévue tombe pendant que le Mac dort.
5. **Range ton export ailleurs que dans Téléchargements.** Il finira supprimé au pire moment.

---

## Les limites, en toute franchise

**Ce n'est pas de la magie, c'est de la transcription.** Si tes Reels n'ont pas de voix off, il n'y aura pas grand-chose à extraire — vérifie sur 10 vidéos avant d'en lancer 300.

**L'enrichissement (étape 3 du pipeline) dépend de la puissance de ton Mac, pas d'un quota.** Un gros lot (des milliers de vidéos) prendra simplement plus longtemps en local — bascule sur `qwen2.5:3b` si c'est trop lent. Les quotas Claude n'entrent en jeu qu'à l'Étape 7, pour interroger les résumés déjà condensés.

**Instagram limite le rythme.** Sur plusieurs centaines de posts, mieux vaut procéder par lots de 50 étalés sur quelques jours.

**Une partie du contenu est irrécupérable.** Les posts supprimés ou passés en privé depuis que tu les avais enregistrés sont perdus. Sur un stock ancien, compte facilement un tiers de pertes.

---

## Le pipeline, en bref

| Étape | Commande | Outils | Ce qu'elle fait |
|---|---|---|---|
| **1· collect** | `reels-pipeline` | yt-dlp, Whisper | Métadonnées + audio + transcription |
| **2· images** | `reels-pipeline` | ffmpeg, gallery-dl | 3 captures vidéo (ou carrousel) |
| **3· enrich** | `reels-pipeline` | Ollama (`qwen2.5:7b`) | Tags + résumé |
| **4· publish** | `reels-pipeline` | asyncpg | Upsert asynchrone dans Postgres |
| **Telegram** *(déclencheur)* | `reels-telegram` | API Telegram | Récupère les URLs, appelle le pipeline |
| **Backoffice** | `make bo-setup` / `make bo-dev` | Next.js, Postgres, Docker | Page web + API JSON en lecture seule |
| **Collections Studio** *(bonus)* | `make cs-setup` / `make cs-dev` | Next.js | Pipeline scopé à une collection, UI dédiée |

> ⚠️ **Le pipeline (`reels-pipeline`) est testé sur une base réelle.** Telegram a été porté vers la nouvelle structure du projet mais **pas encore vérifié en conditions réelles** depuis — teste-le prudemment (petit lot, base de test) avant de t'y fier.

Voir `schema.md` pour le détail du flux complet (diagrammes, modèle de données Postgres).

## Les fichiers

- **`src/reels_pipeline/collect.py`** / **`extract_images.py`** / **`enrich.py`** — les 3 premières étapes
- **`src/reels_pipeline/publish.py`** — étape 4 : upsert asynchrone dans Postgres
- **`src/reels_pipeline/cli.py`** — l'orchestrateur async, point d'entrée `reels-pipeline`
- **`src/reels_pipeline/telegram.py`** — récupère les URLs depuis le bot Telegram et appelle le pipeline
- **`src/reels_pipeline/_ollama.py`** / **`_naming.py`** — code partagé entre les étapes
- **`src/backoffice/`** — backoffice (Next.js + Postgres) ; voir `src/backoffice/README.md` pour le détail
- **`src/collections-studio/`** — pipeline scopé à une collection (bonus) ; voir `src/collections-studio/README.md`
- **`pyproject.toml`** — dépendances et commandes `reels-*` (`uv sync` pour installer)
- **`.env.example`** — modèle du fichier de configuration Telegram (copier en `Vault/.env` et remplir)

*Tuto rédigé après un montage réel, du premier `brew install` jusqu'au circuit de voyage. Les pièges décrits ont tous été rencontrés pour de vrai.*

## Commandes utiles

- **`make install`** — installe les dépendances Python
- **`make pipeline FILE=liens.txt [COOKIES=firefox] [LIMIT=20] [COLLECTION=Comprendre] [DRY_RUN=1]`** — lance le pipeline sur un fichier de liens
- **`make collections [FILE=saved_collections.json]`** — liste les collections disponibles et leur nombre de liens
- **`make telegram`** — lance le bot Telegram (équivalent de `inbox.sh`)
- **`make check`** — lint + typecheck (identique à la CI)

Backoffice (`src/backoffice/`) :

- **`make bo-setup`** — première installation : dépendances, Postgres, migrations
- **`make bo-dev`** — lance le backoffice sur http://localhost:3000
- **`make bo-db-up`** / **`make bo-db-down`** — démarre / arrête Postgres (Docker)
- **`make bo-check`** — lint + typecheck du backoffice

Collections Studio (`src/collections-studio/`, bonus) :

- **`make cs-setup`** — première installation : dépendances, symlink images
- **`make cs-dev`** — lance Collections Studio sur http://localhost:3100

`make help` liste toutes les commandes disponibles, avec leurs variables.
