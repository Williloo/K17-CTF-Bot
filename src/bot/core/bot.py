import discord
from discord.ext import commands

from features import *

class K17Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(command_prefix="!", intents=intents)
        
        # self.db_manager: Optional[DatabaseManager] = None
        # self.reaction_manager: Optional[ReactionRoleManager] = None
        # self.ipc: Optional[BotIPC] = None
    
    async def setup_hook(self):
        print("🚀 Starting bot setup...")
        
        # # Initialize database
        # self.db_manager = DatabaseManager()
        # await self.db_manager.connect()

        self.monad_manager = MonadManager()
        
        # # Load cogs
        # await self.load_extension('cogs.admin')
        
        # # Start IPC server
        # self.ipc = BotIPC(self)
        # self.loop.create_task(self.ipc.start())
        
        print("Bot setup complete!")
    
    async def on_ready(self):
        print(f"✅ {self.user} is now online!")
        print(f"Connected to {len(self.guilds)} guilds")
        print(f"Bot ID: {self.user.id}") # type: ignore

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return
        
        ## Debug only
        print(f"Message from {message.author}: {message.content}")
        
        if message.content.startswith("!hello"):
            await self.monad_manager.handle_hello(message)
