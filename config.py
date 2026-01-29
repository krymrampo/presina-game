"""
Configuration for Presina app.
"""
import os


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'presina-secret-key-change-in-production')
    DEBUG = False
    TESTING = False
    
    # Socket.IO settings
    CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ORIGINS', '*')
    
    # Game settings
    MAX_ROOMS = 100
    MAX_CHAT_MESSAGES = 100


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    # In production, set proper CORS origins
    CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ORIGINS', '*')


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True


# Config mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Get configuration based on environment."""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])
