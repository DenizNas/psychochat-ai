import os
import sys
import argparse

# Ensure src module can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings
from src.services.database import init_db, SessionLocal, User, PsychologistProfile
from src.services.auth import get_password_hash, verify_password

def run_stabilization(report_only=False):
    print("======================================================================")
    print("PSIKOCHAT DEVELOPMENT DATABASE STABILIZATION & REPAIR SCRIPT")
    print("======================================================================")
    print(f"Active SQLite Database URL: {settings.DATABASE_URL}")
    print("======================================================================")
    
    # Run standard DB initialization/schema migrations first (does not erase anything)
    if not report_only:
        init_db()
        print("Schema migrations checked and completed.")
        print("----------------------------------------------------------------------")
        
    db = SessionLocal()
    try:
        # Report current users before any changes
        print("CURRENT USER ACCOUNTS IN DATABASE:")
        users = db.query(User).all()
        for u in users:
            pwd_match = "Yes" if verify_password("password123", u.password_hash) or (u.username == "admin" and verify_password("psiko_secret123", u.password_hash)) else "No/Custom"
            print(f" - ID: {u.id:2d} | Username: {u.username:20s} | Email: {str(u.email):30s} | Role: {u.role:12s} | Pwd matches default: {pwd_match}")
        print("----------------------------------------------------------------------")
        
        # Report current psychologist profiles before any changes
        print("CURRENT PSYCHOLOGIST PROFILES:")
        profiles = db.query(PsychologistProfile).all()
        for p in profiles:
            user = db.query(User).filter(User.id == p.user_id).first()
            username = user.username if user else "ORPHANED!"
            full_name = user.full_name if user else "N/A"
            role = user.role if user else "N/A"
            print(f" - User ID: {p.user_id:2d} | Username: {username:15s} | Name: {full_name:18s} | User Role: {role:12s} | Title: {p.title:15s} | Status: {p.status}")
        print("----------------------------------------------------------------------")
        
        if report_only:
            print("Report-only mode. No repairs or seeds were performed.")
            return

        print("PERFORMING DATABASE STABILIZATION AND REPAIRS...")
        actions = []

        # 1. Enforce admin user credentials
        admin = db.query(User).filter(User.username == "admin").first()
        hashed_admin_pw = get_password_hash("psiko_secret123")
        if not admin:
            admin = User(username="admin", email="admin", full_name="Admin", role="admin", password_hash=hashed_admin_pw)
            db.add(admin)
            actions.append("Created admin user.")
        else:
            updated = False
            if admin.email != "admin":
                admin.email = "admin"
                updated = True
            if admin.role != "admin":
                admin.role = "admin"
                updated = True
            if not verify_password("psiko_secret123", admin.password_hash):
                admin.password_hash = hashed_admin_pw
                updated = True
            if updated:
                actions.append("Reset/updated admin user credentials to defaults.")

        # 2. Enforce deniz user credentials
        deniz = db.query(User).filter(User.email == "denizdennasnas@gmail.com").first()
        hashed_deniz_pw = get_password_hash("password123")
        if not deniz:
            deniz = User(username="deniz", email="denizdennasnas@gmail.com", full_name="Deniz Nas", role="user", password_hash=hashed_deniz_pw)
            db.add(deniz)
            actions.append("Created demo user denizdennasnas@gmail.com.")
        else:
            updated = False
            if deniz.username != "deniz":
                deniz.username = "deniz"
                updated = True
            if deniz.role != "user":
                deniz.role = "user"
                updated = True
            if not verify_password("password123", deniz.password_hash):
                deniz.password_hash = hashed_deniz_pw
                updated = True
            if updated:
                actions.append("Reset demo user 'deniz' password to 'password123'.")

        # 3. Clean up orphaned profiles or profiles linked to non-psychologists/mock test users
        # Wait, the rule says: "Do not delete real user data. Only clean orphaned psychologist profiles, testuser_ records, stale demo data, and clearly invalid mappings."
        # So we only delete psychologist profiles belonging to non-psychologists, testusers, or orphans.
        cleaned_profiles = 0
        cleaned_users = 0
        all_profiles = db.query(PsychologistProfile).all()
        for p in all_profiles:
            u = db.query(User).filter(User.id == p.user_id).first()
            should_delete_profile = False
            if not u:
                should_delete_profile = True
                actions.append(f"Deleted orphaned PsychologistProfile for missing User ID {p.user_id}.")
            elif u.role != "psychologist":
                should_delete_profile = True
                actions.append(f"Deleted invalid PsychologistProfile for User ID {p.user_id} (Role is {u.role}).")
            elif "testuser_" in u.username.lower() or "patient_" in u.username.lower():
                should_delete_profile = True
                actions.append(f"Deleted PsychologistProfile for mock user {u.username}.")
                # Also delete the mock user itself to clean up
                db.delete(u)
                cleaned_users += 1
                actions.append(f"Deleted mock test user: {u.username}")
            
            if should_delete_profile:
                db.delete(p)
                cleaned_profiles += 1

        # 4. Clean up any remaining testuser_ or patient_ records from the users table
        all_users = db.query(User).all()
        for u in all_users:
            if "testuser_" in u.username.lower() or "patient_" in u.username.lower():
                db.delete(u)
                cleaned_users += 1
                actions.append(f"Deleted mock test user: {u.username}")

        # 5. Seed default approved psychologists with real names
        default_psychologists = [
            {
                "username": "antepogullari",
                "email": "antepogullari@gmail.com",
                "full_name": "Betül Akarçay",
                "title": "Doçent Psikolog",
                "specialty": "Bilişsel Terapi",
                "bio": "Merhaba, ben Doçent Psikolog Betül Akarçay. Bilişsel davranışçı terapi alanında uzmanım.",
                "status": "approved"
            },
            {
                "username": "ahmet_yilmaz",
                "email": "ahmet_yilmaz@example.com",
                "full_name": "Ahmet Yılmaz",
                "title": "Uzm. Psk.",
                "specialty": "Kaygı",
                "bio": "Merhaba, ben Uzman Psikolog Ahmet Yılmaz. Kaygı bozuklukları ve panik atak üzerinde çalışıyorum.",
                "status": "approved"
            }
        ]
        
        for psy_data in default_psychologists:
            u = db.query(User).filter(User.username == psy_data["username"]).first()
            if not u:
                u = User(
                    username=psy_data["username"],
                    password_hash=hashed_deniz_pw,
                    email=psy_data["email"],
                    full_name=psy_data["full_name"],
                    role="psychologist"
                )
                db.add(u)
                db.flush()
                actions.append(f"Seeded psychologist user: {psy_data['username']}")
            else:
                u.role = "psychologist"
                u.full_name = psy_data["full_name"]
                u.email = psy_data["email"]
                if not verify_password("password123", u.password_hash):
                    u.password_hash = hashed_deniz_pw
                    actions.append(f"Reset password for psychologist: {psy_data['username']}")
            
            p = db.query(PsychologistProfile).filter(PsychologistProfile.user_id == u.id).first()
            if not p:
                p = PsychologistProfile(
                    user_id=u.id,
                    title=psy_data["title"],
                    specialty=psy_data["specialty"],
                    bio=psy_data["bio"],
                    status=psy_data["status"]
                )
                db.add(p)
                actions.append(f"Seeded approved profile for psychologist: {psy_data['username']}")
            else:
                p.title = psy_data["title"]
                p.specialty = psy_data["specialty"]
                p.bio = psy_data["bio"]
                p.status = psy_data["status"]

        db.commit()
        print("DATABASE REPAIRS COMPLETED SUCCESSFULLY.")
        if actions:
            print("Actions performed:")
            for act in actions:
                print(f" - {act}")
        else:
            print(" - None (Database already stable).")
        print("----------------------------------------------------------------------")
        
        # Print final state
        print("FINAL USER ACCOUNTS IN DATABASE:")
        final_users = db.query(User).all()
        for u in final_users:
            pwd_match = "Yes" if verify_password("password123", u.password_hash) or (u.username == "admin" and verify_password("psiko_secret123", u.password_hash)) else "No/Custom"
            print(f" - ID: {u.id:2d} | Username: {u.username:20s} | Email: {str(u.email):30s} | Role: {u.role:12s} | Pwd matches default: {pwd_match}")
            
    except Exception as e:
        db.rollback()
        print(f"Error during database repair: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()
    print("======================================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PsikoChat DB Stabilization Tool")
    parser.add_argument("--report", action="store_true", help="Print report of database and take no actions")
    args = parser.parse_args()
    run_stabilization(report_only=args.report)
