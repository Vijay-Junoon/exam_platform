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
                exam_duration=15 # 15 minutes default
            )
            db.session.add(config)
            db.session.commit()
        return config

    @staticmethod
    def update_config(total_questions, very_complex_pct, complex_pct, medium_pct, easy_pct, duration):
        """Updates the exam configuration. Ensures percentages sum to 100."""
        if (very_complex_pct + complex_pct + medium_pct + easy_pct) != 100:
            return None, "Error: Difficulty percentages must sum to exactly 100%."
            
        config = ExamService.get_or_create_config()
        config.total_questions = total_questions
        config.very_complex_percentage = very_complex_pct
        config.complex_percentage = complex_pct
        config.medium_percentage = medium_pct
        config.easy_percentage = easy_pct
        config.exam_duration = duration

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
            
        config = ExamService.get_or_create_config()
        duration_delta = timedelta(minutes=config.exam_duration)
        expiry_time = attempt.start_time + duration_delta
        now = datetime.now(timezone.utc)

        remaining_seconds = int((expiry_time - now).total_seconds())

        if remaining_seconds <= 0:
            attempt.completed = True
            attempt.end_time = datetime.now(timezone.utc)
            return True, 0

        return False, remaining_seconds

    @staticmethod
    def create_exam_attempt(user_id):
        """
        Starts a new exam attempt.
        Calculates difficulty breakdown, selects random questions, and initializes attempt sequence.
        """
        # Ensure no active attempt exists
        active = ExamService.get_active_attempt(user_id)
        if active:
            return active, None

        config = ExamService.get_or_create_config()
        total_req = config.total_questions

        # Verify we have at least total_req questions in the entire database
        total_available = Question.query.count()
        if total_available < total_req:
            return None, f"Insufficient questions in the question bank. Required: {total_req}, Available: {total_available}. Please contact the administrator."

        # Calculate target counts per difficulty
        targets = {
            'very_complex': int(round((config.very_complex_percentage / 100.0) * total_req)),
            'complex': int(round((config.complex_percentage / 100.0) * total_req)),
            'medium': int(round((config.medium_percentage / 100.0) * total_req)),
            'easy': int(round((config.easy_percentage / 100.0) * total_req))
        }

        # Adjust for rounding discrepancies to ensure total sum is exactly total_req
        current_sum = sum(targets.values())
        if current_sum != total_req:
            diff = total_req - current_sum
            # Add/subtract the difference to the difficulty with the largest allocation
            max_diff = max(targets, key=targets.get)
            targets[max_diff] += diff

        selected_questions = []
        fallback_pool = []

        # Pull random questions for each difficulty
        for diff_level, count in targets.items():
            if count <= 0:
                continue
            # Query random questions for this level
            q_level = Question.query.filter_by(difficulty_level=diff_level).order_by(func.random()).all()
            
            taken = q_level[:count]
            selected_questions.extend(taken)
            
            # Store leftovers for fallback
            fallback_pool.extend(q_level[count:])

        # If we couldn't fulfill the difficulty quotas due to shortage in specific levels
        if len(selected_questions) < total_req:
            needed = total_req - len(selected_questions)
            # Add general leftover questions from fallback_pool or other difficulties
            random.shuffle(fallback_pool)
            selected_questions.extend(fallback_pool[:needed])

        # If still short (edge case of database count vs config total), fetch any remaining question not selected
        if len(selected_questions) < total_req:
            selected_ids = [q.id for q in selected_questions]
            rems = Question.query.filter(~Question.id.in_(selected_ids)).order_by(func.random()).all()
            selected_questions.extend(rems[:(total_req - len(selected_questions))])

        # Final check
        if len(selected_questions) < total_req:
            return None, "Unable to generate exam. There are not enough questions in the database."

        # Shuffle selected questions to ensure random order
        random.shuffle(selected_questions)

        # Create ExamAttempt record
        attempt = ExamAttempt(
            user_id=user_id,
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
            attempt.score += 1

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

        config = ExamService.get_or_create_config()
        duration_delta = timedelta(minutes=config.exam_duration)
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
            
        attempt.manually_passed = not attempt.manually_passed
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
