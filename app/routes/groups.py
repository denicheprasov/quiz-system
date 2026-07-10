import secrets
import string
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app import models, database, auth

router = APIRouter(prefix="/groups", tags=["groups"])
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["display_name"] = auth.get_display_name


def _generate_code(length=8):
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


@router.get("", response_class=HTMLResponse)
async def groups_page(request: Request, db: Session = Depends(database.get_db)):
    user = auth.get_user_from_request(request, db)
    if not user:
        return RedirectResponse(url="/login")

    if user.is_teacher:
        return templates.TemplateResponse("groups.html", {"request": request, "user": user})
    else:
        return templates.TemplateResponse("join_group.html", {"request": request, "user": user})


@router.post("")
def create_group(
    name: str = Form(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can create groups")

    code = _generate_code()
    while db.query(models.StudentGroup).filter(models.StudentGroup.invite_code == code).first():
        code = _generate_code()

    group = models.StudentGroup(name=name, invite_code=code, created_by=current_user.id)
    db.add(group)
    db.commit()
    db.refresh(group)
    return {
        "id": group.id,
        "name": group.name,
        "invite_code": group.invite_code,
        "member_count": 0,
        "created_at": group.created_at.isoformat(),
    }


@router.get("/api/list")
def list_groups(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    query = db.query(models.StudentGroup)
    if current_user.is_teacher:
        query = query.filter(models.StudentGroup.created_by == current_user.id)
    else:
        query = query.join(models.GroupMember).filter(models.GroupMember.student_id == current_user.id)

    groups = query.order_by(models.StudentGroup.created_at.desc()).all()
    return [
        {
            "id": g.id,
            "name": g.name,
            "invite_code": g.invite_code,
            "member_count": len(g.members),
            "created_at": g.created_at.isoformat(),
        }
        for g in groups
    ]


@router.delete("/{group_id}")
def delete_group(
    group_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403)

    group = db.query(models.StudentGroup).filter(
        models.StudentGroup.id == group_id,
        models.StudentGroup.created_by == current_user.id,
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    db.delete(group)
    db.commit()
    return {"message": "Group deleted"}


@router.get("/{group_id}/members")
def get_members(
    group_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    group = db.query(models.StudentGroup).filter(models.StudentGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404)

    if not current_user.is_teacher and group.created_by != current_user.id:
        raise HTTPException(status_code=403)

    return [
        {
            "id": m.student.id,
            "username": m.student.username,
            "display_name": auth.get_display_name(m.student),
            "joined_at": m.joined_at.isoformat(),
        }
        for m in group.members
    ]


@router.post("/join/{code}")
def join_group(
    code: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.is_teacher:
        raise HTTPException(status_code=400, detail="Teachers cannot join groups")

    group = db.query(models.StudentGroup).filter(models.StudentGroup.invite_code == code).first()
    if not group:
        raise HTTPException(status_code=404, detail="Invalid invite code")

    existing = db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group.id,
        models.GroupMember.student_id == current_user.id,
    ).first()
    if existing:
        return {"message": "Already a member", "group_id": group.id, "group_name": group.name}

    member = models.GroupMember(group_id=group.id, student_id=current_user.id)
    db.add(member)
    db.commit()
    return {"message": "Joined group", "group_id": group.id, "group_name": group.name}


@router.get("/join/{code}", response_class=HTMLResponse)
async def join_page(request: Request, code: str, db: Session = Depends(database.get_db)):
    group = db.query(models.StudentGroup).filter(models.StudentGroup.invite_code == code).first()
    user = auth.get_user_from_request(request, db)

    if not group:
        return templates.TemplateResponse("join_group.html", {
            "request": request, "user": user,
            "invite_code": code, "group_name": None,
        })

    if not user:
        return templates.TemplateResponse("join_group.html", {
            "request": request, "user": user,
            "invite_code": code, "group_name": group.name,
        })

    if user.is_teacher:
        return RedirectResponse(url="/groups", status_code=302)

    existing = db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group.id,
        models.GroupMember.student_id == user.id,
    ).first()

    if not existing:
        member = models.GroupMember(group_id=group.id, student_id=user.id)
        db.add(member)
        db.commit()

    return RedirectResponse(url="/student/dashboard", status_code=302)
