import discord
from discord.ext import commands
from datetime import datetime
import pytz

class TimestampCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_user_timezone(self, user_id):
        """Fetch the user's timezone from Postgres; default to None if not found."""
        row = await self.bot.pg_pool.fetchrow(
            "SELECT timezone FROM timezones WHERE user_id = $1",
            user_id
        )
        return row["timezone"] if row else None

    @commands.command(name='timestamp', aliases=['ts'])
    @commands.has_any_role(
        'The BotFather', 'Spreadsheet-Master', 'Server Owner',
        'Manager', 'Moderator', 'Police', 'Honorary Member'
    )
    async def timestamp(self, ctx, *, time_str: str = None):
        """
        Converts a given time (in MM/DD HH:MM) based on the user's timezone
        into a Discord timestamp code (<t:TIMESTAMP:F>).

        Usage: !!timestamp MM/DD HH:MM
        """
        # delete invocation
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        # missing argument
        if not time_str:
            await ctx.author.send(
                "⚠️ **Error:** You must provide a date/time.\n"
                "**Usage:** `!!timestamp MM/DD HH:MM` (e.g., `!!timestamp 03/15 18:00`)"
            )
            return

        # resolve timezone
        user_tz_str = await self.get_user_timezone(ctx.author.id) or 'UTC'
        try:
            tz = pytz.timezone(user_tz_str)
        except pytz.UnknownTimeZoneError:
            tz = pytz.utc

        # parse input
        try:
            parsed = datetime.strptime(time_str, "%m/%d %H:%M")
            parsed = parsed.replace(year=datetime.utcnow().year)
            local_dt = tz.localize(parsed)
            utc_dt = local_dt.astimezone(pytz.utc)
        except ValueError:
            await ctx.author.send(
                "⚠️ **Invalid format!** Please use **MM/DD HH:MM** "
                "(e.g., `!!timestamp 03/15 18:00`)."
            )
            return

        # build outputs
        ts_int = int(utc_dt.timestamp())
        ts_code = f"<t:{ts_int}:F>"

        # DM the user the results
        await ctx.author.send(f"Here is your Discord timestamp display:\n**{ts_code}**")
        await ctx.author.send(str(ts_int))
        await ctx.author.send(
            "For timestamp formatting options, please see: `!!timestamp_formats`"
        )

    @commands.command(
        name='timestamp_formats',
        aliases=['tsf', 'format', 'formats', 'tsformat', 'tsformats']
    )
    @commands.has_any_role(
        'The BotFather', 'Spreadsheet-Master', 'Server Owner',
        'Manager', 'Moderator', 'Police', 'Honorary Member'
    )
    async def timestamp_formats(self, ctx):
        """
        Shows Discord timestamp formatting options.

        Usage: !!timestamp_formats
        """
        # delete invocation
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            title="**Timestamp Formats:**",
            description=(
                "- `<t:###:F>` → Day, Month, Year at Time\n"
                "- `<t:###:f>` → Month, Year at Time\n"
                "- `<t:###:D>` → Month, Year\n"
                "- `<t:###:d>` → MM/DD/YYYY\n"
                "- `<t:###:t>` → Time (HH:MM)\n"
                "- `<t:###:T>` → Time (HH:MM:SS)\n"
                "- `<t:###:R>` → Relative time"
            ),
            color=0xFFC107
        )
        await ctx.author.send(embed=embed)


async def setup(bot):
    await bot.add_cog(TimestampCog(bot))
    print("Loaded TimestampCog!")
