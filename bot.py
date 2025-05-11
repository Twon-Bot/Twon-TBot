# Use RAILWAY as the cloud platform

import discord
import sqlite3
import os
import asyncpg
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime


# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN2")
if not TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN2 environment variable not set.")
# Get Guild ID's from .env to update poll.py's slash commands
GUILD_IDS = [int(gid.strip()) for gid in os.getenv("GUILD_IDS", "").split(",") if gid.strip()]

# grab the test‑announcement channel ID so we can notify it on shutdown
TEST_ANNOUNCEMENT_CHANNEL_ID = int(os.getenv("TEST_ANNOUNCEMENT_CHANNEL_ID", 0))

# Set up the bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!!", intents=intents, case_insensitive=True, help_command=None)

# Track whether slash commands have been synced
_slash_synced = False

class Database:
    def __init__(self, db_file='bot_data.db'):
        self.connection = sqlite3.connect(db_file)

    def execute(self, query, params=()):
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        self.connection.commit()
        return cursor

    def close(self):
        self.connection.close()


def initialize_database(db):
    db.execute('''CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        next_announcement TEXT NOT NULL,
        phase TEXT,
        time INTEGER
    )''')

class AnnouncementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("AnnouncementCog has been loaded.")

    @commands.command()
    async def announce(self, ctx, *, message: str):
        confirmation_msg = await ctx.send("React with 👍 to confirm this announcement to @everyone.")
        await confirmation_msg.add_reaction("👍")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == "👍" and reaction.message.id == confirmation_msg.id

        try:
            await self.bot.wait_for('reaction_add', check=check, timeout=30)
            await ctx.send(f"@everyone {message}")
        except asyncio.TimeoutError:
            await ctx.send("Announcement confirmation timed out. Please try again.")


@bot.command(aliases=["gtz"])
@commands.has_any_role('The BotFather', 'Moderator', 'Manager', 'Server Owner', 'Police')
async def gettimezone(ctx, user: discord.User = None):
    """Show the timezone for yourself or another user."""
    target = user or ctx.author
    row = await bot.pg_pool.fetchrow(
        "SELECT timezone FROM timezones WHERE user_id = $1",
        target.id
    )
    tz = row["timezone"] if row else None

    if tz:
        if user:
            await ctx.send(f"⏰ Timezone for {target.id} is set to **{tz}**.")
        else:
            await ctx.send(f"⏰ Your timezone is set to **{tz}**.")
    else:
        if user:
            await ctx.send(f"❌ {target.id} has no timezone set yet.")
        else:
            await ctx.send("❌ You have not set a timezone yet. Use `!!settimezone <timezone>` to set it.")

async def load_extensions():
    print("Loading extensions...")
    try:
        await bot.load_extension('announce')
        await bot.load_extension('schedule')
        await bot.load_extension('help')
        await bot.load_extension('poll')
        await bot.load_extension('delay')
        await bot.load_extension('expire')
        await bot.load_extension('tracking')
        await bot.load_extension('write')
        await bot.load_extension('endcycle')
        await bot.load_extension('delete')
        await bot.load_extension('addingschedule')
        await bot.load_extension('timestamp')
        await bot.load_extension('tony')
        await bot.load_extension('happytree')
        await bot.load_extension('livepackowner')
        await bot.load_extension('honorary')
        await bot.load_extension('embed')
        print("Extensions loaded successfully.")
        print("Registered commands:", [cmd.name for cmd in bot.commands])
    except Exception as e:
        print(f'Failed to load extension: {e}')

@bot.event
async def on_command_error(ctx, error):
    print(f"Command error: {error}")
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"Unknown command. Use `!!help` to see available commands.")
    else:
        raise error

@bot.event
async def on_ready():
    global _slash_synced
    # Sync slash commands only once
    if not _slash_synced:
        for gid in GUILD_IDS:
            guild_obj = discord.Object(id=gid)
            bot.tree.copy_global_to(guild=guild_obj)
            synced = await bot.tree.sync(guild=guild_obj)
            print(f"Synced {len(synced)} slash commands to guild {gid}.")
        _slash_synced = True
    print("Bot is now ready!")

# Log command usage
@bot.listen()
async def on_command(ctx):
    nickname = ctx.author.nick if ctx.author.nick else ctx.author.display_name
    command_used = ctx.message.content
    time_used = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    channel_name = ctx.channel.name if ctx.channel else "Direct Message"
    print(f"{nickname} used command '{command_used}' in #{channel_name} at {time_used}")

async def main():
    db = Database()
    initialize_database(db)

    # connect to Postgres, make sure timezones table exists...
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print(f"DATABASE_URL from env: {os.getenv('DATABASE_URL')}")
        raise ValueError("DATABASE_URL is not set in the environment!")
    bot.pg_pool = await asyncpg.create_pool(DATABASE_URL)
    await bot.pg_pool.execute("""
        CREATE TABLE IF NOT EXISTS timezones (
            user_id BIGINT PRIMARY KEY,
            timezone TEXT    NOT NULL
        )
    """)

    backoff = 5
    # Attempt to start the bot with exponential backoff on rate-limit
    while True:
        try:
            # load extensions before starting
            await load_extensions()
            await bot.start(TOKEN)
            break  # clean shutdown
        except discord.HTTPException as e:
            if e.status == 429:
                print(f"Rate‑limited on login; sleeping {backoff}s before retry")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300)
            else:
                raise
    db.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down the bot...")
