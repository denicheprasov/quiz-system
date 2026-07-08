from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter
from app.database import engine, Base, get_db
from app.routes import auth, quizzes, bank, variants, student, groups
from app.auth import get_current_user, get_user_from_request
from app import models
from sqlalchemy.orm import Session
import os

from sqlalchemy import text

for col in ["last_name", "first_name", "patronymic"]:
    try:
        with engine.connect() as conn:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} VARCHAR(100)"))
            conn.commit()
    except Exception:
        pass

try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE task_bank ADD COLUMN file_url VARCHAR(500)"))
        conn.commit()
except Exception:
    pass

try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Failed to create tables: {e}")

app = FastAPI(title="Quiz App", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["display_name"] = lambda u: (
    " ".join(p for p in [u.last_name or "", u.first_name or "", u.patronymic or ""] if p).strip() or u.username
)

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
app.include_router(groups.router)

UPLOAD_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ===== ВЕБ-СТРАНИЦЫ =====


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(request, db)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = ""):
    return templates.TemplateResponse("login.html", {"request": request, "next": next})


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(request, db)
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})


@app.post("/profile/update")
def update_profile(
    last_name: str = Form(""),
    first_name: str = Form(""),
    patronymic: str = Form(""),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    current_user.last_name = last_name or None
    current_user.first_name = first_name or None
    current_user.patronymic = patronymic or None
    db.commit()
    return {"message": "Profile updated"}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_redirect(request: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    if user.is_teacher:
        return RedirectResponse(url="/teacher/dashboard")
    else:
        return RedirectResponse(url="/student/dashboard")


# ===== СТРАНИЦЫ ДЛЯ УЧИТЕЛЯ =====


@app.get("/teacher/dashboard", response_class=HTMLResponse)
async def teacher_dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(request, db)

    if not user or not user.is_teacher:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "teacher_dashboard.html", {"request": request, "user": user}
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(request, db)

    if not user or not user.is_teacher:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse("admin.html", {"request": request, "user": user})


@app.get("/bank", response_class=HTMLResponse)
async def bank_page(request: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(request, db)

    if not user or not user.is_teacher:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse("bank.html", {"request": request, "user": user})


@app.get("/import", response_class=HTMLResponse)
async def import_page(request: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(request, db)

    if not user or not user.is_teacher:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse("import.html", {"request": request, "user": user})


@app.get("/variant-builder", response_class=HTMLResponse)
async def variant_builder_page(request: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(request, db)

    if not user or not user.is_teacher:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "variant_builder.html", {"request": request, "user": user}
    )


@app.get("/create-quiz", response_class=HTMLResponse)
async def create_quiz_page(request: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(request, db)

    if not user or not user.is_teacher:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "create_quiz.html", {"request": request, "user": user}
    )


# ===== СТРАНИЦЫ ДЛЯ УЧЕНИКА =====


@app.get("/student/dashboard", response_class=HTMLResponse)
async def student_dashboard_page(request: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "student_dashboard.html", {"request": request, "user": user}
    )


@app.get("/student/bank", response_class=HTMLResponse)
async def student_bank_page(request: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "student_bank.html", {"request": request, "user": user}
    )


@app.get("/student/practice", response_class=HTMLResponse)
async def student_practice_page(request: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "practice.html", {"request": request, "user": user}
    )


@app.get("/student/generate", response_class=HTMLResponse)
async def student_generate_page(request: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "student_generate.html", {"request": request, "user": user}
    )


@app.get("/student/history", response_class=HTMLResponse)
async def student_history_page(request: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(request, db)

    if not user:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "student_history.html", {"request": request, "user": user}
    )


# ===== ОБЩИЕ СТРАНИЦЫ =====


@app.get("/take-quiz/{quiz_id}", response_class=HTMLResponse)
async def take_quiz_page(request: Request, quiz_id: int, db: Session = Depends(get_db)):
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


UPLOAD_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".pdf"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {ext} not allowed")

    filename = f"{os.urandom(8).hex()}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    return {"url": f"/uploads/{filename}", "filename": filename}


@app.post("/admin/promote")
def promote_to_teacher(
    username: str = Form(...),
    secret: str = Form(...),
    db: Session = Depends(get_db),
):
    if secret != "promote2024":
        raise HTTPException(status_code=403)

    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404)

    user.is_teacher = True
    db.commit()
    return {"message": f"User '{username}' is now a teacher"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/debug/uploads")
async def debug_uploads():
    import os
    files = []
    if os.path.exists(UPLOAD_DIR):
        for f in os.listdir(UPLOAD_DIR):
            fp = os.path.join(UPLOAD_DIR, f)
            files.append({"name": f, "size": os.path.getsize(fp), "url": f"/uploads/{f}"})
    return {"dir": UPLOAD_DIR, "exists": os.path.exists(UPLOAD_DIR), "files": files[:20]}


@app.get("/debug/db")
async def debug_db():
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(engine)
    tables = insp.get_table_names()
    columns = {}
    for t in tables:
        cols = [c["name"] for c in insp.get_columns(t)]
        columns[t] = cols
    return {"tables": tables, "columns": columns}


@app.get("/api/v1/info")
async def info():
    return {
        "name": "Quiz App",
        "version": "1.0.0",
        "description": "Система тестирования для подготовки к ЕГЭ по информатике",
    }
