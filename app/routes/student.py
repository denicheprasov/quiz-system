from fastapi import APIRouter, Depends, HTTPException, status, Request, Body
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import random
import re
from datetime import datetime
from app import models, schemas, auth, database
from app.auth import get_user_from_request


def _normalize_numbers(val: str) -> list:
    """Извлекает все числа из строки, возвращает отсортированный список для сравнения"""
    nums = re.findall(r"-?\d+", val.replace("<br/>", " ").replace("\n", " "))
    return sorted(nums, key=lambda x: int(x))


router = APIRouter(prefix="/student", tags=["student"])


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

    # Вирианты, назначенные учителем (не сгенерированные самим учеником, ещё не пройденные)
    variant_assignments = (
        db.query(models.VariantAssignment)
        .filter(
            models.VariantAssignment.student_id == current_user.id,
            models.VariantAssignment.assigned_by != current_user.id,
            models.VariantAssignment.status == "pending",
        )
        .all()
    )

    # Уникальные правильные задания (из тренировок и вариантов)
    completed_task_ids = set()

    correct_practice = db.query(models.PracticeTask).filter(
        models.PracticeTask.is_correct == True,
        models.PracticeTask.session_id.in_(
            db.query(models.PracticeSession.id).filter(
                models.PracticeSession.user_id == current_user.id
            )
        ),
    ).all()
    for pt in correct_practice:
        completed_task_ids.add(pt.task_bank_id)

    all_variant_results = db.query(models.VariantAssignment).filter(
        models.VariantAssignment.student_id == current_user.id,
        models.VariantAssignment.results.isnot(None),
    ).all()
    for va in all_variant_results:
        if va.results:
            for r in va.results:
                if r.get("is_correct"):
                    for vt in va.variant.variant_tasks:
                        if vt.id == r.get("variant_task_id") and vt.task_bank_id:
                            completed_task_ids.add(vt.task_bank_id)

    # Все завершённые варианты с результатом 100% (только идеально решённые)
    all_completed_variants = (
        db.query(models.VariantAssignment)
        .filter(
            models.VariantAssignment.student_id == current_user.id,
            models.VariantAssignment.status == "completed",
            models.VariantAssignment.total > 0,
            models.VariantAssignment.score == models.VariantAssignment.total,
        )
        .count()
    )

    # Группы ученика
    memberships = db.query(models.GroupMember).filter(
        models.GroupMember.student_id == current_user.id
    ).all()
    student_groups = []
    for m in memberships:
        g = m.group
        if g:
            student_groups.append({
                "id": g.id,
                "name": g.name,
                "invite_code": g.invite_code,
            })

    return {
        "assigned_tests": assigned,
        "variant_assignments": [
            {
                "id": va.id,
                "variant_id": va.variant_id,
                "variant_title": va.variant.title if va.variant else "Вариант",
                "status": va.status,
                "assigned_at": va.assigned_at.isoformat() if va.assigned_at else None,
                "due_date": va.due_date.isoformat() if va.due_date else None,
            }
            for va in variant_assignments
        ],
        "practice_sessions": practice_sessions,
        "student_groups": student_groups,
        "unique_tasks_completed": len(completed_task_ids),
        "total_practice_completed": len([s for s in practice_sessions if s.completed_at]),
        "total_assigned": len(assigned) + all_completed_variants,
        "completed_assigned": len([a for a in assigned if a.status == "completed"]) + all_completed_variants,
    }


@router.get("/api/bank", response_model=List[schemas.TaskBankResponse])
def get_student_bank_api(
    request: Request,
    task_number: Optional[int] = None,
    difficulty: Optional[str] = None,
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
    if difficulty:
        query = query.filter(models.TaskBank.difficulty == difficulty)

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

    session = db.query(models.PracticeSession).options(
        joinedload(models.PracticeSession.practice_tasks)
    ).filter(models.PracticeSession.id == session.id).first()
    return session


@router.get("/api/practice/history")
def get_practice_history_api(request: Request, db: Session = Depends(database.get_db)):
    """API: Получить историю тренировок и вариантов"""
    current_user = get_user_from_request(request, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sessions = (
        db.query(models.PracticeSession)
        .filter(models.PracticeSession.user_id == current_user.id)
        .order_by(models.PracticeSession.started_at.desc())
        .all()
    )

    variant_assignments = (
        db.query(models.VariantAssignment)
        .filter(
            models.VariantAssignment.student_id == current_user.id,
            models.VariantAssignment.status == "completed",
        )
        .all()
    )

    return {
        "practice_sessions": sessions,
        "variants": [
            {
                "title": va.variant.title if va.variant else "Вариант",
                "correct_answers": va.score,
                "total_tasks": va.total,
                "completed_at": va.assigned_at.isoformat() if va.assigned_at else None,
                "type": "variant",
            }
            for va in variant_assignments
        ],
    }


@router.delete("/api/clear-history")
def clear_history_api(request: Request, db: Session = Depends(database.get_db)):
    current_user = get_user_from_request(request, db)
    if not current_user:
        raise HTTPException(status_code=401)

    session_ids = [
        s.id for s in db.query(models.PracticeSession).filter(
            models.PracticeSession.user_id == current_user.id
        ).all()
    ]

    for sid in session_ids:
        for pt in db.query(models.PracticeTask).filter(models.PracticeTask.session_id == sid).all():
            pt.user_answer = None
            pt.is_correct = None
            pt.answered_at = None

    db.query(models.VariantAssignment).filter(
        models.VariantAssignment.student_id == current_user.id
    ).update({"results": None}, synchronize_session=False)

    db.commit()
    return {"message": "History cleared"}


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

    is_correct = _normalize_numbers(answer_request.answer) == _normalize_numbers(task.correct_answer)
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


@router.post("/api/practice/{session_id}/finish")
def finish_practice_api(
    session_id: int,
    request: Request,
    db: Session = Depends(database.get_db),
):
    current_user = get_user_from_request(request, db)
    if not current_user:
        raise HTTPException(status_code=401)

    session = db.query(models.PracticeSession).filter(
        models.PracticeSession.id == session_id,
        models.PracticeSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404)

    session.completed_at = datetime.utcnow()
    db.commit()
    return {"message": "Practice completed"}


@router.get("/api/task-history")
def get_task_history_api(request: Request, db: Session = Depends(database.get_db)):
    """API: Получить историю отдельных заданий из тренировок и вариантов"""
    current_user = get_user_from_request(request, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    items = []

    # Задания из тренировок
    practice_tasks = (
        db.query(models.PracticeTask)
        .join(models.PracticeSession)
        .filter(models.PracticeSession.user_id == current_user.id)
        .order_by(models.PracticeTask.answered_at.desc())
        .all()
    )

    seen_bank_ids = set()
    for pt in practice_tasks:
        if not pt.answered_at or not pt.user_answer:
            continue
        task = db.query(models.TaskBank).filter(models.TaskBank.id == pt.task_bank_id).first()
        seen_bank_ids.add(pt.task_bank_id)
        items.append({
            "text": task.text[:100] + "..." if task and task.text else "Задание",
            "task_number": task.task_number if task else "?",
            "user_answer": pt.user_answer or "",
            "correct_answer": task.correct_answer if task else "?",
            "is_correct": pt.is_correct,
            "date": pt.answered_at.isoformat() if pt.answered_at else None,
            "source": "Тренировка",
        })

    # Задания из вариантов
    variant_assignments = (
        db.query(models.VariantAssignment)
        .filter(
            models.VariantAssignment.student_id == current_user.id,
            models.VariantAssignment.status == "completed",
            models.VariantAssignment.results.isnot(None),
        )
        .all()
    )

    for va in variant_assignments:
        if not va.results:
            continue
        for r in va.results:
            if not r.get("user_answer"):
                continue
            task_id = r.get("variant_task_id")
            if not task_id:
                continue
            vt = db.query(models.VariantTask).filter(models.VariantTask.id == task_id).first()
            if not vt:
                continue
            task = vt.task
            bank_id = vt.task_bank_id
            if bank_id in seen_bank_ids:
                continue
            seen_bank_ids.add(bank_id)
            items.append({
                "text": task.text[:100] + "..." if task and task.text else "Задание",
                "task_number": task.task_number if task else "?",
                "user_answer": r.get("user_answer", ""),
                "correct_answer": r.get("correct_answer", "?"),
                "is_correct": r.get("is_correct", False),
                "date": va.assigned_at.isoformat() if va.assigned_at else None,
                "source": "Вариант",
            })

    items.sort(key=lambda x: x["date"] or "", reverse=True)

    return items


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


@router.post("/variant/{variant_id}/submit")
def submit_variant(
    variant_id: int,
    request: Request,
    answers: dict = Body({}),
    db: Session = Depends(database.get_db),
):
    current_user = get_user_from_request(request, db)
    if not current_user:
        raise HTTPException(status_code=401)

    variant = db.query(models.Variant).filter(models.Variant.id == variant_id).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")

    assignment = db.query(models.VariantAssignment).filter(
        models.VariantAssignment.variant_id == variant_id,
        models.VariantAssignment.student_id == current_user.id,
    ).first()

    total = 0
    correct = 0
    results = []

    for vt in variant.variant_tasks:
        total += 1
        task = vt.task
        if not task:
            continue
        user_answer = answers.get(str(vt.id), "")
        is_correct = _normalize_numbers(user_answer) == _normalize_numbers(task.correct_answer)
        if is_correct:
            correct += 1
        results.append({
            "variant_task_id": vt.id,
            "order_number": vt.order_number,
            "user_answer": user_answer,
            "correct_answer": task.correct_answer,
            "is_correct": is_correct,
        })

    if assignment:
        assignment.status = "completed"
    else:
        assignment = models.VariantAssignment(
            variant_id=variant_id,
            student_id=current_user.id,
            assigned_by=current_user.id,
            status="completed",
        )
        db.add(assignment)
    assignment.score = correct
    assignment.total = total
    assignment.results = results
    db.commit()

    return {"score": correct, "total": total, "results": results}
