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
    PsychologistAvailability,
    Appointment
)
import base64

class TestAppointmentAPI(unittest.TestCase):

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

    def test_appointment_booking_flow(self):
        client = TestClient(app)

        # 1. Register a user (patient)
        user_payload = {
            "username": "patient_user",
            "password": "password123",
            "email": "patient@example.com",
            "full_name": "Test Patient",
            "role": "user"
        }
        res = client.post("/register", json=user_payload)
        self.assertEqual(res.status_code, 201)

        # Log in as patient
        login_res = client.post("/login", json={"email": "patient@example.com", "password": "password123"})
        self.assertEqual(login_res.status_code, 200)
        user_token = login_res.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}

        # 2. Register a pending psychologist
        psy_payload = {
            "username": "psy_user",
            "password": "password123",
            "email": "psy@example.com",
            "full_name": "Dr. Therapist",
            "role": "psychologist",
            "title": "Uzm. Psk.",
            "specialty": "Kaygı",
            "bio": "Merhaba, ben uzman klinik psikoloğum ve bu biyografi en az 20 karakterdir."
        }
        res = client.post("/register", json=psy_payload)
        self.assertEqual(res.status_code, 201)

        # Log in as psychologist
        login_res_psy = client.post("/login", json={"email": "psy@example.com", "password": "password123"})
        self.assertEqual(login_res_psy.status_code, 200)
        psy_token = login_res_psy.json()["access_token"]
        psy_headers = {"Authorization": f"Bearer {psy_token}"}

        # 3. Try to book appointment with PENDING psychologist (should fail)
        book_payload = {
            "psychologist_username": "psy_user",
            "appointment_date": "2026-07-20",
            "appointment_time": "14:00"
        }
        res = client.post("/appointments", json=book_payload, headers=user_headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Psikolog henüz onaylanmamış", res.json()["message"])

        # 4. Approve the psychologist
        auth_str = base64.b64encode(b"admin:psiko_secret123").decode("utf-8")
        admin_headers = {"Authorization": f"Basic {auth_str}"}
        res = client.post("/admin/psychologists/psy_user/approve", headers=admin_headers)
        self.assertEqual(res.status_code, 200)

        # 4.5. Set availability for Monday 14:00
        res = client.post("/psychologists/me/availability", json={
            "day_of_week": 0, # Monday
            "start_time": "13:00",
            "end_time": "15:00",
            "slot_duration_minutes": 60
        }, headers=psy_headers)
        self.assertEqual(res.status_code, 201)

        # 5. Book appointment with APPROVED psychologist (should succeed)
        res = client.post("/appointments", json=book_payload, headers=user_headers)
        self.assertEqual(res.status_code, 201)
        appt_data = res.json()
        self.assertEqual(appt_data["status"], "scheduled")
        self.assertEqual(appt_data["appointment_date"], "2026-07-20")
        self.assertEqual(appt_data["appointment_time"], "14:00")
        self.assertEqual(appt_data["psychologist_name"], "Dr. Therapist")
        appt_id = appt_data["id"]

        # 6. Try to book appointment when logged in as psychologist (should fail)
        res = client.post("/appointments", json=book_payload, headers=psy_headers)
        self.assertEqual(res.status_code, 403) # Forbidden

        # 7. Check GET /appointments for patient (user sees own appointments, no patient_email)
        res = client.get("/appointments", headers=user_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)
        self.assertEqual(res.json()[0]["psychologist_name"], "Dr. Therapist")
        self.assertIsNone(res.json()[0].get("patient_email"))

        # 8. Check GET /appointments for psychologist (psychologist sees assigned appointments and patient_email)
        res = client.get("/appointments", headers=psy_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)
        self.assertEqual(res.json()[0]["patient_name"], "Test Patient")
        self.assertEqual(res.json()[0]["patient_email"], "patient@example.com")

        # 9. Register & approve a second psychologist to verify isolation
        psy2_payload = {
            "username": "psy_user2",
            "password": "password123",
            "email": "psy2@example.com",
            "full_name": "Dr. Therapist Two",
            "role": "psychologist",
            "title": "Uzm. Psk.",
            "specialty": "Kaygı",
            "bio": "Merhaba, ben uzman klinik psikoloğum ve bu biyografi en az 20 karakterdir."
        }
        client.post("/register", json=psy2_payload)
        client.post("/admin/psychologists/psy_user2/approve", headers=admin_headers)
        
        login_res_psy2 = client.post("/login", json={"email": "psy2@example.com", "password": "password123"})
        psy2_token = login_res_psy2.json()["access_token"]
        psy2_headers = {"Authorization": f"Bearer {psy2_token}"}

        # Verify psy2 cannot see psy1's appointments
        res_psy2 = client.get("/appointments", headers=psy2_headers)
        self.assertEqual(res_psy2.status_code, 200)
        self.assertEqual(len(res_psy2.json()), 0) # isolation check

        # Verify psy2 cannot cancel psy1's appointment
        cancel_psy2_res = client.put(f"/appointments/{appt_id}/cancel", headers=psy2_headers)
        self.assertEqual(cancel_psy2_res.status_code, 400) # Bad Request/Forbidden

        # 10. Cancel appointment safely (soft-cancel)
        cancel_res = client.put(f"/appointments/{appt_id}/cancel", headers=user_headers)
        self.assertEqual(cancel_res.status_code, 200)
        self.assertEqual(cancel_res.json()["status"], "success")

        # Check status is updated to cancelled
        res = client.get("/appointments", headers=user_headers)
        self.assertEqual(res.json()[0]["status"], "cancelled")

        # Check that record is NOT deleted (soft-cancel validation)
        db = SessionLocal()
        try:
            db_appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
            self.assertIsNotNone(db_appt)
            self.assertEqual(db_appt.status, "cancelled")
        finally:
            db.close()
