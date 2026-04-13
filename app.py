"""
Student Performance Tracker — Phase 3 (Complete)
Author: Adewale Samson Adeagbo
Purpose: Upload a student result CSV and instantly see class analytics,
         individual student trends, at-risk alerts, and topic/question analysis.

HOW TO RUN:
    streamlit run app.py

BASIC CSV COLUMNS (Phases 1 & 2):
    student_name, student_class, subject, score, total, date (DD/MM/YYYY)

EXTENDED CSV COLUMNS (Phase 3 — optional, enables Tab 4):
    student_name, student_class, subject, score, total, date, topic, q1, q2, ... qN
    topic  — the topic this exam covered (e.g. "Quadratic Equations")
    q1..qN — 1 = student got this question right, 0 = wrong

CHANGELOG:
    v1.0 — Phase 1: Core analytics (class average, charts, top/bottom students)
    v2.0 — Phase 2: Individual student profiles, date range filter, at-risk alerts
    v3.0 — Phase 3: Question miss analysis, topic weakness summary
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ─────────────────────────────────────────────
# PAGE CONFIGURATION
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Student Performance Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────
st.markdown("""
    <style>
        .main { background-color: #f8f9fa; }

        div[data-testid="metric-container"] {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 16px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.06);
        }

        h2, h3 { color: #1a1a2e; }
        .dataframe { font-size: 14px; }
    </style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# ═══════════════════════════════════════════
#   HELPER FUNCTIONS
# ═══════════════════════════════════════════
# ─────────────────────────────────────────────

def load_and_validate(uploaded_file):
    """
    Reads the uploaded CSV into a pandas DataFrame.
    Works for both basic (Phases 1 & 2) and extended (Phase 3) CSV formats.

    For Phase 3, the CSV may have extra columns:
      - 'topic': the topic covered in this exam
      - 'q1', 'q2', ... 'qN': 1=correct, 0=wrong for each question

    Returns: (dataframe, error_message, question_columns)
      - question_columns: list of question column names found (e.g. ['q1','q2',...])
        This is empty [] if no question columns exist (basic format).
    """
    required_columns = {"student_name", "student_class", "subject", "score", "total", "date"}

    try:
        df = pd.read_csv(uploaded_file)
    except Exception as e:
        return None, f"Could not read the file: {e}", []

    # Clean column names
    df.columns = df.columns.str.strip().str.lower()

    missing = required_columns - set(df.columns)
    if missing:
        return None, f"Missing columns: {', '.join(missing)}. Please check your CSV.", []

    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df["total"] = pd.to_numeric(df["total"], errors="coerce")
    df = df.dropna(subset=["score", "total"])

    df["percentage"] = (df["score"] / df["total"] * 100).round(2)
    df["status"] = df["percentage"].apply(lambda p: "Pass" if p >= 50 else "Fail")
    df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y", errors="coerce")
    df = df.sort_values("date")

    # ── PHASE 3: Detect question columns ──────
    # Question columns follow the pattern: q1, q2, q3 ... q99
    # We find them automatically so the CSV can have any number of questions.
    question_cols = [
        col for col in df.columns
        if col.startswith("q") and col[1:].isdigit()
    ]

    # Sort them numerically: q1, q2, ..., q10 (not q1, q10, q2 alphabetically)
    question_cols = sorted(question_cols, key=lambda c: int(c[1:]))

    # Convert question columns to numeric (in case they came in as strings)
    for col in question_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    return df, None, question_cols


def compute_summary(df):
    """Returns a dictionary of top-level summary metrics."""
    total_records  = len(df)
    unique_students = df["student_name"].nunique()
    class_avg      = df["percentage"].mean()
    pass_count     = (df["status"] == "Pass").sum()
    fail_count     = (df["status"] == "Fail").sum()
    pass_rate      = (pass_count / total_records * 100) if total_records > 0 else 0

    return {
        "total_records":   total_records,
        "unique_students": unique_students,
        "class_avg":       round(class_avg, 1),
        "pass_count":      int(pass_count),
        "fail_count":      int(fail_count),
        "pass_rate":       round(pass_rate, 1),
    }


def get_top_bottom_students(df, n=5):
    """Returns top N and bottom N students by average percentage."""
    student_avg = (
        df.groupby("student_name")["percentage"]
        .mean().round(1).reset_index()
        .rename(columns={"student_name": "Student", "percentage": "Avg %"})
        .sort_values("Avg %", ascending=False)
    )
    top    = student_avg.head(n).reset_index(drop=True)
    bottom = student_avg.tail(n).sort_values("Avg %").reset_index(drop=True)
    top.index    = top.index + 1
    bottom.index = bottom.index + 1
    return top, bottom


def get_at_risk_students(df, threshold=40, min_failures=2):
    """
    Flags students who scored below `threshold`% in `min_failures`+ exams.
    Returns a DataFrame of at-risk students with their weak subjects.
    """
    df = df.copy()
    df["is_low"]   = df["percentage"] < threshold
    low_records    = df[df["is_low"]]

    grouped = df.groupby("student_name").agg(
        low_score_count=("is_low", "sum"),
        avg_percentage =("percentage", "mean"),
        total_exams    =("percentage", "count"),
    ).reset_index()

    weak_subjects = (
        low_records.groupby("student_name")["subject"]
        .apply(lambda s: ", ".join(sorted(s.unique())))
        .reset_index()
        .rename(columns={"subject": "Weak Subjects"})
    )

    risk_summary = grouped.merge(weak_subjects, on="student_name", how="left")
    at_risk = risk_summary[risk_summary["low_score_count"] >= min_failures].copy()
    at_risk["avg_percentage"] = at_risk["avg_percentage"].round(1)
    at_risk = at_risk.sort_values("low_score_count", ascending=False)
    at_risk = at_risk.rename(columns={
        "student_name":   "Student",
        "low_score_count": f"Scores Below {threshold}%",
        "avg_percentage":  "Avg %",
        "total_exams":     "Total Exams",
    })
    return at_risk.reset_index(drop=True)


def get_student_profile(df, student_name):
    """Filters to one student and returns their records + summary stats."""
    student_df = df[df["student_name"] == student_name].copy()
    summary = {
        "total_exams":    len(student_df),
        "avg_percentage": round(student_df["percentage"].mean(), 1),
        "highest":        round(student_df["percentage"].max(), 1),
        "lowest":         round(student_df["percentage"].min(), 1),
        "pass_count":     int((student_df["status"] == "Pass").sum()),
        "fail_count":     int((student_df["status"] == "Fail").sum()),
    }
    return student_df, summary


# ── PHASE 3 FUNCTIONS ─────────────────────────────────────────────────────────

def get_question_miss_rate(df, question_cols):
    """
    NEW in Phase 3.
    Calculates how often each question was missed (got wrong) across all students.

    How it works:
    - Each question column contains 1 (correct) or 0 (wrong)
    - For each question, count total attempts and total wrong answers
    - Miss rate = (wrong answers ÷ total attempts) × 100

    Returns a DataFrame: question, miss_rate (%), times_wrong, times_attempted
    """
    records = []

    for col in question_cols:
        # Only use rows where the question column has a valid value (0 or 1)
        valid = df[col].dropna()
        total_attempts = len(valid)

        if total_attempts == 0:
            continue

        times_wrong  = int((valid == 0).sum())    # count of 0s = wrong answers
        times_correct = int((valid == 1).sum())   # count of 1s = correct answers
        miss_rate    = round(times_wrong / total_attempts * 100, 1)

        records.append({
            "Question":         col.upper(),   # display as Q1, Q2 etc.
            "Miss Rate (%)":    miss_rate,
            "Times Wrong":      times_wrong,
            "Times Correct":    times_correct,
            "Total Attempts":   total_attempts,
        })

    result = pd.DataFrame(records).sort_values("Miss Rate (%)", ascending=False)
    return result.reset_index(drop=True)


def get_topic_weakness(df, question_cols):
    """
    NEW in Phase 3.
    Groups results by topic and calculates average score and miss rate per topic.
    Requires the 'topic' column to be present in the CSV.

    Returns a DataFrame: topic, avg_score, avg_miss_rate, student_count
    """
    if "topic" not in df.columns:
        return pd.DataFrame()    # no topic column — return empty

    # Strip and clean topic names (extra spaces are common when typing)
    df = df.copy()
    df["topic"] = df["topic"].astype(str).str.strip()

    # Basic topic summary from the score/percentage columns
    topic_score = df.groupby("topic").agg(
        avg_score    =("percentage", "mean"),
        student_count=("student_name", "nunique"),
        exam_count   =("percentage", "count"),
    ).reset_index()

    topic_score["avg_score"] = topic_score["avg_score"].round(1)

    # If question columns exist, compute average miss rate per topic
    if question_cols:
        miss_rates = []

        for topic_name, group in df.groupby("topic"):
            all_answers = group[question_cols].values.flatten()
            valid       = all_answers[~pd.isna(all_answers)]

            if len(valid) == 0:
                avg_miss = None
            else:
                # Miss rate = proportion of 0s in all question answers for this topic
                avg_miss = round((valid == 0).sum() / len(valid) * 100, 1)

            miss_rates.append({"topic": topic_name, "avg_miss_rate": avg_miss})

        miss_df    = pd.DataFrame(miss_rates)
        topic_score = topic_score.merge(miss_df, on="topic", how="left")

    # Sort worst topics first (lowest average score)
    topic_score = topic_score.sort_values("avg_score", ascending=True)

    topic_score = topic_score.rename(columns={
        "topic":        "Topic",
        "avg_score":    "Avg Score (%)",
        "student_count":"Students",
        "exam_count":   "Exam Records",
    })

    if "avg_miss_rate" in topic_score.columns:
        topic_score = topic_score.rename(columns={"avg_miss_rate": "Avg Miss Rate (%)"})

    return topic_score.reset_index(drop=True)


def get_student_question_detail(df, question_cols, student_name):
    """
    NEW in Phase 3.
    Returns a detailed question-by-question breakdown for a single student.

    For each question, shows:
    - How the student answered (1=correct, 0=wrong)
    - Class average for that question (so you can compare)
    - The topic the question belonged to (if available)
    """
    student_rows = df[df["student_name"] == student_name]

    records = []
    for col in question_cols:
        q_label = col.upper()

        # Student's answers for this question across all their exams
        student_answers = student_rows[col].dropna()
        if student_answers.empty:
            continue

        # For each exam row, record how this student did on this question
        for _, row in student_rows.iterrows():
            val = row.get(col)
            if pd.isna(val):
                continue

            topic = row.get("topic", "—") if "topic" in df.columns else "—"

            # Class average for this question on the same exam date
            same_exam = df[
                (df["subject"] == row["subject"]) &
                (df["date"] == row["date"])
            ]
            class_avg_q = same_exam[col].mean()

            records.append({
                "Question":        q_label,
                "Topic":           str(topic).strip(),
                "Student Answer":  "✅ Correct" if int(val) == 1 else "❌ Wrong",
                "Class Avg (%)":   round(class_avg_q * 100, 1) if pd.notna(class_avg_q) else None,
                "Subject":         row.get("subject", ""),
                "Date":            row["date"].strftime("%d/%m/%Y") if pd.notna(row["date"]) else "",
            })

    return pd.DataFrame(records)


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/graduation-cap.png", width=60)
    st.title("📊 Performance Tracker")
    st.caption("By Adewale Samson Adeagbo")
    st.divider()

    st.subheader("1. Upload Your Results")
    uploaded_file = st.file_uploader(
        "Choose a CSV file",
        type=["csv"],
        help="Basic: student_name, student_class, subject, score, total, date\n"
             "Phase 3: add 'topic' and q1, q2, ... columns"
    )

    st.divider()

    # ── SAMPLE CSV (Phase 3 extended format) ──
    # This sample includes topic and q1–q10 columns so all 4 tabs work.
    sample_csv = """student_name,student_class,subject,score,total,date,topic,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10
Amara Okonkwo,SS1A,Mathematics,7,10,15/01/2025,Quadratic Equations,1,1,0,1,1,1,0,1,1,0
Tunde Adeyemi,SS1A,Mathematics,4,10,15/01/2025,Quadratic Equations,1,0,0,1,0,1,0,1,0,0
Chisom Eze,SS1A,Mathematics,9,10,15/01/2025,Quadratic Equations,1,1,1,1,1,1,0,1,1,1
Fatima Bello,SS1A,Mathematics,3,10,15/01/2025,Quadratic Equations,0,0,0,1,1,0,0,1,0,0
Emeka Nwosu,SS1A,Mathematics,6,10,15/01/2025,Quadratic Equations,1,1,0,1,0,1,0,1,1,0
Kemi Oladele,SS1A,Mathematics,5,10,15/01/2025,Quadratic Equations,1,0,0,1,1,1,0,0,1,0
Seun Fashola,SS1A,Mathematics,4,10,15/01/2025,Quadratic Equations,0,1,0,1,0,1,0,0,1,0
Ngozi Obi,SS1A,Mathematics,8,10,15/01/2025,Quadratic Equations,1,1,1,1,1,0,0,1,1,1
Dami Afolabi,SS1A,Mathematics,2,10,15/01/2025,Quadratic Equations,0,0,0,1,0,0,0,1,0,0
Tobi Martins,SS1A,Mathematics,9,10,15/01/2025,Quadratic Equations,1,1,1,1,1,1,0,1,1,1
Amara Okonkwo,SS1A,Physics,7,10,22/01/2025,Newton's Laws,1,1,0,1,1,0,1,1,1,0
Tunde Adeyemi,SS1A,Physics,5,10,22/01/2025,Newton's Laws,1,0,1,1,0,0,1,1,0,0
Chisom Eze,SS1A,Physics,8,10,22/01/2025,Newton's Laws,1,1,1,1,1,0,1,0,1,1
Fatima Bello,SS1A,Physics,3,10,22/01/2025,Newton's Laws,0,0,1,1,0,0,0,1,0,0
Emeka Nwosu,SS1A,Physics,6,10,22/01/2025,Newton's Laws,1,1,0,1,1,0,1,0,1,0
Kemi Oladele,SS1A,Physics,5,10,22/01/2025,Newton's Laws,1,0,0,1,1,0,1,0,1,0
Seun Fashola,SS1A,Physics,3,10,22/01/2025,Newton's Laws,0,0,1,1,0,0,0,1,0,0
Ngozi Obi,SS1A,Physics,8,10,22/01/2025,Newton's Laws,1,1,1,1,1,0,1,0,1,1
Dami Afolabi,SS1A,Physics,2,10,22/01/2025,Newton's Laws,0,0,0,1,0,0,0,1,0,0
Tobi Martins,SS1A,Physics,9,10,22/01/2025,Newton's Laws,1,1,1,1,1,1,1,0,1,1
Amara Okonkwo,SS1A,Chemistry,6,10,29/01/2025,Chemical Bonding,1,1,0,0,1,1,0,1,1,0
Tunde Adeyemi,SS1A,Chemistry,4,10,29/01/2025,Chemical Bonding,1,0,0,0,1,1,0,1,0,0
Chisom Eze,SS1A,Chemistry,8,10,29/01/2025,Chemical Bonding,1,1,0,1,1,1,1,1,1,0
Fatima Bello,SS1A,Chemistry,3,10,29/01/2025,Chemical Bonding,0,0,0,0,1,1,0,1,0,0
Emeka Nwosu,SS1A,Chemistry,7,10,29/01/2025,Chemical Bonding,1,1,0,1,1,1,0,1,1,0
Kemi Oladele,SS1A,Chemistry,5,10,29/01/2025,Chemical Bonding,1,0,0,1,1,1,0,0,1,0
Seun Fashola,SS1A,Chemistry,3,10,29/01/2025,Chemical Bonding,0,0,0,0,1,1,0,1,0,0
Ngozi Obi,SS1A,Chemistry,8,10,29/01/2025,Chemical Bonding,1,1,0,1,1,1,1,1,1,0
Dami Afolabi,SS1A,Chemistry,2,10,29/01/2025,Chemical Bonding,0,0,0,0,1,0,0,1,0,0
Tobi Martins,SS1A,Chemistry,9,10,29/01/2025,Chemical Bonding,1,1,1,1,1,1,1,1,1,0
Amara Okonkwo,SS1A,Mathematics,8,10,05/02/2025,Indices & Logarithms,1,1,1,1,1,0,1,1,1,0
Tunde Adeyemi,SS1A,Mathematics,5,10,05/02/2025,Indices & Logarithms,1,0,1,1,0,0,1,1,0,0
Chisom Eze,SS1A,Mathematics,9,10,05/02/2025,Indices & Logarithms,1,1,1,1,1,1,1,1,1,0
Fatima Bello,SS1A,Mathematics,3,10,05/02/2025,Indices & Logarithms,0,0,1,1,0,0,0,1,0,0
Emeka Nwosu,SS1A,Mathematics,7,10,05/02/2025,Indices & Logarithms,1,1,0,1,1,0,1,1,1,0
Kemi Oladele,SS1A,Mathematics,6,10,05/02/2025,Indices & Logarithms,1,1,0,1,1,0,1,0,1,0
Seun Fashola,SS1A,Mathematics,4,10,05/02/2025,Indices & Logarithms,0,0,1,1,0,0,1,1,0,0
Ngozi Obi,SS1A,Mathematics,9,10,05/02/2025,Indices & Logarithms,1,1,1,1,1,0,1,1,1,1
Dami Afolabi,SS1A,Mathematics,2,10,05/02/2025,Indices & Logarithms,0,0,0,1,0,0,0,1,0,0
Tobi Martins,SS1A,Mathematics,10,10,05/02/2025,Indices & Logarithms,1,1,1,1,1,1,1,1,1,1
Amara Okonkwo,SS1A,Physics,7,10,12/02/2025,Waves & Sound,1,1,0,1,1,1,0,1,1,0
Tunde Adeyemi,SS1A,Physics,5,10,12/02/2025,Waves & Sound,1,0,0,1,1,1,0,0,1,0
Chisom Eze,SS1A,Physics,8,10,12/02/2025,Waves & Sound,1,1,1,1,1,1,0,0,1,1
Fatima Bello,SS1A,Physics,4,10,12/02/2025,Waves & Sound,0,0,0,1,1,1,0,0,1,0
Emeka Nwosu,SS1A,Physics,7,10,12/02/2025,Waves & Sound,1,1,0,1,1,1,0,1,1,0
Kemi Oladele,SS1A,Physics,5,10,12/02/2025,Waves & Sound,1,0,0,1,1,1,0,0,1,0
Seun Fashola,SS1A,Physics,4,10,12/02/2025,Waves & Sound,0,0,0,1,1,1,0,0,1,0
Ngozi Obi,SS1A,Physics,9,10,12/02/2025,Waves & Sound,1,1,1,1,1,1,0,1,1,1
Dami Afolabi,SS1A,Physics,2,10,12/02/2025,Waves & Sound,0,0,0,1,0,1,0,0,0,0
Tobi Martins,SS1A,Physics,9,10,12/02/2025,Waves & Sound,1,1,1,1,1,1,0,1,1,1
Amara Okonkwo,SS1A,Chemistry,6,10,19/02/2025,Acids & Bases,1,1,0,1,0,1,0,1,1,0
Tunde Adeyemi,SS1A,Chemistry,5,10,19/02/2025,Acids & Bases,1,0,1,1,0,1,0,1,0,0
Chisom Eze,SS1A,Chemistry,8,10,19/02/2025,Acids & Bases,1,1,1,1,0,1,0,1,1,1
Fatima Bello,SS1A,Chemistry,3,10,19/02/2025,Acids & Bases,0,0,1,1,0,1,0,0,0,0
Emeka Nwosu,SS1A,Chemistry,7,10,19/02/2025,Acids & Bases,1,1,0,1,1,1,0,1,1,0
Kemi Oladele,SS1A,Chemistry,6,10,19/02/2025,Acids & Bases,1,0,1,1,0,1,0,1,1,0
Seun Fashola,SS1A,Chemistry,4,10,19/02/2025,Acids & Bases,0,0,1,1,0,1,0,0,1,0
Ngozi Obi,SS1A,Chemistry,9,10,19/02/2025,Acids & Bases,1,1,1,1,0,1,0,1,1,1
Dami Afolabi,SS1A,Chemistry,2,10,19/02/2025,Acids & Bases,0,0,0,1,0,0,0,0,1,0
Tobi Martins,SS1A,Chemistry,9,10,19/02/2025,Acids & Bases,1,1,1,1,0,1,0,1,1,1
"""

    st.download_button(
        label="📥 Download Sample CSV (Phase 3)",
        data=sample_csv,
        file_name="sample_results_phase3.csv",
        mime="text/csv",
        help="Includes topic and q1–q10 columns to enable all 4 tabs"
    )

    st.divider()
    st.caption("✅ Phase 1 — Core Analytics")
    st.caption("✅ Phase 2 — Trends, Filters, At-Risk")
    st.caption("✅ Phase 3 — Topic & Question Analysis")


# ─────────────────────────────────────────────
# MAIN CONTENT
# ─────────────────────────────────────────────

st.title("🎓 Student Performance Tracker")
st.markdown("Upload your exam result CSV to generate instant analytics.")

# WELCOME SCREEN
if uploaded_file is None:
    st.info("👈 Upload a CSV file in the sidebar, or download the sample CSV to try it out.")

    st.subheader("CSV Formats Supported")

    col_basic, col_phase3 = st.columns(2)

    with col_basic:
        st.markdown("**Basic (Phases 1 & 2)**")
        basic_df = pd.DataFrame({
            "student_name": ["Amara Okonkwo"],
            "student_class": ["SS1A"],
            "subject": ["Mathematics"],
            "score": [72], "total": [100],
            "date": ["15/01/2025"],
        })
        st.dataframe(basic_df, use_container_width=True)

    with col_phase3:
        st.markdown("**Extended (Phase 3 — adds topic + question columns)**")
        p3_df = pd.DataFrame({
            "student_name": ["Amara Okonkwo"],
            "student_class": ["SS1A"],
            "subject": ["Mathematics"],
            "score": [7], "total": [10],
            "date": ["15/01/2025"],
            "topic": ["Quadratic Equations"],
            "q1": [1], "q2": [1], "q3": [0], "q4": [1], "q5": [0],
        })
        st.dataframe(p3_df, use_container_width=True)
        st.caption("q columns: 1 = correct, 0 = wrong")

    st.stop()


# LOAD AND VALIDATE
df, error, question_cols = load_and_validate(uploaded_file)

if error:
    st.error(f"❌ {error}")
    st.stop()

has_question_data = len(question_cols) > 0
has_topic_data    = "topic" in df.columns
has_valid_dates   = df["date"].notna().any()

# Status line
status_parts = [
    f"{len(df)} records",
    f"{df['student_name'].nunique()} students",
    f"{df['subject'].nunique()} subjects",
]
if has_question_data:
    status_parts.append(f"{len(question_cols)} question columns detected ✅")
if has_topic_data:
    status_parts.append("topic column detected ✅")

st.success("✅ File loaded — " + " | ".join(status_parts))

if not has_question_data:
    st.info(
        "💡 **Phase 3 tip:** Your CSV does not have question columns (q1, q2 ...). "
        "The Topic & Question Analysis tab will be limited. "
        "Add a 'topic' column and q1–qN columns (1=correct, 0=wrong) to unlock full Phase 3 features."
    )

# ─────────────────────────────────────────────
# GLOBAL FILTERS
# ─────────────────────────────────────────────
st.markdown("### 🔎 Filters")

all_classes  = sorted(df["student_class"].unique().tolist())
all_subjects = sorted(df["subject"].unique().tolist())

filter_cols = st.columns([1, 1, 2])

with filter_cols[0]:
    selected_class = st.selectbox("Class", ["All Classes"] + all_classes)

with filter_cols[1]:
    selected_subject = st.selectbox("Subject", ["All Subjects"] + all_subjects)

with filter_cols[2]:
    if has_valid_dates:
        min_date   = df["date"].min().date()
        max_date   = df["date"].max().date()
        date_range = st.date_input(
            "Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            help="Filter results to a specific date range — e.g. one term"
        )
    else:
        st.warning("Date column could not be parsed. Check format is DD/MM/YYYY.")
        date_range = ()

# Apply filters
filtered_df = df.copy()
if selected_class != "All Classes":
    filtered_df = filtered_df[filtered_df["student_class"] == selected_class]
if selected_subject != "All Subjects":
    filtered_df = filtered_df[filtered_df["subject"] == selected_subject]
if has_valid_dates and len(date_range) == 2:
    start_date, end_date = date_range
    filtered_df = filtered_df[
        (filtered_df["date"].dt.date >= start_date) &
        (filtered_df["date"].dt.date <= end_date)
    ]

if filtered_df.empty:
    st.warning("⚠️ No records match your selected filters.")
    st.stop()

st.divider()


# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📊  Class Overview",
    "👤  Student Profile",
    "🚨  At-Risk Students",
    "🔬  Topic & Question Analysis",
])


# ═══════════════════════════════════════════════
#   TAB 1 — CLASS OVERVIEW (Phase 1, unchanged)
# ═══════════════════════════════════════════════

with tab1:
    st.subheader("📌 Summary")
    summary = compute_summary(filtered_df)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Records",   summary["total_records"])
    m2.metric("Unique Students", summary["unique_students"])
    m3.metric("Class Average",   f"{summary['class_avg']}%")
    m4.metric("Pass Rate",       f"{summary['pass_rate']}%",
              delta=f"{summary['pass_count']} passed / {summary['fail_count']} failed")

    st.divider()

    st.subheader("📈 Charts")
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("**Score Distribution**")
        st.caption("How student scores are spread across percentage ranges")
        fig_hist = px.histogram(
            filtered_df, x="percentage", nbins=10,
            color_discrete_sequence=["#2563eb"],
            labels={"percentage": "Score (%)", "count": "Students"},
            template="plotly_white",
        )
        fig_hist.update_layout(
            margin=dict(t=20, b=20, l=0, r=0), bargap=0.1,
            yaxis_title="Number of Students", xaxis_title="Score (%)", showlegend=False,
        )
        fig_hist.add_vline(x=50, line_dash="dash", line_color="red",
                           annotation_text="Pass Mark (50%)", annotation_position="top right")
        st.plotly_chart(fig_hist, use_container_width=True)

    with chart_col2:
        st.markdown("**Pass / Fail Breakdown**")
        st.caption("Proportion of students who passed or failed")
        pass_fail_counts = filtered_df["status"].value_counts().reset_index()
        pass_fail_counts.columns = ["Status", "Count"]
        fig_pie = px.pie(
            pass_fail_counts, names="Status", values="Count", color="Status",
            color_discrete_map={"Pass": "#16a34a", "Fail": "#dc2626"},
            template="plotly_white", hole=0.4,
        )
        fig_pie.update_layout(
            margin=dict(t=20, b=20, l=0, r=0),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        )
        fig_pie.update_traces(textinfo="percent+label")
        st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    if selected_subject == "All Subjects" and len(all_subjects) > 1:
        st.subheader("📚 Average Score by Subject")
        subject_avg = (
            filtered_df.groupby("subject")["percentage"]
            .mean().round(1).reset_index()
            .sort_values("percentage", ascending=False)
        )
        fig_bar = px.bar(
            subject_avg, x="subject", y="percentage",
            color="percentage", color_continuous_scale="Blues",
            labels={"subject": "Subject", "percentage": "Average Score (%)"},
            template="plotly_white", text="percentage",
        )
        fig_bar.update_traces(texttemplate="%{text}%", textposition="outside")
        fig_bar.update_layout(margin=dict(t=20, b=20), coloraxis_showscale=False, yaxis_range=[0, 110])
        fig_bar.add_hline(y=50, line_dash="dash", line_color="red", annotation_text="Pass Mark")
        st.plotly_chart(fig_bar, use_container_width=True)
        st.divider()

    st.subheader("🏆 Top 5 & Bottom 5 Students")
    st.caption("Based on average percentage across all selected exams")
    top_students, bottom_students = get_top_bottom_students(filtered_df, n=5)
    rank_col1, rank_col2 = st.columns(2)

    with rank_col1:
        st.markdown("**🥇 Top 5 Students**")
        st.dataframe(top_students, use_container_width=True,
                     column_config={"Avg %": st.column_config.ProgressColumn(
                         "Avg %", min_value=0, max_value=100, format="%.1f%%")})

    with rank_col2:
        st.markdown("**⚠️ Bottom 5 Students — Need Attention**")
        st.dataframe(bottom_students, use_container_width=True,
                     column_config={"Avg %": st.column_config.ProgressColumn(
                         "Avg %", min_value=0, max_value=100, format="%.1f%%")})

    st.divider()

    st.subheader("📋 Full Result Table")
    with st.expander("Click to view all records"):
        display_cols = ["student_name", "student_class", "subject", "score", "total", "percentage", "status"]
        if has_topic_data:
            display_cols.insert(4, "topic")

        display_df = filtered_df[display_cols].rename(columns={
            "student_name": "Name", "student_class": "Class",
            "subject": "Subject", "topic": "Topic",
            "score": "Score", "total": "Total",
            "percentage": "%", "status": "Status",
        }).sort_values("Name")

        st.dataframe(display_df, use_container_width=True)
        csv_output = display_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Processed Results",
            data=csv_output, file_name="processed_results.csv", mime="text/csv"
        )


# ═══════════════════════════════════════════════
#   TAB 2 — STUDENT PROFILE (Phase 2, unchanged)
# ═══════════════════════════════════════════════

with tab2:
    st.subheader("👤 Individual Student Profile")
    st.caption("Select a student to see their performance across all exams over time.")

    all_students = sorted(filtered_df["student_name"].unique().tolist())

    if not all_students:
        st.warning("No students found with the current filters.")
    else:
        selected_student = st.selectbox(
            "Select Student", options=all_students,
            help="Choose a student to view their individual performance report"
        )

        student_df, student_summary = get_student_profile(filtered_df, selected_student)

        st.markdown(f"### Results for: **{selected_student}**")
        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("Total Exams",   student_summary["total_exams"])
        s2.metric("Average Score", f"{student_summary['avg_percentage']}%")
        s3.metric("Highest Score", f"{student_summary['highest']}%")
        s4.metric("Lowest Score",  f"{student_summary['lowest']}%")
        s5.metric("Pass / Fail",   f"{student_summary['pass_count']}P / {student_summary['fail_count']}F")

        st.divider()

        st.markdown("**📈 Score Trend Over Time**")
        st.caption("Each line is one subject. Hover to see exact date and score.")

        if has_valid_dates and student_df["date"].notna().any():
            trend_df = (
                student_df.groupby(["date", "subject"])["percentage"]
                .mean().round(1).reset_index()
            )
            fig_trend = px.line(
                trend_df, x="date", y="percentage", color="subject", markers=True,
                labels={"date": "Exam Date", "percentage": "Score (%)", "subject": "Subject"},
                template="plotly_white",
            )
            fig_trend.update_layout(
                margin=dict(t=20, b=20), yaxis_range=[0, 105],
                xaxis_title="Exam Date", yaxis_title="Score (%)", legend_title="Subject",
            )
            fig_trend.add_hline(y=50, line_dash="dash", line_color="red",
                                annotation_text="Pass Mark (50%)", annotation_position="top right")
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("Date information not available for trend chart.")

        st.divider()

        st.markdown("**📚 Average Score by Subject**")
        subject_breakdown = (
            student_df.groupby("subject")["percentage"]
            .mean().round(1).reset_index()
            .sort_values("percentage", ascending=True)
        )
        fig_subj = px.bar(
            subject_breakdown, x="percentage", y="subject", orientation="h",
            color="percentage",
            color_continuous_scale=["#dc2626", "#f59e0b", "#16a34a"],
            labels={"percentage": "Average Score (%)", "subject": "Subject"},
            template="plotly_white", text="percentage",
        )
        fig_subj.update_traces(texttemplate="%{text}%", textposition="outside")
        fig_subj.update_layout(margin=dict(t=20, b=20), coloraxis_showscale=False, xaxis_range=[0, 110])
        fig_subj.add_vline(x=50, line_dash="dash", line_color="red",
                           annotation_text="Pass Mark", annotation_position="top right")
        st.plotly_chart(fig_subj, use_container_width=True)

        st.divider()

        st.markdown("**📋 All Exam Records for This Student**")
        student_table = student_df[[
            "date", "subject", "score", "total", "percentage", "status"
        ]].rename(columns={
            "date": "Date", "subject": "Subject",
            "score": "Score", "total": "Total",
            "percentage": "%", "status": "Status",
        }).sort_values("Date", ascending=False)
        student_table["Date"] = student_table["Date"].dt.strftime("%d/%m/%Y")

        st.dataframe(student_table, use_container_width=True)
        csv_student = student_table.to_csv(index=False)
        st.download_button(
            label=f"📥 Download {selected_student}'s Report",
            data=csv_student,
            file_name=f"{selected_student.replace(' ', '_')}_report.csv",
            mime="text/csv"
        )


# ═══════════════════════════════════════════════
#   TAB 3 — AT-RISK STUDENTS (Phase 2, unchanged)
# ═══════════════════════════════════════════════

with tab3:
    st.subheader("🚨 At-Risk Student Alert")
    st.markdown("Flags students who may need **extra attention** based on repeated low scores.")

    risk_col1, risk_col2 = st.columns(2)
    with risk_col1:
        risk_threshold = st.slider(
            "Score threshold (%)", min_value=20, max_value=60, value=40, step=5,
            help="Scores below this percentage are counted as low"
        )
    with risk_col2:
        risk_min_failures = st.slider(
            "Minimum low scores to flag", min_value=1, max_value=5, value=2, step=1,
            help="How many times below threshold before a student is flagged"
        )

    st.caption(
        f"Flagging students who scored below **{risk_threshold}%** "
        f"in **{risk_min_failures} or more** exams."
    )
    st.divider()

    at_risk_df = get_at_risk_students(filtered_df, risk_threshold, risk_min_failures)

    if at_risk_df.empty:
        st.success(f"✅ No students flagged. (Below {risk_threshold}% in {risk_min_failures}+ exams)")
    else:
        st.error(
            f"⚠️ **{len(at_risk_df)} student(s) at risk** — "
            f"scored below {risk_threshold}% in {risk_min_failures}+ exams."
        )

        st.markdown("**At-Risk Student List**")
        st.dataframe(at_risk_df, use_container_width=True,
                     column_config={"Avg %": st.column_config.ProgressColumn(
                         "Avg %", min_value=0, max_value=100, format="%.1f%%")})

        st.divider()

        low_col_name = f"Scores Below {risk_threshold}%"
        fig_risk = px.bar(
            at_risk_df, x="Student", y=low_col_name, color="Avg %",
            color_continuous_scale=["#dc2626", "#f59e0b"],
            labels={low_col_name: "Times Below Threshold"}, template="plotly_white", text=low_col_name,
        )
        fig_risk.update_traces(textposition="outside")
        fig_risk.update_layout(margin=dict(t=20, b=80), xaxis_tickangle=-30)
        st.plotly_chart(fig_risk, use_container_width=True)

        st.divider()
        st.markdown("**📋 Suggested Next Steps**")
        st.markdown("""
        - 📌 **Speak individually** with each flagged student.
        - 📚 **Use the Student Profile tab** to see exactly which exams they struggled in.
        - 🔔 **Consider parent communication** if a student is below threshold in 3+ exams.
        - 📝 **Organise a remedial session** — group at-risk students by subject for targeted revision.
        """)

        csv_risk = at_risk_df.to_csv(index=False)
        st.download_button(
            label="📥 Download At-Risk Student List",
            data=csv_risk, file_name="at_risk_students.csv", mime="text/csv"
        )


# ═══════════════════════════════════════════════════
#   TAB 4 — TOPIC & QUESTION ANALYSIS (Phase 3, NEW)
# ═══════════════════════════════════════════════════

with tab4:
    st.subheader("🔬 Topic & Question Analysis")
    st.markdown(
        "Understand **which questions** the class missed most and **which topics** need more teaching time."
    )

    # ── CHECK IF PHASE 3 DATA IS AVAILABLE ────────────────────────────────────
    # This tab needs question columns (q1, q2 ...) and ideally a topic column.
    # We show helpful messages if the data is not there instead of crashing.
    if not has_question_data and not has_topic_data:
        st.warning(
            "⚠️ Your CSV does not have question or topic columns. "
            "Download the **Phase 3 sample CSV** from the sidebar to see this tab in action."
        )
        st.markdown("""
        **To use Phase 3, add these columns to your CSV:**
        - `topic` — the topic this exam covered (e.g. "Quadratic Equations")
        - `q1`, `q2`, `q3` ... `qN` — 1 = student got it right, 0 = wrong

        Everything else stays the same. Phase 3 adds to your existing CSV — it does not replace it.
        """)
        st.stop()

    # ── SECTION 1: MOST MISSED QUESTIONS ──────────────────────────────────────
    # This section answers: "Which specific questions are students getting wrong most?"
    # Useful for knowing which question to review in class.

    if has_question_data:
        st.markdown("---")
        st.markdown("### ❓ Most Missed Questions")
        st.caption(
            "Sorted by miss rate — the question at the top was wrong most often across all students. "
            "Use this to decide which questions to revisit in class."
        )

        miss_df = get_question_miss_rate(filtered_df, question_cols)

        if miss_df.empty:
            st.info("No question data found in the filtered records.")
        else:
            # ── MISS RATE BAR CHART ───────────────────────────────────────────
            # Each bar = one question. Height = % of students who got it wrong.
            # Colour goes green (easy) → red (hard / most missed).
            fig_miss = px.bar(
                miss_df,
                x="Question",
                y="Miss Rate (%)",
                color="Miss Rate (%)",
                # Reverse scale: low miss rate = green (good), high = red (problem)
                color_continuous_scale=["#16a34a", "#f59e0b", "#dc2626"],
                labels={"Question": "Question", "Miss Rate (%)": "Miss Rate (%)"},
                template="plotly_white",
                text="Miss Rate (%)",
            )
            fig_miss.update_traces(texttemplate="%{text}%", textposition="outside")
            fig_miss.update_layout(
                margin=dict(t=20, b=20),
                yaxis_range=[0, 110],
                coloraxis_showscale=False,
                xaxis=dict(categoryorder="total descending"),   # most missed on the left
            )

            # Draw a reference line at 50% miss rate — anything above is a serious problem
            fig_miss.add_hline(
                y=50, line_dash="dash", line_color="red",
                annotation_text="50% miss rate (serious concern)",
                annotation_position="top right"
            )
            st.plotly_chart(fig_miss, use_container_width=True)

            # ── MISS DETAIL TABLE ─────────────────────────────────────────────
            st.markdown("**Detailed Miss Rate Table**")
            st.dataframe(
                miss_df,
                use_container_width=True,
                column_config={
                    "Miss Rate (%)": st.column_config.ProgressColumn(
                        "Miss Rate (%)", min_value=0, max_value=100, format="%.1f%%"
                    ),
                }
            )

            # Insight: automatically name the hardest question
            hardest_q = miss_df.iloc[0]
            easiest_q = miss_df.iloc[-1]

            insight_col1, insight_col2 = st.columns(2)
            with insight_col1:
                st.error(
                    f"🔴 **Hardest question:** {hardest_q['Question']} — "
                    f"missed by **{hardest_q['Miss Rate (%)']}%** of students "
                    f"({hardest_q['Times Wrong']} out of {hardest_q['Total Attempts']})"
                )
            with insight_col2:
                st.success(
                    f"🟢 **Easiest question:** {easiest_q['Question']} — "
                    f"missed by only **{easiest_q['Miss Rate (%)']}%** of students "
                    f"({easiest_q['Times Wrong']} out of {easiest_q['Total Attempts']})"
                )

    # ── SECTION 2: TOPIC WEAKNESS SUMMARY ─────────────────────────────────────
    # This section answers: "Which topics are students performing worst in overall?"
    # Useful for planning future lessons — spend more time on weak topics.

    if has_topic_data:
        st.markdown("---")
        st.markdown("### 📚 Topic Weakness Summary")
        st.caption(
            "Topics sorted from weakest to strongest. "
            "The topic at the top needs the most attention."
        )

        topic_df = get_topic_weakness(filtered_df, question_cols)

        if topic_df.empty:
            st.info("No topic data found in the filtered records.")
        else:
            # ── TOPIC SCORE BAR CHART ─────────────────────────────────────────
            # Horizontal bar — easiest to read on a tablet with long topic names.
            # Colour goes red (low avg = weak) → green (high avg = strong).
            fig_topic = px.bar(
                topic_df,
                x="Avg Score (%)",
                y="Topic",
                orientation="h",
                color="Avg Score (%)",
                color_continuous_scale=["#dc2626", "#f59e0b", "#16a34a"],
                labels={"Avg Score (%)": "Average Score (%)", "Topic": "Topic"},
                template="plotly_white",
                text="Avg Score (%)",
            )
            fig_topic.update_traces(texttemplate="%{text}%", textposition="outside")
            fig_topic.update_layout(
                margin=dict(t=20, b=20),
                coloraxis_showscale=False,
                xaxis_range=[0, 115],
            )
            fig_topic.add_vline(
                x=50, line_dash="dash", line_color="red",
                annotation_text="Pass Mark", annotation_position="top right"
            )
            st.plotly_chart(fig_topic, use_container_width=True)

            # ── TOPIC DETAIL TABLE ────────────────────────────────────────────
            st.markdown("**Topic Summary Table**")
            st.dataframe(
                topic_df,
                use_container_width=True,
                column_config={
                    "Avg Score (%)": st.column_config.ProgressColumn(
                        "Avg Score (%)", min_value=0, max_value=100, format="%.1f%%"
                    ),
                }
            )

            # Download topic report
            csv_topics = topic_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Topic Weakness Report",
                data=csv_topics,
                file_name="topic_weakness_report.csv",
                mime="text/csv"
            )

            # Automatic insight: name the weakest topic
            weakest = topic_df.iloc[0]
            st.warning(
                f"⚠️ **Weakest topic: {weakest['Topic']}** — "
                f"class average is **{weakest['Avg Score (%)']}%** "
                f"across {weakest['Exam Records']} exam record(s). Consider revising this topic."
            )

    # ── SECTION 3: STUDENT QUESTION DETAIL ────────────────────────────────────
    # This section drills down to ONE student: how did they answer each question?
    # Useful for parent meetings or targeted student feedback.

    if has_question_data:
        st.markdown("---")
        st.markdown("### 🧑‍🎓 Per-Student Question Breakdown")
        st.caption(
            "Select a student to see exactly which questions they got right or wrong, "
            "compared to the class average on each question."
        )

        all_students_p3 = sorted(filtered_df["student_name"].unique().tolist())
        selected_student_p3 = st.selectbox(
            "Select Student for Question Detail",
            options=all_students_p3,
            key="p3_student_select",   # unique key — avoids conflict with Tab 2's selectbox
        )

        student_q_df = get_student_question_detail(
            filtered_df, question_cols, selected_student_p3
        )

        if student_q_df.empty:
            st.info("No question data found for this student.")
        else:
            # ── CORRECT VS WRONG SUMMARY ──────────────────────────────────────
            total_q   = len(student_q_df)
            correct_q = (student_q_df["Student Answer"] == "✅ Correct").sum()
            wrong_q   = total_q - correct_q
            accuracy  = round(correct_q / total_q * 100, 1) if total_q > 0 else 0

            sq1, sq2, sq3 = st.columns(3)
            sq1.metric("Questions Attempted", total_q)
            sq2.metric("Correct", f"{correct_q} ({accuracy}%)")
            sq3.metric("Wrong",   f"{wrong_q}")

            st.divider()

            # ── QUESTION DETAIL TABLE ─────────────────────────────────────────
            # Shows each question, what the student answered, and the class average.
            # The teacher can see at a glance where this student is weaker than the class.
            st.markdown(f"**Question-by-Question Detail for {selected_student_p3}**")
            st.dataframe(student_q_df, use_container_width=True)

            # ── CORRECT/WRONG BREAKDOWN PIE ───────────────────────────────────
            q_breakdown = pd.DataFrame({
                "Result": ["Correct", "Wrong"],
                "Count":  [correct_q, wrong_q],
            })
            fig_q_pie = px.pie(
                q_breakdown, names="Result", values="Count", color="Result",
                color_discrete_map={"Correct": "#16a34a", "Wrong": "#dc2626"},
                template="plotly_white", hole=0.4,
            )
            fig_q_pie.update_traces(textinfo="percent+label")
            fig_q_pie.update_layout(
                margin=dict(t=20, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=-0.2),
            )
            st.plotly_chart(fig_q_pie, use_container_width=True)

            # Download this student's question detail
            csv_q_detail = student_q_df.to_csv(index=False)
            st.download_button(
                label=f"📥 Download {selected_student_p3}'s Question Detail",
                data=csv_q_detail,
                file_name=f"{selected_student_p3.replace(' ', '_')}_question_detail.csv",
                mime="text/csv"
            )


# FOOTER
st.divider()
st.caption("Student Performance Tracker v3.0 — Complete | Built by Adewale Samson Adeagbo")
