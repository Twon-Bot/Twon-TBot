import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime
import pytz
import json
import os

TRACKING_JSON = "tracking_data.json"
TRACKING_TEMPLATE = "tracking.txt"
EMBED_COLOR = 0xFF69B4

# utility to format embed description with markdown header for pack line
def format_embed_text(rec, template):
    """
    Formats the template text, then converts the first line (the pack line) into a markdown heading.
    """
    raw = template.format(**rec)
    lines = raw.splitlines()
    if lines:
        lines[0] = f"### {lines[0]}"
    return "\n".join(lines)

class ConfirmReplaceView(discord.ui.View):
    def __init__(self, cog, old_rec, new_rec, is_slash, ctx_or_interaction):
        super().__init__(timeout=60)
        self.cog = cog
        self.old_rec = old_rec
        self.new_rec = new_rec
        self.is_slash = is_slash
        self.ctx_or_interaction = ctx_or_interaction

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.tracked.remove(self.old_rec)
        self.cog.tracked.append(self.new_rec)
        await self.cog._save()
        embed = discord.Embed(
            description=format_embed_text(self.new_rec, self.cog.get_pack_tracking_format()),
            color=EMBED_COLOR
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            description=f"❌ Swap canceled; kept existing pack #{self.old_rec['PACK_NUMBER']}.",
            color=EMBED_COLOR
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)
        self.stop()

class TrackingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not os.path.exists(TRACKING_JSON):
            with open(TRACKING_JSON, "w") as f:
                json.dump([], f)
        with open(TRACKING_JSON, "r") as f:
            self.tracked = json.load(f)

    async def _save(self):
        with open(TRACKING_JSON, "w") as f:
            json.dump(self.tracked, f, indent=2)

    async def get_user_timezone(self, user_id):
        row = await self.bot.pg_pool.fetchrow(
            "SELECT timezone FROM timezones WHERE user_id = $1",
            user_id
        )
        return row["timezone"] if row else None

    def get_pack_tracking_format(self):
        try:
            with open(TRACKING_TEMPLATE, "r", encoding="utf-8") as file:
                sections = file.read().split("===")
                for section in sections:
                    if "Pack Tracking" in section:
                        lines = section.strip().splitlines()
                        return "\n".join(lines[1:]).strip() if lines else None
        except FileNotFoundError:
            return None

    @commands.command(name="tracking", aliases=["track", "t"])
    @commands.has_any_role('The BotFather', 'Moderator', 'Manager', 'Server Owner')
    async def tracking(self, ctx, action: str = None, arg: str = None):
        """
        No args: prompt for a new tracking entry.
        Sub‑commands:
          clear/empty [n], packs, pack <n>, output, announcement
        """
        # CLEAR / EMPTY
        if action in ("clear", "empty"):
            if arg and arg.isdigit():
                num = int(arg)
                rec = next((r for r in self.tracked if r["PACK_NUMBER"] == num), None)
                if rec:
                    self.tracked.remove(rec)
                    await self._save()
                    embed = discord.Embed(description=f"✅ Removed tracking for pack #{num}.", color=EMBED_COLOR)
                    return await ctx.send(embed=embed)
                embed = discord.Embed(description=f"❌ No tracking found for pack #{num}.", color=EMBED_COLOR)
                return await ctx.send(embed=embed)
            self.tracked.clear()
            await self._save()
            embed = discord.Embed(description="✅ All tracking entries have been cleared.", color=EMBED_COLOR)
            return await ctx.send(embed=embed)

        # PACKS
        if action == "packs":
            embed = discord.Embed(title=f"🌸 {len(self.tracked)} Tracked Packs", color=EMBED_COLOR)
            for rec in sorted(self.tracked, key=lambda r: r['PACK_NUMBER']):
                embed.add_field(name=f"Pack #{rec['PACK_NUMBER']} – {rec['OWNER']}", value=rec['CONTENTS'], inline=False)
            return await ctx.send(embed=embed)

        # PACK <n>
        if action == "pack" and arg and arg.isdigit():
            num = int(arg)
            rec = next((r for r in self.tracked if r['PACK_NUMBER'] == num), None)
            if not rec:
                embed = discord.Embed(description=f"❌ No entry found for pack #{num}.", color=EMBED_COLOR)
                return await ctx.send(embed=embed)
            template = self.get_pack_tracking_format()
            desc = format_embed_text(rec, template)
            embed = discord.Embed(description=desc, color=EMBED_COLOR)
            return await ctx.send(embed=embed)

        # OUTPUT all
        if action == "output":
            await ctx.message.delete()
            template = self.get_pack_tracking_format()
            for rec in sorted(self.tracked, key=lambda r: r['PACK_NUMBER']):
                desc = format_embed_text(rec, template)
                embed = discord.Embed(description=desc, color=EMBED_COLOR)
                await ctx.send(embed=embed)
            return

        # ANNOUNCEMENT
        if action in ("announcement", "a", "ann", "announce"):
            summary = [f"{r['OWNER']}, {r['CONTENTS']}" for r in sorted(self.tracked, key=lambda r: r['PACK_NUMBER'])]
            embed = discord.Embed(description=" , ".join(summary), color=EMBED_COLOR)
            return await ctx.send(embed=embed)

        # prompt new entry
        prompt = (
            "**Please provide:**\n"
            "Pack Number,\n"
            "Owner,\n"
            "Pack Contents,\n"
            "Expiry Date (MM/DD HH:MM),\n"
            "Verification Link"
        )
        await ctx.send(prompt)
        def check(m): return m.author == ctx.author and m.channel == ctx.channel
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=120)
            parts = [p.strip() for p in msg.content.split(",")]
            if len(parts) != 5:
                return await ctx.send("❌ Need exactly 5 comma‑separated values.")
            pack_number, owner, contents, expire_time, verification_link = parts
            try:
                dt = datetime.strptime(expire_time, "%m/%d %H:%M")
                tz = pytz.timezone(await self.get_user_timezone(ctx.author.id) or "UTC")
                dt = dt.replace(year=datetime.now(tz).year)
                dt = tz.localize(dt).astimezone(pytz.utc)
                expire_time = f"<t:{int(dt.timestamp())}:F>"
            except:
                pass
            new_rec = {"PACK_NUMBER": int(pack_number), "OWNER": owner, "CONTENTS": contents, "EXPIRE_TIME": expire_time, "VERIFICATION_LINK": verification_link}
            existing = next((r for r in self.tracked if r['PACK_NUMBER'] == new_rec['PACK_NUMBER']), None)
            template = self.get_pack_tracking_format()
            if existing:
                text_old = template.format(**existing)
                view = ConfirmReplaceView(self, existing, new_rec, False, ctx)
                embed = discord.Embed(description=f"⚠️ A pack #{new_rec['PACK_NUMBER']} already exists:\n{text_old}\nReplace with new entry?", color=EMBED_COLOR)
                return await ctx.send(embed=embed, view=view)
            self.tracked.append(new_rec)
            await self._save()
            desc = format_embed_text(new_rec, template)
            embed = discord.Embed(description=desc, color=EMBED_COLOR)
            await ctx.send(embed=embed)
        except asyncio.TimeoutError:
            await ctx.send("❌ Timed out—please try again.")

    @app_commands.command(name="tracking", description="Track a new pack or view existing")
    @commands.has_any_role('The BotFather', 'Moderator', 'Manager', 'Server Owner')
    @app_commands.describe(
        pack_number="1–6",
        owner="Owner's name",
        expire_time="MM/DD HH:MM",
        verification_link="URL",
        pack1_rarity="Rarity of card 1",
        pack1_contents="Card 1 contents",
        pack2_rarity="(optional) Rarity of card 2",
        pack2_contents="(optional) Card 2 contents"
    )
    @app_commands.choices(
        pack1_rarity=[
            app_commands.Choice(name="⭐ ⭐", value="⭐ ⭐"),
            app_commands.Choice(name="⭐",   value="⭐"),
            app_commands.Choice(name="♦️♦️♦️♦️", value="♦️♦️♦️♦️"),
        ],
        pack2_rarity=[
            app_commands.Choice(name="⭐ ⭐", value="⭐ ⭐"),
            app_commands.Choice(name="⭐",   value="⭐"),
            app_commands.Choice(name="♦️♦️♦️♦️", value="♦️♦️♦️♦️"),
        ]
    )
    async def tracking_slash(self, interaction: discord.Interaction,
                              pack_number: app_commands.Range[int,1,6], owner: str,
                              expire_time: str, verification_link: str,
                              pack1_rarity: app_commands.Choice[str], pack1_contents: str,
                              pack2_rarity: app_commands.Choice[str] = None, pack2_contents: str = None):
        await interaction.response.defer(ephemeral=True)
        contents = f"{pack1_rarity.value} {pack1_contents}"
        if pack2_rarity and pack2_contents:
            contents += f" + {pack2_rarity.value} {pack2_contents}"
        try:
            dt = datetime.strptime(expire_time, "%m/%d %H:%M")
            tz = pytz.timezone(await self.get_user_timezone(interaction.user.id) or "UTC")
            dt = dt.replace(year=datetime.now(tz).year)
            dt = tz.localize(dt).astimezone(pytz.utc)
            expire_code = f"<t:{int(dt.timestamp())}:F>"
        except:
            expire_code = expire_time
        new_rec = {"PACK_NUMBER": pack_number, "OWNER": owner, "CONTENTS": contents, "EXPIRE_TIME": expire_code, "VERIFICATION_LINK": verification_link}
        template = self.get_pack_tracking_format()
        if not template:
            return await interaction.followup.send("⚠️ Could not load the tracking format. Please ensure `tracking.txt` has a Pack Tracking section.", ephemeral=True)
        existing = next((r for r in self.tracked if r['PACK_NUMBER'] == pack_number), None)
        if existing:
            text_old = template.format(**existing)
            view = ConfirmReplaceView(self, existing, new_rec, True, interaction)
            embed = discord.Embed(description=f"⚠️ A pack #{pack_number} already exists:\n{text_old}\nReplace with new entry?", color=EMBED_COLOR)
            return await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        self.tracked.append(new_rec)
        await self._save()
        desc = format_embed_text(new_rec, template)
        embed = discord.Embed(description=desc, color=EMBED_COLOR)
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(TrackingCog(bot))
    print("Loaded TrackingCog!")
