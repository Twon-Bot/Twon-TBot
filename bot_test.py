import discord
import sqlite3
import os
# import gspread  # FOR Google Sheets implementation
import asyncio
from oauth2client.service_account import ServiceAccountCredentials
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN2")
if not TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN2 environment variable not set.")
CREDS = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH2")

# Set up the bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)  # Remove help_command=None

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
        print("AnnouncementCog has been loaded.") # Ensure this prints when loaded

    @commands.command(name='myhelp')
    async def myhelp(self, ctx, category: str = None):
        await ctx.send("MyHelp command is working!")

        if category is None:
            help_message = ("**Available Help Commands:**\n"
                            "- `!help announce` → List available announcements\n"
                            "- `!help schedule` → Show schedule commands\n"
                            "- `!help settimezone` → Change timezone setting\n"
                            "- `!help gettimezone` → Get current timezone setting\n"
                            "*Example: `!help announce`*")
            await ctx.send(help_message)
            return

        if category.lower() == "announce":
            await self.send_announce_help(ctx)
        elif category.lower() == "schedule":
            await ctx.send("**Schedule Commands:**\n"
                        "- `!resetschedule` → Set a new schedule\n"
                        "- `!currentschedule` → View the current schedule\n")
        elif category.lower() == "settimezone":
            await ctx.send("**Set Timezone Command:**\n"
                        "- `!settimezone <timezone>` → Set your timezone (e.g., `!settimezone UTC+2`)\n"
                        "Use `!gettimezone` to check your current timezone.")
        elif category.lower() == "gettimezone":
            await ctx.send("**Get Timezone Command:**\n"
                        "- `!gettimezone` → Displays the currently set timezone.")
        else:
            await ctx.send(f"Unknown help category `{category}`. Try `!help` for options.")

    async def send_announce_help(self, ctx):
        try:
            with open('announcements.txt', 'r', encoding='utf-8') as file:
                content = file.read()
                announcements = content.split('===')
                available_announcements = [lines[0].strip() for lines in (a.strip().splitlines() for a in announcements) if lines]

                help_message = "**Input format example:**\n*!announce Announcement1*\n\n**Available Announcements:**\n - " + "\n - ".join(available_announcements)
                await ctx.send(help_message)
        except Exception as e:
            await ctx.send(f'An error occurred while reading the announcements: {str(e)}')

    @commands.command()
    async def announce(self, ctx, *, message: str):
        # Create a confirmation message
        confirmation_msg = await ctx.send("React with 👍 to confirm this announcement to @everyone.")

        # Add a thumbs-up reaction for confirmation
        await confirmation_msg.add_reaction("👍")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == "👍" and reaction.message.id == confirmation_msg.id

        try:
            # Wait for the reaction from the user
            await self.bot.wait_for('reaction_add', check=check, timeout=30)  # Wait for 30 seconds
            await ctx.send(f"@everyone {message}")  # Send the announcement if confirmed
        except asyncio.TimeoutError:
            await ctx.send("Announcement confirmation timed out. Please try again.")

@bot.command()
async def gettimezone(ctx):
    """Fetch and display the user's timezone setting."""
    # Fetch the user's timezone from the database
    user_timezone = None

    with sqlite3.connect("bot_data.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT timezone FROM user_timezones WHERE user_id = ?", (ctx.author.id,))
        result = cursor.fetchone()
        user_timezone = result[0] if result else None  # Get the timezone or None if not set

    if user_timezone:
        await ctx.send(f"Your current timezone is set to: {user_timezone}.")
    else:
        await ctx.send("You have not set a timezone yet. Use `!settimezone <timezone>` to set it.")

async def load_extensions():
    print("Loading extensions...")  # Debug print
    try:
        await bot.load_extension('announce')  # Load announce.py
        print("Loaded announce extension.")
        await bot.load_extension('schedule')   # Load schedule.py
        print("Loaded schedule extension.")
        print("Extensions loaded successfully.")  # Debug print
        print("Registered commands:", [cmd.name for cmd in bot.commands])  # Print command names
    except Exception as e:
        print(f'Failed to load extension: {e}')

# SAVING THIS because I might need that current_time part
#@bot.event
#async def on_ready():
#    current_time = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
#    print(f'[{current_time}] \nLogged in as {bot.user}!')
#################################

# Handle unknown commands
@bot.event
async def on_command_error(ctx, error):
    print(f"Command error: {error}")  # Log the error for debugging
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"Unknown command. Use `!help` to see available commands.")
    else:
        raise error  # Keeps other errors intact

########################
@bot.command()
async def test(ctx):
    await ctx.send("Test command is working!")  # Simple test command

# Log when the bot is ready
@bot.event
async def on_ready():
    print("Bot is now ready!")
#    await load_extensions()  # Ensures extensions load after login
#    print("All extensions have been loaded.")

# Create an async main function to run the bot
async def main():
    db = Database()
    initialize_database(db)  # Initialize the database

    try:
        async with bot:
            await load_extensions()  # Load extensions before bot starts
            print("All extensions have been loaded.")  # My Inclusion
            await bot.start(TOKEN)  # Start bot properly inside async function
    finally:
        db.close()  # Ensure the database closes properly even if an error occurs
        print("Database connection closed.")
    
# Start the bot asynchronously
if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Shutting down the bot...")
    finally:
        loop.close()
