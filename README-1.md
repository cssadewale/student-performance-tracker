# 🎓 Student Performance Tracker — Complete (All 3 Phases)

A free Streamlit web app that turns student result CSVs into actionable visual insights for teachers.

**Built by:** Adewale Samson Adeagbo  
**Stack:** Python · Streamlit · Pandas · Plotly  
**Hosting:** Streamlit Cloud (free)

---

## What It Does

### ✅ Tab 1 — Class Overview (Phase 1)
- Class average, pass rate, total students — at a glance
- Score distribution histogram with pass mark line
- Pass/Fail donut chart
- Average score by subject
- Top 5 and Bottom 5 students
- Full result table with download

### ✅ Tab 2 — Student Profile (Phase 2)
- Individual student trend chart — score across all exams over time, by subject
- Subject-by-subject average bar chart (red → green colour scale)
- Full exam record table for that student
- Downloadable individual student report

### ✅ Tab 3 — At-Risk Students (Phase 2)
- Flags students who scored below a threshold in multiple exams
- Adjustable threshold and minimum failure count (sliders)
- At-risk table with weak subjects listed
- Bar chart of at-risk students
- Downloadable at-risk list

### ✅ Tab 4 — Topic & Question Analysis (Phase 3)
- **Most-missed questions** — bar chart ranking questions by miss rate
- Auto-identifies the hardest and easiest question
- **Topic weakness summary** — which topics the class scores lowest on
- **Per-student question breakdown** — see how one student answered each question vs the class average
- Downloadable topic weakness report and question detail reports

---

## CSV Formats

### Basic CSV (works for Tabs 1, 2, 3)
```
student_name, student_class, subject, score, total, date
Amara Okonkwo, SS1A, Mathematics, 72, 100, 15/01/2025
```

### Extended CSV (adds Tab 4 — Phase 3)
```
student_name, student_class, subject, score, total, date, topic, q1, q2, q3, ...
Amara Okonkwo, SS1A, Mathematics, 7, 10, 15/01/2025, Quadratic Equations, 1, 1, 0, 1, 1, ...
```

**New columns for Phase 3:**
- `topic` — the topic this exam covered (e.g. "Quadratic Equations", "Newton's Laws")
- `q1` ... `qN` — 1 = student got this question correct, 0 = wrong

The app auto-detects how many question columns you have. You can have 5, 10, 20 — any number.  
If question/topic columns are missing, Tabs 1–3 still work normally.

---

## How to Run

```bash
pip install -r requirements.txt
streamlit run app.py
# Open http://localhost:8501
```

## How to Deploy to Streamlit Cloud (Free)

1. Push all files to a GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect GitHub → New app → select `app.py` → Deploy
4. App goes live at a public URL (shareable with other teachers)

> ⚠️ GitHub push requires a laptop/PC once. After that, manage everything from any device.

---

## Pass Mark Logic
- Pass = 50% and above
- Fail = below 50%
- Percentage = (score ÷ total) × 100

## At-Risk Logic (adjustable in app)
- Default: flagged if scored below **40%** in **2 or more** exams

## Question Miss Rate Logic
- Miss Rate = (number of wrong answers ÷ total attempts) × 100
- A question with 70% miss rate was wrong by 7 out of every 10 students
