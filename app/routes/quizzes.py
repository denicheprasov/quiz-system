from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import json
from app import models, schemas, auth, database

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


@router.post("/", response_model=schemas.QuizResponse)
def create_quiz(
    quiz: schemas.QuizCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can create quizzes")

    # Создаем тест
    db_quiz = models.Quiz(
        title=quiz.title, description=quiz.description, created_by=current_user.id
    )
    db.add(db_quiz)
    db.flush()

    # Создаем вопросы
    for q in quiz.questions:
        # Вычисляем общую сумму баллов в зависимости от типа задания
        if q.task_type == "extended":  # 26-27 задания
            # По 1 баллу за каждое правильное поле
            total_points = len(q.correct_answers)
        else:  # 1-25 задания
            # Всегда 1 балл за задание
            total_points = 1

        db_question = models.Question(
            quiz_id=db_quiz.id,
            number=q.number,
            text=q.text,
            image_url=q.image_url,
            file_url=q.file_url,
            answer_count=len(q.correct_answers),
            correct_answers=q.correct_answers,
            task_type=q.task_type,
            total_points=total_points,
        )
        db.add(db_question)

    db.commit()
    db.refresh(db_quiz)
    return db_quiz


@router.get("/", response_model=List[schemas.QuizResponse])
def get_quizzes(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    quizzes = (
        db.query(models.Quiz)
        .filter(models.Quiz.is_active == True)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return quizzes


@router.get("/my", response_model=List[schemas.QuizResponse])
def get_my_quizzes(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Получить все тесты текущего учителя"""
    if not current_user.is_teacher:
        raise HTTPException(
            status_code=403, detail="Only teachers can view their quizzes"
        )

    quizzes = (
        db.query(models.Quiz).filter(models.Quiz.created_by == current_user.id).all()
    )
    return quizzes


@router.get("/{quiz_id}", response_model=schemas.QuizResponse)
def get_quiz(
    quiz_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz


@router.delete("/{quiz_id}")
def delete_quiz(
    quiz_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Удалить тест"""
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can delete quizzes")

    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    if quiz.created_by != current_user.id:
        raise HTTPException(
            status_code=403, detail="You can only delete your own quizzes"
        )

    # Удаляем вопросы
    db.query(models.Question).filter(models.Question.quiz_id == quiz_id).delete()
    # Удаляем тест
    db.delete(quiz)
    db.commit()

    return {"message": "Quiz deleted successfully"}


@router.post("/{quiz_id}/submit")
def submit_quiz(
    quiz_id: int,
    result_data: dict,  # {"question_id": ["42", "15"]}
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Отправить ответы на тест"""
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    questions = (
        db.query(models.Question).filter(models.Question.quiz_id == quiz_id).all()
    )

    total_score = 0
    total_possible = 0
    user_answers = {}

    for q in questions:
        total_possible += q.total_points

        # Получаем ответы пользователя для этого вопроса
        user_ans = result_data.get(str(q.id), [])

        # Проверяем в зависимости от типа задания
        if q.task_type == "extended":  # 26-27: по 1 баллу за каждое поле
            score = 0
            for i, correct_ans in enumerate(q.correct_answers):
                if i < len(user_ans) and user_ans[i].strip() == correct_ans:
                    score += 1
        else:  # 1-25: 1 балл за все поля (все должны быть правильные)
            # Проверяем, что все поля заполнены и правильные
            all_correct = True
            for i, correct_ans in enumerate(q.correct_answers):
                if i >= len(user_ans) or user_ans[i].strip() != correct_ans:
                    all_correct = False
                    break
            score = 1 if all_correct else 0

        total_score += score
        user_answers[str(q.id)] = user_ans

    # Сохраняем результат
    result = models.Result(
        user_id=current_user.id,
        quiz_id=quiz_id,
        score=total_score,
        total_possible=total_possible,
        answers=json.dumps(user_answers),
    )
    db.add(result)
    db.commit()
    db.refresh(result)

    return {
        "score": total_score,
        "total_possible": total_possible,
        "percentage": (
            round((total_score / total_possible) * 100, 2) if total_possible > 0 else 0
        ),
        "result_id": result.id,
    }


@router.get("/{quiz_id}/results")
def get_quiz_results(
    quiz_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Получить результаты всех учеников по тесту"""
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can view results")

    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    if quiz.created_by != current_user.id:
        raise HTTPException(
            status_code=403, detail="You can only view results of your own quizzes"
        )

    # Получаем все результаты по этому тесту
    results = db.query(models.Result).filter(models.Result.quiz_id == quiz_id).all()

    # Для каждого результата получаем данные пользователя
    result_data = []
    for result in results:
        user = db.query(models.User).filter(models.User.id == result.user_id).first()
        result_data.append(
            {
                "id": result.id,
                "user_id": result.user_id,
                "username": user.username if user else "Unknown",
                "score": result.score,
                "total_possible": result.total_possible,
                "percentage": (
                    round((result.score / result.total_possible) * 100, 2)
                    if result.total_possible > 0
                    else 0
                ),
                "completed_at": result.completed_at,
                "answers": json.loads(result.answers) if result.answers else {},
            }
        )

    return result_data
