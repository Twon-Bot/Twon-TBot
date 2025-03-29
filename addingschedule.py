import discord
from discord.ext import commands
import sqlite3
import asyncio
from datetime import datetime, timedelta
import pytz

# Target channel where the schedule announcement will be output.
SCHEDULE_CHANNEL_ID = 1349879809445990560

class AddingScheduleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_user_timezone(self, user_id):
        # Fetch the user's timezone from the database; default to UTC if not found.
        try:
            with sqlite3.connect("bot_data.db") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT timezone FROM user_timezones WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception:
            return None

    @commands.command(name='addingschedule', aliases=['asch'])
    @commands.has_any_role('Spreadsheet-Master', 'Server Owner', 'Manager', 'Moderator')
    async def addingschedule(self, ctx):
        """
        Prompts the user to input the Adding Phase start time (in MM/DD HH:MM format) based on their timezone.
        Then outputs a schedule announcement in the designated schedule channel with both the adding phase
        and pack opening phase (24 hours later) timestamps.
        """
        await ctx.send("Please enter the Adding Phase start time in **MM/DD HH:MM** format.\nType `exit` to cancel.")

        def time_check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        # Get the user's timezone, defaulting to UTC if not set.
        user_tz_str = self.get_user_timezone(ctx.author.id)
        if user_tz_str is None:
            user_tz_str = 'UTC'
        try:
            tz = pytz.timezone(user_tz_str)
        except pytz.UnknownTimeZoneError:
            tz = pytz.utc

        while True:
            try:
                msg = await self.bot.wait_for("message", check=time_check, timeout=60)
                if msg.content.lower() == "exit":
                    await ctx.send("❌ Schedule announcement canceled.")
                    return

                try:
                    # Parse input time (without year) and set the year to the current year.
                    input_time = datetime.strptime(msg.content, "%m/%d %H:%M")
                    current_year = datetime.utcnow().year
                    input_time = input_time.replace(year=current_year)

                    # Localize the input time to the user's timezone and convert to UTC.
                    local_time = tz.localize(input_time)
                    adding_phase_utc = local_time.astimezone(pytz.utc)
                    # Pack Opening Phase is exactly 24 hours later.
                    pack_opening_utc = adding_phase_utc + timedelta(hours=24)
                except ValueError:
                    await ctx.send("⚠️ Invalid format! Please enter the time in **MM/DD HH:MM** format (e.g., `03/15 18:00`). Type `exit` to cancel.")
                    continue

                # Once a valid time is received, break out of the loop.
                break

            except asyncio.TimeoutError:
                await ctx.send("⏳ You took too long to respond. Schedule announcement canceled.")
                return

        # Get the schedule channel.
        schedule_channel = self.bot.get_channel(SCHEDULE_CHANNEL_ID)
        if schedule_channel is None:
            await ctx.send("Error: Schedule channel not found.")
            return

        # Part 1: Plain text announcement.
        text_message = (
            "# ⚠️  START CYCLE SCHEDULE!\n\n"
            "## Hey, <@&1334747903427870742> .  👋 \n\n"
            "### Are you ready for another 2⭐ hunt? This first schedule addresses both the Adding Phase and the Pack Opening Phase. Since the other phases depends on when we verify the first 2⭐ of the cycle, we will post the End Cycle Schedule when that happens! This should help you all to have a rough idea of when we will ping you.\n\n"
            "## 🗓️  Schedule\n"
            "### These timestamps auto update to your current timezone ‼️"
        )
        await schedule_channel.send(text_message)

        # Part 2: Embed with the schedule details.
        embed = discord.Embed(
            title="✅ Start Cycle Schedule",
            color=0x39FF14  # Neon lime green color
        )
        embed.description = (
            "✅ The schedule is as follows:\n"
            f"- Adding Phase will begin at: <t:{int(adding_phase_utc.timestamp())}:F>\n"
            f"- Pack Opening Phase will begin at: <t:{int(pack_opening_utc.timestamp())}:F>"
        )
        await schedule_channel.send(embed=embed)

        # Confirm to the user in the original channel.
        await ctx.send("Adding phase schedule announcement confirmed and output.")

async def setup(bot):
    await bot.add_cog(AddingScheduleCog(bot))
    print ("Loaded AddingScheduleCog!")
