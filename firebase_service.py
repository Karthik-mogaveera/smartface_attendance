"""Service layer for Firebase Realtime Database and face recognition utilities.

Handles authentication, class/subject/student management, attendance tracking,
data normalization, and robust error handling.
"""

import re
import logging
from datetime import datetime
import numpy as np
import cv2
import bcrypt
from firebase_admin import db
import mediapipe as mp
from deepface import DeepFace

logger = logging.getLogger("smartface.service")

# Regex pattern for email validation
EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

# Characters forbidden in Firebase Realtime Database keys
FORBIDDEN_FIREBASE_CHARS = {'.', '$', '#', '[', ']', '/'}


def is_valid_email(email: str) -> bool:
    """Validates email format."""
    if not email or not isinstance(email, str):
        return False
    return bool(re.match(EMAIL_REGEX, email.strip()))


def is_valid_password(password: str) -> bool:
    """Validates password strength:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    - No spaces
    """
    if not password or not isinstance(password, str):
        return False
    return (
        len(password) >= 8
        and any(c.isupper() for c in password)
        and any(c.islower() for c in password)
        and any(c.isdigit() for c in password)
        and any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/" for c in password)
        and " " not in password
    )


def is_valid_firebase_key(key: str) -> bool:
    """Validates if a string is a valid Firebase Realtime Database key."""
    if not key or not isinstance(key, str):
        return False
    key = key.strip()
    if not key:
        return False
    return not any(c in FORBIDDEN_FIREBASE_CHARS for c in key)


def hash_password(password: str) -> str:
    """Hashes a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(stored_password: str, entered_password: str) -> bool:
    """Safely verifies a password against a stored bcrypt hash.
    Catches invalid salt or format errors gracefully.
    """
    if not stored_password or not entered_password:
        return False
    try:
        stored_bytes = stored_password.encode("utf-8")
        entered_bytes = entered_password.encode("utf-8")
        return bcrypt.checkpw(entered_bytes, stored_bytes)
    except (ValueError, TypeError) as e:
        logger.warning(f"Password verification error: {e}")
        return False


def login_user(email: str, password: str):
    """Authenticates a user across institutions.

    Returns:
        tuple[bool, str | None, str]: (success, institution_name, error_message)
    """
    if not is_valid_email(email):
        return False, None, "Invalid email format."
    if not password:
        return False, None, "Password cannot be empty."

    try:
        ref = db.reference("/")
        users = ref.get()
        if not users or not isinstance(users, dict):
            return False, None, "Incorrect email or password."

        for institution, data in users.items():
            if isinstance(data, dict):
                stored_email = data.get("Email")
                stored_pwd = data.get("Password", "")
                if stored_email and stored_email.lower() == email.strip().lower():
                    if verify_password(stored_pwd, password):
                        return True, institution, ""
                    else:
                        return False, None, "Incorrect email or password."

        return False, None, "Incorrect email or password."
    except Exception as e:
        logger.exception("Login failed due to database error.")
        return False, None, f"Database error during login: {str(e)}"


def register_institution(institution: str, email: str, password: str, confirm_password: str):
    """Registers a new institution account with duplicate prevention.

    Returns:
        tuple[bool, str]: (success, message)
    """
    institution = institution.strip() if institution else ""
    email = email.strip() if email else ""

    if not institution:
        return False, "Institution name cannot be empty."
    if not is_valid_firebase_key(institution):
        return False, "Institution name contains invalid characters. Avoid: . $ # [ ] /"
    if not is_valid_email(email):
        return False, "Invalid email format."
    if not is_valid_password(password):
        return False, "Password must be at least 8 characters with uppercase, lowercase, number, and special character."
    if password != confirm_password:
        return False, "Passwords do not match."

    try:
        root_ref = db.reference("/")
        all_data = root_ref.get() or {}

        # Check if institution name already exists
        if institution in all_data:
            return False, "Institution already exists. Please use a different name or log in."

        # Check if email is already registered by any institution
        for inst_name, inst_data in all_data.items():
            if isinstance(inst_data, dict):
                existing_email = inst_data.get("Email", "")
                if existing_email.lower() == email.lower():
                    return False, "Email address is already registered with another institution."

        # Save new institution
        hashed_pwd = hash_password(password)
        inst_ref = db.reference(f"/{institution}")
        inst_ref.set({
            "Institution": institution,
            "Email": email,
            "Password": hashed_pwd,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return True, "Account created successfully!"
    except Exception as e:
        logger.exception("Registration failed due to database error.")
        return False, f"Database error during registration: {str(e)}"


def get_classes(institution: str) -> dict:
    """Fetches all classes for an institution."""
    try:
        ref = db.reference(f"/{institution}/classes")
        classes = ref.get()
        if isinstance(classes, dict):
            return classes
        elif isinstance(classes, list):
            return {str(i): v for i, v in enumerate(classes) if v is not None}
        return {}
    except Exception as e:
        logger.exception("Failed to fetch classes.")
        return {}


def create_class(institution: str, class_name: str):
    """Creates a new class under the institution.
    Initializes with metadata so Firebase Realtime Database retains the node.

    Returns:
        tuple[bool, str]: (success, message)
    """
    class_name = class_name.strip() if class_name else ""
    if not class_name:
        return False, "Class name cannot be empty."
    if not is_valid_firebase_key(class_name):
        return False, "Class name contains invalid characters. Avoid: . $ # [ ] /"

    try:
        ref = db.reference(f"/{institution}/classes/{class_name}")
        existing = ref.get()
        if existing is not None:
            return False, "Class already exists!"

        # Initialize with metadata so RTDB retains the path
        ref.set({
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return True, f"Class '{class_name}' created successfully!"
    except Exception as e:
        logger.exception("Failed to create class.")
        return False, f"Database error: {str(e)}"


def get_subjects(institution: str, class_name: str) -> dict:
    """Fetches all subjects for a class."""
    try:
        ref = db.reference(f"/{institution}/classes/{class_name}/subjects")
        subjects = ref.get()
        if isinstance(subjects, dict):
            return subjects
        elif isinstance(subjects, list):
            return {str(i): v for i, v in enumerate(subjects) if v is not None}
        return {}
    except Exception as e:
        logger.exception("Failed to fetch subjects.")
        return {}


def add_subjects(institution: str, class_name: str, subjects_list: list):
    """Adds multiple subjects to a class.

    Returns:
        tuple[bool, str]: (success, message)
    """
    valid_subjects = [s.strip() for s in subjects_list if s and s.strip()]
    if not valid_subjects:
        return False, "Please enter at least one valid subject name."

    for s in valid_subjects:
        if not is_valid_firebase_key(s):
            return False, f"Subject '{s}' contains invalid characters. Avoid: . $ # [ ] /"

    try:
        subjects_ref = db.reference(f"/{institution}/classes/{class_name}/subjects")
        for subject in valid_subjects:
            subjects_ref.child(subject).child("default").set(0)
        return True, "Subjects added successfully!"
    except Exception as e:
        logger.exception("Failed to add subjects.")
        return False, f"Database error: {str(e)}"


def get_students(institution: str, class_name: str) -> dict:
    """Fetches student dictionary for a class, normalizing list or dict from Firebase.

    Returns:
        dict[str, dict]: {roll_number: student_data}
    """
    try:
        ref = db.reference(f"/{institution}/classes/{class_name}/students")
        data = ref.get()
        if not data:
            return {}

        normalized = {}
        if isinstance(data, dict):
            for roll, student in data.items():
                if isinstance(student, dict):
                    normalized[str(roll)] = student
        elif isinstance(data, list):
            for index, student in enumerate(data):
                if isinstance(student, dict):
                    roll = str(student.get("roll_number", index))
                    normalized[roll] = student
        return normalized
    except Exception as e:
        logger.exception("Failed to fetch students.")
        return {}


def register_student(institution: str, class_name: str, name: str, roll_number: str, phone: str, embeddings: list):
    """Registers a new student with face embeddings.

    Returns:
        tuple[bool, str]: (success, message)
    """
    name = name.strip() if name else ""
    roll_number = roll_number.strip() if roll_number else ""
    phone = phone.strip() if phone else ""

    if not name or not roll_number or not phone:
        return False, "All fields (Name, Roll Number, Phone Number) are required."
    if not is_valid_firebase_key(roll_number):
        return False, "Roll number contains invalid characters. Avoid: . $ # [ ] /"
    if not (phone.isdigit() and len(phone) == 10):
        return False, "Phone number must be exactly 10 digits."
    if not embeddings or not isinstance(embeddings, list):
        return False, "Face embedding data is missing. Please capture student face."

    try:
        student_ref = db.reference(f"/{institution}/classes/{class_name}/students/{roll_number}")
        if student_ref.get():
            return False, f"Roll Number '{roll_number}' is already registered in this class."

        student_ref.set({
            "name": name,
            "roll_number": roll_number,
            "phone": phone,
            "embeddings": embeddings,
            "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return True, "Student registered successfully!"
    except Exception as e:
        logger.exception("Failed to register student.")
        return False, f"Database error: {str(e)}"


def get_attendance(institution: str, class_name: str, subject_name: str) -> dict:
    """Fetches attendance records for a subject."""
    try:
        ref = db.reference(f"/{institution}/classes/{class_name}/subjects/{subject_name}/attendance")
        records = ref.get()
        if isinstance(records, dict):
            return records
        return {}
    except Exception as e:
        logger.exception("Failed to fetch attendance.")
        return {}


def mark_attendance(institution: str, class_name: str, subject_name: str, recognized_roll_numbers: set, student_data: dict):
    """Marks attendance in Firebase for recognized students.
    Prevents duplicate attendance timestamp overwrite if already marked Present today.

    Returns:
        tuple[int, list[str]]: (marked_count, list_of_marked_names)
    """
    if not recognized_roll_numbers:
        return 0, []

    today_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        attendance_ref = db.reference(f"/{institution}/classes/{class_name}/subjects/{subject_name}/attendance/{today_date}")
        existing_today = attendance_ref.get() or {}

        marked_names = []
        for roll_number in recognized_roll_numbers:
            if roll_number in student_data:
                student = student_data[roll_number]
                # If already marked present, don't overwrite timestamp
                if roll_number in existing_today and existing_today[roll_number].get("status") == "Present":
                    marked_names.append(student.get("name", roll_number))
                    continue

                attendance_ref.child(roll_number).set({
                    "name": student.get("name", "Unknown"),
                    "roll_number": roll_number,
                    "status": "Present",
                    "timestamp": current_time
                })
                marked_names.append(student.get("name", roll_number))

        return len(marked_names), marked_names
    except Exception as e:
        logger.exception("Failed to mark attendance.")
        return 0, []


# Face recognition utilities
_face_detector = None


def get_face_detector():
    """Lazily initializes and reuses the MediaPipe FaceDetection solution."""
    global _face_detector
    if _face_detector is None:
        mp_face_detection = mp.solutions.face_detection
        _face_detector = mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
    return _face_detector


def extract_face_embeddings_from_image(image_bgr: np.ndarray, enforce_single_face: bool = False):
    """Extracts face embeddings from a BGR image using MediaPipe and DeepFace Facenet.

    Args:
        image_bgr: OpenCV BGR image numpy array.
        enforce_single_face: If True, fails if more than one face is detected.

    Returns:
        tuple[list | None, str | None]: (embeddings_list, error_message)
            When enforce_single_face is True: embeddings_list is a single 128-d embedding list or None.
            When enforce_single_face is False: embeddings_list is a list of 128-d embedding lists.
    """
    if image_bgr is None or image_bgr.size == 0:
        return None, "Invalid or empty image provided."

    detector = get_face_detector()
    h, w, _ = image_bgr.shape
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    results = detector.process(image_rgb)

    if not results or not results.detections:
        return None, "No face detected in the image. Please ensure proper lighting and face position."

    if enforce_single_face and len(results.detections) > 1:
        return None, f"Multiple faces ({len(results.detections)}) detected. Please ensure only one person is in frame."

    embeddings = []
    for detection in results.detections:
        bbox = detection.location_data.relative_bounding_box
        xmin = max(0, int(bbox.xmin * w))
        ymin = max(0, int(bbox.ymin * h))
        xmax = min(w, xmin + max(1, int(bbox.width * w)))
        ymax = min(h, ymin + max(1, int(bbox.height * h)))

        face_crop = image_bgr[ymin:ymax, xmin:xmax]
        if face_crop.size == 0 or face_crop.shape[0] < 20 or face_crop.shape[1] < 20:
            continue

        try:
            face_crop_resized = cv2.resize(face_crop, (160, 160))
            rep = DeepFace.represent(
                face_crop_resized,
                model_name="Facenet",
                enforce_detection=False
            )
            if rep and len(rep) > 0 and "embedding" in rep[0]:
                embeddings.append(rep[0]["embedding"])
        except Exception as e:
            logger.warning(f"Error computing representation for face: {e}")

    if not embeddings:
        return None, "Could not extract face embedding from the detected face."

    if enforce_single_face:
        return embeddings[0], None
    return embeddings, None


def cosine_similarity(vec1, vec2) -> float:
    """Computes cosine similarity between two feature vectors safely."""
    try:
        v1 = np.asarray(vec1, dtype=np.float32)
        v2 = np.asarray(vec2, dtype=np.float32)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0 or np.isnan(norm1) or np.isnan(norm2):
            return 0.0
        dot = np.dot(v1, v2)
        sim = float(dot / (norm1 * norm2))
        return max(-1.0, min(1.0, sim))
    except Exception:
        return 0.0
