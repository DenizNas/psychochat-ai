import sqlite3

db_path = 'c:/Projectss/psikochat-ai/data/psikochat.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

try:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print("Tables:", tables)
    
    if 'users' in tables:
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        print(f"Total users: {len(users)}")
        for user in users:
            print(dict(user))
    else:
        print("No users table found!")
except Exception as e:
    print("Error:", e)
finally:
    conn.close()
