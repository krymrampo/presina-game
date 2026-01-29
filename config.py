"""
Configuration for Presina app.
"""
import os


class Config:
    """Base configuration."""
    _default_secret = 'presina-dev-key-not-for-production'
    SECRET_KEY = os.environ.get('SECRET_KEY', _default_secret)
    DEBUG = False
    TESTING = False
    
    # Socket.IO settings
    CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ORIGINS', '*')
    
    # Game settings
    MAX_ROOMS = 100
    MAX_CHAT_MESSAGES = 100
    MAX_NAME_LENGTH = 30
    MAX_ROOM_NAME_LENGTH = 50
    ENABLE_DUMMY_PLAYERS = False


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    ENABLE_DUMMY_PLAYERS = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    
    # In production, require SECRET_KEY from environment
    @property
    def SECRET_KEY(self):
        key = os.environ.get('SECRET_KEY')
        if not key:
            raise ValueError('SECRET_KEY must be set in production environment')
        return key
    
    # In production, set proper CORS origins (do not allow all)
    CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ORIGINS', None)


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
    cfg_class = config.get(env, config['default'])
    return cfg_class()
