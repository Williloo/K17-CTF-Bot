import os

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

if DISCORD_TOKEN is None:
    raise ValueError("DISCORD_TOKEN environment variable not set")
