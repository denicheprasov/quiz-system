from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Optional
import random
from datetime import datetime
from app import models, schemas, auth, database
from app.auth import decode_token

router = APIRouter(prefix="/student", tags=["student"])
templates = Jinja2Templates(directory="app/templates")


# ===== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ =====
def get_user_from_request(request: Request, db: Session):
    """Получить пользователя из токена в cookies"""
    token = request.cookies.get("access_token")
    if not token:
        return None

    try:
        payload = decode_token(token)
        if not payload:
            return None

        user = (
            db.query(models.User)
            .filter(models.User.username == payload.get("sub"))
            .first()
        )
        return user
    except:
        return None


# ===== СТРАНИЦЫ (HTML) =====


@router.get("/dashboard", response_class=HTMLResponse)
async def student_dashboard_page(
    request: Request, db: Session = Depends(database.get_db)
):
    """Страница панели ученика"""
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "student_dashboard.html", {"request": request, "user": user}
    )


@router.get("/bank", response_class=HTMLResponse)
async def student_bank_page(request: Request, db: Session = Depends(database.get_db)):
    """Страница банка заданий для ученика"""
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "student_bank.html", {"request": request, "user": user}
    )


@router.get("/practice", response_class=HTMLResponse)
async def student_practice_page(
    request: Request, db: Session = Depends(database.get_db)
):
    """Страница тренировки"""
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "practice.html", {"request": request, "user": user}
    )


@router.get("/generate", response_class=HTMLResponse)
async def student_generate_page(
    request: Request, db: Session = Depends(database.get_db)
):
    """Страница генерации варианта"""
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "student_generate.html", {"request": request, "user": user}
    )


@router.get("/history", response_class=HTMLResponse)
async def student_history_page(
    request: Request, db: Session = Depends(database.get_db)
):
    """Страница истории"""
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "student_history.html", {"request": request, "user": user}
    )


# ===== API ЭНДПОИНТЫ (JSON) =====


@router.get("/api/dashboard")
def student_dashboard_api(request: Request, db: Session = Depends(database.get_db)):
    """API: Получить данные для дашборда ученика"""
    current_user = get_user_from_request(request, db)

    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Выданные тесты
    assigned = (
        db.query(models.AssignedTest)
        .filter(models.AssignedTest.user_id == current_user.id)
        .all()
    )

    # Статистика тренировок
    practice_sessions = (
        db.query(models.PracticeSession)
        .filter(models.PracticeSession.user_id == current_user.id)
        .order_by(models.PracticeSession.started_at.desc())
        .limit(5)
        .all()
    )

    return {
        "assigned_tests": assigned,
        "practice_sessions": practice_sessions,
        "total_assigned": len(assigned),
        "completed_assigned": len([a for a in assigned if a.status == "completed"]),
    }


@router.get("/api/assigned-tests", response_model=List[schemas.AssignedTestResponse])
def get_assigned_tests_api(
    request: Request,
    status: Optional[str] = None,
    db: Session = Depends(database.get_db),
):
    """API: Получить все выданные тесты"""
    current_user = get_user_from_request(request, db)

    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    query = db.query(models.AssignedTest).filter(
        models.AssignedTest.user_id == current_user.id
    )

    if status:
        query = query.filter(models.AssignedTest.status == status)

    return query.order_by(models.AssignedTest.assigned_at.desc()).all()


@router.get("/api/assigned-tests/{test_id}")
def get_assigned_test_api(
    test_id: int, request: Request, db: Session = Depends(database.get_db)
):
    """API: Получить выданный тест для прохождения"""
    current_user = get_user_from_request(request, db)

    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    assigned = (
        db.query(models.AssignedTest)
        .filter(
            models.AssignedTest.id == test_id,
            models.AssignedTest.user_id == current_user.id,
        )
        .first()
    )

    if not assigned:
        raise HTTPException(status_code=404, detail="Test not found")

    quiz = db.query(models.Quiz).filter(models.Quiz.id == assigned.quiz_id).first()

    return {"assigned": assigned, "quiz": quiz}


@router.get("/api/bank", response_model=List[schemas.TaskBankResponse])
def get_student_bank_api(
    request: Request,
    task_number: Optional[int] = None,
    limit: int = 100,
    db: Session = Depends(database.get_db),
):
    """API: Получить банк заданий для ученика (только чтение)"""
    current_user = get_user_from_request(request, db)

    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    query = db.query(models.TaskBank)

    if task_number:
        query = query.filter(models.TaskBank.task_number == task_number)

    return (
        query.order_by(models.TaskBank.task_number, models.TaskBank.order_in_file)
        .limit(limit)
        .all()
    )


@router.get("/api/bank/task/{task_id}")
def get_student_task_api(
    task_id: int, request: Request, db: Session = Depends(database.get_db)
):
    """API: Получить задание из банка для решения"""
    current_user = get_user_from_request(request, db)

    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    task = db.query(models.TaskBank).filter(models.TaskBank.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/api/practice/start", response_model=schemas.PracticeSessionResponse)
def start_practice_api(
    request: Request,
    practice_request: schemas.PracticeStartRequest,
    db: Session = Depends(database.get_db),
):
    """API: Начать тренировку"""
    current_user = get_user_from_request(request, db)

    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    query = db.query(models.TaskBank)

    if practice_request.task_numbers:
        query = query.filter(
            models.TaskBank.task_number.in_(practice_request.task_numbers)
        )

    tasks = query.all()

    if not tasks:
        raise HTTPException(status_code=404, detail="No tasks found")

    if practice_request.count and practice_request.count < len(tasks):
        tasks = random.sample(tasks, practice_request.count)

    session = models.PracticeSession(
        user_id=current_user.id,
        title=f"Тренировка {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        total_tasks=len(tasks),
    )
    db.add(session)
    db.flush()

    for i, task in enumerate(tasks, 1):
        practice_task = models.PracticeTask(
            session_id=session.id, task_bank_id=task.id, order_number=i
        )
        db.add(practice_task)

    db.commit()
    db.refresh(session)

    return session


@router.get(
    "/api/practice/{session_id}", response_model=schemas.PracticeSessionResponse
)
def get_practice_session_api(
    session_id: int, request: Request, db: Session = Depends(database.get_db)
):
    """API: Получить сессию тренировки"""
    current_user = get_user_from_request(request, db)

    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = (
        db.query(models.PracticeSession)
        .filter(
            models.PracticeSession.id == session_id,
            models.PracticeSession.user_id == current_user.id,
        )
        .first()
    )

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@router.post("/api/practice/{session_id}/answer")
def answer_practice_task_api(
    session_id: int,
    request: Request,
    answer_request: schemas.PracticeAnswerRequest,
    db: Session = Depends(database.get_db),
):
    """API: Ответить на задание в тренировке"""
    current_user = get_user_from_request(request, db)

    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = (
        db.query(models.PracticeSession)
        .filter(
            models.PracticeSession.id == session_id,
            models.PracticeSession.user_id == current_user.id,
        )
        .first()
    )

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.completed_at:
        raise HTTPException(status_code=400, detail="Session already completed")

    practice_task = (
        db.query(models.PracticeTask)
        .filter(
            models.PracticeTask.session_id == session_id,
            models.PracticeTask.task_bank_id == answer_request.task_id,
        )
        .first()
    )

    if not practice_task:
        raise HTTPException(status_code=404, detail="Task not found in this session")

    if practice_task.answered_at:
        raise HTTPException(status_code=400, detail="Task already answered")

    task = (
        db.query(models.TaskBank)
        .filter(models.TaskBank.id == answer_request.task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    is_correct = answer_request.answer.strip() == task.correct_answer
    points_earned = task.points if is_correct else 0

    practice_task.user_answer = answer_request.answer
    practice_task.is_correct = is_correct
    practice_task.points_earned = points_earned
    practice_task.answered_at = datetime.utcnow()

    session.completed_tasks += 1
    if is_correct:
        session.correct_answers += 1

    if session.completed_tasks >= session.total_tasks:
        session.completed_at = datetime.utcnow()

    db.commit()

    return {
        "is_correct": is_correct,
        "correct_answer": task.correct_answer,
        "points_earned": points_earned,
        "total_points": task.points,
        "completed": session.completed_tasks >= session.total_tasks,
    }


@router.get(
    "/api/practice/history", response_model=List[schemas.PracticeSessionResponse]
)
def get_practice_history_api(request: Request, db: Session = Depends(database.get_db)):
    """API: Получить историю тренировок"""
    current_user = get_user_from_request(request, db)

    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sessions = (
        db.query(models.PracticeSession)
        .filter(models.PracticeSession.user_id == current_user.id)
        .order_by(models.PracticeSession.started_at.desc())
        .all()
    )

    return sessions


@router.post("/api/generate-variant")
def generate_student_variant_api(
    request: Request,
    variant_request: schemas.GenerateVariantRequest,
    db: Session = Depends(database.get_db),
):
    """API: Сгенерировать вариант для ученика"""
    current_user = get_user_from_request(request, db)

    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    all_tasks = db.query(models.TaskBank).all()

    if not all_tasks:
        raise HTTPException(status_code=404, detail="No tasks in bank")

    grouped = {}
    for task in all_tasks:
        if task.task_number not in grouped:
            grouped[task.task_number] = []
        grouped[task.task_number].append(task)

    selected = []
    for number in range(1, 28):
        if number in grouped and grouped[number]:
            selected.append(random.choice(grouped[number]))

    if variant_request.count and variant_request.count < len(selected):
        selected = random.sample(selected, variant_request.count)

    variant = models.Variant(
        title=variant_request.title
        or f"Вариант {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        description=variant_request.description or "Сгенерирован учеником",
        created_by=current_user.id,
        is_public=False,
    )
    db.add(variant)
    db.flush()

    for i, task in enumerate(selected, 1):
        variant_task = models.VariantTask(
            variant_id=variant.id, task_bank_id=task.id, order_number=i
        )
        db.add(variant_task)

    db.commit()
    db.refresh(variant)

    return variant


# ===== ДОБАВЛЕН ЭНДПОИНТ ДЛЯ УЧЕНИКОВ =====
@router.get("/api/students")
def get_students_api(request: Request, db: Session = Depends(database.get_db)):
    """API: Получить список всех учеников (для учителя)"""
    current_user = get_user_from_request(request, db)

    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can view students")

    students = db.query(models.User).filter(models.User.is_teacher == False).all()
    return students
