from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app import models, schemas, auth, database
from app.services.variant_generator import VariantGenerator

router = APIRouter(prefix="/variants", tags=["variants"])

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