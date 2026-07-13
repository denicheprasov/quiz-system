from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app import models, database
import os

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "dev-secret-key-do-not-use-in-production"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_display_name(user) -> str:
    parts = [user.last_name or "", user.first_name or "", user.patronymic or ""]
    full = " ".join(p for p in parts if p)
    return full.strip() or user.username


def get_first_name(user) -> str:
    return user.first_name or user.username


def greeting(user) -> str:
    from datetime import datetime
    hour = datetime.now().hour
    name = get_first_name(user)
    if hour < 6:
        return f"Доброй ночи, {name}!"
    elif hour < 12:
        return f"Доброе утро, {name}!"
    elif hour < 17:
        return f"Добрый день, {name}!"
    else:
        return f"Добрый вечер, {name}!"


def authenticate_user(db: Session, username: str, password: str):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except:
        return None


def _get_user_from_token(token: str, db: Session):
    payload = decode_token(token)
    if payload is None:
        return None
    username: str = payload.get("sub")
    if username is None:
        return None
    return db.query(models.User).filter(models.User.username == username).first()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    request: Request = None,
    db: Session = Depends(database.get_db),
):
    token = None

    if credentials:
        token = credentials.credentials
    elif request:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user = _get_user_from_token(token, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return user


def get_user_from_request(request: Request, db: Session):
    token = request.cookies.get("access_token")
    if not token:
        return None
    return _get_user_from_token(token, db)
