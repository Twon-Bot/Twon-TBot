import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import pytz
import re

LIVE_PACK_ROLE_ID = 1334749513453273118

class LivePackOwnerCog(commands.Cog):
    """Cog for announcing new live pack owners with a friendly message."""
    def __init__(self, bot):
        self.bot = bot

    async def get_user_timezone(self, user_id: int) -> str:
        """Fetch the user's timezone from Postgres; default to UTC if not set."""
        row = await self.bot.pg_pool.fetchrow(
            "SELECT timezone FROM timezones WHERE user_id = $1",
            user_id
        )
        return row["timezone"] if row and row["timezone"] else "UTC"

    @commands.command(name="livepackowner", aliases=["livepackowners","lpo"])
    @commands.has_any_role('The BotFather', 'Moderator', 'Manager', 'Server Owner')
    async def livepackowner(self, ctx, *, when: str = None):
        """
        Announce the start of the live pack owner phase at a given time.
        Usage:
          !!lpo MM/DD HH:MM
        or just
          !!lpo
        and you will be prompted.
        """
        # remove the invoking command
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        # helper to parse a single MM/DD HH:MM string into a UTC datetime
        async def parse_input(ts: str):
            """
            ts may be e.g. "4/5 8:0", "04/05 8:00", "4/05 08:0", "04/05 08:00", etc.
            Returns a timezone-aware UTC datetime or raises ValueError.
            """
            # 1–2 digits for month/day, whitespace, 1–2 digits hour : 1–2 digits minute
            m = re.match(r"^(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{1,2})$", ts.strip())
            if not m:
                raise ValueError("Time must be in MM/DD HH:MM form (you may omit leading zeros)")
            
            mon, day, hr, minute = map(int, m.groups())
            # optional: validate ranges
            if not (1 <= mon <= 12 and 1 <= day <= 31 and 0 <= hr < 24 and 0 <= minute < 60):
                raise ValueError("Month/day/hour/minute out of range")

            # fetch user tz
            tzname = await self.get_user_timezone(ctx.author.id)
            try:
                tz = pytz.timezone(tzname)
            except pytz.UnknownTimeZoneError:
                tz = pytz.utc

            # build localized dt (use current year)
            now = datetime.now(tz)
            local = tz.localize(datetime(year=now.year, month=mon, day=day, hour=hr, minute=minute))
            return local.astimezone(pytz.utc)

        # if they gave us the time already:
        if when is not None:
            when = when.strip()
            try:
                utc_dt = await parse_input(when)
            except ValueError as e:
                return await ctx.send(f"❌ {e}.  Please try again.")
        else:
            # prompt for it
            prompt = await ctx.send("Please enter the Owner’s WP Phase start time in **MM/DD HH:MM** format.")
            def check(m):
                return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=60)
                await prompt.delete()
                await msg.delete()
                utc_dt = await parse_input(msg.content.strip())
            except asyncio.TimeoutError:
                await prompt.delete()
                return await ctx.send("⏳ Timed out; please run the command again when ready.")
            except ValueError as e:
                return await ctx.send(f"❌ {e}.  Please run the command again.")
        
        # build the announcement
        ts = int(utc_dt.timestamp())
        announce = (
            f"<@&{LIVE_PACK_ROLE_ID}> Hey new live pack owners! Congrats on your packs! 🎉\n\n"
            "🏅 This channel is to guide you through the process of being a pack owner, and to offer you a space to ask any questions you may have.\n\n"
            f"🔹 All we ask is that you follow the rules of not unadding anyone until Owner's WP Phase at **<t:{ts}:F>**. "
            "Once that time arrives you'll all have 16 hours to do your own wonder picks! 🍀\n\n"
            "🔸 This channel is also for you to tell us if you are still searching for another live owner's pack(s) or if you are done with the hunt. "
            "As soon as all live pack owners are done with the hunt, we will start the next adding phase! Good luck on picking! 🥂"
        )

        # send it with role‐ping enabled
        allowed = discord.AllowedMentions(roles=True)
        await ctx.send(announce, allowed_mentions=allowed)


async def setup(bot):
    await bot.add_cog(LivePackOwnerCog(bot))
    print("Loaded LivePackOwnerCog!")
