from datetime import datetime, timezone
from . import db

class ExamConfiguration(db.Model):
    """Stores active configurations for the exam, including percentages per difficulty and duration."""
    __tablename__ = 'exam_configurations'

    id = db.Column(db.Integer, primary_key=True)
    total_questions = db.Column(db.Integer, nullable=False, default=40)
    very_complex_percentage = db.Column(db.Integer, nullable=False, default=25)
    complex_percentage = db.Column(db.Integer, nullable=False, default=25)
    medium_percentage = db.Column(db.Integer, nullable=False, default=30)
    easy_percentage = db.Column(db.Integer, nullable=False, default=20)
    exam_duration = db.Column(db.Integer, nullable=False, default=60) # duration in minutes

    def validate_percentages(self):
        """Helper to ensure percentages sum to 100."""
        return (self.very_complex_percentage + 
                self.complex_percentage + 
                self.medium_percentage + 
                self.easy_percentage) == 100

    def __repr__(self):
        return f"<ExamConfiguration id={self.id} total={self.total_questions}>"


class Exam(db.Model):
    """Represents a specific examination created by an administrator."""
    __tablename__ = 'exams'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    subject = db.Column(db.String(100), nullable=False)

    total_questions = db.Column(db.Integer, nullable=False, default=10)
    very_complex_percentage = db.Column(db.Integer, nullable=False, default=25)
    complex_percentage = db.Column(db.Integer, nullable=False, default=25)
    medium_percentage = db.Column(db.Integer, nullable=False, default=30)
    easy_percentage = db.Column(db.Integer, nullable=False, default=20)
    exam_duration = db.Column(db.Integer, nullable=False, default=15) # duration in minutes

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    attempts = db.relationship('ExamAttempt', back_populates='exam', cascade='all, delete-orphan')

    def validate_percentages(self):
        """Helper to ensure percentages sum to 100."""
        return (self.very_complex_percentage + 
                self.complex_percentage + 
                self.medium_percentage + 
                self.easy_percentage) == 100

    def __repr__(self):
        return f"<Exam id={self.id} title={self.title} subject={self.subject}>"


class ExamAttempt(db.Model):
    """Tracks every exam attempt made by a teacher."""
    __tablename__ = 'exam_attempts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id', ondelete='CASCADE'), nullable=True)
    start_time = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    end_time = db.Column(db.DateTime(timezone=True), nullable=True)
    score = db.Column(db.Integer, default=0, nullable=False)
    violation_count = db.Column(db.Integer, default=0, nullable=False)
    manually_passed = db.Column(db.Boolean, default=False, nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    user = db.relationship('User', back_populates='attempts')
    exam = db.relationship('Exam', back_populates='attempts')
    exam_questions = db.relationship('ExamQuestion', back_populates='attempt', cascade='all, delete-orphan')
    answers = db.relationship('Answer', back_populates='attempt', cascade='all, delete-orphan')

    @property
    def percentage_score(self):
        """Calculates percentage based on attempt questions."""
        total_questions = len(self.exam_questions)
        if total_questions == 0:
            return 0.0
        return round((self.score / total_questions) * 100, 2)

    @property
    def passed(self):
        """True if manual pass is granted, or standard score is >= 40% (20/50 etc.)."""
        # If manually passed by admin, always True
        if self.manually_passed:
            return True
        # Standard passing threshold is 40%
        return self.percentage_score >= 40.0

    def __repr__(self):
        return f"<ExamAttempt {self.id} User={self.user_id} Score={self.score} Completed={self.completed}>"


class ExamQuestion(db.Model):
    """Junction table freezing the exact question sequence assigned to an attempt."""
    __tablename__ = 'exam_questions'

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('exam_attempts.id', ondelete='CASCADE'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    question_order = db.Column(db.Integer, nullable=False) # 1-based order index
    attempted = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    attempt = db.relationship('ExamAttempt', back_populates='exam_questions')
    question = db.relationship('Question')

    def __repr__(self):
        return f"<ExamQuestion Attempt={self.attempt_id} Question={self.question_id} Order={self.question_order}>"


class Answer(db.Model):
    """Stores the candidate's answer response to a specific question during an attempt."""
    __tablename__ = 'answers'

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('exam_attempts.id', ondelete='CASCADE'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    selected_answer = db.Column(db.String(1), nullable=False) # 'A', 'B', 'C', or 'D'
    is_correct = db.Column(db.Boolean, nullable=False)

    # Relationships
    attempt = db.relationship('ExamAttempt', back_populates='answers')
    question = db.relationship('Question')

    def __repr__(self):
        return f"<Answer Attempt={self.attempt_id} Question={self.question_id} Selected={self.selected_answer} Correct={self.is_correct}>"
