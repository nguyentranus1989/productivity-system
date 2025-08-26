import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration"""
    # Environment detection
    ENV = os.getenv('ENVIRONMENT', 'development')
    IS_PRODUCTION = ENV == 'production'
    
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    API_KEY = os.getenv('API_KEY', 'dev-api-key-123')
    
    # Determine API URLs based on environment
    if IS_PRODUCTION:
        API_BASE_URL = 'http://134.199.194.237:5000'
        FRONTEND_URL = 'http://134.199.194.237'
    else:
        API_BASE_URL = 'http://localhost:5000'
        FRONTEND_URL = 'http://localhost:5000'
    
    # Server settings
    HOST = '0.0.0.0'
    PORT = int(os.getenv('PORT', 5000))
    
    # Database settings
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_NAME = os.getenv('DB_NAME', 'productivity_tracker')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    
    # Redis settings
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    
    # Connecteam API - REMOVE HARDCODED VALUES
    CONNECTEAM_API_KEY = os.getenv('CONNECTEAM_API_KEY')
    CONNECTEAM_CLOCK_ID = int(os.getenv('CONNECTEAM_CLOCK_ID', 0)) if os.getenv('CONNECTEAM_CLOCK_ID') else None
    ENABLE_AUTO_SYNC = os.getenv('ENABLE_AUTO_SYNC', 'false').lower() == 'true'
    SYNC_INTERVAL = int(os.getenv('SYNC_INTERVAL', 300))
    CONNECTEAM_BASE_URL = os.getenv('CONNECTEAM_BASE_URL', 'https://api.connecteam.com/v1')
    
    # PodFactory settings
    PODFACTORY_API_ENDPOINT = os.getenv('PODFACTORY_API_ENDPOINT')
    PODFACTORY_API_KEY = os.getenv('PODFACTORY_API_KEY')
    
    # Application settings
    TIMEZONE = 'America/Chicago'  # Mobile, Alabama timezone
    BATCH_SIZE = 100
    IDLE_CHECK_INTERVAL = timedelta(minutes=10)
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/app.log')
    
    # Email settings
    SMTP_HOST = os.getenv('SMTP_HOST')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587)) if os.getenv('SMTP_PORT') else 587
    SMTP_USER = os.getenv('SMTP_USER')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
    REPORT_FROM_EMAIL = os.getenv('REPORT_FROM_EMAIL')
    REPORT_TO_EMAILS = os.getenv('REPORT_TO_EMAILS', '').split(',')

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    DB_NAME = 'productivity_tracker_test'

# Configuration dictionary
config_dict = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

# Get the active configuration
env = os.getenv('ENVIRONMENT', 'development')
config = config_dict.get(env, config_dict['default'])()

# REMOVE THE HARDCODED CONNECTEAM_CONFIG - use config object instead