## Extras I may need later!

# Function to authenticate with Google Sheets API
def authenticate_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS, scope)
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

# (IN-PROGRESS) Function to find the next empty row (starting from row 106)
def get_next_available_row(sheet, start_row=1): # CHAN CHANGE START ROW TO WHATEVER
    col_values = sheet.col_values(1)  # Get all values in the first column
    return max(start_row, len(col_values) + 1)  # Ensures we don't overwrite row 106

### THIS PART HAS SOME UPDATES FROM MORE RECENT CHANGES
# Log when the bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    await load_extensions()  # Load extensions here
    await stop_current_phase()  # Call the function with parentheses
    global sheets_client
    sheets_client = authenticate_google_sheets()  # Authenticate and create the client
    print("Database connection opened.")  # Confirm connection


## MAIN 'ADDED' CODE

@bot.command(name='added')
async def added_command(ctx, username: str = None):
    discord_name = ctx.author.name
    user_id = discord_name
    user_row = None  # Initialize to None

    # Adding this bit for fun to test the time/date function
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Format: YYYY-MM-DD HH:MM:SS

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
        sheet = client.open("Test Bot#2").sheet1
        
        # Get column D values
        column_d_values = sheet.col_values(4)  # Column D (4th column)
        if user_id in column_d_values:
            user_row = column_d_values.index(user_id) + 1  # Convert index to 1-based row number
            in_game_name = sheet.cell(user_row, 3).value  # Column C
            
            print(f"\nRun Time: {timestamp}\nANALYSIS: User '{user_id}' found at row {user_row}. User's in-game name is '{in_game_name}'")

            if user_row is not None:
                update_range_row = user_row + 1  # Determine starting row
                end_row = update_range_row + 48  # 49 rows total
                column_index = get_column_index_for_in_game_name(sheet, in_game_name)
                column_letter = column_index_to_letter(column_index)

                dropdown_cell_range = f"{column_letter}{update_range_row}:{column_letter}{end_row}"  # Adjust range dynamically

                # Overwrite all 49 rows with "Sent" // or "Friend"/"Unfriended"/"Full"
                specific_update_values = [["Sent"] for _ in range(49)]

                # Update Google Sheets
                sheet.update(specific_update_values, range_name=dropdown_cell_range)

                # Don't need this atm  (extra debug message)
                # print(f"Updated range: {dropdown_cell_range}")

                # Don't need this atm (extra debug message)
                # print(f"Final dropdown cell range: {dropdown_cell_range}")  # Debug output

                try:
                    sheet.update(specific_update_values, range_name=dropdown_cell_range)
                    print(f"Updated range: {dropdown_cell_range}\n")
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

# I have removed !unadded temporarily
# @bot.command(name='unadded')
