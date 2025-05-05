import discord
from discord.ext import commands
import re

class HonoraryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot  # Store bot instance
        # Role ID for honorary members
        self.honorary_role_id = 1345831887423275059

    @commands.command(
        name='honorarymembers',
        aliases=['honorarymember', 'hmember', 'hmem', 'honorary', 'hm']
    )
    @commands.has_any_role('The BotFather', 'Spreadsheet-Master', 'Server Owner', 'Manager', 'Moderator')
    async def honorarymembers(self, ctx):
        """
        Lists all members with the 'honorary member' role, stripping any leading '#NN ' prefix from their display names.
        """
        # Fetch the role from the guild by ID
        role = ctx.guild.get_role(self.honorary_role_id)
        if role is None:
            await ctx.send("Error: Honorary Member role not found on this server.")
            return

        # Gather and clean names
        cleaned_names = []
        for member in role.members:
            # Use display_name to include nicknames; fallback to username
            raw_name = member.display_name
            # Remove leading '#NN ' if present
            cleaned = re.sub(r'^#\d{2}\s*', '', raw_name)
            cleaned_names.append(cleaned)

        if not cleaned_names:
            await ctx.send("No honorary members found.")
            return

        # Construct a message or embed listing all names
        description = "\n".join(cleaned_names)
        embed = discord.Embed(
            title="Honorary Members",
            description=description,
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

# Cog setup function
async def setup(bot):
    await bot.add_cog(HonoraryCog(bot))
    print("Loaded HonoraryCog!")
