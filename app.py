import os
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, send_file, session, url_for
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from werkzeug.security import check_password_hash, generate_password_hash


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
MAIN_PROJECT_DIR = Path(os.getenv("INTERVIEW_PROJECT_DIR", r"E:\wittmann_interview_ai"))
REPORT_DIR = Path(os.getenv("REPORT_DIR", str(MAIN_PROJECT_DIR / "reports"))).resolve()
RESUME_DIR = (REPORT_DIR / "resumes").resolve()

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/wittmann_interview_ai"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
COMPANY_NAME = os.getenv("COMPANY_NAME", "WITTMANN BATTENFELD India Pvt. Ltd.")
HR_USERNAME = os.getenv("HR_USERNAME", "hr")
HR_PASSWORD_HASH = os.getenv("HR_PASSWORD_HASH", generate_password_hash(os.getenv("HR_PASSWORD", "Wittmann@123")))

SECTION_COUNTS = {"Aptitude": 15, "Programming": 3}

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-hr-portal-secret")


def mask_dsn_password(dsn):
    parsed = urlsplit(dsn)
    if not parsed.password:
        return dsn
    netloc = f"{parsed.username}:***@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def get_db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=5)


@app.errorhandler(psycopg.OperationalError)
def database_connection_error(error):
    return render_template(
        "database_error.html",
        company_name=COMPANY_NAME,
        db_label=mask_dsn_password(DATABASE_URL),
        error=str(error),
    ), 503


def require_login(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("hr_logged_in"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def safe_project_file(path, allowed_root):
    if not path:
        return None
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = (MAIN_PROJECT_DIR / candidate).resolve()
    else:
        candidate = candidate.resolve()
    try:
        candidate.relative_to(allowed_root)
    except ValueError:
        return None
    return candidate if candidate.exists() else None


def fetch_dashboard_stats():
    with get_db() as conn:
        stats = conn.execute(
            """
            SELECT
                COUNT(*) AS total_interviews,
                COUNT(*) FILTER (WHERE i.status = 'Completed') AS completed_interviews,
                COUNT(*) FILTER (WHERE i.shortlist_status = 'Shortlisted') AS shortlisted,
                ROUND(COALESCE(AVG(i.total_score), 0)::numeric, 2) AS average_score
            FROM interviews i
            """
        ).fetchone()
        role_rows = conn.execute(
            """
            SELECT r.role_name, COUNT(i.interview_id) AS total,
                   COUNT(*) FILTER (WHERE i.shortlist_status = 'Shortlisted') AS shortlisted
            FROM roles r
            LEFT JOIN interviews i ON i.role_id = r.role_id
            GROUP BY r.role_name
            ORDER BY r.role_name
            """
        ).fetchall()
        recent = fetch_reports(conn, limit=8)
    return stats, role_rows, recent


def fetch_reports(conn, status="", role_id="", search="", limit=None):
    filters = ["i.report_path IS NOT NULL"]
    params = []
    if status:
        filters.append("i.shortlist_status = %s")
        params.append(status)
    if role_id:
        filters.append("i.role_id = %s")
        params.append(int(role_id))
    if search:
        filters.append("(u.name ILIKE %s OR u.email ILIKE %s OR u.phone ILIKE %s)")
        like = f"%{search}%"
        params.extend([like, like, like])
    limit_sql = "LIMIT %s" if limit else ""
    if limit:
        params.append(limit)
    return conn.execute(
        f"""
        SELECT i.interview_id, i.date, i.total_score, i.status, i.shortlist_status,
               i.shortlist_reason, i.report_path,
               u.name, u.email, u.phone, u.resume_path, r.role_id, r.role_name
        FROM interviews i
        JOIN users u ON u.user_id = i.user_id
        JOIN roles r ON r.role_id = i.role_id
        WHERE {" AND ".join(filters)}
        ORDER BY i.date DESC
        {limit_sql}
        """,
        tuple(params),
    ).fetchall()


def fetch_roles(conn):
    return conn.execute("SELECT role_id, role_slug, role_name FROM roles ORDER BY role_name").fetchall()


def fetch_questions(conn, role_slug="", section="", active=""):
    filters = []
    params = []
    if role_slug:
        filters.append("role_slug = %s")
        params.append(role_slug)
    if section:
        filters.append("section = %s")
        params.append(section)
    if active in {"true", "false"}:
        filters.append("active = %s")
        params.append(active == "true")
    where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
    return conn.execute(
        f"""
        SELECT *
        FROM question_bank
        {where_sql}
        ORDER BY role_slug, CASE section WHEN 'Aptitude' THEN 1 WHEN 'Programming' THEN 2 ELSE 3 END, topic, question_id
        """,
        tuple(params),
    ).fetchall()


def parse_lines(text):
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == HR_USERNAME and check_password_hash(HR_PASSWORD_HASH, password):
            session.clear()
            session["hr_logged_in"] = True
            session["hr_username"] = username
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Invalid HR credentials.", "error")
    return render_template("login.html", company_name=COMPANY_NAME)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@require_login
def dashboard():
    stats, role_rows, recent = fetch_dashboard_stats()
    return render_template(
        "dashboard.html",
        stats=stats,
        role_rows=role_rows,
        recent=recent,
        company_name=COMPANY_NAME,
        db_label=mask_dsn_password(DATABASE_URL),
    )


@app.route("/candidates")
@require_login
def candidates():
    status = request.args.get("status", "Shortlisted")
    role_id = request.args.get("role_id", "")
    search = request.args.get("search", "").strip()
    with get_db() as conn:
        roles = fetch_roles(conn)
        reports = fetch_reports(conn, status=status, role_id=role_id, search=search)
    return render_template(
        "candidates.html",
        reports=reports,
        roles=roles,
        filters={"status": status, "role_id": role_id, "search": search},
        company_name=COMPANY_NAME,
    )


@app.route("/questions")
@require_login
def questions():
    role_slug = request.args.get("role_slug", "")
    section = request.args.get("section", "")
    active = request.args.get("active", "")
    with get_db() as conn:
        roles = fetch_roles(conn)
        rows = fetch_questions(conn, role_slug=role_slug, section=section, active=active)
    return render_template(
        "questions.html",
        questions=rows,
        roles=roles,
        sections=SECTION_COUNTS,
        filters={"role_slug": role_slug, "section": section, "active": active},
        company_name=COMPANY_NAME,
    )


@app.route("/questions/new", methods=["GET", "POST"])
@require_login
def new_question():
    return save_question()


@app.route("/questions/<int:question_id>/edit", methods=["GET", "POST"])
@require_login
def edit_question(question_id):
    return save_question(question_id)


def save_question(question_id=None):
    with get_db() as conn:
        roles = fetch_roles(conn)
        question = None
        if question_id:
            question = conn.execute("SELECT * FROM question_bank WHERE question_id = %s", (question_id,)).fetchone()
            if not question:
                flash("Question not found.", "error")
                return redirect(url_for("questions"))

        if request.method == "POST":
            role_slug = request.form.get("role_slug", "").strip()
            section = request.form.get("section", "").strip()
            topic = request.form.get("topic", "").strip()
            question_code = request.form.get("question_code", "").strip() or None
            difficulty = request.form.get("difficulty", "Medium").strip()
            question_text = request.form.get("question_text", "").strip()
            correct_answer = request.form.get("correct_answer", "").strip()
            options = parse_lines(request.form.get("options", ""))
            keywords = parse_lines(request.form.get("keywords", ""))
            marks = int(request.form.get("marks", 5) or 5)
            active = bool(request.form.get("active"))

            if not all([role_slug, section, topic, question_text, correct_answer]):
                flash("Role, section, topic, question, and answer are required.", "error")
            elif question_id:
                conn.execute(
                    """
                    UPDATE question_bank
                    SET question_code = %s, role_slug = %s, section = %s, topic = %s,
                        difficulty = %s, question_text = %s, options = %s, correct_answer = %s,
                        keywords = %s, marks = %s, active = %s, updated_at = now()
                    WHERE question_id = %s
                    """,
                    (
                        question_code,
                        role_slug,
                        section,
                        topic,
                        difficulty,
                        question_text,
                        Jsonb(options),
                        correct_answer,
                        Jsonb(keywords),
                        marks,
                        active,
                        question_id,
                    ),
                )
                flash("Question updated.", "success")
                return redirect(url_for("questions", role_slug=role_slug, section=section))
            else:
                conn.execute(
                    """
                    INSERT INTO question_bank
                        (question_code, role_slug, section, topic, difficulty, question_text,
                         options, correct_answer, keywords, marks, active, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    """,
                    (
                        question_code,
                        role_slug,
                        section,
                        topic,
                        difficulty,
                        question_text,
                        Jsonb(options),
                        correct_answer,
                        Jsonb(keywords),
                        marks,
                        active,
                    ),
                )
                flash("Question created.", "success")
                return redirect(url_for("questions", role_slug=role_slug, section=section))

    return render_template(
        "question_form.html",
        question=question,
        roles=roles,
        sections=SECTION_COUNTS,
        company_name=COMPANY_NAME,
    )


@app.post("/questions/<int:question_id>/toggle")
@require_login
def toggle_question(question_id):
    with get_db() as conn:
        row = conn.execute("SELECT active FROM question_bank WHERE question_id = %s", (question_id,)).fetchone()
        if row:
            conn.execute("UPDATE question_bank SET active = %s, updated_at = now() WHERE question_id = %s", (not row["active"], question_id))
            flash("Question status changed.", "success")
    return redirect(request.referrer or url_for("questions"))


@app.route("/download/report/<interview_id>")
@require_login
def download_report(interview_id):
    with get_db() as conn:
        row = conn.execute("SELECT report_path FROM interviews WHERE interview_id = %s", (interview_id,)).fetchone()
    path = safe_project_file(row["report_path"] if row else "", REPORT_DIR)
    if not path:
        flash("Report file is not available.", "error")
        return redirect(url_for("candidates"))
    return send_file(path, as_attachment=True)


@app.route("/download/resume/<interview_id>")
@require_login
def download_resume(interview_id):
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT u.resume_path
            FROM interviews i
            JOIN users u ON u.user_id = i.user_id
            WHERE i.interview_id = %s
            """,
            (interview_id,),
        ).fetchone()
    path = safe_project_file(row["resume_path"] if row else "", RESUME_DIR)
    if not path:
        flash("Resume file is not available.", "error")
        return redirect(url_for("candidates"))
    return send_file(path, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5050")), debug=True)
