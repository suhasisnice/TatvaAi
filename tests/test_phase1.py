import pyotp


def test_health_and_ten_routers(client):
    assert client.get("/health").json() == {"status": "ok"}
    import importlib
    names = "auth mfa applications documents precheck verification rules risk alerts audit".split()
    assert len(names) == 10
    for n in names:
        assert importlib.import_module(f"app.api.routers.{n}").router is not None


def test_login_all_roles_and_me(client, login):
    for email, role in [("inst-a@tatva.test", "institution"), ("officer@tatva.test", "officer"),
                        ("inspector@tatva.test", "inspector")]:
        r = client.get("/api/v1/auth/me", headers=login(email))
        assert r.json()["role"] == role


def test_bad_password_and_unauthenticated(client):
    assert client.post("/api/v1/auth/login", json={"email": "officer@tatva.test", "password": "x"}).status_code == 401
    assert client.get("/api/v1/applications").status_code == 401


def test_institution_isolation_and_roles(client, login):
    a, b, off = login("inst-a@tatva.test"), login("inst-b@tatva.test"), login("officer@tatva.test")
    app_id = client.post("/api/v1/applications", json={}, headers=a).json()["id"]
    assert client.get(f"/api/v1/applications/{app_id}", headers=a).status_code == 200
    assert client.get(f"/api/v1/applications/{app_id}", headers=b).status_code == 404
    assert client.get("/api/v1/applications", headers=b).json() == []
    assert len(client.get("/api/v1/applications", headers=off).json()) == 1
    assert client.post("/api/v1/applications", json={}, headers=off).status_code == 403


def test_mfa_flow(client, login):
    h = login("officer@tatva.test")
    secret = client.post("/api/v1/mfa/setup", headers=h).json()["secret"]
    assert client.post("/api/v1/mfa/verify", json={"otp": "000000"}, headers=h).status_code == 400
    assert client.post("/api/v1/mfa/verify", json={"otp": pyotp.TOTP(secret).now()}, headers=h).status_code == 200
    body = {"email": "officer@tatva.test", "password": "Tatva@2026"}
    r = client.post("/api/v1/auth/login", json=body)
    assert r.status_code == 401 and r.json()["detail"] == "MFA_REQUIRED"
    assert client.post("/api/v1/auth/login", json={**body, "otp": pyotp.TOTP(secret).now()}).status_code == 200


def test_refresh(client):
    r = client.post("/api/v1/auth/login", json={"email": "inspector@tatva.test", "password": "Tatva@2026"}).json()
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": r["refresh_token"]}).status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": r["access_token"]}).status_code == 401
