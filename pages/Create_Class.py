import streamlit as st
import cv2
import numpy as np
import logging
from PIL import Image

import config
import firebase_service

# Logging
logger = logging.getLogger("smartface.create_class")

st.set_page_config(
    page_title="Create Class & Register Students",
    page_icon="🏫",
    layout="wide"
)

# Initialize Firebase safely
firebase_ok, firebase_msg = config.init_firebase()
if not firebase_ok:
    st.error(f"⚠️ Database Error: {firebase_msg}")
    st.stop()

# Ensure user is authenticated
if "authenticated" not in st.session_state or not st.session_state.authenticated or not st.session_state.get("institution"):
    st.error("🔒 Unauthorized access. Please log in from the Home page first.")
    st.info("Navigate to the **Home** page to log in or create an institution account.")
    st.stop()

institution = st.session_state.institution

st.title("🏫 Manage Classes & Register Students")
st.write(f"Logged in as: **{institution}**")

# Section 1: Create or Select Class
st.subheader("1. Class Selection & Creation")

classes = firebase_service.get_classes(institution)
class_names = sorted(list(classes.keys())) if classes else []

c1, c2 = st.columns([1, 1])

with c1:
    st.markdown("##### Create a New Class")
    new_class_name = st.text_input("Enter Class Name", placeholder="e.g. 1 MCA, 3 BCA, BSc-CS", key="input_new_class")
    if st.button("Create Class", key="btn_create_class"):
        if not new_class_name.strip():
            st.error("Class name cannot be empty.")
        else:
            success, msg = firebase_service.create_class(institution, new_class_name)
            if success:
                st.session_state.class_name = new_class_name.strip()
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

with c2:
    st.markdown("##### Or Select an Existing Class")
    if class_names:
        default_idx = 0
        if st.session_state.get("class_name") in class_names:
            default_idx = class_names.index(st.session_state.class_name)

        selected_existing = st.selectbox(
            "Select Active Class to Manage",
            options=class_names,
            index=default_idx,
            key="select_existing_class"
        )
        if st.session_state.get("class_name") != selected_existing:
            st.session_state.class_name = selected_existing
            st.rerun()
    else:
        st.info("No classes created yet. Create your first class on the left.")

# Stop if no class is active
active_class = st.session_state.get("class_name")
if not active_class:
    st.stop()

st.markdown("---")
st.header(f"Managing Class: **{active_class}**")

# Section 2 & 3: Tabs for Subjects and Students
tab_subjects, tab_students = st.tabs(["📚 Subject Management", "👤 Student Registration"])

# --- TAB 1: SUBJECT MANAGEMENT ---
with tab_subjects:
    st.subheader(f"Subjects for {active_class}")
    
    # Display existing subjects
    existing_subjects = firebase_service.get_subjects(institution, active_class)
    if existing_subjects:
        st.markdown("**Currently Configured Subjects:**")
        cols = st.columns(4)
        for i, s_name in enumerate(sorted(existing_subjects.keys())):
            cols[i % 4].info(f"📘 {s_name}")
    else:
        st.warning("No subjects configured for this class yet.")

    st.markdown("#### Add New Subjects")
    if "subjects_to_add" not in st.session_state:
        st.session_state.subjects_to_add = [""]

    # Subject input fields
    for i in range(len(st.session_state.subjects_to_add)):
        sub_c1, sub_c2 = st.columns([5, 1])
        st.session_state.subjects_to_add[i] = sub_c1.text_input(
            f"Subject {i + 1}",
            value=st.session_state.subjects_to_add[i],
            key=f"subject_field_{i}",
            placeholder="e.g. Data Structures, AI, Operating Systems"
        )
        if len(st.session_state.subjects_to_add) > 1:
            if sub_c2.button("❌ Remove", key=f"btn_remove_sub_{i}"):
                st.session_state.subjects_to_add.pop(i)
                st.rerun()

    action_c1, action_c2 = st.columns([1, 1])
    with action_c1:
        if st.button("➕ Add Another Subject Field", key="btn_add_sub_field"):
            st.session_state.subjects_to_add.append("")
            st.rerun()

    with action_c2:
        if st.button("💾 Save All Subjects", key="btn_submit_subjects", type="primary"):
            success, msg = firebase_service.add_subjects(
                institution, active_class, st.session_state.subjects_to_add
            )
            if success:
                st.success(msg)
                st.session_state.subjects_to_add = [""]
                st.rerun()
            else:
                st.error(msg)


# --- TAB 2: STUDENT REGISTRATION ---
with tab_students:
    st.subheader(f"Register Student for {active_class}")

    # View existing registered students
    existing_students = firebase_service.get_students(institution, active_class)
    with st.expander(f"📋 View Registered Students ({len(existing_students)})", expanded=False):
        if existing_students:
            student_rows = []
            for roll, s_data in sorted(existing_students.items()):
                student_rows.append({
                    "Roll Number": s_data.get("roll_number", roll),
                    "Name": s_data.get("name", "Unknown"),
                    "Phone": s_data.get("phone", "N/A"),
                    "Has Face Data": "✅ Yes" if bool(s_data.get("embeddings")) else "❌ No"
                })
            st.dataframe(student_rows, use_container_width=True)
        else:
            st.info("No students registered in this class yet.")

    st.markdown("#### New Student Details")
    st_col1, st_col2 = st.columns(2)

    with st_col1:
        st_name = st.text_input("Full Name", placeholder="e.g. John Doe", key="reg_student_name")
        st_roll = st.text_input("Roll Number", placeholder="e.g. 101 or CS01", key="reg_student_roll")
        st_phone = st.text_input("Phone Number (10 digits)", placeholder="e.g. 9876543210", key="reg_student_phone")

    with st_col2:
        st.markdown("**Face Registration**")
        capture_method = st.radio(
            "Select Face Capture Mode:",
            options=["Browser Camera", "Upload Image", "Desktop OpenCV Camera"],
            horizontal=True,
            key="capture_method_radio"
        )

        captured_embedding = st.session_state.get("current_student_embedding", None)

        if capture_method == "Browser Camera":
            cam_image = st.camera_input("Take a student snapshot", key="browser_camera_reg")
            if cam_image is not None:
                bytes_data = cam_image.getvalue()
                cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
                embedding, err = firebase_service.extract_face_embeddings_from_image(cv2_img, enforce_single_face=True)
                if embedding:
                    st.session_state.current_student_embedding = embedding
                    st.success("✅ Face detected and embedding extracted successfully!")
                else:
                    st.session_state.current_student_embedding = None
                    st.error(f"❌ {err}")

        elif capture_method == "Upload Image":
            uploaded_file = st.file_uploader("Upload student portrait (JPG/PNG)", type=["jpg", "jpeg", "png"], key="upload_reg_img")
            if uploaded_file is not None:
                bytes_data = uploaded_file.getvalue()
                cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
                embedding, err = firebase_service.extract_face_embeddings_from_image(cv2_img, enforce_single_face=True)
                if embedding:
                    st.session_state.current_student_embedding = embedding
                    st.success("✅ Face detected and embedding extracted successfully!")
                else:
                    st.session_state.current_student_embedding = None
                    st.error(f"❌ {err}")

        elif capture_method == "Desktop OpenCV Camera":
            st.info("Click below to open local desktop webcam window. Press **'c'** to capture or **'q'** to quit.")
            if st.button("Launch Desktop Camera", key="btn_opencv_cam"):
                try:
                    cap = cv2.VideoCapture(0)
                    if not cap.isOpened():
                        st.error("Could not access desktop webcam.")
                    else:
                        st.info("Camera window opened on desktop. Press 'c' to capture face.")
                        captured_frame = None
                        while cap.isOpened():
                            ret, frame = cap.read()
                            if not ret:
                                st.error("Failed to read frame from webcam.")
                                break
                            cv2.imshow("Capture Face - Press 'c' to capture, 'q' to quit", frame)
                            key = cv2.waitKey(1) & 0xFF
                            if key == ord('c'):
                                captured_frame = frame.copy()
                                break
                            elif key == ord('q'):
                                break
                        cap.release()
                        cv2.destroyAllWindows()

                        if captured_frame is not None:
                            embedding, err = firebase_service.extract_face_embeddings_from_image(captured_frame, enforce_single_face=True)
                            if embedding:
                                st.session_state.current_student_embedding = embedding
                                st.success("✅ Face captured and embedding extracted successfully!")
                            else:
                                st.session_state.current_student_embedding = None
                                st.error(f"❌ {err}")
                except Exception as ex:
                    st.error(f"Desktop webcam error: {ex}")

        # Show status badge
        if st.session_state.get("current_student_embedding"):
            st.success("Face Data Ready: 128-d embedding loaded ✅")
        else:
            st.warning("⚠️ No face data registered yet for this student.")

    st.markdown("---")
    if st.button("Register Student", type="primary", use_container_width=True, key="btn_register_student"):
        if not st_name or not st_roll or not st_phone:
            st.error("All fields (Name, Roll Number, Phone) are required.")
        elif not (st_phone.isdigit() and len(st_phone) == 10):
            st.error("Phone number must be exactly 10 digits.")
        elif not st.session_state.get("current_student_embedding"):
            st.error("Please capture or upload the student's face before registering.")
        else:
            success, msg = firebase_service.register_student(
                institution=institution,
                class_name=active_class,
                name=st_name,
                roll_number=st_roll,
                phone=st_phone,
                embeddings=st.session_state.current_student_embedding
            )
            if success:
                st.success(msg)
                st.session_state.current_student_embedding = None
                st.rerun()
            else:
                st.error(msg)
