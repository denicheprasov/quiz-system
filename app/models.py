from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_teacher = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    quizzes = relationship("Quiz", back_populates="creator")
    results = relationship("Result", back_populates="user")
    variants = relationship("Variant", back_populates="creator")
    assigned_tests = relationship(
        "AssignedTest", 
        back_populates="user",
        foreign_keys="AssignedTest.user_id"
    )
    assigned_by_me = relationship(
        "AssignedTest",
        back_populates="assigned_by_user",
        foreign_keys="AssignedTest.assigned_by"
    )
    practice_sessions = relationship("PracticeSession", back_populates="practice_user", foreign_keys="PracticeSession.user_id")

class Quiz(Base):
    __tablename__ = "quizzes"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    creator = relationship("User", back_populates="quizzes")
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")
    assigned_tests = relationship("AssignedTest", back_populates="quiz")
    results = relationship("Result", back_populates="quiz")  # ← ДОБАВЛЯЕМ

class Question(Base):
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    image_url = Column(String(500), nullable=True)
    file_url = Column(String(500), nullable=True)
    
    answer_count = Column(Integer, default=1)
    correct_answers = Column(JSON, nullable=False)
    task_type = Column(String(20), default="standard")
    total_points = Column(Integer, default=1)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    quiz = relationship("Quiz", back_populates="questions")

class Result(Base):
    __tablename__ = "results"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    assigned_test_id = Column(Integer, ForeignKey("assigned_tests.id"), nullable=True)
    score = Column(Integer)
    total_possible = Column(Integer)
    completed_at = Column(DateTime, default=datetime.utcnow)
    answers = Column(Text)
    
    user = relationship("User", back_populates="results")
    quiz = relationship("Quiz", back_populates="results")  # ← ДОБАВЛЯЕМ
    assigned_test = relationship("AssignedTest", back_populates="results")

# ===== БАНК ЗАДАНИЙ =====
class TaskBank(Base):
    __tablename__ = "task_bank"
    
    id = Column(Integer, primary_key=True, index=True)
    task_number = Column(Integer, nullable=False)
    source_file = Column(String(255), nullable=True)
    order_in_file = Column(Integer, nullable=True)
    
    text = Column(Text, nullable=False)
    image_url = Column(String(500), nullable=True)
    file_url = Column(String(500), nullable=True)
    table_data = Column(Text, nullable=True)
    question = Column(Text, nullable=True)
    correct_answer = Column(String(50), nullable=False)
    answer_type = Column(String(20), default="int")
    answer_count = Column(Integer, default=1)
    points = Column(Integer, default=1)
    
    topic = Column(String(100), nullable=True)
    difficulty = Column(String(20), default="base")
    tags = Column(String(255), nullable=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    variant_tasks = relationship("VariantTask", back_populates="task")
    practice_tasks = relationship("PracticeTask", back_populates="task")

class Variant(Base):
    __tablename__ = "variants"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    is_public = Column(Boolean, default=False)
    
    creator = relationship("User", back_populates="variants")
    variant_tasks = relationship("VariantTask", back_populates="variant", cascade="all, delete-orphan")

class VariantTask(Base):
    __tablename__ = "variant_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    variant_id = Column(Integer, ForeignKey("variants.id"))
    task_bank_id = Column(Integer, ForeignKey("task_bank.id"))
    order_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    variant = relationship("Variant", back_populates="variant_tasks")
    task = relationship("TaskBank", back_populates="variant_tasks")

# ===== ВЫДАННЫЕ ТЕСТЫ =====
class AssignedTest(Base):
    __tablename__ = "assigned_tests"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    assigned_by = Column(Integer, ForeignKey("users.id"))
    assigned_at = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime, nullable=True)
    status = Column(String(20), default="pending")
    
    user = relationship(
        "User", 
        back_populates="assigned_tests", 
        foreign_keys=[user_id]
    )
    assigned_by_user = relationship(
        "User", 
        back_populates="assigned_by_me", 
        foreign_keys=[assigned_by]
    )
    quiz = relationship("Quiz", back_populates="assigned_tests")
    results = relationship("Result", back_populates="assigned_test")

# ===== ТРЕНИРОВКА =====
class PracticeSession(Base):
    __tablename__ = "practice_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(255), nullable=True)
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    practice_user = relationship("User", back_populates="practice_sessions", foreign_keys=[user_id])
    practice_tasks = relationship("PracticeTask", back_populates="session")


class StudentGroup(Base):
    __tablename__ = "student_groups"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    invite_code = Column(String(20), unique=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    creator = relationship("User", backref="created_groups")
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")


class GroupMember(Base):
    __tablename__ = "group_members"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("student_groups.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    group = relationship("StudentGroup", back_populates="members")
    student = relationship("User", backref="memberships")


class PracticeTask(Base):
    __tablename__ = "practice_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("practice_sessions.id"))
    task_bank_id = Column(Integer, ForeignKey("task_bank.id"))
    order_number = Column(Integer, nullable=False)
    user_answer = Column(String(50), nullable=True)
    is_correct = Column(Boolean, default=False)
    points_earned = Column(Integer, default=0)
    answered_at = Column(DateTime, nullable=True)
    
    session = relationship("PracticeSession", back_populates="practice_tasks")
    task = relationship("TaskBank", back_populates="practice_tasks")