import discord
from discord.ext import commands
import random
from utils.helpers import YTDLSource, YTDLError
from .utils import is_dj
import asyncio
import logging
import os
import traceback
import math
from utils.helpers import YTDLError
from utils.logger import get_logger

# Inicjalizacja loggera
logger = get_logger()

class QueuePaginator(discord.ui.View):
    """
    Widok do paginacji kolejki.
    
    Pozwala na nawigację po stronach kolejki za pomocą przycisków.
    """
    
    def __init__(self, pages, ctx, timeout=120):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.total_pages = len(pages)
        self.current_page = 0
        self.ctx = ctx
        self.message = None
        
        # Wyłącz przyciski, jeśli mamy tylko jedną stronę
        if self.total_pages <= 1:
            self.first_page.disabled = True
            self.prev_page.disabled = True
            self.next_page.disabled = True
            self.last_page.disabled = True
    
    @discord.ui.button(label="⏪ Pierwsza", style=discord.ButtonStyle.primary)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.current_page = 0
        await self.update_page(interaction)
    
    @discord.ui.button(label="◀️ Poprzednia", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.current_page > 0:
            self.current_page -= 1
        await self.update_page(interaction)
    
    @discord.ui.button(label="▶️ Następna", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        await self.update_page(interaction)
    
    @discord.ui.button(label="⏩ Ostatnia", style=discord.ButtonStyle.primary)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.current_page = self.total_pages - 1
        await self.update_page(interaction)
    
    async def update_page(self, interaction):
        """Aktualizuje stronę do wyświetlenia"""
        # Pobierz bieżącą stronę
        page = self.pages[self.current_page]
        
        # Zaktualizuj przyciski
        self.first_page.disabled = self.current_page == 0
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page == self.total_pages - 1
        self.last_page.disabled = self.current_page == self.total_pages - 1
        
        # Aktualizuj wiadomość
        await interaction.message.edit(embed=page, view=self)
    
    async def on_timeout(self):
        """Obsługa timeout widoku"""
        # Wyłącz wszystkie przyciski po timeout
        self.first_page.disabled = True
        self.prev_page.disabled = True
        self.next_page.disabled = True
        self.last_page.disabled = True
        
        if self.message:
            await self.message.edit(view=self)


async def _toggle_repeat(self, ctx):
    """Włącza/wyłącza tryb powtarzania dla bieżącego utworu."""
    guild_id = ctx.guild.id
    
    # Sprawdź, czy bot jest na kanale głosowym
    if not ctx.voice_client:
        await ctx.send("❌ Nie jestem połączony z kanałem głosowym!")
        return
    
    # Sprawdź, czy coś jest odtwarzane
    if guild_id not in self.now_playing or not self.now_playing[guild_id]:
        await ctx.send("❌ Nic teraz nie gram!")
        return
    
    # Przełącz tryb powtarzania
    if not hasattr(self, 'repeat_mode'):
        self.repeat_mode = {}
    
    # Włącz/wyłącz tryb powtarzania dla tego serwera
    current_mode = self.repeat_mode.get(guild_id, 0)
    
    # Tryby: 0 - wyłączony, 1 - powtarzanie utworu, 2 - powtarzanie kolejki
    if current_mode == 0:
        self.repeat_mode[guild_id] = 1
        await ctx.send("🔂 Powtarzanie **bieżącego utworu** włączone")
    elif current_mode == 1:
        self.repeat_mode[guild_id] = 2
        await ctx.send("🔁 Powtarzanie **całej kolejki** włączone")
    else:
        self.repeat_mode[guild_id] = 0
        await ctx.send("🔄 Powtarzanie **wyłączone**")


async def _playlist(self, ctx, *, url):
    """
    Dodaje całą playlistę YouTube do kolejki.
    
    Args:
        ctx: Kontekst komendy
        url: URL playlisty YouTube
    """
    # Sprawdź, czy bot jest na kanale głosowym
    if ctx.voice_client is None:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
            await ctx.send(f"Dołączono do kanału {ctx.author.voice.channel.mention}")
        else:
            await ctx.send("Musisz być na kanale głosowym, aby użyć tej komendy!")
            return
    
    # Sprawdź, czy URL zawiera listę odtwarzania
    if "list=" not in url:
        await ctx.send("⚠️ To nie jest link do playlisty YouTube!")
        return
    
    # Zapisz kanał, na którym wywołano komendę
    self.command_channels[ctx.guild.id] = ctx.channel
    
    # Dodaj playlistę do kolejki
    await self._add_playlist(ctx, url)


async def _add_playlist(self, ctx, playlist_url, *, max_tracks=100, chunk_size=25):
    """
    Dodaje playlistę do kolejki po kawałkach.
    
    Args:
        ctx: Kontekst komendy
        playlist_url: URL playlisty YouTube
        max_tracks: Maksymalna liczba utworów do dodania
        chunk_size: Rozmiar porcji do przetworzenia na raz
    """
    async with ctx.typing():
        try:
            await ctx.send(f"🔍 Pobieram informacje o playliście...")
            
            # Przygotuj opcje yt-dlp
            ytdl_options = {
                'format': 'bestaudio/best',
                'outtmpl': 'temp/%(extractor)s-%(id)s-%(title)s.%(ext)s',
                'restrictfilenames': True,
                'noplaylist': False,  # Potrzebujemy playlist
                'nocheckcertificate': True,
                'ignoreerrors': False,
                'logtostderr': False,
                'quiet': True,
                'no_warnings': True,
                'default_search': 'auto',
                'source_address': '0.0.0.0',
                'extract_flat': True,  # Nie pobieraj wszystkich informacji na raz
                'force_generic_extractor': False
            }
            
            # Inicjalizacja YTDL
            import yt_dlp
            ydl = yt_dlp.YoutubeDL(ytdl_options)
            
            # Pobierz informacje o playliście
            info = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ydl.extract_info(playlist_url, download=False)
            )
            
            if 'entries' not in info:
                await ctx.send("❌ Nie znaleziono playlisty lub wystąpił błąd!")
                return
            
            # Pobierz tytuł playlisty, jeśli dostępny
            playlist_title = info.get('title', 'Playlista YouTube')
            
            # Ogranicz liczbę utworów do max_tracks
            entries = info['entries'][:max_tracks]
            total_tracks = len(entries)
            
            if total_tracks == 0:
                await ctx.send("❌ Playlista jest pusta!")
                return
            
            # Wyświetl informacje o playliście
            await ctx.send(f"📋 Dodaję playlistę **{playlist_title}** ({total_tracks} utworów)...")
            
            # Inicjalizacja kolejki dla tego serwera, jeśli nie istnieje
            if ctx.guild.id not in self.queues:
                self.queues[ctx.guild.id] = []
            
            # Liczniki do śledzenia postępu
            added_count = 0
            failed_count = 0
            duplicate_count = 0
            
            # Pobierz informacje o każdym utworze w playliście w mniejszych porcjach
            for i in range(0, total_tracks, chunk_size):
                chunk = entries[i:i+chunk_size]
                chunk_size_actual = len(chunk)
                
                # Aktualizuj status co każdą porcję
                if i > 0:
                    await ctx.send(f"⏳ Przetwarzanie {i}/{total_tracks} utworów...")
                
                for entry in chunk:
                    # Sprawdź czy mamy URL
                    if 'url' not in entry and 'id' not in entry:
                        failed_count += 1
                        continue
                    
                    # Utwórz URL na podstawie ID, jeśli potrzeba
                    video_url = entry.get('url', f"https://www.youtube.com/watch?v={entry.get('id')}")
                    
                    # Sprawdź, czy utwór już jest w kolejce (duplikat)
                    is_duplicate = False
                    for track in self.queues[ctx.guild.id]:
                        if track.url == video_url:
                            duplicate_count += 1
                            is_duplicate = True
                            break
                    
                    if is_duplicate:
                        continue
                    
                    try:
                        # Pobierz informacje o utworze
                        player = await YTDLSource.from_url(
                            video_url, 
                            loop=self.bot.loop, 
                            stream=True,
                            volume=0.5
                        )
                        
                        # Dodaj dodatkowe informacje
                        player.requester = ctx.author
                        
                        # Dodaj do kolejki
                        self.queues[ctx.guild.id].append(player)
                        added_count += 1
                    except Exception as e:
                        logger.error(f"Błąd podczas dodawania utworu {video_url} do kolejki: {e}")
                        failed_count += 1
                
                # Daj czas na inne operacje asyncio
                await asyncio.sleep(0.1)
            
            # Wyświetl podsumowanie
            message = f"✅ Dodano **{added_count}** utworów do kolejki"
            if duplicate_count > 0:
                message += f", **{duplicate_count}** duplikatów pominięto"
            if failed_count > 0:
                message += f", **{failed_count}** nie udało się załadować"
            await ctx.send(message)
            
            # Rozpocznij odtwarzanie, jeśli nic nie jest odtwarzane
            if ctx.voice_client and not ctx.voice_client.is_playing():
                await self._play_next(ctx)
                
        except Exception as e:
            logger.error(f"Błąd podczas dodawania playlisty: {e}")
            await ctx.send(f"❌ Wystąpił błąd podczas dodawania playlisty: {str(e)}")


async def _queue(self, ctx):
    """
    Wyświetla aktualną kolejkę utworów z paginacją.
    """
    guild_id = ctx.guild.id
    
    # Sprawdź, czy kolejka istnieje
    if guild_id not in self.queues or not self.queues[guild_id]:
        # Jeśli jest coś odtwarzane, pokaż to
        if guild_id in self.now_playing and self.now_playing[guild_id]:
            player = self.now_playing[guild_id]
            embed = discord.Embed(
                title="🎵 Aktualnie odtwarzane",
                description=f"[{player.title}]({player.url})",
                color=discord.Color.blue()
            )
            
            # Dodaj miniaturę utworu
            if player.thumbnail:
                embed.set_thumbnail(url=player.thumbnail)
            
            # Dodaj informacje o utworze
            embed.add_field(name="Twórca", value=player.uploader, inline=True)
            embed.add_field(name="Czas trwania", value=player.duration, inline=True)
            embed.add_field(name="Na prośbę", value=player.requester.mention, inline=True)
            
            embed.set_footer(text="Kolejka jest pusta.")
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Kolejka jest pusta i nic nie jest odtwarzane!")
        return
    
    # Przygotuj zawartość kolejki do wyświetlenia z paginacją
    queue = self.queues[guild_id]
    items_per_page = 10
    pages = []
    
    # Oblicz liczbę stron
    page_count = math.ceil(len(queue) / items_per_page)
    
    # Utwórz stronę dla każdej części kolejki
    for page_num in range(page_count):
        start_idx = page_num * items_per_page
        end_idx = start_idx + items_per_page
        page_items = queue[start_idx:end_idx]
        
        embed = discord.Embed(
            title=f"📋 Kolejka utworów - {guild_id}",
            color=discord.Color.blue()
        )
        
        # Dodaj informacje o aktualnie odtwarzanym utworze, jeśli istnieje
        if guild_id in self.now_playing and self.now_playing[guild_id]:
            player = self.now_playing[guild_id]
            embed.add_field(
                name="🎵 Aktualnie odtwarzane",
                value=f"[{player.title}]({player.url}) | {player.duration} | {player.requester.mention}",
                inline=False
            )
        
        # Dodaj utwory na tej stronie
        tracks_details = []
        for i, track in enumerate(page_items, start=start_idx + 1):
            tracks_details.append(
                f"`{i}.` [{track.title}]({track.url}) | `{track.duration}` | {track.requester.mention}"
            )
        
        # Jeśli mamy utwory na tej stronie, dodaj je
        if tracks_details:
            embed.add_field(
                name=f"Utwory w kolejce",
                value="\n".join(tracks_details),
                inline=False
            )
        
        # Dodaj informacje o stronie
        total_duration = sum(track.duration_raw for track in queue)
        minutes, seconds = divmod(total_duration, 60)
        hours, minutes = divmod(minutes, 60)
        
        # Formatuj czas całkowity
        if hours > 0:
            total_time = f"{hours}h {minutes}m {seconds}s"
        else:
            total_time = f"{minutes}m {seconds}s"
        
        embed.set_footer(text=f"Strona {page_num + 1}/{page_count} • {len(queue)} utworów • Łączny czas: {total_time}")
        
        # Dodaj stronę do listy stron
        pages.append(embed)
    
    # Jeśli mamy tylko jedną stronę, wyślij ją bez paginacji
    if len(pages) == 1:
        await ctx.send(embed=pages[0])
    else:
        # W przeciwnym razie użyj paginatora
        view = QueuePaginator(pages, ctx)
        message = await ctx.send(embed=pages[0], view=view)
        view.message = message


# Funkcja ustawiająca komendy kolejki
def setup_queue_commands(cog):
    """
    Konfiguruje komendy związane z kolejką.
    
    Args:
        cog: Instancja klasy Music
    """
    # Inicjalizuj kolekcje, jeśli nie istnieją
    if not hasattr(cog, 'queues'):
        cog.queues = {}
    
    if not hasattr(cog, 'now_playing'):
        cog.now_playing = {}
    
    if not hasattr(cog, '_queue_history'):
        cog._queue_history = {}
    
    # Przypisz metody do cog
    cog._toggle_repeat = _toggle_repeat.__get__(cog, type(cog))
    cog._playlist = _playlist.__get__(cog, type(cog))
    cog._add_playlist = _add_playlist.__get__(cog, type(cog))
    cog._queue = _queue.__get__(cog, type(cog))
    
    # Alias dla kompatybilności
    cog.queue = cog._queue
    cog.playlist = cog._playlist
    cog.toggle_repeat = cog._toggle_repeat
    
    # Komendy dla modułu queue_manager
    @cog.bot.command(name="remove", aliases=["usun"], help="Usuwa utwór z kolejki")
    @is_dj()
    async def remove_command(ctx, *, index: int):
        """Usuwa utwór z kolejki"""
        guild_id = ctx.guild.id
        
        # Sprawdź czy kolejka istnieje
        if guild_id not in cog.queues or not cog.queues[guild_id]:
            await ctx.send("❌ Kolejka jest pusta!")
            return
        
        # Sprawdź czy indeks jest poprawny
        if index < 1 or index > len(cog.queues[guild_id]):
            await ctx.send(f"⚠️ Podaj poprawny numer utworu (1-{len(cog.queues[guild_id])})!")
            return
        
        # Pobierz utwór do usunięcia
        track = cog.queues[guild_id][index-1]
        
        # Usuń utwór z kolejki
        cog.queues[guild_id].pop(index-1)
        
        # Wyślij potwierdzenie
        await ctx.send(f"✅ Usunięto z kolejki: **{track.title}**")
    
    @cog.bot.command(name="shuffle", aliases=["pomieszaj"], help="Miesza kolejkę utworów")
    @is_dj()
    async def shuffle_command(ctx):
        """Miesza kolejkę utworów"""
        guild_id = ctx.guild.id
        
        # Sprawdź czy kolejka istnieje
        if guild_id not in cog.queues or not cog.queues[guild_id]:
            await ctx.send("❌ Kolejka jest pusta!")
            return
        
        # Zapisz długość kolejki przed mieszaniem
        queue_length = len(cog.queues[guild_id])
        
        # Pomieszaj kolejkę
        import random
        random.shuffle(cog.queues[guild_id])
        
        # Wyślij potwierdzenie
        await ctx.send(f"🔀 Pomieszano {queue_length} utworów w kolejce!")
    
    @cog.bot.command(name="clear_queue", aliases=["wyczysc_kolejke", "clear_music"], help="Czyści kolejkę utworów")
    @is_dj()
    async def clear_command(ctx):
        """Czyści kolejkę utworów"""
        guild_id = ctx.guild.id
        
        # Sprawdź czy kolejka istnieje
        if guild_id not in cog.queues or not cog.queues[guild_id]:
            await ctx.send("❌ Kolejka już jest pusta!")
            return
        
        # Zapisz długość kolejki przed czyszczeniem
        queue_length = len(cog.queues[guild_id])
        
        # Wyczyść kolejkę
        cog.queues[guild_id] = []
        
        # Wyślij potwierdzenie
        await ctx.send(f"🧹 Wyczyszczono kolejkę ({queue_length} utworów)!")
        
    @cog.bot.command(name="move", aliases=["przenies"], help="Przenosi utwór na inną pozycję w kolejce")
    @is_dj()
    async def move_command(ctx, from_pos: int, to_pos: int):
        """Przenosi utwór na inną pozycję w kolejce"""
        guild_id = ctx.guild.id
        
        # Sprawdź czy kolejka istnieje
        if guild_id not in cog.queues or not cog.queues[guild_id]:
            await ctx.send("❌ Kolejka jest pusta!")
            return
        
        # Sprawdź poprawność indeksów (użytkownicy numerują od 1)
        queue_length = len(cog.queues[guild_id])
        if from_pos < 1 or from_pos > queue_length or to_pos < 1 or to_pos > queue_length:
            await ctx.send(f"⚠️ Podaj poprawne numery utworów (1-{queue_length})!")
            return
        
        # Pobierz utwór do przeniesienia
        track = cog.queues[guild_id][from_pos-1]
        
        # Usuń z oryginalnej pozycji
        cog.queues[guild_id].pop(from_pos-1)
        
        # Wstaw na nowej pozycji
        cog.queues[guild_id].insert(to_pos-1, track)
        
        # Wyślij potwierdzenie
        await ctx.send(f"✅ Przeniesiono **{track.title}** z pozycji {from_pos} na {to_pos}!")
    
    return cog