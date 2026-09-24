def test_start_practice(client, student_headers, sample_task):
    r = client.post("/student/api/practice/start", json={
        "task_numbers": [3],
        "count": 5
    }, headers=student_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total_tasks"] <= 5
    assert len(data["tasks"]) > 0


def test_start_practice_all_numbers(client, student_headers, sample_task):
    r = client.post("/student/api/practice/start", json={
        "count": 5
    }, headers=student_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total_tasks"] <= 5


def test_start_practice_no_tasks(client, student_headers):
    r = client.post("/student/api/practice/start", json={
        "task_numbers": [99],
        "count": 5
    }, headers=student_headers)
    assert r.status_code == 404


def test_submit_answer(client, student_headers, sample_task):
    # Start practice first
    r = client.post("/student/api/practice/start", json={
        "task_numbers": [3],
        "count": 1
    }, headers=student_headers)
    assert r.status_code == 200
    session = r.json()
    task_id = session["tasks"][0]["task"]["id"]

    # Submit correct answer
    r2 = client.post(f"/student/api/practice/{session['id']}/answer", json={
        "task_id": task_id,
        "answer": "42"
    }, headers=student_headers)
    assert r2.status_code == 200
    data = r2.json()
    assert data["is_correct"] is True


def test_submit_wrong_answer(client, student_headers, sample_task):
    r = client.post("/student/api/practice/start", json={
        "task_numbers": [3],
        "count": 1
    }, headers=student_headers)
    session = r.json()
    task_id = session["tasks"][0]["task"]["id"]

    r2 = client.post(f"/student/api/practice/{session['id']}/answer", json={
        "task_id": task_id,
        "answer": "0"
    }, headers=student_headers)
    assert r2.status_code == 200
    assert r2.json()["is_correct"] is False


def _text_task(db):
    from app.models import TaskBank
    task = TaskBank(
        task_number=5,
        source_file="test_string.html",
        text="Text task",
        correct_answer="привет",
        answer_type="string",
        points=1,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_text_answer_is_not_always_correct(client, student_headers, db):
    _text_task(db)
    r = client.post("/student/api/practice/start", json={
        "task_numbers": [5], "count": 1
    }, headers=student_headers)
    session = r.json()
    task_id = session["tasks"][0]["task"]["id"]

    r2 = client.post(f"/student/api/practice/{session['id']}/answer", json={
        "task_id": task_id,
        "answer": "пока"
    }, headers=student_headers)
    assert r2.json()["is_correct"] is False


def test_text_answer_matches_case_insensitively(client, student_headers, db):
    _text_task(db)
    r = client.post("/student/api/practice/start", json={
        "task_numbers": [5], "count": 1
    }, headers=student_headers)
    session = r.json()
    task_id = session["tasks"][0]["task"]["id"]

    r2 = client.post(f"/student/api/practice/{session['id']}/answer", json={
        "task_id": task_id,
        "answer": "Привет"
    }, headers=student_headers)
    assert r2.json()["is_correct"] is True


def test_practice_history(client, student_headers, sample_task):
    r = client.get("/student/api/practice/history", headers=student_headers)
    assert r.status_code == 200
    data = r.json()
    assert "practice_sessions" in data
    assert "variants" in data


def test_unauthorized_practice(client):
    r = client.post("/student/api/practice/start", json={"count": 5})
    assert r.status_code == 401
