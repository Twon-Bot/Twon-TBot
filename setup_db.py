import sqlite3

# Database file name
DB_NAME = "bot_data.db"

# Connect to SQLite (creates the file if it doesn't exist)
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# Create table: discord_inputs
cursor.execute("""
    CREATE TABLE IF NOT EXISTS discord_inputs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

# Create table: google_sheets_mapping
cursor.execute("""
    CREATE TABLE IF NOT EXISTS google_sheets_mapping (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command TEXT NOT NULL UNIQUE,
        sheet_column TEXT NOT NULL,
        dropdown_value TEXT
    )
""")

# Insert command mappings
mappings = [
    ("!updateStatus", "Status", "Pending,Completed,In Progress"),
    ("!setPriority", "Priority", "High,Medium,Low")
]

# Insert data into google_sheets_mapping
for command, sheet_column, dropdown_value in mappings:
    cursor.execute("""
        INSERT OR IGNORE INTO google_sheets_mapping (command, sheet_column, dropdown_value)
        VALUES (?, ?, ?)
    """, (command, sheet_column, dropdown_value))

# Commit and close connection
conn.commit()
conn.close()

print(f"Database '{DB_NAME}' and tables created successfully with command mappings!")
