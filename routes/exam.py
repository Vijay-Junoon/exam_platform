from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from services.exam_service import ExamService
from models import db, ExamAttempt, ExamQuestion

exam_bp = Blueprint('exam', __name__)

def faculty_required(f):
    """Decorator to restrict access to faculty only."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_faculty:
            if current_user.is_authenticated and current_user.is_admin:
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@exam_bp.route('/')
@login_required
def index():
    """Default root routing logic based on user roles."""
    if current_user.is_admin:
        return redirect(url_for('admin.dashboard'))
    return redirect(url_for('exam.intro'))


@exam_bp.route('/exam/intro')
@login_required
@faculty_required
def intro():
    """Renders the listing of all available exams."""
    # Check if there is an active exam running already
    active = ExamService.get_active_attempt(current_user.id)
    if active:
        flash("Resuming your active exam attempt.", "info")
        return redirect(url_for('exam.show_question'))

    # Load all exams
    from models import Exam, Question
    exams = Exam.query.order_by(Exam.created_at.desc()).all()
    
    # Check question pool size per exam subject
    subject_counts = {}
    from sqlalchemy import func
    counts = db.session.query(Question.subject, func.count(Question.id)).group_by(Question.subject).all()
    for sub, count in counts:
        subject_counts[sub] = count

    # List past attempts for this faculty
    past_attempts = ExamAttempt.query.filter_by(user_id=current_user.id, completed=True)\
                                      .order_by(ExamAttempt.end_time.desc()).all()

    return render_template('exam/intro.html', 
                           exams=exams, 
                           subject_counts=subject_counts,
                           past_attempts=past_attempts,
                           exam=None)


@exam_bp.route('/exam/intro/<int:exam_id>')
@login_required
@faculty_required
def exam_instructions(exam_id):
    """Instructions page before starting a specific exam. Explains fullscreen requirements."""
    # Check if there is an active exam running already
    active = ExamService.get_active_attempt(current_user.id)
    if active:
        flash("Resuming your active exam attempt.", "info")
        return redirect(url_for('exam.show_question'))

    from models import Exam, Question
    exam = Exam.query.get_or_404(exam_id)
    
    # Check if we have enough questions in the database for this exam's subject
    total_q = Question.query.filter_by(subject=exam.subject).count()
    can_start = total_q >= exam.total_questions

    return render_template('exam/intro.html', 
                           exam=exam, 
                           can_start=can_start, 
                           total_available=total_q)


@exam_bp.route('/exam/start/<int:exam_id>', methods=['POST'])
@login_required
@faculty_required
def start_exam(exam_id):
    """Starts the exam, allocates questions, and redirects to the first question."""
    attempt, error = ExamService.create_exam_attempt(current_user.id, exam_id)
    if error:
        flash(error, 'danger')
        return redirect(url_for('exam.exam_instructions', exam_id=exam_id))
        
    return redirect(url_for('exam.show_question'))


@exam_bp.route('/exam/question', methods=['GET'])
@login_required
@faculty_required
def show_question():
    """Renders the single active question in sequence. Optimized to minimize query latency."""
    attempt = ExamService.get_active_attempt(current_user.id)
    if not attempt:
        flash("You do not have an active exam attempt. Start a new one.", "warning")
        return redirect(url_for('exam.intro'))

    # Verify if timer has expired on the backend using the preloaded attempt object
    expired, remaining_seconds = ExamService.check_timer_expired_with_attempt(attempt)
    if expired:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        flash("Your exam time has expired.", "danger")
        return redirect(url_for('exam.completed', attempt_id=attempt.id))

    # Retrieve current active question in-memory from preloaded attempt
    eq, progress_text = ExamService.get_current_question_from_attempt(attempt)
    if not eq:
        # No more questions, force submit
        ExamService.force_submit_exam(attempt.id)
        return redirect(url_for('exam.completed', attempt_id=attempt.id))

    question = eq.question
    config = ExamService.get_or_create_config()
    
    return render_template('exam/question.html',
                           attempt=attempt,
                           question=question,
                           progress_text=progress_text,
                           remaining_seconds=remaining_seconds,
                           exam_config=config)


@exam_bp.route('/exam/submit-answer', methods=['POST'])
@login_required
@faculty_required
def submit_answer():
    """Submits the answer for the current question and advances to the next."""
    attempt = ExamService.get_active_attempt(current_user.id)
    if not attempt:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'No active exam found.'}), 400
        flash("No active exam found.", "danger")
        return redirect(url_for('exam.intro'))

    question_id = request.form.get('question_id', type=int)
    selected_answer = request.form.get('answer')

    if not selected_answer or selected_answer not in ['A', 'B', 'C', 'D']:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Please select a valid option.'}), 400
        flash("Please select a valid option before submitting.", "warning")
        return redirect(url_for('exam.show_question'))

    success, error = ExamService.submit_answer(attempt.id, question_id, selected_answer)
    if not success:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': error or "Error submitting answer."}), 400
        flash(error or "Error submitting answer.", "danger")
        return redirect(url_for('exam.intro'))

    # Fetch correct answer for feedback
    from models import Question
    question = Question.query.get(question_id)
    correct_answer = question.correct_answer if question else 'A'
    is_correct = (selected_answer.upper() == correct_answer.upper())

    # Eager load attempt and its associated questions to optimize next question retrieval in AJAX
    db_attempt = ExamAttempt.query.options(
        joinedload(ExamAttempt.exam_questions).joinedload(ExamQuestion.question)
    ).get(attempt.id)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if is_ajax:
        # Fetch the next question details to send back to JS in-memory
        next_data = None
        if not db_attempt.completed:
            eq, progress_text = ExamService.get_current_question_from_attempt(db_attempt)
            if not eq:
                # Fallback if no questions left but completed was False
                ExamService.force_submit_exam(db_attempt.id)
                db_attempt.completed = True
            else:
                next_data = {
                    'question_id': eq.question.id,
                    'question_text': eq.question.question_text,
                    'option_a': eq.question.option_a,
                    'option_b': eq.question.option_b,
                    'option_c': eq.question.option_c,
                    'option_d': eq.question.option_d,
                    'progress_text': progress_text
                }
            
        _, remaining_seconds = ExamService.check_timer_expired_with_attempt(db_attempt)
        
        return jsonify({
            'completed': db_attempt.completed,
            'redirect_url': url_for('exam.completed', attempt_id=db_attempt.id),
            'is_correct': is_correct,
            'correct_answer': correct_answer,
            'next_question': next_data,
            'remaining_seconds': remaining_seconds
        })

    if db_attempt.completed:
        return redirect(url_for('exam.completed', attempt_id=db_attempt.id))
    return redirect(url_for('exam.show_question'))


@exam_bp.route('/exam/violation', methods=['POST'])
@login_required
@faculty_required
def log_violation():
    """AJAX endpoint to record fullscreen or focus tab-switching violations."""
    attempt = ExamService.get_active_attempt(current_user.id)
    if not attempt:
        return jsonify({'error': 'No active exam'}), 400

    max_allowed = current_app.config.get('MAX_VIOLATIONS_ALLOWED', 3)
    violation_count, auto_submitted = ExamService.log_violation(attempt.id, max_allowed=max_allowed)

    return jsonify({
        'violation_count': violation_count,
        'auto_submitted': auto_submitted,
        'message': 'Violation logged successfully.'
    })


@exam_bp.route('/exam/completed/<int:attempt_id>')
@login_required
@faculty_required
def completed(attempt_id):
    """Renders the final scorecard screen for the faculty, masking admin overrides or status."""
    attempt = ExamAttempt.query.get_or_404(attempt_id)
    
    # Ensure this attempt belongs to the logged-in user
    if attempt.user_id != current_user.id:
        abort(403)

    # Force submit the attempt if it's somehow not completed
    if not attempt.completed:
        ExamService.force_submit_exam(attempt.id)

    total_questions = ExamQuestion.query.filter_by(attempt_id=attempt.id).count()
    
    return render_template('exam/completed.html', 
                           attempt=attempt, 
                           total_questions=total_questions)
