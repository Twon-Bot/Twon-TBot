import discord
from discord.ext import commands
from discord import app_commands
import csv
import io
import asyncio
from datetime import datetime, timedelta
import pytz
import re  # for regex matching

# Use numeric keycap emojis for consistent display across platforms
OPTION_EMOJIS = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
# Shorten bar length to avoid wrapping on mobile
BAR_LENGTH = 8


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
        try:
            if option_text in self.poll_data['options']:
                return await interaction.response.send_message("That option already exists.", ephemeral=True)
            if len(self.poll_data['options']) >= 10:
                return await interaction.response.send_message("Maximum number of options reached.", ephemeral=True)
            # ... (rest of your append/rebuild code) ...
        except Exception as e:
            return await interaction.response.send_message(
                f"Something went wrong adding the option: {e}",
                ephemeral=True
            )
        
        # Append new option and initialize counts
        self.poll_data["options"].append(option_text)
        self.poll_data["vote_count"][option_text] = 0

        # Create corresponding button
        idx = len(self.poll_data["options"]) - 1
        new_button = discord.ui.Button(label=OPTION_EMOJIS[idx], custom_id=option_text)
        new_button.callback = self.poll_data["button_callback"]
        # Rebuild the view so all buttons (including the new one) render immediately
        view = self.poll_data['view']
        view.clear_items()
        # Re-add option buttons
        for i, opt in enumerate(self.poll_data['options']):
            btn = discord.ui.Button(label=OPTION_EMOJIS[i], custom_id=opt)
            btn.callback = self.poll_data['button_callback']
            view.add_item(btn)
        # ➕ Add-option button
        plus = discord.ui.Button(label="➕", style=discord.ButtonStyle.secondary, custom_id="add_option")
        plus.callback = self.poll_data['cog'].add_option_callback
        view.add_item(plus)
        # ⚙️ Settings button
        settings = discord.ui.Button(label="⚙️", style=discord.ButtonStyle.secondary, custom_id="settings")
        settings.callback = self.settings_callback  # PollCog.settings_callback
        view.add_item(settings)

        # Edit the poll message to show new option and buttons
        embed = self.poll_data['build_embed'](self.poll_data)
        await self.poll_message.edit(embed=embed, view=view)

class SettingsView(discord.ui.View):
    def __init__(self, cog, poll_data, message_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.poll_data = poll_data
        self.message_id = message_id

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary)
    async def edit(self, button, interaction):
        # ← add this
        await interaction.response.defer(ephemeral=True)

        # Collect inputs: question, mentions, each option
        modal = discord.ui.Modal(title="Edit Poll")
        question_input = discord.ui.TextInput(label="Question", default=self.poll_data['question'], max_length=200)
        mention_input = discord.ui.TextInput(label="Mentions (e.g. @everyone)", default=self.poll_data.get('mention_text',''), required=False)
        modal.add_item(question_input)
        modal.add_item(mention_input)
        for i,opt in enumerate(self.poll_data['options']):
            modal.add_item(discord.ui.TextInput(label=f"Option {i+1}", default=opt, max_length=100))

        async def on_submit(inner, inter: discord.Interaction):
            vals = inner.children
            self.poll_data['question'] = vals[0].value
            mention_text = vals[1].value.strip()
            self.poll_data['mention'] = bool(mention_text)
            self.poll_data['mention_text'] = mention_text
            # Update options but preserve counts
            old_counts = [self.poll_data['vote_count'].get(o,0) for o in self.poll_data['options']]
            new_opts = [c.value for c in vals[2:]]
            self.poll_data['options'] = new_opts
            self.poll_data['vote_count'] = {opt: (old_counts[i] if i < len(old_counts) else 0) for i,opt in enumerate(new_opts)}

            # Rebuild buttons in view
            view = self.poll_data['view']
            view.clear_items()
            # Option buttons
            for i,opt in enumerate(new_opts):
                btn = discord.ui.Button(label=OPTION_EMOJIS[i], custom_id=opt)
                btn.callback = self.poll_data['button_callback']
                view.add_item(btn)
            # Add plus
            plus = discord.ui.Button(label="➕", style=discord.ButtonStyle.secondary, custom_id="add_option")
            plus.callback = self.cog.add_option_callback
            view.add_item(plus)
            # Settings button
            settings = discord.ui.Button(label="⚙️", style=discord.ButtonStyle.secondary, custom_id="settings")
            settings.callback = self.settings_callback  # PollCog.settings_callback
            view.add_item(settings)

            channel = await self.cog.bot.fetch_channel(inter.channel_id)
            msg = await channel.fetch_message(self.message_id)
            await msg.edit(embed=self.poll_data['build_embed'](self.poll_data), view=view)
            await inter.response.send_message("Poll updated.", ephemeral=True)

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Voter List", style=discord.ButtonStyle.secondary)
    async def voter_list(self, button, interaction):
        # ← add this
        await interaction.response.defer(ephemeral=True)

        options = [discord.SelectOption(label=opt, value=opt, emoji=OPTION_EMOJIS[i])
                   for i,opt in enumerate(self.poll_data['options'])]
        select = discord.ui.Select(placeholder="Choose option", options=options, custom_id="voter_select")

        async def select_cb(select_inter: discord.Interaction):
            sel = select_inter.data['values'][0]
            voters = [f"<@{uid}>" for uid,v in self.poll_data['user_votes'].items()
                      if (sel in v if isinstance(v,list) else v==sel)]
            text = "No votes yet." if not voters else '\n'.join(voters)
            await select_inter.response.send_message(f"Voters for {sel}:\n{text}", ephemeral=True)

        select.callback = select_cb
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message("Select option to view voters:", view=view, ephemeral=True)

    @discord.ui.button(label="End Poll", style=discord.ButtonStyle.secondary)
    async def end_poll(self, button, interaction):
        # ← add this
        await interaction.response.defer(ephemeral=True)

        self.poll_data['closed'] = True
        # Disable all option buttons
        for item in self.poll_data['view'].children:
            if item.custom_id not in ('settings','add_option'):
                item.disabled = True
        channel = await self.cog.bot.fetch_channel(interaction.channel_id)
        msg = await channel.fetch_message(self.message_id)
        await msg.edit(embed=self.poll_data['build_embed'](self.poll_data), view=self.poll_data['view'])
        await interaction.response.send_message("Poll ended.", ephemeral=True)

    @discord.ui.button(label="Export Votes", style=discord.ButtonStyle.primary)
    async def export_votes(self, button, interaction):
        # ← add this
        await interaction.response.defer(ephemeral=True)

        poll = self.poll_data

        # Build CSV in memory
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["User", "Vote"])

        # 1) All votes
        for uid, vote in poll['user_votes'].items():
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else str(uid)
            if isinstance(vote, list):
                vote = ", ".join(vote)
            writer.writerow([name, vote])

        # 2) Non-voters in specific role
        role = interaction.guild.get_role(1334747903427870742)
        if role:
            writer.writerow([])
            writer.writerow(["=== Did Not Vote ==="])
            for member in role.members:
                if member.id not in poll['user_votes']:
                    writer.writerow([member.display_name, ""])

        buf.seek(0)
        discord_file = discord.File(fp=io.BytesIO(buf.getvalue().encode()), filename="poll_export.csv")

        # Send ephemerally to the clicking user
        await interaction.response.send_message(
            "Here’s the full export:", file=discord_file, ephemeral=True
        )

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete(self, button, interaction):
        # ← add this
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id != self.poll_data['author_id']:
            return await interaction.response.send_message("Only creator can delete.", ephemeral=True)
        channel = await self.cog.bot.fetch_channel(interaction.channel_id)
        msg = await channel.fetch_message(self.message_id)
        await msg.delete()
        self.cog.polls.pop(self.message_id, None)
        await interaction.response.send_message("Poll deleted.", ephemeral=True)


class PollCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.polls = {}

    async def get_user_timezone(self, user_id):
        """Fetch a user's timezone from Postgres (default UTC)."""
        row = await self.bot.pg_pool.fetchrow(
            "SELECT timezone FROM timezones WHERE user_id = $1",
            user_id
        )
        return row["timezone"] if row and row["timezone"] else "UTC"

    # Shared callbacks for add_option and settings
    async def add_option_callback(self, interaction: discord.Interaction):
        pid = interaction.message.id
        poll = self.polls.get(pid)
        if not poll or interaction.user.id != poll['author_id']:
            return await interaction.response.send_message("No permission.", ephemeral=True)
        await interaction.response.send_modal(AddOptionModal(poll, interaction.message))

    async def settings_callback(self, interaction: discord.Interaction):
        poll = self.polls.get(interaction.message.id)
        roles = [r.name for r in interaction.user.roles]
        if not any(r in roles for r in ('Server Owner','Manager','Moderator','The BotFather')):
            return await interaction.response.send_message("No permission.", ephemeral=True)
        # Instead of DMing, send the settings view ephemerally in the same channel:
        await interaction.response.send_message(
            "Poll Settings:",
            view=SettingsView(self, poll, interaction.message.id),
            ephemeral=True
        )
        
    async def schedule_poll_end(self, message_id):
        poll = self.polls.get(message_id)
        if not poll or not poll.get('end_time'):
            return
        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        wait = (poll['end_time'] - now).total_seconds()
        if wait>0:
            await asyncio.sleep(wait)
        poll['closed'] = True
        # disable all but settings/add_option
        for item in poll['view'].children:
            if item.custom_id not in ('settings','add_option'):
                item.disabled = True
        channel = self.bot.get_channel(poll['view']._timeout)  # avoid missing channel id
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(embed=poll['build_embed'](poll), view=poll['view'])
        except:
            pass
        await asyncio.sleep(86400)
        self.polls.pop(message_id, None)

    @app_commands.command(name="poll", description="Create a poll via slash")
    @app_commands.describe(
        question="The poll question",
        mentions="Text to mention (e.g. @everyone)",
        multiple="Allow multiple votes",
        end_time="End time MM/DD HH:MM (optional)"
    )
    async def poll_slash(self, interaction: discord.Interaction,
                          question: str,
                          mentions: str = None,
                          multiple: bool = False,
                          end_time: str = None,
                          option1: str = None,
                          option2: str = None,
                          option3: str = None,
                          option4: str = None,
                          option5: str = None,
                          option6: str = None,
                          option7: str = None,
                          option8: str = None,
                          option9: str = None,
                          option10: str = None):
        # 1) Acknowledge immediately
        await interaction.response.defer()

        # 2) Gather options
        opts = [o for o in (
            option1, option2, option3, option4, option5,
            option6, option7, option8, option9, option10
        ) if o]
        if len(opts) < 2:
            return await interaction.followup.send("Provide at least 2 options.", ephemeral=True)

        # 3) Reconstruct the text‐command style args string
        parts = []
        if mentions:
            parts.append("mention")
        if multiple:
            parts.append("multiple")
        # join question + all options, plus end_time if given
        question_and_opts = question + " | " + " | ".join(opts)
        if end_time:
            question_and_opts += f" | {end_time}"
        parts.append(question_and_opts)
        args = " ".join(parts)

        # 4) Instead of delegating, let's craft mention_text and call the core logic
        ctx = await commands.Context.from_interaction(interaction)
        # pass the exact mention string through
        full_args = f"{mentions or ''} { 'multiple ' if multiple else ''}{args}"
        await self.poll.callback(self, ctx, args=full_args.strip())        # (no additional defer/response needed— your poll command has already sent!)

async def setup(bot):
    await bot.add_cog(PollCog(bot))
    print("Loaded PollCog!")
