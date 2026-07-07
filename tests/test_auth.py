def test_register(client):
    r = client.post("/auth/register", json={
        "username": "newuser",
        "email": "new@test.com",
        "password": "secret123",
        "is_teacher": False
    })
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["username"] == "newuser"
    assert data["user"]["email"] == "new@test.com"
    assert "access_token" in data
    assert "token_type" in data


def test_register_duplicate(client):
    client.post("/auth/register", json={
        "username": "dupuser",
        "email": "dup@test.com",
        "password": "secret123"
    })
    r = client.post("/auth/register", json={
        "username": "dupuser",
        "email": "dup@test.com",
        "password": "secret123"
    })
    assert r.status_code == 400
    assert "already registered" in r.json()["detail"]


def test_login(client):
    client.post("/auth/register", json={
        "username": "loginuser",
        "email": "login@test.com",
        "password": "pass123"
    })
    r = client.post("/auth/login", json={
        "username": "loginuser",
        "password": "pass123"
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "loginuser"


def test_login_wrong_password(client):
    client.post("/auth/register", json={
        "username": "wpuser",
        "email": "wp@test.com",
        "password": "correct"
    })
    r = client.post("/auth/login", json={
        "username": "wpuser",
        "password": "wrong"
    })
    assert r.status_code == 401


def test_login_nonexistent(client):
    r = client.post("/auth/login", json={
        "username": "nobody",
        "password": "pass"
    })
    assert r.status_code == 401


def test_logout(client, teacher_headers):
    r = client.post("/auth/logout", headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()["detail"] == "Logged out"


def test_protected_route_without_token(client):
    r = client.get("/bank/tasks")
    assert r.status_code == 401
