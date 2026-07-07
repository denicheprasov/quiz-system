import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine, inspect as sa_inspect
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import (
    User, Quiz, Question, Result, TaskBank, Variant, VariantTask,
    AssignedTest, PracticeSession, PracticeTask
)

SQLITE_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "quiz.db")
)
SQLITE_URL = f"sqlite:///{SQLITE_PATH}"
PG_URL = os.environ.get("DATABASE_URL")

if not PG_URL:
    print("ERROR: Set DATABASE_URL for Supabase PostgreSQL destination")
    sys.exit(1)

sqlite_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
pg_engine = create_engine(PG_URL)

SQLiteSession = sessionmaker(bind=sqlite_engine)
PGSession = sessionmaker(bind=pg_engine)

Base.metadata.create_all(bind=pg_engine)

sqlite_db = SQLiteSession()
pg_db = PGSession()

MODELS = [
    User, Quiz, Question, Result, TaskBank, Variant, VariantTask,
    AssignedTest, PracticeSession, PracticeTask
]

try:
    for model in MODELS:
        rows = sqlite_db.query(model).all()
        for row in rows:
            data = {c.name: getattr(row, c.name) for c in sa_inspect(model).columns}
            pg_db.execute(model.__table__.insert().values(**data))
        pg_db.commit()
        print(f"  Migrated {len(rows)} {model.__name__} records")
    print("\nMigration complete")
except Exception as e:
    pg_db.rollback()
    print(f"ERROR: {e}")
finally:
    sqlite_db.close()
    pg_db.close()
