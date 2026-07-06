from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from services.question_service import QuestionService
from services.exam_service import ExamService
from services.groq_service import GroqService
from forms import QuestionForm, ExamConfigForm, AIQuestionGenerationForm, ExamForm, ExtractQuestionsPDFForm
from models import User, Question, ExamAttempt, Exam, db

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    """Decorator to restrict access to administrators only."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403) # Forbidden
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/admin/dashboard')
@login_required
@admin_required
def dashboard():
    """Renders the main admin landing page showing quick metrics."""
    db.session.rollback()
    total_questions = Question.query.count()
    total_faculty = User.query.filter_by(role='faculty').count()
    total_attempts = ExamAttempt.query.count()
    completed_attempts = ExamAttempt.query.filter_by(completed=True).count()
    
    # Get active config
    config = ExamService.get_or_create_config()
    
    # Calculate statistics for each exam configuration
    exams = Exam.query.order_by(Exam.created_at.desc()).all()
    exam_stats = []
    for exam in exams:
        attempts = ExamAttempt.query.filter_by(exam_id=exam.id).all()
        completed_attempts_list = [a for a in attempts if a.completed]
        total_completed = len(completed_attempts_list)
        passed = sum(1 for a in completed_attempts_list if a.passed)
        failed = total_completed - passed
        pass_rate = round((passed / total_completed) * 100, 1) if total_completed > 0 else 0.0
        
        exam_stats.append({
            'id': exam.id,
            'title': exam.title,
            'subject': exam.subject,
            'total_attempts': total_completed,
            'passed': passed,
            'failed': failed,
            'pass_rate': pass_rate
        })
        
    # Also include legacy/general exams if there are attempts with exam_id=None
    legacy_attempts = ExamAttempt.query.filter_by(exam_id=None, completed=True).all()
    if legacy_attempts:
        total_completed = len(legacy_attempts)
        passed = sum(1 for a in legacy_attempts if a.passed)
        failed = total_completed - passed
        pass_rate = round((passed / total_completed) * 100, 1) if total_completed > 0 else 0.0
        exam_stats.append({
            'id': None,
            'title': 'General / Legacy Exams',
            'subject': 'N/A',
            'total_attempts': total_completed,
            'passed': passed,
            'failed': failed,
            'pass_rate': pass_rate
        })
    
    return render_template('admin/dashboard.html',
                           total_questions=total_questions,
                           total_faculty=total_faculty,
                           total_attempts=total_attempts,
                           completed_attempts=completed_attempts,
                           exam_config=config,
                           exam_stats=exam_stats)


@admin_bp.route('/admin/questions', methods=['GET'])
@login_required
@admin_required
def list_questions():
    """Renders question list with subject filtering."""
    subject = request.args.get('subject')
    
    # If filter is 'all' or empty, treat as None
    filter_sub = subject if subject and subject != 'all' else None

    questions = QuestionService.get_all_questions(subject=filter_sub)
    subjects = QuestionService.get_all_subjects()
    
    return render_template('admin/questions.html', 
                           questions=questions, 
                           subjects=subjects,
                           current_subject=subject or 'all')


@admin_bp.route('/admin/questions/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_question():
    """Handles manual question creation."""
    form = QuestionForm()
    if form.validate_on_submit():
        question, error = QuestionService.create_question(
            question_text=form.question_text.data,
            option_a=form.option_a.data,
            option_b=form.option_b.data,
            option_c=form.option_c.data,
            option_d=form.option_d.data,
            correct_answer=form.correct_answer.data,
            subject=form.subject.data,
            creator_id=current_user.id
        )
        if error:
            flash(error, 'danger')
        else:
            flash('Question successfully added to the bank!', 'success')
            return redirect(url_for('admin.list_questions'))
            
    return render_template('admin/edit_question.html', form=form, title="Add Question")


@admin_bp.route('/admin/questions/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_question(id):
    """Handles editing an existing question."""
    question = QuestionService.get_question_by_id(id)
    if not question:
        flash("Question not found.", "danger")
        return redirect(url_for('admin.list_questions'))

    # Populate form with current values on GET
    form = QuestionForm(obj=question)
    if form.validate_on_submit():
        updated_q, error = QuestionService.update_question(
            question_id=id,
            question_text=form.question_text.data,
            option_a=form.option_a.data,
            option_b=form.option_b.data,
            option_c=form.option_c.data,
            option_d=form.option_d.data,
            correct_answer=form.correct_answer.data,
            subject=form.subject.data
        )
        if error:
            flash(error, 'danger')
        else:
            flash('Question successfully updated!', 'success')
            return redirect(url_for('admin.list_questions'))
            
    return render_template('admin/edit_question.html', form=form, title="Edit Question", question=question)


@admin_bp.route('/admin/questions/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_question(id):
    """Deletes a question from the database."""
    success, error = QuestionService.delete_question(id)
    if success:
        flash("Question successfully deleted.", "success")
    else:
        flash(error or "Failed to delete question.", "danger")
    return redirect(url_for('admin.list_questions'))


@admin_bp.route('/admin/questions/delete-all', methods=['POST'])
@login_required
@admin_required
def delete_all_questions():
    """Deletes all questions from the database."""
    try:
        num_deleted = Question.query.delete(synchronize_session=False)
        db.session.commit()
        flash(f"Successfully deleted all {num_deleted} questions from the database.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete all questions: {str(e)}", "danger")
    return redirect(url_for('admin.list_questions'))


@admin_bp.route('/admin/config', methods=['GET', 'POST'])
@login_required
@admin_required
def configure_exam():
    """Handles updating global exam settings (total questions and duration)."""
    config = ExamService.get_or_create_config()
    form = ExamConfigForm(obj=config)
    
    if form.validate_on_submit():
        updated_cfg, error = ExamService.update_config(
            total_questions=form.total_questions.data,
            duration=form.exam_duration.data,
            pattern=form.pattern.data,
            passing_marks=form.passing_marks.data,
            override_threshold=form.override_threshold.data
        )
        if error:
            flash(error, 'danger')
        else:
            flash('Exam configuration updated successfully!', 'success')
            return redirect(url_for('admin.dashboard'))
            
    return render_template('admin/config.html', form=form)


def extract_text_from_pdf(file_stream):
    """Helper to extract text from a file stream using pypdf."""
    from pypdf import PdfReader
    try:
        reader = PdfReader(file_stream)
        text = ""
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"
        return text.strip()
    except Exception as e:
        current_app.logger.error(f"PDF extraction error: {e}")
        return ""


def extract_pages_from_pdf(file_stream):
    """Helper to extract a list of page texts from a PDF file stream using pypdf."""
    from pypdf import PdfReader
    try:
        reader = PdfReader(file_stream)
        pages = []
        for page in reader.pages:
            content = page.extract_text()
            pages.append(content or "")
        return pages
    except Exception as e:
        current_app.logger.error(f"PDF page extraction error: {e}")
        return []


@admin_bp.route('/admin/generate-questions', methods=['GET', 'POST'])
@login_required
@admin_required
def generate_questions():
    """Calls GROQ LLM API to bulk-generate questions and inserts them into DB."""
    form = AIQuestionGenerationForm()
    if form.validate_on_submit():
        api_key = current_app.config.get('GROQ_API_KEY')
        
        # Combine PDF text and text description
        combined_description = ""
        
        # Check if PDF was uploaded
        if form.pdf_file.data:
            pdf_text = extract_text_from_pdf(form.pdf_file.data.stream)
            if not pdf_text:
                flash("Failed to extract readable text from the uploaded PDF. Please make sure it is not scanned or password protected.", "danger")
                return render_template('admin/generate_questions.html', form=form)
            # Truncate text from PDF to 20,000 characters as requested
            combined_description += f"Syllabus Source (PDF):\n{pdf_text[:20000]}\n\n"
            
        if form.topic_description.data and form.topic_description.data.strip():
            combined_description += f"Additional Context:\n{form.topic_description.data.strip()}"
            
        # Invoke LLM Generator Service
        questions_generated, error = GroqService.generate_questions(
            subject=form.subject.data,
            topic_description=combined_description,
            num_questions=form.num_questions.data,
            api_key=api_key
        )
        
        if error:
            flash(error, 'danger')
        else:
            # Bulk Insert questions
            count, db_error = QuestionService.bulk_insert_questions(questions_generated, current_user.id)
            if db_error:
                flash(db_error, 'danger')
            else:
                flash(f"Success! {count} questions generated and loaded into database.", 'success')
                return redirect(url_for('admin.list_questions'))
                
    return render_template('admin/generate_questions.html', form=form)


@admin_bp.route('/admin/extract-questions', methods=['GET', 'POST'])
@login_required
@admin_required
def extract_questions():
    """Extracts questions from a PDF using GROQ LLM API and inserts them into DB."""
    form = ExtractQuestionsPDFForm()
    if form.validate_on_submit():
        api_key = current_app.config.get('GROQ_API_KEY')
        
        if not form.pdf_file.data:
            flash("Please upload a PDF file.", "danger")
            return render_template('admin/extract_questions.html', form=form)
            
        # Extract pages from the uploaded PDF
        pages = extract_pages_from_pdf(form.pdf_file.data.stream)
        # Filter out empty pages
        pages = [p.strip() for p in pages if p.strip()]
        if not pages:
            flash("Failed to extract readable text from the uploaded PDF. Please make sure it is not scanned or password protected.", "danger")
            return render_template('admin/extract_questions.html', form=form)
            
        # Group pages into batches of 3 to prevent LLM output token limits and input constraints
        batch_size = 3
        page_batches = []
        for i in range(0, len(pages), batch_size):
            batch_text = "\n\n--- Page Break ---\n\n".join(pages[i:i+batch_size])
            page_batches.append(batch_text)
            
        # Process each batch
        questions_extracted = []
        extraction_errors = []
        
        for idx, batch_text in enumerate(page_batches):
            batch_qs, error = GroqService.extract_questions_from_text(
                pdf_text=batch_text,
                subject=form.subject.data,
                api_key=api_key
            )
            if error:
                current_app.logger.warning(f"Error extracting batch {idx+1}: {error}")
                extraction_errors.append(f"Segment {idx+1}: {error}")
            elif batch_qs:
                questions_extracted.extend(batch_qs)
                
        if not questions_extracted:
            error_msg = "Failed to extract any questions from the PDF. Errors: " + "; ".join(extraction_errors[:3])
            flash(error_msg, 'danger')
        else:
            # Bulk insert questions
            count, db_error = QuestionService.bulk_insert_questions(questions_extracted, current_user.id)
            if db_error:
                flash(db_error, 'danger')
            else:
                success_msg = f"Success! {count} questions extracted from PDF and loaded into the database."
                if extraction_errors:
                    success_msg += f" Note: {len(extraction_errors)} segments failed to process due to limits/errors."
                flash(success_msg, 'success')
                return redirect(url_for('admin.list_questions'))
                
    return render_template('admin/extract_questions.html', form=form)


@admin_bp.route('/admin/results')
@login_required
@admin_required
def view_results():
    """Lists faculty exam attempt details, tracking scores and browser violations, grouped by exam."""
    db.session.rollback()
    from sqlalchemy.orm import joinedload
    exams = Exam.query.order_by(Exam.created_at.desc()).all()
    grouped_attempts = []
    for exam in exams:
        attempts = ExamAttempt.query.options(joinedload(ExamAttempt.user)).filter_by(exam_id=exam.id).order_by(ExamAttempt.start_time.desc()).all()
        grouped_attempts.append((exam, attempts))
        
    legacy_attempts = ExamAttempt.query.options(joinedload(ExamAttempt.user)).filter_by(exam_id=None).order_by(ExamAttempt.start_time.desc()).all()
    
    return render_template('admin/results.html', 
                           grouped_attempts=grouped_attempts, 
                           legacy_attempts=legacy_attempts)


@admin_bp.route('/admin/results/toggle-pass/<int:attempt_id>', methods=['POST'])
@login_required
@admin_required
def toggle_pass(attempt_id):
    """Allows manual pass adjustment for borderline scoring faculty."""
    success, error = ExamService.toggle_manual_pass(attempt_id)
    if success:
        flash("Candidate status updated successfully.", "success")
    else:
        flash(error or "Failed to update candidate status.", "danger")
    return redirect(url_for('admin.view_results'))


@admin_bp.route('/admin/exams')
@login_required
@admin_required
def list_exams():
    """Lists all configured examinations."""
    exams = Exam.query.order_by(Exam.created_at.desc()).all()
    # Check question counts per subject for helper messages
    subject_counts = {}
    from sqlalchemy import func
    counts = db.session.query(Question.subject, func.count(Question.id)).group_by(Question.subject).all()
    for sub, count in counts:
        subject_counts[sub] = count

    return render_template('admin/exams.html', exams=exams, subject_counts=subject_counts)


@admin_bp.route('/admin/exams/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_exam():
    """Handles creation of a new examination."""
    form = ExamForm()
    
    # Populate subjects dynamically from the question bank
    subjects = QuestionService.get_all_subjects()
    if not subjects:
        subjects = ['General']
    form.subject.choices = [(s, s) for s in subjects]

    if request.method == 'GET':
        # pre-populate with default config
        config = ExamService.get_or_create_config()
        form.total_questions.data = config.total_questions
        form.exam_duration.data = config.exam_duration
        form.pattern.data = config.pattern
        form.passing_marks.data = config.passing_marks
        form.override_threshold.data = config.override_threshold

    if form.validate_on_submit():
        exam = Exam(
            title=form.title.data,
            subject=form.subject.data,
            total_questions=form.total_questions.data,
            exam_duration=form.exam_duration.data,
            pattern=form.pattern.data,
            passing_marks=form.passing_marks.data,
            override_threshold=form.override_threshold.data
        )
        db.session.add(exam)
        try:
            db.session.commit()
            flash(f"Examination '{exam.title}' created successfully!", "success")
            return redirect(url_for('admin.list_exams'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating exam: {str(e)}", "danger")

    return render_template('admin/edit_exam.html', form=form, title="Create Exam")


@admin_bp.route('/admin/exams/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_exam(id):
    """Handles editing an existing examination configuration."""
    exam = Exam.query.get_or_404(id)
    form = ExamForm(obj=exam)

    # Populate subjects dynamically from the question bank
    subjects = QuestionService.get_all_subjects()
    if exam.subject and exam.subject not in subjects:
        subjects.append(exam.subject)
    if not subjects:
        subjects = ['General']
    form.subject.choices = [(s, s) for s in subjects]

    if form.validate_on_submit():
        exam.title = form.title.data
        exam.subject = form.subject.data
        exam.total_questions = form.total_questions.data
        exam.exam_duration = form.exam_duration.data
        exam.pattern = form.pattern.data
        exam.passing_marks = form.passing_marks.data
        exam.override_threshold = form.override_threshold.data

        try:
            db.session.commit()
            flash(f"Examination '{exam.title}' updated successfully!", "success")
            return redirect(url_for('admin.list_exams'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating exam: {str(e)}", "danger")

    return render_template('admin/edit_exam.html', form=form, title="Edit Exam", exam=exam)


@admin_bp.route('/admin/exams/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_exam(id):
    """Deletes an examination configuration."""
    exam = Exam.query.get_or_404(id)
    try:
        db.session.delete(exam)
        db.session.commit()
        flash(f"Examination '{exam.title}' deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete exam: {str(e)}", "danger")
    return redirect(url_for('admin.list_exams'))


@admin_bp.route('/admin/users')
@login_required
@admin_required
def list_users():
    """Lists all registered user accounts (Faculty & Admins) in the system."""
    db.session.rollback()
    users = User.query.order_by(User.role.asc(), User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)


@admin_bp.route('/admin/users/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_user(id):
    """Deletes a user account from the system."""
    if current_user.id == id:
        flash("You cannot delete your own administrator account.", "danger")
        return redirect(url_for('admin.list_users'))

    user = User.query.get_or_404(id)
    name = user.name
    email = user.email
    try:
        db.session.delete(user)
        db.session.commit()
        flash(f"User account for '{name}' ({email}) has been deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete user account: {str(e)}", "danger")

    return redirect(url_for('admin.list_users'))
