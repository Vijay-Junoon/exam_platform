import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

class Config:
    """Base configuration settings."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-dev-secret-key-12345')
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI:
        if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
            # SQLAlchemy requires postgresql:// instead of postgres:// (which is often used by Heroku/Supabase)
            SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
    else:
        # Smart Developer Fallback: SQLite for instant testing without Postgres server
        base_dir = os.path.abspath(os.path.dirname(__file__))
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(base_dir, 'exam_platform.db')}"
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # GROQ API Configuration
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    
    # Application Security Settings
    MAX_VIOLATIONS_ALLOWED = 1
