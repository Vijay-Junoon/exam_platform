from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from services.question_service import QuestionService
from services.exam_service import ExamService
from services.groq_service import GroqService
from forms import QuestionForm, ExamConfigForm, AIQuestionGenerationForm
from models import User, Question, ExamAttempt

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
    total_questions = Question.query.count()
    total_teachers = User.query.filter_by(role='teacher').count()
    total_attempts = ExamAttempt.query.count()
    completed_attempts = ExamAttempt.query.filter_by(completed=True).count()
    
    # Calculate counts per difficulty
    difficulty_counts = {
        'easy': Question.query.filter_by(difficulty_level='easy').count(),
        'medium': Question.query.filter_by(difficulty_level='medium').count(),
        'complex': Question.query.filter_by(difficulty_level='complex').count(),
        'very_complex': Question.query.filter_by(difficulty_level='very_complex').count()
    }
    
    # Get active config
    config = ExamService.get_or_create_config()
    
    return render_template('admin/dashboard.html',
                           total_questions=total_questions,
                           total_teachers=total_teachers,
                           total_attempts=total_attempts,
                           completed_attempts=completed_attempts,
                           difficulty_counts=difficulty_counts,
                           exam_config=config)


@admin_bp.route('/admin/questions', methods=['GET'])
@login_required
@admin_required
def list_questions():
    """Renders question list with difficulty level filtering."""
    difficulty = request.args.get('difficulty')
    subject = request.args.get('subject')
    
    # If filter is 'all' or empty, treat as None
    filter_diff = difficulty if difficulty and difficulty != 'all' else None
    filter_sub = subject if subject and subject != 'all' else None

    questions = QuestionService.get_all_questions(difficulty=filter_diff, subject=filter_sub)
    subjects = QuestionService.get_all_subjects()
    
    return render_template('admin/questions.html', 
                           questions=questions, 
                           subjects=subjects,
                           current_difficulty=difficulty or 'all',
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
            difficulty_level=form.difficulty_level.data,
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
            difficulty_level=form.difficulty_level.data,
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


@admin_bp.route('/admin/config', methods=['GET', 'POST'])
@login_required
@admin_required
def configure_exam():
    """Handles updating global exam settings (percentages and duration)."""
    config = ExamService.get_or_create_config()
    form = ExamConfigForm(obj=config)
    
    if form.validate_on_submit():
        updated_cfg, error = ExamService.update_config(
            total_questions=form.total_questions.data,
            very_complex_pct=form.very_complex_percentage.data,
            complex_pct=form.complex_percentage.data,
            medium_pct=form.medium_percentage.data,
            easy_pct=form.easy_percentage.data,
            duration=form.exam_duration.data
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
            difficulty_level=form.difficulty_level.data,
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


@admin_bp.route('/admin/results')
@login_required
@admin_required
def view_results():
    """Lists teacher exam attempt details, tracking scores and browser violations."""
    attempts = ExamService.get_all_attempts()
    return render_template('admin/results.html', attempts=attempts)


@admin_bp.route('/admin/results/toggle-pass/<int:attempt_id>', methods=['POST'])
@login_required
@admin_required
def toggle_pass(attempt_id):
    """Allows manual pass adjustment for borderline scoring teachers."""
    success, error = ExamService.toggle_manual_pass(attempt_id)
    if success:
        flash("Candidate status updated successfully.", "success")
    else:
        flash(error or "Failed to update candidate status.", "danger")
    return redirect(url_for('admin.view_results'))
