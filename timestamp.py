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
    @commands.has_any_role('The BotFather', 'Spreadsheet-Master', 'Server Owner', 'Manager', 'Moderator', 'Police', 'Honorary Member')
    async def timestamp(self, ctx, *, time_str: str = None):
        """
        Converts a given time (in MM/DD HH:MM) based on the user's timezone
        into a Discord timestamp code (<t:TIMESTAMP:F>).

        Usage: !!timestamp MM/DD HH:MM
        """
        # delete invocation
        try: await ctx.message.delete()
        except discord.Forbidden: pass

        if time_str is None:
            return await ctx.respond(
                "⚠️ **Error:** An argument is required.\n"
                "**Usage:** `!!timestamp MM/DD HH:MM` (e.g., `!!timestamp 03/15 18:00`)",
                ephemeral=True
            )

        # Get the user's timezone; default to UTC if not set.
        user_tz_str = await self.get_user_timezone(ctx.author.id) or 'UTC'
        try:
            tz = pytz.timezone(user_tz_str)
        except pytz.UnknownTimeZoneError:
            tz = pytz.utc

        try:
            # Parse the provided time string and set the year to the current year.
            input_time = datetime.strptime(time_str, "%m/%d %H:%M")
            current_year = datetime.utcnow().year
            input_time = input_time.replace(year=current_year)

            # Localize the input time and convert to UTC.
            local_time = tz.localize(input_time)
            utc_time = local_time.astimezone(pytz.utc)
        except ValueError:
            return await ctx.respond(
                "⚠️ **Invalid format!** Please use **MM/DD HH:MM** (e.g., `03/15 18:00`).",
                ephemeral=True
            )

        # Generate the Discord timestamp code and the raw timestamp.
        timestamp_int = int(utc_time.timestamp())
        full_timestamp = f"<t:{timestamp_int}:F>"

        # already deleted invocation above
        # Send results ephemerally in two separate messages
        await ctx.respond(
            f"Here is your Discord timestamp display:\n**{full_timestamp}**\n\n"
            "For timestamp formatting options, please see: **!!formats**",
            ephemeral=True
        )
        await ctx.followup.send(f"{timestamp_int}", ephemeral=True)

    @timestamp.error
    async def timestamp_error(self, ctx, error):
        # delete invocation
        try: await ctx.message.delete()
        except discord.Forbidden: pass

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.respond(
                "⚠️ **Error:** An argument is required.\n"
                "**Usage:** `!!timestamp MM/DD HH:MM` (e.g., `!!timestamp 03/15 18:00`)",
                ephemeral=True
            )
        else:
            await ctx.respond("❌ An unexpected error occurred.", ephemeral=True)

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
        """
        # delete invocation
        try: await ctx.message.delete()
        except discord.Forbidden: pass

        # Build and send the formats embed ephemerally
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
    print ("Loaded TimestampCog!")
