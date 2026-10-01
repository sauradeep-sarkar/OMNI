import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from music.db import init_db

load_dotenv()

class OmniBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!", 
            intents=discord.Intents.default()
        )

    async def setup_hook(self):
        init_db()
        # Load cogs here
        await self.load_extension("cogs.general")
        await self.load_extension("cogs.music_cog")
        await self.tree.sync()
        print("Slash commands synced")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        for guild in self.guilds:
            try:
                self.tree.clear_commands(guild=guild)
                await self.tree.sync(guild=guild)
            except Exception as e:
                print(f"Failed to clear local commands for guild {guild.id}: {e}")
        print("Cleared local duplicates, relying on global sync!")

if __name__ == "__main__":
    bot = OmniBot()
    token = os.getenv("DISCORD_TOKEN")
    
    if not token:
        print("Error: DISCORD_TOKEN is missing or empty. Please check your .env file.")
    else:
        try:
            bot.run(token)
        except discord.errors.LoginFailure:
            print("Error: Improper token has been passed. Please reset your bot token on the Developer Portal and update the .env file.")
