from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import sys

DATABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get("DATABASE_URL")
engine = None

if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL)
        print(f"Database: PostgreSQL ({DATABASE_URL[:25]}...)", flush=True)
    except Exception as e:
        print(f"DB init error: {e}. Falling back to SQLite.", flush=True)
        engine = None

if engine is None:
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
    print(f"Database: SQLite ({DB_PATH})", flush=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
