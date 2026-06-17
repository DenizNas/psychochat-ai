import sys
import os
import argparse

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.database import SessionLocal, User
from src.services.auth import get_password_hash
from src.ai.preprocessing import prepare_model_input, turkish_lower

def main():
    parser = argparse.ArgumentParser(description="Reset development user password.")
    parser.add_argument("--identifier", required=True, help="Email or username of the user.")
    parser.add_argument("--password", required=True, help="New password for the user.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        clean_identifier = turkish_lower(args.identifier.strip())
        # Search by email first
        user = db.query(User).filter(User.email == clean_identifier).first()
        if not user:
            # Search by username
            user = db.query(User).filter(User.username == clean_identifier).first()

        if not user:
            print(f"User with identifier '{args.identifier}' not found.")
            sys.exit(1)

        hashed = get_password_hash(args.password)
        user.password_hash = hashed
        db.commit()
        print(f"Successfully updated password for user {user.username} (ID: {user.id})")
    except Exception as e:
        db.rollback()
        print(f"Error resetting password: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
