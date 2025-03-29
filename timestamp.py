import discord
from discord.ext import commands
import sqlite3
from datetime import datetime
import pytz

class TimestampCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_user_timezone(self, user_id):
        """Fetch the user's timezone from the database; default to UTC if not found."""
        try:
            with sqlite3.connect("bot_data.db") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT timezone FROM user_timezones WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception:
            return None

    @commands.command(name='timestamp', aliases=['ts'])
    @commands.has_any_role('Spreadsheet-Master', 'Server Owner', 'Manager', 'Moderator')
    async def timestamp(self, ctx, *, time_str: str = None):
        """
        Converts a given time (in MM/DD HH:MM format) based on the user's timezone
        into a Discord timestamp code (<t:TIMESTAMP:F>).

        Example usage: !!timestamp 03/15 18:00
        """
        if time_str is None:
            await ctx.send("⚠️ **Error:** An argument is required.\n**Usage:** `!!timestamp MM/DD HH:MM` (e.g., `!!timestamp 03/15 18:00`)")
            return

        # Get the user's timezone; default to UTC if not set.
        user_tz_str = self.get_user_timezone(ctx.author.id)
        if user_tz_str is None:
            user_tz_str = 'UTC'
        try:
            tz = pytz.timezone(user_tz_str)
        except pytz.UnknownTimeZoneError:
            tz = pytz.utc

        try:
            # Parse the provided time string and set the year to the current year.
            input_time = datetime.strptime(time_str, "%m/%d %H:%M")
            current_year = datetime.utcnow().year
            input_time = input_time.replace(year=current_year)

            # Localize the input time to the user's timezone and convert it to UTC.
            local_time = tz.localize(input_time)
            utc_time = local_time.astimezone(pytz.utc)
        except ValueError:
            await ctx.send("⚠️ Invalid format! Please use **MM/DD HH:MM** (e.g., `03/15 18:00`).")
            return

        # Generate the Discord timestamp code and the 10-digit code.
        timestamp_int = int(utc_time.timestamp())
        full_timestamp = f"<t:{timestamp_int}:F>"

        # First message: full Discord timestamp code.
        await ctx.send(f"Here is your Discord timestamp display:\n**{full_timestamp}**")
        # Second message: just the 10-digit code.
        await ctx.send(f"Copy this code for your usage:\n```{timestamp_int}```")
        await ctx.send(f"For formatting options, please see: **!!help timestamp**")

    @timestamp.error
    async def timestamp_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("⚠️ **Error:** An argument is required.\n**Usage:** `!!timestamp MM/DD HH:MM` (e.g., `!!timestamp 03/15 18:00`)")
        else:
            await ctx.send("An unexpected error occurred.")

async def setup(bot):
    await bot.add_cog(TimestampCog(bot))
    print ("Loaded TimestampCog!")
