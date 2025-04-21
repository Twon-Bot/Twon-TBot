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

class TrackingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # --- ensure our JSON store exists ---
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

    # ─── prefix command with sub‑actions ───
    @commands.command(name="tracking", aliases=["track"])
    @commands.has_any_role('The BotFather', 'Moderator', 'Manager', 'Server Owner')
    async def tracking(self, ctx, action: str = None, arg: str = None):
        """  
        No args: prompt for a new tracking entry.  
        Sub‑commands:  
          clear/empty, packs, pack <n>, output  
        """
        # --- CLEAR / EMPTY ---
        if action in ("clear", "empty"):
            self.tracked.clear()
            await self._save()
            return await ctx.send("✅ All tracking entries have been cleared.")

        # --- PACKS: list summaries ---
        if action == "packs":
            embed = discord.Embed(
                title=f"🌸 {len(self.tracked)} Tracked Packs",
                color=0xFF69B4
            )
            for rec in self.tracked:
                embed.add_field(
                    name=f"Pack #{rec['PACK_NUMBER']} – {rec['OWNER']}",
                    value=rec["CONTENTS"],
                    inline=False
                )
            return await ctx.send(embed=embed)

        # --- PACK <n>: show one entry ---
        if action == "pack" and arg and arg.isdigit():
            num = int(arg)
            rec = next((r for r in self.tracked if r["PACK_NUMBER"] == num), None)
            if not rec:
                return await ctx.send(f"❌ No entry found for pack #{num}.")
            template = self.get_pack_tracking_format()
            text = template.format(**rec)
            return await ctx.send(text)

        # --- OUTPUT: show all saved entries back‑to‑back ---
        if action == "output":
            await ctx.message.delete()
            template = self.get_pack_tracking_format()
            for rec in self.tracked:
                await ctx.send(template.format(**rec))
            return

        # --- otherwise: fall back to prompting a new entry ---
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

            # convert expire_time to <t:...:F>
            try:
                dt = datetime.strptime(expire_time, "%m/%d %H:%M")
                tz = pytz.timezone(await self.get_user_timezone(ctx.author.id) or "UTC")
                dt = dt.replace(year=datetime.now(tz).year)
                dt = tz.localize(dt).astimezone(pytz.utc)
                expire_time = f"<t:{int(dt.timestamp())}:F>"
            except:
                pass

            rec = {
                "PACK_NUMBER": int(pack_number),
                "OWNER": owner,
                "CONTENTS": contents,
                "EXPIRE_TIME": expire_time,
                "VERIFICATION_LINK": verification_link
            }
            # send formatted
            template = self.get_pack_tracking_format()
            text = template.format(**rec)
            await ctx.send(text)

            # save
            self.tracked.append(rec)
            await self._save()

        except asyncio.TimeoutError:
            await ctx.send("❌ Timed out—please try again.")

    # ─── slash command /tracking ───
    @app_commands.command(name="tracking", description="Track a new pack or view existing")
    @commands.has_any_role('The BotFather', 'Moderator', 'Manager', 'Server Owner')
    @app_commands.describe(
        pack_number="1–6",
        owner="Owner's name",
        expire_time="MM/DD HH:MM",
        verification_link="URL",
        pack1_rarity="Rarity of pack 1",
        pack1_contents="Contents of pack 1",
        pack2_rarity="(optional) Rarity of pack 2",
        pack2_contents="(optional) Contents of pack 2"
    )
    @app_commands.choices(pack1_rarity=[
        app_commands.Choice(name="⭐ ⭐", value="⭐ ⭐"),
        app_commands.Choice(name="⭐",   value="⭐"),
        app_commands.Choice(name="♦️♦️♦️♦️", value="♦️♦️♦️♦️"),
    ],
    pack2_rarity=[
        app_commands.Choice(name="⭐ ⭐", value="⭐ ⭐"),
        app_commands.Choice(name="⭐",   value="⭐"),
        app_commands.Choice(name="♦️♦️♦️♦️", value="♦️♦️♦️♦️"),
    ])
    async def tracking_slash(
        self, interaction: discord.Interaction,
        pack_number: app_commands.Range[int,1,6],
        owner: str,
        expire_time: str,
        verification_link: str,
        pack1_rarity: app_commands.Choice[str],
        pack1_contents: str,
        pack2_rarity: app_commands.Choice[str] = None,
        pack2_contents: str = None,
    ):
        # defer immediately so Discord shows “thinking…”
        await interaction.response.defer(ephemeral=False)

        try:
            # combine rarities + contents
            contents = f"{pack1_rarity.value} {pack1_contents}"
            if pack2_rarity and pack2_contents:
                contents += f" + {pack2_rarity.value} {pack2_contents}"

            # parse expire_time
            try:
                dt = datetime.strptime(expire_time, "%m/%d %H:%M")
                tz = pytz.timezone(await self.get_user_timezone(interaction.user.id) or "UTC")
                dt = dt.replace(year=datetime.now(tz).year)
                dt = tz.localize(dt).astimezone(pytz.utc)
                expire_code = f"<t:{int(dt.timestamp())}:F>"
            except:
                expire_code = expire_time

            # match your template placeholders
            rec = {
                "PACK_NUMBER": pack_number,
                "OWNER": owner,
                "CONTENTS": contents,
                "EXPIRE_TIME": expire_code,
                "VERIFICATION_LINK": verification_link
            }

            # guard against missing template
            template = self.get_pack_tracking_format()
            if not template:
                return await interaction.followup.send(
                    "⚠️ Could not load the tracking format. "
                    "Please make sure `tracking.txt` has a “Pack Tracking” section."
                )

            # send and save
            await interaction.followup.send(template.format(**rec))
            self.tracked.append(rec)
            await self._save()

        except Exception as e:
            # always send a response so the interaction completes
            await interaction.followup.send(f"❌ Error: {e}")

async def setup(bot):
    await bot.add_cog(TrackingCog(bot))
    print("Loaded TrackingCog!")
