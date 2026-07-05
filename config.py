import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration settings."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-dev-secret-key-12345')
    
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI:
        if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
            SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
    else:
        base_dir = os.path.abspath(os.path.dirname(__file__))
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(base_dir, 'exam_platform.db')}"
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    
    MAX_VIOLATIONS_ALLOWED = 1
