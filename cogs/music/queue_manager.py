import discord
from discord.ext import commands
import random
from utils.helpers import YTDLSource, ytdl
from .utils import is_dj
import asyncio
import logging
import os
import traceback

logger = logging.getLogger(__name__)

async def _toggle_repeat(self, ctx):
    """Włącza/wyłącza tryb powtarzania dla bieżącego utworu."""
    guild_id = ctx.guild.id
    
    # Sprawdź, czy bot jest na kanale głosowym
    if not ctx.voice_client:
        await ctx.send("❌ Nie jestem połączony z żadnym kanałem głosowym.")
        return
    
    # Sprawdź, czy coś jest odtwarzane
    if guild_id not in self.now_playing or not self.now_playing[guild_id]:
        await ctx.send("❌ Aktualnie nic nie jest odtwarzane.")
        return
    
    # Przełącz tryb powtarzania
    if not hasattr(self, 'repeat_mode'):
        self.repeat_mode = {}
    
    # Włącz/wyłącz tryb powtarzania dla tego serwera
    current_mode = self.repeat_mode.get(guild_id, 0)
    
    # Tryby: 0 - wyłączony, 1 - powtarzanie utworu, 2 - powtarzanie kolejki
    if current_mode == 0:
        self.repeat_mode[guild_id] = 1
        await ctx.send("🔂 Tryb powtarzania **utworu włączony**. Bieżący utwór będzie odtwarzany w pętli.")
    elif current_mode == 1:
        self.repeat_mode[guild_id] = 2
        await ctx.send("🔁 Tryb powtarzania **kolejki włączony**. Po zakończeniu kolejki, rozpocznę od początku.")
    else:
        self.repeat_mode[guild_id] = 0
        await ctx.send("➡️ Tryb powtarzania **wyłączony**. Po zakończeniu utworu przejdę do następnego.")

async def _playlist(self, ctx, *, url):
    """
    Dodaje całą playlistę YouTube do kolejki.
    
    Args:
        ctx: Kontekst komendy
        url: URL playlisty YouTube
    """
    # Sprawdź, czy bot jest na kanale głosowym
    if not ctx.voice_client:
        # Próbuj dołączyć do kanału głosowego
        if ctx.author.voice:
            try:
                await ctx.author.voice.channel.connect()
            except Exception as e:
                await ctx.send(f"Nie mogę dołączyć do kanału: {str(e)}")
                return
        else:
            await ctx.send("Musisz być na kanale głosowym, aby użyć tej komendy!")
            return
    
    # Sprawdź, czy URL jest URL playlisty
    if "list=" not in url:
        await ctx.send("❌ To nie wygląda na link do playlisty YouTube. Użyj komendy `%play` dla pojedynczych utworów.")
        return
    
    # Dodaj playlistę
    await self._add_playlist(ctx, url)

async def _add_playlist(self, ctx, playlist_url, *, max_tracks=100, chunk_size=25):
    """
    Dodaje utwory z playlisty YouTube do kolejki w sposób zoptymalizowany.
    
    Args:
        ctx: Kontekst komendy
        playlist_url: URL playlisty
        max_tracks: Maksymalna liczba utworów do dodania
        chunk_size: Rozmiar porcji do ładowania
    """
    try:
        message = await ctx.send(f"🔍 Pobieram informacje o playliście... Może to chwilę potrwać.")
        
        # Ustaw asynchroniczny event loop
        loop = asyncio.get_event_loop()
        
        # Wstępne pobranie informacji o playliście
        options = {
            'extract_flat': True,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'playlistend': max_tracks
        }
        
        # Pobieramy informacje o playliście
        try:
            playlist_info = await loop.run_in_executor(None, lambda: ytdl.extract_info(playlist_url, download=False, process=False, ie_key=None, extra_info={}, **options))
        except Exception as e:
            await message.edit(content=f"❌ Wystąpił błąd podczas pobierania playlisty: {str(e)}")
            logger.error(f"Error fetching playlist: {e}")
            return
        
        if not playlist_info or 'entries' not in playlist_info:
            await message.edit(content=f"❌ Nie mogę pobrać informacji o playliście. Upewnij się, że URL jest poprawny.")
            return
        
        # Pobierz całkowitą liczbę utworów
        entries = playlist_info['entries']
        if not entries:
            await message.edit(content=f"❌ Playlista jest pusta lub niedostępna.")
            return
            
        total_tracks = len(entries)
        
        # Ogranicz liczbę utworów
        if total_tracks > max_tracks:
            await message.edit(content=f"⚠️ Playlista zawiera {total_tracks} utworów, co przekracza limit {max_tracks}. Załaduję tylko pierwsze {max_tracks} utworów.")
            total_tracks = max_tracks
            entries = entries[:max_tracks]
        
        # Inicjalizuj kolejkę dla serwera, jeśli nie istnieje
        guild_id = ctx.guild.id
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        
        # Zapisz kanał, na którym wywołano komendę
        self.command_channels[guild_id] = ctx.channel
        
        # Pobieraj utwory w porcjach
        added_tracks = 0
        progress_message = await ctx.send(f"📥 Ładowanie utworów: 0/{total_tracks}")
        
        # Inicjalizacja historii kolejki jeśli nie istnieje
        if not hasattr(self, '_queue_history'):
            self._queue_history = {}
        
        if guild_id not in self._queue_history:
            self._queue_history[guild_id] = []
        
        # Dodawaj utwory w porcjach
        for i in range(0, total_tracks, chunk_size):
            chunk_end = min(i + chunk_size, total_tracks)
            current_chunk = entries[i:chunk_end]
            
            # Aktualizuj wiadomość z postępem
            await progress_message.edit(content=f"📥 Ładowanie utworów: {i}/{total_tracks}")
            
            # Pobierz informacje o utworach w tej porcji
            for entry in current_chunk:
                try:
                    # Pobierz szczegóły utworu
                    url = entry.get('url', entry.get('webpage_url', None))
                    if not url:
                        continue
                    
                    # Pobieramy informacje o utworze
                    source = await YTDLSource.from_url(url, loop=loop, stream=True)
                    
                    # Dodaj utwór do kolejki
                    self.queues[guild_id].append(source)
                    
                    # Dodaj do historii kolejki
                    self._queue_history[guild_id].append(source)
                    
                    added_tracks += 1
                    
                    # Co 5 utworów aktualizuj wiadomość
                    if added_tracks % 5 == 0:
                        await progress_message.edit(content=f"📥 Ładowanie utworów: {added_tracks}/{total_tracks}")
                except Exception as e:
                    logger.error(f"Błąd podczas dodawania utworu z playlisty: {e}")
                    continue
        
        # Aktualizuj finalne wiadomości
        await progress_message.edit(content=f"✅ Załadowano {added_tracks} utworów z playlisty!")
        await message.edit(content=f"🎵 Dodano playlistę do kolejki! Liczba utworów: {added_tracks}")
        
        # Jeśli bot nie odtwarza muzyki, rozpocznij odtwarzanie
        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await self._play_next(ctx)
            
    except Exception as e:
        logger.error(f"Błąd podczas ładowania playlisty: {e}")
        await ctx.send(f"❌ Wystąpił błąd podczas ładowania playlisty: {str(e)}")

# Zaktualizuj funkcję _queue, zastępując wszystkie wystąpienia cog na self

async def _queue(self, ctx):
    """Wyświetla aktualną kolejkę utworów"""
    guild_id = ctx.guild.id
    
    if not ctx.voice_client or (guild_id not in self.queues or not self.queues[guild_id]):
        await ctx.send("Kolejka jest pusta!")
        return
    
    queue = self.queues[guild_id]
    
    # Utwórz embed
    embed = discord.Embed(
        title="📋 Kolejka utworów",
        description=f"Łącznie {len(queue)} utworów w kolejce",
        color=discord.Color.blue()
    )
    
    # Dodaj informację o aktualnie odtwarzanym utworze
    if guild_id in self.now_playing and ctx.voice_client.is_playing():
        current = self.now_playing[guild_id]
        embed.add_field(
            name="🎵 Teraz odtwarzane",
            value=f"**{current.title}** ({current.duration})",
            inline=False
        )
    
    # Dodaj utwory z kolejki
    tracks_per_page = 10
    if len(queue) > 0:
        queue_list = []
        for i, track in enumerate(queue[:tracks_per_page]):
            queue_list.append(f"**{i+1}.** {track.title} ({track.duration})")
        
        embed.add_field(
            name="Następne utwory",
            value="\n".join(queue_list) if queue_list else "Brak utworów w kolejce",
            inline=False
        )
        
        # Jeśli kolejka jest dłuższa, dodaj informację o pozostałych utworach
        if len(queue) > tracks_per_page:
            embed.add_field(
                name="...",
                value=f"i {len(queue) - tracks_per_page} więcej utworów",
                inline=False
            )
    
    # Dodaj informację o powtarzaniu
    repeat_mode = self.repeat_mode.get(guild_id, 0)
    repeat_info = "Wyłączony"
    if repeat_mode == 1:
        repeat_info = "Ten utwór 🔂"
    elif repeat_mode == 2:
        repeat_info = "Cała kolejka 🔁"
    embed.add_field(name="Powtarzanie", value=repeat_info, inline=True)
    
    # Wyślij embed
    await ctx.send(embed=embed)

# Poprawienie funkcji queue wewnątrz setup_queue_commands
def setup_queue_commands(cog):
    """Dodaje komendy związane z zarządzaniem kolejką do coga Music."""
    
    # Dodaj funkcje do coga
    cog._toggle_repeat = _toggle_repeat.__get__(cog, type(cog))
    cog._playlist = _playlist.__get__(cog, type(cog))
    cog._add_playlist = _add_playlist.__get__(cog, type(cog))
    
    # Zastąpienie głównej funkcji _queue przypisanej do klasy
    cog._queue = _queue.__get__(cog, type(cog))
    
    # Definicje funkcji obsługujących komendy
    async def queue(ctx, page: int = 1):
        """Wyświetla kolejkę utworów z paginacją"""
        await cog._queue(ctx, page)  # Użyj cog zamiast self
    
    async def _shuffle(self, ctx):
        """Miesza kolejkę utworów"""
        guild_id = ctx.guild.id
        
        if guild_id not in self.queues or not self.queues[guild_id]:
            await ctx.send("Kolejka jest pusta! Nie ma czego mieszać.")
            return
        
        # Pobierz aktualną kolejkę
        queue = self.queues[guild_id]
        
        # Jeśli jest tylko jeden utwór, nie ma sensu mieszać
        if len(queue) <= 1:
            await ctx.send("W kolejce jest za mało utworów, aby je wymieszać!")
            return
        
        # Zapisz liczbę utworów
        queue_length = len(queue)
        
        # Wymieszaj kolejkę
        random.shuffle(queue)
        
        await ctx.send(f"🔀 Kolejka wymieszana! ({queue_length} utworów)")
    
    async def _clear(self, ctx):
        """Czyści kolejkę utworów"""
        guild_id = ctx.guild.id
        
        if guild_id not in self.queues or not self.queues[guild_id]:
            await ctx.send("Kolejka jest już pusta!")
            return
        
        # Zapisz liczbę utworów przed wyczyszczeniem
        queue_length = len(self.queues[guild_id])
        
        # Wyczyść kolejkę
        self.queues[guild_id].clear()
        
        await ctx.send(f"✅ Kolejka wyczyszczona! Usunięto {queue_length} utworów.")
    
    async def _remove(self, ctx, index: int):
        """Usuwa utwór z kolejki na podanej pozycji"""
        guild_id = ctx.guild.id
        
        if guild_id not in self.queues or not self.queues[guild_id]:
            await ctx.send("Kolejka jest pusta!")
            return
        
        queue = self.queues[guild_id]
        
        # Sprawdź, czy podany indeks jest prawidłowy
        if index < 1 or index > len(queue):
            await ctx.send(f"❌ Nieprawidłowy numer utworu! Kolejka zawiera {len(queue)} utworów.")
            return
        
        # Pobierz i usuń utwór z kolejki
        removed_track = queue.pop(index - 1)
        
        await ctx.send(f"🗑️ Usunięto z kolejki: **{removed_track.title}**")
    
    # Przypisanie funkcji do coga
    cog.queue = _queue.__get__(cog, type(cog))
    cog.clear = _clear.__get__(cog, type(cog))
    cog.shuffle = _shuffle.__get__(cog, type(cog))
    cog.remove = _remove.__get__(cog, type(cog))
    
    return cog