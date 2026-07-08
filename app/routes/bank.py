from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import os
from datetime import datetime
from app import models, schemas, auth, database
from app.services.import_service import ImportService
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


@router.get(
    "/tasks/by-number/{task_number}", response_model=List[schemas.TaskBankResponse]
)
def get_tasks_by_number(
    task_number: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can view bank")

    tasks = (
        db.query(models.TaskBank)
        .filter(models.TaskBank.task_number == task_number)
        .order_by(models.TaskBank.order_in_file)
        .all()
    )

    return tasks


@router.get("/tasks/numbers", response_model=List[int])
def get_task_numbers(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can view bank")

    result = (
        db.query(models.TaskBank.task_number)
        .distinct()
        .order_by(models.TaskBank.task_number)
        .all()
    )

    return [r[0] for r in result]


@router.post("/import")
def import_tasks(
    file: UploadFile = File(...),
    task_number: int = Form(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Импорт заданий из TXT файла с указанием номера задания"""
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can import tasks")

    if not file.filename.endswith(".txt") and not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .txt and .zip files are supported")

    if task_number < 1 or task_number > 27:
        raise HTTPException(
            status_code=400, detail="Task number must be between 1 and 27"
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{task_number}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    try:
        # Сохраняем файл
        content = file.file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)

        # Проверяем, что файл не пустой
        if os.path.getsize(file_path) == 0:
            return {
                "total": 0,
                "imported": 0,
                "skipped": 0,
                "errors": ["Файл пустой"],
                "tasks": [],
            }

        import_service = ImportService()

        if file.filename.endswith(".zip"):
            result = import_service.import_from_zip(file_path, file.filename, task_number)
        else:
            result = import_service.import_from_txt(file_path, file.filename, task_number)

        # Удаляем временный файл
        try:
            os.remove(file_path)
        except:
            pass

        return result

    except Exception as e:
        # Удаляем временный файл в случае ошибки
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass

        return {
            "total": 0,
            "imported": 0,
            "skipped": 0,
            "errors": [str(e)],
            "tasks": [],
        }


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


@router.put("/tasks/{task_id}", response_model=schemas.TaskBankResponse)
def update_task(
    task_id: int,
    task_data: schemas.TaskBankCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can update tasks")

    task = db.query(models.TaskBank).filter(models.TaskBank.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    for key, value in task_data.dict().items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)
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

    count = query.count()
    query.delete()
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
