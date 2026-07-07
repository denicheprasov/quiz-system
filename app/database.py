from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.environ.get("DATABASE_URL")
IS_PRODUCTION = os.environ.get("RENDER", "") or os.environ.get("IS_PRODUCTION", "")

if DATABASE_URL and "postgres" in DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL)
    except Exception:
        print(f"Invalid DATABASE_URL, falling back to SQLite")
        DATABASE_URL = None

if not DATABASE_URL or "postgres" not in DATABASE_URL:
    if IS_PRODUCTION:
        raise RuntimeError(
            "DATABASE_URL is not set. Configure Supabase PostgreSQL URL in "
            "Render Dashboard -> Environment Variables -> DATABASE_URL"
        )
    DATA_DIR = os.environ.get(
        "DATA_DIR",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    )
    os.makedirs(DATA_DIR, exist_ok=True)
    DB_PATH = os.path.join(DATA_DIR, "quiz.db")
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
