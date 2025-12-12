import discord

class MonadManager:
    def __init__(self):
        pass

    async def handle_hello(
            self,
            payload: discord.Message
    ):
        await payload.channel.send("A monad is a monoid in the category of endofunctors.")
