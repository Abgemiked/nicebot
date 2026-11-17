"""Tests der Massen-Rollen-Routen: Berechtigung, CSRF, Akteur aus Session, Validierung."""
import pytest
from fastapi.testclient import TestClient

from app import deps, main
from app.config import settings
from app.rbac import Tier
from app.routes import massrole_routes as mr
from app.session import issue_session

ORIGIN = "https://abgemiked.de"
H = {"Origin": ORIGIN}


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(settings, "SESSION_SECRET", "test-secret")
    monkeypatch.setenv("PUBLIC_ORIGIN", ORIGIN)
    calls = []

    async def fake_request(method, path, body=None):
        calls.append((method, path, body))
        return 200, {"job": {"id": 1}}

    async def fake_roles():
        return [{"id": "50001", "name": "abgemiked"}]

    monkeypatch.setattr(mr, "massrole_request", fake_request)
    monkeypatch.setattr(mr, "massrole_roles", fake_roles)
    state = {"tier": "full_admin"}

    async def fake_live(discord_id):
        return Tier(state["tier"])

    monkeypatch.setattr(deps, "current_tier_live", fake_live)
    return TestClient(main.app), calls, state


def _cookies(tier="full_admin"):
    return {settings.SESSION_COOKIE: issue_session("42", "Mike", tier)}


def test_requires_login(env):
    c, calls, _ = env
    assert c.get("/api/massrole/roles").status_code == 401
    assert c.post("/api/massrole/start", json={}, headers=H).status_code == 401
    assert calls == []


def test_dc_mod_forbidden_even_with_session(env):
    c, calls, state = env
    state["tier"] = "dc_mod"
    r = c.get("/api/massrole/roles", cookies=_cookies("dc_mod"))
    assert r.status_code == 403
    assert calls == []


def test_live_check_revoked_role(env):
    c, calls, state = env
    state["tier"] = "dc_mod"  # Session sagt full_admin, live nicht mehr
    r = c.post("/api/massrole/preview", json={"role_id": "50001"}, cookies=_cookies(), headers=H)
    assert r.status_code == 403 and calls == []


def test_csrf_blocks_post_without_origin(env):
    c, calls, _ = env
    r = c.post("/api/massrole/start", json={"role_id": "50001", "confirm_count": 1}, cookies=_cookies())
    assert r.status_code == 403 and calls == []


def test_roles_ok(env):
    c, _, _ = env
    r = c.get("/api/massrole/roles", cookies=_cookies())
    assert r.status_code == 200 and r.json()["roles"][0]["name"] == "abgemiked"


def test_start_uses_session_actor_not_body(env):
    c, calls, _ = env
    r = c.post("/api/massrole/start", cookies=_cookies(), headers=H,
               json={"role_id": "50001", "confirm_count": 7, "actor_id": "666", "actor_name": "Evil"})
    assert r.status_code == 200
    _, path, body = calls[-1]
    assert path == "/internal/mass-role/start"
    assert body["actor_id"] == "42" and body["actor_name"] == "Mike" and body["confirm_count"] == 7
    assert body["include_bots"] is False


@pytest.mark.parametrize("payload", [
    {"role_id": "abc", "confirm_count": 1},
    {"role_id": "50001"},
    {"role_id": "50001", "confirm_count": "5"},
    {"role_id": "50001", "confirm_count": True},
    {"role_id": "50001", "confirm_count": -1},
    {"role_id": 50001, "confirm_count": 1},
])
def test_start_validation(env, payload):
    c, calls, _ = env
    r = c.post("/api/massrole/start", json=payload, cookies=_cookies(), headers=H)
    assert r.status_code == 400 and calls == []


def test_bot_error_passthrough_and_502(env, monkeypatch):
    c, _, _ = env

    async def blocked(method, path, body=None):
        return 409, {"code": "role_dangerous", "message": "x"}

    monkeypatch.setattr(mr, "massrole_request", blocked)
    r = c.post("/api/massrole/start", json={"role_id": "50001", "confirm_count": 1},
               cookies=_cookies(), headers=H)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "role_dangerous"

    async def boom(method, path, body=None):
        return 500, {}

    monkeypatch.setattr(mr, "massrole_request", boom)
    assert c.get("/api/massrole/jobs/current", cookies=_cookies()).status_code == 502


def test_job_endpoints_paths(env):
    c, calls, _ = env
    c.get("/api/massrole/jobs/3", cookies=_cookies())
    c.post("/api/massrole/jobs/3/cancel", cookies=_cookies(), headers=H)
    c.post("/api/massrole/jobs/3/resume", cookies=_cookies(), headers=H)
    assert [p for _, p, _ in calls] == [
        "/internal/mass-role/jobs/3", "/internal/mass-role/jobs/3/cancel",
        "/internal/mass-role/jobs/3/resume"]
    assert c.get("/api/massrole/jobs/x", cookies=_cookies()).status_code == 422
