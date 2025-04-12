import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import pytz
import sqlite3  # Needed to fetch the user's timezone from the database

class TrackingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_user_timezone(self, user_id):
        """
        Fetch the user's timezone from the database.
        Returns the timezone string (e.g., "America/Denver") or None if not set.
        """
        try:
            with sqlite3.connect("bot_data.db") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT timezone FROM user_timezones WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception:
            return None

    def get_pack_tracking_format(self):
        """
        Reads the announcements.txt file and returns the Pack Tracking section.
        Looks for the section that includes "Pack Tracking" and returns the layout (ignoring the header line).
        """
        try:
            with open("announcements.txt", "r", encoding="utf-8") as file:
                sections = file.read().split("===")
                for section in sections:
                    if "Pack Tracking" in section:
                        lines = section.strip().splitlines()
                        if lines:
                            # Assume the first line is the header, so return the rest.
                            return "\n".join(lines[1:]).strip()
            return None
        except FileNotFoundError:
            return None

    @commands.command(name="tracking")
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner')
    async def tracking(self, ctx):
        prompt = (
            "**Please provide the following details separated by commas:**\n"
            "Pack Number,\n"
            "Owner,\n"
            "Pack Contents,\n"
            "Expiry Date (MM/DD HH:MM),\n"
            "Verification Link"
        )
        await ctx.send(prompt)

        def check(message):
            return message.author == ctx.author and message.channel == ctx.channel

        try:
            response = await self.bot.wait_for("message", check=check, timeout=120)
            data = [part.strip() for part in response.content.split(",")]

            if len(data) != 5:
                await ctx.send("Error: Invalid format. Please provide exactly 5 parts separated by commas.")
                return

            pack_number, owner, contents, expire_time, verification_link = data

            # Convert expiry date to a Discord timestamp using the user's specific timezone.
            try:
                # Parse the provided expiry time string into a naive datetime.
                expiry_dt = datetime.strptime(expire_time, "%m/%d %H:%M")
                
                # Retrieve the user's timezone from the database; default to "UTC" if not set.
                user_tz_str = self.get_user_timezone(ctx.author.id) or "UTC"
                tz = pytz.timezone(user_tz_str)
                
                # Set the year based on the current year in the user's timezone.
                current_year = datetime.now(tz).year
                expiry_dt = expiry_dt.replace(year=current_year)
                
                # Localize the naive datetime so it becomes timezone-aware.
                expiry_dt = tz.localize(expiry_dt)
                
                # Convert the localized time to UTC to generate the proper Unix timestamp.
                utc_time = expiry_dt.astimezone(pytz.utc)
                timestamp = int(utc_time.timestamp())
                
                # Build the Discord timestamp format (<t:TIMESTAMP:F>).
                expire_time = f"<t:{timestamp}:F>"
            except Exception as e:
                # If conversion fails, log the error and use the raw input.
                print(f"Error converting expiry time: {e}")
                pass

            # Get the pack tracking format template from announcements.txt.
            format_template = self.get_pack_tracking_format()
            if not format_template:
                await ctx.send("Error: Could not load the Pack Tracking format from announcements.txt.")
                return

            # Replace the placeholders in the template with the provided values.
            announcement_text = format_template.format(
                PACK_NUMBER=pack_number,
                OWNER=owner,
                CONTENTS=contents,
                EXPIRE_TIME=expire_time,
                VERIFICATION_LINK=verification_link
            )

            # Output the final announcement in the current channel.
            await ctx.send(announcement_text)

        except asyncio.TimeoutError:
            await ctx.send("Error: Timed out. Please try again and respond within 120 seconds.")

async def setup(bot):
    await bot.add_cog(TrackingCog(bot))
    print("Loaded TrackingCog!")
