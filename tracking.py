import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import pytz

class TrackingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    @commands.command(name='tracking', aliases=['track'])
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

            # Convert expiry date to Discord timestamp
            try:
                expiry_dt = datetime.strptime(expire_time, "%m/%d %H:%M")
                current_year = datetime.utcnow().year
                expiry_dt = expiry_dt.replace(year=current_year)
                
                # Explicitly define your intended timezone (change "US/Eastern" to your desired zone)
                tz = pytz.timezone("US/Eastern")
                
                # Localize the parsed expiry_dt to your timezone
                expiry_dt = tz.localize(expiry_dt)
                
                # Convert the localized time to UTC
                utc_time = expiry_dt.astimezone(pytz.utc)
                
                timestamp = int(utc_time.timestamp())
                expire_time = f"<t:{timestamp}:F>"
            except Exception:
                # If conversion fails, use the raw input
                pass

            format_template = self.get_pack_tracking_format()
            if not format_template:
                await ctx.send("Error: Could not load the Pack Tracking format from announcements.txt.")
                return

            # Replace placeholders in the template with the provided values.
            announcement_text = format_template.format(
                PACK_NUMBER=pack_number,
                OWNER=owner,
                CONTENTS=contents,
                EXPIRE_TIME=expire_time,
                VERIFICATION_LINK=verification_link
            )

            # Instead of sending to the announcement channel, output the announcement in the current channel.
            await ctx.send(announcement_text)

        except asyncio.TimeoutError:
            await ctx.send("Error: Timed out. Please try again and respond within 120 seconds.")

async def setup(bot):
    await bot.add_cog(TrackingCog(bot))
    print ("Loaded TrackingCog!")
