import discord
from discord.ext import commands
import sqlite3
import asyncio
from datetime import datetime, timedelta
import pytz

class Schedule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.create_tables()  # Create both schedule and user timezone tables

    def create_tables(self):
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
            cursor.execute(""" 
                CREATE TABLE IF NOT EXISTS user_timezones (
                    user_id INTEGER PRIMARY KEY,
                    timezone TEXT
                )
            """)
            conn.commit()

    def get_user_timezone(self, user_id):
        with sqlite3.connect("bot_data.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timezone FROM user_timezones WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else None  # Return timezone or None if not set

    def get_schedule(self):
        with sqlite3.connect("bot_data.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT time1, time2, time3, time4 FROM schedule")
            result = cursor.fetchone()
            if result and all(result):  # Ensure all times exist
                return result  # Return tuple of times
            return None  # Return None if no schedule is found

    @commands.command(name="settimezone", aliases=["stz"])
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner', 'Police')
    async def set_timezone(self, ctx, timezone: str = None):
        """Set your timezone (e.g., Europe/Berlin)."""
        if not timezone:
            await ctx.send("⚠️ Please enter a timezone. Example: `!!settimezone America/Denver`.")
            return

        try:
            pytz.timezone(timezone)  # Validate the timezone

            with sqlite3.connect("bot_data.db") as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO user_timezones (user_id, timezone) VALUES (?, ?)",
                               (ctx.author.id, timezone))
                conn.commit()

            await ctx.send(f"Your timezone has been set to {timezone}.")
        except pytz.UnknownTimeZoneError:
            await ctx.send("⚠️ Invalid timezone. Please try again.\n*If you're not sure how to format your time zone, ask Blimo.*")

    @commands.command(name="time")
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner', 'Police')
    async def show_time(self, ctx):
        """Displays the current time based on your timezone setting."""
        user_timezone = self.get_user_timezone(ctx.author.id)  # Get the user's timezone

        if user_timezone:
            current_time = datetime.now(pytz.timezone(user_timezone))  # Get current time in user's timezone
            await ctx.send(f"The current time in your timezone ({user_timezone}) is: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            await ctx.send("⚠️ You have not set a timezone yet. Use `!settimezone <timezone>` to set it.")

    @commands.command(name="resetschedule", aliases=["rsch"])
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner')
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

            user_timezone = self.get_user_timezone(ctx.author.id) or 'UTC'  # Default to UTC if not set
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

    @commands.command(name="currentschedule", aliases=["csch"])
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner', 'Police')
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
                await ctx.send("⚠️ There was an issue reading the stored schedule. Try resetting it with `!resetschedule`.")
        else:
            await ctx.send("No schedule is set. Use `!resetschedule` to create one.")

    def cog_unload(self):
        """Properly handles cog unloading. No need to close a new connection here."""        
        print("Schedule cog is unloading.")

async def setup(bot):
    await bot.add_cog(Schedule(bot))
    print("Loaded ScheduleCog!")  # Debug print
##############################################    
# DOESN'T MATCH SAVEFILE SINCE EMBED UPDATE!!!
##############################################