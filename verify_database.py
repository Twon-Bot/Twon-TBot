import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect("bot_data.db")
cursor = conn.cursor()

# Query the discord_inputs table
cursor.execute("SELECT * FROM discord_inputs")
rows = cursor.fetchall()

# Print out each row in the table
for row in rows:
    print(row)

# Close the connection
conn.close()
