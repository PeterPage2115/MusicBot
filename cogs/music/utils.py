from discord.ext import commands
from config import DJ_ROLE_ENABLED
import discord

def is_dj():
    """
    Sprawdza, czy użytkownik ma uprawnienia DJ.
    
    Użytkownik ma uprawnienia DJ, jeśli:
    1. Jest administratorem serwera
    2. Ma rolę "DJ" (jeśli DJ_ROLE_ENABLED jest True)
    3. Jest sam na kanale głosowym z botem
    """
    async def predicate(ctx):
        # Jeśli użytkownik jest administratorem, zawsze ma uprawnienia
        if ctx.author.guild_permissions.administrator:
            return True
        
        # Jeśli system DJ jest włączony, sprawdzamy rolę DJ
        if DJ_ROLE_ENABLED:
            # Sprawdzamy, czy użytkownik ma rolę "DJ"
            dj_role = discord.utils.get(ctx.guild.roles, name="DJ")
            if dj_role and dj_role in ctx.author.roles:
                return True
        
        # Jeśli użytkownik jest sam na kanale głosowym z botem, też ma uprawnienia
        if ctx.voice_client and len(ctx.voice_client.channel.members) <= 2:
            # <= 2 bo liczymy użytkownika i bota
            return True
        
        # W każdym innym przypadku, użytkownik nie ma uprawnień
        await ctx.send("Potrzebujesz roli DJ, aby użyć tej komendy gdy na kanale są inni użytkownicy!")
        return False
        
    return commands.check(predicate)