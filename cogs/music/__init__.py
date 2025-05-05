from .music_module import Music

async def setup(bot):
    await bot.add_cog(Music(bot))