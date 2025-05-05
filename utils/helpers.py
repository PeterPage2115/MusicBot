import discord
import asyncio
import os
import time
import shutil
from utils.logger import get_logger
import yt_dlp

# Inicjalizacja loggera
logger = get_logger()

# Klasa do obsługi błędów YT-DLP
class YTDLError(Exception):
    pass

# Opcje dla yt-dlp

ytdl_options = {
    'format': 'bestaudio/best',
    'outtmpl': 'temp/%(id)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': False,  # Zmienione na False, aby zobaczyć logi
    'no_warnings': False,  # Zmienione na False, aby zobaczyć ostrzeżenia
    'default_search': 'ytsearch',  # Wymuszenie używania ytsearch
    'source_address': '0.0.0.0',
    'socket_timeout': 15,  # Zwiększ timeout
    'retries': 10,
    'extractor_retries': 5,
    'skip_download': True,  # Tylko streamowanie
    'verbose': True  # Włącz więcej logów
}

# Opcje FFmpeg dla lepszej stabilności
ffmpeg_options = {
    'options': '-vn -loglevel warning', 
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 10 -nostdin -rw_timeout 15000000'
}

# Inicjalizacja yt-dlp jednorazowo
ytdl = yt_dlp.YoutubeDL(ytdl_options)

# Kompletna implementacja klasy YTDLSource

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data
        self.title = data.get('title', 'Brak tytułu')
        self.url = data.get('url', '') 
        self.thumbnail = data.get('thumbnail', '')
        self.duration = self._format_duration(data.get('duration', 0))
        self.uploader = data.get('uploader', 'Nieznany kanał')
        self.webpage_url = data.get('webpage_url', '')
        
    def __str__(self):
        return f"**{self.title}** [{self.duration}]"
        
    def _format_duration(self, duration):
        """Format duration into readable string"""
        if duration is None:
            return "Nieznany czas"
            
        if isinstance(duration, str):
            return duration
            
        try:
            duration = int(duration)
            minutes = duration // 60
            seconds = duration % 60
            return f"{minutes}:{seconds:02d}"
        except (ValueError, TypeError):
            return "Nieznany czas"

    @classmethod
    async def from_url(cls, query, *, loop=None, stream=True):
        """Tworzy źródło audio z URL lub wyszukiwania"""
        loop = loop or asyncio.get_event_loop()
        
        # Stwórz folder temp, jeśli nie istnieje
        os.makedirs('temp', exist_ok=True)
        
        try:
            # Sprawdź, czy to URL czy fraza wyszukiwania
            is_url = query.startswith('http://') or query.startswith('https://')
            
            # Używamy yt-dlp
            yt = yt_dlp.YoutubeDL(ytdl_options)
            
            if not is_url:
                # To jest fraza wyszukiwania - użyjmy bezpośrednio YouTube search URL
                search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
                logger.info(f"Wyszukiwanie YouTube: {search_url}")
                
                # Najpierw pobierz listę wyników
                search_results = await loop.run_in_executor(None, 
                    lambda: yt.extract_info(f"ytsearch:{query}", download=False))
                
                if not search_results or 'entries' not in search_results or not search_results['entries']:
                    raise YTDLError(f"Nie znaleziono wyników dla: {query}")
                
                # Pobierz pierwszy wynik
                video = search_results['entries'][0]
                video_url = f"https://www.youtube.com/watch?v={video['id']}"
                logger.info(f"Znaleziono URL: {video_url} ({video.get('title', 'Brak tytułu')})")
                
                # Teraz pobierz pełne informacje o tym konkretnym filmie
                data = await loop.run_in_executor(None, 
                    lambda: yt.extract_info(video_url, download=False))
            else:
                # To jest bezpośredni URL
                logger.info(f"Pobieranie informacji z URL: {query}")
                data = await loop.run_in_executor(None, 
                    lambda: yt.extract_info(query, download=False))
            
            # Sprawdź dane
            if not data:
                raise YTDLError(f"Nie udało się pobrać danych dla: {query}")
            
            # Jeśli to lista, pobierz pierwszy element
            if 'entries' in data:
                data = data['entries'][0]
            
            # Sprawdź, czy mamy URL streamowania
            if 'url' not in data:
                raise YTDLError(f"Nie znaleziono URL streamowania dla: {query}")
            
            stream_url = data['url']
            logger.info(f"URL streamowania: {stream_url[:50]}...")
            
            # Utwórz źródło audio
            ffmpeg_opts = {
                'options': '-vn -loglevel warning',
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 10 -nostdin'
            }
            
            source = discord.FFmpegPCMAudio(stream_url, **ffmpeg_opts)
            return cls(source, data=data)
            
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"yt-dlp error: {e}")
            # Szczegółowe logowanie błędu
            import traceback
            traceback.print_exc()
            raise YTDLError(f"Błąd pobierania: {e}")
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            raise YTDLError(f"Nieoczekiwany błąd: {e}")

    @staticmethod
    async def cleanup_temp_files(max_age_hours=24):
        """Usuwa stare pliki tymczasowe, aby zwolnić miejsce na dysku"""
        try:
            temp_dir = "temp"
            
            # Sprawdź czy folder istnieje
            if not os.path.isdir(temp_dir):
                os.makedirs(temp_dir)
                return
            
            # Aktualny czas
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            # Liczniki dla logowania
            deleted_count = 0
            total_size = 0
            
            # Przejdź przez wszystkie pliki w temp
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                
                # Sprawdź czy to plik i czy jest wystarczająco stary
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getmtime(file_path)
                    
                    if file_age > max_age_seconds:
                        # Pobierz rozmiar pliku przed usunięciem
                        file_size = os.path.getsize(file_path)
                        total_size += file_size
                        
                        # Usuń plik
                        os.remove(file_path)
                        deleted_count += 1
            
            # Zaloguj wyniki czyszczenia
            if deleted_count > 0:
                total_size_mb = total_size / (1024 * 1024)
                logger.info(f"Wyczyszczono {deleted_count} plików tymczasowych, zwolniono {total_size_mb:.2f} MB")
                
        except Exception as e:
            logger.error(f"Błąd podczas czyszczenia plików tymczasowych: {e}")