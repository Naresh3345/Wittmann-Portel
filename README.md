# Wittmann HR Interview Portal

Separate HR-only portal for the Wittmann AI Interview System.

## What HR Can Do

- Login with HR credentials only.
- View shortlisted candidates and all generated interview reports.
- See shortlisted candidates and not-shortlisted/review candidates in separate result sections with marks.
- Download candidate reports and resumes from the main interview project.
- Create and edit interview roles.
- Add, edit, enable, or disable live questions for every role.
- Import multiple roles and questions from Excel or CSV.
- Main HR admin can create other HR portal users and email access details.
- HR can use automatic or manual shortlisting and approve candidates for second round technical interview by email.
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
HR_PORTAL_URL=http://192.168.70.102:5050
SHORTLIST_MIN_SCORE=70
HR_USERNAME=hr
HR_PASSWORD=Wittmann@123
HR_EMAIL=hr@example.com
```

## Excel / CSV Question Import

Open **Question Bank > Import Excel** and upload `.xlsx`, `.xlsm`, or `.csv`.

Use these columns:

```text
Role Name, Role Slug, Question Code, Section, Topic, Difficulty, Question, Options, Correct Answer, Keywords, Marks, Active
```

Required columns are `Role Name`, `Section`, `Topic`, `Question`, and `Correct Answer`.
Use one option/keyword per line, or separate them with `|`. If `Question Code` is present, importing again updates the same question.

## Role and Question Flow

Open **Roles > New Role** to create a new interview role. Then use **Add Question** from that role row, or open **Question Bank > New Question** and choose the role.

A role is ready for candidate interviews when it has at least 15 active Aptitude questions and 3 active Programming questions.

## HR User Access

The `HR_USERNAME` / `HR_PASSWORD` account becomes the main admin user. After login, open **Users > New User** to create another HR portal login.

The main HR admin enters the new user's username and password. If SMTP settings are configured, the portal emails the new user the portal link, username, and password. If SMTP is not configured, those details are shown on screen so the main HR admin can share them manually.

Optional SMTP settings:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
```

The same SMTP settings are used when HR clicks **Approve** in manual shortlisting mode. The approved candidate receives a formal email that they are shortlisted for the second round technical interview.

Run:

```powershell
python app.py
```

Open:

```text
http://localhost:5050
```

## Deploying on Vercel

The app is configured for Vercel with `pyproject.toml` and `vercel.json`.

Add these Environment Variables in the Vercel project settings before deploying:

```text
SECRET_KEY=use-a-long-random-value
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
HR_USERNAME=Vasanth
HR_PASSWORD=use-a-strong-initial-password
HR_EMAIL=hr@example.com
HR_PORTAL_URL=https://your-vercel-domain.vercel.app
```

Do not use `localhost` in `DATABASE_URL` on Vercel. Use a hosted PostgreSQL database such as Vercel Postgres, Neon, Supabase, or another public PostgreSQL provider.

## Important

This portal has no candidate registration, OTP, interview, or test routes. It is only for HR/admin work.

For production, replace `HR_PASSWORD` with `HR_PASSWORD_HASH` generated using Werkzeug.
