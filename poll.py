import discord
from discord.ext import commands
from discord import app_commands
import csv
import io
import asyncio
from datetime import datetime, timedelta
import pytz
import re  # NEW: for regex matching

# A list of explicit regional indicator emojis for options.
OPTION_EMOJIS = ["🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", "🇭", "🇮", "🇯"]

def get_user_timezone(user_id):
    """Helper: Look up user timezone in bot_data.db; default to UTC if not set."""
    import sqlite3
    with sqlite3.connect("bot_data.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT timezone FROM user_timezones WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else "UTC"

def format_time_delta(delta: timedelta):
    """Helper: Return a human-friendly string for a timedelta."""
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return "0 minutes"
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    parts = []
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return " ".join(parts)

class ConfirmView(discord.ui.View):
    def __init__(self, timeout: float = 30):
        super().__init__(timeout=timeout)
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = False
        self.stop()

class AddOptionModal(discord.ui.Modal, title="Add an Option"):
    new_option = discord.ui.TextInput(label="New Option", placeholder="Enter your new poll option here", max_length=100)

    def __init__(self, poll_data, poll_message):
        super().__init__()
        self.poll_data = poll_data
        self.poll_message = poll_message

    async def on_submit(self, interaction: discord.Interaction):
        option_text = self.new_option.value.strip()
        if option_text in self.poll_data["options"]:
            await interaction.response.send_message("That option already exists.", ephemeral=True)
            return

        # Check maximum of 10 options.
        if len(self.poll_data["options"]) >= 10:
            await interaction.response.send_message("Maximum number of options reached.", ephemeral=True)
            return

        self.poll_data["options"].append(option_text)
        self.poll_data["vote_count"][option_text] = 0
        # Add a new button for the added option.
        new_button = discord.ui.Button(label=OPTION_EMOJIS[len(self.poll_data["options"]) - 1],
                                         custom_id=option_text)
        new_button.callback = self.poll_data["button_callback"]
        self.poll_data["view"].add_item(new_button)
        await self.poll_message.edit(view=self.poll_data["view"])
        await self.poll_message.edit(embed=self.poll_data["build_embed"](self.poll_data))
        await interaction.response.send_message(f"Added option: {option_text}", ephemeral=True)

class PollCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Store poll data per poll message id.
        self.polls = {}

    @commands.command()
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner')
    async def poll(self, ctx, *, args: str):
        """
        Create a poll. Defaults to single voting.
        Format:
          !!poll [mention] [multiple] Question? | Option 1 | Option 2 | ... | MM/DD HH:MM (end time)
        The last field (if it matches MM/DD HH:MM) is used as the poll end time.
        """
        # Check for mention flag.
        mention = False
        if args.startswith("mention "):
            mention = True
            args = args[len("mention "):].strip()

        # Check if the first argument is "multiple"
        if args.startswith("multiple"):
            voting_type = "multiple"
            args = args[len("multiple "):].strip()  # Remove "multiple " from args
        else:
            voting_type = "single"

        # Split the input into parts using "|" as a delimiter.
        parts = [part.strip() for part in args.split('|')]
        if len(parts) < 3:
            await ctx.send("Please provide a question, at least 2 options, and optionally an end time (MM/DD HH:MM).")
            return

        # Check if the last part matches an end time format (MM/DD HH:MM)
        end_time_str = parts[-1]
        if re.match(r"^\d{2}/\d{2} \d{2}:\d{2}$", end_time_str):
            try:
                user_tz = pytz.timezone(get_user_timezone(ctx.author.id))
                poll_end_local = datetime.strptime(end_time_str, "%m/%d %H:%M")
                # Set the current year
                poll_end_local = poll_end_local.replace(year=datetime.now(user_tz).year)
                poll_end = user_tz.localize(poll_end_local).astimezone(pytz.utc)
                parts = parts[:-1]  # Remove the end time from the options list
            except Exception as e:
                await ctx.send(f"Error parsing end time: {e}")
                return
        else:
            poll_end = None  # No end time provided

        question = parts[0]
        options = parts[1:]
        if len(options) < 2:
            await ctx.send("Please provide at least 2 options for the poll.")
            return
        if len(options) > 10:
            await ctx.send("You cannot have more than 10 options for the poll.")
            return

        # Build initial poll state.
        poll_data = {
            "question": question,
            "options": options,
            "vote_count": {option: 0 for option in options},
            "total_votes": 0,
            "user_votes": {},  # For each user id, store vote (str for single, list for multiple)
            "voting_type": voting_type,
            "author": ctx.author.display_name,
            "author_id": ctx.author.id,  # For permission checks
            "end_time": poll_end,       # NEW: store poll end time (UTC) if provided
            "closed": False,          # NEW: flag if poll is closed
        }

        # Create buttons for each option using explicit emojis.
        buttons = []
        for i, option in enumerate(options):
            button = discord.ui.Button(label=OPTION_EMOJIS[i], custom_id=option)
            buttons.append(button)

        view = discord.ui.View(timeout=None)
        for button in buttons:
            view.add_item(button)

        # Add export button (with gear emoji) to export votes for THIS poll.
        export_button = discord.ui.Button(label="⚙️", style=discord.ButtonStyle.secondary, custom_id="export")
        view.add_item(export_button)

        # Add plus button (with plus emoji) to add an option.
        add_option_button = discord.ui.Button(label="➕", style=discord.ButtonStyle.secondary, custom_id="add_option")
        view.add_item(add_option_button)

        # Define the callback for poll option buttons.
        async def button_callback(interaction: discord.Interaction):
            pid = interaction.message.id
            poll = self.polls.get(pid)
            if poll is None:
                await interaction.response.send_message("Poll data not found.", ephemeral=True)
                return

            # If the poll is closed, disallow voting.
            if poll.get("closed", False):
                await interaction.response.send_message("This poll has closed.", ephemeral=True)
                return

            user_id = interaction.user.id
            selected_option = interaction.data['custom_id']

            # If user already voted for this option, ask for confirmation to remove vote.
            if user_id in poll["user_votes"]:
                if poll["voting_type"] == 'single':
                    if poll["user_votes"][user_id] == selected_option:
                        confirm_view = ConfirmView()
                        await interaction.response.send_message("You already voted for this option. Remove vote?", view=confirm_view, ephemeral=True)
                        await confirm_view.wait()
                        if confirm_view.value:
                            poll["total_votes"] -= 1
                            await self.update_vote_count(poll, selected_option, -1)
                            poll["user_votes"].pop(user_id)
                            await interaction.followup.send("Your vote has been removed.", ephemeral=True)
                        else:
                            await interaction.followup.send("Vote removal canceled.", ephemeral=True)
                        await interaction.message.edit(embed=poll["build_embed"](poll), view=poll["view"])
                        return
                elif poll["voting_type"] == 'multiple':
                    if selected_option in poll["user_votes"][user_id]:
                        confirm_view = ConfirmView()
                        await interaction.response.send_message("You already voted for this option. Remove vote?", view=confirm_view, ephemeral=True)
                        await confirm_view.wait()
                        if confirm_view.value:
                            poll["user_votes"][user_id].remove(selected_option)
                            poll["total_votes"] -= 1
                            await self.update_vote_count(poll, selected_option, -1)
                            await interaction.followup.send("Your vote has been removed.", ephemeral=True)
                        else:
                            await interaction.followup.send("Vote removal canceled.", ephemeral=True)
                        await interaction.message.edit(embed=poll["build_embed"](poll), view=poll["view"])
                        return

            try:
                if poll["voting_type"] == 'single':
                    previous_vote = poll["user_votes"].get(user_id)
                    if previous_vote and previous_vote != selected_option:
                        poll["total_votes"] -= 1
                        await self.update_vote_count(poll, previous_vote, -1)
                    poll["user_votes"][user_id] = selected_option
                    poll["total_votes"] += 1
                    await self.update_vote_count(poll, selected_option, 1)
                    await interaction.response.send_message(f"You voted for: {selected_option}", ephemeral=True)
                elif poll["voting_type"] == 'multiple':
                    if user_id not in poll["user_votes"]:
                        poll["user_votes"][user_id] = []
                    poll["user_votes"][user_id].append(selected_option)
                    poll["total_votes"] += 1
                    await self.update_vote_count(poll, selected_option, 1)
                    await interaction.response.send_message(f"Added your vote for: {selected_option}", ephemeral=True)

                await interaction.message.edit(embed=poll["build_embed"](poll), view=poll["view"])

            except Exception as e:
                print(f"Failed to send interaction response: {e}")

        # Define export button callback.
        async def export_callback(interaction: discord.Interaction):
            pid = interaction.message.id
            poll = self.polls.get(pid)
            if poll is None:
                await interaction.response.send_message("Poll data not found.", ephemeral=True)
                return
            # Restrict export button to poll creator.
            if interaction.user.id != poll["author_id"]:
                await interaction.response.send_message("Only the poll creator can export votes.", ephemeral=True)
                return

            output = io.StringIO()
            writer = csv.writer(output)
            # Do not include header row.
            for uid, vote in poll["user_votes"].items():
                if isinstance(vote, list):
                    vote_str = ', '.join(vote)
                else:
                    vote_str = vote
                writer.writerow([uid, vote_str])
            output.seek(0)
            file = discord.File(fp=io.BytesIO(output.read().encode('utf-8')), filename="poll_votes.csv")
            await interaction.response.send_message("Here are the poll votes:", file=file, ephemeral=True)

        # Define add option button callback.
        async def add_option_callback(interaction: discord.Interaction):
            pid = interaction.message.id
            poll = self.polls.get(pid)
            if poll is None:
                await interaction.response.send_message("Poll data not found.", ephemeral=True)
                return
            # Restrict add option button to poll creator.
            if interaction.user.id != poll["author_id"]:
                await interaction.response.send_message("Only the poll creator can add options.", ephemeral=True)
                return
            modal = AddOptionModal(poll, interaction.message)
            await interaction.response.send_modal(modal)

        for button in buttons:
            button.callback = button_callback

        export_button.callback = export_callback
        add_option_button.callback = add_option_callback

        poll_data["view"] = view

        # Build embed using description (to avoid extra spacing) and add a footer.
        def format_poll_results():
            result_message = ""
            for i, option in enumerate(poll_data["options"]):
                count = poll_data["vote_count"].get(option, 0)
                percentage = (count / poll_data["total_votes"] * 100) if poll_data["total_votes"] > 0 else 0
                bar_length = int(10 * percentage // 100)
                result_message += f"**{OPTION_EMOJIS[i]} {option}**\n"
                result_message += f"[{'🟩' * bar_length}{'⬜' * (10 - bar_length)}] | {percentage:.1f}% ({count})\n"
            return result_message

        poll_data["format_results"] = format_poll_results

        def build_embed(poll):
            # NEW: Build header text with time remaining (if poll end set)
            header = ""
            if poll.get("end_time"):
                now = datetime.utcnow().replace(tzinfo=pytz.utc)
                if not poll.get("closed") and poll["end_time"] > now:
                    delta = poll["end_time"] - now
                    header = f"⏳ Time remaining: {format_time_delta(delta)}\n\n"
                else:
                    header = "❌ Poll closed\n\n"
            footer_text = f"Made by {poll['author']}" if not poll.get("anonymous", False) else "Anonymous poll"
            embed = discord.Embed(
                title="📊 " + poll["question"],
                description=header + poll["format_results"](),
                color=0xfe407d
            )
            embed.set_footer(text=footer_text)
            return embed

        poll_data["build_embed"] = build_embed

        embed = build_embed(poll_data)

        if mention:
            await ctx.send("@everyone")

        poll_message = await ctx.send(embed=embed, view=view)
        poll_data["message_id"] = poll_message.id
        self.polls[poll_message.id] = poll_data

        # NEW: Schedule poll end if an end_time was provided.
        if poll_data.get("end_time"):
            self.bot.loop.create_task(self.schedule_poll_end(poll_message.id))

    async def update_vote_count(self, poll, option, increment):
        if option in poll["vote_count"]:
            poll["vote_count"][option] += increment

    async def schedule_poll_end(self, message_id):
        """Wait until the poll end time, then disable voting buttons (but keep export active) for 24 hours."""
        poll = self.polls.get(message_id)
        if not poll or not poll.get("end_time"):
            return
        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        wait_seconds = (poll["end_time"] - now).total_seconds()
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
        # Mark poll as closed.
        poll["closed"] = True
        # Disable all buttons except export.
        for item in poll["view"].children:
            if item.custom_id not in ["export"]:
                item.disabled = True
        # Update the poll embed to show poll closed.
        try:
            poll_message = await self.bot.get_channel(poll["view"].message.channel.id).fetch_message(message_id)
            await poll_message.edit(embed=poll["build_embed"](poll), view=poll["view"])
        except Exception as e:
            print(f"Error closing poll: {e}")
        # Keep poll data for 24 hours, then remove it.
        await asyncio.sleep(86400)
        self.polls.pop(message_id, None)

    # Slash command version remains similar (you can add an extra parameter for end time if desired)
    @app_commands.command(name="poll", description="Create a poll via slash command")
    @app_commands.describe(
        question="The poll question",
        option1="First option",
        option2="Second option",
        option3="Third option (optional)",
        option4="Fourth option (optional)",
        multiple="Allow multiple votes",
        anonymous="Hide the poll creator (anonymous poll)",
        end_time="Poll end time in MM/DD HH:MM (optional)"
    )
    async def poll_slash(self, interaction: discord.Interaction, question: str, option1: str, option2: str, option3: str = None, option4: str = None, multiple: bool = False, anonymous: bool = False, end_time: str = None):
        options = [option1, option2]
        if option3:
            options.append(option3)
        if option4:
            options.append(option4)
        if len(options) < 2:
            await interaction.response.send_message("Please provide at least 2 options.", ephemeral=True)
            return
        if len(options) > 10:
            await interaction.response.send_message("You cannot have more than 10 options.", ephemeral=True)
            return

        poll_data = {
            "question": question,
            "options": options,
            "vote_count": {option: 0 for option in options},
            "total_votes": 0,
            "user_votes": {},
            "voting_type": "multiple" if multiple else "single",
            "author": interaction.user.display_name,
            "author_id": interaction.user.id,
            "anonymous": anonymous,
        }
        # Process end_time if provided.
        if end_time:
            try:
                user_tz = pytz.timezone(get_user_timezone(interaction.user.id))
                poll_end_local = datetime.strptime(end_time, "%m/%d %H:%M")
                poll_end_local = poll_end_local.replace(year=datetime.now(user_tz).year)
                poll_data["end_time"] = user_tz.localize(poll_end_local).astimezone(pytz.utc)
            except Exception as e:
                await interaction.response.send_message(f"Error parsing end time: {e}", ephemeral=True)
                return

        buttons = []
        for i, option in enumerate(options):
            button = discord.ui.Button(label=OPTION_EMOJIS[i], custom_id=option)
            buttons.append(button)

        view = discord.ui.View(timeout=None)
        for button in buttons:
            view.add_item(button)

        export_button = discord.ui.Button(label="⚙️", style=discord.ButtonStyle.secondary, custom_id="export")
        view.add_item(export_button)

        add_option_button = discord.ui.Button(label="➕", style=discord.ButtonStyle.secondary, custom_id="add_option")
        view.add_item(add_option_button)

        async def button_callback(interaction: discord.Interaction):
            pid = interaction.message.id
            poll = self.polls.get(pid)
            if poll is None:
                await interaction.response.send_message("Poll data not found.", ephemeral=True)
                return
            if poll.get("closed", False):
                await interaction.response.send_message("This poll has closed.", ephemeral=True)
                return

            user_id = interaction.user.id
            selected_option = interaction.data['custom_id']

            if user_id in poll["user_votes"]:
                if poll["voting_type"] == 'single':
                    if poll["user_votes"][user_id] == selected_option:
                        confirm_view = ConfirmView()
                        await interaction.response.send_message("You already voted for this option. Remove vote?", view=confirm_view, ephemeral=True)
                        await confirm_view.wait()
                        if confirm_view.value:
                            poll["total_votes"] -= 1
                            await self.update_vote_count(poll, selected_option, -1)
                            poll["user_votes"].pop(user_id)
                            await interaction.followup.send("Your vote has been removed.", ephemeral=True)
                        else:
                            await interaction.followup.send("Vote removal canceled.", ephemeral=True)
                        await interaction.message.edit(embed=poll["build_embed"](poll), view=poll["view"])
                        return
                elif poll["voting_type"] == 'multiple':
                    if selected_option in poll["user_votes"].get(user_id, []):
                        confirm_view = ConfirmView()
                        await interaction.response.send_message("You already voted for this option. Remove vote?", view=confirm_view, ephemeral=True)
                        await confirm_view.wait()
                        if confirm_view.value:
                            poll["user_votes"][user_id].remove(selected_option)
                            poll["total_votes"] -= 1
                            await self.update_vote_count(poll, selected_option, -1)
                            await interaction.followup.send("Your vote has been removed.", ephemeral=True)
                        else:
                            await interaction.followup.send("Vote removal canceled.", ephemeral=True)
                        await interaction.message.edit(embed=poll["build_embed"](poll), view=poll["view"])
                        return

            try:
                if poll["voting_type"] == 'single':
                    previous_vote = poll["user_votes"].get(user_id)
                    if previous_vote and previous_vote != selected_option:
                        poll["total_votes"] -= 1
                        await self.update_vote_count(poll, previous_vote, -1)
                    poll["user_votes"][user_id] = selected_option
                    poll["total_votes"] += 1
                    await self.update_vote_count(poll, selected_option, 1)
                    await interaction.response.send_message(f"You voted for: {selected_option}", ephemeral=True)
                else:
                    if user_id not in poll["user_votes"]:
                        poll["user_votes"][user_id] = []
                    poll["user_votes"][user_id].append(selected_option)
                    poll["total_votes"] += 1
                    await self.update_vote_count(poll, selected_option, 1)
                    await interaction.response.send_message(f"Added your vote for: {selected_option}", ephemeral=True)

                await interaction.message.edit(embed=poll["build_embed"](poll), view=poll["view"])
            except Exception as e:
                print(f"Failed to process vote: {e}")

        async def export_callback(interaction: discord.Interaction):
            pid = interaction.message.id
            poll = self.polls.get(pid)
            if poll is None:
                await interaction.response.send_message("Poll data not found.", ephemeral=True)
                return
            if interaction.user.id != poll["author_id"]:
                await interaction.response.send_message("Only the poll creator can export votes.", ephemeral=True)
                return

            output = io.StringIO()
            writer = csv.writer(output)
            for uid, vote in poll["user_votes"].items():
                if isinstance(vote, list):
                    vote_str = ', '.join(vote)
                else:
                    vote_str = vote
                writer.writerow([uid, vote_str])
            output.seek(0)
            file = discord.File(fp=io.BytesIO(output.read().encode('utf-8')), filename="poll_votes.csv")
            await interaction.response.send_message("Here are the poll votes:", file=file, ephemeral=True)

        async def add_option_callback(interaction: discord.Interaction):
            pid = interaction.message.id
            poll = self.polls.get(pid)
            if poll is None:
                await interaction.response.send_message("Poll data not found.", ephemeral=True)
                return
            if interaction.user.id != poll["author_id"]:
                await interaction.response.send_message("Only the poll creator can add options.", ephemeral=True)
                return
            modal = AddOptionModal(poll, interaction.message)
            await interaction.response.send_modal(modal)

        for button in buttons:
            button.callback = button_callback
        export_button.callback = export_callback
        add_option_button.callback = add_option_callback

        poll_data["view"] = view

        def format_poll_results():
            result_message = ""
            for i, option in enumerate(poll_data["options"]):
                count = poll_data["vote_count"].get(option, 0)
                percentage = (count / poll_data["total_votes"] * 100) if poll_data["total_votes"] > 0 else 0
                bar_length = int(10 * percentage // 100)
                result_message += f"**{OPTION_EMOJIS[i]} {option}**\n"
                result_message += f"[{'🟩' * bar_length}{'⬜' * (10 - bar_length)}] | {percentage:.1f}% ({count})\n"
            return result_message

        poll_data["format_results"] = format_poll_results

        def build_embed(poll):
            header = ""
            if poll.get("end_time"):
                now = datetime.utcnow().replace(tzinfo=pytz.utc)
                if not poll.get("closed") and poll["end_time"] > now:
                    delta = poll["end_time"] - now
                    header = f"⏳ Time remaining: {format_time_delta(delta)}\n\n"
                else:
                    header = "❌ Poll closed\n\n"
            footer_text = f"Made by {poll['author']}" if not poll.get("anonymous", False) else "Anonymous poll"
            embed = discord.Embed(
                title="📊 " + poll["question"],
                description=header + poll["format_results"](),
                color=0xfe407d
            )
            embed.set_footer(text=footer_text)
            return embed

        poll_data["build_embed"] = build_embed

        embed = build_embed(poll_data)
        await interaction.response.send_message(embed=embed, view=view)
        poll_message = await interaction.original_response()
        poll_data["message_id"] = poll_message.id
        self.polls[poll_message.id] = poll_data

        if poll_data.get("end_time"):
            self.bot.loop.create_task(self.schedule_poll_end(poll_message.id))

async def setup(bot):
    await bot.add_cog(PollCog(bot))
    print("Loaded PollCog!")
