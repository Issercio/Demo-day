import os
from datetime import timedelta

class Config:
    """Base configuration class.
    
    Contains default configuration settings for the application.
    All other configuration classes inherit from this class.
    """
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default_secret_key')
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Désactive le suivi des modifications SQLAlchemy (meilleures performances)
    
    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

class DevelopmentConfig(Config):
    """Development configuration settings.
    
    Used for local development with debugging enabled.
    """
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URI', 'sqlite:///development.db')

class TestingConfig(Config):
    """Testing configuration settings.
    
    Used for running tests with testing mode enabled.
    """
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URI', 'sqlite:///testing.db')
    
    # Shorter token expiration for testing
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(hours=1)

class ProductionConfig(Config):
    """Production configuration settings.
    
    Used for deployment in production environment.
    """
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///production.db')
    
    # Use a separate secret key for JWT in production
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
