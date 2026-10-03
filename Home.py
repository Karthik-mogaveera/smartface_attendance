import streamlit as st
import pandas as pd
import io
import logging
from datetime import datetime
import config
import firebase_service

# Configure logging
logger = logging.getLogger("smartface.home")

# Page configuration
st.set_page_config(
    page_title="SmartFace Attendance System",
    page_icon="🎓",
    layout="wide"
)

# Initialize Firebase safely
firebase_ok, firebase_msg = config.init_firebase()
if not firebase_ok:
    st.error(f"⚠️ System Configuration Error:\n\n{firebase_msg}")
    st.info("Please verify your `.env` file settings (FIREBASE_DATABASE_URL and FIREBASE_CREDENTIALS_PATH).")
    st.stop()

# Initialize Session State
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "institution" not in st.session_state:
    st.session_state.institution = None
if "page" not in st.session_state:
    st.session_state.page = "login"
if "class_name" not in st.session_state:
    st.session_state.class_name = None
if "selected_subject" not in st.session_state:
    st.session_state.selected_subject = None


def login():
    st.title("🎓 SmartFace Attendance - Login")
    
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.subheader("Institution Login")
            email = st.text_input("Email Address", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Login", use_container_width=True):
                    if not email or not password:
                        st.error("Please provide both email and password.")
                    else:
                        success, inst_name, err = firebase_service.login_user(email, password)
                        if success and inst_name:
                            st.session_state.authenticated = True
                            st.session_state.institution = inst_name
                            st.session_state.class_name = None
                            st.session_state.selected_subject = None
                            st.success(f"Welcome back, {inst_name}!")
                            st.rerun()
                        else:
                            st.error(err or "Incorrect email or password.")
            
            with c2:
                if st.button("Create Account", use_container_width=True):
                    st.session_state.page = "signup"
                    st.rerun()


def signup():
    st.title("🎓 SmartFace Attendance - Sign Up")
    
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.subheader("Register Institution")
            institution = st.text_input("Institution Name", key="signup_institution")
            email = st.text_input("Email Address", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            confirm_password = st.text_input("Confirm Password", type="password", key="signup_confirm_password")
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Sign Up", use_container_width=True):
                    success, msg = firebase_service.register_institution(
                        institution, email, password, confirm_password
                    )
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.institution = institution.strip()
                        st.session_state.class_name = None
                        st.session_state.selected_subject = None
                        st.success("Account created successfully!")
                        st.rerun()
                    else:
                        st.error(msg)
            
            with c2:
                if st.button("Back to Login", use_container_width=True):
                    st.session_state.page = "login"
                    st.rerun()


def dashboard():
    st.title("📊 SmartFace Attendance Dashboard")
    
    top_c1, top_c2 = st.columns([4, 1])
    with top_c1:
        st.subheader(f"Institution: **{st.session_state.institution}**")
    with top_c2:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.institution = None
            st.session_state.class_name = None
            st.session_state.selected_subject = None
            st.session_state.page = "login"
            st.rerun()

    st.markdown("---")

    # Fetch classes
    classes = firebase_service.get_classes(st.session_state.institution)
    if not classes:
        st.info("ℹ️ No classes found for your institution. Please navigate to **Create Class** from the sidebar to set up your first class.")
        return

    class_names = sorted(list(classes.keys()))
    
    # Class and Subject selector
    col_class, col_subject = st.columns(2)
    
    with col_class:
        # Default index
        default_class_idx = 0
        if st.session_state.class_name in class_names:
            default_class_idx = class_names.index(st.session_state.class_name)
            
        selected_class = st.selectbox(
            "Select Class",
            options=class_names,
            index=default_class_idx,
            key="dashboard_class_select"
        )
        if selected_class != st.session_state.class_name:
            st.session_state.class_name = selected_class
            st.session_state.selected_subject = None
            st.rerun()

    subjects = firebase_service.get_subjects(st.session_state.institution, selected_class)
    
    with col_subject:
        if not subjects:
            st.warning("⚠️ No subjects found in this class. Please add subjects under **Create Class**.")
            return

        subject_names = sorted(list(subjects.keys()))
        default_subj_idx = 0
        if st.session_state.selected_subject in subject_names:
            default_subj_idx = subject_names.index(st.session_state.selected_subject)

        selected_subj = st.selectbox(
            "Select Subject",
            options=subject_names,
            index=default_subj_idx,
            key="dashboard_subject_select"
        )
        if selected_subj != st.session_state.selected_subject:
            st.session_state.selected_subject = selected_subj
            st.rerun()

    if selected_class and selected_subj:
        display_attendance_table(selected_class, selected_subj)


def display_attendance_table(class_name: str, subject_name: str):
    st.markdown("---")
    st.header(f"📋 Attendance Sheet: {class_name} - {subject_name}")
    institution = st.session_state.institution

    # Fetch students safely
    students = firebase_service.get_students(institution, class_name)
    if not students:
        st.info(f"ℹ️ No students are registered in class '{class_name}'. Please register students under **Create Class**.")
        return

    # Fetch attendance records safely
    attendance_data = firebase_service.get_attendance(institution, class_name, subject_name)
    all_dates = sorted(list(attendance_data.keys()))

    # Build attendance table rows
    table_data = []
    total_present_count = 0
    total_entries_count = len(students) * len(all_dates) if all_dates else 0

    # Sort students by roll number
    def roll_sort_key(roll):
        try:
            return (0, int(roll))
        except ValueError:
            return (1, str(roll))

    sorted_rolls = sorted(list(students.keys()), key=roll_sort_key)

    for roll in sorted_rolls:
        student = students[roll]
        student_name = student.get("name", "Unknown")
        student_roll = student.get("roll_number", roll)
        
        row = {
            "Roll No": student_roll,
            "Student Name": student_name,
        }
        
        student_presents = 0
        for date in all_dates:
            date_records = attendance_data.get(date, {})
            if isinstance(date_records, dict) and roll in date_records and date_records[roll].get("status") == "Present":
                row[date] = "Present"
                student_presents += 1
                total_present_count += 1
            else:
                row[date] = "Absent"
        
        if all_dates:
            pct = round((student_presents / len(all_dates)) * 100, 1)
            row["Attendance %"] = f"{pct}%"
            
        table_data.append(row)

    df = pd.DataFrame(table_data)

    # Display Metrics Summary
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Students", len(students))
    with m2:
        st.metric("Recorded Sessions", len(all_dates))
    with m3:
        overall_pct = round((total_present_count / total_entries_count) * 100, 1) if total_entries_count > 0 else 0.0
        st.metric("Overall Attendance", f"{overall_pct}%")
    with m4:
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_present = 0
        if today_str in attendance_data and isinstance(attendance_data[today_str], dict):
            today_present = sum(1 for r in attendance_data[today_str].values() if isinstance(r, dict) and r.get("status") == "Present")
        st.metric("Today's Present", f"{today_present} / {len(students)}")

    if not all_dates:
        st.warning("⚠️ No attendance has been recorded for this subject yet. Start a session under **Take Attendance**.")

    # Show Attendance Dataframe
    st.dataframe(df, use_container_width=True)

    # Export Section
    st.subheader("📥 Export Attendance")
    e_col1, e_col2 = st.columns(2)
    
    with e_col1:
        # In-memory Excel generation using openpyxl
        try:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Attendance")
            excel_bytes = excel_buffer.getvalue()
            
            st.download_button(
                label="📊 Download Excel Report (.xlsx)",
                data=excel_bytes,
                file_name=f"{class_name}_{subject_name}_attendance_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Error generating Excel file: {e}")

    with e_col2:
        # CSV generation
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📄 Download CSV Report (.csv)",
            data=csv_bytes,
            file_name=f"{class_name}_{subject_name}_attendance_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )


# Navigation router
if not st.session_state.authenticated:
    if st.session_state.page == "signup":
        signup()
    else:
        login()
else:
    dashboard()
