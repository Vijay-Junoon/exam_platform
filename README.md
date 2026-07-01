# ExamSphere - Secure Online Examination Platform

A production-quality web application built using Flask, PostgreSQL, and GROQ LLM API for automated exam generation. The project uses a role-based authorization system separating Admins and Teachers.

## Technologies Used

- **Backend**: Python 3.12+, Flask, Flask-SQLAlchemy (ORM), Flask-Migrate (Alembic), Flask-Login (Sessions), Flask-WTF (CSRF + Forms validation).
- **Frontend**: HTML5, CSS3, JavaScript (Proctoring/Security Engine), Bootstrap 5.
- **AI Integration**: GROQ API (utilizing Llama 3.1) for structured JSON question generation.
- **Database**: PostgreSQL (with automated fallback to local SQLite for easy development/testing).

---

## Folder Structure

```
exam_platform/
│
├── app.py                   # Main Application Entry Point & DB Seeder
├── config.py                # Environment Configuration Manager
├── forms.py                 # WTForms validation schemas
├── requirements.txt         # Package dependencies
├── README.md                # Setup & run instructions
│
├── models/                  # SQLAlchemy ORM schemas
│   ├── __init__.py          # Database initialization
│   ├── user.py              # User roles Mixin
│   ├── question.py          # Question bank structure
│   └── exam.py              # ExamConfiguration, ExamAttempt, ExamQuestion, Answer
│
├── routes/                  # Controller blueprints
│   ├── __init__.py
│   ├── auth.py              # Register, login, logout
│   ├── admin.py             # CRUD questions, stats, AI generator, manual pass
│   └── exam.py              # Instructions, timer checks, security tracking, scores
│
├── services/                # Business services
│   ├── __init__.py
│   ├── auth_service.py
│   ├── question_service.py
│   ├── groq_service.py
│   └── exam_service.py
│
├── static/                  # Static assets
│   ├── css/
│   │   └── style.css        # Glassmorphic, modern CSS style system
│   └── js/
│       └── exam_security.js # Tab-switching, Fullscreen control & shortcut block
│
└── templates/               # Jinja2 HTML templates
    ├── base.html            # Main site frame
    ├── auth/                # Login & Register views
    ├── admin/               # Dashboard, config, list/edit questions, results
    ├── exam/                # Intro rules, active question, scorecard
    └── errors/              # Custom 403, 404, 500 error cards
```

---

## Installation & Setup

Follow these steps to run the application on your local machine:

### 1. Clone or Navigate to the Directory
Open a terminal in the root of the project directory `exam_platform`.

### 2. Create and Activate a Virtual Environment
**On Windows:**
```bash
python -m venv venv
.\venv\Scripts\activate
```

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Package Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables (`.env`)
A `.env` file should be created in the `exam_platform` directory.
Configure your database credentials and GROQ API key:

```env
SECRET_KEY=your_secret_session_key_here
DATABASE_URL=postgresql://username:password@localhost:5432/exam_db
GROQ_API_KEY=gsk_your_groq_api_key_here
```

*Note: If `DATABASE_URL` is omitted, the application will automatically fall back to creating a local SQLite database file `exam_platform.db` in the project root so you can test it immediately.*

### 5. Initialize the Database & Run Migrations
Run the following Flask commands to set up the database tables:
```bash
flask db init
flask db migrate -m "initial_schema"
flask db upgrade
```

### 6. Seed Default Users & Questions
Run the custom seeder command to create default login accounts and populate 10 sample exam questions:
```bash
flask seed-db
```

This command automatically creates:
1. **Admin Account**:
   - **Email**: `admin@exam.com`
   - **Password**: `admin123`
2. **Teacher Account**:
   - **Email**: `teacher@exam.com`
   - **Password**: `teacher123`
3. **10 Sample Questions** spanning various difficulty levels (Easy, Medium, Complex, Very Complex) on Computer Science and Operating Systems.

### 7. Launch the Development Server
```bash
flask run
```
Open your browser and navigate to `http://127.0.0.1:5000/`.

---

## Proctored Exam Security Mechanisms

1. **Strict Fullscreen Mode**:
   Candidates cannot begin the exam until they consent to enter fullscreen mode. Exiting fullscreen will flag a warning overlay block and log a security violation to the database.
2. **Tab-Switching / Minimize Monitoring**:
   If a user switches to another browser tab, focuses on a separate monitor screen, or launches another local application, the `visibilitychange` and window `blur` trackers will capture the event and record a violation.
3. **Shortcut Defenses**:
   - Context menus (Right click) are disabled.
   - Text copying, cutting, and pasting are blocked.
   - Keyboard shortcuts for Inspect Element/Developer Tools (`F12`, `Ctrl+Shift+I`, `Ctrl+Shift+J`, `Ctrl+Shift+C`) and view-source (`Ctrl+U`) are intercepted and blocked.
4. **Auto-Submit Protocol**:
   If the student exceeds the maximum violations (calculated as 10% of total questions or default of 3), the proctoring engine submits the current state of the exam automatically and terminates the session.
5. **Server-Backed Timer**:
   The exam session tracks time elapsed on the backend. If the browser tries to fake or delay the client timer, the next page reload or question submission triggers the backend time validation, terminating the exam if the duration has run out.
