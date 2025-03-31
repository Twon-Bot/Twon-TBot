import discord
import sqlite3
import os
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN2")
if not TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN2 environment variable not set.")

# Set up the bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!!", intents=intents, case_insensitive=True, help_command=None)

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
        print("AnnouncementCog has been loaded.")  # Ensure this prints when loaded

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
@commands.has_any_role('Moderator', 'Manager', 'Server Owner', 'Police')
async def gettimezone(ctx):
    user_timezone = None

    with sqlite3.connect("bot_data.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT timezone FROM user_timezones WHERE user_id = ?", (ctx.author.id,))
        result = cursor.fetchone()
        user_timezone = result[0] if result else None

    if user_timezone:
        await ctx.send(f"Your current timezone is set to: {user_timezone}.")
    else:
        await ctx.send("You have not set a timezone yet. Use `!settimezone <timezone>` to set it.")

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
    await bot.tree.sync()  # Sync slash commands
    print("Bot is now ready!")

# Show who uses which command in powershells
@bot.listen()
async def on_command(ctx):
    # Get the server nickname if available; if not, use the display name.
    nickname = ctx.author.nick if ctx.author.nick else ctx.author.display_name
    # Get the command that was used (the full message content will show the !! command and arguments)
    command_used = ctx.message.content
    # Get the current time (you can adjust the format or timezone as needed)
    time_used = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Get the channel name
    channel_name = ctx.channel.name if ctx.channel else "Direct Message"
    
    print(f"{nickname} used command '{command_used}' in #{channel_name} at {time_used}")

async def main():
    db = Database()
    initialize_database(db)

    try:
        async with bot:
            await load_extensions()  # Load before starting
            await bot.start(TOKEN)
            await asyncio.Future()  # Keep the bot running
    finally:
        db.close()

if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Shutting down the bot...")
    finally:
        loop.close()
