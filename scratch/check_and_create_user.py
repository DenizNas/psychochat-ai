import sys
import os
import sqlite3

# Adjust sys.path to import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.auth import get_password_hash

DB_PATH = "data/psikochat.db"

def main():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Print all users
    cur.execute("SELECT id, username, email FROM users")
    users = cur.fetchall()
    print("Existing users in DB:")
    for u in users:
        print(u)

    # 2. Check if deniznas or denznas exists
    cur.execute("SELECT id, username, email FROM users WHERE username = 'deniznas' OR username = 'denznas'")
    found = cur.fetchall()
    print("\nMatching users:")
    for f in found:
        print(f)

    # 3. Hash password123
    hashed_pw = get_password_hash("password123")

    # 4. Upsert deniznas@example.com
    # If denznas exists, we can rename/update it or create a new user deniznas
    # Let's check if 'denznas' exists but 'deniznas' does not
    has_denznas = any(u[1] == 'denznas' for u in users)
    has_deniznas = any(u[1] == 'deniznas' for u in users)

    if has_denznas and not has_deniznas:
        print("\nRenaming denznas to deniznas and updating email to deniznas@example.com")
        cur.execute(
            "UPDATE users SET username = 'deniznas', email = 'deniznas@example.com', password_hash = ? WHERE username = 'denznas'",
            (hashed_pw,)
        )
    elif not has_deniznas:
        print("\nInserting new user deniznas / deniznas@example.com")
        cur.execute(
            "INSERT INTO users (username, email, password_hash, full_name) VALUES ('deniznas', 'deniznas@example.com', ?, 'Deniz Nas')",
            (hashed_pw,)
        )
    else:
        print("\nUser deniznas already exists, updating password to password123")
        cur.execute(
            "UPDATE users SET email = 'deniznas@example.com', password_hash = ? WHERE username = 'deniznas'",
            (hashed_pw,)
        )

    # Commit changes
    conn.commit()

    # Verify again
    cur.execute("SELECT id, username, email FROM users")
    print("\nUsers after update:")
    for u in cur.fetchall():
        print(u)

    # Print user profiles too
    cur.execute("SELECT * FROM user_profiles")
    print("\nUser profiles:")
    for p in cur.fetchall():
        print(p)

    conn.close()

if __name__ == "__main__":
    main()
