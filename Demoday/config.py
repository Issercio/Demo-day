import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


PLACEHOLDER_SECRET_KEYS = {
    '',
    'change-me-to-a-long-random-string-min-32-chars',
    'florashop-dev-secret-key-min-32-chars',
}  # clés d'exemple : un JWT signé avec elles serait forgeable


def _resolve_secret_key():
    key = (os.environ.get('SECRET_KEY') or '').strip()
    if key in PLACEHOLDER_SECRET_KEYS or len(key) < 32:
        return os.urandom(32).hex()
    return key


class Config:
    DEBUG = False
    TESTING = False
    SECRET_KEY = _resolve_secret_key()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URI', 'sqlite:///development.db')


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URI', 'sqlite:///testing.db')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(hours=1)


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///production.db')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
