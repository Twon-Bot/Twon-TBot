import discord
import sqlite3
import os
import gspread
import time
from oauth2client.service_account import ServiceAccountCredentials
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Set up the bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Function to authenticate with Google Sheets API
def authenticate_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('C:\\sqlite\\discoord-bot-sqlite-530949af8e55.json', scope)
    client = gspread.authorize(creds)
    return client

# Function to convert a column index (1-based) to its corresponding letter in Excel/Google Sheets
def column_index_to_letter(index):
    """Convert a column index (1-based) to its corresponding letter in Excel/Google Sheets."""
    letter = ''
    while index > 0:
        index -= 1
        letter = chr(index % 26 + 65) + letter  # Convert to letter (A=65)
        index //= 26
    return letter

# Global database connection variable
conn = None

# Function to get a database connection
def get_db_connection():
    global conn  # Use the global conn variable
    conn = sqlite3.connect("bot_data.db")
    return conn

# Function to insert commands into the database
def insert_command(user_id, command, argument):
    conn = get_db_connection()  # Get a new database connection
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO discord_inputs (user_id, command, argument) VALUES (?, ?, ?)", (user_id, command, argument))
        conn.commit()
        print(f'Inserted command: {command} from user {user_id}')  # Debug output
    except Exception as e:
        print(f"An error occurred while inserting command: {str(e)}")  # Log the error
    finally:
        conn.close()  # Ensure the connection is closed after the operation

# Log when the bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!') 
    global sheets_client
    sheets_client = authenticate_google_sheets()  # Authenticate and create the client
    print("Database connection opened.")  # Confirm connection

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith('!'):
        parts = message.content.split()
        command = parts[0][1:]  # Remove "!"
        argument = parts[1] if len(parts) > 1 else None

        # Insert command into SQLite
        insert_command(message.author.id, command, argument)

        # Send confirmation message
        await message.channel.send(f'Command "{command}" with argument "{argument}" received and stored!')

    await bot.process_commands(message)

@bot.command(name='updateStatus')
async def update_status(ctx, status: str):
    insert_command(ctx.author.id, 'updateStatus', status)
    await ctx.send(f'Status updated to: {status}')

@bot.command(name='setPriority')
async def set_priority(ctx, priority: str):
    insert_command(ctx.author.id, 'setPriority', priority)
    await ctx.send(f'Priority set to: {priority}')

@bot.command(name='assignUser')
async def assign_user(ctx, user: str):
    insert_command(ctx.author.id, 'assignUser', user)
    await ctx.send(f'Task assigned to: {user}')

@bot.command(name='announce')
@commands.has_role('Moderator')  # Allow access to users with the 'moderator' role
async def announce(ctx, *, message: str):
    announcement_channel = discord.utils.get(ctx.guild.text_channels, name='announcements')  # Change 'announcements' to your channel name
    if announcement_channel:
        await announcement_channel.send(message)
        await ctx.send(f'Announcement sent: {message}')
    else:
        await ctx.send('Announcement channel not found.')

@bot.command(name='added')
async def added_command(ctx, username: str = None):
    discord_name = ctx.author.name
    user_id = discord_name
    user_row = None  # Initialize to None

    if username:
        guild = ctx.guild
        user = next((member for member in guild.members if member.name == username or member.display_name == username), None)
        if user:
            user_id = user.name
        else:
            await ctx.send(f'User {username} not found in this guild.')
            return

    try:
        client = authenticate_google_sheets()
        sheet = client.open("Test SQLite PTCGP Copy").sheet1
        
        # Get column D values
        column_d_values = sheet.col_values(4)  # Column D (4th column)
        if user_id in column_d_values:
            user_row = column_d_values.index(user_id) + 1  # Convert index to 1-based row number
            in_game_name = sheet.cell(user_row, 3).value  # Column C
            
            print(f"DEBUG: User {user_id} found at row {user_row}, in-game name: {in_game_name}")

            if user_row is not None:
                update_range_row = user_row + 1  # Determine starting row
                end_row = update_range_row + 48  # 49 rows total
                column_index = get_column_index_for_in_game_name(sheet, in_game_name)
                column_letter = column_index_to_letter(column_index)

                dropdown_cell_range = f"{column_letter}{update_range_row}:{column_letter}{end_row}"  # Adjust range dynamically

                # Overwrite all 49 rows with "Sent"
                specific_update_values = [["Sent"] for _ in range(49)]

                # Update Google Sheets
                sheet.update(specific_update_values, range_name=dropdown_cell_range)

                print(f"Updated range: {dropdown_cell_range}")


                print(f"Final dropdown cell range: {dropdown_cell_range}")  # Debug output

                try:
                    sheet.update(specific_update_values, range_name=dropdown_cell_range)
                    print(f"Updated range: {dropdown_cell_range}")
                    await ctx.send(f'{discord_name}, your dropdowns have been updated.')
                except Exception as e:
                    print(f"Update error: {str(e)}")
                    await ctx.send(f'Error updating Google Sheets: {str(e)}')

            else:
                await ctx.send(f'Error: user_row is None before updating range.')

        else:
            await ctx.send(f'User {discord_name} not found in the sheet.')

    except Exception as e:
        print(f"ERROR: Google Sheets error: {str(e)}")
        await ctx.send(f'Google Sheets error: {str(e)}')

def get_column_index_for_in_game_name(sheet, in_game_name):
    """Get the column index in the sheet where the in-game name is located."""
    column_bo_values = sheet.row_values(2)  # Get the values from the second row (header)
    try:
        return column_bo_values.index(in_game_name) + 1  # Adjust for the correct starting column (G=7)
    except ValueError:
        return None  # Return None if the in-game name is not found

# Assume 'user_row' is defined earlier in your code

@bot.command(name='unadded')
async def unadded_command(ctx):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM discord_inputs WHERE command = 'added'")
    added_users = {row[0] for row in cursor.fetchall()}
    
    # Assuming you have a way to get all users in the server
    all_users = {member.id: member.name for member in ctx.guild.members}
    
    unadded_users = [name for user_id, name in all_users.items() if user_id not in added_users]
    
    if unadded_users:
        await ctx.send(f'Users who have not used !added: {", ".join(unadded_users)}')
    else:
        await ctx.send('All users have used the !added command.')
    
    conn.close()

@bot.command(name='reset')
@commands.has_role('Spreadsheet-Master')
async def reset_command(ctx):
    try:
        client = authenticate_google_sheets()
        sheet = client.open("Test SQLite PTCGP Copy").sheet1

        # Reset all dropdowns (G3 to DA101) to "Unfriended"
        for row in range(3, 102):
            for col in range(7, 106):
                sheet.update_cell(row, col, "Unfriended")

        # Clear previous entries in the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM discord_inputs")
        conn.commit()
        conn.close()

        await ctx.send('All dropdowns have been reset to "Unfriended" and unadded counts cleared.')

    except Exception as e:
        await ctx.send(f'An error occurred while resetting the dropdowns: {str(e)}')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("You do not have permission to use this command.")
    else:
        await ctx.send(f"Error: {error}")

# Run the bot
try:
    bot.run(TOKEN)
finally:
    if conn:
        conn.close()  # Only close if conn is defined
    print("Database connection closed.")  # Debug output
