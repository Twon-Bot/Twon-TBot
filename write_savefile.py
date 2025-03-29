import discord
from discord.ext import commands

class WriteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    @commands.has_any_role('Spreadsheet-Master', 'Server Owner')
    async def write(self, ctx, *, message: str):
        try:
            await ctx.message.delete()  # Delete the original message
            await ctx.send(message)  # Send the message exactly as written
        except discord.Forbidden:
            await ctx.send("Error: I don't have permission to delete messages.")
        except Exception as e:
            await ctx.send(f"Error: {str(e)}")

async def setup(bot):
    await bot.add_cog(WriteCog(bot))