def test_profile_page(client, teacher_headers):
    r = client.get("/profile", headers=teacher_headers, follow_redirects=False)
    assert r.status_code == 200


def test_profile_page_unauthorized(client):
    r = client.get("/profile", follow_redirects=False)
    assert r.status_code in (302, 307)


def test_update_profile(client, teacher_headers):
    r = client.post("/profile/update", data={
        "last_name": "Иванов",
        "first_name": "Иван",
        "patronymic": "Иванович"
    }, headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()["message"] == "Profile updated"


def test_update_partial_profile(client, teacher_headers):
    r = client.post("/profile/update", data={
        "first_name": "Пётр"
    }, headers=teacher_headers)
    assert r.status_code == 200
