import sqlite3
import bcrypt

def check_user():
    conn = sqlite3.connect('data/psikochat.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, password_hash, email, role FROM users')
    rows = cursor.fetchall()
    print("Database users:")
    for row in rows:
        uid, username, pwd_hash, email, role = row
        print(f"ID: {uid}, Username: {username}, Email: {email}, Role: {role}")
        print(f"  Hash: {pwd_hash} (len={len(pwd_hash) if pwd_hash else 0})")
        if pwd_hash:
            try:
                matches_pwd123 = bcrypt.checkpw('password123'.encode('utf-8'), pwd_hash.encode('utf-8'))
                print(f"  Matches 'password123': {matches_pwd123}")
                if username == "admin":
                    matches_admin = bcrypt.checkpw('psiko_secret123'.encode('utf-8'), pwd_hash.encode('utf-8'))
                    print(f"  Matches 'psiko_secret123': {matches_admin}")
            except Exception as e:
                print(f"  Bcrypt check error: {e}")
    conn.close()

if __name__ == "__main__":
    check_user()
