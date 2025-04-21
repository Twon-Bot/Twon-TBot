import discord
from discord.ext import commands
import asyncio

class TonyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["ton"])
    @commands.has_any_role('Server Owner', 'Manager', 'Moderator', 'The BotFather', 'Police')
    async def tony(self, ctx):
        # Tony's user ID and mention
        tony_id = 317373446541672448
        tony_mention = f"<@{tony_id}>"
        
        # Send a message pinging Tony
        prompt_message = await ctx.send(f"Hey {tony_mention} 👋 How are you doing today?")
        
        # React with a thumbs up and thumbs down
        await prompt_message.add_reaction("👍")
        await prompt_message.add_reaction("👎")
        
        # Define a check to ensure we only process Tony's reaction on the correct message
        def check(reaction, user):
            return (
                user.id == tony_id and 
                reaction.message.id == prompt_message.id and 
                str(reaction.emoji) in ["👍", "👎"]
            )
        
        try:
            # Wait for Tony's reaction (timeout after 60 seconds)
            reaction, user = await self.bot.wait_for('reaction_add', check=check, timeout=60.0)
        except asyncio.TimeoutError:
            await ctx.send("Tony did not react in time.")
            return
        
        # Respond according to Tony's reaction
        if str(reaction.emoji) == "👎":
            await ctx.send("Hope your day gets better, Tony! 🤞")
        elif str(reaction.emoji) == "👍":
            await ctx.send("Great to hear you're doing well, Tony! Keep it up! 😊")

async def setup(bot):
    await bot.add_cog(TonyCog(bot))
    print ("Loaded TonyCog!")
