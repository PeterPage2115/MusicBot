import discord
from discord.ext import commands
from datetime import datetime, timedelta
from utils.helpers import YTDLSource, YTDLError
from .utils import is_dj
import asyncio
import traceback
import os
import time
import sys
from config import INACTIVITY_TIMEOUT
from utils.logger import get_logger

# Inicjalizacja loggera
logger = get_logger()

def setup_player_commands(cog):
    """Dodaje komendy związane z odtwarzaniem muzyki do klasy Music"""
    
    # Na początku funkcji setup_player_commands, inicjalizuj wszystkie kolekcje
    if not hasattr(cog, 'inactive_timeout'):
        cog.inactive_timeout = {}
    
    if not hasattr(cog, 'disconnected_sessions'):
        cog.disconnected_sessions = {}
    
    if not hasattr(cog, 'command_channels'):
        cog.command_channels = {}
    
    if not hasattr(cog, 'repeat_mode'):
        cog.repeat_mode = {}
        
    if not hasattr(cog, 'volume_settings'):
        cog.volume_settings = {}
    
    # Definicja funkcji formatującej bajty
    def _format_bytes(size):
        """Formatuje bajty do czytelnej wielkości (KB, MB, GB)."""
        try:
            # Upewnij się, że otrzymujemy liczbę
            size = float(size)
            
            # Sprawdź czy wartość jest dodatnia
            if size <= 0:
                return "0 B"
                
            # Stałe do konwersji
            units = ['B', 'KB', 'MB', 'GB', 'TB']
            power = 1024.0
            n = 0
            
            # Konwersja do czytelnego formatu
            while size >= power and n < len(units) - 1:
                size /= power
                n += 1
                
            return f"{size:.2f} {units[n]}"
        except Exception as e:
            logger.error(f"Błąd podczas formatowania bajtów: {e}")
            return "? B"  # Zwróć wartość zastępczą w przypadku błędu
    
    # Definicja funkcji czyszczenia plików tymczasowych
    async def _cleanup_temp_files(hours=24):
        """
        Czyści pliki tymczasowe, które są starsze niż określona liczba godzin,
        z wyjątkiem plików, które są aktualnie odtwarzane.
        
        Args:
            hours: Maksymalny wiek plików w godzinach
        """
        try:
            temp_dir = 'temp'
            
            # Sprawdź czy katalog istnieje
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
                logger.info(f"Utworzono katalog {temp_dir}")
                return
            
            # Zbierz wszystkie aktualnie odtwarzane pliki ze wszystkich serwerów
            active_files = set()  # Używaj set() dla szybszego sprawdzania członkostwa
            
            # Zbierz pliki z now_playing
            for guild_now_playing in cog.now_playing.values():
                if hasattr(guild_now_playing, 'filename'):
                    active_files.add(guild_now_playing.filename)
                if hasattr(guild_now_playing, 'original_file'):
                    active_files.add(guild_now_playing.original_file)
            
            # Dodaj pliki z kolejek
            for guild_queue in cog.queues.values():
                for track in guild_queue:
                    if hasattr(track, 'filename'):
                        active_files.add(track.filename)
                    if hasattr(track, 'original_file'):
                        active_files.add(track.original_file)

            # Debug info
            logger.debug(f"Aktywne pliki, które nie będą usunięte: {active_files}")
                    
            current_time = time.time()
            max_age_seconds = hours * 3600
            
            # Liczniki statystyk
            removed_count = 0
            error_count = 0
            total_size_removed = 0
            
            # Przetwarzaj pliki w mniejszych porcjach, aby uniknąć blokowania pętli zdarzeń
            files_to_process = os.listdir(temp_dir)
            for i in range(0, len(files_to_process), 20):
                batch = files_to_process[i:i+20]
                
                for filename in batch:
                    file_path = os.path.join(temp_dir, filename)
                    try:
                        # Sprawdź czy to plik (nie katalog)
                        if not os.path.isfile(file_path):
                            continue
                        
                        # Sprawdź czy plik jest używany
                        if file_path in active_files or filename in active_files:
                            logger.debug(f"Pomijam aktywny plik: {file_path}")
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
                        error_count += 1
                        logger.error(f"Błąd podczas próby usunięcia pliku {file_path}: {e}")
                
                # Po każdej porcji, daj czas na inne operacje asyncio
                await asyncio.sleep(0.1)
            
            # Zwróć statystyki
            human_readable_size = _format_bytes(total_size_removed)
            logger.info(f"Czyszczenie plików tymczasowych: usunięto {removed_count} plików ({human_readable_size}), błędów: {error_count}")
        except Exception as e:
            logger.error(f"Błąd podczas czyszczenia plików tymczasowych: {e}")
    
    # Funkcja pomocnicza do czyszczenia plików
    async def cleanup_files():
        """Czyści pliki tymczasowe"""
        await _cleanup_temp_files(24)  # Domyślnie czyści pliki starsze niż 24 godziny
    
    # Funkcja do bezpiecznego czyszczenia pamięci podręcznej
    async def _cleancache(ctx):
        """Czyści pliki tymczasowe z katalogu temp"""
        try:
            await ctx.send("Rozpoczynam czyszczenie plików tymczasowych...")
            
            # Wywołaj czyszczenie plików tymczasowych
            await _cleanup_temp_files(24)  # Domyślnie 24 godziny
            
            # Powiadomienie o zakończeniu
            await ctx.send("✅ Czyszczenie plików tymczasowych zakończone.")
        except Exception as e:
            await ctx.send(f"Wystąpił błąd podczas czyszczenia plików tymczasowych: {str(e)}")
    
    # Definicje funkcji zarządzania głośnością
    async def _get_volume(guild_id):
        """Bezpieczne pobieranie głośności dla danego serwera"""
        # Sprawdź czy istnieje ustawienie dla tego serwera
        if guild_id in cog.volume_settings:
            return cog.volume_settings[guild_id]
        # Jeśli nie, użyj domyślnej wartości
        return cog.volume_value
    
    async def _set_volume(ctx, volume_float):
        """Bezpieczne ustawianie głośności dla danego serwera"""
        guild_id = ctx.guild.id
        
        try:
            # Upewnij się, że value jest liczbą zmiennoprzecinkową
            volume_float = float(volume_float)
            
            # Zapisz głośność dla serwera
            cog.volume_settings[guild_id] = volume_float
            
            # Ustaw podstawową wartość volume_value dla kompatybilności
            cog.volume_value = volume_float
            
            # Ustaw głośność na aktualnym źródle dźwięku, jeśli istnieje
            if ctx.voice_client and ctx.voice_client.source:
                ctx.voice_client.source.volume = volume_float
                
            return True, None  # Sukces, brak błędu
        except ValueError:
            return False, "Nieprawidłowa wartość głośności."
        except Exception as e:
            traceback.print_exc()
            return False, f"Wystąpił błąd: {str(e)}"
    
    # Uproszczona i poprawiona funkcja _play next

    async def _play_next(ctx):
        """
        Odtwarza następny utwór z kolejki.
        
        Args:
            ctx: Kontekst komendy
        """
        guild_id = ctx.guild.id
        
        # Dodajmy informacje diagnostyczne
        logger.debug(f"Wywołanie _play_next dla {guild_id}")
        
        try:
            # 1. Sprawdź czy bot jest połączony z kanałem głosowym
            if not ctx.voice_client or not ctx.voice_client.is_connected():
                logger.warning(f"_play_next: Bot nie jest połączony z kanałem głosowym dla {guild_id}")
                return
            
            # 2. Upewnij się, że mamy kolejkę dla tego serwera
            if guild_id not in cog.queues:
                logger.debug(f"_play_next: Inicjalizacja pustej kolejki dla {guild_id}")
                cog.queues[guild_id] = []
            
            # 3. Sprawdź czy kolejka jest pusta
            if not cog.queues[guild_id]:
                logger.debug(f"_play_next: Kolejka jest pusta dla {guild_id}")
                
                # 3.1 Sprawdź tryb powtarzania
                repeat_mode = cog.repeat_mode.get(guild_id, 0)
                
                if repeat_mode == 1 and guild_id in cog.now_playing and cog.now_playing[guild_id]:
                    # Powtarzamy ten sam utwór
                    player = cog.now_playing[guild_id]
                    logger.info(f"_play_next: Powtarzanie utworu: {player.title}")
                    
                    # Ponownie dodaj utwór do kolejki
                    cog.queues[guild_id].append(player)
                    
                elif repeat_mode == 2 and hasattr(cog, '_queue_history') and guild_id in cog._queue_history and cog._queue_history[guild_id]:
                    # Powtarzamy całą kolejkę
                    history_length = len(cog._queue_history[guild_id])
                    logger.info(f"_play_next: Powtarzanie całej kolejki ({history_length} utworów)")
                    
                    # Głęboka kopia kolejki historii
                    cog.queues[guild_id] = []
                    for track in cog._queue_history[guild_id]:
                        cog.queues[guild_id].append(track)
                    
                else:
                    # Kolejka jest pusta i nie ma powtarzania
                    logger.info(f"_play_next: Kolejka pusta dla {guild_id}, zakończono odtwarzanie")
                    
                    # Wyczyść informację o aktualnie odtwarzanym
                    if guild_id in cog.now_playing:
                        cog.now_playing[guild_id] = None
                    
                    # Wyślij komunikat o pustej kolejce
                    await ctx.send("Kolejka jest pusta. Odtwarzanie zakończone.")
                    return
            
            # 4. Sprawdź, czy voice_client już odtwarza muzykę
            if ctx.voice_client.is_playing():
                logger.warning(f"_play_next: VoiceClient już odtwarza dźwięk dla {guild_id}, zatrzymuję odtwarzanie")
                ctx.voice_client.stop()
            
            # 5. Pobierz następny utwór z kolejki
            player = cog.queues[guild_id].pop(0)
            logger.debug(f"_play_next: Pobrano utwór z kolejki: {player.title}")
            
            # 6. Zapisz informację o aktualnie odtwarzanym utworze
            cog.now_playing[guild_id] = player
            
            logger.info(f"_play_next: Odtwarzanie utworu: {player.title}")
            
            # 7. Funkcja wywoływana po zakończeniu odtwarzania
            def after_playing(error):
                logger.debug(f"after_playing: Wywołano po zakończeniu odtwarzania")
                
                if error:
                    logger.error(f"after_playing: Błąd odtwarzania: {error}")
                
                # WAŻNE: Używamy call_later, aby opóźnić wywołanie _play_next
                # To zapobiega zbyt szybkiemu wywołaniu lub konfliktom
                cog.bot.loop.call_later(0.5, lambda: 
                    asyncio.run_coroutine_threadsafe(_play_next(ctx), cog.bot.loop)
                )
            
            # 8. Odtwórz utwór
            try:
                ctx.voice_client.play(player, after=after_playing)
                
                # 9. Ustawiamy głośność
                try:
                    # Pobierz właściwą głośność dla tego serwera
                    if guild_id in cog.volume_settings:
                        volume = cog.volume_settings[guild_id]
                    else:
                        volume = getattr(cog, 'volume_value', 0.5)
                    
                    ctx.voice_client.source.volume = float(volume)
                except Exception as e:
                    logger.error(f"_play_next: Błąd podczas ustawiania głośności: {e}")
                    ctx.voice_client.source.volume = 0.5
                    
                # 10. Wyślij informację o aktualnie odtwarzanym utworze
                await cog._send_now_playing_embed(ctx)
                    
            except Exception as e:
                logger.error(f"_play_next: Błąd podczas odtwarzania: {e}")
                await ctx.send(f"❌ Wystąpił błąd podczas odtwarzania: {str(e)}")
                
                # Spróbuj odtworzyć następny utwór w przypadku błędu
                if guild_id in cog.queues and cog.queues[guild_id]:
                    await asyncio.sleep(1)  # Małe opóźnienie
                    await _play_next(ctx)
                
        except Exception as e:
            logger.error(f"_play_next: Ogólny błąd w funkcji: {e}")
            import traceback
            traceback.print_exc()
            await ctx.send(f"❌ Wystąpił nieoczekiwany błąd: {str(e)}")
    
    # Funkcja timera nieaktywności
    async def _start_inactivity_timer(self, ctx):
        """Rozpoczyna timer nieaktywności, po którym bot opuści kanał głosowy"""
        
        guild_id = ctx.guild.id
        
        # Anuluj poprzedni timer, jeśli istnieje
        if hasattr(self, 'inactive_timeout') and guild_id in self.inactive_timeout:
            try:
                self.inactive_timeout[guild_id].cancel()
                logger.debug(f"Anulowano poprzedni timer nieaktywności dla {guild_id}")
            except Exception as e:
                logger.error(f"Błąd podczas anulowania timera nieaktywności: {e}")
        
        # Inicjalizuj słownik timerów, jeśli nie istnieje
        if not hasattr(self, 'inactive_timeout'):
            self.inactive_timeout = {}
            
        # Jeśli timeout jest wyłączony (0), to nie uruchamiaj timera
        if INACTIVITY_TIMEOUT <= 0:
            return
            
        # Funkcja, która zostanie wywołana po timeoucie
        async def leave_after_timeout():
            try:
                # Czekamy określony czas
                await asyncio.sleep(INACTIVITY_TIMEOUT)
                
                # Double-check czy bot nadal istnieje (linie 460-462)
                if not hasattr(self, 'bot') or not self.bot:
                    logger.warning(f"Bot nie jest dostępny podczas sprawdzania timera dla {guild_id}")
                    return
                    
                # Pobierz voice_client dla tego serwera
                voice_client = discord.utils.get(self.bot.voice_clients, guild__id=guild_id)
                
                # Sprawdź, czy bot nadal jest na kanale głosowym i czy nie odtwarza muzyki
                if (
                    voice_client and voice_client.is_connected() and
                    (not voice_client.is_playing()) and (not voice_client.is_paused())
                ):
                    # Zachowanie kiedy timer upłynął (linie 473-485)
                    logger.info(f"Timer nieaktywności upłynął dla {guild_id}, rozłączanie...")
                    
                    # Bezpiecznie rozłącz
                    try:
                        await voice_client.disconnect()
                        logger.info(f"Rozłączono z kanału głosowego w {guild_id} z powodu nieaktywności")
                    except Exception as e:
                        logger.error(f"Błąd podczas rozłączania: {e}")
                    
                    # Czyścimy kolejkę i inne dane dla tego serwera
                    if guild_id in self.queues:
                        del self.queues[guild_id]
                    if guild_id in self.now_playing:
                        del self.now_playing[guild_id]
                    
                    # Wyślij informację o rozłączeniu
                    if hasattr(self, 'command_channels') and guild_id in self.command_channels:
                        channel = self.command_channels[guild_id]
                        try:
                            await channel.send("Opuszczam kanał głosowy z powodu braku aktywności.")
                        except Exception as e:
                            logger.error(f"Nie można wysłać informacji o rozłączeniu: {e}")
                else:
                    # Bot nadal odtwarza muzykę lub został ręcznie rozłączony - nie robimy nic
                    if voice_client and voice_client.is_playing():
                        logger.debug(f"Timer nieaktywności upłynął, ale bot nadal odtwarza muzykę dla {guild_id}")
                    elif not (voice_client and voice_client.is_connected()):
                        logger.debug(f"Timer nieaktywności upłynął, ale bot nie jest już połączony dla {guild_id}")
            except asyncio.CancelledError:
                # Timer został anulowany, co jest normalne gdy zaczyna się nowy utwór
                logger.debug(f"Timer nieaktywności anulowany dla {guild_id}")
            except Exception as e:
                logger.error(f"Błąd w timerze nieaktywności: {e}")
        
        # Rozpocznij timer
        try:
            self.inactive_timeout[guild_id] = asyncio.create_task(leave_after_timeout())
            logger.debug(f"Rozpoczęto nowy timer nieaktywności dla {guild_id}")
        except Exception as e:
            logger.error(f"Nie udało się utworzyć timera nieaktywności: {e}")
    
    # Obserwator stanu połączenia głosowego - przeniesiony z globalnego zakresu
    async def on_voice_state_update(self, member, before, after):
        """Obsługa zmian statusu połączenia głosowego."""
        
        try:
            # Jeśli to nie jest bot, sprawdź czy ludzie opuścili kanał
            if member.id != self.bot.user.id and before.channel != after.channel:
                # Jeśli ktoś opuścił kanał, na którym jest bot
                if before.channel and any(m.id == self.bot.user.id for m in before.channel.members):
                    # Sprawdź, czy bot jest teraz sam na kanale (tylko boty)
                    human_members = [m for m in before.channel.members if not m.bot]
                    if not human_members:
                        guild_id = before.channel.guild.id
                        logger.info(f"Bot został sam na kanale w {guild_id}. Rozpoczynam odliczanie do rozłączenia.")
                        
                        # Stwórz tymczasowy kontekst
                        class TempContext:
                            def __init__(self, guild):
                                self.guild = guild
                        
                        # Stwórz tymczasowy kontekst i uruchom timer
                        temp_ctx = TempContext(before.channel.guild)
                        await self._start_inactivity_timer(temp_ctx)
            
            # Jeśli bot został rozłączony (np. wyrzucony ręcznie przez kogoś)
            if member.id == self.bot.user.id and before.channel and not after.channel:
                guild_id = before.channel.guild.id
                logger.info(f"Bot został rozłączony z kanału w {guild_id}")
                
                # Anuluj timer nieaktywności, jeśli istnieje
                if hasattr(self, 'inactive_timeout') and guild_id in self.inactive_timeout:
                    try:
                        self.inactive_timeout[guild_id].cancel()
                        logger.debug(f"Anulowano timer nieaktywności po rozłączeniu dla {guild_id}")
                    except Exception as e:
                        logger.error(f"Błąd podczas anulowania timera po rozłączeniu: {e}")
                
                # Zapisz informacje o sesji, która została przerwana
                self.disconnected_sessions = {}
                
                # Zapisz informacje tylko jeśli jest co zapisać
                self.disconnected_sessions[guild_id] = {
                    'now_playing': self.now_playing[guild_id],
                    'queue': self.queues.get(guild_id, []).copy(), # Używamy copy aby uniknąć referencji
                    'channel_id': before.channel.id,
                    'timestamp': datetime.now()
                }
                
                # Jeśli mamy zapisany kanał tekstowy, wyślij powiadomienie
                if hasattr(self, 'command_channels') and guild_id in self.command_channels:
                    try:
                        channel = self.command_channels[guild_id]
                        await channel.send("⚠️ Zostałem odłączony od kanału głosowego. Użyj `%reconnect` aby przywrócić sesję.")
                    except Exception as e:
                        logger.error(f"Nie udało się wysłać powiadomienia o rozłączeniu: {e}")
        except Exception as e:
            logger.error(f"Błąd w obsłudze zmian statusu głosowego: {e}")
            traceback.print_exc()
    
    # Komenda dołączania do kanału
    async def _join(self, ctx):
        """Komenda dołączająca bota do kanału głosowego użytkownika"""
        
        if ctx.author.voice is None:
            await ctx.send("Musisz być na kanale głosowym, aby użyć tej komendy!")
            return False
            
        if ctx.voice_client is not None:
            await ctx.voice_client.move_to(ctx.author.voice.channel)
            await ctx.send(f"Przeniesiono na kanał {ctx.author.voice.channel.mention}")
            return True
        else:
            await ctx.author.voice.channel.connect()
            await ctx.send(f"Dołączono do kanału {ctx.author.voice.channel.mention}")
            return True
    
    # Komenda opuszczania kanału
    async def _leave(ctx):
        """Komenda rozłączająca bota z kanału głosowego"""
        
        if ctx.voice_client is None:
            await ctx.send("Nie jestem połączony z żadnym kanałem głosowych!")
            return
            
        await ctx.voice_client.disconnect()
        await ctx.send("Rozłączono z kanałem głosowym.")
        
        # Czyścimy dane dla tego serwera
        guild_id = ctx.guild.id
        if guild_id in cog.queues:
            del cog.queues[guild_id]
        if guild_id in cog.now_playing:
            del cog.now_playing[guild_id]
        
        # Czyścimy pliki tymczasowe
        await cleanup_files()  # Używamy lokalnej funkcji
    
    # Komenda odtwarzania
    async def _play(self, ctx, *, query=None):
        """
        Uproszczona wersja funkcji odtwarzania do debugowania.
        
        Args:
            ctx: Kontekst komendy
            query: Link lub fraza wyszukiwania
        """
        try:
            guild_id = ctx.guild.id
            
            # Upewnij się, że bot jest na kanale głosowym
            if ctx.voice_client is None:
                if ctx.author.voice:
                    await ctx.author.voice.channel.connect()
                    await ctx.send(f"Dołączono do kanału {ctx.author.voice.channel.mention}")
                else:
                    await ctx.send("❌ Nie jesteś połączony z kanałem głosowym!")
                    return
            
            # Sprawdź czy podano zapytanie
            if not query:
                await ctx.send("⚠️ Podaj tytuł utworu lub link!")
                return
            
            # Zatrzymaj aktualnie odtwarzany dźwięk, jeśli istnieje
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
                await ctx.send("Zatrzymuję aktualnie odtwarzany utwór...")
            
            # Wyszukiwanie
            await ctx.send(f"🔍 Wyszukuję: `{query}`...")
            
            # Pobierz utwór
            try:
                from utils.helpers import YTDLSource
                player = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True)
                await ctx.send(f"✅ Znaleziono: **{player.title}**")
            except Exception as e:
                await ctx.send(f"❌ Błąd wyszukiwania: {str(e)}")
                import traceback
                traceback.print_exc()
                return
            
            # Funkcja wywoływana po zakończeniu odtwarzania
            def after_playing(error):
                if error:
                    print(f"ERROR in after_playing: {error}")
                    asyncio.run_coroutine_threadsafe(
                        ctx.send(f"❌ Błąd odtwarzania: {error}"), 
                        self.bot.loop
                    )
                else:
                    print("Playback completed normally")
                    asyncio.run_coroutine_threadsafe(
                        ctx.send("✅ Odtwarzanie zakończone!"), 
                        self.bot.loop
                    )
            
            # Rozpocznij odtwarzanie
            await ctx.send("▶️ Rozpoczynam odtwarzanie...")
            ctx.voice_client.play(player, after=after_playing)
            
            # Ustaw głośność
            ctx.voice_client.source.volume = 0.5
            
            # Zapisz informacje do kontekstu bota
            self.now_playing[guild_id] = player
            if guild_id not in self.queues:
                self.queues[guild_id] = []
            
        except Exception as e:
            await ctx.send(f"❌ Nieoczekiwany błąd: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Komenda wstrzymywania odtwarzania
    async def _pause(self, ctx):
        """Komenda wstrzymująca odtwarzanie"""
        
        if ctx.voice_client is None or not ctx.voice_client.is_playing():
            await ctx.send("Nie odtwarzam teraz żadnej muzyki!")
            return
        
        ctx.voice_client.pause()
        
        # Dodajmy informacje o aktualnie wstrzymanym utworze
        if ctx.guild.id in self.now_playing:
            track = self.now_playing[ctx.guild.id]
            await ctx.send(f"⏸️ Odtwarzanie wstrzymane: **{track.title}**")
        else:
            await ctx.send("Odtwarzanie wstrzymane.")
    
    # Komenda wznawiania odtwarzania
    async def _resume(self, ctx):
        """Komenda wznawiająca odtwarzanie"""
        
        if ctx.voice_client is None:
            await ctx.send("Nie jestem połączony z kanałem głosowym!")
            return
            
        if not ctx.voice_client.is_paused():
            await ctx.send("Odtwarzanie nie jest wstrzymane!")
            return
            
        ctx.voice_client.resume()
        await ctx.send("▶️ Odtwarzanie wznowione.")
    
    # Komenda zatrzymywania
    async def _stop(self, ctx):
        """Komenda zatrzymująca odtwarzanie i czyszcząca kolejkę"""
        
        if ctx.voice_client is None:
            await ctx.send("Nie jestem połączony z kanałem głosowym!")
            return
            
        # Czyścimy kolejkę
        if ctx.guild.id in self.queues:
            self.queues[ctx.guild.id] = []
            
        # Zatrzymujemy odtwarzanie
        ctx.voice_client.stop()
        await ctx.send("🛑 Odtwarzanie zatrzymane i kolejka wyczyszczona.")
        
        # Czyścimy pliki tymczasowe
        await cleanup_files()  # Używamy lokalnej funkcji
    
    # Komenda pomijania utworu
    async def _skip(self, ctx):
        """Komenda pomijająca aktualny utwór"""
        
        if ctx.voice_client is None:
            await ctx.send("Nie jestem połączony z kanałem głosowym!")
            return
            
        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await ctx.send("Nic teraz nie gram!")
            return
            
        # Zatrzymujemy aktualny utwór, co automatycznie uruchomi następny
        ctx.voice_client.stop()
        await ctx.send("⏭️ Pomijam utwór.")
    
    # Komenda ustawiania głośności
    async def _volume(self, ctx, *, volume_str: str):
        """Komenda ustawiająca głośność odtwarzania"""
        
        if ctx.voice_client is None:
            await ctx.send("Nie jestem połączony z żadnym kanałem głosowych!")
            return
            
        # Sprawdzamy, czy podano wartość głośności
        try:
            # Obsługa różnych formatów wejściowych (przecinek/kropka)
            volume_str = volume_str.replace(',', '.')
            volume = float(volume_str)
        except ValueError:
            await ctx.send("Podaj wartość głośności od 1 do 100!")
            return
            
        # Sprawdzamy, czy wartość jest w prawidłowym zakresie
        if volume < 1 or volume > 100:
            await ctx.send("Głośność musi być od 1 do 100!")
            return
            
        # Ustawiamy głośność (Discord używa wartości od 0.0 do 1.0)
        volume_float = volume / 100.0
        
        success, error = await _set_volume(ctx, volume_float)
        
        if success:
            await ctx.send(f"🔊 Głośność ustawiona na {int(volume)}%")
        else:
            await ctx.send(f"❌ Nie udało się ustawić głośności: {error}")
    
    # Dodaj po funkcji _volume
    async def _toggle_repeat(self, ctx):
        """Przełącza tryb powtarzania między: wyłączony, utwór, kolejka"""
        guild_id = ctx.guild.id
        
        # Pobierz aktualny tryb powtarzania
        current_mode = self.repeat_mode.get(guild_id, 0)
        
        # Przełącz na następny tryb (0 -> 1 -> 2 -> 0)
        new_mode = (current_mode + 1) % 3
        self.repeat_mode[guild_id] = new_mode
        
        # Wyślij informację o zmianie trybu
        if new_mode == 0:
            await ctx.send("🔄 Powtarzanie **wyłączone**")
        elif new_mode == 1:
            await ctx.send("🔂 Powtarzanie **bieżącego utworu** włączone")
        else:  # new_mode == 2
            await ctx.send("🔁 Powtarzanie **całej kolejki** włączone")
    
    # Funkcja ponownego połączenia
    async def _reconnect(ctx):
        """Próbuje przywrócić ostatnią sesję muzyczną po rozłączeniu."""
        guild_id = ctx.guild.id
        
        # Sprawdź, czy autor komendy jest na kanale głosowym
        if not ctx.author.voice:
            await ctx.send("Musisz być na kanale głosowym, aby mnie połączyć!")
            return
        
        # Sprawdź, czy bot jest już połączony
        if ctx.voice_client and ctx.voice_client.is_connected():
            await ctx.send("Już jestem połączony z kanałem głosowym!")
            return
        
        # Sprawdź, czy mamy zapisaną sesję dla tego serwera
        if hasattr(cog, 'disconnected_sessions') and guild_id in cog.disconnected_sessions:
            session = cog.disconnected_sessions[guild_id]
            
            # Sprawdź, czy sesja nie jest za stara (np. 30 minut)
            max_age = 30  # w minutach
            if (datetime.now() - session['timestamp']) > timedelta(minutes=max_age):
                await ctx.send(f"Zapisana sesja jest starsza niż {max_age} minut i nie może być przywrócona.")
                del cog.disconnected_sessions[guild_id]
                await ctx.author.voice.channel.connect()
                return
            
            # Próba połączenia
            try:
                await ctx.author.voice.channel.connect()
                
                # Przywróć kolejkę
                if not guild_id in cog.queues:
                    cog.queues[guild_id] = []
                
                # Przywróć zapisaną kolejkę
                cog.queues[guild_id] = session['queue']
                
                await ctx.send(f"✅ Przywrócono sesję muzyczną z {len(session['queue'])} utworami w kolejce.")
                
                # Rozpocznij odtwarzanie
                if session['now_playing']:
                    # Dodaj aktualnie odtwarzany utwór na początek kolejki
                    cog.queues[guild_id].insert(0, session['now_playing'])
                    
                # Usuń zapisaną sesję
                del cog.disconnected_sessions[guild_id]
                
                # Uruchom odtwarzanie, jeśli kolejka nie jest pusta
                if cog.queues.get(guild_id, []):
                    await cog._play_next(ctx)
            except Exception as e:
                logger.error(f"Błąd podczas przywracania sesji: {e}")
                await ctx.send(f"Wystąpił błąd podczas przywracania sesji: {str(e)}")
        else:
            # Brak zapisanej sesji, po prostu połącz
            try:
                await ctx.author.voice.channel.connect()
                await ctx.send(f"✅ Połączono z kanałem głosowym: {ctx.author.voice.channel.name}")
            except Exception as e:
                logger.error(f"Nie udało się połączyć z kanałem głosowym: {e}")
                await ctx.send(f"Nie udało się połączyć z kanałem głosowym: {str(e)}")

    async def _nowplaying(ctx):
        """Wyświetla informacje o aktualnie odtwarzanym utworze"""
        
        if ctx.voice_client is None or not ctx.voice_client.is_playing():
            await ctx.send("Nie odtwarzam teraz żadnej muzyki!")
            return
            
        # Wywołaj funkcję wyświetlającą informacje o utworze zdefiniowaną w ui.py
        await cog._send_now_playing_embed(ctx)
    
    # Przypisanie funkcji do klasy cog
    cog._get_volume = _get_volume
    cog._set_volume = _set_volume
    cog._play_next = _play_next
    cog._format_bytes = _format_bytes
    cog._cleanup_temp_files = _cleanup_temp_files
    cog.cleanup_files = cleanup_files
    cog._cleancache = _cleancache

    # Funkcje z self konwertowane do metod
    cog._start_inactivity_timer = _start_inactivity_timer.__get__(cog, type(cog))
    cog.on_voice_state_update = on_voice_state_update.__get__(cog, type(cog))
    cog.join = _join.__get__(cog, type(cog))
    cog.play = _play.__get__(cog, type(cog))
    cog.pause = _pause.__get__(cog, type(cog))
    cog.resume = _resume.__get__(cog, type(cog))
    cog.nowplaying = _nowplaying.__get__(cog, type(cog))  # Dodaj tę linię

    # Przypisanie funkcji obsługujących komendy z ctx
    cog.leave = _leave
    cog.stop = _stop
    cog.skip = _skip
    cog.volume = _volume.__get__(cog, type(cog))  # Ta funkcja potrzebuje __get__
    cog.cleancache = _cleancache.__get__(cog, type(cog))
    cog.reconnect = _reconnect
    cog.toggle_repeat = _toggle_repeat.__get__(cog, type(cog))

    return cog
