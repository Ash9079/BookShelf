import os
from dotenv import load_dotenv

load_dotenv()

def _db_url():
    """Build MySQL URL from individual env vars or use DATABASE_URL directly."""
    if os.environ.get('DATABASE_URL'):
        return os.environ['DATABASE_URL']
    user   = os.environ.get('DB_USER', 'root')
    pw     = os.environ.get('DB_PASSWORD', 'Ash@1234')
    host   = os.environ.get('DB_HOST', 'localhost')
    port   = os.environ.get('DB_PORT', '3306')
    name   = os.environ.get('DB_NAME', 'book_recommender')
    return f'mysql+pymysql://{user}:{pw}@{host}:{port}/{name}'


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    CACHE_DEFAULT_TIMEOUT = 300
    BOOKS_PER_PAGE = 24
    RECS_PER_PAGE = 20


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = _db_url()
    CACHE_TYPE = 'SimpleCache'


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = _db_url()
    CACHE_TYPE = 'RedisCache'
    CACHE_REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    CACHE_TYPE = 'SimpleCache'


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'testing':     TestingConfig,
    'default':     DevelopmentConfig,
}
