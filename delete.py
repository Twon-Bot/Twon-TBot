import discord
from discord.ext import commands

class DeleteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='delete', aliases=['del'])
    @commands.has_any_role('Spreadsheet-Master', 'Server Owner', 'Manager', 'Moderator')
    async def delete(self, ctx, num: int = 1):
        """
        Deletes the command message along with the previous num messages.
        If no number is provided, it defaults to deleting the command message and the one message before it.
        Maximum number of previous messages to delete is capped at 10.
        """
        # Cap the number to a maximum of 10.
        if num > 10:
            num = 10

        # Total messages to delete (the command message itself + previous messages)
        total_to_delete = num + 1

        # Fetch the messages from the channel history, including the command message.
        messages_to_delete = []
        async for message in ctx.channel.history(limit=total_to_delete):
            messages_to_delete.append(message)

        # Bulk delete the messages.
        try:
            await ctx.channel.delete_messages(messages_to_delete)
        except discord.Forbidden:
            await ctx.send("Error: I don't have permission to delete messages.", delete_after=5)
        except Exception as e:
            await ctx.send(f"Error: {str(e)}", delete_after=5)

async def setup(bot):
    await bot.add_cog(DeleteCog(bot))
    print ("Loaded DeleteCog!")
