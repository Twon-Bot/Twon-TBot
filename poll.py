import discord
from discord.ext import commands
from discord import app_commands, TextStyle
import csv
import io
import asyncio
from datetime import datetime, timedelta
import pytz
import re  # for regex matching
import os
from dotenv import load_dotenv
import json

# ─── Role IDs for reminders ─────────────────────────────
load_dotenv()
PLAYER_ROLE_ID       = int(os.getenv("PLAYER_ROLE_ID"      ,  "1334747903427870742"))
VOTE_PENDING_ROLE_ID = int(os.getenv("VOTE_PENDING_ROLE_ID","1366303580591755295"))

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

import logging
import pytz
from datetime import datetime

# configure module logger
log = logging.getLogger(__name__)

class EditPollModal(discord.ui.Modal, title="Edit Poll"):
    question = discord.ui.TextInput(label="Question", max_length=200)
    mentions = discord.ui.TextInput(label="Mentions (e.g. @everyone)", required=False)
    end_time = discord.ui.TextInput(label="End Time MM/DD HH:MM", required=False)
    options = discord.ui.TextInput(
        label="Options (one per line)",
        style=TextStyle.paragraph,
        max_length=1000
    )

    def __init__(self, cog, poll_data, message_id):
        super().__init__()
        self.cog = cog
        self.poll_data = poll_data
        self.message_id = message_id
        # pre‑fill defaults for question and mentions
        self.question.default = poll_data.get('question', '')
        self.mentions.default = poll_data.get('mention_text', '')

        # pre‑fill end_time: use stored string, else format existing datetime
        if 'end_time_str' in poll_data:
            default_end = poll_data['end_time_str'] or ''
        elif 'end_time' in poll_data:
            # format UTC datetime to MM/DD HH:MM
            default_end = poll_data['end_time'].strftime("%m/%d %H:%M")
        else:
            default_end = ''
        self.end_time.default = default_end
        self._original_end_str = default_end

        # pre‑fill options
        self.options.default = "\n".join(poll_data.get('options', []))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # collect new values
            new_opts = [line.strip() for line in self.options.value.splitlines() if line.strip()]
            if len(new_opts) < 2:
                await interaction.response.send_message(
                    "❌ You must have at least two options to create a poll.",
                    ephemeral=True
                )
                return

            # determine end_time handling
            end_input = self.end_time.value.strip()
            if end_input and end_input != self._original_end_str:
                tz = pytz.timezone(await self.cog.get_user_timezone(interaction.user.id))
                dt_input = datetime.strptime(end_input, "%m/%d %H:%M").replace(
                    year=datetime.now(tz).year
                )
                localized = tz.localize(dt_input)
                if localized <= datetime.now(tz):
                    await interaction.response.send_message(
                        "❌ End time must be in the future.",
                        ephemeral=True
                    )
                    return
                new_end_utc = localized.astimezone(pytz.utc)
                new_end_str = end_input
            elif end_input == '':
                # user cleared end time
                new_end_utc = None
                new_end_str = None
            else:
                # unchanged original
                new_end_utc = self.poll_data.get('end_time')
                new_end_str = self._original_end_str

            # prepare updated vote counts
            old_opts = self.poll_data.get('options', [])
            old_counts = self.poll_data.get('vote_count', {})
            new_counts = {}
            for idx, opt in enumerate(new_opts):
                if opt in old_counts:
                    new_counts[opt] = old_counts[opt]
                elif idx < len(old_opts) and old_opts[idx] in old_counts:
                    new_counts[opt] = old_counts[old_opts[idx]]
                else:
                    new_counts[opt] = 0

            # apply updates
            self.poll_data.update({
                'question': self.question.value,
                'mention_text': self.mentions.value.strip(),
                'mention': bool(self.mentions.value.strip()),
                'options': new_opts,
                'vote_count': new_counts
            })
            if new_end_utc is not None:
                self.poll_data['end_time'] = new_end_utc
                self.poll_data['end_time_str'] = new_end_str
            else:
                self.poll_data.pop('end_time', None)
                self.poll_data.pop('end_time_str', None)

        except Exception as e:
            log.exception(f"EditPollModal error: {e}")
            await interaction.response.send_message(
                "❌ Something went wrong while updating the poll. No changes applied.",
                ephemeral=True
            )
            return

        # rebuild embed & view
        embed = self.poll_data['build_embed'](self.poll_data)
        new_view = discord.ui.View()
        for i, opt in enumerate(self.poll_data['options']):
            btn = discord.ui.Button(label=OPTION_EMOJIS[i], custom_id=opt)
            btn.callback = self.poll_data['button_callback']
            new_view.add_item(btn)
        plus = discord.ui.Button(label="➕", style=discord.ButtonStyle.secondary, custom_id="add_option")
        plus.callback = self.cog.add_option_callback
        settings_btn = discord.ui.Button(label="⚙️", style=discord.ButtonStyle.secondary, custom_id="settings")
        settings_btn.callback = self.cog.settings_callback
        new_view.add_item(plus)
        new_view.add_item(settings_btn)

        # apply message edit with mentions allowed
        channel = self.cog.bot.get_channel(self.poll_data['channel_id'])
        msg = await channel.fetch_message(self.message_id)
        await msg.edit(
            content=self.poll_data.get('mention_text') or None,
            embed=embed,
            view=new_view,
            allowed_mentions=discord.AllowedMentions(everyone=True, roles=True, users=True)
        )

        await interaction.response.send_message("✅ Poll updated.", ephemeral=True)
        self.poll_data['view'] = new_view


class SettingsView(discord.ui.View):
    def __init__(self, cog, poll_data, message_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.poll_data = poll_data
        self.message_id = message_id

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        # launch the corrected modal
        await interaction.response.send_modal(EditPollModal(self.cog, self.poll_data, self.message_id))
        
    @discord.ui.button(label="Voters", style=discord.ButtonStyle.primary)
    async def voter_list(self, interaction: discord.Interaction, button: discord.ui.Button):

        # build option list + final “Not Voted”
        options = [
            discord.SelectOption(label=opt, value=opt, emoji=OPTION_EMOJIS[i])
            for i,opt in enumerate(self.poll_data['options'])
        ]
        options.append(discord.SelectOption(label="Not Voted", value="__NOT_VOTED__"))
        
        view = discord.ui.View(timeout=None)
        select = discord.ui.Select(
            placeholder="Select an option",
            options=[discord.SelectOption(label=o, value=o) for o in self.poll_data['options']] + 
                    [discord.SelectOption(label="All (not voted)", value="__all__")]
        )
        async def select_cb(select_inter: discord.Interaction):
            sel = select.values[0]
            if sel == "__all__":
                # find everyone who hasn’t voted
                role = select_inter.guild.get_role(PLAYER_ROLE_ID)
                not_voted = [m.mention for m in role.members if m.id not in self.poll_data['user_votes']]
                text = "\n".join(not_voted) if not_voted else "Everyone has voted!"
                await select_inter.response.edit_message(content=f"Users not voted:\n{text}", view=None, ephemeral=True)
            else:
                voters = [
                    f"<@{uid}>" 
                    for uid, v in self.poll_data['user_votes'].items() 
                    if (isinstance(v, list) and sel in v) or v == sel
                ]
                text = "\n".join(voters) if voters else "No votes yet."
                await select_inter.response.edit_message(content=f"Voters for {sel}:\n{text}", view=None, ephemeral=True)
        select.callback = select_cb    # ← bind here
        view.add_item(select)
        # replace the settings prompt with the voter‑select menu
        await interaction.response.edit_message(
            content="Select option to view voters:", view=view, ephemeral=True
        )

    @discord.ui.button(label="End Poll", style=discord.ButtonStyle.primary)
    async def end_poll(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        # now complete the interaction
        await interaction.followup.send(
            content="Preparing to End Poll…", view=None, ephemeral=True)

        # if already closed, just report when it ended
        if self.poll_data.get('closed'):
            et = self.poll_data.get('end_time')
            when = et.strftime("%m/%d %H:%M UTC") if et else "unknown time"
            return await interaction.followup.send(
                f"❌ Poll already ended on {when}.", ephemeral=True
            )
        # Show confirmation prompt
        confirm_view = discord.ui.View(timeout=30)

        # ── Confirm button ────────────────────────────
        confirm_btn = discord.ui.Button(label="Confirm End Poll", style=discord.ButtonStyle.danger)
        async def confirm_cb(confirm_inter: discord.Interaction):
            # 1) mark closed
            self.poll_data['closed'] = True
            # 2) disable all non-settings/add_option buttons
            for item in list(self.poll_data['view'].children):
                # now disable everything except the settings button
                if getattr(item, 'custom_id', None) != 'settings':
                    item.disabled = True
            # 3) edit the original poll message
            channel = self.cog.bot.get_channel(self.poll_data['channel_id'])
            poll_msg = await channel.fetch_message(self.message_id)
            await poll_msg.edit(embed=self.poll_data['build_embed'](self.poll_data), view=self.poll_data['view'])
            # 4) send confirmation separately
            await confirm_inter.response.send_message("✅ Poll ended.", ephemeral=True)
            # ── remove from Postgres so it no longer reloads ────────────
            await self.cog.bot.pg_pool.execute("DELETE FROM polls WHERE id = $1", self.poll_data["id"])
            confirm_view.stop()
        confirm_btn.callback = confirm_cb
        confirm_view.add_item(confirm_btn)

        # ── Cancel button ─────────────────────────────
        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        async def cancel_cb(cancel_inter: discord.Interaction):
            # replace prompt with a new ephemeral cancellation notice
            await cancel_inter.response.send_message("❌ Action cancelled.", ephemeral=True)
            confirm_view.stop()
        cancel_btn.callback = cancel_cb
        confirm_view.add_item(cancel_btn)

        # show the confirm/cancel buttons via follow‑up after defer
        await interaction.followup.send(
            content="Are you sure you want to end the poll?",
            view=confirm_view,
            ephemeral=True
        )

    @discord.ui.button(label="Export Votes", style=discord.ButtonStyle.primary)
    async def export_votes(self, interaction: discord.Interaction, button: discord.ui.Button):
        # no defer — respond immediately with file

        # Build CSV in memory
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["User", "Vote"])

        # 1) All votes
        for uid, vote in self.poll_data['user_votes'].items():
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else str(uid)
            if isinstance(vote, list):
                vote = ", ".join(vote)
            writer.writerow([name, vote])

        # 2) Non‑voters
        role = interaction.guild.get_role(PLAYER_ROLE_ID)
        if role:
            writer.writerow([])
            writer.writerow(["=== Did Not Vote ==="])
            for m in role.members:
                if m.id not in self.poll_data['user_votes']:
                    writer.writerow([m.display_name, ""])

        buf.seek(0)
        discord_file = discord.File(fp=io.BytesIO(buf.getvalue().encode()), filename="poll_export.csv")

        # edit the same ephemeral to include the file
        await interaction.response.send_message(file=discord_file, ephemeral=True)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button):
        # no defer - open confirm view immediately

        if interaction.user.id != self.poll_data['author_id']:
            return await interaction.followup.send("Only creator can delete.", ephemeral=True)

        confirm_view = discord.ui.View(timeout=30)
        btn_yes = discord.ui.Button(label="Confirm Delete", style=discord.ButtonStyle.danger)
        async def yes_cb(i):
            channel = self.cog.bot.get_channel(self.poll_data['channel_id'])
            msg = await channel.fetch_message(self.message_id)
            await msg.delete()
            self.cog.polls.pop(self.message_id, None)
            await self.cog.bot.pg_pool.execute("DELETE FROM polls WHERE id = $1", self.poll_data["id"])
            # send a fresh ephemeral reply so the original confirm prompt no longer errors
            await i.response.send_message("✅ Poll deleted.", ephemeral=True)
        btn_yes.callback = yes_cb
        confirm_view.add_item(btn_yes)

        btn_no = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        async def no_cb(i):
            # replace prompt with fresh cancellation notice
            await i.response.send_message("❌ Delete action cancelled.", ephemeral=True)
        btn_no.callback = no_cb
        confirm_view.add_item(btn_no)

        # show delete‑confirmation prompt
        await interaction.response.send_message(
            content="Are you sure you want to **delete** the poll?",
            view=confirm_view,
            ephemeral=True
        )

    @discord.ui.button(label="Color", style=discord.ButtonStyle.success)
    async def color(self, interaction: discord.Interaction, button: discord.ui.Button):
        # pass the live poll_data dict into the modal so it can update embed_color
        await interaction.response.send_modal(ColorModal(self.poll_data))


class PollCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.polls = {}

    @commands.Cog.listener()
    async def on_ready(self):
        """Ensure table exists, load saved polls, and schedule their tasks."""
        # 1) create the table if missing
        await self.bot.pg_pool.execute(
            """
            CREATE TABLE IF NOT EXISTS polls (
              id TEXT PRIMARY KEY,
              data JSONB NOT NULL,
              embed_color INTEGER NOT NULL DEFAULT 52479,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )
        # 2) load polls
        rows = await self.bot.pg_pool.fetch("SELECT id, data, embed_color FROM polls")
        for row in rows:
            poll = json.loads(row["data"])
            # rehydrate end_time
            if poll.get("end_time"):
                dt = datetime.fromisoformat(poll["end_time"])
                poll["end_time"] = dt if dt.tzinfo else dt.replace(tzinfo=pytz.utc)
            poll["embed_color"] = row["embed_color"]
            self.polls[poll["id"]] = poll

            # ── Rebuild main voting View ─────────────────────────────────────────────
            from discord.ui import View, Button
            main_view = View(timeout=None)
            # Option buttons
            for i, opt in enumerate(poll["options"]):
                btn = Button(label=OPTION_EMOJIS[i], custom_id=opt)
                btn.callback = self.polls[poll["id"]]['button_callback']
                main_view.add_item(btn)
            # Add‑option
            plus = Button(label="➕", style=discord.ButtonStyle.secondary, custom_id="add_option")
            plus.callback = self.add_option_callback
            main_view.add_item(plus)
            # Settings
            settings_btn = Button(label="⚙️", style=discord.ButtonStyle.secondary, custom_id="settings")
            settings_btn.callback = self.settings_callback
            main_view.add_item(settings_btn)

            # Tell discord.py to listen for interactions on that view, for that message
            self.bot.add_view(main_view, message_id=int(poll["id"]))
            poll["view"] = main_view

            # ── Rebuild SettingsView ────────────────────────────────────────────────────
            settings_view = SettingsView(self, poll, message_id=int(poll["id"]))
            self.bot.add_view(settings_view, message_id=int(poll["id"]))
            poll["settings_view"] = settings_view

            # 3) schedule close & one‑hour reminder
            self.bot.loop.create_task(self.schedule_poll_end(poll['id']))
            if poll.get("one_hour_reminder"):
                self.bot.loop.create_task(self.schedule_poll_reminder(poll['id']))

    async def _create_poll(
        self,
        ctx,
        *,
        question: str,
        options: list[str],
        mention: bool = False,
        mention_text: str = "",
        multiple: bool = False,
        one_hour_reminder: bool = False,
        end_time: datetime | None = None,
    ):        
        """
        Create a poll. Format:
        !!poll [mention @everyone] [multiple] Question? | Opt1 | Opt2 | ... | MM/DD HH:MM
        """
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
            'one_hour_reminder': one_hour_reminder,
            'channel_id': ctx.channel.id,
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
                txt += f"{OPTION_EMOJIS[i]} {opt}\n{'🟩'*filled}{'⬜'*(BAR_LENGTH-filled)} | {pct:.1f}% ({cnt})\n"
            return txt

        def build_embed(data):
            header = ''
            if data['end_time']:
                # ensure end_time is timezone‑aware in UTC
                end = data['end_time']
                if end.tzinfo is None:
                    end = end.replace(tzinfo=pytz.utc)

                now = datetime.utcnow().replace(tzinfo=pytz.utc)
                if not data['closed'] and end > now:
                    header = f"⏳ Time remaining: {format_time_delta(end - now)}\n\n"
                else:
                    header = "❌ Poll closed\n\n"
            desc = header + format_results()
            # ─── tell them single vs multiple ────────────────────────────
            if data['voting_type'] == 'single':
                desc += "\n*You may select **only one option** in this poll.*\n"
            else:
                desc += "\n*You may select **multiple options** in this poll.*\n"
            # ── One‑hour‑reminder status line ────────────────────────────────────
            status = "**On**" if data.get('one_hour_reminder') else "Off"
            desc += f"*One Hour Reminder: {status}*\n"
            
            embed = discord.Embed(
                title=f"📊 {data['question']}",
                description=desc,
                color=data.get('embed_color', 0x00BFFF)  # default bright blue
            )

            embed.set_footer(text=f"➕ Add Option | ⚙️ Settings | Created by {data['author']}")
            return embed

        # Callbacks
        async def vote_callback(interaction: discord.Interaction):
            poll = self.polls[interaction.message.id]
            uid = interaction.user.id
            choice = interaction.data['custom_id']

            # ─── single-vote mode ───────────────────────────────────────
            prev = poll['user_votes'].get(interaction.user.id)
            # if clicking same option, remove vote immediately
            if prev == choice:
                # decrement count & remove vote
                poll['vote_count'][prev] -= 1
                del poll['user_votes'][uid]
                poll['total_votes'] = sum(poll['vote_count'].values())
                # update embed
                embed = poll['build_embed'](poll)
                await interaction.response.edit_message(embed=embed, view=poll['view'])
                # remove pending role
                rp = discord.utils.get(interaction.user.roles, id=VOTE_PENDING_ROLE_ID)
                if rp:
                    try: await interaction.user.remove_roles(rp, reason="Vote removed")
                    except: pass
                return

            # if they’d voted something else, change vote
            # else if different, ask to change
            if prev:
                # decrement old, set new
                poll['vote_count'][prev] -= 1
                poll['user_votes'][uid] = choice
                poll['vote_count'][choice] = poll['vote_count'].get(choice, 0) + 1
                poll['total_votes'] = sum(poll['vote_count'].values())
                embed = poll['build_embed'](poll)
                await interaction.response.edit_message(embed=embed, view=poll['view'])
                # remove pending role
                rp = discord.utils.get(interaction.user.roles, id=VOTE_PENDING_ROLE_ID)
                if rp:
                    try: await interaction.user.remove_roles(rp, reason="Vote changed")
                    except: pass
                return

            # ─── multiple-vote mode ─────────────────────────────────────
            user_list = poll['user_votes'].setdefault(uid, [])

            if choice in user_list:
                # toggle off
                user_list.remove(choice)
                poll['vote_count'][choice] -= 1
            else:
                # toggle on
                user_list.append(choice)
                poll['vote_count'][choice] = poll['vote_count'].get(choice, 0) + 1

            # recompute total votes as sum of all counts for correct percentages
            poll['total_votes'] = sum(poll['vote_count'].values())

            embed = poll['build_embed'](poll)
            await interaction.response.edit_message(embed=embed, view=poll['view'])

            # after updating poll['user_votes']…
            # remove pending role
            vote_pending = discord.utils.get(interaction.user.roles, id=1366303580591755295)
            if vote_pending:
                try:
                    await interaction.user.remove_roles(vote_pending, reason="Voted in poll")
                except:
                    pass

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
            content=poll_data['mention_text'] or None,            embed=embed, 
            view=view, 
            allowed_mentions=allowed)

        poll_data['view'] = view
        poll_data['build_embed'] = build_embed
        poll_data['button_callback'] = vote_callback
        # Store the ID as a string
        poll_data['id'] = str(msg.id)
        self.polls[msg.id] = poll_data
        # ── persist new poll to Postgres ───────────────────────────
        clean = { k: v for k, v in poll_data.items()
                if k not in ("view","cog","build_embed","button_callback","settings_view") }
        await self.bot.pg_pool.execute(
            """
            INSERT INTO polls(id, data, embed_color)
            VALUES($1, $2::jsonb, $3)
            ON CONFLICT (id) DO UPDATE
            SET data = EXCLUDED.data,
                embed_color = EXCLUDED.embed_color
            """,
            str(msg.id),
            json.dumps(poll_data, default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o)),
            poll_data.get("embed_color", 0x00BFFF)
        )

        if end_time:
            # schedule the one-hour warning
            if poll_data['one_hour_reminder']:
                self.bot.loop.create_task(self.schedule_poll_reminder(msg.id))
            # schedule the actual close
            self.bot.loop.create_task(self.schedule_poll_end(msg.id))
            # schedule periodic countdown updates (every 60 seconds)
            self.bot.loop.create_task(self.schedule_countdown_update(msg.id))

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
        settings_view = SettingsView(self, poll, interaction.message.id)
        self.polls[interaction.message.id]['settings_view'] = settings_view
        await interaction.response.send_message(
            "Poll Settings:",
            view=settings_view,
            ephemeral=True
        )
        
    async def schedule_poll_end(self, message_id):
        poll = self.polls.get(message_id)
        if not poll or not poll.get('end_time'):
            return
        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        wait = (poll['end_time'] - now).total_seconds()
        if wait > 0:
            await asyncio.sleep(wait)
        poll['closed'] = True

        channel = self.bot.get_channel(poll['channel_id'])
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(embed=poll['build_embed'](poll), view=poll['view'])
        except:
            pass

        await asyncio.sleep(86400)
        self.polls.pop(message_id, None)

    async def schedule_poll_reminder(self, message_id):
        poll = self.polls.get(message_id)
        if not poll or not poll.get('end_time'):
            return

        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        remind_at = poll['end_time'] - timedelta(hours=1)
        wait = (remind_at - now).total_seconds()
        if wait > 0:
            await asyncio.sleep(wait)

        # do nothing if poll already closed
        if poll.get('closed'):
            return

        # fetch channel & message
        channel = self.bot.get_channel(poll['channel_id'])
        if not channel:
            return
        msg = await channel.fetch_message(message_id)

        # fetch roles
        guild = channel.guild
        player_role = guild.get_role(PLAYER_ROLE_ID)
        vote_pending_role = guild.get_role(VOTE_PENDING_ROLE_ID)
        if not player_role or not vote_pending_role:
            # roles not found → bail
            return

        # assign @Vote_Pending to every @Player who hasn't voted
        # assign @Vote_Pending to every @Player who hasn't voted
        player_role       = guild.get_role(PLAYER_ROLE_ID)
        vote_pending_role = guild.get_role(VOTE_PENDING_ROLE_ID)

        if player_role and vote_pending_role:
            for member in player_role.members:
                if member.id not in poll['user_votes']:
                    try:
                        await member.add_roles(vote_pending_role, reason="Poll reminder: please vote")
                    except Exception:
                        # log if you like, but swallow errors so one failure
                        # doesn’t break the whole loop
                        pass

        # send a reminder ping
        await channel.send(
            f"{vote_pending_role.mention} Poll “{poll['question']}” ends in 1 hour—please cast your vote!",
            allowed_mentions=discord.AllowedMentions(roles=True)
        )

    async def schedule_countdown_update(self, message_id):
        # loop until closed or past end, re-fetching poll each iteration
        while True:
            poll = self.polls.get(message_id)
            if not poll or not poll.get('end_time'):
                return
            now = datetime.utcnow().replace(tzinfo=pytz.utc)
            # stop if closed or time’s up
            if poll.get('closed') or poll['end_time'] <= now:
                break
            try:
                channel = self.bot.get_channel(poll['channel_id'])
                msg = await channel.fetch_message(message_id)
                await msg.edit(embed=poll['build_embed'](poll), view=poll['view'])
            except Exception:
                pass
            # wait one minute before next update
            await asyncio.sleep(60)

    @app_commands.command(name="poll", description="Create a poll via slash")
    @app_commands.describe(
        question="The poll question",
        mentions="Text to mention (e.g. @everyone)",
        multiple="Allow multiple votes",
        end_time="End time MM/DD HH:MM (optional)",
        one_hour_reminder="Send 1-hour warning to non-voters",
    )
    async def poll_slash(
        self,
        interaction: discord.Interaction,
        question: str,
        mentions: str = None,
        multiple: bool = False,
        end_time: str = None,
        one_hour_reminder: bool = False,
        option1: str = None,                          
        option2: str = None,
        option3: str = None,
        option4: str = None,
        option5: str = None,
        option6: str = None,
        option7: str = None,
        option8: str = None,
        option9: str = None,
        option10: str = None
    ):

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
        # build exactly: [<@&role>] [multiple ] [reminder ] Question | Opt1 | Opt2 [| end_time]
        question_and_opts = question + " | " + " | ".join(opts)
        if end_time:
            question_and_opts += f" | {end_time}"

        flags = ""
        if multiple:
            flags += "multiple "
        if one_hour_reminder:
            flags += "one_hour_reminder "

        ctx = await commands.Context.from_interaction(interaction)
        try:
            # ── make end_time UTC‑aware using the user’s timezone ─────────────────────────
            if end_time:
                # look up the user’s tz (same helper you use in SettingsView)
                tz = pytz.timezone(await self.get_user_timezone(interaction.user.id))
                # parse into a naive dt in that zone, then localize → UTC
                local_dt = datetime.strptime(end_time, "%m/%d %H:%M").replace(year=datetime.now(tz).year)
                end_time_aware = tz.localize(local_dt).astimezone(pytz.utc)
            else:
                end_time_aware = None

            # ── ensure end time is in the future ───────────────────────
            if end_time_aware is not None:
                now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
                if end_time_aware <= now_utc:
                    return await interaction.followup.send(
                        "🚨 You must pick an end time in the future.", ephemeral=True
                    )

            await self._create_poll(
                ctx,
                question=question,
                options=opts,
                mention=bool(mentions),
                mention_text=mentions or "",
                multiple=multiple,
                one_hour_reminder=one_hour_reminder,
                end_time=end_time_aware
            )

        except Exception as e:
            await interaction.followup.send(f"🚨 Poll creation error: {e}", ephemeral=True)
            raise

class ConfirmChangeView(discord.ui.View):
    def __init__(self, poll, user_id, new_choice):
        super().__init__(timeout=60)
        self.poll = poll
        self.user_id = user_id
        self.new_choice = new_choice

    @discord.ui.button(label="Change Vote", style=discord.ButtonStyle.primary)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1) remove old vote
        prev = self.poll['user_votes'].get(self.user_id)
        if prev:
            self.poll['vote_count'][prev] -= 1

        # 2) set new vote
        self.poll['user_votes'][self.user_id] = self.new_choice
        self.poll['vote_count'][self.new_choice] = (
            self.poll['vote_count'].get(self.new_choice, 0) + 1
        )
        # 3) recompute totals if you display percentages
        self.poll['total_votes'] = sum(self.poll['vote_count'].values())

        # 4) update the original message
        channel = interaction.guild.get_channel(self.poll['channel_id'])
        msg = await channel.fetch_message(self.poll['id'])
        await msg.edit(embed=self.poll['build_embed'](self.poll), view=self.poll['view'])

        await interaction.response.send_message("✅ Vote changed.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction, button):
        # edit the original ephemeral confirmation prompt
        await interaction.response.edit_message(content="❌ Vote unchanged.", view=None)
        self.stop()

class RemoveVoteView(discord.ui.View):
    def __init__(self, poll: dict, user_id: int, *, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.poll = poll
        self.user_id = user_id

    @discord.ui.button(label="✅ Remove Vote", style=discord.ButtonStyle.danger)
    async def confirm_remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        # remove the user's previous vote
        choice = self.poll["user_votes"].pop(self.user_id, None)
        if choice is not None:
            # decrement that option's count
            self.poll["vote_count"][choice] = max(
                0, self.poll["vote_count"].get(choice, 1) - 1
            )
        # update the embed in the original poll message
        channel = interaction.guild.get_channel(self.poll["channel_id"])
        msg     = await channel.fetch_message(self.poll["id"])
        
        await msg.edit(embed=self.poll["build_embed"](self.poll), view=self.poll["view"])
        # acknowledge to the user
        await interaction.response.send_message("Your vote was removed.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction, button):
        # edit the original ephemeral confirmation prompt
        await interaction.response.edit_message(content="❌ Vote unchanged.", view=None)
        self.stop()

class ColorModal(discord.ui.Modal):
    def __init__(self, poll_data):
        super().__init__(title="Choose embed color")
        self.poll = poll_data
        self.color_input = discord.ui.TextInput(
            label="Hex code (#RRGGBB) or name (e.g. RED,PURPLE)",
            placeholder="#FF00FF"
        )
        self.add_item(self.color_input)

    async def on_submit(self, interaction: discord.Interaction):
        # 1) defer so we don’t hit the 3s timeout while updating DB & editing the embed
        await interaction.response.defer()

        raw = self.color_input.value.strip().lstrip('#').upper()
        # map of names → hex (you can add more as you like)
        names = {
            "RED":       "FF0000",
            "ORANGE":    "FFA500",
            "YELLOW":    "FFFF00",
            "LIME":      "BFFF00",
            "GREEN":     "00FF00",
            "TEAL":      "008080",
            "CYAN":      "00FFFF",
            "SKY":       "87CEEB",
            "BLUE":      "0000FF",
            "NAVY":      "000080",
            "PURPLE":    "800080",
            "VIOLET":    "EE82EE",
            "PINK":      "FF00FF",
            "MAGENTA":   "FF00FF",
            "FUCHSIA":   "FF77FF",
            "BROWN":     "8B4513",
            "BLACK":     "000000",
            "GRAY":      "808080",
            "WHITE":     "FFFFFF",
            "GOLD":      "FFD700",
            "SILVER":    "C0C0C0"
        }

        # decide whether this is a named colour or a hex code
        if raw in names:
            hexcode = names[raw]
        elif len(raw) == 6 and all(c in "0123456789ABCDEF" for c in raw):
            hexcode = raw
        else:
            await interaction.followup.send(
                "❌ Invalid colour. Please enter a hex code like `#FFA500` or a name like `RED`.",
                ephemeral=True
            )
            return

        color_int = int(hexcode, 16)

        poll = self.poll  # use the poll_data we stored in __init__
        poll['embed_color'] = color_int
        # ── strip out non‑serializable entries before saving ─────────────────
        clean = {
            k: v
            for k, v in poll.items()
            if k not in ("view", "cog", "build_embed", "button_callback", "settings_view")
        }
        # ── persist the new color and cleaned data ──────────────────────────
        # strip non‑serializable bits
        clean = {
            k: v
            for k, v in poll.items()
            if k not in ("view","cog","build_embed","button_callback","settings_view")
        }
        await interaction.client.pg_pool.execute(
            "UPDATE polls SET embed_color = $1, data = $2::jsonb WHERE id = $3",
            color_int,
            json.dumps(clean, default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o)),
            poll["id"]
        )

        # ── persist cleaned data-only (no color change) ─────────────────────
        await interaction.client.pg_pool.execute(
            "UPDATE polls SET data = $1::jsonb WHERE id = $2",
            json.dumps(clean, default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o)),
            poll["id"]
        )

        # 2) edit the public poll message embed (so everyone sees the new color)
        channel = interaction.client.get_channel(poll['channel_id'])
        msg = await channel.fetch_message(int(poll["id"]))
        embed = poll['build_embed'](poll)
        embed.color = color_int
        await msg.edit(embed=embed, view=poll['view'])

        # 3) send one follow‑up in the modal thread to confirm success
        if interaction.message:
            await interaction.message.edit(view=None)  # this removes the buttons
        await interaction.followup.send("✅ Embed color updated.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(PollCog(bot))
    print("Loaded PollCog!")
