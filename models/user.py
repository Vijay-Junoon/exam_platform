from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db

class User(UserMixin, db.Model):
    """User model for storing registration and authentication info."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='teacher') # 'admin' or 'teacher'
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    attempts = db.relationship('ExamAttempt', back_populates='user', cascade='all, delete-orphan')

    def set_password(self, password):
        """Hashes the password and saves it."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifies the hashed password."""
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        """Returns True if the user is an administrator."""
        return self.role == 'admin'

    @property
    def is_teacher(self):
        """Returns True if the user is a teacher."""
        return self.role == 'teacher'

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
