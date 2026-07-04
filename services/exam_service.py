import random
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from models import db, ExamConfiguration, ExamAttempt, ExamQuestion, Answer, Question, User

class ExamService:
    @staticmethod
    def get_or_create_config():
        """Retrieves the system exam configuration, creating a default one if none exists."""
        config = ExamConfiguration.query.first()
        if not config:
            config = ExamConfiguration(
                total_questions=10, # small default for easy initial test
                very_complex_percentage=20,
                complex_percentage=20,
                medium_percentage=30,
                easy_percentage=30,
                exam_duration=15, # 15 minutes default
                use_difficulty_distribution=True,
                pattern='HR',
                passing_marks=4.0,
                override_threshold=3.0
            )
            db.session.add(config)
            db.session.commit()
        return config

    @staticmethod
    def update_config(total_questions, duration, pattern, passing_marks, override_threshold):
        """Updates the exam configuration."""
        config = ExamService.get_or_create_config()
        config.total_questions = total_questions
        config.exam_duration = duration
        config.pattern = pattern
        config.passing_marks = passing_marks
        config.override_threshold = override_threshold

        try:
            db.session.commit()
            return config, None
        except Exception as e:
            db.session.rollback()
            return None, f"Database error: {str(e)}"

    @staticmethod
    def get_active_attempt(user_id):
        """Checks if there is an ongoing (uncompleted) exam attempt for this user. Eager loads questions to optimize latency."""
        attempt = ExamAttempt.query.options(
            joinedload(ExamAttempt.exam_questions).joinedload(ExamQuestion.question)
        ).filter_by(user_id=user_id, completed=False).first()
        
        if attempt:
            # Verify if timer has already expired
            expired, _ = ExamService.check_timer_expired_with_attempt(attempt)
            if expired:
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                return None
        return attempt

    @staticmethod
    def get_current_question_from_attempt(attempt):
        """Finds the current question from a preloaded attempt object in-memory to eliminate database queries."""
        # Sort in-memory by sequence order
        questions = sorted(attempt.exam_questions, key=lambda x: x.question_order)
        eq = next((q for q in questions if not q.attempted), None)
        if not eq:
            return None, None
        return eq, f"Question {eq.question_order} of {len(questions)}"

    @staticmethod
    def check_timer_expired_with_attempt(attempt):
        """Timer check that uses a preloaded attempt object to save database queries."""
        if not attempt:
            return True, 0
        if attempt.completed:
            return False, 0
            
        if attempt.exam:
            duration = attempt.exam.exam_duration
        else:
            config = ExamService.get_or_create_config()
            duration = config.exam_duration
            
        duration_delta = timedelta(minutes=duration)
        expiry_time = attempt.start_time + duration_delta
        now = datetime.now(timezone.utc)

        remaining_seconds = int((expiry_time - now).total_seconds())

        if remaining_seconds <= 0:
            attempt.completed = True
            attempt.end_time = datetime.now(timezone.utc)
            return True, 0

        return False, remaining_seconds

    @staticmethod
    def create_exam_attempt(user_id, exam_id):
        """
        Starts a new exam attempt for a specific Exam.
        Selects random questions from the exam's subject, and initializes attempt sequence.
        """
        # Ensure no active attempt exists
        active = ExamService.get_active_attempt(user_id)
        if active:
            return active, None

        # Fetch the specific exam config
        from models import Exam
        exam = Exam.query.get(exam_id)
        if not exam:
            return None, "Exam not found."

        total_req = exam.total_questions
        subject = exam.subject

        # Verify we have at least total_req questions in the specified subject
        total_available = Question.query.filter_by(subject=subject).count()
        if total_available < total_req:
            return None, f"Insufficient questions in the question bank for subject '{subject}'. Required: {total_req}, Available: {total_available}. Please contact the administrator."

        # Query random questions from the given subject
        selected_questions = Question.query.filter_by(subject=subject).order_by(func.random()).limit(total_req).all()

        # Final check
        if len(selected_questions) < total_req:
            return None, f"Unable to generate exam. There are not enough questions in subject '{subject}'."

        # Shuffle selected questions to ensure random order
        random.shuffle(selected_questions)

        # Create ExamAttempt record
        attempt = ExamAttempt(
            user_id=user_id,
            exam_id=exam.id,
            start_time=datetime.now(timezone.utc),
            completed=False,
            score=0,
            violation_count=0
        )
        db.session.add(attempt)
        db.session.flush() # get attempt ID

        # Save question sequence
        for idx, question in enumerate(selected_questions):
            eq = ExamQuestion(
                attempt_id=attempt.id,
                question_id=question.id,
                question_order=idx + 1,
                attempted=False
            )
            db.session.add(eq)

        try:
            db.session.commit()
            return attempt, None
        except Exception as e:
            db.session.rollback()
            return None, f"Failed to initialize exam: {str(e)}"

    @staticmethod
    def get_current_question(attempt_id):
        """Retrieves the next unattempted question in sequence order for the given attempt."""
        eq = ExamQuestion.query.filter_by(attempt_id=attempt_id, attempted=False)\
                               .order_by(ExamQuestion.question_order.asc()).first()
        if not eq:
            return None, None
        
        # Calculate progress: e.g., question 3 of 10
        total_questions = ExamQuestion.query.filter_by(attempt_id=attempt_id).count()
        current_num = eq.question_order
        
        return eq, f"Question {current_num} of {total_questions}"

    @staticmethod
    def submit_answer(attempt_id, question_id, selected_answer):
        """
        Submits answer for the active question.
        Ensures questions are submitted strictly in sequence and checks for timer expiry.
        Optimized with eager loading and in-memory checks to minimize network latency.
        """
        # Eager load attempt, exam_questions, and their respective questions in one single query
        attempt = ExamAttempt.query.options(
            joinedload(ExamAttempt.exam_questions).joinedload(ExamQuestion.question)
        ).get(attempt_id)
        
        if not attempt or attempt.completed:
            return False, "Exam is already completed or invalid."

        # Check timer in-memory
        expired, _ = ExamService.check_timer_expired_with_attempt(attempt)
        if expired:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            return False, "Time has expired! Exam submitted automatically."

        # Get current active question in order in-memory
        eq, _ = ExamService.get_current_question_from_attempt(attempt)
        if not eq or eq.question_id != question_id:
            return False, "Invalid question sequence. You can only answer the current question."

        question = eq.question
        is_correct = (selected_answer.upper() == question.correct_answer.upper())

        # Save answer
        ans = Answer(
            attempt_id=attempt_id,
            question_id=question_id,
            selected_answer=selected_answer.upper(),
            is_correct=is_correct
        )
        db.session.add(ans)

        # Mark question attempted in-memory
        eq.attempted = True

        # Update attempt score
        if is_correct:
            attempt.score += 1.0
        else:
            if attempt.pattern == 'GATE':
                attempt.score -= 1.0 / 3.0

        try:
            # Check if there are any remaining questions in-memory
            next_eq = next((q for q in attempt.exam_questions if not q.attempted), None)
            if not next_eq:
                attempt.completed = True
                attempt.end_time = datetime.now(timezone.utc)

            db.session.commit()
            return True, None
        except Exception as e:
            db.session.rollback()
            return False, f"Database error during answer submission: {str(e)}"

    @staticmethod
    def check_timer_expired(attempt_id):
        """
        Backend verification of time elapsed since exam startup.
        If expired, submits attempt. Returns (is_expired, remaining_seconds).
        """
        attempt = ExamAttempt.query.get(attempt_id)
        if not attempt:
            return True, 0

        if attempt.completed:
            return False, 0

        if attempt.exam:
            duration = attempt.exam.exam_duration
        else:
            config = ExamService.get_or_create_config()
            duration = config.exam_duration

        duration_delta = timedelta(minutes=duration)
        expiry_time = attempt.start_time + duration_delta
        now = datetime.now(timezone.utc)

        remaining_seconds = int((expiry_time - now).total_seconds())

        if remaining_seconds <= 0:
            # Time's up! Force mark completed
            attempt.completed = True
            attempt.end_time = datetime.now(timezone.utc)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            return True, 0

        return False, remaining_seconds

    @staticmethod
    def log_violation(attempt_id, max_allowed=3):
        """
        Logs a fullscreen or tab-switch violation.
        Auto-submits if violations reach or exceed the maximum limit.
        """
        attempt = ExamAttempt.query.get(attempt_id)
        if not attempt or attempt.completed:
            return 0, False

        attempt.violation_count += 1
        auto_submitted = False

        if attempt.violation_count >= max_allowed:
            attempt.completed = True
            attempt.end_time = datetime.now(timezone.utc)
            auto_submitted = True

        try:
            db.session.commit()
            return attempt.violation_count, auto_submitted
        except Exception:
            db.session.rollback()
            return attempt.violation_count, False

    @staticmethod
    def get_all_attempts():
        """Returns all completed attempts sorted by end time."""
        return ExamAttempt.query.order_by(ExamAttempt.start_time.desc()).all()

    @staticmethod
    def toggle_manual_pass(attempt_id):
        """Grants manual pass override status for borderline scoring candidate."""
        attempt = ExamAttempt.query.get(attempt_id)
        if not attempt:
            return False, "Exam attempt not found."
            
        if not attempt.manually_passed:
            # Check eligibility for manual override
            if not attempt.can_override:
                return False, "Candidate score is below the override threshold and cannot be manually passed."
            attempt.manually_passed = True
        else:
            attempt.manually_passed = False
            
        try:
            db.session.commit()
            return True, None
        except Exception as e:
            db.session.rollback()
            return False, f"Database error toggling pass override: {str(e)}"
            
    @staticmethod
    def force_submit_exam(attempt_id):
        """Forces immediate completion of the exam attempt."""
        attempt = ExamAttempt.query.get(attempt_id)
        if not attempt or attempt.completed:
            return True
        attempt.completed = True
        attempt.end_time = datetime.now(timezone.utc)
        try:
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False
