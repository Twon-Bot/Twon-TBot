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
    def __init__(self, poll_data, poll_message, choice, timeout: float = 30):
        super().__init__(timeout=timeout)
        self.poll_data = poll_data
        self.poll_message = poll_message
        self.choice = choice

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, button, interaction: discord.Interaction):
        # 1) immediately reply (acks the interaction)
        await interaction.response.send_message("✅ Vote changed.", ephemeral=True)

        # 2) now update the original poll message
        uid = interaction.user.id
        prev = self.poll_data['user_votes'].pop(uid, None)
        if prev:
            self.poll_data['vote_count'][prev] -= 1

        self.poll_data['user_votes'][uid] = self.choice
        self.poll_data['vote_count'][self.choice] += 1
        self.poll_data['total_votes'] = len(self.poll_data['user_votes'])

        embed = self.poll_data['build_embed'](self.poll_data)
        await self.poll_message.edit(embed=embed, view=self.poll_data['view'])

        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, button, interaction: discord.Interaction):
        # 1) immediately reply (acks)
        await interaction.response.send_message("👍 Keeping your vote.", ephemeral=True)
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

            # ── Append and rebuild ──────────────────
            self.poll_data['options'].append(option_text)
            self.poll_data['vote_count'][option_text] = 0

            view = self.poll_data['view']
            view.clear_items()
            # Re‑add each option button
            for i, opt in enumerate(self.poll_data['options']):
                btn = discord.ui.Button(label=OPTION_EMOJIS[i], custom_id=opt)
                btn.callback = self.poll_data['button_callback']
                view.add_item(btn)

            # Add‑option button
            plus = discord.ui.Button(label="➕", style=discord.ButtonStyle.secondary, custom_id="add_option")
            plus.callback = self.poll_data['cog'].add_option_callback
            view.add_item(plus)

            # Settings button (use the cog’s callback stored on poll_data)
            settings = discord.ui.Button(
                label="⚙️",
                style=discord.ButtonStyle.secondary,
                custom_id="settings"
            )
            settings.callback = self.poll_data['cog'].settings_callback
            view.add_item(settings)

            # Update the poll message
            embed = self.poll_data['build_embed'](self.poll_data)
            await self.poll_message.edit(embed=embed, view=view)

            # ACK the modal submission
            await interaction.response.send_message(f"Added option: {option_text}", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"Something went wrong adding the option: {e}", ephemeral=True
            )

class SettingsView(discord.ui.View):
    def __init__(self, cog, poll_data, message_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.poll_data = poll_data
        self.message_id = message_id

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary)
    async def edit(self, button, interaction):

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
            settings = discord.ui.Button(..., custom_id="settings")
            settings.callback = self.poll_data['cog'].settings_callback
            view.add_item(settings)

            channel = await self.cog.bot.fetch_channel(inter.channel_id)
            msg = await channel.fetch_message(self.message_id)
            await msg.edit(embed=self.poll_data['build_embed'](self.poll_data), view=view)
            await inter.response.send_message("Poll updated.", ephemeral=True)

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Voter List", style=discord.ButtonStyle.secondary)
    async def voter_list(self, button, interaction):

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

    async def _create_poll(self, ctx, *, args: str):
        """
        Create a poll. Format:
        !!poll [mention @everyone] [multiple] Question? | Opt1 | Opt2 | ... | MM/DD HH:MM
        """
        # ——— handle a real role‐mention or @everyone at the front ———
        mention = False
        mention_text = ''
        # if it begins with a role‐mention like <@&123…> or @everyone
        m = re.match(r'^(<@&\d+>|@everyone)\s+', args)
        if m:
            mention = True
            mention_text = m.group(1)
            args = args[m.end():]
        # Strip any leftover literal word "mention"
        if args.startswith("mention "):
            args = args[len("mention ") :]
        # now your existing “multiple” flag logic will apply to the remainder:

        multiple = False
        if args.startswith("multiple "):
            multiple = True
            args = args[len("multiple "):]

        parts = [p.strip() for p in args.split('|')]
        if len(parts) < 3:
            return await ctx.send("Provide question, 2+ options, optionally end time.")

        # Detect end time
        end_time = None
        if re.match(r"^\d{2}/\d{2} \d{2}:\d{2}$", parts[-1]):
            try:
                user_tz_str = await self.get_user_timezone(ctx.author.id)
                tz = pytz.timezone(user_tz_str)
                dt = datetime.strptime(parts[-1], "%m/%d %H:%M").replace(year=datetime.now(tz).year)
                end_time = tz.localize(dt).astimezone(pytz.utc)
                parts = parts[:-1]
            except Exception as e:
                return await ctx.send(f"Error parsing end time: {e}")

        question = parts[0]
        options = parts[1:]
        if not 2 <= len(options) <= 10:
            return await ctx.send("Poll must have between 2 and 10 options.")

        # Initialize poll data
        poll_data = {
            'question': question,
            'options': options.copy(),
            'vote_count': {opt:0 for opt in options},
            'total_votes': 0,
            'user_votes': {},
            'voting_type': 'multiple' if multiple else 'single',
            'author': ctx.author.display_name,
            'author_id': ctx.author.id,
            'mention': mention,
            'mention_text': mention_text,
            'end_time': end_time,
            'closed': False
        }
        # Give the modal access back to this cog instance
        poll_data['cog'] = self

        # Build embed
        def format_results():
            txt = ''
            for i,opt in enumerate(poll_data['options']):
                cnt = poll_data['vote_count'].get(opt,0)
                pct = (cnt/poll_data['total_votes']*100) if poll_data['total_votes']>0 else 0
                filled = int(BAR_LENGTH * pct//100)
                txt += f"{OPTION_EMOJIS[i]} {opt}\n[{'🟩'*filled}{'⬜'*(BAR_LENGTH-filled)}] | {pct:.1f}% ({cnt})\n"
            return txt

        def build_embed(data):
            header = ''
            if data['end_time']:
                now = datetime.utcnow().replace(tzinfo=pytz.utc)
                if not data['closed'] and data['end_time']>now:
                    header = f"⏳ Time remaining: {format_time_delta(data['end_time']-now)}\n\n"
                else:
                    header = "❌ Poll closed\n\n"
            desc = header + format_results()
            
            embed = discord.Embed(
                title=f"📊 {data['question']}",
                description=desc,
                color=0x39FF14
            )

            embed.set_footer(text=f"➕ Add Option | ⚙️ Settings | Created by {data['author']}")
            return embed

        # Callbacks
        async def vote_callback(interaction: discord.Interaction):
            poll = self.polls[interaction.message.id]
            uid = interaction.user.id
            choice = interaction.data['custom_id']

            # Single‑vote confirmation
            if poll['voting_type'] == 'single' and uid in poll['user_votes']:
                # launch ConfirmView which will handle removal+re-render
                view = ConfirmView(poll, interaction.message, choice)
                return await interaction.response.send_message(
                    "You already voted. Remove your vote?", view=view, ephemeral=True
                )
            # Register new vote
            poll['user_votes'][uid] = choice
            poll['vote_count'][choice] = poll['vote_count'].get(choice, 0) + 1
            poll['total_votes'] = len(poll['user_votes'])

            embed = poll['build_embed'](poll)
            await interaction.response.edit_message(embed=embed, view=poll['view'])

        # Assemble view
        view = discord.ui.View(timeout=None)
        # Option buttons
        for i,opt in enumerate(options):
            btn = discord.ui.Button(label=OPTION_EMOJIS[i], custom_id=opt)
            btn.callback = vote_callback
            view.add_item(btn)
        # Add option
        plus = discord.ui.Button(label="➕", style=discord.ButtonStyle.secondary, custom_id="add_option")
        plus.callback = self.add_option_callback
        view.add_item(plus)
        # Settings
        settings = discord.ui.Button(
            label="⚙️",
            style=discord.ButtonStyle.secondary,
            custom_id="settings"
        )
        # wire directly to the Cog’s settings_callback
        settings.callback = self.settings_callback
        view.add_item(settings)

        embed = build_embed(poll_data)
        # send a single message containing both custom mention_text and the embed
        content = poll_data['mention_text'] if poll_data['mention_text'] else None
        
        # Trying to add 'mention' with ping into poll from old code
        allowed = discord.AllowedMentions(roles=True, everyone=True)
        msg = await ctx.send(
            content=poll_data['mention_text'], 
            embed=embed, 
            view=view, 
            allowed_mentions=allowed)

        poll_data['view'] = view
        poll_data['build_embed'] = build_embed
        poll_data['button_callback'] = vote_callback
        self.polls[msg.id] = poll_data

        if end_time:
            self.bot.loop.create_task(self.schedule_poll_end(msg.id))

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
        full_args = f"{mentions or ''} { 'multiple ' if multiple else ''}{args}"
        try:
            await self._create_poll(ctx, args=full_args.strip())
        except Exception as e:
            # send the exception so you can debug
            await interaction.followup.send(f"🚨 Poll creation error: {e}", ephemeral=True)
            # re-raise if you want it in your logs
            raise
        # (no additional defer/response needed— your poll command has already sent!)

async def setup(bot):
    await bot.add_cog(PollCog(bot))
    print("Loaded PollCog!")
