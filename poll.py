import discord
from discord.ext import commands, tasks
from discord import app_commands
import csv, io, asyncio, re
from datetime import datetime, timedelta
import pytz

# Numeric keycap emojis 1–10
OPTION_EMOJIS = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
BAR_LENGTH = 8
NEON_GREEN = 0x39FF14

def format_time_delta(delta: timedelta):
    secs = int(delta.total_seconds())
    if secs < 0:
        return "0 minutes"
    h, r = divmod(secs, 3600)
    m, _ = divmod(r, 60)
    parts = []
    if h: parts.append(f"{h} hour{'s' if h!=1 else ''}")
    if m: parts.append(f"{m} minute{'s' if m!=1 else ''}")
    return " ".join(parts)

class ConfirmView(discord.ui.View):
    def __init__(self, poll_data, message, new_choice):
        super().__init__(timeout=30)
        self.poll_data = poll_data
        self.message = message
        self.new_choice = new_choice

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, button, interaction):
        uid = interaction.user.id
        # remove old vote
        old = self.poll_data['user_votes'].pop(uid, None)
        if old:
            self.poll_data['vote_count'][old] -= 1
        # add new vote
        self.poll_data['user_votes'][uid] = self.new_choice
        self.poll_data['vote_count'][self.new_choice] += 1
        self.poll_data['total_votes'] = len(self.poll_data['user_votes'])
        # re-render
        embed = self.poll_data['build'](self.poll_data)
        await self.message.edit(embed=embed, view=self.poll_data['view'])
        await interaction.response.send_message("✅ Your vote was changed.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, button, interaction):
        await interaction.response.send_message("👍 Your vote remains.", ephemeral=True)
        self.stop()

class AddOptionModal(discord.ui.Modal, title="Add Poll Option"):
    new_option = discord.ui.TextInput(label="Option text", max_length=100)
    def __init__(self, poll_data, message):
        super().__init__()
        self.poll_data = poll_data
        self.message = message

    async def on_submit(self, interaction):
        opt = self.new_option.value.strip()
        if not opt:
            return await interaction.response.send_message("Cannot add empty option.", ephemeral=True)
        if opt in self.poll_data['options']:
            return await interaction.response.send_message("Option already exists.", ephemeral=True)
        if len(self.poll_data['options'])>=10:
            return await interaction.response.send_message("Max 10 options.", ephemeral=True)
        # append
        self.poll_data['options'].append(opt)
        self.poll_data['vote_count'][opt] = 0
        # rebuild view
        view = self.poll_data['view']
        view.clear_items()
        for i,o in enumerate(self.poll_data['options']):
            btn = discord.ui.Button(label=OPTION_EMOJIS[i], custom_id=o)
            btn.callback = self.poll_data['vote_cb']
            view.add_item(btn)
        # add and settings
        plus = discord.ui.Button(label="➕", style=discord.ButtonStyle.secondary, custom_id="add_option")
        plus.callback = self.poll_data['cog'].add_option
        view.add_item(plus)
        settings = discord.ui.Button(label="⚙️", style=discord.ButtonStyle.secondary, custom_id="settings")
        settings.callback = self.poll_data['cog'].open_settings
        view.add_item(settings)
        # update
        embed = self.poll_data['build'](self.poll_data)
        await self.message.edit(embed=embed, view=view)
        await interaction.response.send_message(f"Added option **{opt}**.", ephemeral=True)

class SettingsView(discord.ui.View):
    def __init__(self, cog, poll_data, message):
        super().__init__(timeout=None)
        self.cog = cog
        self.poll_data = poll_data
        self.message = message

    @discord.ui.select(
        placeholder="Choose action…",
        options=[
            discord.SelectOption(label="Edit spelling", value="edit"),
            discord.SelectOption(label="Change end time", value="time"),
            discord.SelectOption(label="Remove voting option", value="remove")
        ]
    )
    async def select_action(self, select, interaction):
        choice = select.values[0]
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(f"You chose **{select.placeholder}**.", ephemeral=True)
        if choice=="edit":
            # prompt in chat
            await interaction.followup.send("Reply with `# new text`, e.g. `2. Oranges`", ephemeral=True)
            def chk(m):
                return m.author==interaction.user and m.channel_id==interaction.channel_id and re.match(r"^\d+\.\s+.+", m.content)
            try:
                msg = await self.cog.bot.wait_for("message", check=chk, timeout=60)
            except asyncio.TimeoutError:
                return await interaction.followup.send("✋ Timed out.", ephemeral=True)
            idx,text = msg.content.split(".",1)
            idx = int(idx)-1
            if 0<=idx<len(self.poll_data['options']):
                old = self.poll_data['options'][idx]
                self.poll_data['options'][idx] = text.strip()
                # preserve votes
                cnt = self.poll_data['vote_count'].pop(old,0)
                self.poll_data['vote_count'][text.strip()] = cnt
                embed = self.poll_data['build'](self.poll_data)
                await self.message.edit(embed=embed, view=self.poll_data['view'])
                await msg.delete()
                await interaction.followup.send(f"Edited option #{idx+1}.", ephemeral=True)
            else:
                await interaction.followup.send("Invalid index.", ephemeral=True)

        elif choice=="time":
            await interaction.followup.send("Reply with new end time `MM/DD HH:MM`", ephemeral=True)
            def chk2(m):
                return m.author==interaction.user and re.match(r"^\d{2}/\d{2}\s+\d{2}:\d{2}$", m.content)
            try:
                msg2 = await self.cog.bot.wait_for("message", check=chk2, timeout=60)
            except asyncio.TimeoutError:
                return await interaction.followup.send("✋ Timed out.", ephemeral=True)
            # parse timezone
            tz = pytz.timezone(self.poll_data['tz'])
            dt = datetime.strptime(msg2.content, "%m/%d %H:%M").replace(year=datetime.now(tz).year)
            utc = tz.localize(dt).astimezone(pytz.utc)
            self.poll_data['end'] = utc
            embed = self.poll_data['build'](self.poll_data)
            await self.message.edit(embed=embed, view=self.poll_data['view'])
            await msg2.delete()
            await interaction.followup.send("End time updated.", ephemeral=True)

        else:  # remove
            opts = self.poll_data['options']
            text = "\n".join(f"{i+1}. {o}" for i,o in enumerate(opts))
            await interaction.followup.send(f"Which to remove?\n{text}", ephemeral=True)
            def chk3(m):
                return m.author==interaction.user and m.content.isdigit()
            try:
                msg3 = await self.cog.bot.wait_for("message", check=chk3, timeout=60)
            except asyncio.TimeoutError:
                return await interaction.followup.send("✋ Timed out.", ephemeral=True)
            i = int(msg3.content)-1
            if 0<=i<len(opts):
                rem = opts.pop(i)
                self.poll_data['vote_count'].pop(rem,None)
                embed = self.poll_data['build'](self.poll_data)
                await self.message.edit(embed=embed, view=self.poll_data['view'])
                await msg3.delete()
                await interaction.followup.send(f"Removed option **{rem}**.", ephemeral=True)
            else:
                await interaction.followup.send("Invalid.", ephemeral=True)

    @discord.ui.button(label="Close Settings", style=discord.ButtonStyle.secondary)
    async def close(self, button, interaction):
        await interaction.response.edit_message(content="Settings closed.", view=None, ephemeral=True)

class PollCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.polls = {}

    async def get_tz(self, user_id):
        row = await self.bot.pg_pool.fetchrow("SELECT timezone FROM timezones WHERE user_id=$1", user_id)
        return row["timezone"] if row else "UTC"

    @commands.Cog.listener()
    async def on_ready(self):
        # sync slash
        await self.bot.tree.sync()

    @app_commands.command(name="poll", description="Create a poll")
    @app_commands.describe(
        question="Poll question",
        mentions="Role or @everyone to mention",
        multiple="Allow multiple votes",
        end_time="MM/DD HH:MM (optional)",
        option1="Option 1",
        option2="Option 2",
        option3="Option 3",
        option4="Option 4",
        option5="Option 5",
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
                         option5: str = None):
        await interaction.response.defer()
        opts = [o for o in (option1,option2,option3,option4,option5) if o]
        if len(opts)<2:
            return await interaction.followup.send("Need ≥2 options.", ephemeral=True)
        # parse end_time
        tzname = await self.get_tz(interaction.user.id)
        tz = pytz.timezone(tzname)
        utc_end = None
        if end_time:
            if not re.match(r"^\d{2}/\d{2}\s+\d{2}:\d{2}$", end_time):
                return await interaction.followup.send("Invalid end_time format.", ephemeral=True)
            dt = datetime.strptime(end_time,"%m/%d %H:%M").replace(year=datetime.now(tz).year)
            utc_end = tz.localize(dt).astimezone(pytz.utc)

        poll_data = {
            'question': question,
            'options': opts.copy(),
            'vote_count': {o:0 for o in opts},
            'total_votes': 0,
            'user_votes': {},
            'multiple': multiple,
            'author': interaction.user.display_name,
            'mention': mentions or "",
            'end': utc_end,
            'tz': tzname,
            'cog': self
        }

        def build(pd):
            # header
            header = ""
            if pd['end']:
                now = datetime.utcnow().replace(tzinfo=pytz.utc)
                if now < pd['end']:
                    ts = int(pd['end'].timestamp())
                    header = f"**Poll ends:** <t:{ts}:F>\n\n"
                else:
                    header = "**The poll has ended.**\n\n"
            # bars
            txt=""
            for i,o in enumerate(pd['options']):
                cnt = pd['vote_count'][o]
                pct = (cnt/pd['total_votes']*100) if pd['total_votes'] else 0
                filled = int(BAR_LENGTH*pct//100)
                txt+=f"{OPTION_EMOJIS[i]} {o}\n[{'🟩'*filled}{'⬜'*(BAR_LENGTH-filled)}] | {pct:.1f}% ({cnt})\n"
            # mention field at bottom
            if pd['mention']:
                txt+=f"\n{pd['mention']}\n"
            embed=discord.Embed(title=f"📊 **{pd['question']}**",
                                description=header+txt,
                                color=NEON_GREEN)
            embed.set_footer(text=f"➕ Add Option | ⚙️ Settings | Created by {pd['author']}")
            return embed

        poll_data['build']=build

        # create view
        view=discord.ui.View(timeout=None)
        async def vote_cb(interaction: discord.Interaction):
            pd = self.polls[interaction.message.id]
            uid = interaction.user.id
            choice = interaction.data['custom_id']

            # Single-vote confirmation
            if not pd['multiple'] and uid in pd['user_votes'] and pd['user_votes'][uid] != choice:
                return await interaction.response.send_message(
                    "You already voted—remove old vote?",
                    view=ConfirmView(pd, interaction.message, choice),
                    ephemeral=True
                )

            # Multiple-vote toggle or single-vote register
            if pd['multiple']:
                user_list = pd['user_votes'].setdefault(uid, [])
                if choice in user_list:
                    user_list.remove(choice)
                    pd['vote_count'][choice] -= 1
                else:
                    user_list.append(choice)
                    pd['vote_count'][choice] += 1
            else:
                # either first vote or re-voted same choice
                pd['user_votes'][uid] = choice
                pd['vote_count'][choice] += 1

            pd['total_votes'] = len(pd['user_votes'])
            await interaction.response.edit_message(embed=pd['build'](pd), view=pd['view'])

        # add buttons
        for i,o in enumerate(opts):
            b=discord.ui.Button(label=OPTION_EMOJIS[i], custom_id=o)
            b.callback=vote_cb
            view.add_item(b)
        addb = discord.ui.Button(label="➕", style=discord.ButtonStyle.secondary, custom_id="add_option")
        async def add_cb(interaction: discord.Interaction):
            await interaction.response.send_modal(AddOptionModal(poll_data, interaction.message))
        addb.callback = add_cb
        view.add_item(addb)
        setb = discord.ui.Button(label="⚙️", style=discord.ButtonStyle.secondary, custom_id="settings")
        async def settings_cb(interaction: discord.Interaction):
            await interaction.response.send_message(
                "Poll Settings:",
                view=SettingsView(self, poll_data, interaction.message),
                ephemeral=True
            )
        setb.callback = settings_cb
        view.add_item(setb)

        msg=await interaction.followup.send(content=poll_data['mention'], embed=build(poll_data), view=view)
        poll_data['view']=view
        poll_data['channel_id'] = msg.channel.id
        poll_data['vote_cb']=vote_cb
        self.polls[msg.id]=poll_data

        if utc_end:
            # schedule
            delay=(utc_end-datetime.utcnow().replace(tzinfo=pytz.utc)).total_seconds()
            asyncio.create_task(self._auto_close(msg.id, delay))

    async def _auto_close(self, msg_id, delay):
        if delay>0: await asyncio.sleep(delay)
        pd=self.polls.get(msg_id)
        if not pd: return
        pd['end']=datetime.utcnow().replace(tzinfo=pytz.utc)
        # disable option & add
        for i in pd['view'].children:
            if i.custom_id not in ("settings",):
                i.disabled=True
        ch = self.bot.get_channel(pd['channel_id'])
        msg=await ch.fetch_message(msg_id)
        await msg.edit(embed=pd['build'](pd), view=pd['view'])

async def setup(bot):
    await bot.add_cog(PollCog(bot))
