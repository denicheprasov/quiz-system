from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import os
from app import models, schemas, auth, database
from app.services.kpolyakov_parser import KpolyakovParser

router = APIRouter(prefix="/bank", tags=["bank"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/tasks", response_model=List[schemas.TaskBankResponse])
def get_tasks(
    skip: int = 0,
    limit: int = 9999,
    task_number: Optional[int] = None,
    source_file: Optional[str] = None,
    difficulty: Optional[str] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can view bank")

    query = db.query(models.TaskBank)

    if task_number:
        query = query.filter(models.TaskBank.task_number == task_number)
    if source_file:
        query = query.filter(models.TaskBank.source_file == source_file)
    if difficulty:
        query = query.filter(models.TaskBank.difficulty == difficulty)

    tasks = (
        query.order_by(models.TaskBank.task_number, models.TaskBank.order_in_file)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return tasks


@router.post("/import-url")
def import_from_url(
    url: str = Form(""),
    html: str = Form(""),
    task_number: int = Form(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can import tasks")

    if task_number < 1 or task_number > 27:
        raise HTTPException(status_code=400, detail="Task number must be between 1 and 27")

    parser = KpolyakovParser()
    result = parser.parse_page(url=url or None, html=html or None, task_number=task_number, db_session=db)
    return result


@router.get("/tasks/{task_id}", response_model=schemas.TaskBankResponse)
def get_task(
    task_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can view tasks")

    task = db.query(models.TaskBank).filter(models.TaskBank.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can delete tasks")

    task = db.query(models.TaskBank).filter(models.TaskBank.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    deleted_number = task.task_number
    deleted_order = task.order_in_file

    db.delete(task)
    db.commit()

    # Перенумеровываем order_in_file для оставшихся заданий того же номера
    remaining = db.query(models.TaskBank).filter(
        models.TaskBank.task_number == deleted_number,
        models.TaskBank.order_in_file > deleted_order,
    ).order_by(models.TaskBank.order_in_file).all()

    for i, t in enumerate(remaining):
        t.order_in_file = deleted_order + i

    db.commit()
    return {"message": "Task deleted successfully"}


@router.put("/tasks/{task_id}")
def update_task(
    task_id: int,
    data: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can edit tasks")

    task = db.query(models.TaskBank).filter(models.TaskBank.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if "text" in data:
        task.text = data["text"]
    if "correct_answer" in data:
        task.correct_answer = str(data["correct_answer"])
    if "image_url" in data:
        task.image_url = data["image_url"]
    if "difficulty" in data:
        task.difficulty = data["difficulty"] or None
    if "answer_count" in data:
        task.answer_count = int(data["answer_count"]) or 1

    db.commit()
    db.refresh(task)
    return task


@router.post("/tasks/batch-set-answer-count")
def batch_set_answer_count(
    task_number: int,
    answer_count: int = 2,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403)

    updated = db.query(models.TaskBank).filter(
        models.TaskBank.task_number == task_number
    ).update({"answer_count": answer_count}, synchronize_session=False)
    db.commit()
    return {"message": f"Updated {updated} tasks", "updated": updated}


@router.delete("/tasks")
def delete_all_tasks(
    task_number: Optional[int] = None,
    batch_size: Optional[int] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can delete tasks")

    query = db.query(models.TaskBank)
    if task_number:
        query = query.filter(models.TaskBank.task_number == task_number)
        label = f"№{task_number}"
    else:
        label = "всех"

    total = query.count()
    if total == 0:
        return {"message": "Нет заданий для удаления", "deleted": 0, "total": 0}

    tasks = query.order_by(models.TaskBank.id).limit(batch_size or total).all()
    deleted = 0
    for task in tasks:
        db.query(models.VariantTask).filter(models.VariantTask.task_bank_id == task.id).delete()
        db.query(models.PracticeTask).filter(models.PracticeTask.task_bank_id == task.id).delete()
        db.delete(task)
        deleted += 1
    db.commit()

    return {
        "message": f"Удалено {deleted} из {total} заданий {label}",
        "deleted": deleted,
        "total": total,
    }
