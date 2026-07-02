from flask_sqlalchemy import SQLAlchemy

# Initialize db instance
db = SQLAlchemy()

# Import models so they register with Alembic/SQLAlchemy
from .user import User
from .question import Question
from .exam import Exam, ExamConfiguration, ExamAttempt, ExamQuestion, Answer
