import discord
from discord.ext import commands
from datetime import datetime
import pytz

class TimestampCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_user_timezone(self, user_id):
        """Fetch the user's timezone from Postgres; default to UTC if not set."""
        row = await self.bot.pg_pool.fetchrow(
            "SELECT timezone FROM timezones WHERE user_id = $1", user_id
        )
        return row["timezone"] if row else "UTC"

    @commands.hybrid_command(name='timestamp', aliases=['ts'])
    @commands.has_any_role(
        'The BotFather', 'Spreadsheet-Master', 'Server Owner',
        'Manager', 'Moderator', 'Police', 'Honorary Member'
    )
    async def timestamp(self, ctx: commands.Context, *, time_str: str = None):
        """
        Converts MM/DD HH:MM (in your timezone) into a Discord timestamp code.
        Usage: !!timestamp 03/15 18:00  (or /timestamp)
        """
        # If prefix call, delete the user's message
        if ctx.interaction is None and ctx.message:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass

        # Missing argument
        if not time_str:
            msg = (
                "⚠️ **Error:** You must provide a date/time.\n"
                "**Usage:** `!!timestamp MM/DD HH:MM` (e.g., `!!timestamp 03/15 18:00`)"
            )
            if ctx.interaction:
                return await ctx.respond(msg, ephemeral=True)
            return await ctx.send(msg)

        # Resolve and parse
        user_tz_str = await self.get_user_timezone(ctx.author.id)
        try:
            tz = pytz.timezone(user_tz_str)
        except pytz.UnknownTimeZoneError:
            tz = pytz.utc

        try:
            parsed = datetime.strptime(time_str, "%m/%d %H:%M")
            parsed = parsed.replace(year=datetime.utcnow().year)
            local_dt = tz.localize(parsed)
            utc_dt = local_dt.astimezone(pytz.utc)
        except ValueError:
            msg = "⚠️ **Invalid format!** Please use **MM/DD HH:MM** (e.g., `!!timestamp 03/15 18:00`)."
            if ctx.interaction:
                return await ctx.respond(msg, ephemeral=True)
            return await ctx.send(msg)

        # Build timestamp code
        ts_int = int(utc_dt.timestamp())
        ts_code = f"<t:{ts_int}:F>"

        # Send outputs
        header = f"Here is your Discord timestamp display:\n**{ts_code}**"
        raw = str(ts_int)
        footer = "For timestamp formatting options, please see: `!!formats`"

        if ctx.interaction:
            # ephemeral slash responses
            await ctx.respond(header, ephemeral=True)
            await ctx.followup.send(raw, ephemeral=True)
            await ctx.followup.send(footer, ephemeral=True)
        else:
            # normal prefix responses
            await ctx.send(header)
            await ctx.send(raw)
            await ctx.send(footer)

    @timestamp.error
    async def timestamp_error(self, ctx: commands.Context, error):
        # Delete prefix invocation
        if ctx.interaction is None and ctx.message:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass

        if isinstance(error, commands.MissingRequiredArgument):
            msg = (
                "⚠️ **Error:** You must provide a date/time.\n"
                "**Usage:** `!!timestamp MM/DD HH:MM`"
            )
        else:
            msg = "❌ An unexpected error occurred."

        if ctx.interaction:
            await ctx.respond(msg, ephemeral=True)
        else:
            await ctx.send(msg)

    @commands.hybrid_command(
        name='timestamp_formats',
        aliases=['tsf', 'format', 'formats', 'tsformat', 'tsformats']
    )
    @commands.has_any_role(
        'The BotFather', 'Spreadsheet-Master', 'Server Owner',
        'Manager', 'Moderator', 'Police', 'Honorary Member'
    )
    async def timestamp_formats(self, ctx: commands.Context):
        """
        Shows Discord timestamp formatting options.
        Usage: !!timestamp_formats  or  /timestamp_formats
        """
        # Delete prefix invocation
        if ctx.interaction is None and ctx.message:
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

        if ctx.interaction:
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(TimestampCog(bot))
    print("Loaded TimestampCog!")
