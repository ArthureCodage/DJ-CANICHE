import discord
import os
import asyncio
import yt_dlp
import logging
import sys
from openai import OpenAI
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
OPENROUTER_KEY = os.getenv('OPENROUTER_API_KEY')
PREFIX = os.getenv('PREFIX', '$')
BOT_COLOR = 0x00AEFF

# ─── CONFIGURATION IA (LISTE DE SECOURS) ─────────────────────────
if OPENROUTER_KEY:
    client_ia = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY)
    # Liste de modèles gratuits du plus stable au plus performant
    MODELS_TO_TRY = [
        "google/gemini-2.0-flash-001",           # Le plus stable via OpenRouter
        "meta-llama/llama-3.1-8b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "openchat/openchat-7b:free",
        "microsoft/phi-3-medium-128k-instruct:free"
    ]
    chat_histories = {}
else:
    logger.warning("OPENROUTER_API_KEY non trouvée.")

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
        super().__init__(command_prefix=PREFIX, intents=intents)
        self.queue = {}; self.volumes = {}; self.current_songs = {}; self.temp_channels = {} 
        self.generator_id = 1497351422986031324

    async def setup_hook(self):
        logger.info(f"Bot DJ-CANICHE PRO — Connecté : {self.user}")

bot = MusicBot()

# ─── GESTION IA AVEC FALLBACK AUTOMATIQUE ───────────────────────

@bot.event
async def on_message(message):
    if message.author.bot: return
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user.mentioned_in(message)

    if (is_dm or is_mentioned) and OPENROUTER_KEY:
        if message.content.startswith(PREFIX):
            await bot.process_commands(message)
            return

        prompt = message.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
        if not prompt and is_mentioned: return await message.reply("Wesh ! Tu veux jaser ? 🐩🔥")
        elif not prompt: return

        async with message.channel.typing():
            # Essayer chaque modèle jusqu'à ce qu'un fonctionne
            response_text = None
            session_id = message.author.id if is_dm else message.channel.id
            
            if session_id not in chat_histories:
                chat_histories[session_id] = [{"role": "system", "content": "Tu es DJ-CANICHE, un bot Discord stylé, amical et passionné de musique. Tu réponds de façon décontractée, avec de l'argot québécois (wesh, gang, beats, etc.)."}]
            
            chat_histories[session_id].append({"role": "user", "content": prompt})

            for model_id in MODELS_TO_TRY:
                try:
                    logger.info(f"Tentative IA avec le modèle : {model_id}")
                    completion = await bot.loop.run_in_executor(None, lambda: client_ia.chat.completions.create(
                        model=model_id,
                        messages=chat_histories[session_id],
                        extra_headers={"X-Title": "DJ-Caniche Bot"}
                    ))
                    response_text = completion.choices[0].message.content
                    if response_text: 
                        logger.info(f"Succès avec le modèle : {model_id}")
                        break
                except Exception as e:
                    logger.warning(f"Modèle {model_id} a échoué : {e}")
                    continue

            if response_text:
                chat_histories[session_id].append({"role": "assistant", "content": response_text})
                if len(chat_histories[session_id]) > 15: chat_histories[session_id] = [chat_histories[session_id][0]] + chat_histories[session_id][-10:]
                await message.reply(response_text)
            else:
                await message.reply("Gros, tous les serveurs d'IA sont pleins en ce moment... Réessaie dans une minute ! 🤖🔌")

    await bot.process_commands(message)

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
    if guild_id in bot.queue and bot.queue[guild_id]:
        song = bot.queue[guild_id].pop(0)
        try:
            if not song.get('filename') or not os.path.exists(song['filename']):
                data = await bot.loop.run_in_executor(None, lambda: ytdl.extract_info(song['url'], download=True))
                song['filename'] = ytdl.prepare_filename(data)
            bot.current_songs[guild_id] = song
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(song['filename'], **FFMPEG_OPTIONS))
            source.volume = bot.volumes.get(guild_id, 0.5)
            ctx.voice_client.play(source, after=lambda e: bot.loop.create_task(play_next(ctx)))
            embed = discord.Embed(title="▶️ Lecture", description=f"[{song['title']}]({song['url']})", color=0x00FF00)
            if song.get('thumbnail'): embed.set_thumbnail(url=song['thumbnail'])
            await ctx.send(embed=embed, view=MusicControlView(bot, ctx))
        except Exception as e: logger.error(f"Erreur : {e}"); bot.loop.create_task(play_next(ctx))

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
            if ctx.voice_client.is_playing():
                if ctx.guild.id not in bot.queue: bot.queue[ctx.guild.id] = []
                bot.queue[ctx.guild.id].append(song)
                await ctx.send(embed=discord.Embed(title="📑 Ajouté", description=song['title'], color=BOT_COLOR), view=MusicControlView(bot, ctx))
            else:
                if ctx.guild.id not in bot.queue: bot.queue[ctx.guild.id] = []
                bot.queue[ctx.guild.id].insert(0, song); await play_next(ctx)
        except Exception as e: await ctx.send(f"❌ Erreur : {e}")

bot.run(TOKEN)
