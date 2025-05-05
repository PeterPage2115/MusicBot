try:
    import discord
    import yt_dlp
    import dotenv
except ImportError as e:
    print(f"BŁĄD: Brak wymaganej zależności: {e}")
    print("Musisz zainstalować wszystkie wymagane biblioteki. Użyj komendy:")
    print("pip install -r requirements.txt")
    exit(1)

# Sprawdź czy FFmpeg jest dostępny
import shutil
if not shutil.which("ffmpeg"):
    print("OSTRZEŻENIE: FFmpeg nie został znaleziony w PATH.")
    print("Bot może nie odtwarzać dźwięku. Zainstaluj FFmpeg i upewnij się, że jest w PATH.")

import os
import discord
from discord.ext import commands, tasks
import asyncio
import traceback
from config import TOKEN, PREFIX, DEBUG_MODE
from utils.logger import get_logger
import time

# Inicjalizacja loggera
logger = get_logger()

# Ustawienia intencji (Intents)
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

# Inicjalizacja bota
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# Konfiguracja zaawansowanego logowania
if DEBUG_MODE:
    import logging
    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(logging.DEBUG)
    logging.getLogger('discord.http').setLevel(logging.INFO)
    logging.getLogger('discord.voice_client').setLevel(logging.DEBUG)

@tasks.loop(hours=6)
async def cleanup_temp_files():
    """Okresowo czyści pliki tymczasowe"""
    logger.info("Rozpoczynam czyszczenie plików tymczasowych...")
    try:
        # Implementacja czyszczenia plików w samym bot.py zamiast polegania na YTDLSource
        temp_dir = 'temp'
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            logger.info(f"Utworzono katalog {temp_dir}")
            return

        current_time = time.time()
        max_age_seconds = 24 * 3600  # 24 godziny
        
        # Liczniki statystyk
        removed_count = 0
        total_size_removed = 0
        
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            try:
                # Sprawdź czy to plik (nie katalog)
                if not os.path.isfile(file_path):
                    continue
                
                # Pobierz czas modyfikacji pliku
                file_modified_time = os.path.getmtime(file_path)
                file_age_seconds = current_time - file_modified_time
                
                # Jeśli plik jest starszy niż dozwolony wiek
                if file_age_seconds > max_age_seconds:
                    # Pobierz rozmiar pliku przed usunięciem
                    file_size = os.path.getsize(file_path)
                    
                    # Usuń plik
                    os.unlink(file_path)
                    
                    # Aktualizuj statystyki
                    removed_count += 1
                    total_size_removed += file_size
            except Exception as e:
                logger.error(f"Błąd podczas próby usunięcia pliku {file_path}: {e}")
        
        logger.info(f"Usunięto {removed_count} plików, zwolniono {total_size_removed} bajtów")
    except Exception as e:
        logger.error(f"Błąd podczas czyszczenia plików tymczasowych: {e}")

@bot.event
async def on_ready():
    """Wywoływane gdy bot jest gotowy i połączony"""
    logger.info(f"Bot zalogowany jako {bot.user.name} ({bot.user.id})")
    
    # Ustaw status bota
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening, 
        name=f"{PREFIX}help_music | Muzyka"
    ))
    
    # Wyświetl informacje o serwerach
    guild_count = len(bot.guilds)
    logger.info(f"Bot jest na {guild_count} serwerach")
    
    # Załaduj moduły
    await load_extensions()
    
    # Uruchom zadanie czyszczenia plików
    cleanup_temp_files.start()

@bot.event
async def on_command_error(ctx, error):
    """Obsługa błędów komend"""
    if isinstance(error, commands.CommandNotFound):
        return
    
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Brakuje wymaganego argumentu: {error.param.name}")
        return
    
    if isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Nieprawidłowy argument: {str(error)}")
        return
    
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Nie masz wymaganych uprawnień do wykonania tej komendy.")
        return
    
    if isinstance(error, commands.BotMissingPermissions):
        await ctx.send("❌ Bot nie ma wymaganych uprawnień do wykonania tej komendy.")
        return
    
    # Loguj szczegóły błędu
    logger.error(f"Błąd komendy {ctx.command}: {error}")
    if DEBUG_MODE:
        logger.error(traceback.format_exc())
    
    # Powiadom użytkownika
    await ctx.send(f"❌ Wystąpił błąd podczas wykonywania komendy: {str(error)}")

async def load_extensions():
    """Ładuje wszystkie rozszerzenia (cogs)"""
    # Główne moduły
    main_extensions = ['cogs.music']
    
    # Opcjonalne moduły - dodaj tutaj dodatkowe moduły
    optional_extensions = []
    
    # Załaduj główne moduły
    for extension in main_extensions:
        try:
            await bot.load_extension(extension)
            logger.info(f"Załadowano moduł {extension}")
        except Exception as e:
            logger.error(f"Nie udało się załadować modułu {extension}: {e}")
            logger.error(traceback.format_exc())
    
    # Załaduj opcjonalne moduły (jeśli istnieją)
    for extension in optional_extensions:
        try:
            await bot.load_extension(extension)
            logger.info(f"Załadowano opcjonalny moduł {extension}")
        except Exception as e:
            logger.warning(f"Nie udało się załadować opcjonalnego modułu {extension}: {e}")
    
    # Dodaj rozszerzenie diagnostyczne
    try:
        await bot.load_extension("cogs.diagnostics")
        logger.info("Załadowano moduł cogs.diagnostics")
    except Exception as e:
        logger.error(f"Nie udało się załadować modułu cogs.diagnostics: {e}")

@bot.command(name="ping", help="Sprawdza opóźnienie bota")
async def ping(ctx):
    """Sprawdza opóźnienie bota"""
    # Oblicz opóźnienie bota
    latency = round(bot.latency * 1000)  # Konwersja na milisekundy
    
    # Utwórz osadzony komunikat z informacją o opóźnieniu
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Opóźnienie bota: **{latency}ms**",
        color=discord.Color.green() if latency < 200 else discord.Color.gold() if latency < 400 else discord.Color.red()
    )
    
    await ctx.send(embed=embed)

if __name__ == "__main__":
    try:
        # Uruchom bota
        asyncio.run(bot.start(TOKEN))
    except KeyboardInterrupt:
        logger.info("Bot zatrzymany przez użytkownika")
    except Exception as e:
        logger.critical(f"Krytyczny błąd: {e}")
        logger.critical(traceback.format_exc())