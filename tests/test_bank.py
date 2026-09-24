def test_list_tasks_empty(client, teacher_headers):
    r = client.get("/bank/tasks", headers=teacher_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_student_cannot_access_bank(client, student_headers):
    r = client.get("/bank/tasks", headers=student_headers)
    assert r.status_code == 403


def test_unauthorized_cannot_access_bank(client):
    r = client.get("/bank/tasks")
    assert r.status_code == 401


def test_student_bank_hides_correct_answer(client, student_headers, sample_task):
    r = client.get("/student/api/bank?task_number=3", headers=student_headers)
    assert r.status_code == 200
    tasks = r.json()
    assert len(tasks) == 1
    assert "correct_answer" not in tasks[0]
