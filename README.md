# Transformer ses vidéos Instagram sauvegardées en base de données interrogeable

*Tuto complet, testé sur macOS (Sonoma/Sequoia). Zéro connaissance en code requise. Coût : 0 € si tu as déjà un abonnement Claude.*

---

## Le problème

Tu as des centaines de Reels sauvegardés. Des restos, des adresses, des astuces, des idées de voyage. Et tu ne retrouves jamais rien, parce que tout est enfermé dans des vidéos qu'aucune recherche ne peut lire.

À la fin de ce tuto, tu pourras demander en langage normal : *« je pars au Japon, sors-moi tout ce que j'ai gardé »* — et obtenir la liste, avec les adresses, les horaires et les prix.

Le principe : chaque vidéo est **téléchargée, transcrite et résumée**, puis rangée dans une base de fichiers texte. Et une fois le système en place, tu partages un Reel depuis ton téléphone et il s'ajoute tout seul pendant la nuit.

---

## Ce que ça coûte vraiment

Le montage d'origine (celui qui a tourné sur X) repose sur un agent nommé Hermes, branché à une clé API facturée au token, sur une machine allumée en permanence.

La version de ce tuto ne coûte **rien de plus** qu'un abonnement Claude Pro, parce qu'elle remplace chaque brique payante par un équivalent gratuit :

| Le montage d'origine | Ce qu'on utilise à la place | Coût |
|---|---|---|
| Hermes + clé API | **Claude Cowork** (inclus dans Pro) | 0 € |
| Agent iMessage 24h/24 | **Un raccourci iPhone + une tâche planifiée (launchd)** | 0 € |
| Serveur allumé en permanence | **Ton Mac, quand il est allumé** | 0 € |
| Transcription par API | **Whisper en local** | 0 € |
| Téléchargement des vidéos | **yt-dlp** | 0 € |

**La seule vraie limite** : les quotas d'usage de Claude. Compter quelques centaines de vidéos par session confortablement. Traiter 10 000 vidéos d'un coup n'est pas réaliste sur un abonnement Pro — mais 300 fiches bien rangées servent davantage que 10 000 en vrac.

---

## Ce qu'il te faut

- Un Mac (Apple Silicon ou Intel)
- Un abonnement **Claude Pro**
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

### 1.2 — Python et ffmpeg

```
brew install python@3.12 ffmpeg
```

### 1.3 — Environnement virtuel et paquets Python

Un environnement virtuel isole les dépendances du projet — ça évite les conflits avec d'autres outils installés sur ton Mac. C'est la manière recommandée depuis Python 3.12.

```
mkdir -p "$HOME/Vault"
cd "$HOME/Vault"
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **`(venv)` s'affiche dans ton Terminal ?** C'est normal — ça signifie que l'environnement virtuel est actif. **Tu devras relancer `source "$HOME/Vault/.venv/bin/activate"` à chaque nouvelle session Terminal** avant d'utiliser les scripts.

> **Des lignes rouges pendant `pip install` ?** C'est souvent sans conséquence. Tant que tu lis `Successfully installed` à la fin, tout va bien. Si l'installation échoue, essaie `pip install --upgrade pip` puis relance.

### 1.4 — Vérification

```
python3 -m yt_dlp --version
```

```
ffmpeg -version
```

Le premier affiche une date, le second un pavé de texte. Si l'un des deux dit « command not found », l'installation n'est pas passée — reprends-la avant d'aller plus loin.

> **La première fois que tu lances `ffmpeg` ou `python3`, macOS peut afficher une alerte Gatekeeper** (« ne peut pas être ouvert car il provient d'un développeur non identifié »). Comme ils viennent de Homebrew, ce n'est normalement pas le cas — mais si ça arrive, va dans **Réglages Système → Confidentialité et sécurité** et clique sur « Ouvrir quand même ».

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
python3 -m yt_dlp --cookies-from-browser firefox --dump-json --skip-download "https://www.instagram.com/reel/UN_REEL_QUELCONQUE/"
```

Un déluge de texte illisible = c'est gagné. Une erreur = inutile de continuer, il faut régler ça d'abord.

---

## Étape 3 — Récupérer ses liens

Sur Instagram : **Paramètres → Centre des comptes → Vos informations et autorisations → Télécharger vos informations**. Choisis le format **JSON**. Le fichier arrive par mail, parfois sous 48 h.

Dézippe-le, puis **déplace le dossier dans un endroit sûr** — pas dans Téléchargements, où il finira par disparaître.

Deux fichiers t'intéressent :

- `saved_posts.json` — tes posts sauvegardés
- `saved_collections.json` — tes posts rangés en collections

> Traite les deux, l'un après l'autre. Le script tient un journal et ne retraitera jamais deux fois la même vidéo.

---

## Étape 4 — Le script de récolte

Crée un dossier `Vault` dans ton dossier personnel et places-y **`ingest.py`** (lien de téléchargement en bas de page).

Ce qu'il fait, pour chaque lien :

1. récupère la description et les métadonnées via **yt-dlp**
2. télécharge l'audio et le transcrit en local avec **Whisper**
3. extrait trois images de la vidéo
4. écrit une fiche Markdown dans `raw/`
5. note son avancement, pour pouvoir reprendre après une interruption

**Commence par 10 vidéos**, jamais par la totalité :

```
cd "$HOME/Vault"
source .venv/bin/activate
```

```
python3 ingest.py "CHEMIN/VERS/saved_posts.json" --vault "$HOME/Vault" --cookies firefox --limite 10
```

Le premier lancement télécharge le modèle Whisper (500 Mo, une seule fois) — plusieurs minutes de silence, c'est normal.

> **Terminal te demande l'accès à un dossier (Téléchargements, Documents…) ?** C'est la protection « Accès complet au disque » / permissions par dossier de macOS. Autorise l'accès, sinon `ingest.py` ne pourra ni lire ton export ni écrire dans `Vault`. Tu peux gérer ça a posteriori dans **Réglages Système → Confidentialité et sécurité → Fichiers et dossiers**.

Ouvre ensuite une fiche dans `raw/` et **lis la section « Transcription audio »**. C'est le moment décisif :

- **Elle est riche et cohérente** → parfait, tout le contenu utile est dans le texte. Tu peux lancer la totalité.
- **Elle est vide ou incompréhensible** → tes Reels sont sur musique de fond, l'information est dans le texte incrusté à l'image. Il faudra faire lire les images extraites par Claude, ce qui consomme beaucoup plus de quota.

Si le test est concluant, lance tout en retirant `--limite 10`. Compter **20 à 40 secondes par vidéo** : environ 1 h 30 pour 200 Reels. Tu peux couper avec `Ctrl+C` et relancer la même commande plus tard, il reprend où il s'était arrêté.

> **Beaucoup d'échecs sur des liens en `/p/` ?** Ce sont des carrousels (des photos, pas des vidéos) : `gallery-dl` prend le relais, à condition de l'avoir installé à l'étape 1. Et si tes liens en échec commencent par `B5`, `B6`… ce sont des posts de 2019-2020, souvent supprimés depuis. Irrécupérables, et sans grande valeur.

---

## Étape 5 — Transformer les transcriptions en index

À ce stade, tu as des centaines de fiches brutes, longues et brouillonnes. Il faut les condenser.

Installe **Claude Desktop** depuis **claude.ai/download** (choisis la version macOS) — surtout pas depuis l'App Store, les versions tierces ne gèrent pas Cowork correctement. Cowork sur Mac s'appuie sur le framework de virtualisation natif d'Apple : il n'y a **aucune fonctionnalité système à activer manuellement** (contrairement à Windows, où il faut activer « Plateforme de machine virtuelle »). Si Cowork refuse de démarrer, vérifie simplement que Claude Desktop est à jour et que macOS l'autorise dans **Réglages Système → Confidentialité et sécurité**.

Ouvre Cowork, donne-lui le dossier `Vault`, et colle cette consigne :

```
Tu travailles dans le dossier de mon Vault.

Objectif : construire un index consultable de mes vidéos Instagram sauvegardées.

Le dossier `raw` contient une fiche .md par vidéo, avec sa source, son auteur,
sa description et la transcription de l'audio.

Travaille par lots de 25 fiches. Pour chaque fiche :
- résume en 2 à 4 lignes ce qu'elle apporte CONCRÈTEMENT : les noms cités, les
  titres recommandés, les lieux, les adresses, les prix, les horaires. Surtout
  pas de généralité du type "cette vidéo parle de productivité".
- attribue 1 à 3 thèmes. N'utilise aucune liste prédéfinie : déduis les thèmes
  de ce que tu lis, et réutilise les mêmes libellés d'une fiche à l'autre pour
  rester cohérent.
- si une fiche est trop pauvre pour un vrai résumé, signale-le plutôt que
  d'inventer.

Écris le résultat dans `index.md`, en AJOUTANT à la fin à chaque lot (ne réécris
jamais le fichier entier). Format de chaque entrée :

### <titre court et parlant>
- lien : <url>
- auteur : <auteur>
- thèmes : <thème1>, <thème2>
- contenu : <le résumé concret>

Tiens à jour un fichier `progression.txt` avec le nom de la dernière fiche
traitée, pour pouvoir reprendre plus tard.

Fais le premier lot de 25, puis arrête-toi et dis-moi combien il en reste.
```

Réponds ensuite **« continue »** à la fin de chaque lot. Compter une dizaine de lots pour 250 fiches. Si tu atteins ta limite d'usage, attends la réouverture et écris « reprends l'indexation à partir de progression.txt ».

**Pourquoi un index plutôt que d'interroger les fiches brutes ?** Parce que faire relire 250 fiches complètes à chaque question épuiserait ton quota en trois requêtes. L'index tient dans une fraction de la place et suffit à 90 % des questions.

**Ne décide pas des catégories à l'avance.** En laissant Claude les déduire, tu découvres ce que tu sauvegardes réellement — et c'est rarement ce qu'on croit.

---

## Étape 6 — Une page pour consulter

Le script **`generate_vault.py`** (à la racine du projet) lit `Vault/index.md` et écrit `Vault/vault.html` : une page autonome avec recherche instantanée, filtres par thème et liens cliquables, qui fonctionne hors ligne et sans consommer une miette de quota.

Lance-le depuis le Terminal :

```
cd "$HOME/Documents/reels-vault"   # ou le dossier où tu as cloné le projet
source Vault/.venv/bin/activate 2>/dev/null || source .venv/bin/activate
python3 generate_vault.py
```

Il affiche le nombre d'entrées générées et le chemin de sortie :

```
vault.html regenere avec 247 entrees -> /Users/toi/Documents/reels-vault/Vault/vault.html
```

Ouvre ensuite `Vault/vault.html` d'un double-clic dans le Finder. **C'est ce que tu utiliseras au quotidien.**

> À chaque fois que `index.md` est mis à jour (après une session d'indexation dans Cowork), relance `python3 generate_vault.py` pour regénérer la page. Tu peux aussi demander à Cowork de le faire automatiquement :

```
Après toute modification de index.md, exécute generate_vault.py pour régénérer vault.html.
```

---

## Étape 7 — Envoyer une vidéo depuis son téléphone

L'idée : tu envoies le lien à un bot Telegram depuis ton téléphone. Quand ton Mac se réveille, il interroge le bot, récupère les URLs en attente et les ingère. Les liens s'accumulent côté Telegram même si ton Mac est éteint plusieurs jours — rien n'est perdu.

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
cat > "$HOME/Vault/.env" << 'EOF'
TELEGRAM_TOKEN=REMPLACE_PAR_TON_TOKEN
TELEGRAM_CHAT_ID=REMPLACE_PAR_TON_CHAT_ID
EOF
```

**Remplace les deux valeurs** par ton vrai token et ton vrai chat_id. Ce fichier est lu par `telegram_inbox.py` à chaque exécution.

> **Sécurité :** `.env` est listé dans `.gitignore` — il ne sera jamais poussé sur GitHub. Ne le déplace pas hors du Vault et ne le partage pas. Si le token fuite, régénère-le via `/revoke` chez @BotFather.

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

À l'usage : sur un Reel, **Partager → Plus → Envoyer au Vault**. Ça marche aussi depuis TikTok sans rien changer.

Teste en envoyant un vrai lien depuis ton téléphone, puis vérifie sur Mac :

```
curl "https://api.telegram.org/bot<TON_TOKEN>/getUpdates"
```

Le lien doit apparaître dans `"text"` d'un message.

### 7.5 — L'automatisation

#### Créer `inbox.sh`

```
cat > "$HOME/Vault/inbox.sh" << 'EOF'
#!/bin/zsh
cd "$HOME/Vault"
source .venv/bin/activate
python3 telegram_inbox.py --vault "$HOME/Vault" --cookies firefox
EOF
chmod +x "$HOME/Vault/inbox.sh"
```

#### Utiliser `inbox.sh` manuellement

Tu peux lancer l'ingestion à tout moment depuis le Terminal :

```
"$HOME/Vault/inbox.sh"
```

Le script affiche une ligne par URL traitée et indique le nombre de réussites/échecs à la fin. Si aucune nouvelle URL n'attend dans Telegram, il s'arrête immédiatement sans rien faire.

Pour voir les logs de la dernière exécution (automatique ou manuelle) :

```
cat "$HOME/Vault/inbox.log"
```

Pour suivre les logs en temps réel pendant une exécution :

```
tail -f "$HOME/Vault/inbox.log"
```

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
        <string>$HOME/Vault/inbox.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>18</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$HOME/Vault/inbox.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/Vault/inbox.log</string>
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

Dernière brique, dans Cowork :

```
Crée une tâche récurrente quotidienne à 8h :
1. lire le dossier raw et repérer les fiches absentes de index.md
2. les résumer avec le même format et le même vocabulaire de thèmes
3. les ajouter à la fin de index.md, mettre à jour progression.txt
4. régénérer vault.html
S'il n'y a aucune nouvelle fiche, ne rien faire.
```

**La boucle est bouclée** : tu partages depuis ton lit, ton Mac transcrit le soir, l'index se met à jour le lendemain matin.

---

## Étape 8 — Interroger sa base

Crée un fichier `CLAUDE.md` à la racine du Vault. Cowork le lit automatiquement au début de chaque session :

```
- Ce dossier est une base de vidéos Instagram et TikTok que j'ai sauvegardées.
- Pour toute question sur mon contenu, commence TOUJOURS par lire index.md.
- N'ouvre les fiches complètes de raw/ que si index.md ne suffit pas.
- Ne mentionne jamais un lieu, un titre ou un conseil qui ne vient pas de mes
  fiches. Si je n'ai rien sur un sujet, dis-le simplement.
- Après toute modification de index.md, régénère vault.html.
- Réponds en français.
```

Tu peux alors demander directement :

> Je pars 7 jours au Japon. Organise-moi un circuit avec tout ce que j'ai gardé — lieux, restaurants, adresses. Dis-moi ce que tu écartes et pourquoi.

> Qu'est-ce que je sauvegarde le plus sans jamais l'utiliser ?

> Ressors-moi les pâtisseries parisiennes, classées par arrondissement.

**Depuis ton téléphone** : dépose `index.md` et `vault.html` sur Google Drive, et interroge-les depuis l'app Claude avec le connecteur Drive activé.

---

## Bonus — La carte du graphe

C'est l'image qui a fait circuler le projet : un nuage de points reliés, chaque point une vidéo, chaque gros nœud un thème.

Installe **Obsidian** (gratuit) :

```
brew install --cask obsidian
```

Au lancement, choisis **« Ouvrir un dossier comme coffre »** et sélectionne ton `Vault` — pas le coffre de démonstration créé par défaut.

Lance ensuite **`graphe.py`** (lien en bas de page), qui ajoute les liens `[[Thème]]` à chaque fiche et crée une note par thème :

```
cd "$HOME/Vault" && source .venv/bin/activate
python3 graphe.py --vault "$HOME/Vault"
```

Puis `Cmd+G` dans Obsidian. Monte **Repel** dans les réglages « Forces » pour aérer, et crée un groupe `path:themes` en couleur vive pour faire ressortir les thèmes.

**Sois honnête avec toi-même** : c'est superbe, ça fait un excellent visuel, mais on s'en sert peu au quotidien. La page `vault.html` avec ses filtres est bien plus efficace pour retrouver quelque chose. Le graphe, c'est l'affiche du projet.

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

**Les quotas existent.** Ce montage tient sur un abonnement Pro parce qu'on ne fait relire que l'index. Traiter des dizaines de milliers de vidéos demanderait une clé API et un vrai budget.

**Instagram limite le rythme.** Sur plusieurs centaines de posts, mieux vaut procéder par lots de 50 étalés sur quelques jours.

**Une partie du contenu est irrécupérable.** Les posts supprimés ou passés en privé depuis que tu les avais enregistrés sont perdus. Sur un stock ancien, compte facilement un tiers de pertes.

---

## Les fichiers

- **`ingest.py`** — récolte et transcription
- **`generate_vault.py`** — relit `Vault/index.md` et régénère `Vault/vault.html`
- **`telegram_inbox.py`** — récupère les URLs depuis le bot Telegram et appelle `ingest.py`
- **`graphe.py`** — création des liens pour Obsidian
- **`requirements.txt`** — dépendances Python (`pip install -r requirements.txt`)
- **`.env.example`** — modèle du fichier de configuration Telegram (copier en `.env` et remplir)

*Tuto rédigé après un montage réel, du premier `brew install` jusqu'au circuit de voyage. Les pièges décrits ont tous été rencontrés pour de vrai.*



##Commandes utiles

- **`make install`** - Installe les dépendances Python
- **`make run`** - Lance le script d'ingestion
- **`make generate`** - Génère le vault HTML
- **`make telegram`** - Lance le bot Telegram
- **`make graph`** - Crée les liens pour Obsidian
- **`make ingest FILE="./your_instagram_activity/saved/saved_posts.json" LIMITE=100 COOKIES=firefox`** - Traite un fichier JSON spécifique avec limite de 100 posts et cookies Firefox
