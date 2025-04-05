import discord
from discord.ext import commands
from datetime import datetime
import asyncio
import pytz
from dotenv import load_dotenv
import os

# Get channel ID's from .env
load_dotenv()

ANNOUNCEMENT_CHANNEL_ID = int(os.getenv("ANNOUNCEMENT_CHANNEL_ID"))
TEST_ANNOUNCEMENT_CHANNEL_ID = int(os.getenv("TEST_ANNOUNCEMENT_CHANNEL_ID"))
SCHEDULE_CHANNEL_ID = int(os.getenv("SCHEDULE_CHANNEL_ID"))
ACTIVITY_CHECK_CHANNEL_ID = int(os.getenv("ACTIVITY_CHECK_CHANNEL_ID"))

class AnnouncementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Helper: Create a schedule embed matching !!csch ──
    def create_schedule_embed(self, schedule):
        try:
            time1, time2, time3, time4 = map(datetime.fromisoformat, schedule)
            embed = discord.Embed(
                title="✅ **The current schedule is as follows:**",
                color=0x39FF14  # Neon lime green
            )
            embed.description = (
                "──────────────────────────────\n" +
                f"🔹 Voting will begin at:\n**<t:{int(time1.timestamp())}:F>**\n\n"
                f"🔹 Picking will begin at:\n**<t:{int(time2.timestamp())}:F>**\n\n"
                f"🔹 Owner WP will begin at:\n**<t:{int(time3.timestamp())}:F>**\n\n"
                f"🔹 Pack will die at:\n**<t:{int(time4.timestamp())}:F>**"
            )
            return embed
        except Exception as e:
            print(f"Error creating schedule embed: {e}")
            return None

    async def send_announcement(self, ctx, announcement_message, test_mode=False):
        """Sends the formatted announcement message."""
        channel_id = TEST_ANNOUNCEMENT_CHANNEL_ID if test_mode else ANNOUNCEMENT_CHANNEL_ID
        announcement_channel = self.bot.get_channel(channel_id)
        
        if announcement_channel is None:
            await ctx.send("Error: Announcement channel not found.")
            return
        
        await announcement_channel.send(announcement_message)

    async def handle_wonder_pick_or_voting_end(self, ctx, lower_message, message, num_winners=None, test_mode=False):
        if lower_message.startswith("wonder pick"):
            await ctx.send(f"**Please input the {num_winners} winners and their pack contents**, in the following format:\n"
                           f"***User 1, User 1's Pack, \nUser 2, User 2's Pack{', \nUser 3, User 3\'s Pack' if num_winners > 2 else ''}{', \nUser 4, User 4\'s Pack' if num_winners > 3 else ''}***\n"
                           "*Note: Commas **must** separate each input!*")
            expected_inputs = num_winners * 2

        elif lower_message == "voting end":
            await ctx.send("**Please input the 4 vote winners and their pack contents**, in the following format:\n"
                           "***User 1, User 1's Pack, \nUser 2, User 2's Pack, \nUser 3, User 3's Pack, \nUser 4, User 4's Pack***\n"
                           "*Note: Commas **must** separate each input!*")
            expected_inputs = 8
        else:
            return

        try:
            msg = await self.bot.wait_for('message', timeout=60.0, 
                                           check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
            winners_info = [info.strip() for info in msg.content.split(',')]

            if len(winners_info) != expected_inputs:
                await ctx.send(f"This requires **exactly {expected_inputs} values**: \n"
                               f"***{' \n'.join(['USER' + str(i + 1) + ', User ' + str(i + 1) + '\'s Pack' for i in range(num_winners if num_winners else 4)])}***\n\n"
                               "*The program has **been reset**, **please try again.***")
                return

            delay_cog = self.bot.get_cog("DelayedAnnouncements")
            if delay_cog is None:
                await ctx.send("DelayedAnnouncements cog is not available.")
                return

            if lower_message.startswith("wonder pick"):
                user_pack_data = {}
                for i in range(num_winners):
                    user_pack_data[f"USER{i+1}"] = winners_info[2*i]
                    user_pack_data[f"PACK{i+1}"] = winners_info[2*i+1]
                # Build a dynamic key such as "Wonder Pick 2", "Wonder Pick 3", or "Wonder Pick 4"
                template_key = f"Wonder Pick {num_winners}"
                announcement_message = await self.get_announcement(template_key, test_mode=test_mode)
                if announcement_message is None:
                    await ctx.send(f'{template_key} announcement template not found.')
                    return
                announcement_message = announcement_message.format(**user_pack_data)

            elif lower_message == "voting end":
                user_pack_data = {
                    "USER1": winners_info[0],
                    "PACK1": winners_info[1],
                    "USER2": winners_info[2],
                    "PACK2": winners_info[3],
                    "USER3": winners_info[4],
                    "PACK3": winners_info[5],
                    "USER4": winners_info[6],
                    "PACK4": winners_info[7]
                }
                selected_announcement = await self.get_announcement("Voting End", test_mode=test_mode)
                if selected_announcement is None:
                    await ctx.send('Voting End announcement template not found.')
                    return
                announcement_message = selected_announcement.format(**user_pack_data)

        except asyncio.TimeoutError:
            await ctx.send("You took too long to respond. Please try again.")
            return

        if ctx.invoked_with in ["ann", "announce"]:
            confirm_msg = await ctx.send("React with 👍 to confirm this announcement to @/everyone. React with ⏳ to schedule it.")
            await confirm_msg.add_reaction("👍")
            await confirm_msg.add_reaction("⏳")

            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["👍", "⏳"] and reaction.message.id == confirm_msg.id

            try:
                reaction, user = await self.bot.wait_for("reaction_add", check=check, timeout=30)
                if str(reaction.emoji) == "👍":
                    await self.send_announcement(ctx, announcement_message)
                    # ──[Change #1: For schedule announcements, also output current schedule]─
                    if message.lower() == "schedule":
                        schedule_cog = self.bot.get_cog("Schedule")
                        if schedule_cog:
                            schedule = schedule_cog.get_schedule()
                            if schedule:
                                embed = self.create_schedule_embed(schedule)
                                if embed:
                                    target_channel = self.bot.get_channel(SCHEDULE_CHANNEL_ID)
                                    if target_channel:
                                        await target_channel.send(embed=embed)
                    await ctx.send("Announcement confirmed.")
                elif str(reaction.emoji) == "⏳":
                    await ctx.send("Please enter the time for scheduling (e.g., MM/DD HH:MM).")
                    time_msg = await self.bot.wait_for("message", 
                                                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel, 
                                                    timeout=60)
                    scheduled_time = time_msg.content.strip()
                    if lower_message == "schedule":
                        schedule_cog = self.bot.get_cog("Schedule")
                        schedule = schedule_cog.get_schedule() if schedule_cog else None
                        if schedule is None:
                            await ctx.send("No schedule has been set. Use `!resetschedule` to set one.")
                            return
                        try:
                            time1, time2, time3, time4 = map(datetime.fromisoformat, schedule)
                        except ValueError as e:
                            await ctx.send("An error occurred while converting schedule times. Please check the database.")
                            return
                        subs = {
                            "time1": f"<t:{int(time1.timestamp())}:F>",
                            "time2": f"<t:{int(time2.timestamp())}:F>",
                            "time3": f"<t:{int(time3.timestamp())}:F>",
                            "time4": f"<t:{int(time4.timestamp())}:F>",
                        }
                        await delay_cog.delay_announcement(ctx, lower_message, scheduled_time, substitutions=subs)
                    else:
                        # For wonder pick or voting end, pass the substitutions dictionary (user_pack_data) if available.
                        if lower_message == "voting end" or lower_message.startswith("wonder pick"):
                            await delay_cog.delay_announcement(ctx, lower_message, scheduled_time, substitutions=user_pack_data)
                        else:
                            await delay_cog.delay_announcement(ctx, lower_message, scheduled_time)
            except asyncio.TimeoutError:
                await ctx.send("Announcement confirmation timed out. Please try again.")
        else:
            await self.send_announcement(ctx, announcement_message, test_mode=True)
            # ──[Change #1 for testannounce schedule: Output current schedule]─
            if message.lower() == "schedule":
                schedule_cog = self.bot.get_cog("Schedule")
                if schedule_cog:
                    schedule = schedule_cog.get_schedule()
                    if schedule:
                        embed = self.create_schedule_embed(schedule)
                        target_channel = self.bot.get_channel(SCHEDULE_CHANNEL_ID)
                        if embed and target_channel:
                            await target_channel.send(embed=embed)
            await ctx.send("Announcement confirmed.")

    @commands.command(aliases=["ann"])
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner')
    async def announce(self, ctx, *, message: str = None):
        if message is None:
            await ctx.send('Error: Please provide an announcement. Try **"!!help announce"** for available options.')
            return

        delay_cog = self.bot.get_cog("DelayedAnnouncements")
        if delay_cog is None:
            await ctx.send("DelayedAnnouncements cog is not available yet.")
            return

        selected_announcement = await delay_cog.get_announcement(message)
        if selected_announcement is None:
            await ctx.send(f'Announcement "{message}" not found. Try **"!!help announce"** for available options.')
            return

        lower_message = message.lower()

        # ──[Change #2: Activity Check - collect deadline then remind user before confirmation]─
        if lower_message == "activity check":
            await ctx.send("**Please enter the deadline for the Activity Check**\n(e.g., `MM/DD HH:MM`).")
            try:
                time_msg = await self.bot.wait_for(
                    "message",
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                    timeout=60
                )
            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond. Please try again.")
                return
            check_time_input = time_msg.content.strip()
            schedule_cog = self.bot.get_cog("Schedule")
            user_timezone = schedule_cog.get_user_timezone(ctx.author.id) if schedule_cog else "UTC"
            tz = pytz.timezone(user_timezone)
            try:
                local_time = datetime.strptime(check_time_input, "%m/%d %H:%M")
                local_time = local_time.replace(year=datetime.now(tz).year)
                localized_time = tz.localize(local_time)
                timestamp = int(localized_time.timestamp())
                checktime_formatted = f"<t:{timestamp}:F>"
            except Exception as e:
                await ctx.send("Invalid time format! Use MM/DD HH:MM.")
                return

            # Send the SESH poll reminder in the same channel BEFORE confirmation
            await ctx.send("### ⚠️Reminder: After this announcement, please post the activity check SESH poll manually in the activity check channel.")

            confirmation_msg = await ctx.send("React with 👍 to confirm this announcement to @/everyone. React with ⏳ to schedule it.")
            await confirmation_msg.add_reaction("👍")
            await confirmation_msg.add_reaction("⏳")
            
            def check_reaction(reaction, user):
                return (
                    user == ctx.author and 
                    str(reaction.emoji) in ["👍", "⏳"] and 
                    reaction.message.id == confirmation_msg.id
                )
            try:
                reaction, user = await self.bot.wait_for("reaction_add", check=check_reaction, timeout=30)
                if str(reaction.emoji) == "👍":
                    selected_announcement = await self.get_announcement("Activity Check")
                    if selected_announcement is None:
                        await ctx.send('Activity Check announcement template not found.')
                        return
                    announcement_message = selected_announcement.format(CHECKTIME=checktime_formatted)
                    channel_id = ACTIVITY_CHECK_CHANNEL_ID
                    announcement_channel = self.bot.get_channel(channel_id)
                    if announcement_channel is None:
                        await ctx.send("Error: Activity Check channel not found.")
                        return
                    await announcement_channel.send(announcement_message)
                    await ctx.send('Announcement confirmed.')
                elif str(reaction.emoji) == "⏳":
                    await ctx.send("**Please enter the time for scheduling (e.g., `MM/DD HH:MM`).**")
                    try:
                        time_msg = await self.bot.wait_for(
                            "message",
                            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                            timeout=60
                        )
                    except asyncio.TimeoutError:
                        await ctx.send("You took too long to respond. Please try again.")
                        return
                    scheduled_time = time_msg.content.strip()
                    await delay_cog.delay_announcement(ctx, message, scheduled_time, substitutions={"CHECKTIME": checktime_formatted})
            except asyncio.TimeoutError:
                await ctx.send("Announcement confirmation timed out. Please try again.")
            return

        # Delegate Wonder Pick or Voting End
        if "wonder pick" in lower_message or lower_message == "voting end":
            num_winners = int(lower_message[-1]) if "wonder pick" in lower_message else 4
            await self.handle_wonder_pick_or_voting_end(ctx, lower_message, message, num_winners)
            return

        confirmation_msg = await ctx.send("React with 👍 to confirm this announcement to @/everyone. React with ⏳ to schedule it.")
        await confirmation_msg.add_reaction("👍")
        await confirmation_msg.add_reaction("⏳")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["👍", "⏳"] and reaction.message.id == confirmation_msg.id

        try:
            reaction, user = await self.bot.wait_for("reaction_add", check=check, timeout=30)
            if str(reaction.emoji) == "👍":
                await self.handle_announcement(ctx, message, test_mode=False)
            elif str(reaction.emoji) == "⏳":
                await ctx.send("Please enter the time for scheduling (e.g., `MM/DD HH:MM`).")
                time_msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                scheduled_time = time_msg.content.strip()
                if lower_message == "schedule":
                    schedule_cog = self.bot.get_cog("Schedule")
                    schedule = schedule_cog.get_schedule() if schedule_cog else None
                    if schedule is None:
                        await ctx.send("No schedule has been set. Use `!resetschedule` to set one.")
                        return
                    try:
                        time1, time2, time3, time4 = map(datetime.fromisoformat, schedule)
                    except ValueError as e:
                        await ctx.send("An error occurred while converting schedule times. Please check the database.")
                        return
                    subs = {
                        "time1": f"<t:{int(time1.timestamp())}:F>",
                        "time2": f"<t:{int(time2.timestamp())}:F>",
                        "time3": f"<t:{int(time3.timestamp())}:F>",
                        "time4": f"<t:{int(time4.timestamp())}:F>",
                    }
                    await delay_cog.delay_announcement(ctx, message, scheduled_time, substitutions=subs)
                else:
                    await delay_cog.delay_announcement(ctx, message, scheduled_time)
        except asyncio.TimeoutError:
            await ctx.send("Announcement confirmation timed out. Please try again.")

    @commands.command(aliases=["testann"])
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner')
    async def testannounce(self, ctx, *, message: str = None):
        if message is None:
            await ctx.send('Error: Please provide an announcement. Try **"!!help announce"** for available options.')
            return
        await self.handle_announcement(ctx, message, test_mode=True)

    async def handle_announcement(self, ctx, message: str, test_mode: bool):
        lower_message = message.lower()
        if "wonder pick" in lower_message or lower_message == "voting end":
            num_winners = int(lower_message[-1]) if "wonder pick" in lower_message else 4
            await self.handle_wonder_pick_or_voting_end(ctx, lower_message, message, num_winners, test_mode=test_mode)
            return
        if lower_message == "schedule":
            schedule_cog = self.bot.get_cog("Schedule")
            if not schedule_cog:
                await ctx.send("Error: Schedule system is not loaded.")
                return
            schedule = schedule_cog.get_schedule()
            if schedule is None:
                await ctx.send("No schedule has been set. Use `!resetschedule` to set one.")
                return
            try:
                time1, time2, time3, time4 = map(datetime.fromisoformat, schedule)
            except ValueError as e:
                await ctx.send("An error occurred while converting schedule times. Please check the format in the database.")
                print(f"Error converting schedule times: {e}")
                return
            selected_announcement = await self.get_announcement("Schedule", test_mode=test_mode)
            if selected_announcement is None:
                await ctx.send('Schedule announcement template not found.')
                return
            announcement_message = selected_announcement.format(
                time1=f"<t:{int(time1.timestamp())}:F>",
                time2=f"<t:{int(time2.timestamp())}:F>",
                time3=f"<t:{int(time3.timestamp())}:F>",
                time4=f"<t:{int(time4.timestamp())}:F>"
            )
            channel_id = TEST_ANNOUNCEMENT_CHANNEL_ID if test_mode else SCHEDULE_CHANNEL_ID
            announcement_channel = self.bot.get_channel(channel_id)
            if announcement_channel is None:
                await ctx.send("Error: Schedule channel not found.")
                return
            await announcement_channel.send(announcement_message)
            # ──[Change: Output the current schedule embed in the same channel]─
            embed = self.create_schedule_embed(schedule)
            if embed:
                await announcement_channel.send(embed=embed)
            await ctx.send('Announcement confirmed and sent.')
            return
        if lower_message == "activity check":
            await ctx.send("**Please enter the deadline for the Activity Check**\n(e.g., `MM/DD HH:MM`).")
            try:
                time_msg = await self.bot.wait_for(
                    "message",
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                    timeout=60
                )
            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond. Please try again.")
                return
            check_time_input = time_msg.content.strip()
            schedule_cog = self.bot.get_cog("Schedule")
            user_timezone = schedule_cog.get_user_timezone(ctx.author.id) if schedule_cog else "UTC"
            tz = pytz.timezone(user_timezone)
            try:
                local_time = datetime.strptime(check_time_input, "%m/%d %H:%M")
                local_time = local_time.replace(year=datetime.now(tz).year)
                localized_time = tz.localize(local_time)
                timestamp = int(localized_time.timestamp())
                checktime_formatted = f"<t:{timestamp}:F>"
            except Exception as e:
                await ctx.send("Invalid time format! Use MM/DD HH:MM.")
                return
            # ──[Change #2 in handle_announcement: Reminder for SESH poll]─
            await ctx.send("### ⚠️Reminder: After this announcement, please post the activity check SESH poll manually in the activity check channel.")
            selected_announcement = await self.get_announcement("Activity Check", test_mode=test_mode)
            if selected_announcement is None:
                await ctx.send('Activity Check announcement template not found.')
                return
            announcement_message = selected_announcement.format(CHECKTIME=checktime_formatted)
            channel_id = TEST_ANNOUNCEMENT_CHANNEL_ID if test_mode else ACTIVITY_CHECK_CHANNEL_ID
            announcement_channel = self.bot.get_channel(channel_id)
            if announcement_channel is None:
                await ctx.send("Error: Activity Check channel not found.")
                return
            await announcement_channel.send(announcement_message)
            await ctx.send('Announcement confirmed.')
            return
        selected_announcement = await self.get_announcement(message, test_mode=test_mode)
        if selected_announcement is None:
            await ctx.send(f'Announcement "{message}" not found. Try **"!!help announce"** for available options.')
            return
        channel_id = TEST_ANNOUNCEMENT_CHANNEL_ID if test_mode else ANNOUNCEMENT_CHANNEL_ID
        announcement_channel = self.bot.get_channel(channel_id)
        if announcement_channel is None:
            await ctx.send("Error: Announcement channel not found.")
            return
        try:
            await self.process_announcement(announcement_channel, selected_announcement, message)
            await ctx.send('Announcement confirmed.')
        except Exception as e:
            error_msg = f'An error occurred while processing the announcement: {str(e)}'
            await ctx.send(error_msg)

    async def get_announcement(self, message, test_mode=False):
        file_to_open = 'testannouncements.txt' if test_mode else 'announcements.txt'
        try:
            with open(file_to_open, 'r', encoding='utf-8') as file:
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
        await channel.send(selected_announcement)

async def setup(bot):
    await bot.add_cog(AnnouncementCog(bot))
    print("Loaded AnnouncementCog!")
