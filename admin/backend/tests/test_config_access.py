"""Route-Tests: Zugriffsschutz, CSRF und Audit der Konfigurations-/Secret-Verwaltung (#9)."""
import json

import pytest
from fastapi.testclient import TestClient

from app import audit_db, bot_config, env_secrets
from app.config import settings
from app.deps import current_user
from app.main import app
from app.rbac import Tier
from app.routes import config_routes, secrets_routes

ORIGIN = "https://abgemiked.de"


@pytest.fixture
def client(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"ALLGEMEIN_ID": 111}), encoding="utf-8")
    env = tmp_path / ".env"
    env.write_text("NICEBOT_TOKEN=geheim_alt\n", encoding="utf-8")
    monkeypatch.setattr(settings, "BOT_CONFIG_PATH", str(cfg), raising=False)
    monkeypatch.setattr(settings, "BOT_ENV_PATH", str(env))
    monkeypatch.setattr(settings, "PUBLIC_ORIGIN", ORIGIN, raising=False)
    monkeypatch.setattr(settings, "public_origin", lambda: ORIGIN, raising=False)
    monkeypatch.setattr(config_routes, "read_config", lambda: json.loads(cfg.read_text()))
    monkeypatch.setattr(config_routes, "write_config",
                        lambda d: cfg.write_text(json.dumps(d), encoding="utf-8"))
    events = []
    monkeypatch.setattr(config_routes, "log_admin_override", lambda **k: events.append(k))
    monkeypatch.setattr(secrets_routes, "log_admin_override", lambda **k: events.append(k))
    app.dependency_overrides[current_user] = lambda: {
        "discord_id": "1", "username": "t", "tier": Tier.FULL_ADMIN.value}
    c = TestClient(app)
    c.events, c.env = events, env
    yield c
    app.dependency_overrides.clear()


def _live(monkeypatch, tier):
    async def fake(_id):
        return tier
    monkeypatch.setattr(config_routes, "current_tier_live", fake)
    monkeypatch.setattr(secrets_routes, "current_tier_live", fake)


H = {"Origin": ORIGIN}


def test_put_config_without_origin_is_csrf_blocked(client, monkeypatch):
    _live(monkeypatch, Tier.FULL_ADMIN)
    r = client.put("/api/config", json={"updates": {"ALLGEMEIN_ID": "222222"}})
    assert r.status_code == 403
    assert client.events == []


def test_put_config_live_tier_none_forbidden(client, monkeypatch):
    # Session sagt Admin, Live-Pruefung sagt: Rolle entzogen -> 403
    _live(monkeypatch, Tier.NONE)
    r = client.put("/api/config", json={"updates": {"ALLGEMEIN_ID": "222222"}}, headers=H)
    assert r.status_code == 403


def test_put_config_writes_and_audits_keys_only(client, monkeypatch):
    _live(monkeypatch, Tier.DC_MOD)
    r = client.put("/api/config", json={"updates": {"ALLGEMEIN_ID": "222222"}}, headers=H)
    assert r.status_code == 200
    assert len(client.events) == 1
    meta = client.events[0]["meta"]
    assert meta["changed_keys"] == ["ALLGEMEIN_ID"]
    assert "222222" not in json.dumps(meta)


def test_put_config_secret_key_rejected(client, monkeypatch):
    _live(monkeypatch, Tier.FULL_ADMIN)
    r = client.put("/api/config", json={"updates": {"TOKEN": "x"}}, headers=H)
    assert r.status_code == 400
    assert client.events == []


def test_secrets_get_forbidden_for_dc_mod(client, monkeypatch):
    _live(monkeypatch, Tier.DC_MOD)
    assert client.get("/api/secrets").status_code == 403


def test_secrets_put_forbidden_for_dc_mod_and_unchanged(client, monkeypatch):
    _live(monkeypatch, Tier.DC_MOD)
    r = client.put("/api/secrets", json={"updates": {"NICEBOT_TOKEN": "neu"}}, headers=H)
    assert r.status_code == 403
    assert "geheim_alt" in client.env.read_text()
    assert client.events == []


def test_secrets_put_audits_key_names_not_values(client, monkeypatch):
    _live(monkeypatch, Tier.FULL_ADMIN)
    r = client.put("/api/secrets", json={"updates": {"NICEBOT_TOKEN": "supergeheim_neu"}}, headers=H)
    assert r.status_code == 200
    assert len(client.events) == 1
    assert client.events[0]["meta"]["changed_keys"] == ["NICEBOT_TOKEN"]
    assert "supergeheim_neu" not in json.dumps(client.events)


def test_api_responses_not_cacheable(client, monkeypatch):
    _live(monkeypatch, Tier.FULL_ADMIN)
    r = client.get("/api/secrets")
    assert r.headers.get("cache-control") == "no-store"


def test_secrets_put_without_origin_is_csrf_blocked(client, monkeypatch):
    _live(monkeypatch, Tier.FULL_ADMIN)
    r = client.put("/api/secrets", json={"updates": {"NICEBOT_TOKEN": "x"}})
    assert r.status_code == 403
    assert "geheim_alt" in client.env.read_text()
