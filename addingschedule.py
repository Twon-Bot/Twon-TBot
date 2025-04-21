import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
import pytz

# Target channel where the schedule announcement will be output.
SCHEDULE_CHANNEL_ID = 1349879809445990560

class AddingScheduleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_user_timezone(self, user_id):
        """Fetch the user's timezone from Postgres; default to None if not set."""
        row = await self.bot.pg_pool.fetchrow(
            "SELECT timezone FROM timezones WHERE user_id = $1",
            user_id
        )
        return row["timezone"] if row else None

    @commands.command(name='addingschedule', aliases=['asch', 'as'])
    @commands.has_any_role('The BotFather', 'Spreadsheet-Master', 'Server Owner', 'Manager', 'Moderator')
    async def addingschedule(self, ctx):
        """
        Prompts for Adding Phase start time (MM/DD HH:MM) based on user's timezone,
        then outputs schedule announcement with Adding Phase and Pack Opening Phase.
        """
        await ctx.send("Please enter the Adding Phase start time in **MM/DD HH:MM** format.\nType `exit` to cancel.")

        def time_check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        # Get the user's timezone, defaulting to UTC if not set.
        user_tz_str = await self.get_user_timezone(ctx.author.id)
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
                    # Parse input time (without year) and set the current year.
                    input_time = datetime.strptime(msg.content, "%m/%d %H:%M")
                    current_year = datetime.utcnow().year
                    input_time = input_time.replace(year=current_year)

                    # Localize to user's timezone and convert to UTC.
                    local_time = tz.localize(input_time)
                    adding_phase_utc = local_time.astimezone(pytz.utc)
                    # Pack Opening Phase is 24 hours later.
                    pack_opening_utc = adding_phase_utc + timedelta(hours=24)
                except ValueError:
                    await ctx.send(
                        "⚠️ Invalid format! Please enter the time in **MM/DD HH:MM** format (e.g., `03/15 18:00`). Type `exit` to cancel."
                    )
                    continue

                break
            except asyncio.TimeoutError:
                await ctx.send("⏳ You took too long to respond. Schedule announcement canceled.")
                return

        # Send announcements to the schedule channel.
        schedule_channel = self.bot.get_channel(SCHEDULE_CHANNEL_ID)
        if schedule_channel is None:
            await ctx.send("Error: Schedule channel not found.")
            return

        # Part 1: Plain text announcement.
        text_message = (
            "# ⚠️  START CYCLE SCHEDULE!\n\n"
            "## Hey, <@&1334747903427870742> .  👋 \n\n"
            "### Are you ready for another 2⭐ hunt? This first schedule addresses both the Adding Phase and the Pack Opening Phase. "
            "Since the other phases depend on when we verify the first 2⭐ of the cycle, we will post the End Cycle Schedule when that happens! "
            "This should help you all to have a rough idea of when we will ping you.\n\n"
            "## 🗓️  Schedule\n"
            "### These timestamps auto update to your current timezone ‼️"
        )
        await schedule_channel.send(text_message)

        # Part 2: Embed with the schedule details.
        embed = discord.Embed(
            title="✅ Start Cycle Schedule",
            color=0x39FF14  # Neon lime green
        )
        embed.description = (
            "✅ The schedule is as follows:\n"
            f"- Adding Phase will begin at: <t:{int(adding_phase_utc.timestamp())}:F>\n"
            f"- Pack Opening Phase will begin at: <t:{int(pack_opening_utc.timestamp())}:F>"
        )
        await schedule_channel.send(embed=embed)

        # Confirm to the user.
        await ctx.send("Adding phase schedule announcement confirmed and output.")

async def setup(bot):
    await bot.add_cog(AddingScheduleCog(bot))
    print ("Loaded AddingScheduleCog!")
