import streamlit as st
import cv2
import numpy as np
import logging
from datetime import datetime, timedelta

import config
import firebase_service

logger = logging.getLogger("smartface.take_attendance")

st.set_page_config(
    page_title="Take Attendance",
    page_icon="📸",
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
    st.info("Navigate to the **Home** page to log in.")
    st.stop()

institution = st.session_state.institution

st.title("📸 Automated Face Attendance")
st.write(f"Institution: **{institution}**")

# Fetch all classes
classes = firebase_service.get_classes(institution)
if not classes:
    st.warning("⚠️ No classes found. Please create a class and register students first under **Create Class**.")
    st.stop()

class_names = sorted(list(classes.keys()))

col_class, col_subject = st.columns(2)

with col_class:
    default_c_idx = 0
    if st.session_state.get("selected_class") in class_names:
        default_c_idx = class_names.index(st.session_state.selected_class)

    selected_class = st.selectbox(
        "Select Class",
        options=class_names,
        index=default_c_idx,
        key="attendance_class_select"
    )
    if selected_class != st.session_state.get("selected_class"):
        st.session_state.selected_class = selected_class
        st.session_state.selected_subject = None
        st.rerun()

subjects = firebase_service.get_subjects(institution, selected_class)
if not subjects:
    st.warning(f"⚠️ No subjects found for class '{selected_class}'. Please add subjects under **Create Class** first.")
    st.stop()

subject_names = sorted(list(subjects.keys()))

with col_subject:
    default_s_idx = 0
    if st.session_state.get("selected_subject") in subject_names:
        default_s_idx = subject_names.index(st.session_state.selected_subject)

    selected_subject = st.selectbox(
        "Select Subject",
        options=subject_names,
        index=default_s_idx,
        key="attendance_subject_select"
    )
    if selected_subject != st.session_state.get("selected_subject"):
        st.session_state.selected_subject = selected_subject
        st.rerun()

# Fetch students for this class
student_data = firebase_service.get_students(institution, selected_class)
students_with_embeddings = {
    roll: s for roll, s in student_data.items()
    if s.get("embeddings") and isinstance(s.get("embeddings"), list)
}

if not student_data:
    st.warning(f"⚠️ No students found in class '{selected_class}'. Please register students under **Create Class**.")
    st.stop()

if not students_with_embeddings:
    st.error("⚠️ Students exist in this class, but none have facial embedding data registered. Please re-register students with face images.")
    st.stop()

st.markdown("---")

# Attendance Configuration & Mode
st.subheader(f"Attendance Session: {selected_class} ➔ {selected_subject}")

threshold = config.FACE_MATCH_THRESHOLD
with st.expander("⚙️ Detection Settings", expanded=False):
    threshold = st.slider(
        "Face Match Similarity Threshold (higher = stricter)",
        min_value=0.40,
        max_value=0.90,
        value=config.FACE_MATCH_THRESHOLD,
        step=0.02,
        help="Cosine similarity threshold for recognizing a registered student face."
    )

mode = st.radio(
    "Select Attendance Capture Method:",
    options=["Browser Camera (Fast Snapshot)", "Upload Classroom Photo", "Desktop Live Webcam (OpenCV Window)"],
    horizontal=True,
    key="attendance_mode_radio"
)


def process_attendance_frame(frame_bgr, threshold_val):
    """Processes a single BGR frame, detects all faces, matches against registered students,
    and returns recognized roll numbers with match details.
    """
    embeddings, err = firebase_service.extract_face_embeddings_from_image(frame_bgr, enforce_single_face=False)
    if not embeddings:
        return set(), {}, err or "No faces detected in the image."

    recognized_rolls = set()
    match_details = {}

    for face_emb in embeddings:
        best_match_roll = None
        best_similarity = -1.0

        for roll_num, student in students_with_embeddings.items():
            stored_emb = student.get("embeddings")
            sim = firebase_service.cosine_similarity(face_emb, stored_emb)
            if sim > best_similarity:
                best_similarity = sim
                best_match_roll = roll_num

        if best_match_roll and best_similarity >= threshold_val:
            recognized_rolls.add(best_match_roll)
            match_details[best_match_roll] = {
                "name": students_with_embeddings[best_match_roll].get("name", "Unknown"),
                "similarity": round(best_similarity, 3)
            }

    return recognized_rolls, match_details, None


# --- MODE 1: BROWSER CAMERA ---
if mode == "Browser Camera (Fast Snapshot)":
    st.info("Point camera towards students and capture a snapshot. Multiple faces are recognized simultaneously.")
    cam_input = st.camera_input("Take Attendance Snapshot", key="attendance_browser_cam")
    if cam_input is not None:
        img_bytes = cam_input.getvalue()
        frame = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)

        with st.spinner("Analyzing faces and verifying against registered students..."):
            recognized_rolls, match_details, err = process_attendance_frame(frame, threshold)

        if err:
            st.error(f"❌ {err}")
        else:
            marked_count, marked_names = firebase_service.mark_attendance(
                institution, selected_class, selected_subject, recognized_rolls, student_data
            )
            st.success(f"🎉 Attendance Processed! Recognized {len(recognized_rolls)} student(s).")

            # Summary Table
            summary_rows = []
            for roll, s_info in student_data.items():
                is_present = roll in recognized_rolls
                sim_score = match_details[roll]["similarity"] if is_present and roll in match_details else "N/A"
                summary_rows.append({
                    "Roll Number": roll,
                    "Student Name": s_info.get("name", "Unknown"),
                    "Status": "✅ Present" if is_present else "❌ Absent",
                    "Similarity Score": sim_score
                })
            st.dataframe(summary_rows, use_container_width=True)


# --- MODE 2: UPLOAD PHOTO ---
elif mode == "Upload Classroom Photo":
    st.info("Upload a photo containing one or more students to mark attendance.")
    uploaded_photo = st.file_uploader("Upload Classroom Image", type=["jpg", "jpeg", "png"], key="attendance_file_upload")
    if uploaded_photo is not None:
        img_bytes = uploaded_photo.getvalue()
        frame = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)

        with st.spinner("Scanning uploaded photo for registered student faces..."):
            recognized_rolls, match_details, err = process_attendance_frame(frame, threshold)

        if err:
            st.error(f"❌ {err}")
        else:
            marked_count, marked_names = firebase_service.mark_attendance(
                institution, selected_class, selected_subject, recognized_rolls, student_data
            )
            st.success(f"🎉 Attendance Processed! Recognized {len(recognized_rolls)} student(s).")

            summary_rows = []
            for roll, s_info in student_data.items():
                is_present = roll in recognized_rolls
                sim_score = match_details[roll]["similarity"] if is_present and roll in match_details else "N/A"
                summary_rows.append({
                    "Roll Number": roll,
                    "Student Name": s_info.get("name", "Unknown"),
                    "Status": "✅ Present" if is_present else "❌ Absent",
                    "Similarity Score": sim_score
                })
            st.dataframe(summary_rows, use_container_width=True)


# --- MODE 3: DESKTOP LIVE WEBCAM ---
elif mode == "Desktop Live Webcam (OpenCV Window)":
    st.info("Runs real-time face attendance using your local desktop webcam. Press **'q'** in the camera window to stop.")
    session_timeout = config.ATTENDANCE_SESSION_TIMEOUT_SECONDS

    if st.button("🚀 Start Desktop Webcam Session", type="primary", key="btn_start_live_attendance"):
        status_box = st.empty()
        status_box.info("Opening webcam window on desktop...")

        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                st.error("Failed to access local desktop webcam. Please verify camera connection or use 'Browser Camera' mode.")
            else:
                start_time = datetime.now()
                recognized_roll_numbers = set()
                match_scores = {}
                frame_count = 0

                status_box.warning("Webcam running! Look at the camera. Press 'q' in the camera window to finish.")

                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break

                    frame_count += 1
                    # Process face embeddings every 3 frames to maintain high video frame rate
                    if frame_count % 3 == 0:
                        rec_rolls, matches, _ = process_attendance_frame(frame, threshold)
                        for r in rec_rolls:
                            recognized_roll_numbers.add(r)
                            if r in matches:
                                match_scores[r] = matches[r]["similarity"]

                    # Display on-screen overlay of recognized names
                    overlay_y = 30
                    for roll in list(recognized_roll_numbers)[-5:]:
                        name = student_data.get(roll, {}).get("name", roll)
                        cv2.putText(
                            frame, f"Present: {name} ({roll})",
                            (10, overlay_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
                        )
                        overlay_y += 30

                    cv2.imshow("Taking Attendance - Press 'q' to stop", frame)

                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break

                    # Auto timeout
                    if (datetime.now() - start_time) >= timedelta(seconds=session_timeout):
                        break

                cap.release()
                cv2.destroyAllWindows()

                # Mark attendance in database
                marked_count, marked_names = firebase_service.mark_attendance(
                    institution, selected_class, selected_subject, recognized_roll_numbers, student_data
                )

                status_box.success(f"✅ Session ended. Successfully marked attendance for {marked_count} student(s)!")

                summary_rows = []
                for roll, s_info in student_data.items():
                    is_present = roll in recognized_roll_numbers
                    sim_score = match_scores.get(roll, "N/A")
                    summary_rows.append({
                        "Roll Number": roll,
                        "Student Name": s_info.get("name", "Unknown"),
                        "Status": "✅ Present" if is_present else "❌ Absent",
                        "Similarity Score": sim_score
                    })
                st.dataframe(summary_rows, use_container_width=True)

        except Exception as ex:
            logger.exception("Webcam attendance session failed.")
            st.error(f"Live webcam session error: {ex}")
