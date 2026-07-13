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
    is_verified: Optional[bool] = None,
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
    if is_verified is not None:
        query = query.filter(models.TaskBank.is_verified == is_verified)

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

    db.delete(task)
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

    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks")
def delete_all_tasks(
    task_number: Optional[int] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can delete tasks")

    query = db.query(models.TaskBank)
    label = "всех"
    if task_number:
        query = query.filter(models.TaskBank.task_number == task_number)
        label = f"№{task_number}"

    tasks = query.all()
    count = len(tasks)
    for task in tasks:
        db.query(models.VariantTask).filter(models.VariantTask.task_bank_id == task.id).delete()
        db.query(models.PracticeTask).filter(models.PracticeTask.task_bank_id == task.id).delete()
        db.delete(task)
    db.commit()
    return {"message": f"Удалено {count} заданий {label}"}


@router.post("/tasks/{task_id}/verify")
def verify_task(
    task_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can verify tasks")

    task = db.query(models.TaskBank).filter(models.TaskBank.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.is_verified = True
    db.commit()

    return {"message": "Task verified successfully"}
