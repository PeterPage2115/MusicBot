import discord
from discord.ext import commands
import asyncio
import sys
import traceback
import yt_dlp
import os
import subprocess

class Diagnostics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command(name="diagnose")
    @commands.is_owner()
    async def diagnose_audio(self, ctx, *, query="pezet magenta"):
        """Szczegółowa diagnostyka odtwarzania audio"""
        try:
            await ctx.send("🔍 Rozpoczynam diagnostykę audio...")
            
            # 1. Sprawdzenie czy bot jest na kanale głosowym
            if ctx.voice_client is None:
                if ctx.author.voice:
                    voice_client = await ctx.author.voice.channel.connect()
                    await ctx.send(f"✅ Dołączono do kanału głosowego {ctx.author.voice.channel.name}")
                else:
                    await ctx.send("❌ Musisz być na kanale głosowym!")
                    return
            else:
                voice_client = ctx.voice_client
                await ctx.send(f"✅ Bot jest już na kanale głosowym {voice_client.channel.name}")
            
            # 2. Sprawdzenie wersji FFmpeg
            try:
                process = await asyncio.create_subprocess_exec(
                    'ffmpeg', '-version',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    ffmpeg_version = stdout.decode().split('\n')[0]
                    await ctx.send(f"✅ FFmpeg dostępny: `{ffmpeg_version}`")
                else:
                    await ctx.send(f"⚠️ Problem z FFmpeg: `{stderr.decode()}`")
            except Exception as e:
                await ctx.send(f"❌ Błąd sprawdzania FFmpeg: {e}")
            
            # 3. Pobieranie informacji o utworze z yt-dlp
            await ctx.send(f"🔍 Wyszukuję: `{query}`...")
            
            ytdl_opts = {
                'format': 'bestaudio/best',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'default_search': 'auto',
                'extract_flat': True,
            }
            
            ydl = yt_dlp.YoutubeDL(ytdl_opts)
            
            # Sprawdź, czy to URL czy fraza wyszukiwania
            if not (query.startswith('http://') or query.startswith('https://')):
                search_query = f"ytsearch:{query}"
            else:
                search_query = query
                
            info = await self.bot.loop.run_in_executor(None, lambda: ydl.extract_info(search_query, download=False))
            
            if 'entries' in info:
                info = info['entries'][0]
            
            if 'formats' in info:
                audio_formats = [f for f in info['formats'] if f.get('acodec') != 'none']
                if audio_formats:
                    best_audio = audio_formats[-1]
                    await ctx.send(f"✅ Znaleziono {len(audio_formats)} formatów audio dla: **{info.get('title')}**")
                    
                    # Najlepszy format audio
                    audio_url = best_audio['url']
                    truncated_url = audio_url[:50] + "..." if len(audio_url) > 50 else audio_url
                    await ctx.send(f"🔗 URL streamowania: `{truncated_url}`")
                    
                    # Testowanie URL audio
                    await ctx.send("🧪 Testuję bezpośrednie połączenie z URL audio...")
                    
                    try:
                        import aiohttp
                        async with aiohttp.ClientSession() as session:
                            async with session.head(audio_url, timeout=5) as response:
                                if response.status == 200:
                                    await ctx.send(f"✅ URL audio dostępny (status 200)")
                                else:
                                    await ctx.send(f"⚠️ URL audio zwrócił status {response.status}")
                    except Exception as e:
                        await ctx.send(f"❌ Błąd testowania URL audio: {e}")
                    
                    # 4. Testowanie FFmpeg bezpośrednio
                    await ctx.send("🧪 Testuję FFmpeg z URL audio...")
                    
                    try:
                        temp_file = "temp/test_output.wav"
                        os.makedirs("temp", exist_ok=True)
                        
                        # Uruchom FFmpeg by przetworzyć 3 sekundy audio
                        process = await asyncio.create_subprocess_exec(
                            'ffmpeg', '-y', '-reconnect', '1', '-reconnect_streamed', '1',
                            '-i', audio_url, '-t', '3', '-vn', temp_file,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        
                        stdout, stderr = await process.communicate()
                        
                        if process.returncode == 0 and os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                            size_kb = os.path.getsize(temp_file) / 1024
                            await ctx.send(f"✅ FFmpeg wygenerował plik audio ({size_kb:.2f} KB)")
                        else:
                            error_output = stderr.decode()
                            short_error = error_output[-500:] if len(error_output) > 500 else error_output
                            await ctx.send(f"⚠️ FFmpeg nie wygenerował pliku audio. Błąd:\n```\n{short_error}\n```")
                    except Exception as e:
                        await ctx.send(f"❌ Błąd testowania FFmpeg: {e}")
                    
                    # 5. Testowanie odtwarzania audio przez discord.py
                    await ctx.send("🧪 Testuję odtwarzanie przez discord.py...")
                    
                    # Ustaw flagę zakończenia
                    is_playback_finished = asyncio.Event()
                    playback_error = None
                    
                    def after_playing(error):
                        nonlocal playback_error
                        playback_error = error
                        is_playback_finished.set()
                    
                    try:
                        # Stwórz źródło FFmpegPCMAudio z dokładnymi parametrami
                        ffmpeg_options = {
                            'options': '-vn -loglevel warning',
                            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
                        }
                        
                        source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options)
                        source = discord.PCMVolumeTransformer(source, volume=0.5)
                        
                        # Rozpocznij odtwarzanie
                        voice_client.play(source, after=after_playing)
                        await ctx.send("▶️ Rozpoczynam odtwarzanie testowe (3 sekundy)...")
                        
                        # Czekaj na zakończenie (maksymalnie 5 sekund) lub sprawdzaj status
                        start_time = asyncio.get_event_loop().time()
                        
                        # Sprawdzaj co 1 sekundę, czy odtwarzacz nadal gra
                        for i in range(5):
                            if voice_client.is_playing():
                                await ctx.send(f"✅ {i+1}s: Odtwarzanie trwa...")
                                await asyncio.sleep(1)
                            else:
                                elapsed = asyncio.get_event_loop().time() - start_time
                                await ctx.send(f"⚠️ Odtwarzanie zakończyło się po {elapsed:.2f}s")
                                break
                        
                        # Sprawdź, czy mamy błąd
                        if playback_error:
                            await ctx.send(f"❌ Błąd odtwarzania: {playback_error}")
                        else:
                            await ctx.send("✅ Test odtwarzania zakończony")
                            
                    except Exception as e:
                        await ctx.send(f"❌ Błąd podczas testu odtwarzania: {e}")
                        traceback.print_exc()
                
                else:
                    await ctx.send("❌ Nie znaleziono formatów audio")
            else:
                await ctx.send("❌ Nie znaleziono informacji o formacie")
            
        except Exception as e:
            await ctx.send(f"❌ Błąd diagnostyki: {e}")
            traceback.print_exc()

async def setup(bot):
    await bot.add_cog(Diagnostics(bot))