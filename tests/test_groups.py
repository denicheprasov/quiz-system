def test_create_group(client, teacher_headers):
    r = client.post("/groups", data={"name": "11A"}, headers=teacher_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "11A"
    assert len(data["invite_code"]) == 8


def test_list_groups_empty(client, teacher_headers):
    r = client.get("/groups/api/list", headers=teacher_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_list_groups_with_data(client, teacher_headers):
    client.post("/groups", data={"name": "Group1"}, headers=teacher_headers)
    r = client.get("/groups/api/list", headers=teacher_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "Group1"


def test_join_group(client, student_headers, student_group):
    r = client.post(f"/groups/join/{student_group.invite_code}", headers=student_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["message"] == "Joined group"


def test_join_group_invalid_code(client, student_headers):
    r = client.post("/groups/join/INVALID", headers=student_headers)
    assert r.status_code == 404


def test_join_duplicate(client, student_headers, student_group):
    client.post(f"/groups/join/{student_group.invite_code}", headers=student_headers)
    r = client.post(f"/groups/join/{student_group.invite_code}", headers=student_headers)
    assert r.status_code == 200
    assert "Already a member" in r.json()["message"]


def test_student_cannot_create_group(client, student_headers):
    r = client.post("/groups", data={"name": "MyGroup"}, headers=student_headers)
    assert r.status_code == 403


def test_delete_group(client, teacher_headers, student_group):
    r = client.delete(f"/groups/{student_group.id}", headers=teacher_headers)
    assert r.status_code == 200
    r2 = client.get("/groups/api/list", headers=teacher_headers)
    assert r2.json() == []


def test_list_members(client, teacher_headers, student_group_with_member):
    r = client.get(f"/groups/{student_group_with_member.id}/members", headers=teacher_headers)
    assert r.status_code == 200
    members = r.json()
    assert len(members) == 1
