import discord
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio
from difflib import get_close_matches  # For inputs spelled wrong
from bot import AnnouncementCog

MOD_LOG_CHANNEL_ID = 1349879806870949971  # Replace with your mod log channel ID

class AnnouncementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["ann"])
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner')  # Keep role restriction
    async def announce(self, ctx, *, message: str):
        await self.handle_announcement(ctx, message, test_mode=False)

    @commands.command(aliases=["testann"])
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner')  # Keep role restriction
    async def testannounce(self, ctx, *, message: str):
        await self.handle_announcement(ctx, message, test_mode=True)

    async def handle_announcement(self, ctx, message: str, test_mode: bool):
        # Determine which channel to send to
        channel_id = 1349269241374965790 if test_mode else 1346741590345125938
        announcement_channel = self.bot.get_channel(channel_id)

        if announcement_channel is None:
            await ctx.send("Error: Announcement channel not found.")
            return

        lower_message = message.lower()

        # Handle "Voting End" announcement
        if lower_message == "voting end":
            await ctx.send("**Please input the 4 vote winners and their pack contents**, in the following format:\n"
                        "***User 1, User 1's Pack, \nUser 2, User 2's Pack, \nUser 3, User 3's Pack, \nUser 4, User 4's Pack***\n"
                        "*Note: Commas **must** separate each input!*")

            try:
                msg = await self.bot.wait_for('message', timeout=60.0,
                                            check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                winners_info = msg.content.split(',')
                if len(winners_info) != 8:
                    await ctx.send("Please provide **exactly** 8 values: \n"
                                "***USER1, pack contents, \nUSER2, User 2's Pack, \nUSER3, pack, \nUSER4, pack.***\n\n"
                                "*The program has been reset, **please try '!announce' again.***")
                    return

                USER1, PACK1, USER2, PACK2, USER3, PACK3, USER4, PACK4 = [info.strip() for info in winners_info]
                selected_announcement = await self.get_announcement("Voting End")
                if selected_announcement is None:
                    await ctx.send('Voting End announcement template not found.')
                    return

                announcement_message = selected_announcement.format(USER1=USER1, PACK1=PACK1,
                                                                USER2=USER2, PACK2=PACK2,
                                                                USER3=USER3, PACK3=PACK3,
                                                                USER4=USER4, PACK4=PACK4)

                await announcement_channel.send(announcement_message)
                await ctx.send('Announcement confirmed.')

            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond. Please try again.")
            return

        # Handle "Schedule" announcement
        if lower_message == "schedule":
            schedule_cog = self.bot.get_cog("Schedule")
            if not schedule_cog:
                await ctx.send("Error: Schedule system is not loaded.")
                return

            schedule = schedule_cog.get_schedule()
            if schedule is None:
                await ctx.send("No schedule has been set. Use `!resetschedule` to set one.")
                return

            time1, time2, time3, time4 = schedule  # Unpack stored times

            # Load the Schedule announcement template
            selected_announcement = await self.get_announcement("Schedule")
            if selected_announcement is None:
                await ctx.send('Schedule announcement template not found.')
                return

            # Convert string times back to datetime objects
            try:
                time1, time2, time3, time4 = map(datetime.fromisoformat, schedule)
            except ValueError as e:
                await ctx.send("An error occurred while converting schedule times. Please check the format in the database.")
                print(f"Error converting schedule times: {e}")
                return

            announcement_message = selected_announcement.format(
                time1=f"<t:{int(time1.timestamp())}:F>",
                time2=f"<t:{int(time2.timestamp())}:F>",
                time3=f"<t:{int(time3.timestamp())}:F>",
                time4=f"<t:{int(time4.timestamp())}:F>"
            )

            await announcement_channel.send(announcement_message)
            await ctx.send('Announcement confirmed and sent.')
            return

        # Handle standard announcements
        selected_announcement = await self.get_announcement(message)
        if selected_announcement is None:
            await ctx.send(f'Announcement "{message}" not found. Try **"!help"** for available options.')
            return

        try:
            await self.process_announcement(announcement_channel, selected_announcement, message)
            await ctx.send('Announcement confirmed.')

        except Exception as e:
            error_msg = f'An error occurred while processing the announcement: {str(e)}'
            await ctx.send(error_msg)

            # Log error to moderator channel
            mod_log_channel = self.bot.get_channel(MOD_LOG_CHANNEL_ID)
            if mod_log_channel:
                await mod_log_channel.send(f"🚨 **Announcement Error** 🚨\nUser: {ctx.author.mention}\nError: {error_msg}")

        # If the message doesn't match any known announcement, suggest similar ones
        selected_announcement = await self.get_announcement(message)
        if selected_announcement is None:
            # Get a list of all announcement names
            with open('announcements.txt', 'r', encoding='utf-8') as file:
                announcements = [line.strip().splitlines()[0].lower() for line in file.read().split('===') if line.strip()]
            
            # Find the closest matches to what the user entered
            matches = get_close_matches(message.lower(), announcements, n=3, cutoff=0.5)

            suggestion_msg = f'Announcement "{message}" not found.'
            if matches:
                suggestion_msg += f' Did you mean: {", ".join(matches)}?'
            
            await ctx.send(suggestion_msg)
            return

    async def get_announcement(self, message):
        try:
            with open('announcements.txt', 'r', encoding='utf-8') as file:
                content = file.read()
                announcements = content.split('===')

            for announcement in announcements:
                lines = announcement.strip().splitlines()
                if lines and lines[0].strip().lower() == message.lower():
                    return "\n".join(lines[1:])
        except Exception as e:
            print(f'Error reading announcements: {str(e)}')
        return None

    async def process_announcement(self, channel, selected_announcement, message):
        # Handle specific messages here, similar to your original code
        await channel.send(selected_announcement)

# This is where the cog is added to the bot
async def setup(bot):
    await bot.add_cog(AnnouncementCog(bot))
    print("Loaded AnnouncementCog!")  # This should print when the cog is loaded
