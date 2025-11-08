import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration class."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess-this'
    MONGO_URI = os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/finance_tracker_saas'
    DATABASE_NAME = os.environ.get('DATABASE_NAME') or 'finance_tracker_saas'

    # Hardcoded Super Admin Telegram ID for initial setup
    SUPER_ADMIN_ID = "1836585300"

    # Telegram Bot Token (used by the web_service for scheduled reports)
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')

    # API Key for exchange rate service
    EXCHANGERATE_API_KEY = os.environ.get('EXCHANGERATE_API_KEY')

    # Ensure keys are present for production
    if not MONGO_URI:
        raise ValueError("No MONGO_URI set for Flask application.")

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = True

def get_config_class():
    """Returns the appropriate config class based on environment."""
    env = os.environ.get('FLASK_ENV', 'development')
    if env == 'production':
        return ProductionConfig
    return DevelopmentConfig