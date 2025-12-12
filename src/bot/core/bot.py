import discord
from discord.ext import commands, tasks
import logging
import sys
import os

# Add parent directory to path to import shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from features import *
from shared.database import DatabaseManager

logger = logging.getLogger(__name__)

class K17Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(command_prefix="!", intents=intents)
    
    async def setup_hook(self):
        logger.info("🚀 Starting bot setup...")
        
        # Initialize database
        self.db_manager = DatabaseManager()
        await self.db_manager.connect()

        self.monad_manager = MonadManager()
        self.ctfd_manager = CTFLeaderboardManager(self, self.db_manager)
        
        # # Load cogs
        # await self.load_extension('cogs.admin')
        
        # # Start IPC server
        # self.ipc = BotIPC(self)
        # self.loop.create_task(self.ipc.start())
        
        # Start background tasks
        self.minute_task.start()
        
        logger.info("Bot setup complete!")
    
    ## On Ready Event
    async def on_ready(self):
        logger.info(f"✅ {self.user} is now online!")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        logger.info(f"Bot ID: {self.user.id}") # type: ignore

    ## On Message Event
    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return
        
        ## Debug only
        logger.debug(f"Message from {message.author}: {message.content}")
        
        if message.content.startswith("!hello"):
            await self.monad_manager.handle_hello(message)

    ## On minute task
    @tasks.loop(minutes=1)
    async def minute_task(self):
        logger.info("🕐 Minute task triggered")
        
        await self.ctfd_manager.update_leaderboards()
    
    ## Pre Minute Task
    @minute_task.before_loop
    async def before_minute_task(self):
        await self.wait_until_ready()
        await self.ctfd_manager.initialize()
