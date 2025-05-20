import discord
from discord.ext import commands, tasks
import json
import os  # For safe file replacement
from datetime import datetime
import pytz
import asyncio
from dotenv import load_dotenv

# File to store scheduled announcements
DELAY_FILE = "delayed_announcements.json"
ANNOUNCEMENTS_FILE = "announcements.txt"  # Ensure this file exists

# Get channel ID's from .env
load_dotenv()

ANNOUNCEMENT_CHANNEL_ID = int(os.getenv("ANNOUNCEMENT_CHANNEL_ID"))
TEST_ANNOUNCEMENT_CHANNEL_ID = int(os.getenv("TEST_ANNOUNCEMENT_CHANNEL_ID"))
SCHEDULE_CHANNEL_ID = int(os.getenv("SCHEDULE_CHANNEL_ID"))
ACTIVITY_CHECK_CHANNEL_ID = int(os.getenv("ACTIVITY_CHECK_CHANNEL_ID"))

class DelayedAnnouncements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Load announcements from file into memory
        self.delayed_announcements = self.load_delayed_announcements()
        self.lock = asyncio.Lock()
        self.existing_announcements = self.load_announcements()
        if not self.check_delays.is_running():
            self.check_delays.start()
        print("DEBUG: DelayedAnnouncementsCog initialized.")
        
    def cog_unload(self):
        # Cancel the check_delays task when the cog unloads
        self.check_delays.cancel()

    def load_delayed_announcements(self):
        """Load delayed announcements from the JSON file.
           Expected structure: { "timestamp": [ann_dict, ...], ... }"""
        if not os.path.exists(DELAY_FILE):
            return {}
        try:
            with open(DELAY_FILE, "r") as file:
                data = json.load(file)
            # Convert keys to ints and ensure each value is a list.
            return {int(k): (v if isinstance(v, list) else [v]) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error loading JSON from {DELAY_FILE}: {e}")
            return {}

    def save_delayed_announcements(self):
        """Save the current delayed announcements to the JSON file safely using a temp file."""
        try:
            temp_file = DELAY_FILE + ".tmp"
            with open(temp_file, "w") as file:
                json.dump(self.delayed_announcements, file, indent=4)
            os.replace(temp_file, DELAY_FILE)
        except Exception as e:
            print(f"Error saving JSON to {DELAY_FILE}: {e}")

    def load_announcements(self):
        """Load announcement names from announcements.txt."""
        try:
            with open(ANNOUNCEMENTS_FILE, "r", encoding="utf-8") as file:
                lines = file.read().splitlines()
            return [line.strip().lower() for line in lines if line.strip()]
        except FileNotFoundError:
            return []

    async def get_announcement(self, message):
        """Retrieve the full announcement template text by name."""
        try:
            with open(ANNOUNCEMENTS_FILE, "r", encoding="utf-8") as file:
                content = file.read()
            announcements = content.split("===")
            for announcement in announcements:
                lines = announcement.strip().splitlines()
                if lines and lines[0].strip().lower() == message.lower():
                    return "\n".join(lines[1:])
        except Exception as e:
            print(f"Error reading announcements: {e}")
        return None

    # ── Helper: Create a schedule embed matching your >csch output ──
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

    async def delay_announcement(self, ctx, announcement_name: str, time_str: str, substitutions: dict = None):
        """
        Schedule an announcement for a later time (format: MM/DD HH:MM).
        If the provided time is in the past or already used, prompt for a new time (or type 'exit' to cancel).
        The optional substitutions dictionary is stored for later template formatting.
        """
        normalized_name = announcement_name.lower()
        if normalized_name not in self.existing_announcements:
            await ctx.send(f"Error: The announcement {announcement_name} does not exist.")
            return

        user_timezone = self.bot.get_cog("Schedule").get_user_timezone(ctx.author.id) or "UTC"
        tz = pytz.timezone(user_timezone)

        while True:
            if time_str.lower() == "exit":
                await ctx.send("Announcement scheduling canceled.")
                return

            try:
                local_time = datetime.strptime(time_str, "%m/%d %H:%M")
                local_time = local_time.replace(year=datetime.now(tz).year)
            except ValueError:
                await ctx.send("Invalid time format! Use MM/DD HH:MM. Please try again or type `exit` to cancel.")
                msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                time_str = msg.content.strip()
                continue

            localized_time = tz.localize(local_time)
            utc_time = localized_time.astimezone(pytz.utc)
            now_utc = datetime.now(pytz.utc)
            if utc_time < now_utc:
                await ctx.send(f"Error: The time you provided, <t:{int(utc_time.timestamp())}:F>, is in the past.")
                await ctx.send("Please provide a new time in MM/DD HH:MM format or type `exit` to cancel.")
                msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                time_str = msg.content.strip()
                continue

            timestamp = int(utc_time.timestamp())
            async with self.lock:
                if timestamp in self.delayed_announcements:
                    await ctx.send("There is already an announcement scheduled for that time. Please choose a different time or type `exit` to cancel.")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                    time_str = msg.content.strip()
                    continue
            break

        # Optional debug: warn if scheduling a wonder pick announcement without substitutions.
        if normalized_name.startswith("wonder pick") and substitutions is None:
            print(f"DEBUG: Scheduling wonder pick announcement '{announcement_name}' without substitutions.")

        # ── Change in channel selection for test mode ──
        if normalized_name == "activity check":
            channel_id = ACTIVITY_CHECK_CHANNEL_ID  # Activity Check channel
        elif normalized_name == "schedule":
            # If the scheduling command came from a test channel, use the test announcement channel
            if ctx.channel.id == TEST_ANNOUNCEMENT_CHANNEL_ID:
                channel_id = TEST_ANNOUNCEMENT_CHANNEL_ID
            else:
                channel_id = SCHEDULE_CHANNEL_ID
        else:
            channel_id = ANNOUNCEMENT_CHANNEL_ID  # Default announcements channel

        ann_data = {
            "name": normalized_name,
            "announce_channel": channel_id,
            "input_channel": ctx.channel.id,
            "author": ctx.author.id,
            "substitutions": substitutions,
            "warned": False
        }
        async with self.lock:
            if timestamp in self.delayed_announcements:
                self.delayed_announcements[timestamp].append(ann_data)
            else:
                self.delayed_announcements[timestamp] = [ann_data]
            self.save_delayed_announcements()  # Save changes after scheduling
            pending_count = sum(len(lst) for lst in self.delayed_announcements.values())
            print(f"DEBUG: Added announcement at {timestamp}. Current announcements: {self.delayed_announcements}")
        await ctx.send(f"Scheduled announcement: **{announcement_name}** for <t:{timestamp}:F>.\n"
                       f"There are now **{pending_count} announcement(s)** pending.")

    @commands.command(name="viewdelay", aliases=["vdelay"])
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner')
    async def view_delayed_announcements(self, ctx):
        """Show all pending delayed announcements in a clean format with a small orange diamond emoji."""
        async with self.lock:
            if not self.delayed_announcements:
                await ctx.send("No pending announcements.")
                return
            
            embed = discord.Embed(title="Pending Announcements  📋", color=0xFF8C00)
            lines = ["──────────────────────────────"]
            
            for ts, ann_list in sorted(self.delayed_announcements.items()):
                for ann in ann_list:
                    lines.append(f"🔸 **{ann['name']}**\n   - <t:{ts}:F>")
                    
            embed.description = "\n".join(lines)
            await ctx.send(embed=embed)

    @commands.command(name="canceldelay", aliases=["cdelay"])
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner')
    async def cancel_delayed_announcement(self, ctx, *, time_str: str = None):
        """Cancel a scheduled announcement. Format: >canceldelay MM/DD HH:MM"""
        async with self.lock:
            if not self.delayed_announcements:
                await ctx.send("There are no pending announcements to cancel.")
                return
            if not time_str:
                await ctx.send("Error: Please provide the scheduled time to cancel in the format:\n **>canceldelay MM/DD HH:MM**")
                return
            try:
                user_timezone = self.bot.get_cog("Schedule").get_user_timezone(ctx.author.id) or "UTC"
                tz = pytz.timezone(user_timezone)
                local_time = datetime.strptime(time_str, "%m/%d %H:%M")
                local_time = local_time.replace(year=datetime.now(tz).year)
                localized_time = tz.localize(local_time)
                utc_time = localized_time.astimezone(pytz.utc)
                timestamp = int(utc_time.timestamp())
                if timestamp in self.delayed_announcements:
                    removed_list = self.delayed_announcements.pop(timestamp)
                    self.save_delayed_announcements()  # Save changes after removal
                    names = ", ".join(f"**{ann['name']}**" for ann in removed_list)
                    await ctx.send(f"Cancelled {names} originally set for <t:{timestamp}:F>.")
                else:
                    print(f"DEBUG: Timestamp {timestamp} not found. Current keys: {list(self.delayed_announcements.keys())}")
                    await ctx.send("No announcement found at that time.")
            except ValueError:
                await ctx.send("Invalid time format! Use MM/DD HH:MM.")

    @tasks.loop(minutes=1)
    async def check_delays(self):
        async with self.lock:
            now = int(datetime.now(pytz.utc).timestamp())
            # Send 5-minute warnings for announcements that are not yet due
            for ts, ann_list in self.delayed_announcements.items():
                time_remaining = ts - now
                if 0 < time_remaining <= 300:  # 300 seconds = 5 minutes
                    for ann in ann_list:
                        if not ann.get("warned", False):
                            ann["warned"] = True
                            input_channel = self.bot.get_channel(ann["input_channel"])
                            if input_channel:
                                warning_msg = (
                                    f"**5 Minute Warning:** The announcement **{ann['name']}** "
                                    f"scheduled for <t:{ts}:F> from <@{ann['author']}> will be announced in 5 minutes. "
                                    "You can cancel it using `!!canceldelay`."
                                )
                                await input_channel.send(warning_msg)
            # Process due announcements
            due_announcements = []
            for ts in list(self.delayed_announcements.keys()):
                if ts <= now:
                    due_announcements.extend(self.delayed_announcements.pop(ts))
            self.save_delayed_announcements()  # Save after processing due announcements
            pending_count = sum(len(lst) for lst in self.delayed_announcements.values())
        confirmations = {}
        for data in due_announcements:
            announce_channel = self.bot.get_channel(data["announce_channel"])
            input_channel = self.bot.get_channel(data["input_channel"])
            announcement_text = await self.get_announcement(data["name"])
            if announcement_text and data.get("substitutions"):
                try:
                    announcement_text = announcement_text.format(**data["substitutions"])
                except Exception as e:
                    print("Error formatting announcement:", e)
            if announce_channel:
                if announcement_text:
                    await announce_channel.send(announcement_text)
                else:
                    await announce_channel.send(f"Announcement {data['name']} is now due.")
                # ── Change: If this is a schedule announcement, also send the current schedule embed ──
                if data["name"].lower() == "schedule":
                    schedule_cog = self.bot.get_cog("Schedule")
                    if schedule_cog:
                        schedule = schedule_cog.get_schedule()
                        if schedule:
                            embed = self.create_schedule_embed(schedule)
                            if embed:
                                await announce_channel.send(embed=embed)
            if input_channel:
                confirmations.setdefault(input_channel.id, input_channel)
        for ch in confirmations.values():
            await ch.send(f"Announcement confirmed. There are {pending_count} announcement(s) pending.")

    @check_delays.before_loop
    async def before_check_delays(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(DelayedAnnouncements(bot))
    print("Loaded DelayedAnnouncementsCog!")
