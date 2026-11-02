import os

from dotenv import load_dotenv

load_dotenv()  # read .env so `python seed.py` gets the same settings as `flask run`


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-not-secret")
    NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "ektemat-dev-db")  # dev default, see docker-compose.yml
    NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "neo4j")
    # Relative paths are resolved against the Flask instance folder.
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
    # The separate neo4j-test container from docker-compose.yml. Tests wipe it, so never point it at dev data.
    NEO4J_URI = os.environ.get("TEST_NEO4J_URI", "bolt://localhost:7688")
    NEO4J_USER = os.environ.get("TEST_NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.environ.get("TEST_NEO4J_PASSWORD", "ektemat-test")
    NEO4J_DATABASE = "neo4j"
