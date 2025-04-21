import discord
from discord.ext import commands

class LivePackOwnerCog(commands.Cog):
    """Cog for announcing new live pack owners with a friendly message."""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="livepackowner", aliases=["livepackowners", "lpo"])
    @commands.has_any_role('The BotFather', 'Moderator', 'Manager', 'Server Owner')
    async def livepackowner(self, ctx):
        """
        Announce the start of the live pack owner phase and delete the invoking command.
        """
        # Delete the original command message
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            # Missing permissions to delete, ignore
            pass

        # The announcement message
        message = (
            "<@&1334749513453273118> Hey new live pack owners! Congrats with your packs people! 🎉\n\n"
            "🏅 This channel is to guide you through the process of being a pack owner, and to offer you a space to ask any questions you may have.\n\n"
            "🔹 All we ask is that you follow the rules of not unadding anyone until Owner's WP Phase at **<t:1745244000:F>**. "
            "Once that time arrives you'll all have 16 hours to do your own wonder picks! 🍀\n\n"
            "🔸 This channel is also for you to tell us if you are still searching for another live owner's pack(s) or if you are done with the hunt. "
            "As soon as all live pack owners are done with the hunt, we will start the next adding phase! Good luck on picking! 🥂"
        )
        # Send the announcement
        await ctx.send(message)

async def setup(bot):
    await bot.add_cog(LivePackOwnerCog(bot))
    print("Loaded LivePackOwnerCog!")
