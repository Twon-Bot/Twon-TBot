import discord
from discord.ext import commands
import asyncpg
import sqlite3
import asyncio
from datetime import datetime, timedelta
import pytz

class Schedule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.create_tables()  # Create both schedule and user timezone tables

    def create_tables(self):
        # Only need the schedule table in SQLite now
        with sqlite3.connect("bot_data.db") as conn:
            cursor = conn.cursor()
            cursor.execute(""" 
                CREATE TABLE IF NOT EXISTS schedule (
                    id INTEGER PRIMARY KEY,
                    time1 TEXT,
                    time2 TEXT,
                    time3 TEXT,
                    time4 TEXT
                )
            """)
            conn.commit()

    async def get_user_timezone(self, user_id):
#        \"\"\"Fetch a user's timezone from Postgres.\"\"\"
        row = await self.bot.pg_pool.fetchrow(
            "SELECT timezone FROM timezones WHERE user_id = $1",
            user_id
        )
        return row["timezone"] if row else None

    def get_schedule(self):
        with sqlite3.connect("bot_data.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT time1, time2, time3, time4 FROM schedule")
            result = cursor.fetchone()
            if result and all(result):  # Ensure all times exist
                return result  # Return tuple of times
            return None  # Return None if no schedule is found

    @commands.command(name="settimezone", aliases=["stz"])
    @commands.has_any_role('The BotFather', 'Moderator', 'Manager', 'Server Owner', 'Police')
    async def set_timezone(self, ctx, first: str = None, second: str = None):
        """
        Set a timezone.
        Usage:
          !!stz Europe/Berlin          → sets *your* TZ
          !!stz 123456789012345678 Zone → sets TZ for that user ID
        """
        if first is None:
            return await ctx.send("⚠️ Usage: `!!settimezone [user] <timezone>` — e.g. `!!stz Europe/Berlin` or `!!stz 1234567890 America/Denver`.")

        # figure out if they passed a user ID or mention
        if second:
            # two args: first is user, second is tz
            try:
                target = await commands.UserConverter().convert(ctx, first)
            except commands.BadArgument:
                return await ctx.send(f"⚠️ Could not find user `{first}`.")
            timezone = second
        else:
            target = ctx.author
            timezone = first

        # validate the timezone string
        try:
            pytz.timezone(timezone)
        except pytz.UnknownTimeZoneError:
            return await ctx.send("⚠️ Invalid timezone. Please try again (e.g. `Europe/Berlin`).")

        # upsert into Postgres
        await self.bot.pg_pool.execute(
            """
            INSERT INTO timezones(user_id, timezone)
            VALUES($1, $2)
            ON CONFLICT (user_id) DO UPDATE
              SET timezone = EXCLUDED.timezone
            """,
            target.id, timezone
        )

        if target == ctx.author:
            await ctx.send(f"✅ Your timezone has been set to **{timezone}**.")
        else:
            await ctx.send(f"✅ Timezone for {target.id} has been set to **{timezone}**.")

    @commands.command(name="time", aliases=["t"])
    @commands.has_any_role('The BotFather', 'Moderator', 'Manager', 'Server Owner', 'Police')
    async def show_time(self, ctx):
        """Displays the current time based on your timezone setting."""
        user_timezone = await self.get_user_timezone(ctx.author.id)  # Get the user's timezone

        if user_timezone:
            current_time = datetime.now(pytz.timezone(user_timezone))  # Get current time in user's timezone
            await ctx.send(f"The current time in your timezone ({user_timezone}) is: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            await ctx.send("⚠️ You have not set a timezone yet. Use `!settimezone <timezone>` to set it.")

    @commands.command(name="resetschedule", aliases=["rsch", "rs"])
    @commands.has_any_role('The BotFather', 'Moderator', 'Manager', 'Server Owner')
    async def reset_schedule(self, ctx):
        """Prompts user to confirm reset, input the pack expiration time, and update schedule."""        
        await ctx.send("⚠️ **Are you sure you want to reset the schedule?** \n(Type `Y` to confirm, `N` to cancel.)")

        def confirm_check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["y", "n"]

        try:
            response = await self.bot.wait_for("message", timeout=15.0, check=confirm_check)

            if response.content.lower() == "n":
                return await ctx.send("❌ Schedule reset canceled.")

            await ctx.send("Please enter the pack expiration time in **MM/DD HH:MM** format.\n*To exit this loop, type **exit.***")

            def time_check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            user_timezone = await self.get_user_timezone(ctx.author.id) or 'UTC'  # Default to UTC if not set
            tz = pytz.timezone(user_timezone)

            while True:  # Loop to keep asking for the time until it's valid or user exits
                try:
                    msg = await self.bot.wait_for("message", check=time_check, timeout=60)

                    # Allow user to exit
                    if msg.content.lower() == "exit":
                        return await ctx.send("❌ Schedule reset canceled by the user.")

                    try:
                        # Parse input time
                        pack_expiration = datetime.strptime(msg.content, "%m/%d %H:%M")
                        current_year = datetime.utcnow().year
                        pack_expiration = pack_expiration.replace(year=current_year)  # Set the year to current year
                        local_time = tz.localize(pack_expiration)  # Localize to the user's timezone
                        utc_time = local_time.astimezone(pytz.utc)  # Convert to UTC

                        # Calculate schedule times
                        time4 = utc_time
                        time3 = time4 - timedelta(hours=16)
                        time2 = time3 - timedelta(hours=32)
                        time1 = time2 - timedelta(hours=8)

                        # Store in database (replacing old values)
                        with sqlite3.connect("bot_data.db") as conn:
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM schedule")
                            cursor.execute("INSERT INTO schedule (time1, time2, time3, time4) VALUES (?, ?, ?, ?)",
                                           (time1.isoformat(), time2.isoformat(), time3.isoformat(), time4.isoformat()))
                            conn.commit()

                        # Build the updated schedule embed
                        embed = discord.Embed(
                            title="✅ **Schedule successfully updated!**",
                            color=0x39FF14  # Neon lime green color
                        )
                        # Combine the divider and schedule info in the embed description so there's no extra blank line
                        schedule_info = (
                            "──────────────────────────────\n" +
                            f"🔸 Voting will begin at:\n**<t:{int(time1.timestamp())}:F>**\n\n"
                            f"🔸 Picking will begin at:\n**<t:{int(time2.timestamp())}:F>**\n\n"
                            f"🔸 Owner WP will begin at:\n**<t:{int(time3.timestamp())}:F>**\n\n"
                            f"🔸 Pack will die at:\n**<t:{int(time4.timestamp())}:F>**"
                        )
                        embed.description = schedule_info
                        await ctx.send(embed=embed)
                        return  # Exit the loop after successful update

                    except ValueError:
                        await ctx.send("⚠️ Invalid format! Please enter the time in MM/DD HH:MM format (e.g., 03/15 18:00). Type `exit` to cancel.")
                        # The loop will continue asking for input again

                except asyncio.TimeoutError:
                    await ctx.send("⏳ You took too long to respond. Schedule reset canceled.")
                    return

        except asyncio.TimeoutError:
            await ctx.send("⏳ No response received. Schedule reset canceled.")

    @commands.command(name="currentschedule", aliases=["csch", "cs"])
    @commands.has_any_role('The BotFather', 'Moderator', 'Manager', 'Server Owner', 'Police')
    async def current_schedule(self, ctx):
        """Displays the current stored schedule without making changes."""
        try:
            await ctx.message.delete()  # Delete the user's command message
        except discord.Forbidden:
            await ctx.send("Error: I don't have permission to delete messages.")
        except Exception as e:
            await ctx.send(f"Error deleting your message: {str(e)}")
        
        schedule = self.get_schedule()
        if schedule:
            try:
                time1, time2, time3, time4 = map(datetime.fromisoformat, schedule)
                embed = discord.Embed(
                    title="✅ **The current schedule is as follows:**",
                    color=0x39FF14  # Neon lime green color
                )
                # Combine divider and schedule info in the description with no extra blank line
                schedule_info = (
                    "──────────────────────────────\n" +
                    f"🔹 Voting will begin at:\n**<t:{int(time1.timestamp())}:F>**\n\n"
                    f"🔹 Picking will begin at:\n**<t:{int(time2.timestamp())}:F>**\n\n"
                    f"🔹 Owner WP will begin at:\n**<t:{int(time3.timestamp())}:F>**\n\n"
                    f"🔹 Pack will die at:\n**<t:{int(time4.timestamp())}:F>**"
                )
                embed.description = schedule_info
                await ctx.send(embed=embed)
            except Exception:
                await ctx.send("⚠️ There was an issue reading the stored schedule. Try resetting it with `!!resetschedule`.")
        else:
            await ctx.send("No schedule is set. Use `!!resetschedule` to create one.")

    def cog_unload(self):
        """Properly handles cog unloading. No need to close a new connection here."""        
        print("Schedule cog is unloading.")

async def setup(bot):
    await bot.add_cog(Schedule(bot))
    print("Loaded ScheduleCog!")  # Debug print
