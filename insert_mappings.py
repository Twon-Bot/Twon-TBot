import sqlite3
import json

# Connect to the database
conn = sqlite3.connect("bot_data.db")
cursor = conn.cursor()

# Drop the existing google_sheets_mapping table if it exists
cursor.execute("DROP TABLE IF EXISTS google_sheets_mapping")

# Create table: google_sheets_mapping
cursor.execute("""
    CREATE TABLE IF NOT EXISTS google_sheets_mapping (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command TEXT NOT NULL UNIQUE,
        sheet_column TEXT NOT NULL,
        valid_values TEXT  -- Ensure this column matches the insert statement
    )
""")

# Sample mappings of commands to Google Sheets columns and valid dropdown values
mappings = [
    ("!updateStatus", "Status", json.dumps(["Pending", "Completed", "In Progress"])),
    ("!setPriority", "Priority", json.dumps(["High", "Medium", "Low"])),
    ("!assignUser", "Assigned To", json.dumps(["Alice", "Bob", "Charlie"]))
]

# Insert the mappings into the table
cursor.executemany("INSERT OR IGNORE INTO google_sheets_mapping (command, sheet_column, valid_values) VALUES (?, ?, ?)", mappings)

# Commit and close
conn.commit()
conn.close()

print("Sample mappings inserted into SQLite.")
