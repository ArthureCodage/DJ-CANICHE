# 🐩 DJ-CANICHE - Le Bot Discord Ultime

**DJ-CANICHE** est un bot Discord polyvalent conçu pour offrir une expérience musicale de haute qualité, une intelligence artificielle réactive et une gestion automatisée de serveurs.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![discord.py](https://img.shields.io/badge/discord.py-bot-5865F2?logo=discord&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-pr%C3%AAt-2496ED?logo=docker&logoColor=white)

🌐 **Site du bot :** https://arthurecodage.github.io/DJ-CANICHE/

> Installation avec Docker : remplis `.env` (voir plus bas) puis `docker compose up -d`.

## 🚀 Caractéristiques

### 🎵 Musique Haute Fidélité
- **Qualité Fibre** : Flux audio optimisé (192kbps / 48kHz) pour une fluidité parfaite.
- **Playlists Instantanées** : Ajout de playlists entières en quelques secondes via `$pl`.
- **Interface Interactive** : Contrôle total par boutons (Pause, Skip, Queue, Clear, Stop).
- **Gestion Avancée** : Menu déroulant dans la file d'attente pour sélectionner un morceau précis.
- **Zéro Lag** : Téléchargement "juste à temps" local pour éviter les saccades réseau.

### 🤖 Intelligence Artificielle (IA)
- **Discussion par Mention** : Mentionne `@DJ-CANICHE` pour discuter avec lui.
- **Support MP** : Discute avec le bot en messages privés.
- **Multimodèle** : Utilise OpenRouter avec un système de secours automatique (Fallback) pour garantir une réponse rapide même en cas de surcharge.
- **Personnalité** : Un style décontracté et amical (vibe caniche DJ).

### 🌟 Salons Temporaires (Auto-Voice)
- **Génération Automatique** : Crée une catégorie, un vocal et un textuel dès qu'un utilisateur rejoint le salon "Générateur".
- **Auto-Nettoyage** : Supprime les salons dès qu'ils sont vides.
- **Positionnement Intelligent** : S'insère proprement dans la hiérarchie de ton serveur.

## 🛠️ Installation (Local Windows)

1. **Prérequis** :
   - [Python 3.11+](https://www.python.org/)
   - [FFmpeg](https://ffmpeg.org/download.html) installé et ajouté au PATH Windows.

2. **Cloner le projet** :
   ```bash
   git clone https://github.com/ArthureCodage/DJ-CANICHE.git
   cd DJ-CANICHE
   ```

3. **Installer les dépendances** :
   ```bash
   pip install -r requirements.txt
   ```

4. **Configuration** :
   - Renomme `.env.example` en `.env`.
   - Remplis ton `DISCORD_TOKEN` et ta `OPENROUTER_API_KEY`.

5. **Lancer le bot** :
   - En mode visible : `python main.py`
   - En arrière-plan (sans terminal) :
     ```powershell
     Start-Process pythonw -ArgumentList "main.py" -WorkingDirectory "C:\chemin\vers\le\dossier"
     ```

## 🎮 Commandes (Prefix : `$`)

| Commande | Alias | Description |
| :--- | :--- | :--- |
| `$play <titre/lien>` | `$p` | Joue une musique YouTube. |
| `$playlist <lien>` | `$pl` | Ajoute une playlist entière. |
| `$skip` | `$s` | Passe au morceau suivant. |
| `$queue` | `$q` | Affiche la file et le menu de sélection. |
| `$clear` | `$c` | Vide toute la file d'attente. |
| `$volume <0-100>` | `$vol` | Règle le volume. |
| `$nowplaying` | `$np` | Affiche les infos du son actuel. |
| `$setup_temp` | | Définit le salon actuel comme générateur. |

---
*Développé avec passion pour la gang ! 🐩🔥🎶*
