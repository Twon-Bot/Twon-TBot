import discord
from discord.ext import commands
from datetime import datetime  # Ensure this import is included
import asyncio
from delay import DelayedAnnouncements  # Import the DelayedAnnouncements class

class AnnouncementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.delayed_announcements = DelayedAnnouncements(bot)  # Instantiate DelayedAnnouncements here

    async def send_announcement(self, ctx, announcement_message):
        """Sends the formatted announcement message in the designated channel."""
        # Use the announcement channel based on the mode (test or normal)
        channel_id = 1350575699567710259 if ctx.command.name == "testannounce" else 1350575635340464138
        announcement_channel = self.bot.get_channel(channel_id)

        if announcement_channel is None:
            await ctx.send("Error: Announcement channel not found.")
            return
        
        await announcement_channel.send(announcement_message)

    async def handle_wonder_pick_or_voting_end(self, ctx, lower_message, num_winners=None):
        """
        Handles input and formatting for Wonder Pick and Voting End announcements.
        """
        if lower_message.startswith("wonder pick"):
            await ctx.send(f"**Please input the {num_winners} winners and their pack contents**, in the following format:\n"
                           f"***User 1, User 1's Pack, \nUser 2, User 2's Pack{', \nUser 3, User 3\'s Pack' if num_winners > 2 else ''}{', \nUser 4, User 4\'s Pack' if num_winners > 3 else ''}***\n"
                           "*Note: Commas **must** separate each input!*")
            expected_inputs = num_winners * 2

        elif lower_message == "voting end":
            await ctx.send("**Please input the 4 vote winners and their pack contents**, in the following format:\n"
                           "***User 1, User 1's Pack, \nUser 2, User 2's Pack, \nUser 3, User 3's Pack, \nUser 4, User 4's Pack***\n"
                           "*Note: Commas **must** separate each input!*")
            expected_inputs = 8  # Always 4 users + 4 packs

        else:
            return  # If the function was called incorrectly, just return

        # Collect user response
        try:
            msg = await self.bot.wait_for('message', timeout=60.0, 
                                        check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
            winners_info = msg.content.split(',')

            if len(winners_info) != expected_inputs:
                await ctx.send(f"Please provide **exactly {expected_inputs} values**: \n"
                            f"***{' \\n'.join(['USER' + str(i + 1) + ', User ' + str(i + 1) + '\'s Pack' for i in range(num_winners if num_winners else 4)])}***\n\n"
                            "*The program has been reset, **please try again.***")
                return

            # Prepare the announcement message
            winners_info = [info.strip() for info in winners_info]

            if lower_message.startswith("wonder pick"):
                selected_announcement = await self.delayed_announcements.get_announcement(lower_message)
                if selected_announcement is None:
                    await ctx.send(f"{lower_message.title()} announcement template not found.")
                    return

                announcement_message = selected_announcement.format(*winners_info)

            elif lower_message == "voting end":
                USER1, PACK1, USER2, PACK2, USER3, PACK3, USER4, PACK4 = winners_info
                selected_announcement = await self.get_announcement("Voting End")
                if selected_announcement is None:
                    await ctx.send('Voting End announcement template not found.')
                    return

                announcement_message = selected_announcement.format(USER1=USER1, PACK1=PACK1,
                                                                    USER2=USER2, PACK2=PACK2,
                                                                    USER3=USER3, PACK3=PACK3,
                                                                    USER4=USER4, PACK4=PACK4)

            await self.send_announcement(ctx, announcement_message)  # Send formatted announcement
            await ctx.send('Announcement confirmed.')  # Add confirmation message after sending

        except asyncio.TimeoutError:
            await ctx.send("You took too long to respond. Please try again.")

    @commands.command(aliases=["ann"])
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner')  # Keep role restriction
    async def announce(self, ctx, *, message: str):
        # Check if the announcement exists first using the delayed_announcements instance
        selected_announcement = await self.delayed_announcements.get_announcement(message)  # Call the method here
        if selected_announcement is None:
            await ctx.send(f'Announcement "{message}" not found. Try **"!!help announce"** for available options.')
            return  # Exit if the announcement is not found

        lower_message = message.lower()

        # If it's a Wonder Pick or Voting End announcement
        if "wonder pick" in lower_message or lower_message == "voting end":
            num_winners = int(lower_message[-1]) if "wonder pick" in lower_message else 4
            await self.handle_wonder_pick_or_voting_end(ctx, lower_message, num_winners)
            return

        # If it reaches here, show confirmation
        confirmation_msg = await ctx.send("React with 👍 to confirm this announcement to @everyone. React with ⏳ to schedule it.")
        await confirmation_msg.add_reaction("👍")
        await confirmation_msg.add_reaction("⏳")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["👍", "⏳"] and reaction.message.id == confirmation_msg.id

        try:
            reaction, user = await self.bot.wait_for('reaction_add', check=check, timeout=30)
            if str(reaction.emoji) == "👍":
                await self.handle_announcement(ctx, message, test_mode=False)
                await ctx.send('Announcement confirmed.')  # Add confirmation after announcement is sent
            elif str(reaction.emoji) == "⏳":
                await ctx.send("Please enter the time (e.g., `MM/DD HH:MM`).")

                def time_check(m):
                    return m.author == ctx.author and m.channel == ctx.channel
                
                time_msg = await self.bot.wait_for('message', check=time_check, timeout=60)
                scheduled_time = time_msg.content.strip()  # Ensure to strip any whitespace

                # Call the delay_announcement method
                await self.delayed_announcements.delay_announcement(ctx, message, scheduled_time)  # Ensure this method is async

        except asyncio.TimeoutError:
            await ctx.send("Announcement confirmation timed out. Please try again.")

    @commands.command(aliases=["testann"])
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner')  # Keep role restriction
    async def testannounce(self, ctx, *, message: str):
        await self.handle_announcement(ctx, message, test_mode=True)

    async def handle_announcement(self, ctx, message: str, test_mode: bool):
        # Determine which channel to send to (1st 'test', 2nd MAIN)
        channel_id = 1350575699567710259 if test_mode else 1350575635340464138
        announcement_channel = self.bot.get_channel(channel_id)

        if announcement_channel is None:
            await ctx.send("Error: Announcement channel not found.")
            return

        # If the announcement exists, proceed to prompt for user input based on the type of announcement
        lower_message = message.lower()

        # If it's a Wonder Pick or Voting End announcement
        if "wonder pick" in lower_message or lower_message == "voting end":
            num_winners = int(lower_message[-1]) if "wonder pick" in lower_message else 4
            await self.handle_wonder_pick_or_voting_end(ctx, lower_message, num_winners)
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
            await ctx.send(f'Announcement "{message}" not found. Try **"!!help announce"** for available options.')
            return

        try:
            await self.process_announcement(announcement_channel, selected_announcement, message)
            await ctx.send('Announcement confirmed.')  # Confirmation message after processing

        except Exception as e:
            error_msg = f'An error occurred while processing the announcement: {str(e)}'
            await ctx.send(error_msg)  # Send error in the same channel

    async def get_announcement(self, message):
        try:
            with open('announcements.txt', 'r', encoding='utf-8') as file:
                content = file.read()
                announcements = content.split('===')  # Assuming announcements are separated by '==='

            for announcement in announcements:
                lines = announcement.strip().splitlines()
                if lines and lines[0].strip().lower() == message.lower():
                    return "\n".join(lines[1:])  # Return the formatted message part
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
