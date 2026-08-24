# Transformer ses vidéos Instagram sauvegardées en base de données interrogeable

*Tuto complet, testé sur macOS (Sonoma/Sequoia). Zéro connaissance en code requise. Coût : 0 € si tu as déjà un abonnement Claude.*

---

## Le problème

Tu as des centaines de Reels sauvegardés. Des restos, des adresses, des astuces, des idées de voyage. Et tu ne retrouves jamais rien, parce que tout est enfermé dans des vidéos qu'aucune recherche ne peut lire.

À la fin de ce tuto, tu pourras demander en langage normal : *« je pars au Japon, sors-moi tout ce que j'ai gardé »* — et obtenir la liste, avec les adresses, les horaires et les prix.

Le principe : chaque vidéo est **collectée** (téléchargée et transcrite), **digérée** (résumée et catégorisée), puis **publiée** dans une page consultable hors ligne. Et une fois le système en place, tu partages un Reel depuis ton téléphone et il s'ajoute tout seul pendant la nuit.

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

**La collecte et la digestion (Collect + Digest) ne consomment aucun quota Claude** : tout tourne en local via Whisper et Ollama. Le seul moment où Claude entre en jeu, c'est quand tu **interroges** ta base en langage naturel (Étape 8) — et là, un abonnement Pro (voire le niveau gratuit, pour un usage occasionnel) suffit largement, puisque tu ne fais lire que l'index condensé, jamais les centaines de fiches brutes.

---

## Ce qu'il te faut

- Un Mac (Apple Silicon ou Intel)
- Idéalement un abonnement **Claude Pro** (facultatif — seulement pour interroger ta base en langage naturel à l'Étape 8)
- **Homebrew**, le gestionnaire de paquets de macOS
- Un iPhone, pour la partie « envoyer depuis son téléphone » (facultatif)

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

> Traite les deux, l'un après l'autre. Collect tient un journal et ne retraitera jamais deux fois la même vidéo.

---

## Étape 4 — Collect : la récolte

C'est la phase purement mécanique du pipeline — **aucune dépendance à un LLM**. Pour chaque lien :

1. récupère la description et les métadonnées via **yt-dlp**
2. télécharge l'audio et le transcrit en local avec **Whisper**
3. extrait trois images de la vidéo
4. écrit une fiche Markdown dans `Vault/raw/` (tags vides pour l'instant — Digest s'en charge à l'étape suivante)
5. note son avancement dans `Vault/journal.json`, pour pouvoir reprendre après une interruption

**Commence par 10 vidéos**, jamais par la totalité, depuis le dossier du projet :

```
cd "$HOME/Documents/reels-vault"
uv run reels-collect "CHEMIN/VERS/saved_posts.json" --vault "./Vault" --cookies firefox --limite 10
```

Le premier lancement télécharge le modèle Whisper (500 Mo, une seule fois) — plusieurs minutes de silence, c'est normal.

> **Terminal te demande l'accès à un dossier (Téléchargements, Documents…) ?** C'est la protection « Accès complet au disque » / permissions par dossier de macOS. Autorise l'accès, sinon `reels-collect` ne pourra ni lire ton export ni écrire dans `Vault`. Tu peux gérer ça a posteriori dans **Réglages Système → Confidentialité et sécurité → Fichiers et dossiers**.

Ouvre ensuite une fiche dans `Vault/raw/` et **lis la section « Transcription audio »**. C'est le moment décisif :

- **Elle est riche et cohérente** → parfait, tout le contenu utile est dans le texte. Tu peux lancer la totalité.
- **Elle est vide ou incompréhensible** → tes Reels sont sur musique de fond, l'information est dans le texte incrusté à l'image. Il faudra faire lire les images extraites par Claude, ce qui consomme beaucoup plus de quota.

Si le test est concluant, lance tout en retirant `--limite 10`. Compter **20 à 40 secondes par vidéo** : environ 1 h 30 pour 200 Reels. Tu peux couper avec `Ctrl+C` et relancer la même commande plus tard, il reprend où il s'était arrêté.

> **Beaucoup d'échecs sur des liens en `/p/` ?** Ce sont des carrousels (des photos, pas des vidéos) : `gallery-dl` prend le relais, à condition de l'avoir installé à l'étape 1. Et si tes liens en échec commencent par `B5`, `B6`… ce sont des posts de 2019-2020, souvent supprimés depuis. Irrécupérables, et sans grande valeur.

---

## Étape 5 — Digest : tags et résumé (Ollama, en local)

À ce stade, tu as des centaines de fiches brutes, longues et brouillonnes, sans tags. Digest les condense automatiquement, **en local, sans consommer une miette de quota Claude** : pour chaque fiche, un modèle Ollama génère 3 tags de catégorisation et un résumé concret (titre, auteur, thèmes, contenu), patche les tags dans la fiche brute, et ajoute une entrée dans `index.md`.

Installe Ollama et le modèle par défaut :

```
brew install ollama
ollama pull qwen2.5:7b
ollama serve
```

`ollama serve` doit rester actif — laisse cet onglet Terminal ouvert (ou lance-le une fois, il tourne ensuite en arrière-plan).

Dans un **nouvel** onglet Terminal :

```
cd "$HOME/Documents/reels-vault"
uv run reels-digest --vault "./Vault" --batch 25
```

Chaque lancement traite jusqu'à 25 fiches (`--batch`) et **reprend automatiquement là où il s'est arrêté** — relance la même commande pour continuer jusqu'à ce qu'il n'y ait plus rien à faire. `--dry-run` affiche combien de fiches restent, sans rien écrire.

> **Mac avec moins de 16 Go de RAM ?** `--llm-model qwen2.5:3b` (après `ollama pull qwen2.5:3b`) est nettement plus rapide, un peu moins précis sur les résumés longs.

**Pourquoi un index plutôt que d'interroger les fiches brutes ?** Parce que faire relire des centaines de fiches complètes à chaque question épuiserait ton quota Claude en trois requêtes. L'index tient dans une fraction de la place et suffit à 90 % des questions.

**Ne décide pas des catégories à l'avance.** Le prompt de Digest déduit les thèmes du contenu lui-même plutôt que de piocher dans une liste prédéfinie — tu découvres ce que tu sauvegardes réellement, et c'est rarement ce qu'on croit.

---

## Étape 6 — Publish : une page pour consulter

`reels-publish` lit `Vault/index.md` et écrit `Vault/gallery.html` : une page autonome avec recherche instantanée, filtres par thème, galerie d'images et liens cliquables, qui fonctionne hors ligne et sans consommer une miette de quota.

Lance-le depuis le Terminal :

```
cd "$HOME/Documents/reels-vault"
uv run reels-publish --vault "./Vault"
```

Il affiche le nombre d'entrées générées et le chemin de sortie :

```
gallery.html regenere avec 247 entrees -> /Users/toi/Documents/reels-vault/Vault/gallery.html
```

Ouvre ensuite `Vault/gallery.html` d'un double-clic dans le Finder. **C'est ce que tu utiliseras au quotidien.**

> À chaque fois que `index.md` change (après une session Digest), relance `uv run reels-publish --vault "./Vault"` pour regénérer la page — ou enchaîne les deux commandes à la suite dans le même terminal.

---

## Étape 7 — Envoyer une vidéo depuis son téléphone

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

**Digest et Publish restent des étapes à part** — inbox.sh ne fait que collecter. Relance-les à la main quand tu veux mettre ta base à jour :

```
uv run reels-digest --vault "./Vault" && uv run reels-publish --vault "./Vault"
```

Comme elles ne consomment aucun quota Claude et tournent en quelques secondes à minutes, tu peux aussi dupliquer le `.plist` ci-dessus (avec un `Label` différent et un script qui enchaîne ces deux commandes) si tu veux que toute la chaîne tourne sans y penser.

**La boucle est bouclée** : tu partages depuis ton lit, ton Mac transcrit le soir, l'index se met à jour quand tu relances Digest.

---

## Étape 8 — Interroger sa base

Crée un fichier `CLAUDE.md` à la racine du Vault. Claude le lit automatiquement au début de chaque session :

```
- Ce dossier est une base de vidéos Instagram que j'ai sauvegardées.
- Pour toute question sur mon contenu, commence TOUJOURS par lire index.md.
- N'ouvre les fiches complètes de raw/ que si index.md ne suffit pas.
- Ne mentionne jamais un lieu, un titre ou un conseil qui ne vient pas de mes
  fiches. Si je n'ai rien sur un sujet, dis-le simplement.
- Après toute modification de index.md, régénère gallery.html
  (uv run reels-publish --vault ./Vault).
- Réponds en français.
```

Tu peux alors demander directement :

> Je pars 7 jours au Japon. Organise-moi un circuit avec tout ce que j'ai gardé — lieux, restaurants, adresses. Dis-moi ce que tu écartes et pourquoi.

> Qu'est-ce que je sauvegarde le plus sans jamais l'utiliser ?

> Ressors-moi les pâtisseries parisiennes, classées par arrondissement.

**Depuis ton téléphone** : dépose `index.md` et `gallery.html` sur Google Drive, et interroge-les depuis l'app Claude avec le connecteur Drive activé.

---

## Bonus — La carte du graphe

C'est l'image qui a fait circuler le projet : un nuage de points reliés, chaque point une vidéo, chaque gros nœud un thème.

Installe **Obsidian** (gratuit) :

```
brew install --cask obsidian
```

Au lancement, choisis **« Ouvrir un dossier comme coffre »** et sélectionne ton `Vault` — pas le coffre de démonstration créé par défaut.

Lance ensuite `reels-graph`, qui ajoute les liens `[[Thème]]` à chaque fiche et crée une note par thème :

```
cd "$HOME/Documents/reels-vault"
uv run reels-graph --vault "./Vault"
```

Puis `Cmd+G` dans Obsidian. Monte **Repel** dans les réglages « Forces » pour aérer, et crée un groupe `path:themes` en couleur vive pour faire ressortir les thèmes.

**Sois honnête avec toi-même** : c'est superbe, ça fait un excellent visuel, mais on s'en sert peu au quotidien. La page `gallery.html` avec ses filtres est bien plus efficace pour retrouver quelque chose. Le graphe, c'est l'affiche du projet.

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

**Digest dépend de la puissance de ton Mac, pas d'un quota.** Un gros lot (des milliers de fiches) prendra simplement plus longtemps en local — bascule sur `qwen2.5:3b` si c'est trop lent. Les quotas Claude n'entrent en jeu qu'à l'Étape 8, pour interroger l'index déjà condensé.

**Instagram limite le rythme.** Sur plusieurs centaines de posts, mieux vaut procéder par lots de 50 étalés sur quelques jours.

**Une partie du contenu est irrécupérable.** Les posts supprimés ou passés en privé depuis que tu les avais enregistrés sont perdus. Sur un stock ancien, compte facilement un tiers de pertes.

---

## Le pipeline, en bref

| Phase | Commande | Ce qu'elle fait |
|---|---|---|
| **Collect** | `reels-collect` | Télécharge, transcrit, capture des images — aucune dépendance LLM |
| **Digest** | `reels-digest` | Tags + résumé par fiche, via Ollama en local |
| **Publish** | `reels-publish` | `index.md` → `gallery.html`, la page de consultation |
| **Graph** *(bonus)* | `reels-graph` | Ajoute les liens `[[Thème]]` pour Obsidian |
| **Telegram** *(déclencheur)* | `reels-telegram` | Récupère les URLs du bot et appelle Collect |

Voir `schema.md` pour le détail du flux complet (diagrammes).

## Les fichiers

- **`src/reels_vault/collect.py`** — récolte et transcription
- **`src/reels_vault/digest.py`** — tags et résumé (Ollama)
- **`src/reels_vault/publish.py`** — relit `Vault/index.md` et régénère `Vault/gallery.html`
- **`src/reels_vault/graph.py`** — création des liens pour Obsidian
- **`src/reels_vault/telegram.py`** — récupère les URLs depuis le bot Telegram et appelle Collect
- **`src/reels_vault/_ollama.py`** / **`_naming.py`** — code partagé entre les phases
- **`pyproject.toml`** — dépendances et commandes `reels-*` (`uv sync` pour installer)
- **`.env.example`** — modèle du fichier de configuration Telegram (copier en `Vault/.env` et remplir)

*Tuto rédigé après un montage réel, du premier `brew install` jusqu'au circuit de voyage. Les pièges décrits ont tous été rencontrés pour de vrai.*

## Commandes utiles

- **`make install`** — installe les dépendances Python
- **`make collect FILE=liens.txt [COOKIES=firefox] [LIMITE=20]`** — lance Collect sur un fichier de liens
- **`make digest [LLM_MODEL=qwen2.5:7b] [BATCH=25]`** — lance Digest (tags + résumé)
- **`make digest-dry`** — aperçu de Digest, sans écriture
- **`make publish`** — régénère `gallery.html`
- **`make graph`** — crée les liens Obsidian
- **`make telegram`** — lance le bot Telegram (équivalent de `inbox.sh`)
- **`make check`** — lint + typecheck (identique à la CI)
