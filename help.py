import discord
from discord.ext import commands


#List of changes between channels:
# - announce.py = ANNOUNCEMENT_CHANNEL_ID
# - ^^ same in delay.py
# - announce.py = TEST_ANNOUNCEMENT_CHANNEL_ID
# - announce.py = line 336 activity check
#     ^^ channel_id = TEST_ANNOUNCEMENT_CHANNEL_ID if test_mode else 1352203828694483018
# - announce.py = line 191 channel_id = ?? #Activity Check channel ID
# - delay.py = line 128 (if activity check - channel_ID = ???) # Activity Check
# - announce.py = line 298 (if... test announcement... else... schedule_ID)
# - delay.py = line 130 (elif "schedule"... channel_ID = schedule)


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
                    "- `!!help delay` → Show how to schedule future announcements\n"
                    "- `!!help timestamp` → Show timestamp formats"
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
                    "- `!!write`  → ***Limited Access***\n"
                    "- `!!endcycle` or `!!endc`\n"
                    "- `!!del`  → ***Be Careful!***\n"
                    "- `!!addingschedule` or `!!asch`\n"
                    "- `!!timestamp` or `!!ts`"
                ),
                color=color
            )
            await ctx.send(embed=embed)
        elif category.lower() == "timestamp":
            embed = discord.Embed(
                title="**Timestamp Formats:**",
                description=(
                    "- `<t: ### :F>` → Day, Month, Year at Time\n"
                    "- `<t: ### :f>` → Month, Year at Time\n"
                    "- `<t: ### :D>` → Month, Year\n"
                    "- `<t: ### :d>` → MM/DD/YYYY\n"
                    "- `<t: ### :t>` → Time (HH:MM)\n"
                    "- `<t: ### :T>` → Time (HH:MM:SS)\n"
                    "- `<t: ### :R>` → Relative time (?? hours ago)"
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
