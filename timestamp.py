import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import pytz

# List of available Discord timestamp format specifiers
TIMESTAMP_FORMATS = {
    "F": "Day, Month, Year at Time",
    "f": "Month, Year at Time",
    "D": "Month, Year",
    "d": "MM/DD/YYYY",
    "t": "Time (HH:MM)",
    "T": "Time (HH:MM:SS)",
    "R": "Relative time"
}

# Pre-built list of timezone offsets choices from UTC-7 to UTC+7
TZ_CHOICES = [app_commands.Choice(name=f"UTC{offset:+}", value=offset) for offset in range(-7, 8)]

class TimestampCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_user_timezone(self, user_id: int) -> str:
        """Fetch the user's timezone from Postgres; default to UTC if not set."""
        row = await self.bot.pg_pool.fetchrow(
            "SELECT timezone FROM timezones WHERE user_id = $1",
            user_id
        )
        return row["timezone"] if row else "UTC"

    @commands.command(name='timestamp', aliases=['ts'])
    @commands.has_any_role(
        'The BotFather', 'Spreadsheet-Master', 'Server Owner',
        'Manager', 'Moderator', 'Police', 'Honorary Member'
    )
    async def timestamp(self, ctx, *, time_str: str = None):
        """
        Prefix-only: Converts MM/DD HH:MM (in your timezone) into <t:TIMESTAMP:F>
        Usage: !!timestamp 3/5 9:30
        """
        # delete invocation
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        if not time_str:
            return await ctx.send(
                "⚠️ **Error:** You must provide a date/time.\n"
                "**Usage:** `!!timestamp MM/DD HH:MM`",
                delete_after=10
            )

        # resolve user's timezone from DB or default UTC
        tz_name = await self.get_user_timezone(ctx.author.id)
        try:
            tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            tz = pytz.utc

        # try flexible parsing
        parsed = None
        for fmt in ("%m/%d %H:%M", "%-m/%-d %H:%M", "%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M"):
            try:
                parsed = datetime.strptime(time_str, fmt)
                break
            except Exception:
                continue
        if not parsed:
            return await ctx.send(
                "⚠️ **Invalid format!** Use `MM/DD HH:MM` or `YYYY-MM-DD HH:MM`.",
                delete_after=10
            )

        # assume year if missing
        if parsed.year == 1900:
            parsed = parsed.replace(year=datetime.utcnow().year)

        # localize and build
        local_dt = tz.localize(parsed)
        ts_int = int(local_dt.timestamp())
        ts_code = f"<t:{ts_int}:F>"

        await ctx.send(f"{ts_code}\n{ts_int}\nFor formatting options, see: `!!timestamp_formats`")

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
        Prefix-only: shows Discord timestamp formatting options.
        Usage: !!timestamp_formats
        """
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            title="**Timestamp Formats:**",
            description="\n".join(
                f"- `<t:###:{k}>` → {v}" for k, v in TIMESTAMP_FORMATS.items()
            ),
            color=0xFFC107
        )
        await ctx.send(embed=embed)

    @app_commands.command(name="timestamp", description="Convert a date/time into a Discord timestamp")
    @app_commands.describe(
        datetime_str="Date & time, e.g. MM/DD HH:MM or YYYY-MM-DD HH:MM",
        parsing_timezone="Your timezone offset",
        public="If true, message is visible to everyone",
        style="Which Discord timestamp style to use"
    )
    @app_commands.choices(parsing_timezone=TZ_CHOICES,
                         style=[app_commands.Choice(name=k, value=k) for k in TIMESTAMP_FORMATS.keys()])
    @app_commands.checks.has_any_role(
        'The BotFather', 'Spreadsheet-Master', 'Server Owner',
        'Manager', 'Moderator', 'Police', 'Honorary Member'
    )
    async def slash_timestamp(
        self,
        interaction: discord.Interaction,
        datetime_str: str,
        parsing_timezone: app_commands.Choice[int],
        public: bool = False,
        style: app_commands.Choice[str] = app_commands.Choice(name="F", value="F")
    ):
        """
        Slash command: Convert a date/time into <t:TIMESTAMP:style>.
        """
        await interaction.response.defer(ephemeral=not public)

        # parse timezone
        offset = parsing_timezone.value
        tz = pytz.FixedOffset(offset * 60)

        # parse datetime string
        parsed = None
        for fmt in ("%m/%d %H:%M", "%-m/%-d %H:%M", "%Y-%m-%d %H:%M"):
            try:
                parsed = datetime.strptime(datetime_str, fmt)
                break
            except Exception:
                continue
        if not parsed:
            return await interaction.followup.send(
                "⚠️ **Invalid date/time format!** Use MM/DD HH:MM or YYYY-MM-DD HH:MM.",
                ephemeral=not public
            )
        if parsed.year == 1900:
            parsed = parsed.replace(year=datetime.utcnow().year)

        # localize and build timestamp
        local_dt = tz.localize(parsed)
        ts_int = int(local_dt.timestamp())
        ts_code = f"<t:{ts_int}:{style.value}>"

        # respond
        await interaction.followup.send(f"{ts_code}", ephemeral=not public)

async def setup(bot):
    await bot.add_cog(TimestampCog(bot))
    print("Loaded TimestampCog!")
