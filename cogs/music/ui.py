import discord
from discord.ext import commands
import asyncio
import traceback
from config import DJ_ROLE_ENABLED
from .utils import is_dj
import time
from utils.logger import get_logger

# Inicjalizacja loggera
logger = get_logger()

# Klasa widoku z przyciskami kontrolnymi
class MusicControlsView(discord.ui.View):
    """Widok przycisków do sterowania odtwarzaniem muzyki"""
    
    def __init__(self, cog, ctx):
        super().__init__(timeout=600)  # 10 minut timeout
        self.cog = cog
        self.ctx = ctx
        self.guild_id = ctx.guild.id
        self._update_buttons(ctx)
        
    def _update_buttons(self, ctx):
        """Aktualizacja stanu przycisków na podstawie aktualnego stanu odtwarzania"""
        is_playing = ctx.voice_client and ctx.voice_client.is_playing()
        is_paused = ctx.voice_client and ctx.voice_client.is_paused()
        has_queue = self.guild_id in self.cog.queues and len(self.cog.queues[self.guild_id]) > 0
        repeat_mode = self.cog.repeat_mode.get(self.guild_id, 0)
        
        # Znajdź i zaktualizuj przyciski
        for item in self.children:
            if item.custom_id == "pause_button":
                item.disabled = not is_playing or is_paused
                item.label = "⏸️" 
            elif item.custom_id == "resume_button":
                item.disabled = not is_paused
                item.label = "▶️"
            elif item.custom_id == "skip_button":
                item.disabled = not (is_playing or is_paused or has_queue)
                item.label = "⏭️"
            elif item.custom_id == "stop_button":
                item.disabled = not (is_playing or is_paused or has_queue)
                item.label = "🛑"
            elif item.custom_id == "repeat_button":
                item.disabled = not (is_playing or is_paused)
                # Zmień etykietę zależnie od trybu powtarzania
                if repeat_mode == 0:
                    item.label = "🔁"  # Powtarzanie wyłączone
                    item.style = discord.ButtonStyle.secondary
                elif repeat_mode == 1:
                    item.label = "🔂"  # Powtarzanie utworu
                    item.style = discord.ButtonStyle.success
                else:
                    item.label = "🔁"  # Powtarzanie kolejki
                    item.style = discord.ButtonStyle.success
            elif item.custom_id == "queue_button":
                item.disabled = not (is_playing or is_paused or has_queue)
                item.label = "📋"
    
    async def on_timeout(self):
        """Wykonywana po upływie czasu widoku (dezaktywuje przyciski)"""
        for item in self.children:
            item.disabled = True
        
        # Spróbuj zaktualizować wiadomość z nieaktywnymi przyciskami
        try:
            guild_id = self.guild_id
            if guild_id in self.cog.last_np_message:
                await self.cog.last_np_message[guild_id].edit(view=self)
        except Exception as e:
            logger.error(f"Błąd podczas dezaktywacji przycisków: {e}")
    
    @discord.ui.button(label="⏸️", style=discord.ButtonStyle.primary, custom_id="pause_button", row=0)
    async def pause_button(self, interaction, button):
        """Przycisk pauzy"""
        await interaction.response.defer()
        ctx = self.ctx
        ctx.author = interaction.user
        
        # Wywołaj funkcję pauzy z coga
        await self.cog.pause(ctx)
        
        # Aktualizuj przyciski
        self._update_buttons(ctx)
        await interaction.message.edit(view=self)
    
    @discord.ui.button(label="▶️", style=discord.ButtonStyle.success, custom_id="resume_button", row=0)
    async def resume_button(self, interaction, button):
        """Przycisk wznowienia odtwarzania"""
        await interaction.response.defer()
        ctx = self.ctx
        ctx.author = interaction.user
        
        # Wywołaj funkcję wznowienia z coga
        await self.cog.resume(ctx)
        
        # Aktualizuj przyciski
        self._update_buttons(ctx)
        await interaction.message.edit(view=self)
    
    @discord.ui.button(label="⏭️", style=discord.ButtonStyle.primary, custom_id="skip_button", row=0)
    async def skip_button(self, interaction, button):
        """Przycisk pominięcia utworu"""
        await interaction.response.defer()
        ctx = self.ctx
        ctx.author = interaction.user
        
        # Wywołaj funkcję pominięcia z coga
        await self.cog.skip(ctx)
        
        # Aktualizacja przycisków nastąpi przy odtwarzaniu następnego utworu
    
    @discord.ui.button(label="🛑", style=discord.ButtonStyle.danger, custom_id="stop_button", row=0)
    async def stop_button(self, interaction, button):
        """Przycisk zatrzymania odtwarzania"""
        await interaction.response.defer()
        ctx = self.ctx
        ctx.author = interaction.user
        
        # Wywołaj funkcję stopu z coga
        await self.cog.stop(ctx)
        
        # Dezaktywuj wszystkie przyciski
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
    
    @discord.ui.button(label="🔁", style=discord.ButtonStyle.secondary, custom_id="repeat_button", row=1)
    async def toggle_repeat(self, interaction, button):
        """Przycisk przełączania trybu powtarzania"""
        await interaction.response.defer()
        ctx = self.ctx
        ctx.author = interaction.user
        
        # Wywołaj funkcję z coga
        await self.cog.toggle_repeat(ctx)
        
        # Aktualizuj przyciski
        self._update_buttons(ctx)
        await interaction.message.edit(view=self)
    
    @discord.ui.button(label="📋", style=discord.ButtonStyle.secondary, custom_id="queue_button", row=1)
    async def show_queue(self, interaction, button):
        """Przycisk pokazujący kolejkę"""
        await interaction.response.defer()
        ctx = self.ctx
        ctx.author = interaction.user
        
        # Wywołaj funkcję z coga
        await self.cog.queue(ctx)

# Dodaj tę funkcję na końcu pliku

def setup_ui_commands(cog):
    """
    Konfiguruje komendy związane z interfejsem użytkownika.
    
    Args:
        cog: Instancja klasy Music
    """
    
    async def _send_now_playing_embed(self, ctx):
        """Wysyła embed z informacjami o aktualnie odtwarzanym utworze"""
        try:
            guild_id = ctx.guild.id
            
            if guild_id not in self.now_playing or not ctx.voice_client or not ctx.voice_client.is_playing():
                return
            
            # Pobieramy informacje o utworze
            track = self.now_playing[guild_id]
            
            # Tworzymy embeda
            embed = discord.Embed(
                title="🎵 Teraz odtwarzane",
                description=f"**{track.title}**",
                color=discord.Color.blue(),
                url=track.url if hasattr(track, 'url') else None
            )
            
            # Dodajemy thumbnail
            if hasattr(track, 'thumbnail') and track.thumbnail:
                embed.set_thumbnail(url=track.thumbnail)
            
            # Dodajemy pola z dodatkowymi informacjami
            if hasattr(track, 'uploader') and track.uploader:
                embed.add_field(name="Kanał", value=track.uploader, inline=True)
            
            if hasattr(track, 'duration') and track.duration:
                # Próbuj wyświetlić czas trwania w formacie mm:ss
                try:
                    duration_seconds = int(track.data.get('duration', 0))
                    if duration_seconds > 0:
                        minutes = duration_seconds // 60
                        seconds = duration_seconds % 60
                        formatted_duration = f"{minutes}:{seconds:02d}"
                        embed.add_field(name="Długość", value=formatted_duration, inline=True)
                    else:
                        embed.add_field(name="Długość", value=track.duration, inline=True)
                except:
                    embed.add_field(name="Długość", value=track.duration, inline=True)
            
            # Informacja o kolejce
            queue_length = len(self.queues.get(guild_id, []))
            embed.add_field(name="Pozycja w kolejce", value="Odtwarzane", inline=True)
            embed.add_field(name="W kolejce", value=f"{queue_length} utworów", inline=True)
            
            # Dodajemy informację o głośności
            try:
                # Pobieramy głośność bezpiecznie
                if guild_id in self.volume_settings:
                    volume_value = self.volume_settings[guild_id]
                else:
                    volume_value = getattr(self, 'volume_value', 0.5)
                
                volume_percent = int(float(volume_value) * 100)
                embed.add_field(name="Głośność", value=f"{volume_percent}%", inline=True)
            except Exception as e:
                logger.error(f"Błąd podczas pobierania głośności: {e}")
                # Nie dodajemy pola w przypadku błędu
            
            # Dodaj informację o trybie powtarzania
            repeat_mode = self.repeat_mode.get(guild_id, 0)
            repeat_info = "Wyłączony"
            if repeat_mode == 1:
                repeat_info = "Ten utwór 🔂"
            elif repeat_mode == 2:
                repeat_info = "Cała kolejka 🔁"
            embed.add_field(name="Powtarzanie", value=repeat_info, inline=True)
            
            # Dodajemy stopkę
            if hasattr(ctx, 'author') and ctx.author:
                author_name = ctx.author.display_name
                author_avatar = ctx.author.avatar.url if ctx.author.avatar else None
                embed.set_footer(text=f"Komenda wywołana przez {author_name}", icon_url=author_avatar)
            
            # Usuń poprzednią wiadomość, jeśli istnieje
            if hasattr(self, 'last_np_message') and guild_id in self.last_np_message:
                try:
                    old_message = self.last_np_message[guild_id]
                    await old_message.delete()
                except (discord.NotFound, discord.Forbidden):
                    # Ignoruj jeśli wiadomość już nie istnieje lub nie mamy praw
                    pass
                except Exception as e:
                    logger.error(f"Błąd podczas usuwania starej wiadomości: {e}")
            
            # Inicjalizuj słownik wiadomości jeśli nie istnieje
            if not hasattr(self, 'last_np_message'):
                self.last_np_message = {}
            
            # Wysyłamy nową wiadomość z przyciskami
            view = MusicControlsView(self, ctx)
            self.last_np_message[guild_id] = await ctx.send(embed=embed, view=view)
        
        except Exception as e:
            logger.error(f"Błąd podczas wyświetlania informacji o utworze: {e}")
            traceback.print_exc()
            # Spróbuj wysłać prostą wiadomość jako fallback
            try:
                track = self.now_playing.get(guild_id)
                if track:
                    await ctx.send(f"🎵 Teraz odtwarzam: **{track.title}**")
            except:
                pass
    
    async def now_playing_info(ctx):
        """Pokazuje szczegółowe informacje o aktualnie odtwarzanym utworze"""
        
        if ctx.voice_client is None or not ctx.voice_client.is_playing():
            await ctx.send("Nie odtwarzam teraz żadnej muzyki!")
            return
            
        await cog._send_now_playing_embed(ctx)
    
    async def music_help(ctx):
        """Komenda wyświetlająca pomoc dotyczącą muzyki"""
        
        embed = discord.Embed(
            title="🎵 Pomoc - Komendy muzyczne",
            description="Lista dostępnych komend muzycznych",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🎵 Podstawowe",
            value=(
                f"`%join` - Dołącza do kanału głosowego\n"
                f"`%leave` - Opuszcza kanał głosowy\n"
                f"`%play <tytuł/URL>` - Odtwarza muzykę\n"
                f"`%now` - Pokazuje aktualnie odtwarzany utwór"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⏯️ Kontrola odtwarzania",
            value=(
                f"`%pause` - Wstrzymuje odtwarzanie\n"
                f"`%resume` - Wznawia odtwarzanie\n"
                f"`%skip` - Pomija aktualny utwór\n"
                f"`%stop` - Zatrzymuje odtwarzanie"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔄 Kolejka",
            value=(
                f"`%queue` - Wyświetla kolejkę utworów\n"
                f"`%clear` - Czyści kolejkę\n"
                f"`%shuffle` - Miesza kolejkę\n"
                f"`%remove <numer>` - Usuwa utwór z kolejki"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Ustawienia",
            value=(
                f"`%volume <1-100>` - Ustawia głośność\n"
                f"`%repeat` - Przełącza tryb powtarzania"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    async def dj_info(ctx):
        """Wyświetla informacje o uprawnieniach DJ"""
        
        # Pobierz informacje o roli DJ
        dj_role_enabled = cog.bot.get_cog("Config").dj_role_enabled
        dj_role_name = cog.bot.get_cog("Config").dj_role_name
        
        embed = discord.Embed(
            title="🎧 Informacje o uprawnieniach DJ",
            color=discord.Color.blue()
        )
        
        if dj_role_enabled:
            embed.description = f"Na tym serwerze wymagana jest rola **{dj_role_name}** do wykonywania niektórych komend."
            # Sprawdź czy użytkownik ma rolę DJ
            has_dj_role = discord.utils.get(ctx.author.roles, name=dj_role_name) is not None
            embed.add_field(
                name="Twoje uprawnienia", 
                value=f"{'✅ Masz rolę DJ' if has_dj_role else '❌ Nie masz roli DJ'}", 
                inline=False
            )
        else:
            embed.description = "Na tym serwerze każdy może używać wszystkich komend muzycznych."
        
        # Lista komend wymagających uprawnień DJ
        embed.add_field(
            name="Komendy wymagające uprawnień DJ (gdy włączone):", 
            value=(
                "`%pause` - Wstrzymanie odtwarzania\n"
                "`%resume` - Wznowienie odtwarzania\n"
                "`%skip` - Pominięcie utworu\n"
                "`%stop` - Zatrzymanie odtwarzania\n"
                "`%volume` - Zmiana głośności\n"
                "`%clear` - Czyszczenie kolejki\n"
                "`%repeat` - Zmiana trybu powtarzania\n"
                "`%shuffle` - Mieszanie kolejki\n"
                "`%remove` - Usuwanie utworu z kolejki"
            ), 
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    # Przypisanie metod do klasy
    cog._send_now_playing_embed = _send_now_playing_embed.__get__(cog, type(cog))
    cog.now_playing_info = now_playing_info
    cog.music_help = music_help
    cog.dj_info = dj_info
    
    return cog