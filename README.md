# Wittmann HR Interview Portal

Separate HR-only portal for the Wittmann AI Interview System.

## What HR Can Do

- Login with HR credentials only.
- View shortlisted candidates and all generated interview reports.
- Download candidate reports and resumes from the main interview project.
- Add, edit, enable, or disable live questions for every role.
- Use the same PostgreSQL database as the candidate interview project.

## Setup

Install requirements:

```powershell
python -m pip install -r requirements.txt
```

Create `.env` from `.env.example` and set the same PostgreSQL connection used by `E:\wittmann_interview_ai`:

```text
DATABASE_URL=postgresql://postgres:your-password@localhost:5432/wittmann_interview_ai
INTERVIEW_PROJECT_DIR=E:\wittmann_interview_ai
REPORT_DIR=E:\wittmann_interview_ai\reports
HR_USERNAME=hr
HR_PASSWORD=Wittmann@123
```

Run:

```powershell
python app.py
```

Open:

```text
http://localhost:5050
```

## Important

This portal has no candidate registration, OTP, interview, or test routes. It is only for HR/admin work.

For production, replace `HR_PASSWORD` with `HR_PASSWORD_HASH` generated using Werkzeug.
