## TODO: Have it update leaderboards n shit
## Make api calls to here:
## https://docs.ctfd.io/docs/api/redoc/

import discord
import logging

logger = logging.getLogger(__name__)

class CTFLeaderboardManager:
    def __init__(self, bot):
        self.bot = bot
        self.relevant_messages = []

    async def initialize(self):
        channel = self.bot.get_channel(913554033065750541)
        if not isinstance(channel, discord.TextChannel):
            logger.error("Channel not found or not a text channel")
            logger.debug(f"Channel found: {channel}")
            return

        msg = await channel.send("Counting: 0")
        self.relevant_messages.append((913554033065750541, msg.id))
        logger.info(f"Created counting message with ID {msg.id}")


    async def update_leaderboards(
        self
    ):      
        for channel_id, message_id in self.relevant_messages:
            channel = self.bot.get_channel(channel_id)

            if not isinstance(channel, discord.TextChannel):
                continue
        
            try:
                message = await channel.fetch_message(message_id)
                new_message = int(message.content.split(" ")[1]) + 1
                await message.edit(content=f"Counting: {new_message}")
            except discord.NotFound:
                logger.error(f"Message {message_id} not found")
            except discord.HTTPException as e:
                logger.error(f"Failed to edit message {message_id}: {e}")