## TODO: Have it update leaderboards n shit
## Make api calls to here:
## https://docs.ctfd.io/docs/api/redoc/

import discord
import logging
import sys
import os
import json
import requests

# Add parent directory to path to import shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.database import DatabaseManager

logger = logging.getLogger(__name__)

# Hard-coded message template for CTFd tracker
CTFD_TRACKER_TEMPLATE = """
```
==============================
========== UNSW K17 ==========
==============================
* Position:     {position} 
* Challenges:   {solved_rate}

In-Progress:{progress}
Solves:
{solves}
```
"""

def format_leaderboard_entry(ctfd_domain, api_key=None, forum_channel=None) -> str:
    api_url = f"{ctfd_domain}api/v1/"
    
    headers = {}
    if api_key:
        headers['Authorization'] = f'Token {api_key}'
        headers["Content-Type"] = "application/json"

    res = requests.get(api_url + "scoreboard", headers=headers)
    scoreboard = json.loads(res.text)['data']

    position = 0
    solved_count = 0
    

    for player in scoreboard:
        if player["name"] == "K17":
            position = player["pos"]
            break

    res = requests.get(api_url + "challenges", headers=headers)
    solved_rate="1/23"

    challenges = json.loads(res.text)['data']
    solved_challs = []
    for challenge in challenges:
        logger.debug(f"Challenge: {challenge}")
        if challenge["solved_by_me"]:
            solved_count += 1
            solved_challs.append(challenge)
    solved_rate=f"{solved_count}/{len(challenges)}"

    solves=""
    for challenge in solved_challs:
        solves += f"\t* {challenge['name']}\n"

    # Get in-progress challenges from forum posts
    progress = "\n"
    if forum_channel and isinstance(forum_channel, discord.ForumChannel):
        logger.debug(f"Forum channel found: {forum_channel.name} (ID: {forum_channel.id})")
        logger.debug(f"Total threads in channel: {len(forum_channel.threads)}")
        
        # Get all active threads (forum posts)
        for thread in forum_channel.threads:
            logger.debug(f"Thread: {thread.name} | Archived: {thread.archived} | ID: {thread.id}")
            if not thread.archived:
                if "SOLVED" in thread.name.upper():
                    continue
                progress += f"\t* {thread.name}\n"
        
        logger.debug(f"Active threads found: {progress.count('*')}")
    else:
        logger.debug(f"Forum channel issue - Channel: {forum_channel}, Type: {type(forum_channel)}")

    return CTFD_TRACKER_TEMPLATE.format(
        position=position,
        solved_rate=solved_rate,
        progress=progress,
        solves=solves
    )

class CTFLeaderboardManager:
    def __init__(self, bot, db: DatabaseManager):
        self.bot = bot
        self.db = db
        self._message_cache = {}  # Cache: {message_id: {channel_id, guild_id, message_type, metadata}}

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
                    'message_type': record.get('message_type', 'counter'),
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
            message_type="counter",
            metadata={"counter": 0}
        )
        
        # Add to cache
        self._message_cache[msg.id] = {
            'channel_id': channel.id,
            'guild_id': channel.guild.id,
            'message_type': 'counter',
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
                message_type = data.get('message_type', 'counter')
                
                if message_type == 'counter':
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
                
                elif message_type == 'ctfd_tracker':
                    # Get CTFd domain, API key, and forum channel from metadata
                    metadata = data['metadata']
                    ctfd_domain = metadata.get('ctfd_domain', '')
                    api_key = metadata.get('api_key')
                    forum_channel_id = metadata.get('forum_channel_id')
                    
                    # Get forum channel if configured
                    forum_channel = None
                    if forum_channel_id:
                        forum_channel = self.bot.get_channel(forum_channel_id)
                    
                    # Generate formatted leaderboard content
                    formatted_content = format_leaderboard_entry(ctfd_domain, api_key, forum_channel)
                    
                    # Update message
                    await message.edit(content=formatted_content)
                    
                    logger.debug(f"Updated CTFd tracker message {message_id} for {ctfd_domain}")
                
            except discord.NotFound:
                logger.error(f"Message {message_id} not found, deactivating")
                await self.db.deactivate_tracked_message(message_id)
                # Remove from cache
                del self._message_cache[message_id]
            except discord.HTTPException as e:
                logger.error(f"Failed to edit message {message_id}: {e}")
    
    # IPC Methods for Web Interface
    
    def get_cache(self) -> dict:
        """Return the entire message cache for the web interface"""
        # Convert integer message IDs to strings to preserve precision in JSON
        return {str(k): v for k, v in self._message_cache.items()}
    
    def get_cache_message(self, message_id: int) -> dict:
        """Get a specific message from cache"""
        return self._message_cache.get(message_id)  # type: ignore
    
    async def update_counter(self, message_id: int, value: int) -> bool:
        """Update a specific counter value from the web interface"""
        if message_id not in self._message_cache:
            logger.error(f"Message {message_id} not found in cache")
            return False
        
        try:
            # Update cache
            self._message_cache[message_id]['metadata']['counter'] = value
            
            # Update database
            await self.db.update_tracked_message_metadata(
                message_id=message_id,
                metadata={"counter": value}
            )
            
            # Update Discord message
            channel = self.bot.get_channel(self._message_cache[message_id]['channel_id'])
            if isinstance(channel, discord.TextChannel):
                message = await channel.fetch_message(message_id)
                await message.edit(content=f"Counting: {value}")
            
            logger.info(f"Manually updated counter for message {message_id} to {value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update counter: {e}")
            return False
    
    async def create_tracked_message(self, channel_id: int, message_type: str = 'counter', 
                                     initial_counter: int = 0, ctfd_domain: str = "", 
                                     ctfd_api_key: str = "", forum_channel_id: int = 0) -> dict:
        """Create a new tracked message in a specified channel"""
        try:
            channel = self.bot.get_channel(channel_id)
            
            if not isinstance(channel, discord.TextChannel):
                logger.error(f"Channel {channel_id} not found or not a text channel")
                return {"success": False, "error": "Channel not found or not accessible"}
            
            # Create message based on type
            if message_type == 'counter':
                msg = await channel.send(f"Counting: {initial_counter}")
                metadata = {"counter": initial_counter}
            elif message_type == 'ctfd_tracker':
                if not ctfd_domain:
                    return {"success": False, "error": "CTFd domain is required for ctfd_tracker type"}
                
                # Get forum channel if provided
                forum_channel = None
                if forum_channel_id:
                    forum_channel = self.bot.get_channel(forum_channel_id)
                
                # Generate formatted leaderboard content
                initial_message = format_leaderboard_entry(ctfd_domain, ctfd_api_key or None, forum_channel)
                msg = await channel.send(initial_message)
                metadata = {"ctfd_domain": ctfd_domain}
                if ctfd_api_key:
                    metadata["api_key"] = ctfd_api_key
                if forum_channel_id:
                    metadata["forum_channel_id"] = forum_channel_id # type: ignore
            else:
                return {"success": False, "error": f"Unknown message type: {message_type}"}
            
            # Track it in database
            await self.db.add_tracked_message(
                message_id=msg.id,
                channel_id=channel.id,
                guild_id=channel.guild.id,
                feature_type="ctf_leaderboard",
                message_type=message_type,
                metadata=metadata
            )
            
            # Add to cache
            self._message_cache[msg.id] = {
                'channel_id': channel.id,
                'guild_id': channel.guild.id,
                'message_type': message_type,
                'metadata': metadata
            }
            
            logger.info(f"Created new tracked message {msg.id} in channel {channel_id}")
            return {
                "success": True,
                "message_id": msg.id,
                "channel_id": channel.id,
                "guild_id": channel.guild.id
            }
            
        except discord.Forbidden:
            logger.error(f"No permission to send message in channel {channel_id}")
            return {"success": False, "error": "No permission to send messages in that channel"}
        except Exception as e:
            logger.error(f"Failed to create tracked message: {e}")
            return {"success": False, "error": str(e)}
    
    async def delete_tracked_message(self, message_id: int, delete_discord_message: bool = True) -> dict:
        """Delete a tracked message from database and optionally from Discord"""
        try:
            # Check if message exists in cache
            if message_id not in self._message_cache:
                return {"success": False, "error": "Message not found in cache"}
            
            # Optionally delete from Discord
            if delete_discord_message:
                try:
                    channel_id = self._message_cache[message_id]['channel_id']
                    channel = self.bot.get_channel(channel_id)
                    if isinstance(channel, discord.TextChannel):
                        message = await channel.fetch_message(message_id)
                        await message.delete()
                        logger.info(f"Deleted Discord message {message_id}")
                except discord.NotFound:
                    logger.warning(f"Discord message {message_id} not found, continuing with database deletion")
                except Exception as e:
                    logger.warning(f"Failed to delete Discord message {message_id}: {e}")
            
            # Delete from database
            await self.db.delete_tracked_message(message_id)
            
            # Remove from cache
            del self._message_cache[message_id]
            
            logger.info(f"Successfully deleted tracked message {message_id}")
            return {"success": True, "message": "Message deleted successfully"}
            
        except Exception as e:
            logger.error(f"Failed to delete tracked message {message_id}: {e}")
            return {"success": False, "error": str(e)}
