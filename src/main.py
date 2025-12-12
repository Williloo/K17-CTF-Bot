import discord
import logging
from src.bot.config import *

class WrapperClient(discord.Client):
    async def on_ready(self):
        print(f"Logged on as {self.user}!")

    async def on_message(self, message):
        if message.author == self.user:
            return
        
        print(f"Message from {message.author}: {message.content}")
        
        if message.content.startswith("!hello"):
            await message.channel.send("Hello!")

## Set up logging
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

## Set up intents
## TODO: Read documentation for intents
intents = discord.Intents.default()
intents.message_content = True

## Run Client
client = WrapperClient(intents=intents)
client.run(DISCORD_TOKEN, log_handler=handler, log_level=logging.DEBUG)  # type: ignore