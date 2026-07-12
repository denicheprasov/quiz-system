def test_create_variant(client, teacher_headers):
    r = client.post("/variants/new", data={"title": "Var1"}, headers=teacher_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Var1"
    assert data["task_count"] == 0


def test_add_task_to_variant(client, teacher_headers, sample_variant, sample_task):
    r = client.post(
        f"/variants/{sample_variant.id}/tasks/{sample_task.id}",
        headers=teacher_headers
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Task added to variant"


def test_add_duplicate_task(client, teacher_headers, sample_variant, sample_task):
    client.post(f"/variants/{sample_variant.id}/tasks/{sample_task.id}", headers=teacher_headers)
    r = client.post(f"/variants/{sample_variant.id}/tasks/{sample_task.id}", headers=teacher_headers)
    assert r.status_code == 400
    assert "already in variant" in r.json()["detail"]


def test_list_variants(client, teacher_headers, sample_variant):
    r = client.get("/variants/", headers=teacher_headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_view_variant(client, teacher_headers, variant_with_task):
    r = client.get(f"/variants/{variant_with_task.id}", headers=teacher_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Test Variant"
    assert len(data["variant_tasks"]) == 1


def test_delete_variant(client, teacher_headers, sample_variant):
    r = client.delete(f"/variants/{sample_variant.id}", headers=teacher_headers)
    assert r.status_code == 200


def test_generate_variant(client, teacher_headers, sample_task):
    r = client.post("/variants/generate", json={
        "title": "Generated",
        "shuffle": False,
        "fill_missing": True
    }, headers=teacher_headers)
    assert r.status_code == 200


def test_student_cannot_create_variant(client, student_headers):
    r = client.post("/variants/new", data={"title": "X"}, headers=student_headers)
    assert r.status_code == 403


def test_assign_variant_to_group(client, teacher_headers, sample_variant, student_group_with_member):
    r = client.post(
        f"/variants/{sample_variant.id}/assign/{student_group_with_member.id}",
        headers=teacher_headers
    )
    assert r.status_code == 200
    assert "assigned" in r.json()["message"]
