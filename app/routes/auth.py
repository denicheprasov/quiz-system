from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from app import models, schemas, auth, database
from datetime import timedelta

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=schemas.UserResponse)
def register(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(
        (models.User.username == user.username) | (models.User.email == user.email)
    ).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")

    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        is_teacher=user.is_teacher
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    access_token = auth.create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=30)
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": db_user
    }

@router.post("/login", response_model=schemas.Token)
def login(
    user_data: dict,
    response: Response,
    db: Session = Depends(database.get_db)
):
    user = auth.authenticate_user(db, user_data.get("username"), user_data.get("password"))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token = auth.create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=30)
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=True,
        max_age=1800,
        path="/"
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"detail": "Logged out"}
