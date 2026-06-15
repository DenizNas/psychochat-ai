import unittest
from fastapi.testclient import TestClient
from src.api.main import app
from src.core.config import settings
from src.services.database import (
    init_db,
    SessionLocal,
    User,
    UserProfile,
    PsychologistProfile,
    Appointment,
    PsychologistAvailability
)
import base64
from datetime import datetime, timedelta
from src.services.intervention_scheduler import ISTANBUL_TZ

class TestAvailabilityAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        from src.core.redis_client import redis_client
        type(redis_client).client = property(lambda self: None)
        cls.original_rate_limit = settings.RATE_LIMIT_ENABLED
        settings.RATE_LIMIT_ENABLED = False

    @classmethod
    def tearDownClass(cls):
        settings.RATE_LIMIT_ENABLED = cls.original_rate_limit

    def setUp(self):
        db = SessionLocal()
        try:
            db.query(Appointment).delete()
            db.query(PsychologistAvailability).delete()
            db.query(PsychologistProfile).delete()
            db.query(UserProfile).delete()
            db.query(User).delete()
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def test_availability_and_booking_flow(self):
        client = TestClient(app)

        # Register normal user
        res = client.post("/register", json={
            "username": "user1",
            "password": "password123",
            "email": "user1@example.com",
            "full_name": "Normal User",
            "role": "user"
        })
        self.assertEqual(res.status_code, 201)
        token_res = client.post("/login", json={"email": "user1@example.com", "password": "password123"})
        user_headers = {"Authorization": f"Bearer {token_res.json()['access_token']}"}

        # Register psychologist 1
        res = client.post("/register", json={
            "username": "psy1",
            "password": "password123",
            "email": "psy1@example.com",
            "full_name": "Dr. Freud",
            "role": "psychologist",
            "title": "Dr. Psk.",
            "specialty": "Rüya Analizi",
            "bio": "Merhaba, rüya analizi konusunda uzmanım."
        })
        self.assertEqual(res.status_code, 201)
        token_res = client.post("/login", json={"email": "psy1@example.com", "password": "password123"})
        psy1_headers = {"Authorization": f"Bearer {token_res.json()['access_token']}"}

        # Register psychologist 2
        res = client.post("/register", json={
            "username": "psy2",
            "password": "password123",
            "email": "psy2@example.com",
            "full_name": "Dr. Jung",
            "role": "psychologist",
            "title": "Dr. Psk.",
            "specialty": "Analitik Psikoloji",
            "bio": "Merhaba, analitik psikoloji üzerine uzmanım."
        })
        self.assertEqual(res.status_code, 201)
        token_res = client.post("/login", json={"email": "psy2@example.com", "password": "password123"})
        psy2_headers = {"Authorization": f"Bearer {token_res.json()['access_token']}"}

        # 1. Normal user cannot create availability
        res = client.post("/psychologists/me/availability", json={
            "day_of_week": 0,
            "start_time": "09:00",
            "end_time": "12:00",
            "slot_duration_minutes": 60
        }, headers=user_headers)
        self.assertEqual(res.status_code, 403)

        # 2. Psychologist can create availability
        res = client.post("/psychologists/me/availability", json={
            "day_of_week": 0, # Monday
            "start_time": "09:00",
            "end_time": "12:00",
            "slot_duration_minutes": 60
        }, headers=psy1_headers)
        self.assertEqual(res.status_code, 201)
        psy1_av = res.json()
        self.assertEqual(psy1_av["day_of_week"], 0)
        self.assertEqual(psy1_av["start_time"], "09:00")
        self.assertEqual(psy1_av["end_time"], "12:00")
        
        # Get psychologist 1's ID from database
        db = SessionLocal()
        psy1_db = db.query(User).filter(User.username == "psy1").first()
        psy1_id = psy1_db.id
        db.close()

        # 3. Pending psychologist slots should not be exposed
        res = client.get(f"/psychologists/{psy1_id}/available-slots?date=2026-06-22", headers=user_headers) # Monday
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["slots"]), 0) # Should be empty list because not approved

        # Approve psychologist 1
        auth_str = base64.b64encode(b"admin:psiko_secret123").decode("utf-8")
        admin_headers = {"Authorization": f"Basic {auth_str}"}
        res = client.post("/admin/psychologists/psy1/approve", headers=admin_headers)
        self.assertEqual(res.status_code, 200)

        # 4. Slots generated correctly for approved psychologist
        res = client.get(f"/psychologists/{psy1_id}/available-slots?date=2026-06-22", headers=user_headers) # Monday
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["psychologist_id"], psy1_id)
        slots = data["slots"]
        # 09:00-12:00 with 60 mins => 09:00, 10:00, 11:00
        self.assertEqual(len(slots), 3)
        self.assertEqual(slots[0]["time"], "09:00")
        self.assertEqual(slots[1]["time"], "10:00")
        self.assertEqual(slots[2]["time"], "11:00")

        # 5. Overlapping availability block should be rejected
        res = client.post("/psychologists/me/availability", json={
            "day_of_week": 0,
            "start_time": "11:00",
            "end_time": "13:00",
            "slot_duration_minutes": 60
        }, headers=psy1_headers)
        self.assertEqual(res.status_code, 400) # Bad Request due to overlap validation

        # 6. Psychologist cannot edit/delete another psychologist's availability
        # psy2 tries to edit psy1's availability
        res = client.put(f"/psychologists/me/availability/{psy1_av['id']}", json={
            "start_time": "10:00"
        }, headers=psy2_headers)
        self.assertEqual(res.status_code, 400) # Forbidden / Bad Request

        # psy2 tries to delete psy1's availability
        res = client.delete(f"/psychologists/me/availability/{psy1_av['id']}", headers=psy2_headers)
        self.assertEqual(res.status_code, 400) # Forbidden / Bad Request

        # 7. Book slot & check slot disappears
        # Book "10:00" slot
        book_res = client.post("/appointments", json={
            "psychologist_username": "psy1",
            "appointment_date": "2026-06-22",
            "appointment_time": "10:00"
        }, headers=user_headers)
        self.assertEqual(book_res.status_code, 201)
        appt_id = book_res.json()["id"]

        # Check available slots again -> "10:00" should be gone
        res = client.get(f"/psychologists/{psy1_id}/available-slots?date=2026-06-22", headers=user_headers)
        self.assertEqual(res.status_code, 200)
        slots = res.json()["slots"]
        self.assertEqual(len(slots), 2)
        self.assertEqual(slots[0]["time"], "09:00")
        self.assertEqual(slots[1]["time"], "11:00")

        # 8. Same slot booking/double booking must be rejected
        res = client.post("/appointments", json={
            "psychologist_username": "psy1",
            "appointment_date": "2026-06-22",
            "appointment_time": "10:00"
        }, headers=user_headers)
        self.assertEqual(res.status_code, 400) # Already booked

        # 9. Booking outside availability must be rejected
        res = client.post("/appointments", json={
            "psychologist_username": "psy1",
            "appointment_date": "2026-06-22",
            "appointment_time": "12:00"
        }, headers=user_headers)
        self.assertEqual(res.status_code, 400)

        # 10. Cancel slot & check slot becomes available again
        cancel_res = client.put(f"/appointments/{appt_id}/cancel", headers=user_headers)
        self.assertEqual(cancel_res.status_code, 200)

        res = client.get(f"/psychologists/{psy1_id}/available-slots?date=2026-06-22", headers=user_headers)
        slots = res.json()["slots"]
        self.assertEqual(len(slots), 3) # Back to 3 slots: 09:00, 10:00, 11:00
