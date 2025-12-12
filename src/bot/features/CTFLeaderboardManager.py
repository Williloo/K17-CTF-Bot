## TODO: Have it update leaderboards n shit
## Make api calls to here:
## https://docs.ctfd.io/docs/api/redoc/

import discord
import logging
import sys
import os
import json

# Add parent directory to path to import shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.database import DatabaseManager

logger = logging.getLogger(__name__)

class CTFLeaderboardManager:
    def __init__(self, bot, db: DatabaseManager):
        self.bot = bot
        self.db = db
        self._message_cache = {}  # Cache: {message_id: {channel_id, guild_id, metadata}}

    async def initialize(self):
        # Fetch all existing tracked messages from DB and populate cache
        existing = await self.db.get_tracked_messages(
            feature_type="ctf_leaderboard",
            is_active=True
        )
        
        if existing:
            # Populate cache with existing messages
            for record in existing:
                # Parse metadata if it's a JSON string, otherwise use as-is
                metadata = record['metadata']
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except json.JSONDecodeError:
                        metadata = {}
                elif metadata is None:
                    metadata = {}
                
                self._message_cache[record['message_id']] = {
                    'channel_id': record['channel_id'],
                    'guild_id': record['guild_id'],
                    'metadata': metadata
                }
            logger.info(f"Found {len(existing)} existing CTF leaderboard messages, loaded into cache")
            logger.info(f"Cache contents: {self._message_cache}")
            return
        
        # No existing messages, create a new one in my test channel
        channel = self.bot.get_channel(913554033065750541)

        if not isinstance(channel, discord.TextChannel):
            logger.error("Channel not found or not a text channel")
            return
        
        # Create new counting message
        msg = await channel.send("Counting: 0")
        
        # Track it in database
        await self.db.add_tracked_message(
            message_id=msg.id,
            channel_id=channel.id,
            guild_id=channel.guild.id,
            feature_type="ctf_leaderboard",
            metadata={"counter": 0}
        )
        
        # Add to cache
        self._message_cache[msg.id] = {
            'channel_id': channel.id,
            'guild_id': channel.guild.id,
            'metadata': {"counter": 0}
        }
        
        logger.info(f"Created and tracked counting message with ID {msg.id}")


    async def update_leaderboards(self):
        # Use cached messages instead of querying database
        for message_id, data in list(self._message_cache.items()):
            channel = self.bot.get_channel(data['channel_id'])

            if not isinstance(channel, discord.TextChannel):
                continue
        
            try:
                message = await channel.fetch_message(message_id)
                
                # Get current counter from cached metadata
                metadata = data['metadata']
                current_count = metadata.get('counter', 0)
                new_count = current_count + 1
                
                # Update message
                await message.edit(content=f"Counting: {new_count}")
                
                # Update cache
                self._message_cache[message_id]['metadata']['counter'] = new_count
                
                # Update metadata in database
                await self.db.update_tracked_message_metadata(
                    message_id=message_id,
                    metadata={"counter": new_count}
                )
                
                logger.debug(f"Updated message {message_id} to count {new_count}")
                
            except discord.NotFound:
                logger.error(f"Message {message_id} not found, deactivating")
                await self.db.deactivate_tracked_message(message_id)
                # Remove from cache
                del self._message_cache[message_id]
            except discord.HTTPException as e:
                logger.error(f"Failed to edit message {message_id}: {e}")
