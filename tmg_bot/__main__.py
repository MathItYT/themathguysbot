from dotenv import load_dotenv
import os
import discord

load_dotenv()

from .ai import AI

def main() -> None:
    tmg_bot = discord.Bot(intents=discord.Intents.all(), activity=discord.Game(name="math"))
    tmg_bot.add_cog(AI(tmg_bot))
    tmg_bot.run(os.getenv("DISCORD_TOKEN"))
