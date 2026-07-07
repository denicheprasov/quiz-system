from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter
from app.database import engine, Base, get_db
from app.routes import auth, quizzes, bank, variants, student
from app.auth import get_current_user, get_user_from_request
from sqlalchemy.orm import Session
from app.models import User
import os

try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Failed to create tables: {e}")

app = FastAPI(title="Quiz App", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

templates = Jinja2Templates(directory="app/templates")

ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(quizzes.router)
app.include_router(bank.router)
app.include_router(variants.router)
app.include_router(student.router)


# ===== ВЕБ-СТРАНИЦЫ =====


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    db = next(get_db())
    user = get_user_from_request(request, db)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_redirect(request: Request):
    db = next(get_db())
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    if user.is_teacher:
        return RedirectResponse(url="/teacher/dashboard")
    else:
        return RedirectResponse(url="/student/dashboard")


# ===== СТРАНИЦЫ ДЛЯ УЧИТЕЛЯ =====


@app.get("/teacher/dashboard", response_class=HTMLResponse)
async def teacher_dashboard(request: Request):
    db = next(get_db())
    user = get_user_from_request(request, db)

    if not user or not user.is_teacher:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "teacher_dashboard.html", {"request": request, "user": user}
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    db = next(get_db())
    user = get_user_from_request(request, db)

    if not user or not user.is_teacher:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse("admin.html", {"request": request, "user": user})


@app.get("/bank", response_class=HTMLResponse)
async def bank_page(request: Request):
    db = next(get_db())
    user = get_user_from_request(request, db)

    if not user or not user.is_teacher:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse("bank.html", {"request": request, "user": user})


@app.get("/import", response_class=HTMLResponse)
async def import_page(request: Request):
    db = next(get_db())
    user = get_user_from_request(request, db)

    if not user or not user.is_teacher:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse("import.html", {"request": request, "user": user})


@app.get("/variant-builder", response_class=HTMLResponse)
async def variant_builder_page(request: Request):
    db = next(get_db())
    user = get_user_from_request(request, db)

    if not user or not user.is_teacher:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "variant_builder.html", {"request": request, "user": user}
    )


@app.get("/create-quiz", response_class=HTMLResponse)
async def create_quiz_page(request: Request):
    db = next(get_db())
    user = get_user_from_request(request, db)

    if not user or not user.is_teacher:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "create_quiz.html", {"request": request, "user": user}
    )


# ===== СТРАНИЦЫ ДЛЯ УЧЕНИКА =====


@app.get("/student/dashboard", response_class=HTMLResponse)
async def student_dashboard_page(request: Request):
    db = next(get_db())
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "student_dashboard.html", {"request": request, "user": user}
    )


@app.get("/student/bank", response_class=HTMLResponse)
async def student_bank_page(request: Request):
    db = next(get_db())
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "student_bank.html", {"request": request, "user": user}
    )


@app.get("/student/practice", response_class=HTMLResponse)
async def student_practice_page(request: Request):
    db = next(get_db())
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "practice.html", {"request": request, "user": user}
    )


@app.get("/student/generate", response_class=HTMLResponse)
async def student_generate_page(request: Request):
    db = next(get_db())
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "student_generate.html", {"request": request, "user": user}
    )


@app.get("/student/history", response_class=HTMLResponse)
async def student_history_page(request: Request):
    db = next(get_db())
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "student_history.html", {"request": request, "user": user}
    )


# ===== ОБЩИЕ СТРАНИЦЫ =====


@app.get("/take-quiz/{quiz_id}", response_class=HTMLResponse)
async def take_quiz_page(request: Request, quiz_id: int):
    db = next(get_db())
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "take_quiz.html", {"request": request, "user": user, "quiz_id": quiz_id}
    )


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("access_token", path="/")
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/v1/info")
async def info():
    return {
        "name": "Quiz App",
        "version": "1.0.0",
        "description": "Система тестирования для подготовки к ЕГЭ по информатике",
    }
