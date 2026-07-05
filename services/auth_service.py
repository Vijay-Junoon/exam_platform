from models import db, User

class AuthService:
    @staticmethod
    def get_user_by_id(user_id):
        """Finds user by their ID (called by Flask-Login user_loader)."""
        return User.query.get(int(user_id))

    @staticmethod
    def get_user_by_email(email):
        """Finds user by email address."""
        return User.query.filter(User.email.ilike(email)).first()

    @staticmethod
    def register_user(name, email, password, role='faculty', dept=None, faculty_role=None, subject=None):
        """Registers a new user, checks duplicates and hashes password."""
        existing_user = AuthService.get_user_by_email(email)
        if existing_user:
            return None, "A user with this email address already exists."
        
        new_user = User(
            name=name,
            email=email,
            role=role,
            dept=dept,
            faculty_role=faculty_role,
            subject=subject
        )
        new_user.set_password(password)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            return new_user, None
        except Exception as e:
            db.session.rollback()
            return None, f"Database error during registration: {str(e)}"

    @staticmethod
    def authenticate_user(email, password):
        """Authenticates user credentials. Returns User object if successful, else None."""
        user = AuthService.get_user_by_email(email)
        if user and user.check_password(password):
            return user
        return None
