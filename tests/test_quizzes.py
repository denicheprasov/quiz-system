def test_list_active_quizzes_empty(client, teacher_headers):
    r = client.get("/quizzes/", headers=teacher_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_create_quiz(client, teacher_headers):
    r = client.post("/quizzes/", headers=teacher_headers, json={
        "title": "Test Quiz",
        "description": "A test",
        "questions": [
            {
                "number": 1,
                "text": "2+2?",
                "correct_answers": ["4"],
                "answer_count": 1,
                "task_type": "standard",
                "total_points": 1
            }
        ]
    })
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Test Quiz"
    assert len(data["questions"]) == 1


def test_student_cannot_create_quiz(client, student_headers):
    r = client.post("/quizzes/", headers=student_headers, json={
        "title": "Bad",
        "questions": []
    })
    assert r.status_code == 403


def test_get_quiz_detail(client, teacher_headers):
    create = client.post("/quizzes/", headers=teacher_headers, json={
        "title": "Detail Quiz",
        "questions": [{"number": 1, "text": "Q", "correct_answers": ["1"], "answer_count": 1}]
    })
    quiz_id = create.json()["id"]

    r = client.get(f"/quizzes/{quiz_id}", headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()["title"] == "Detail Quiz"


def test_delete_quiz(client, teacher_headers):
    create = client.post("/quizzes/", headers=teacher_headers, json={
        "title": "To Delete",
        "questions": [{"number": 1, "text": "Q", "correct_answers": ["1"], "answer_count": 1}]
    })
    quiz_id = create.json()["id"]

    r = client.delete(f"/quizzes/{quiz_id}", headers=teacher_headers)
    assert r.status_code == 200


def test_submit_quiz(client, teacher_headers, student_headers):
    create = client.post("/quizzes/", headers=teacher_headers, json={
        "title": "Submission Quiz",
        "questions": [{"number": 1, "text": "2+2?", "correct_answers": ["4"], "answer_count": 1, "total_points": 1}]
    })
    quiz_id = create.json()["id"]

    r = client.post(f"/quizzes/{quiz_id}/submit", headers=student_headers, json={
        "1": ["4"]
    })
    assert r.status_code == 200
    assert r.json()["score"] == 1
