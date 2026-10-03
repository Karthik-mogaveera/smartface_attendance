# 🎓 SmartFace Attendance System

SmartFace Attendance is an automated, AI-powered attendance management web application. It combines facial detection and deep learning recognition with real-time database synchronization to streamline attendance tracking for educational institutions and organizations.

---

## 📌 Project Overview

Traditional attendance taking is time-consuming and prone to proxy marking. SmartFace Attendance solves this by providing:

- **Institution Multi-Tenant Authentication**: Secure account creation and login for schools, colleges, and training institutes with encrypted passwords (`bcrypt`).
- **Class & Subject Management**: Flexible structure to organize classes, configure subjects, and manage student rosters.
- **Biometric Face Enrollment**: 128-dimensional facial feature representation extracted using **MediaPipe** and **DeepFace (Facenet)**.
- **Multi-Mode Attendance Capture**:
  - **Browser Camera**: Instant snapshot directly from modern desktop and mobile browsers.
  - **Classroom Photo Upload**: Upload high-resolution images with automatic multi-student face detection.
  - **Desktop Live Webcam**: High-speed real-time OpenCV stream with live visual feedback.
- **Real-Time Database**: Backed by Google **Firebase Realtime Database** with duplicate attendance prevention.
- **Dashboard & Analytics**: Live attendance percentage metrics, attendance status tracking, and export to **Excel (`.xlsx`)** and **CSV (`.csv`)**.

---

## 🛠 Technology Stack

- **Frontend / Framework**: [Streamlit](https://streamlit.io/) (v1.41+)
- **Face Detection**: [Google MediaPipe Face Detection](https://developers.google.com/mediapipe/solutions/vision/face_detector)
- **Face Embeddings**: [DeepFace](https://github.com/serengil/deepface) with **Facenet** architecture
- **Computer Vision**: [OpenCV (opencv-python)](https://opencv.org/)
- **Machine Learning Core**: [TensorFlow](https://www.tensorflow.org/) & `tf-keras`
- **Database & Storage**: [Firebase Realtime Database](https://firebase.google.com/docs/database) via `firebase-admin`
- **Security & Cryptography**: `bcrypt` password hashing
- **Data & Reporting**: `pandas`, `openpyxl` (Excel), `numpy`
- **Configuration Management**: `python-dotenv`

---

## 📋 Requirements

- **Python Version**: Python 3.10 – 3.12 (Tested on Python 3.12.4)
- **Operating System**: Windows 10/11, Linux (Ubuntu 20.04+), or macOS
- **Hardware**: Standard CPU (x86_64); webcam or integrated camera for live capture
- **External Services**:
  - Firebase project with **Realtime Database** enabled
  - Firebase Service Account private key JSON credentials file

---

## 🚀 Installation & Setup

### 1. Clone or Open the Repository

```bash
cd c:\smartface_attendance
```

### 2. Create and Activate a Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv env
.\env\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
python -m venv env
.\env\Scripts\activate.bat
```

**Linux / macOS:**
```bash
python3 -m venv env
source env/bin/activate
```

### 3. Install Required Dependencies

```bash
pip install -r requirements.txt
```

---

## ⚙️ Environment Configuration

1. Copy the sample environment template:
   ```bash
   cp .env.example .env
   ```
2. Place your Firebase service account private key JSON file in the project folder (e.g. `firebase_configurations.json`).
3. Open `.env` and fill in your details:

```env
# Firebase Realtime Database Configuration
FIREBASE_DATABASE_URL=https://your-project-id-default-rtdb.region.firebasedatabase.app/
FIREBASE_CREDENTIALS_PATH=firebase_configurations.json

# Security and Application Configuration
SECRET_KEY=your_secure_random_secret_key_here
DEBUG=False

# Face Recognition Settings
FACE_MATCH_THRESHOLD=0.6
ATTENDANCE_SESSION_TIMEOUT_SECONDS=120
```

> ⚠️ **Important Security Note:** Never commit your `.env` or `firebase_configurations.json` files to Git. Both are listed in `.gitignore`.

---

## 🏃 Running the Application

Launch the Streamlit application:

```bash
streamlit run Home.py
```

The web interface will open automatically in your default browser at:
`http://localhost:8501`

---

## 🧪 Running Automated Tests

Run the full automated test suite covering configuration, authentication, database operations, face recognition, and Excel export:

```bash
python -m unittest tests/test_smartface.py
```

Or using `pytest`:

```bash
pytest tests/
```

---

## 📱 Application Flow & Features

1. **Home / Login & Signup (`Home.py`)**:
   - Register new institutions with strict password validation (min 8 chars, uppercase, lowercase, numbers, special characters).
   - Institution-isolated login with bcrypt hashing.
   - Comprehensive dashboard showing class attendance sheets and real-time statistics.
   - One-click Excel (`.xlsx`) and CSV report downloads.

2. **Create Class & Register Students (`pages/Create_Class.py`)**:
   - Create classes (with database persistence).
   - Configure subjects for each class.
   - Register students with Name, Roll Number, 10-digit Phone, and Biometric Face capture.
   - Face validation guarantees only 1 face is captured per student.

3. **Take Attendance (`pages/Take_Attendance.py`)**:
   - Select Class and Subject.
   - Choose capture mode: Browser Camera, Upload Photo, or Desktop Live Webcam.
   - Multiple faces in the frame are detected and matched simultaneously.
   - Prevents duplicate attendance entries on the same date while recording exact arrival timestamps.

---

## 🔧 Troubleshooting

| Issue | Cause | Solution |
|---|---|---|
| `FIREBASE_DATABASE_URL is not configured` | Missing or incomplete `.env` file | Create `.env` based on `.env.example` and set `FIREBASE_DATABASE_URL`. |
| `Firebase credentials file not found` | Key file path incorrect | Ensure `FIREBASE_CREDENTIALS_PATH` in `.env` points to your valid Firebase JSON file. |
| `No module named 'openpyxl'` | Missing Excel dependency | Run `pip install openpyxl` or `pip install -r requirements.txt`. |
| `No module named 'dotenv'` | Missing environment loader | Run `pip install python-dotenv` or `pip install -r requirements.txt`. |
| `OpenCV webcam fails to open` | Camera blocked by permissions or occupied | Close other apps using the webcam, or select **Browser Camera** mode in the UI. |
| `No face detected / Multiple faces detected` | Poor lighting or multiple people in frame | Ensure single person is centered with adequate front lighting during registration. |
| `PermissionError on Excel download` | Temporary file locked on Windows | The export now uses in-memory `io.BytesIO()`, eliminating temporary file locking errors. |
