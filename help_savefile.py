import discord
from discord.ext import commands

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='help')
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner', 'Police')
    async def help(self, ctx, category: str = None):
        # Use a warm yellow color for the embed
        color = 0xFFC107
        
        if category is None:
            embed = discord.Embed(
                title="**Available Help Commands:**",
                description=(
                    "- `!!help commands` → To show **all available** commands\n"
                    "- `!!help announce` → List available announcements\n"
                    "- `!!help schedule` → Show schedule commands\n"
                    "- `!!help timezone` → Show timezone commands\n"
                    "- `!!help delay` → Show how to schedule future announcements"
                ),
                color=color
            )
            await ctx.send(embed=embed)
            return

        if category.lower() == "announce":
            await self.send_announce_help(ctx, color)
        elif category.lower() == "schedule":
            embed = discord.Embed(
                title="**Schedule Commands:**",
                description=(
                    "- `!!resetschedule` or `!!rsch` → Set a new schedule\n"
                    "- `!!currentschedule` or `!!csch` → View the current schedule\n"
                    "- `!!expire` → Calculate the expiration time/date of a live pack"
                ),
                color=color
            )
            await ctx.send(embed=embed)
        elif category.lower() == "timezone":
            embed = discord.Embed(
                title="**Time Zone Commands:**",
                description=(
                    "- `!!time` → View the current time for your set time zone\n"
                    "- `!!settimezone <timezone>` → Set your timezone (e.g., `!!settimezone Europe/Berlin`)\n"
                    "- `!!gettimezone` → Displays the currently set timezone."
                ),
                color=color
            )
            await ctx.send(embed=embed)
        elif category.lower() == "delay":
            embed = discord.Embed(
                title="**Delay Commands:**",
                description=(
                    "- **Delaying an Announcement:**\n"
                    "  When using `!!announce`, react with ⏳ (hourglass) to schedule the announcement.\n"
                    "  The bot will prompt you to enter a time in `MM/DD HH:MM` format based on your set timezone.\n"
                    "- `!!viewdelay` or `!!vdelay` → View all pending delayed announcements.\n"
                    "- `!!canceldelay <MM/DD HH:MM>` or `!!cdelay <MM/DD HH:MM>` → Cancel a scheduled delayed announcement. \n"
                    "  *Example: `!!canceldelay 03/18 15:30`*"
                ),
                color=color
            )
            await ctx.send(embed=embed)
        elif category.lower() == "commands":
            embed = discord.Embed(
                title="**All Commands:**",
                description=(
                    "- `!!announce` or `!!ann`\n"
                    "- `!!testannounce` or `!!testann`\n"
                    "- `!!currentschedule` or `!!csch`\n"
                    "- `!!resetschedule` or `!!rsch`\n"
                    "- `!!settimezone` or `!!stz`\n"
                    "- `!!gettimezone` or `!!gtz`\n"
                    "- `!!time`\n"
                    "- `!!viewdelay` or `!!vdelay`\n"
                    "- `!!canceldelay` or `!!cdelay`\n"
                    "- `!!poll` → ***In-Progress***\n"
                    "- `!!export_votes` → ***In-Progress***\n"
                    "- `!!expire`\n"
                    "- `!!tracking`\n"
                    "- `!!write`"
                ),
                color=color
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="**Unknown Help Category**",
                description=f"Unknown help category `{category}`. Try `!!help` for options.",
                color=color
            )
            await ctx.send(embed=embed)

    async def send_announce_help(self, ctx, color):
        try:
            with open('announcements.txt', 'r', encoding='utf-8') as file:
                content = file.read()
                announcements = content.split('===')
                # Get the first line of each announcement as its title
                available_announcements = [lines[0].strip() for lines in (a.strip().splitlines() for a in announcements) if lines]

            embed = discord.Embed(
                title="**Available Announcements:**",
                description=(
                    "- " + "\n- ".join(available_announcements) + "\n\n"
                    "**Input format:**\n"
                    "*`!!announce Adding Phase`*\n\n"
                    "**To test out announcements:**\n"
                    "*Use the `!!testannounce` function!*"
                ),
                color=color
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="**Error**",
                description=f'An error occurred while reading the announcements: {str(e)}',
                color=color
            )
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
    print("Loaded HelpCog!")
