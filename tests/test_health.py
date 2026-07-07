def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_info(client):
    r = client.get("/api/v1/info")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Quiz App"
    assert "version" in data
