from fastapi import APIRouter, Depends, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app import models, schemas, auth, database
from app.services.variant_generator import VariantGenerator

router = APIRouter(prefix="/variants", tags=["variants"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/create", response_class=HTMLResponse)
async def create_variant_page(request: Request, db: Session = Depends(database.get_db)):
    user = auth.get_user_from_request(request, db)
    if not user or not user.is_teacher:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("create_variant.html", {"request": request, "user": user})


@router.post("/create")
def create_variant(
    title: str = Form(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403)
    variant = models.Variant(title=title, created_by=current_user.id)
    db.add(variant)
    db.commit()
    db.refresh(variant)
    return {"id": variant.id, "title": variant.title, "task_count": 0}


@router.post("/{variant_id}/tasks/{task_id}")
def add_task_to_variant(
    variant_id: int,
    task_id: int,
    order_number: Optional[int] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403)

    variant = db.query(models.Variant).filter(models.Variant.id == variant_id).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")

    task = db.query(models.TaskBank).filter(models.TaskBank.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    existing = db.query(models.VariantTask).filter(
        models.VariantTask.variant_id == variant_id,
        models.VariantTask.task_bank_id == task_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Task already in variant")

    max_order = db.query(func.max(models.VariantTask.order_number)).filter(
        models.VariantTask.variant_id == variant_id
    ).scalar() or 0

    vt = models.VariantTask(
        variant_id=variant_id,
        task_bank_id=task_id,
        order_number=order_number or (max_order + 1),
    )
    db.add(vt)
    db.commit()
    return {"message": "Task added to variant", "variant_id": variant_id, "task_id": task_id}


@router.post("/generate", response_model=schemas.VariantResponse)
def generate_variant(
    data: schemas.GenerateVariantRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Сгенерировать новый вариант из банка заданий"""
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can generate variants")
    
    generator = VariantGenerator(db)
    result = generator.generate_variant(
        title=data.title,
        description=data.description,
        user=current_user,
        shuffle=data.shuffle,
        fill_missing=data.fill_missing
    )
    
    return result['variant']

@router.get("/", response_model=List[schemas.VariantResponse])
def get_variants(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Получить список всех вариантов"""
    variants = db.query(models.Variant).offset(skip).limit(limit).all()
    return variants

@router.get("/{variant_id}", response_model=schemas.VariantResponse)
def get_variant(
    variant_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Получить вариант по ID"""
    variant = db.query(models.Variant).filter(models.Variant.id == variant_id).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return variant

@router.delete("/{variant_id}")
def delete_variant(
    variant_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Удалить вариант"""
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can delete variants")
    
    variant = db.query(models.Variant).filter(models.Variant.id == variant_id).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    
    db.delete(variant)
    db.commit()
    return {"message": "Variant deleted successfully"}