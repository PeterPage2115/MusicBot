import discord
from discord.ext import commands
from .player import setup_player_commands
from .queue_manager import setup_queue_commands
from .ui import setup_ui_commands
from .utils import is_dj  # Dodaj ten import
from utils.logger import get_logger
import asyncio

# Inicjalizacja loggera
logger = get_logger()

class Music(commands.Cog):
    """Komenda muzyczne dla bota Discord"""
    
    def __init__(self, bot):
        self.bot = bot
        self.volume_value = 0.5
        self.queues = {}
        self.now_playing = {}
        
        # Inicjalizacja kolekcji
        self.inactive_timeout = {}
        self.disconnected_sessions = {}
        self.command_channels = {}
        self.repeat_mode = {}
        self.volume_settings = {}
        self._queue_history = {}
        self.last_np_message = {}
        
        # Dodawanie komend z różnych modułów - najpierw ui, potem player
        setup_ui_commands(self)
        setup_player_commands(self)
        setup_queue_commands(self)
        
        logger.info("Moduł muzyczny zainicjalizowany")
    
    # Komendy podstawowe
    @commands.command(name="join", aliases=["dolacz", "j"], help="Dołącza do kanału głosowego")
    async def join_command(self, ctx):
        await self.join(ctx)

    @commands.command(name="leave", aliases=["wyjdz", "l", "disconnect", "dc"], help="Opuszcza kanał głosowy")
    async def leave_command(self, ctx):
        await self.leave(ctx)

    @commands.command(name="play", aliases=["p", "graj", "odtworz"], help="Odtwarza muzykę z podanego linku lub frazy wyszukiwania")
    async def play_command(self, ctx, *, query=None):
        await self.play(ctx, query=query)

    @commands.command(name="pause", aliases=["pauza", "wstrzymaj"], help="Wstrzymuje odtwarzanie")
    @is_dj()
    async def pause_command(self, ctx):
        await self.pause(ctx)

    @commands.command(name="resume", aliases=["wznow", "r", "kontynuuj"], help="Wznawia odtwarzanie")
    @is_dj()
    async def resume_command(self, ctx):
        await self.resume(ctx)

    @commands.command(name="stop", aliases=["zatrzymaj"], help="Zatrzymuje odtwarzanie i czyści kolejkę")
    @is_dj()
    async def stop_command(self, ctx):
        await self.stop(ctx)

    @commands.command(name="skip", aliases=["s", "pomin", "next", "n"], help="Pomija aktualny utwór")
    @is_dj()
    async def skip_command(self, ctx):
        await self.skip(ctx)

    @commands.command(name="volume", aliases=["vol", "v", "glosnosc"], help="Ustawia głośność odtwarzania (1-100)")
    @is_dj()
    async def volume_command(self, ctx, *, volume: str):
        await self.volume(ctx, volume_str=volume)

    @commands.command(name="now", aliases=["np", "nowplaying", "current", "teraz", "aktualny"], help="Pokazuje aktualnie odtwarzany utwór")
    async def nowplaying_command(self, ctx):
        await self.nowplaying(ctx)

    @commands.command(name="queue", aliases=["q", "kolejka", "lista"], help="Wyświetla kolejkę utworów")
    async def queue_command(self, ctx):
        await self.queue(ctx)

    @commands.command(name="clear", aliases=["wyczysc", "c", "clearqueue", "czyszczenie"], help="Czyści kolejkę utworów")
    @is_dj()
    async def clear_command(self, ctx):
        await self.clear(ctx)

    @commands.command(name="reconnect", aliases=["polacz", "polaczponownie"], help="Próbuje przywrócić ostatnią sesję muzyczną")
    async def reconnect_command(self, ctx):
        await self.reconnect(ctx)
    
    @commands.command(name="cleancache", help="Czyści pliki tymczasowe")
    @commands.has_permissions(administrator=True)
    async def cleancache_command(self, ctx):
        await self.cleancache(ctx)
    
    @commands.command(name="help_music", aliases=["mhelp", "pomoc", "komendy"], help="Wyświetla pomoc dotyczącą komend muzycznych")
    async def music_help_command(self, ctx):
        await self.music_help(ctx)
    
    @commands.command(name="dj", help="Wyświetla informacje o systemie DJ")
    async def dj_command(self, ctx):
        await self.dj_info(ctx)
    
    # Obsługa zdarzeń głosowych
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # To zdarzenie jest już obsługiwane przez przypisaną funkcję
        pass
    
    @commands.command(name="test", help="Testuje funkcję odtwarzania (tylko dla debugowania)")
    async def test_command(self, ctx, *, query=None):
        """Komenda testowa do diagnostyki odtwarzania"""
        if not query:
            await ctx.send("Podaj nazwę utworu do testu")
            return
            
        await ctx.send(f"🧪 Rozpoczynam test odtwarzania: `{query}`")
        await self._test_playback(ctx, query)
    
    # Po dodaniu komendy, zaimplementuj metodę testową
    async def _test_playback(self, ctx, query):
        """Prosta funkcja testowa odtwarzania"""
        try:
            guild_id = ctx.guild.id
            
            # Dołącz do kanału jeśli potrzeba
            if ctx.voice_client is None:
                if ctx.author.voice:
                    await ctx.author.voice.channel.connect()
                    await ctx.send("Dołączono do kanału głosowego")
                else:
                    await ctx.send("Musisz być na kanale głosowym!")
                    return
                    
            # Bezpośrednio pobierz i odtwórz utwór bez używania kolejki
            await ctx.send("🔍 Wyszukuję utwór...")
            
            from utils.helpers import YTDLSource
            
            # Użyj streamowania
            source = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True)
            await ctx.send(f"✅ Znaleziono: **{source.title}**")
            
            # Zdefiniuj prosty callback
            def after_playback(error):
                if error:
                    print(f"TEST ERROR: {error}")
                    asyncio.run_coroutine_threadsafe(
                        ctx.send(f"❌ Test error: {error}"), 
                        self.bot.loop
                    )
                else:
                    print("TEST: Playback completed normally")
                    asyncio.run_coroutine_threadsafe(
                        ctx.send("✅ Test odtwarzania zakończony pomyślnie!"), 
                        self.bot.loop
                    )
            
            # Odtwórz utwór
            await ctx.send("▶️ Rozpoczynam odtwarzanie testowe...")
            ctx.voice_client.play(source, after=after_playback)
            
            # Ustaw głośność
            ctx.voice_client.source.volume = 0.5
            
        except Exception as e:
            await ctx.send(f"❌ Test error: {e}")
            import traceback
            traceback.print_exc()
    
    # Dodaj nową komendę

    @commands.command(name="yplay", help="Odtwarza muzykę poprzez bezpośrednie wyszukiwanie YouTube")
    async def youtube_play(self, ctx, *, query=None):
        """Odtwarza muzykę z bezpośrednim wyszukiwaniem YouTube"""
        if not query:
            await ctx.send("⚠️ Podaj tytuł utworu do wyszukania")
            return
        
        # Dołącz do kanału głosowego, jeśli bot nie jest jeszcze połączony
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("❌ Nie jesteś połączony z kanałem głosowym!")
                return
        
        await ctx.send(f"🔍 Wyszukuję na YouTube: `{query}`...")
        
        try:
            # Tworzenie bezpośredniego URL wyszukiwania YouTube
            import urllib.parse
            search_query = urllib.parse.quote(query)
            search_url = f"https://www.youtube.com/results?search_query={search_query}"
            
            await ctx.send(f"🔗 [Link do wyszukiwania]({search_url})")
            
            # Użyj requests i BeautifulSoup do parsowania wyników (zamiast yt-dlp)
            import aiohttp
            from bs4 import BeautifulSoup
            
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url) as response:
                    if response.status != 200:
                        await ctx.send(f"❌ Błąd wyszukiwania: status {response.status}")
                        return
                    
                    html = await response.text()
                    
            # Parsowanie HTML, aby znaleźć pierwszy film
            soup = BeautifulSoup(html, 'html.parser')
            
            # Szukamy pierwszego linku filmu (to jest uproszczone, może wymagać dostosowania)
            video_link = None
            for link in soup.find_all('a'):
                href = link.get('href')
                if href and 'watch?v=' in href:
                    video_link = f"https://www.youtube.com{href}"
                    break
            
            if not video_link:
                await ctx.send("❌ Nie znaleziono filmu na YouTube")
                return
            
            await ctx.send(f"✅ Znaleziono film: {video_link}")
            
            # Teraz odtwórz ten konkretny film
            from utils.helpers import YTDLSource
            player = await YTDLSource.from_url(video_link, loop=self.bot.loop, stream=True)
            
            # Funkcja wywoływana po zakończeniu
            def after_playback(error):
                if error:
                    print(f"Error in playback: {error}")
                    asyncio.run_coroutine_threadsafe(
                        ctx.send(f"❌ Błąd odtwarzania: {error}"), 
                        self.bot.loop
                    )
                else:
                    print("Playback completed normally")
                    asyncio.run_coroutine_threadsafe(
                        ctx.send("✅ Odtwarzanie zakończone"), 
                        self.bot.loop
                    )
            
            # Odtwórz utwór
            ctx.voice_client.play(player, after=after_playback)
            ctx.voice_client.source.volume = 0.5
            
            await ctx.send(f"▶️ Odtwarzam: **{player.title}**")
            
        except Exception as e:
            await ctx.send(f"❌ Błąd: {str(e)}")
            import traceback
            traceback.print_exc()

def setup(bot):
    bot.add_cog(Music(bot))