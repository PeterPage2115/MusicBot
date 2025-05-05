import discord
from discord.ext import commands
from config import DJ_ROLE_ENABLED
from .utils import is_dj
from utils.logger import get_logger
import asyncio
import datetime
import time
import math

# Inicjalizacja loggera
logger = get_logger()

# Klasa widoku z przyciskami kontrolnymi
class MusicControlsView(discord.ui.View):
    """Widok przycisków do sterowania odtwarzaniem muzyki"""
    
    def __init__(self, cog, ctx):
        super().__init__(timeout=600.0)  # 10 minut timeout
        self.cog = cog
        self.ctx = ctx
        self.guild_id = ctx.guild.id
        self.message = None
        self._update_buttons(ctx)
        
    def _update_buttons(self, ctx):
        """Aktualizuje stan przycisków na podstawie aktualnego stanu odtwarzania"""
        try:
            # Czy bot jest na kanale głosowym
            is_connected = ctx.voice_client is not None and ctx.voice_client.is_connected()
            # Czy coś jest odtwarzane
            is_playing = is_connected and ctx.voice_client.is_playing()
            # Czy jest wstrzymane
            is_paused = is_connected and ctx.voice_client.is_paused()
            # Czy kolejka jest pusta
            is_queue_empty = not self.cog.queues.get(ctx.guild.id, [])
            # Aktualny tryb powtarzania
            repeat_mode = self.cog.repeat_mode.get(ctx.guild.id, 0)
            
            # Ustaw stan przycisków
            pause_button = discord.utils.get(self.children, custom_id="pause_button")
            if pause_button:
                pause_button.disabled = not is_playing
                
            resume_button = discord.utils.get(self.children, custom_id="resume_button")
            if resume_button:
                resume_button.disabled = not is_paused
                
            skip_button = discord.utils.get(self.children, custom_id="skip_button")
            if skip_button:
                skip_button.disabled = not (is_playing or is_paused) or is_queue_empty
                
            stop_button = discord.utils.get(self.children, custom_id="stop_button")
            if stop_button:
                stop_button.disabled = not is_connected
                
            # Ustaw przycisk powtarzania na odpowiedni kolor i etykietę
            repeat_button = discord.utils.get(self.children, custom_id="repeat_button")
            if repeat_button:
                if repeat_mode == 0:
                    repeat_button.style = discord.ButtonStyle.secondary
                    repeat_button.label = "🔄 Powtarzanie Wył."
                elif repeat_mode == 1:
                    repeat_button.style = discord.ButtonStyle.primary
                    repeat_button.label = "🔂 Powtórz Utwór"
                else:  # repeat_mode == 2
                    repeat_button.style = discord.ButtonStyle.success
                    repeat_button.label = "🔁 Powtórz Kolejkę"
            
            queue_button = discord.utils.get(self.children, custom_id="queue_button")
            if queue_button:
                queue_button.disabled = is_queue_empty
                
        except Exception as e:
            logger.error(f"Błąd podczas aktualizacji przycisków: {e}")
    
    async def on_timeout(self):
        """Wywoływane po timeout widoku"""
        try:
            if self.message:
                # Wyłącz wszystkie przyciski
                for child in self.children:
                    child.disabled = True
                await self.message.edit(view=self)
        except Exception as e:
            logger.error(f"Błąd podczas obsługi timeout widoku: {e}")
    
    @discord.ui.button(label="⏸️ Pauza", style=discord.ButtonStyle.primary, custom_id="pause_button", row=0)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Obsługa przycisku pauzy"""
        await interaction.response.defer()
        
        ctx = self.ctx
        # Sprawdzamy uprawnienia DJ
        if not await self._check_dj(interaction):
            return
            
        try:
            # Wykonaj pauzę
            await self.cog.pause(ctx)
            
            # Aktualizuj przyciski
            self._update_buttons(ctx)
            await interaction.message.edit(view=self)
        except Exception as e:
            logger.error(f"Błąd podczas pauzowania: {e}")
            await interaction.followup.send(f"❌ Błąd: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="▶️ Wznów", style=discord.ButtonStyle.success, custom_id="resume_button", row=0)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Obsługa przycisku wznowienia"""
        await interaction.response.defer()
        
        ctx = self.ctx
        # Sprawdzamy uprawnienia DJ
        if not await self._check_dj(interaction):
            return
            
        try:
            # Wykonaj wznowienie
            await self.cog.resume(ctx)
            
            # Aktualizuj przyciski
            self._update_buttons(ctx)
            await interaction.message.edit(view=self)
        except Exception as e:
            logger.error(f"Błąd podczas wznawiania: {e}")
            await interaction.followup.send(f"❌ Błąd: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="⏭️ Pomiń", style=discord.ButtonStyle.primary, custom_id="skip_button", row=0)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Obsługa przycisku pomijania"""
        await interaction.response.defer()
        
        ctx = self.ctx
        # Sprawdzamy uprawnienia DJ
        if not await self._check_dj(interaction):
            return
            
        try:
            # Wykonaj pominięcie
            await self.cog.skip(ctx)
            
            # Aktualizuj przyciski
            self._update_buttons(ctx)
            await interaction.message.edit(view=self)
        except Exception as e:
            logger.error(f"Błąd podczas pomijania: {e}")
            await interaction.followup.send(f"❌ Błąd: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🛑 Stop", style=discord.ButtonStyle.danger, custom_id="stop_button", row=0)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Obsługa przycisku stop"""
        await interaction.response.defer()
        
        ctx = self.ctx
        # Sprawdzamy uprawnienia DJ
        if not await self._check_dj(interaction):
            return
            
        try:
            # Wykonaj zatrzymanie
            await self.cog.stop(ctx)
            
            # Aktualizuj przyciski
            self._update_buttons(ctx)
            await interaction.message.edit(view=self)
        except Exception as e:
            logger.error(f"Błąd podczas zatrzymywania: {e}")
            await interaction.followup.send(f"❌ Błąd: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🔄 Powtarzanie", style=discord.ButtonStyle.secondary, custom_id="repeat_button", row=1)
    async def repeat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Obsługa przycisku powtarzania"""
        await interaction.response.defer()
        
        ctx = self.ctx
        # Sprawdzamy uprawnienia DJ
        if not await self._check_dj(interaction):
            return
            
        try:
            # Wykonaj przełączenie powtarzania
            await self.cog.toggle_repeat(ctx)
            
            # Aktualizuj przyciski
            self._update_buttons(ctx)
            await interaction.message.edit(view=self)
        except Exception as e:
            logger.error(f"Błąd podczas zmiany trybu powtarzania: {e}")
            await interaction.followup.send(f"❌ Błąd: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="📋 Kolejka", style=discord.ButtonStyle.secondary, custom_id="queue_button", row=1)
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Obsługa przycisku kolejki"""
        await interaction.response.defer()
        
        ctx = self.ctx
        try:
            # Wykonaj komendę kolejki
            await self.cog.queue(ctx)
            
            # Nie aktualizuj przycisków, ponieważ to tylko wyświetlenie kolejki
        except Exception as e:
            logger.error(f"Błąd podczas wyświetlania kolejki: {e}")
            await interaction.followup.send(f"❌ Błąd: {str(e)}", ephemeral=True)
    
    async def _check_dj(self, interaction):
        """Sprawdza uprawnienia DJ dla interakcji"""
        # Sprawdź, czy użytkownik ma uprawnienia DJ
        ctx = self.ctx
        
        # Jeśli użytkownik jest administratorem, zawsze ma uprawnienia
        if interaction.user.guild_permissions.administrator:
            return True
        
        # Jeśli system DJ jest włączony, sprawdzamy rolę DJ
        if DJ_ROLE_ENABLED:
            # Sprawdzamy, czy użytkownik ma rolę "DJ"
            dj_role = discord.utils.get(interaction.guild.roles, name="DJ")
            if dj_role and dj_role in interaction.user.roles:
                return True
        
        # Jeśli użytkownik jest sam na kanale głosowym z botem, też ma uprawnienia
        if ctx.voice_client and len(ctx.voice_client.channel.members) <= 2:
            # <= 2 bo liczymy użytkownika i bota
            return True
        
        # W każdym innym przypadku, użytkownik nie ma uprawnień
        await interaction.followup.send("Potrzebujesz roli DJ, aby użyć tej komendy gdy na kanale są inni użytkownicy!", ephemeral=True)
        return False


# Funkcja generująca tekstowy pasek postępu
def generate_progress_bar(current, total, bar_length=15):
    """
    Generuje tekstowy pasek postępu.
    
    Args:
        current: Aktualna pozycja (w sekundach)
        total: Całkowita długość (w sekundach)
        bar_length: Długość paska postępu w znakach
        
    Returns:
        str: Tekstowy pasek postępu
    """
    if total == 0:
        progress = 0
    else:
        progress = min(1.0, current / total)
    
    filled_length = int(bar_length * progress)
    empty_length = bar_length - filled_length
    
    # Bardziej estetyczny pasek postępu z ładniejszymi symbolami
    bar = '▓' * filled_length + '░' * empty_length
    
    # Formatuj czas jako MM:SS
    current_time = time.strftime('%M:%S', time.gmtime(current))
    total_time = time.strftime('%M:%S', time.gmtime(total))
    
    return f"[{bar}] {current_time}/{total_time}"


# Dodaj tę funkcję na końcu pliku
def setup_ui_commands(cog):
    """
    Konfiguruje komendy związane z interfejsem użytkownika.
    
    Args:
        cog: Instancja klasy Music
    """
    
    async def _send_now_playing_embed(self, ctx):
        """
        Wysyła osadzoną wiadomość z informacjami o aktualnie odtwarzanym utworze.
        
        Args:
            ctx: Kontekst komendy
        """
        guild_id = ctx.guild.id
        
        # Sprawdź czy coś jest odtwarzane
        if guild_id not in self.now_playing or not self.now_playing[guild_id]:
            await ctx.send("❌ Nic teraz nie gram!")
            return
        
        # Pobierz informacje o utworze
        player = self.now_playing[guild_id]
        
        # Utwórz osadzoną wiadomość
        embed = discord.Embed(
            title="🎵 Teraz odtwarzam",
            description=f"[{player.title}]({player.url})",
            color=0x3498db  # Niebieski kolor
        )
        
        # Dodaj miniaturę, jeśli dostępna
        if player.thumbnail:
            embed.set_thumbnail(url=player.thumbnail)
        
        # Dodaj informacje o utworze
        if player.uploader:
            embed.add_field(name="Twórca", value=player.uploader, inline=True)
            
        # Dodaj czas trwania
        embed.add_field(name="Czas trwania", value=player.duration, inline=True)
        
        # Wyświetl informacje o głośności
        volume_percentage = int(player.volume * 100)
        volume_emoji = "🔇" if volume_percentage == 0 else "🔉" if volume_percentage < 50 else "🔊"
        embed.add_field(name="Głośność", value=f"{volume_emoji} {volume_percentage}%", inline=True)
        
        # Dodaj pasek postępu
        if hasattr(ctx.voice_client, 'source') and hasattr(ctx.voice_client, '_start_time'):
            # Oblicz czas odtwarzania
            elapsed = time.time() - ctx.voice_client._start_time
            elapsed = min(elapsed, player.duration_raw)  # Nie przekraczaj długości utworu
            
            progress_bar = generate_progress_bar(elapsed, player.duration_raw)
            embed.add_field(name="Postęp", value=f"{progress_bar}", inline=False)
        
        # Dodaj informacje o wyświetleniach i polubieniach, jeśli dostępne
        if player.views is not None:
            embed.add_field(name="Wyświetlenia", value=f"👁️ {player.views:,}", inline=True)
        
        if player.likes is not None:
            embed.add_field(name="Polubienia", value=f"👍 {player.likes:,}", inline=True)
        
        # Informacje o kolejce
        queue_size = len(self.queues.get(guild_id, []))
        embed.add_field(name="W kolejce", value=f"📋 {queue_size} utworów", inline=True)
        
        # Informacje o trybie powtarzania
        repeat_mode = self.repeat_mode.get(guild_id, 0)
        repeat_status = "Wyłączone" if repeat_mode == 0 else "Utwór" if repeat_mode == 1 else "Kolejka"
        embed.add_field(name="Powtarzanie", value=f"🔄 {repeat_status}", inline=True)
        
        # Dodaj informację o prośbie o utwór
        embed.set_footer(text=f"Na prośbę: {player.requester.display_name}", 
                        icon_url=player.requester.display_avatar.url)
        
        # Dodaj czas wysłania wiadomości
        embed.timestamp = datetime.datetime.utcnow()
        
        # Utwórz widok z przyciskami
        view = MusicControlsView(self, ctx)
        
        try:
            # Wyślij wiadomość z przyciskami
            message = await ctx.send(embed=embed, view=view)
            view.message = message  # Zapisz referencję do wiadomości
        except Exception as e:
            logger.error(f"Błąd podczas wysyłania osadzonej wiadomości: {e}")
            await ctx.send(f"❌ Wystąpił błąd: {str(e)}")
    
    # Przypisz funkcję do klasy cog
    cog._send_now_playing_embed = _send_now_playing_embed.__get__(cog, type(cog))
    
    return cog