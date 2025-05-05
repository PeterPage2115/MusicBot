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
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # Bind to ipv4
}

# Inicjalizacja yt-dlp
ytdl = yt_dlp.YoutubeDL(ytdl_options)

# Opcje FFmpeg dla discord.py
ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 10 -nostdin',
    'options': '-vn'
}

# Klasa do obsługi błędów YT-DLP
class YTDLError(Exception):
    """Niestandardowy wyjątek dla błędów związanych z YT-DLP"""
    pass

class YTDLSource(discord.PCMVolumeTransformer):
    """
    Klasa źródła PCMVolumeTransformer do odtwarzania audio z YouTube.
    """
    # Używanie globalnej zmiennej jako zmiennej klasowej
    ytdl = ytdl
    
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        
        # Podstawowe informacje o utworze
        self.data = data
        self.id = data.get('id')
        self.title = data.get('title', 'Unknown')
        self.url = data.get('webpage_url', f'https://www.youtube.com/watch?v={self.id}')
        
        # Dodatkowe metadane
        self.uploader = data.get('uploader', 'Unknown')
        self.uploader_url = data.get('uploader_url', None)
        self.thumbnail = data.get('thumbnail', None)
        self.description = data.get('description', 'No description')
        self.duration_raw = int(data.get('duration', 0))
        self.duration = self._format_duration(self.duration_raw)
        self.tags = data.get('tags', [])
        self.views = data.get('view_count', 0)
        self.likes = data.get('like_count', 0)
        self.stream_url = data.get('url')
        self.requester = None  # To będzie ustawione po utworzeniu

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
            
        # Używamy cls.ytdl zamiast zmiennej lokalnej ytdl
        cls.ytdl = yt_dlp.YoutubeDL(ytdl_opts)

        try:
            # Logujemy próbę
            logger.info(f"Próba {retry_count+1}/{MAX_RETRIES} pobierania informacji: {url}")
            
            # Tworzymy funkcję częściową do wykonania przez executor
            partial = functools.partial(cls.ytdl.extract_info, url, download=not stream)
            
            # Wykonujemy z timeout
            try:
                data = await asyncio.wait_for(
                    loop.run_in_executor(None, partial), 
                    timeout=30.0  # 30 sekund timeout
                )
            except asyncio.TimeoutError:
                raise YTDLError("Timeout podczas pobierania informacji o utworze.")

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

        except Exception as e:
            logger.warning(f"Błąd podczas pobierania {url}: {e}")
            
            # Dla błędów związanych z siecią lub chwilową niedostępnością, spróbuj ponownie
            if retry_count < MAX_RETRIES:
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
                raise YTDLError(f"Nie udało się przetworzyć filmu: {e}")

    @classmethod
    async def search(cls, query, *, loop=None, limit=5):
        """
        Wyszukuje utwory na YouTube i zwraca listę wyników.
        
        Args:
            query: Fraza wyszukiwania
            loop: Pętla asyncio
            limit: Maksymalna liczba wyników
            
        Returns:
            List[Dict]: Lista znalezionych utworów
        """
        search_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
            'default_search': f'ytsearch{limit}',
            'noplaylist': True
        }
        
        # Używamy klasy yt_dlp zamiast importu zmiennej
        search_ytdl = yt_dlp.YoutubeDL(search_opts)
        
        # Logujemy wyszukiwanie
        logger.info(f"Wyszukiwanie YouTube: {query}")
        
        try:
            # Wykonaj wyszukiwanie asynchronicznie
            partial = functools.partial(search_ytdl.extract_info, query, download=False)
            data = await loop.run_in_executor(None, partial)
            
            # Sprawdź wyniki
            if 'entries' not in data:
                raise YTDLError("Nie znaleziono wyników wyszukiwania.")
                
            return data['entries'][:limit]  # Zwróć określoną liczbę wyników
            
        except Exception as e:
            logger.error(f"Błąd podczas wyszukiwania '{query}': {e}")
            raise YTDLError(f"Błąd podczas wyszukiwania: {e}")