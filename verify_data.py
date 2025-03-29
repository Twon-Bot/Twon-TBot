import sqlite3

# Connect to the database
conn = sqlite3.connect("bot_data.db")
cursor = conn.cursor()

# Execute a query to select all rows from the google_sheets_mapping table
cursor.execute("SELECT * FROM google_sheets_mapping")
rows = cursor.fetchall()

# Print each row
for row in rows:
    print(row)

# Close the connection
conn.close()
