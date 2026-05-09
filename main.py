import discord
import os
import asyncio
import yt_dlp
import logging
import sys
from discord.ext import commands
from discord.ui import Button, View, Select
from dotenv import load_dotenv

# ─── CONFIGURATION LOGGING ───────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("MusicBot")

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = os.getenv('PREFIX', '$')
BOT_COLOR = 0x00AEFF

DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)

YTDL_OPTIONS = {
    'format': 'bestaudio/best', 'outtmpl': f'{DOWNLOAD_DIR}/%(id)s.%(ext)s', 'noplaylist': False,
    'quiet': True, 'no_warnings': True, 'source_address': '0.0.0.0',
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

FFMPEG_OPTIONS = {'options': '-vn -ar 48000 -ac 2 -b:a 192k'}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# ─── COMPOSANTS INTERACTIFS ──────────────────────────────────────

class QueueSelect(Select):
    def __init__(self, bot, guild_id, options):
        super().__init__(placeholder="Sélectionne une chanson à jouer...", options=options)
        self.bot = bot
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        index = int(self.values[0])
        chosen_song = self.bot.queue[self.guild_id].pop(index)
        self.bot.queue[self.guild_id].insert(0, chosen_song)
        if interaction.guild.voice_client:
            interaction.guild.voice_client.stop()
            await interaction.response.send_message(f"🚀 On passe à : **{chosen_song['title']}**", ephemeral=True)

class MusicControlView(View):
    def __init__(self, bot, ctx, queue_options=None):
        super().__init__(timeout=None)
        self.bot = bot; self.ctx = ctx
        if queue_options: self.add_item(QueueSelect(bot, ctx.guild.id, queue_options))

    @discord.ui.button(label="⏯️ Pause", style=discord.ButtonStyle.secondary)
    async def pause_resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.ctx.voice_client: return
        if self.ctx.voice_client.is_playing(): self.ctx.voice_client.pause()
        elif self.ctx.voice_client.is_paused(): self.ctx.voice_client.resume()
        await interaction.response.defer()

    @discord.ui.button(label="⏭️ Skip", style=discord.ButtonStyle.primary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ctx.voice_client: self.ctx.voice_client.stop()
        await interaction.response.defer()

    @discord.ui.button(label="📜 Queue", style=discord.ButtonStyle.secondary)
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = self.ctx.guild.id
        if guild_id not in self.bot.queue or not self.bot.queue[guild_id]: return await interaction.response.send_message("File vide.", ephemeral=True)
        desc = ""; options = []
        for i, song in enumerate(self.bot.queue[guild_id][:25], 0):
            desc += f"{i+1}. **{song['title']}**\n"
            options.append(discord.SelectOption(label=f"{i+1}. {song['title']}"[:100], value=str(i)))
        embed = discord.Embed(title="📜 File d'attente", description=desc[:2000], color=BOT_COLOR)
        view = View(); view.add_item(QueueSelect(self.bot, guild_id, options))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="🗑️ Clear", style=discord.ButtonStyle.secondary)
    async def clear_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ctx.guild.id in self.bot.queue:
            self.bot.queue[self.ctx.guild.id] = []
            await interaction.response.send_message("🧹 File vidée !", ephemeral=True)

    @discord.ui.button(label="🛑 Stop", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ctx.voice_client:
            self.bot.queue[self.ctx.guild.id] = []
            await self.ctx.voice_client.disconnect()
            await interaction.response.send_message("🛑 Stop", ephemeral=True)

# ─── BOT LOGIC ───────────────────────────────────────────────────

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True; intents.voice_states = True
        intents.guilds = True; intents.members = True; intents.dm_messages = True
        super().__init__(command_prefix=PREFIX, intents=intents, help_command=None)
        self.queue = {}; self.volumes = {}; self.current_songs = {}; self.temp_channels = {} 
        self.generator_id = 1497351422986031324

    async def setup_hook(self):
        logger.info(f"Bot DJ-CANICHE PRO — Connecté : {self.user}")

bot = MusicBot()

# ─── GESTION DES SALONS TEMPORAIRES ──────────────────────────────

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id == bot.generator_id:
        guild = member.guild; category_name = f"🌟 │ {member.display_name}"
        user_category = discord.utils.get(guild.categories, name="---USER---")
        overwrites = {guild.default_role: discord.PermissionOverwrite(connect=True, speak=True, view_channel=True),
                      member: discord.PermissionOverwrite(manage_channels=True, manage_permissions=True, connect=True, speak=True, mute_members=True, deafen_members=True, move_members=True)}
        category = await guild.create_category(name=category_name, overwrites=overwrites)
        if user_category: await category.edit(position=user_category.position + 1)
        voice = await guild.create_voice_channel(name=f"🔊 Vocal de {member.display_name}", category=category)
        text = await guild.create_text_channel(name=f"💬-salon-de-{member.display_name}", category=category)
        bot.temp_channels[voice.id] = {'category': category, 'voice': voice, 'text': text, 'owner_id': member.id}
        await member.move_to(voice); await text.send(f"👋 Bienvenue {member.mention} !")

    if before.channel and before.channel.id in bot.temp_channels:
        voice = before.channel
        if len(voice.members) == 0:
            temp_data = bot.temp_channels.pop(voice.id)
            try: await temp_data['voice'].delete(); await temp_data['text'].delete(); await temp_data['category'].delete()
            except Exception as e: logger.error(f"Erreur nettoyage : {e}")

# ─── LOGIQUE MUSIQUE ──────────────────────────────────────────────

async def play_next(ctx):
    guild_id = ctx.guild.id
    if guild_id not in bot.queue or not bot.queue[guild_id]:
        bot.current_songs[guild_id] = None
        return

    if not ctx.voice_client or not ctx.voice_client.is_connected():
        logger.warning(f"Lecture annulée : Bot non connecté au vocal dans {ctx.guild.name}")
        return

    song = bot.queue[guild_id].pop(0)
    try:
        if not song.get('filename') or not os.path.exists(song['filename']):
            data = await bot.loop.run_in_executor(None, lambda: ytdl.extract_info(song['url'], download=True))
            song['filename'] = ytdl.prepare_filename(data)
        
        bot.current_songs[guild_id] = song
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(song['filename'], **FFMPEG_OPTIONS))
        source.volume = bot.volumes.get(guild_id, 0.5)

        def after_playing(error):
            if error: logger.error(f"Erreur après lecture : {error}")
            bot.loop.create_task(play_next(ctx))

        ctx.voice_client.play(source, after=after_playing)
        
        embed = discord.Embed(title="▶️ Lecture", description=f"[{song['title']}]({song['url']})", color=0x00FF00)
        if song.get('thumbnail'): embed.set_thumbnail(url=song['thumbnail'])
        await ctx.send(embed=embed, view=MusicControlView(bot, ctx))
        
    except Exception as e:
        logger.error(f"Erreur dans play_next : {e}")
        # On ne relance play_next que si ce n'est pas une erreur de connexion
        if "Not connected to voice" not in str(e):
            await asyncio.sleep(2)
            bot.loop.create_task(play_next(ctx))

# ─── COMMANDES ────────────────────────────────────────────────────

@bot.command(name='play', aliases=['p'])
async def play(ctx, *, search: str):
    if not ctx.guild: return await ctx.send("Serveur requis.")
    if not ctx.author.voice: return await ctx.send("Vocal requis !")
    if not ctx.voice_client: await ctx.author.voice.channel.connect()
    async with ctx.typing():
        try:
            params = YTDL_OPTIONS.copy(); params['noplaylist'] = True
            with yt_dlp.YoutubeDL(params) as ydl:
                data = await bot.loop.run_in_executor(None, lambda: ydl.extract_info(search, download=False))
            if 'entries' in data: data = data['entries'][0]
            song = {'title': data.get('title'), 'url': data.get('webpage_url'), 'thumbnail': data.get('thumbnail'), 'filename': None}
            if ctx.guild.id not in bot.queue: bot.queue[ctx.guild.id] = []
            if ctx.voice_client.is_playing():
                bot.queue[ctx.guild.id].append(song)
                await ctx.send(embed=discord.Embed(title="📑 Ajouté", description=song['title'], color=BOT_COLOR), view=MusicControlView(bot, ctx))
            else:
                bot.queue[ctx.guild.id].insert(0, song); await play_next(ctx)
        except Exception as e: await ctx.send(f"❌ Erreur : {e}")

@bot.command(name='playlist', aliases=['pl'])
async def playlist(ctx, *, url: str):
    if not ctx.guild: return await ctx.send("Serveur requis.")
    if not ctx.author.voice: return await ctx.send("Vocal requis !")
    if not ctx.voice_client: await ctx.author.voice.channel.connect()
    
    msg = await ctx.send("🔍 Analyse de la playlist... (La lecture va commencer)")
    
    try:
        # Extraction rapide des infos de base sans extraire les entrées complètes
        params = YTDL_OPTIONS.copy()
        params['extract_flat'] = True  # Ne pas extraire les infos de chaque vidéo, juste les URLs/Titres
        
        with yt_dlp.YoutubeDL(params) as ydl:
            data = await bot.loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
        
        if 'entries' not in data:
            return await msg.edit(content="❌ Ce lien n'est pas une playlist valide.")
            
        entries = list(data['entries'])
        total_songs = len(entries)
        
        if ctx.guild.id not in bot.queue: bot.queue[ctx.guild.id] = []
        
        # On ajoute le premier morceau et on lance la lecture direct
        first_entry = entries[0]
        song_url = first_entry.get('url') or f"https://www.youtube.com/watch?v={first_entry['id']}"
        first_song = {
            'title': first_entry.get('title') or "Chargement...",
            'url': song_url,
            'thumbnail': first_entry.get('thumbnail'),
            'filename': None
        }
        
        bot.queue[ctx.guild.id].append(first_song)
        if not ctx.voice_client.is_playing():
            await play_next(ctx)
            await msg.edit(content=f"🎶 **Lecture lancée !** Ajout de **{total_songs}** morceaux en cours...")
        else:
            await msg.edit(content=f"✅ Playlist détectée. Ajout de **{total_songs}** morceaux en cours...")

        # On ajoute le reste en arrière-plan sans bloquer
        async def add_rest_background():
            for entry in entries[1:]:
                s_url = entry.get('url') or f"https://www.youtube.com/watch?v={entry['id']}"
                bot.queue[ctx.guild.id].append({
                    'title': entry.get('title') or "Titre inconnu",
                    'url': s_url,
                    'thumbnail': entry.get('thumbnail'),
                    'filename': None
                })
            logger.info(f"Playlist de {total_songs} morceaux ajoutée pour {ctx.guild.name}")

        asyncio.create_task(add_rest_background())

    except Exception as e:
        logger.error(f"Erreur playlist : {e}")
        await msg.edit(content=f"❌ Erreur lors de l'ajout : {e}")

@bot.command(name='commands', aliases=['h', 'help'])
async def commands_list(ctx):
    embed = discord.Embed(title="🎮 Commandes (Prefix : $)", color=BOT_COLOR)
    embed.add_field(name="$play <titre/lien> (alias: $p)", value="Joue une musique YouTube.", inline=False)
    embed.add_field(name="$playlist <lien> (alias: $pl)", value="Ajoute une playlist entière.", inline=False)
    embed.add_field(name="$skip (alias: $s)", value="Passe au morceau suivant.", inline=False)
    embed.add_field(name="$queue (alias: $q)", value="Affiche la file et le menu de sélection.", inline=False)
    embed.add_field(name="$clear (alias: $c)", value="Vide toute la file d'attente.", inline=False)
    embed.add_field(name="$volume <0-100> (alias: $vol)", value="Règle le volume.", inline=False)
    embed.add_field(name="$nowplaying (alias: $np)", value="Affiche les infos du son actuel.", inline=False)
    embed.add_field(name="$setup_temp", value="Définit le salon actuel comme générateur.", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='skip', aliases=['s'])
async def skip(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        return await ctx.send("Rien en cours de lecture.")
    ctx.voice_client.stop()
    await ctx.send("⏭️ Skippé !")

@bot.command(name='queue', aliases=['q'])
async def queue(ctx):
    guild_id = ctx.guild.id
    if guild_id not in bot.queue or not bot.queue[guild_id]:
        return await ctx.send("La file d'attente est vide.")
    desc = ""; options = []
    for i, song in enumerate(bot.queue[guild_id][:25], 1):
        desc += f"`{i}.` **{song['title']}**\n"
        options.append(discord.SelectOption(label=f"{i}. {song['title']}"[:100], value=str(i - 1)))
    embed = discord.Embed(title="📜 File d'attente", description=desc[:2000], color=BOT_COLOR)
    embed.set_footer(text=f"{len(bot.queue[guild_id])} morceau(x) en attente")
    view = View(); view.add_item(QueueSelect(bot, guild_id, options))
    await ctx.send(embed=embed, view=view)

@bot.command(name='clear', aliases=['c'])
async def clear(ctx):
    if ctx.guild.id in bot.queue:
        bot.queue[ctx.guild.id] = []
    await ctx.send("🧹 File d'attente vidée !")

@bot.command(name='volume', aliases=['vol'])
async def volume(ctx, vol: int):
    if not ctx.voice_client: return await ctx.send("Pas connecté au vocal.")
    if not 0 <= vol <= 100: return await ctx.send("Volume entre 0 et 100.")
    bot.volumes[ctx.guild.id] = vol / 100
    if ctx.voice_client.source:
        ctx.voice_client.source.volume = vol / 100
    await ctx.send(f"🔊 Volume réglé à **{vol}%**")

@bot.command(name='nowplaying', aliases=['np'])
async def nowplaying(ctx):
    guild_id = ctx.guild.id
    song = bot.current_songs.get(guild_id)
    if not song: return await ctx.send("Rien en cours de lecture.")
    embed = discord.Embed(title="🎵 En cours", description=f"[{song['title']}]({song['url']})", color=BOT_COLOR)
    if song.get('thumbnail'): embed.set_thumbnail(url=song['thumbnail'])
    await ctx.send(embed=embed)

@bot.command(name='setup_temp')
@commands.has_permissions(manage_channels=True)
async def setup_temp(ctx):
    bot.generator_id = ctx.channel.id
    await ctx.send(f"✅ Salon **{ctx.channel.name}** défini comme générateur de salons temporaires.")

bot.run(TOKEN)
