import os
from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from config import Config
from models import db, User, Question, ExamConfiguration
from routes import auth_bp, admin_bp, exam_bp
from services.auth_service import AuthService

def create_app():
    """Application factory pattern to configure and return Flask instance."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)
    CSRFProtect(app) # Enable global CSRF protection
    
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'
    login_manager.init_app(app)

    # Set up user loader
    @login_manager.user_loader
    def load_user(user_id):
        return AuthService.get_user_by_id(user_id)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(exam_bp)

    # Register custom error page handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500

    # Custom context processors or CLI commands
    @app.cli.command("seed-db")
    def seed_db():
        """Seeds default Admin/Teacher accounts and a few questions."""
        print("Starting database seeding...")
        
        # 1. Create Default Config if missing
        from services.exam_service import ExamService
        config = ExamService.get_or_create_config()
        print(f"Exam configuration loaded: {config}")

        # 2. Seed Default Admin
        admin_email = "admin@exam.com"
        admin = User.query.filter_by(email=admin_email).first()
        if not admin:
            admin = User(name="System Admin", email=admin_email, role="admin")
            admin.set_password("admin123")
            db.session.add(admin)
            print(f"Created default Admin user: {admin_email} / admin123")
        else:
            print(f"Admin user '{admin_email}' already exists.")

        # 3. Seed Default Teacher
        teacher_email = "teacher@exam.com"
        teacher = User.query.filter_by(email=teacher_email).first()
        if not teacher:
            teacher = User(name="Jane Doe", email=teacher_email, role="teacher")
            teacher.set_password("teacher123")
            db.session.add(teacher)
            print(f"Created default Teacher user: {teacher_email} / teacher123")
        else:
            print(f"Teacher user '{teacher_email}' already exists.")

        db.session.commit()

        # Get admin ID for questions created_by
        admin_id = User.query.filter_by(role='admin').first().id

        # 4. Seed sample questions if empty
        if Question.query.count() == 0:
            sample_questions = [
                # Easy
                {
                    "question_text": "What does CPU stand for?",
                    "option_a": "Central Process Unit",
                    "option_b": "Central Processing Unit",
                    "option_c": "Computer Personal Unit",
                    "option_d": "Central Processor Utility",
                    "correct_answer": "B",
                    "difficulty_level": "easy",
                    "subject": "Computer Science"
                },
                {
                    "question_text": "Which memory is volatile?",
                    "option_a": "ROM",
                    "option_b": "Hard Disk",
                    "option_c": "RAM",
                    "option_d": "SSD",
                    "correct_answer": "C",
                    "difficulty_level": "easy",
                    "subject": "Computer Science"
                },
                {
                    "question_text": "What is the primary function of an operating system?",
                    "option_a": "To compile source code",
                    "option_b": "To design web pages",
                    "option_c": "To manage computer hardware resources",
                    "option_d": "To run anti-virus scans",
                    "correct_answer": "C",
                    "difficulty_level": "easy",
                    "subject": "Operating Systems"
                },
                # Medium
                {
                    "question_text": "Which CPU scheduling algorithm is non-preemptive by default?",
                    "option_a": "Round Robin",
                    "option_b": "First-Come, First-Served (FCFS)",
                    "option_c": "Shortest Remaining Time First (SRTF)",
                    "option_d": "Priority Preemptive Scheduling",
                    "correct_answer": "B",
                    "difficulty_level": "medium",
                    "subject": "Operating Systems"
                },
                {
                    "question_text": "What is virtual memory primarily used for?",
                    "option_a": "Increasing physical RAM speed",
                    "option_b": "Allowing execution of processes larger than physical memory",
                    "option_c": "Creating temporary file shares",
                    "option_d": "Running code inside virtual machines",
                    "correct_answer": "B",
                    "difficulty_level": "medium",
                    "subject": "Operating Systems"
                },
                {
                    "question_text": "Which of the following is NOT a necessary condition for deadlock?",
                    "option_a": "Mutual Exclusion",
                    "option_b": "Hold and Wait",
                    "option_c": "Preemption",
                    "option_d": "Circular Wait",
                    "correct_answer": "C",
                    "difficulty_level": "medium",
                    "subject": "Operating Systems"
                },
                # Complex
                {
                    "question_text": "In paging, what is 'thrashing'?",
                    "option_a": "Rapid writing of data to temporary disks",
                    "option_b": "Excessive page swapping activity resulting in low CPU utilization",
                    "option_c": "Clearing the cache memory on reboot",
                    "option_d": "Deleting dead or zombie child processes",
                    "correct_answer": "B",
                    "difficulty_level": "complex",
                    "subject": "Operating Systems"
                },
                {
                    "question_text": "What is the Bankers Algorithm used for in operating systems?",
                    "option_a": "Deadlock prevention",
                    "option_b": "Deadlock avoidance",
                    "option_c": "Deadlock detection",
                    "option_d": "Process synchronization",
                    "correct_answer": "B",
                    "difficulty_level": "complex",
                    "subject": "Operating Systems"
                },
                # Very Complex
                {
                    "question_text": "Under the buddy system memory allocation, what is the allocated block size for a 23KB request if the minimum block size is 8KB?",
                    "option_a": "24 KB",
                    "option_b": "32 KB",
                    "option_c": "16 KB",
                    "option_d": "64 KB",
                    "correct_answer": "B",
                    "difficulty_level": "very_complex",
                    "subject": "Operating Systems"
                },
                {
                    "question_text": "What is the primary difference between a hard link and a soft link in Unix filesystems?",
                    "option_a": "Soft link shares the inode; hard link creates a new inode",
                    "option_b": "Hard link points directly to the inode; soft link points to the filename path",
                    "option_c": "Soft links are only for directories; hard links are only for files",
                    "option_d": "Hard links are slower to resolve than soft links",
                    "correct_answer": "B",
                    "difficulty_level": "very_complex",
                    "subject": "Operating Systems"
                }
            ]
            for item in sample_questions:
                q = Question(
                    question_text=item["question_text"],
                    option_a=item["option_a"],
                    option_b=item["option_b"],
                    option_c=item["option_c"],
                    option_d=item["option_d"],
                    correct_answer=item["correct_answer"],
                    difficulty_level=item["difficulty_level"],
                    subject=item["subject"],
                    created_by=admin_id
                )
                db.session.add(q)
            db.session.commit()
            print("Successfully seeded 10 sample questions into the database.")
        
        print("Database seeding completed.")

# Instantiate the global application object for Gunicorn / Vercel
app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
