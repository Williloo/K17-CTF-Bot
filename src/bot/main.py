#!/usr/bin/env python3

# Entry Point to K17 CTF Bot
# Bunch of functions, currently:
# - Responds to "!hello" with "Hello!"

from core.bot import K17Bot
from config import *
from utils.logger import setup_logger


# ## Set up logging
# handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

# ## Set up intents
# ## TODO: Read documentation for intents
# intents = discord.Intents.default()
# intents.message_content = True

# ## Run Client
# client = WrapperClient(intents=intents)
# client.run(DISCORD_TOKEN, log_handler=handler, log_level=logging.DEBUG)  # type: ignore

logger = setup_logger()

# Entry Point for the Bot
def main():        
    # Create and run bot
    bot = K17Bot()
    
    try:
        logger.info("Starting K17 CTF Bot...")
        bot.run(DISCORD_TOKEN) # type: ignore
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        logger.info("Bot stopped")

if __name__ == "__main__":
    main()