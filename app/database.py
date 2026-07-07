from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get("DATABASE_URL")
USING_POSTGRES = False

if SUPABASE_URL:
    try:
        engine = create_engine(SUPABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        USING_POSTGRES = True
        print("DB: Supabase PostgreSQL (connected)", flush=True)
    except Exception as e:
        print(f"DB: PostgreSQL unavailable ({e}), falling back to SQLite", flush=True)

if not USING_POSTGRES:
    DATA_DIR = os.environ.get(
        "DATA_DIR",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    )
    os.makedirs(DATA_DIR, exist_ok=True)
    DB_PATH = os.path.join(DATA_DIR, "quiz.db")
    engine = create_engine(
        f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False}
    )
    print(f"DB: SQLite ({DB_PATH})", flush=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
