"""Automated Test Suite for SmartFace Attendance System.
Covers positive and negative test cases for Configuration, Authentication,
Class & Student Management, Face Recognition logic, Attendance marking,
and Excel/CSV export generation.
"""

import unittest
import io
import os
import numpy as np
import pandas as pd
from unittest.mock import patch

import config
import firebase_service


class TestConfiguration(unittest.TestCase):
    """Tests environment configuration loading and validation."""

    def test_config_loaded(self):
        self.assertTrue(bool(config.FIREBASE_DATABASE_URL), "Database URL should be loaded from .env")
        self.assertTrue(bool(config.FIREBASE_CREDENTIALS_PATH), "Credentials path should be configured")

    def test_validate_config_success(self):
        is_valid, msg = config.validate_config()
        self.assertTrue(is_valid)
        self.assertEqual(msg, "")

    @patch("config.FIREBASE_DATABASE_URL", "")
    def test_missing_database_url_validation(self):
        is_valid, msg = config.validate_config()
        self.assertFalse(is_valid)
        self.assertIn("FIREBASE_DATABASE_URL is not configured", msg)

    @patch("config.FIREBASE_CREDENTIALS_PATH", "non_existent_credentials_path.json")
    def test_missing_credentials_file_validation(self):
        is_valid, msg = config.validate_config()
        self.assertFalse(is_valid)
        self.assertIn("credentials file not found", msg)

    def test_init_firebase(self):
        ok, msg = config.init_firebase()
        self.assertTrue(ok)


class TestAuthenticationAndValidation(unittest.TestCase):
    """Tests authentication logic, input validation, and password security."""

    def test_email_validation_positive(self):
        self.assertTrue(firebase_service.is_valid_email("admin@college.edu"))
        self.assertTrue(firebase_service.is_valid_email("user.name+tag@domain.co.in"))

    def test_email_validation_negative(self):
        self.assertFalse(firebase_service.is_valid_email(""))
        self.assertFalse(firebase_service.is_valid_email("no-at-sign.com"))
        self.assertFalse(firebase_service.is_valid_email("user@domain"))
        self.assertFalse(firebase_service.is_valid_email("@domain.com"))
        self.assertFalse(firebase_service.is_valid_email(None))

    def test_password_validation_positive(self):
        self.assertTrue(firebase_service.is_valid_password("SecurePass123!"))
        self.assertTrue(firebase_service.is_valid_password("Admin#2025@Key"))

    def test_password_validation_negative(self):
        self.assertFalse(firebase_service.is_valid_password("short1!"))  # <8 chars
        self.assertFalse(firebase_service.is_valid_password("alllowercase123!"))  # no upper
        self.assertFalse(firebase_service.is_valid_password("ALLUPPERCASE123!"))  # no lower
        self.assertFalse(firebase_service.is_valid_password("NoDigitsHere!@#"))  # no digit
        self.assertFalse(firebase_service.is_valid_password("NoSpecialChar123"))  # no special
        self.assertFalse(firebase_service.is_valid_password("Has Space123!"))  # has space
        self.assertFalse(firebase_service.is_valid_password(""))
        self.assertFalse(firebase_service.is_valid_password(None))

    def test_firebase_key_validation(self):
        self.assertTrue(firebase_service.is_valid_firebase_key("Computer-Science_1"))
        self.assertTrue(firebase_service.is_valid_firebase_key("101"))
        self.assertFalse(firebase_service.is_valid_firebase_key("Invalid.Key"))
        self.assertFalse(firebase_service.is_valid_firebase_key("Key/Slash"))
        self.assertFalse(firebase_service.is_valid_firebase_key("Key$Dollar"))
        self.assertFalse(firebase_service.is_valid_firebase_key("Key#Hash"))
        self.assertFalse(firebase_service.is_valid_firebase_key("Key[Bracket]"))
        self.assertFalse(firebase_service.is_valid_firebase_key(""))
        self.assertFalse(firebase_service.is_valid_firebase_key(None))

    def test_password_hashing_and_verification(self):
        raw_pw = "Antigravity2025!"
        hashed = firebase_service.hash_password(raw_pw)
        self.assertNotEqual(raw_pw, hashed)
        self.assertTrue(hashed.startswith("$2"))

        # Positive verification
        self.assertTrue(firebase_service.verify_password(hashed, raw_pw))

        # Negative: incorrect password
        self.assertFalse(firebase_service.verify_password(hashed, "WrongPassword123!"))

        # Negative: corrupted hash or empty string should not crash
        self.assertFalse(firebase_service.verify_password("not_a_valid_hash", raw_pw))
        self.assertFalse(firebase_service.verify_password("", raw_pw))
        self.assertFalse(firebase_service.verify_password(None, raw_pw))


class TestFaceRecognitionLogic(unittest.TestCase):
    """Tests facial recognition mathematics and embedding comparison."""

    def test_cosine_similarity_identical(self):
        v = [0.2, 0.5, 0.8, -0.3]
        sim = firebase_service.cosine_similarity(v, v)
        self.assertAlmostEqual(sim, 1.0, places=4)

    def test_cosine_similarity_orthogonal(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0]
        sim = firebase_service.cosine_similarity(v1, v2)
        self.assertAlmostEqual(sim, 0.0, places=4)

    def test_cosine_similarity_opposite(self):
        v1 = [1.0, 2.0, 3.0]
        v2 = [-1.0, -2.0, -3.0]
        sim = firebase_service.cosine_similarity(v1, v2)
        self.assertAlmostEqual(sim, -1.0, places=4)

    def test_cosine_similarity_zero_vectors_no_crash(self):
        v_zero = [0.0, 0.0, 0.0]
        v_normal = [1.0, 2.0, 3.0]
        sim = firebase_service.cosine_similarity(v_zero, v_normal)
        self.assertEqual(sim, 0.0)
        sim_both_zero = firebase_service.cosine_similarity(v_zero, v_zero)
        self.assertEqual(sim_both_zero, 0.0)

    def test_extract_face_empty_image(self):
        empty_img = np.zeros((0, 0, 3), dtype=np.uint8)
        emb, err = firebase_service.extract_face_embeddings_from_image(empty_img)
        self.assertIsNone(emb)
        self.assertIn("empty image", err.lower())

    def test_extract_face_no_face_in_black_canvas(self):
        canvas = np.zeros((200, 200, 3), dtype=np.uint8)
        emb, err = firebase_service.extract_face_embeddings_from_image(canvas)
        self.assertIsNone(emb)
        self.assertIn("no face detected", err.lower())


class TestExcelAndCSVExport(unittest.TestCase):
    """Tests in-memory generation of Excel and CSV attendance reports."""

    def test_excel_export_openpyxl(self):
        sample_data = [
            {"Roll No": "101", "Student Name": "Alice", "2026-10-01": "Present", "2026-10-02": "Present", "Attendance %": "100%"},
            {"Roll No": "102", "Student Name": "Bob", "2026-10-01": "Absent", "2026-10-02": "Present", "Attendance %": "50%"}
        ]
        df = pd.DataFrame(sample_data)

        # Generate Excel buffer
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Attendance")
        excel_bytes = excel_buffer.getvalue()

        self.assertGreater(len(excel_bytes), 0)
        # Verify it can be read back as valid Excel
        read_df = pd.read_excel(io.BytesIO(excel_bytes))
        self.assertEqual(len(read_df), 2)
        self.assertIn("Student Name", read_df.columns)
        self.assertEqual(read_df.iloc[0]["Student Name"], "Alice")

    def test_csv_export(self):
        sample_data = [
            {"Roll No": "101", "Student Name": "Alice", "Status": "Present"}
        ]
        df = pd.DataFrame(sample_data)
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        self.assertGreater(len(csv_bytes), 0)
        self.assertIn(b"Alice", csv_bytes)


class TestDatabaseWorkflowsEndToEnd(unittest.TestCase):
    """Tests actual database workflows on a test institution namespace.
    Cleans up after testing to avoid database pollution.
    """

    TEST_INST = "__QA_Test_Institute__"
    TEST_EMAIL = "__qa_test__@college.edu"
    TEST_PASS = "TestPassword123!"

    @classmethod
    def setUpClass(cls):
        config.init_firebase()

    @classmethod
    def tearDownClass(cls):
        # Clean up test node
        from firebase_admin import db
        try:
            ref = db.reference(f"/{cls.TEST_INST}")
            ref.delete()
        except Exception:
            pass

    def test_01_institution_registration_and_login(self):
        # Positive registration
        ok, msg = firebase_service.register_institution(
            self.TEST_INST, self.TEST_EMAIL, self.TEST_PASS, self.TEST_PASS
        )
        self.assertTrue(ok, f"Registration failed: {msg}")

        # Negative: duplicate registration
        ok_dup, msg_dup = firebase_service.register_institution(
            self.TEST_INST, "different@college.edu", self.TEST_PASS, self.TEST_PASS
        )
        self.assertFalse(ok_dup)
        self.assertIn("already exists", msg_dup)

        # Negative: duplicate email with another institution name
        ok_dup_email, msg_dup_email = firebase_service.register_institution(
            "__Another_Test_Inst__", self.TEST_EMAIL, self.TEST_PASS, self.TEST_PASS
        )
        self.assertFalse(ok_dup_email)
        self.assertIn("already registered", msg_dup_email)

        # Positive login
        success, inst_name, err = firebase_service.login_user(self.TEST_EMAIL, self.TEST_PASS)
        self.assertTrue(success)
        self.assertEqual(inst_name, self.TEST_INST)

        # Negative login: invalid password
        bad_pw_ok, _, _ = firebase_service.login_user(self.TEST_EMAIL, "WrongPass123!")
        self.assertFalse(bad_pw_ok)

        # Negative login: non-existent email
        non_ex_ok, _, _ = firebase_service.login_user("nobody@college.edu", self.TEST_PASS)
        self.assertFalse(non_ex_ok)

    def test_02_class_and_subject_management(self):
        # Negative: empty class name
        ok, msg = firebase_service.create_class(self.TEST_INST, "   ")
        self.assertFalse(ok)

        # Negative: invalid firebase characters
        ok, msg = firebase_service.create_class(self.TEST_INST, "CS/101")
        self.assertFalse(ok)

        # Positive: create class
        class_name = "QA_Class_A"
        ok, msg = firebase_service.create_class(self.TEST_INST, class_name)
        self.assertTrue(ok, msg)

        # Negative: duplicate class creation
        ok_dup, _ = firebase_service.create_class(self.TEST_INST, class_name)
        self.assertFalse(ok_dup)

        # Verify class exists in list
        classes = firebase_service.get_classes(self.TEST_INST)
        self.assertIn(class_name, classes)

        # Add subjects
        subjects = ["Mathematics", "Computer Science"]
        ok_sub, msg_sub = firebase_service.add_subjects(self.TEST_INST, class_name, subjects)
        self.assertTrue(ok_sub, msg_sub)

        # Verify subjects exist
        fetched_subs = firebase_service.get_subjects(self.TEST_INST, class_name)
        self.assertIn("Mathematics", fetched_subs)
        self.assertIn("Computer Science", fetched_subs)

    def test_03_student_registration_and_attendance(self):
        class_name = "QA_Class_A"
        subject_name = "Computer Science"

        # Synthetic 128-d embedding
        synthetic_emb = list(np.random.normal(0, 1, 128).astype(float))

        # Negative: invalid phone number
        ok_p, msg_p = firebase_service.register_student(
            self.TEST_INST, class_name, "QA Student", "QA01", "123", synthetic_emb
        )
        self.assertFalse(ok_p)
        self.assertIn("10 digits", msg_p)

        # Negative: missing embedding
        ok_e, msg_e = firebase_service.register_student(
            self.TEST_INST, class_name, "QA Student", "QA01", "9876543210", None
        )
        self.assertFalse(ok_e)

        # Positive student registration
        ok, msg = firebase_service.register_student(
            self.TEST_INST, class_name, "QA Student One", "QA01", "9876543210", synthetic_emb
        )
        self.assertTrue(ok, msg)

        # Negative: duplicate roll number in same class
        ok_dup, msg_dup = firebase_service.register_student(
            self.TEST_INST, class_name, "QA Student Duplicate", "QA01", "9876543210", synthetic_emb
        )
        self.assertFalse(ok_dup)
        self.assertIn("already registered", msg_dup)

        # Verify student retrieval (handles both list and dict formats)
        students = firebase_service.get_students(self.TEST_INST, class_name)
        self.assertIn("QA01", students)
        self.assertEqual(students["QA01"]["name"], "QA Student One")

        # Mark attendance
        marked_count, marked_names = firebase_service.mark_attendance(
            self.TEST_INST, class_name, subject_name, {"QA01"}, students
        )
        self.assertEqual(marked_count, 1)
        self.assertIn("QA Student One", marked_names)

        # Verify duplicate attendance does not duplicate or crash
        marked_count2, _ = firebase_service.mark_attendance(
            self.TEST_INST, class_name, subject_name, {"QA01"}, students
        )
        self.assertEqual(marked_count2, 1)

        # Verify attendance record exists in database
        attendance = firebase_service.get_attendance(self.TEST_INST, class_name, subject_name)
        self.assertTrue(len(attendance) > 0)


if __name__ == "__main__":
    unittest.main()
