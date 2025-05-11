import discord
from discord.ext import commands
from discord import app_commands

# Default embed color (purple)
EMBED_COLOR = 0x800080

# Named colours mapping
NAMED_COLOURS = {
    "RED":       "FF0000",
    "ORANGE":    "FFA500",
    "YELLOW":    "FFFF00",
    "LIME":      "BFFF00",
    "GREEN":     "00FF00",
    "TEAL":      "008080",
    "CYAN":      "00FFFF",
    "SKY":       "87CEEB",
    "BLUE":      "0000FF",
    "NAVY":      "000080",
    "PURPLE":    "800080",
    "VIOLET":    "EE82EE",
    "PINK":      "FF00FF",
    "MAGENTA":   "FF00FF",
    "FUCHSIA":   "FF77FF",
    "BROWN":     "8B4513",
    "BLACK":     "000000",
    "GRAY":      "808080",
    "WHITE":     "FFFFFF",
    "GOLD":      "FFD700",
    "SILVER":    "C0C0C0"
}

class EmbedCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="embed", aliases=["emb", "em"])
    @commands.has_any_role('The BotFather', 'Moderator', 'Manager', 'Server Owner')
    async def embed(self, ctx, *, content: str):
        """Create an embed with the given content and delete the invocation."""
        # delete the user's original message
        await ctx.message.delete()
        # build and send the embed
        embed = discord.Embed(description=content, color=EMBED_COLOR)
        await ctx.send(embed=embed)

    @app_commands.command(name="embed", description="Create an embed with optional color")
    @commands.has_any_role('The BotFather', 'Moderator', 'Manager', 'Server Owner')
    @app_commands.describe(
        colour="Hex code (#RRGGBB) or named colour (e.g. RED). Leave blank for default purple",
        content="Contents of the embed"
    )
    async def embed_slash(
        self,
        interaction: discord.Interaction,
        content: str,
        colour: str = None
    ):
        """Slash command to create an embed with the given content and optional colour."""
        # determine final colour
        color_int = EMBED_COLOR

        if colour:
            key = colour.strip().lstrip('#').upper()

            # 1) Named colour?
            if key in NAMED_COLOURS:
                hexcode = NAMED_COLOURS[key]
                color_int = int(hexcode, 16)

            else:
                # 2) Raw hex code?
                try:
                    # must be exactly 6 hex digits
                    if len(key) == 6 and all(c in "0123456789ABCDEF" for c in key):
                        color_int = int(key, 16)
                except Exception:
                    color_int = EMBED_COLOR

        # build and send the embed
        embed = discord.Embed(description=content, color=color_int)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(EmbedCog(bot))
    print("Loaded EmbedCog!")
