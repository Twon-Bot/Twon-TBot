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

    @commands.hybrid_command(name='timestamp', aliases=['ts'])
    @commands.has_any_role(
        'The BotFather', 'Spreadsheet-Master', 'Server Owner',
        'Manager', 'Moderator', 'Police', 'Honorary Member'
    )
    async def timestamp(self, ctx: commands.Context, *, time_str: str = None):
        """
        Converts a given time (in MM/DD HH:MM) based on the user's timezone
        into a Discord timestamp code (<t:TIMESTAMP:F>).

        Usage: /timestamp MM/DD HH:MM
        """
        # delete invocation message (prefix only)
        if ctx.message:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass

        # missing argument
        if not time_str:
            return await ctx.respond(
                "⚠️ **Error:** You must provide a date/time.\n"
                "**Usage:** `/timestamp MM/DD HH:MM` (e.g., `/timestamp 03/15 18:00`)",
                ephemeral=True
            )

        # determine timezone
        user_tz_str = await self.get_user_timezone(ctx.author.id) or 'UTC'
        try:
            tz = pytz.timezone(user_tz_str)
        except pytz.UnknownTimeZoneError:
            tz = pytz.utc

        # parse input
        try:
            input_time = datetime.strptime(time_str, "%m/%d %H:%M")
            input_time = input_time.replace(year=datetime.utcnow().year)
            local_time = tz.localize(input_time)
            utc_time = local_time.astimezone(pytz.utc)
        except ValueError:
            return await ctx.respond(
                "⚠️ **Invalid format!** Please use **MM/DD HH:MM** (e.g., `/timestamp 03/15 18:00`).",
                ephemeral=True
            )

        # build timestamps
        timestamp_int = int(utc_time.timestamp())
        full_timestamp = f"<t:{timestamp_int}:F>"

        # respond ephemerally
        await ctx.respond(
            f"Here is your Discord timestamp display:\n**{full_timestamp}**",
            ephemeral=True
        )
        await ctx.followup.send(str(timestamp_int), ephemeral=True)
        await ctx.followup.send(
            "For timestamp formatting options, please see: `/timestamp formats`",
            ephemeral=True
        )

    @timestamp.error
    async def timestamp_error(self, ctx: commands.Context, error):
        # delete invocation (prefix only)
        if ctx.message:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.respond(
                "⚠️ **Error:** You must provide a date/time.\n"
                "**Usage:** `/timestamp MM/DD HH:MM` (e.g., `/timestamp 03/15 18:00`)",
                ephemeral=True
            )
        else:
            await ctx.respond("❌ An unexpected error occurred.", ephemeral=True)

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
        """
        # delete invocation message (prefix only)
        if ctx.message:
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
        await ctx.respond(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(TimestampCog(bot))
    print("Loaded TimestampCog!")
