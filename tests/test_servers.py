"""Server CRUD API 테스트."""


def test_create_server_success(client):
    """정상적인 서버 등록."""
    res = client.post(
        "/servers",
        json={
            "name": "test-server",
            "url": "http://example.com",
            "importance": "HIGH",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "test-server"
    assert data["url"] == "http://example.com"
    assert data["importance"] == "HIGH"
    assert data["is_active"] is True


def test_create_server_duplicate_name(client):
    """동일 이름 서버 중복 등록 시 409."""
    body = {"name": "dup", "url": "http://a.com"}
    client.post("/servers", json=body)
    res = client.post("/servers", json=body)
    assert res.status_code == 409


def test_create_server_invalid_url(client):
    """http/https 아닌 URL은 422."""
    res = client.post(
        "/servers",
        json={
            "name": "bad",
            "url": "ftp://example.com",
        },
    )
    assert res.status_code == 422


def test_list_servers(client):
    """서버 목록 조회."""
    client.post("/servers", json={"name": "s1", "url": "http://a.com"})
    client.post("/servers", json={"name": "s2", "url": "http://b.com"})
    res = client.get("/servers")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_get_server_not_found(client):
    """존재하지 않는 서버 조회 시 404."""
    res = client.get("/servers/999")
    assert res.status_code == 404


def test_update_server(client):
    """서버 정보 수정."""
    create = client.post("/servers", json={"name": "orig", "url": "http://a.com"})
    sid = create.json()["id"]
    res = client.put(f"/servers/{sid}", json={"name": "changed"})
    assert res.status_code == 200
    assert res.json()["name"] == "changed"


def test_delete_server(client):
    """서버 삭제 후 204 반환."""
    create = client.post("/servers", json={"name": "del", "url": "http://a.com"})
    sid = create.json()["id"]
    res = client.delete(f"/servers/{sid}")
    assert res.status_code == 204
    # 삭제 후 조회 시 404
    assert client.get(f"/servers/{sid}").status_code == 404
