"""Configuration module for smartface_attendance.

Loads environment variables from .env and provides centralized configuration
and Firebase initialization with validation and robust error handling.
"""

import os
import sys
import logging
from pathlib import Path

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# If running from system Python without activated virtual environment,
# automatically include project virtual environment site-packages in sys.path
_venv_site = BASE_DIR / "env" / "Lib" / "site-packages"
if _venv_site.exists() and str(_venv_site) not in sys.path:
    sys.path.insert(0, str(_venv_site))

from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, db

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("smartface")

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

# Configuration variables
FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "").strip()
CREDENTIALS_ENV = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase_configurations.json").strip()

# Resolve credentials path (relative to BASE_DIR if not absolute)
if CREDENTIALS_ENV:
    _cand_path = Path(CREDENTIALS_ENV)
    if not _cand_path.is_absolute():
        FIREBASE_CREDENTIALS_PATH = str(BASE_DIR / _cand_path)
    else:
        FIREBASE_CREDENTIALS_PATH = str(_cand_path)
else:
    FIREBASE_CREDENTIALS_PATH = str(BASE_DIR / "firebase_configurations.json")

SECRET_KEY = os.getenv("SECRET_KEY", "smartface_default_secret_key")
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t", "yes")

try:
    FACE_MATCH_THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.6"))
except ValueError:
    FACE_MATCH_THRESHOLD = 0.6

try:
    ATTENDANCE_SESSION_TIMEOUT_SECONDS = int(os.getenv("ATTENDANCE_SESSION_TIMEOUT_SECONDS", "120"))
except ValueError:
    ATTENDANCE_SESSION_TIMEOUT_SECONDS = 120


def validate_config():
    """Validates required environment configuration.

    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    if not FIREBASE_DATABASE_URL:
        return (
            False,
            "FIREBASE_DATABASE_URL is not configured.\n"
            "Please create a .env file and provide the required configuration.",
        )

    if not os.path.exists(FIREBASE_CREDENTIALS_PATH):
        return (
            False,
            f"Firebase credentials file not found at: {FIREBASE_CREDENTIALS_PATH}\n"
            "Please provide a valid service account JSON file and configure FIREBASE_CREDENTIALS_PATH in .env.",
        )

    return True, ""


def init_firebase():
    """Initializes Firebase Admin SDK safely (idempotent).

    Returns:
        tuple[bool, str]: (is_initialized, message)
    """
    is_valid, err_msg = validate_config()
    if not is_valid:
        logger.error(err_msg)
        return False, err_msg

    if not firebase_admin._apps:
        try:
            cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(
                cred,
                {
                    "databaseURL": FIREBASE_DATABASE_URL,
                },
            )
            logger.info("Firebase initialized successfully.")
            return True, "Firebase initialized successfully."
        except Exception as e:
            logger.exception("Failed to initialize Firebase app.")
            return False, f"Unable to connect to the database. Error: {str(e)}"

    return True, "Firebase already initialized."
