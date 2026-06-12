import os
import sys

# Ensure backend source is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set env to development so it loads data/psikochat.db
os.environ["APP_ENV"] = "development"

from src.services.database import SessionLocal, User, get_user_by_email
from src.services.auth import get_password_hash

def run():
    email = "deniznas@example.com"
    username = "deniznas"
    password = "password123"
    
    db = SessionLocal()
    try:
        user = db.query(User).filter((User.email == email) | (User.username == username)).first()
        if user:
            print("User already exists in DB:")
            print(f"ID: {user.id}, Username: {user.username}, Email: {user.email}, Full Name: {user.full_name}, Password Hash: {user.password_hash}")
            # If the user password hash needs to be updated to password123, do it:
            hashed = get_password_hash(password)
            user.password_hash = hashed
            user.email = email
            user.username = username
            user.full_name = "Deniz Nas"
            db.commit()
            print("Updated user password and details to match expected.")
        else:
            hashed = get_password_hash(password)
            new_user = User(
                username=username,
                email=email,
                full_name="Deniz Nas",
                password_hash=hashed,
                role="user"
            )
            db.add(new_user)
            db.commit()
            print("Successfully created user deniznas@example.com!")
    except Exception as e:
        db.rollback()
        print("Error:", e)
    finally:
        db.close()

if __name__ == "__main__":
    run()
