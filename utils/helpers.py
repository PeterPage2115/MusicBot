import asyncio
import functools
import discord
import yt_dlp
import re
import time
import os
import random
import traceback
from typing import Dict, List, Optional, Tuple, Union
from utils.logger import get_logger

# Inicjalizacja loggera
logger = get_logger("youtube")

# Stałe, które pomogą z ponownymi próbami
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # sekundy, będzie zwiększane wykładniczo

# Opcje yt-dlp zoptymalizowane dla stabilności i jakości
ytdl_options = {
    'format': 'bestaudio/best',
    'outtmpl': 'temp/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,  # Zmieniamy na True dla produkcji
    'no_warnings': True,  # Zmieniamy na True dla produkcji
    'default_search': 'ytsearch',  # Wymuszenie używania ytsearch
    'source_address': '0.0.0.0',
    'socket_timeout': 15,  
    'retries': 10,
    'extractor_retries': 5,
    'skip_download': True,  # Tylko streamowanie
    # Unikamy niepotrzebnych ekstraktorów
    'extractor_args': {
        'youtube': {
            'skip': ['dash', 'hls'],  # Pomijamy formaty, które mogą powodować problemy
        },
    },
    # Cookiefile dla obsługi ograniczeń wieku (opcjonalne)
    # 'cookiefile': 'youtube-cookies.txt',
}

# Opcje FFmpeg dla lepszej stabilności
ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 10 -nostdin -rw_timeout 15000000',
    'options': '-vn -loglevel warning'
}

# Klasa do obsługi błędów YT-DLP
class YTDLError(Exception):
    """Niestandardowy wyjątek dla błędów związanych z YT-DLP"""
    pass

class YTDLSource(discord.PCMVolumeTransformer):
    """
    Klasa źródła PCMVolumeTransformer do odtwarzania audio z YouTube.
    Zawiera zaawansowane mechanizmy odtwarzania i obsługi błędów.
    """
    # Inicjalizujemy yt-dlp jednorazowo z opcjami
    ytdl = yt_dlp.YoutubeDL(ytdl_options)

    def __init__(self, source, *, data, volume=0.5):
        """Inicjalizacja źródła audio"""
        super().__init__(source, volume)

        # Podstawowe informacje o utworze
        self.data = data
        self.id = data.get('id')
        self.title = data.get('title', 'Unknown')
        self.url = data.get('webpage_url', f'https://www.youtube.com/watch?v={self.id}')
        
        # Dodatkowe metadane
        self.uploader = data.get('uploader', 'Unknown')
        self.uploader_url = data.get('uploader_url', None)
        self.thumbnail = data.get('thumbnail', 'https://i.imgur.com/3wVhixV.png')  # Domyślna miniatura
        self.description = data.get('description', 'No description')
        self.duration_raw = int(data.get('duration', 0))
        self.duration = self._format_duration(self.duration_raw)
        self.tags = data.get('tags', [])
        self.views = data.get('view_count', 0)
        self.likes = data.get('like_count', 0)
        self.stream_url = data.get('url')
        self.original_file = data.get('original_file', None)

    def __str__(self):
        """Reprezentacja tekstowa utworu"""
        return f'**{self.title}** by **{self.uploader}**'

    def _format_duration(self, duration):
        """Formatuje czas trwania w sekundach do czytelnej postaci."""
        if not duration:
            return "00:00"
            
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True, volume=0.5, retry_count=0):
        """
        Tworzy źródło audio na podstawie URL lub zapytania wyszukiwania.
        
        Args:
            url: Link YouTube lub fraza wyszukiwania
            loop: Pętla asyncio do wykonania operacji
            stream: Czy streamować (True) czy pobierać (False)
            volume: Początkowa głośność (0.0-1.0)
            retry_count: Liczba już wykonanych prób (dla rekurencji)
            
        Returns:
            YTDLSource: Obiekt źródła audio
        """
        loop = loop or asyncio.get_event_loop()

        # Sprawdź czy przekroczono limit prób
        if retry_count >= MAX_RETRIES:
            raise YTDLError(f"Nie udało się przetworzyć {url} po {MAX_RETRIES} próbach.")

        # Modyfikuj opcje na podstawie parametru stream
        ytdl_opts = dict(ytdl_options)
        if not stream:
            ytdl_opts['format'] = 'bestaudio/best'
            ytdl_opts['skip_download'] = False
        else:
            ytdl_opts['format'] = 'bestaudio/best'
            ytdl_opts['skip_download'] = True

        try:
            # Logujemy próbę
            logger.info(f"Próba {retry_count+1}/{MAX_RETRIES} pobierania informacji: {url}")
            
            # Tworzymy funkcję częściową do wykonania przez executor
            partial = functools.partial(cls.ytdl.extract_info, url, download=not stream)
            
            # Wykonujemy z timeout
            data = await asyncio.wait_for(
                loop.run_in_executor(None, partial), 
                timeout=30.0  # 30 sekund timeout
            )

            # Jeśli to wynik wyszukiwania, weź pierwszy element
            if 'entries' in data:
                # Pobierz pierwszy element z listy wyników
                if not data['entries']:
                    raise YTDLError("Nie znaleziono wyników wyszukiwania.")
                data = data['entries'][0]

            # Zwróć plik jeśli pobieramy lokalnie
            if not stream:
                file_path = cls.ytdl.prepare_filename(data)
                return cls(discord.FFmpegPCMAudio(file_path, **ffmpeg_options), data=data, volume=volume)
            else:
                # Twórz jako stream
                return cls(discord.FFmpegPCMAudio(data['url'], **ffmpeg_options), data=data, volume=volume)

        except asyncio.TimeoutError:
            # Timeout podczas pobierania informacji
            logger.warning(f"Timeout podczas pobierania informacji o {url}")
            
            # Exponential backoff
            retry_delay = RETRY_DELAY_BASE * (2 ** retry_count) + random.uniform(0, 1)
            logger.info(f"Oczekiwanie {retry_delay:.2f}s przed ponowną próbą...")
            await asyncio.sleep(retry_delay)
            
            # Rekurencyjnie spróbuj ponownie
            return await cls.from_url(url, loop=loop, stream=stream, volume=volume, retry_count=retry_count+1)
            
        except Exception as e:
            # Analizujemy błąd
            error_message = str(e)
            
            # Sprawdzamy typowe błędy YouTube i dodajemy instrukcje
            if "Sign in to confirm your age" in error_message:
                raise YTDLError("Ten film ma ograniczenie wiekowe i wymaga zalogowania do YouTube.")
            elif "The uploader has not made this video available" in error_message:
                raise YTDLError("Ten film nie jest dostępny w Twojej lokalizacji.")
            elif "Video unavailable" in error_message:
                raise YTDLError("Ten film nie jest już dostępny na YouTube.")
            
            # Dla błędów związanych z siecią lub chwilową niedostępnością, spróbuj ponownie
            if retry_count < MAX_RETRIES:
                logger.warning(f"Błąd podczas pobierania {url}: {e}")
                logger.info(f"Próba {retry_count+1}/{MAX_RETRIES}, ponowne próbowanie...")
                
                # Exponential backoff
                retry_delay = RETRY_DELAY_BASE * (2 ** retry_count) + random.uniform(0, 1)
                await asyncio.sleep(retry_delay)
                
                # Przy kolejnych próbach możemy zmienić strategię
                if retry_count == 1:
                    # Przy drugiej próbie zresetuj cache
                    logger.info("Czyszczenie cache yt-dlp...")
                    cls.ytdl.cache.remove()
                elif retry_count >= 2:
                    # Przy trzeciej próbie zmień format na mniej wymagający
                    logger.info("Próba z niższą jakością audio...")
                    ytdl_opts['format'] = 'worstaudio'
                    cls.ytdl = yt_dlp.YoutubeDL(ytdl_opts)
                
                # Rekurencyjnie spróbuj ponownie
                return await cls.from_url(url, loop=loop, stream=stream, volume=volume, retry_count=retry_count+1)
            else:
                # Jeśli wykorzystaliśmy wszystkie próby, zgłaszamy szczegółowy błąd
                logger.error(f"Nie udało się przetworzyć {url} po {MAX_RETRIES} próbach: {e}")
                logger.error(traceback.format_exc())
                raise YTDLError(f"Nie udało się przetworzyć filmu: {e}")
                
    @classmethod
    async def search_source(cls, ctx, search: str, *, loop=None, max_results=5, retry_count=0):
        """
        Wyszukuje utwory na YouTube i zwraca listę wyników.
        
        Args:
            ctx: Kontekst komendy
            search: Fraza wyszukiwania
            loop: Pętla asyncio
            max_results: Maksymalna liczba wyników
            retry_count: Liczba już wykonanych prób
            
        Returns:
            List[Dict]: Lista znalezionych utworów
        """
        if retry_count >= MAX_RETRIES:
            raise YTDLError(f"Nie udało się wyszukać '{search}' po {MAX_RETRIES} próbach.")
        
        # Parametry wyszukiwania - lepsze niż domyślne
        search_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',
            'noplaylist': True,
            'extract_flat': 'in_playlist',
            'max_downloads': max_results,
            'retries': 3,
        }
        
        ytdl = yt_dlp.YoutubeDL(search_opts)
        
        try:
            # Dodajemy max_results do zapytania
            search_query = f"ytsearch{max_results}:{search}"
            partial = functools.partial(ytdl.extract_info, search_query, download=False)
            info = await asyncio.wait_for(
                (loop or asyncio.get_event_loop()).run_in_executor(None, partial),
                timeout=15.0  # 15 sekund timeout
            )
            
            if 'entries' not in info:
                raise YTDLError("Nie znaleziono wyników wyszukiwania.")
                
            if not info['entries']:
                raise YTDLError("Nie znaleziono wyników wyszukiwania.")
                
            return info['entries'][:max_results]
            
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"Błąd podczas wyszukiwania '{search}': {e}")
            
            # Exponential backoff
            retry_delay = RETRY_DELAY_BASE * (2 ** retry_count)
            await asyncio.sleep(retry_delay)
            
            # Zmień strategię przy kolejnych próbach
            if retry_count == 1:
                ytdl.cache.remove()  # Wyczyść cache
                
            # Rekurencyjnie spróbuj ponownie
            return await cls.search_source(ctx, search, loop=loop, max_results=max_results, retry_count=retry_count+1)

    @staticmethod
    def format_search_results(results):
        """
        Formatuje wyniki wyszukiwania do czytelnej listy.
        
        Args:
            results: Lista wyników wyszukiwania
            
        Returns:
            str: Sformatowana lista wyników
        """
        entries = []
        
        for i, entry in enumerate(results, start=1):
            title = entry.get('title', 'Unknown title')
            uploader = entry.get('uploader', 'Unknown uploader')
            duration = entry.get('duration', 0)
            
            # Formatuj czas trwania
            if duration:
                minutes, seconds = divmod(int(duration), 60)
                duration_str = f"{minutes:02d}:{seconds:02d}"
            else:
                duration_str = "??:??"
                
            entries.append(f"`{i}.` **{title}** by *{uploader}* `[{duration_str}]`")
            
        return "\n".join(entries)