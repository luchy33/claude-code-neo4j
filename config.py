import os

from dotenv import load_dotenv

load_dotenv()  # read .env so `python seed.py` gets the same settings as `flask run`


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-not-secret")
    # Relative paths are resolved against the Flask instance folder.
    DATABASE = os.environ.get("DATABASE", "ektemat.sqlite")
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB per request (image uploads)
    IMAGE_GENERATOR = os.environ.get("IMAGE_GENERATOR", "claude")  # "claude" or "fake"
    CSRF_ENABLED = True
    SESSION_COOKIE_SAMESITE = "Lax"
    TESTING = False


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test"
    IMAGE_GENERATOR = "fake"
    CSRF_ENABLED = False
