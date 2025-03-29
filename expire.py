import discord
import pytz
import sqlite3
from discord.ext import commands
from datetime import datetime, timedelta, time

class ExpiryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_user_timezone(self, user_id):
        with sqlite3.connect("bot_data.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timezone FROM user_timezones WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else None

    @commands.command()
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner', 'Police')
    async def expire(self, ctx, *, date_time: str = None):
        """Calculates pack expiry time based on user input."""
        if not date_time:
            await ctx.send("Error: Please provide the pack's opening date and time in the format: `!!expire MM/DD HH:MM`.\n"
                           "Example: `!!expire 03/24 2:00` (when you opened the pack).")
            return

        user_timezone_str = self.get_user_timezone(ctx.author.id)
        if not user_timezone_str:
            await ctx.send("You have not set a timezone yet. Use `!!settimezone <timezone>` to set it.")
            return

        try:
            # Parse the user's input (assume current year) and localize it.
            user_timezone = pytz.timezone(user_timezone_str)
            input_time = datetime.strptime(date_time, "%m/%d %H:%M")
            now = datetime.now()
            input_time = input_time.replace(year=now.year)
            user_time = user_timezone.localize(input_time)

            # Determine the local cutoff time corresponding to 6:00 UTC for the user's opening date.
            local_date = user_time.date()
            utc_cutoff_for_local_date = datetime.combine(local_date, time(6, 0), tzinfo=pytz.utc)
            local_cutoff = utc_cutoff_for_local_date.astimezone(user_timezone)

            # If the pack was opened before the local cutoff, effective start is that cutoff; otherwise, next day.
            if user_time < local_cutoff:
                effective_day_local = local_cutoff
            else:
                effective_day_local = local_cutoff + timedelta(days=1)

            # Add three full in-game days.
            expiry_local = effective_day_local + timedelta(days=3)
            # Use the local expiry's Unix timestamp directly.
            discord_timestamp = f"<t:{int(expiry_local.timestamp())}:F>"

            await ctx.send(f"Your pack will expire at **{expiry_local.strftime('%m/%d %H:%M')}** {expiry_local.strftime('%Z')} ({discord_timestamp})")
        except Exception as e:
            await ctx.send("Invalid date/time format. Please use `!!expire MM/DD HH:MM` where the date and time are when the pack was first opened.")
            print(f"Error parsing date/time: {e}")

async def setup(bot):
    await bot.add_cog(ExpiryCog(bot))
    print ("Loaded ExpiryCog!")
