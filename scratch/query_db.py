import sqlite3

def main():
    conn = sqlite3.connect('data/psikochat.db')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("Tables in database:", tables)
        
        cursor.execute("SELECT * FROM users;")
        users = cursor.fetchall()
        print("Users in database:", users)
    except Exception as e:
        print("Error:", e)
    finally:
        conn.close()

if __name__ == '__main__':
    main()
