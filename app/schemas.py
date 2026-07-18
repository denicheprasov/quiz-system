from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class TaskType(str, Enum):
    STANDARD = "standard"
    EXTENDED = "extended"


# ===== User =====
class UserBase(BaseModel):
    username: str
    email: EmailStr
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    patronymic: Optional[str] = None
    is_teacher: bool = False


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Question =====
class QuestionBase(BaseModel):
    number: int
    text: str
    image_url: Optional[str] = None
    file_url: Optional[str] = None
    answer_count: int = 1
    correct_answers: List[str]
    task_type: TaskType = TaskType.STANDARD


class QuestionCreate(QuestionBase):
    pass


class QuestionResponse(QuestionBase):
    id: int
    quiz_id: int
    total_points: int
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Quiz =====
class QuizBase(BaseModel):
    title: str
    description: Optional[str] = None


class QuizCreate(QuizBase):
    questions: List[QuestionCreate]


class QuizResponse(QuizBase):
    id: int
    created_by: int
    created_at: datetime
    is_active: bool
    questions: List[QuestionResponse] = []

    class Config:
        from_attributes = True


# ===== Assigned Test =====
class AssignedTestBase(BaseModel):
    user_id: int
    quiz_id: int
    due_date: Optional[datetime] = None


class AssignedTestCreate(AssignedTestBase):
    pass


class AssignedTestResponse(AssignedTestBase):
    id: int
    assigned_by: int
    assigned_at: datetime
    status: str
    quiz: QuizResponse

    class Config:
        from_attributes = True


# ===== Result =====
class ResultResponse(BaseModel):
    id: int
    user_id: int
    quiz_id: int
    score: int
    total_possible: int
    completed_at: datetime
    answers: Dict[str, List[str]]

    class Config:
        from_attributes = True


# ===== Auth =====
class Token(BaseModel):
    access_token: str
    token_type: str


# ===== BANK =====
class TaskBankBase(BaseModel):
    task_number: int
    source_file: Optional[str] = None
    order_in_file: Optional[int] = None
    text: str
    image_url: Optional[str] = None
    file_url: Optional[str] = None
    table_data: Optional[str] = None
    question: Optional[str] = None
    correct_answer: str
    answer_type: str = "int"
    answer_count: int = 1
    points: int = 1
    topic: Optional[str] = None
    difficulty: Optional[str] = None
    tags: Optional[str] = None
    is_verified: bool = True


class TaskBankCreate(TaskBankBase):
    pass


class TaskBankResponse(TaskBankBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ===== VARIANT =====
class VariantBase(BaseModel):
    title: str
    description: Optional[str] = None
    is_public: bool = False


class VariantCreate(VariantBase):
    task_ids: List[int]


class VariantTaskResponse(BaseModel):
    id: int
    order_number: int
    task: Optional[TaskBankResponse] = None

    class Config:
        from_attributes = True


class VariantResponse(VariantBase):
    id: int
    created_by: int
    created_by_name: Optional[str] = None
    assigned_groups: List[str] = []  # названия групп, которым выдан вариант
    created_at: datetime
    is_active: bool
    variant_tasks: List[VariantTaskResponse] = []

    class Config:
        from_attributes = True


# ===== PRACTICE =====
class PracticeTaskResponse(BaseModel):
    id: int
    order_number: int
    task: Optional[TaskBankResponse] = None
    user_answer: Optional[str] = None
    is_correct: bool = False
    points_earned: int = 0
    answered_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PracticeSessionResponse(BaseModel):
    id: int
    title: Optional[str]
    total_tasks: int
    completed_tasks: int
    correct_answers: int
    started_at: datetime
    completed_at: Optional[datetime]
    tasks: List[PracticeTaskResponse] = Field(default=[], validation_alias="practice_tasks")

    class Config:
        from_attributes = True


class PracticeStartRequest(BaseModel):
    task_numbers: Optional[List[int]] = None  # Если None - все номера
    count: Optional[int] = None  # Количество заданий


class PracticeAnswerRequest(BaseModel):
    task_id: int
    answer: str


# ===== Import =====
class ImportResult(BaseModel):
    total: int
    imported: int
    skipped: int
    errors: List[str] = []
    tasks: List[TaskBankResponse] = []


class GenerateVariantRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    shuffle: bool = True
    fill_missing: bool = True
    count: Optional[int] = None  # Для учеников - сколько заданий
