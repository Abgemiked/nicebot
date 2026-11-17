"""Tests für die Massen-Rollenvergabe (mass_role.py + Service-API-Endpoints).

Standalone ausführbar (python test_mass_role.py) und pytest-kompatibel.
Alles gegen Fakes + Temp-SQLite; kein Discord-Zugriff, kein echtes Sleep.
"""
import asyncio
import os
import sqlite3
import sys
import tempfile
from types import SimpleNamespace

import discord
from aiohttp.test_utils import TestClient, TestServer

import mass_role
from mass_role import MassRoleError, MassRoleManager
from service_api import create_service_app

TOKEN = "tok"
GUILD_ID = 123


def _resp(status):
    return SimpleNamespace(status=status, reason="x")


class FakePerms:
    def __init__(self, **kw):
        self.manage_roles = False
        for k in mass_role.DANGEROUS_PERMS:
            setattr(self, k, False)
        for k, v in kw.items():
            setattr(self, k, v)


class FakeRole:
    def __init__(self, rid, name, position, managed=False, perms=None):
        self.id, self.name, self.position, self.managed = rid, name, position, managed
        self.permissions = perms or FakePerms()
        self.color = SimpleNamespace(value=0xFF0000)
        self.members = []

    def __ge__(self, o):
        return self.position >= o.position

    def __lt__(self, o):
        return self.position < o.position

    def __eq__(self, o):
        return isinstance(o, FakeRole) and self.id == o.id

    def __hash__(self):
        return hash(self.id)


class FakeMember:
    def __init__(self, mid, name, bot=False, roles=None):
        self.id, self.name, self.bot = mid, name, bot
        self.roles = list(roles or [])
        self.calls = 0
        self.error = None      # Exception, die add_roles wirft
        self.fail_times = 0    # so oft HTTPException, dann Erfolg

    async def add_roles(self, role, reason=None):
        self.calls += 1
        if self.error is not None:
            raise self.error
        if self.fail_times > 0:
            self.fail_times -= 1
            raise discord.HTTPException(_resp(500), "boom")
        self.roles.append(role)
        role.members.append(self)


class FakeGuild:
    def __init__(self, roles, members, bot_perms=None, bot_top=None):
        self.default_role = FakeRole(10001, "@everyone", 0)
        self.roles = [self.default_role] + roles
        self.members = members
        self.me = SimpleNamespace(
            guild_permissions=bot_perms or FakePerms(manage_roles=True),
            top_role=bot_top or FakeRole(999, "Bot", 100),
        )
        self._m = {m.id: m for m in members}
        for m in members:
            for r in m.roles:
                r.members.append(m)

    def get_role(self, rid):
        return next((r for r in self.roles if r.id == rid), None)

    def get_member(self, mid):
        return self._m.get(mid)


class FakeBot:
    def __init__(self, guild):
        self.g = guild

    def get_guild(self, gid):
        return self.g if gid == GUILD_ID else None

    def get_channel(self, cid):
        return None


def make(members=None, perms=None, position=10, **gkw):
    target = FakeRole(50001, "abgemiked", position, perms=perms)
    members = members if members is not None else [FakeMember(100 + i, f"u{i}") for i in range(5)]
    guild = FakeGuild([target], members, **gkw)
    tmp = tempfile.mkdtemp()
    os.environ.setdefault("AUDIT_DB_PATH", os.path.join(tmp, "audit.db"))
    mass_role.audit_log.AUDIT_DB_PATH = os.path.join(tmp, "audit.db")
    mass_role.audit_log.init_db()
    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)

    mgr = MassRoleManager({"GUILD_ID": GUILD_ID}, FakeBot(guild),
                          db_path=os.path.join(tmp, "audit.db"), sleep=fake_sleep)
    return mgr, guild, target, members, sleeps


def run(coro):
    return asyncio.run(coro)


async def _start_and_wait(mgr, role, n, bots=False):
    job = mgr.start(str(role.id), bots, n, "42", "Mike")
    await mgr._task
    return mgr.get_job(job["id"])


# ---------- Guards ----------
def _blocked(mgr, role_id="50001"):
    return mgr.preview(role_id, False)["blocked"]


def test_guards():
    async def go():
        mgr, g, role, *_ = make()
        assert _blocked(mgr) is None
        assert _blocked(mgr, "999999")["code"] == "role_invalid"
        assert _blocked(mgr, "10001")["code"] == "role_invalid"          # @everyone
        role.managed = True
        assert _blocked(mgr)["code"] == "role_invalid"
        role.managed = False
        g.me.guild_permissions = FakePerms(manage_roles=False)
        assert _blocked(mgr)["code"] == "bot_no_manage_roles"
        g.me.guild_permissions = FakePerms(manage_roles=True)
        role.position = 100                                           # == Bot-Top
        assert _blocked(mgr)["code"] == "role_above_bot"
        role.position = 10
        role.permissions = FakePerms(administrator=True, kick_members=True)
        b = _blocked(mgr)
        assert b["code"] == "role_dangerous" and "Administrator" in b["message"]
        role.permissions = FakePerms()
        role.id = 669879940296081420                                  # Admin-Rolle
        assert _blocked(mgr, str(role.id))["code"] == "role_privileged"
    run(go())


def test_start_blocked_raises():
    async def go():
        mgr, g, role, *_ = make(perms=FakePerms(manage_messages=True))
        try:
            mgr.start("50001", False, 5, "1", "x")
        except MassRoleError as e:
            assert e.status == 409 and e.payload["code"] == "role_dangerous"
        else:
            raise AssertionError("kein Fehler")
    run(go())


# ---------- Preview / Idempotenz / Bots ----------
def test_preview_counts_and_bots():
    async def go():
        role_stub = None
        members = [FakeMember(100, "a"), FakeMember(101, "b"), FakeMember(102, "bot", bot=True)]
        mgr, g, role, members, _ = make(members=members)
        members[0].roles.append(role); role.members.append(members[0])
        p = mgr.preview("50001", False)
        assert (p["total_targets"], p["already_have"], p["will_receive"]) == (2, 1, 1)
        p = mgr.preview("50001", True)
        assert (p["total_targets"], p["already_have"], p["will_receive"]) == (3, 1, 2)
    run(go())


def test_run_idempotent_and_pauses():
    async def go():
        mgr, g, role, members, sleeps = make()
        j = await _start_and_wait(mgr, role, 5)
        assert (j["status"], j["ok"], j["skipped"], j["failed"], j["total"]) == ("done", 5, 0, 0, 5)
        assert all(role in m.roles for m in members)
        assert len(sleeps) == 5 and all(s == mass_role.PAUSE_PER_CALL for s in sleeps)
        # zweiter Lauf: nichts zu tun, kein add_roles mehr
        before = sum(m.calls for m in members)
        try:
            mgr.start("50001", False, 0, "42", "Mike")
        except MassRoleError as e:
            assert e.payload["code"] == "nothing_to_do"
        assert sum(m.calls for m in members) == before
    run(go())


def test_stale_confirm_count():
    async def go():
        mgr, g, role, *_ = make()
        try:
            mgr.start("50001", False, 4, "1", "x")
        except MassRoleError as e:
            assert e.payload["code"] == "stale" and e.payload["will_receive"] == 5
        else:
            raise AssertionError
    run(go())


def test_batch_pause_every_50():
    async def go():
        members = [FakeMember(1000 + i, f"u{i}") for i in range(120)]
        mgr, g, role, members, sleeps = make(members=members)
        j = await _start_and_wait(mgr, role, 120)
        assert j["ok"] == 120
        assert sleeps.count(mass_role.PAUSE_PER_BATCH) == 2   # nach 50 und 100
    run(go())


# ---------- Fehlerpfade ----------
def test_notfound_member_gone_skipped_and_http_retry():
    async def go():
        mgr, g, role, members, sleeps = make()
        members[0].error = discord.NotFound(_resp(404), "weg")
        members[1].fail_times = 2          # 2x 500, dann Erfolg
        j = await _start_and_wait(mgr, role, 5)
        assert j["skipped"] == 1 and j["ok"] == 4 and j["failed"] == 0
        assert members[1].calls == 3
        assert mass_role.BACKOFF_BASE in sleeps
    run(go())


def test_http_error_exhausted_is_failed():
    async def go():
        mgr, g, role, members, _ = make()
        members[0].fail_times = 99
        j = await _start_and_wait(mgr, role, 5)
        assert j["failed"] == 1 and j["ok"] == 4 and j["status"] == "done"
        assert members[0].calls == mass_role.RETRIES
        assert j["errors"][0]["id"] == str(members[0].id)
    run(go())


def test_consecutive_forbidden_aborts():
    async def go():
        members = [FakeMember(2000 + i, f"u{i}") for i in range(10)]
        for m in members:
            m.error = discord.Forbidden(_resp(403), "no")
        mgr, g, role, members, _ = make(members=members)
        j = await _start_and_wait(mgr, role, 10)
        assert j["status"] == "failed" and j["failed"] == mass_role.MAX_CONSECUTIVE_FORBIDDEN
        assert j["pending"] == 5
    run(go())


def test_cancel():
    async def go():
        members = [FakeMember(3000 + i, f"u{i}") for i in range(20)]
        mgr, g, role, members, _ = make(members=members)

        async def sleep_and_cancel(s):
            if mgr._running_id is not None:
                mgr._cancel = True
        mgr._sleep = sleep_and_cancel
        j = mgr.start("50001", False, 20, "1", "x")
        await mgr._task
        j = mgr.get_job(j["id"])
        assert j["status"] == "cancelled" and 0 < j["ok"] < 20 and j["pending"] > 0
    run(go())


def test_single_job_lock_and_cancel_api():
    async def go():
        mgr, g, role, members, _ = make()
        j = mgr.start("50001", False, 5, "1", "x")
        try:
            mgr.start("50001", False, 5, "1", "x")
        except MassRoleError as e:
            assert e.payload["code"] == "job_running"
        else:
            raise AssertionError
        mgr.cancel(j["id"])
        await mgr._task
        try:
            mgr.cancel(j["id"])
        except MassRoleError as e:
            assert e.payload["code"] == "not_running"
    run(go())


# ---------- Resume ----------
def test_resume_after_restart():
    async def go():
        mgr, g, role, members, sleeps = make()
        j = mgr.start("50001", False, 5, "42", "Mike")
        await mgr._task
        # Neustart simulieren: 2 Mitglieder wieder 'pending', Job 'running'
        mgr._exec("UPDATE mass_role_jobs SET status='running' WHERE id=?", (j["id"],))
        mgr._exec("UPDATE mass_role_job_items SET status='pending' WHERE job_id=? AND member_id IN (?,?)",
                  (j["id"], "100", "101"))
        for m in members[:2]:
            m.roles.remove(role)
            role.members.remove(m)
        mgr2 = MassRoleManager(mgr.cfg, mgr.bot, db_path=mgr.db_path, sleep=mgr._sleep)
        assert mgr2.get_job(j["id"])["status"] == "interrupted"     # kein Auto-Resume
        assert not mgr2._is_running()
        mgr2.resume(j["id"])
        await mgr2._task
        r = mgr2.get_job(j["id"])
        assert r["status"] == "done" and r["pending"] == 0 and r["ok"] == 5
        try:
            mgr2.resume(j["id"])
        except MassRoleError as e:
            assert e.payload["code"] == "not_resumable"
    run(go())


# ---------- Audit ----------
def test_audit_entries():
    async def go():
        mgr, g, role, *_ = make()
        await _start_and_wait(mgr, role, 5)
        conn = sqlite3.connect(mgr.db_path)
        rows = conn.execute("SELECT actor_id, actor_name, target_name, meta FROM audit_log "
                            "WHERE event_type='admin_override'").fetchall()
        conn.close()
        assert len(rows) == 2                         # start + end
        assert rows[0][0] == "42" and rows[0][1] == "Mike" and rows[0][2] == "abgemiked"
        assert '"mass_role"' in rows[1][3] and '"ok": 5' in rows[1][3]
    run(go())


# ---------- HTTP-Endpoints ----------
def test_http_endpoints():
    async def go():
        mgr, g, role, members, _ = make()
        app = create_service_app({"TURNIER_SERVICE_TOKEN": TOKEN, "GUILD_ID": GUILD_ID}, mgr.bot)
        # Manager des Apps durch Test-Manager ersetzen: Routen neu registrieren
        app2 = __import__("aiohttp").web.Application()
        mass_role.register_routes(app2, mgr.cfg | {"TURNIER_SERVICE_TOKEN": TOKEN}, mgr.bot,
                                  lambda r, e: r.headers.get("X-Service-Token") == e, manager=mgr)
        async with TestClient(TestServer(app2)) as c:
            H = {"X-Service-Token": TOKEN}
            r = await c.get("/internal/roles/detail")
            assert r.status == 401
            r = await c.post("/internal/mass-role/preview", json={"role_id": "50001"}, headers={})
            assert r.status == 401
            r = await c.get("/internal/roles/detail", headers=H)
            roles = (await r.json())["roles"]
            assert [x["name"] for x in roles] == ["abgemiked"] and roles[0]["color"] == "#ff0000"
            r = await c.post("/internal/mass-role/preview", json={"role_id": "50001"}, headers=H)
            assert (await r.json())["will_receive"] == 5
            r = await c.post("/internal/mass-role/start", json={"role_id": "50001", "confirm_count": "5"}, headers=H)
            assert r.status == 400
            r = await c.post("/internal/mass-role/start", data="kein json", headers=H)
            assert r.status == 400
            r = await c.post("/internal/mass-role/start",
                             json={"role_id": "50001", "confirm_count": 5, "actor_id": "70001", "actor_name": "M"},
                             headers=H)
            assert r.status == 200
            await mgr._task
            r = await c.get("/internal/mass-role/jobs/current", headers=H)
            j = (await r.json())["job"]
            assert j["status"] == "done" and j["ok"] == 5
            r = await c.get(f"/internal/mass-role/jobs/{j['id']}", headers=H)
            assert r.status == 200
            r = await c.get("/internal/mass-role/jobs/999", headers=H)
            assert r.status == 404
            r = await c.get("/internal/mass-role/jobs/abc", headers=H)
            assert r.status == 400
        # Echte Service-App enthält die Routen
        paths = {res.canonical for res in app.router.resources()}
        assert "/internal/mass-role/start" in paths and "/internal/roles/detail" in paths
    run(go())


def test_extra_dangerous_perms_blocked():
    async def go():
        for perm in ("manage_events", "view_audit_log", "move_members", "manage_threads"):
            mgr, g, role, *_ = make(perms=FakePerms(**{perm: True}))
            assert _blocked(mgr)["code"] == "role_dangerous", perm
    run(go())


def test_role_deleted_mid_job_aborts():
    async def go():
        members = [FakeMember(4000 + i, f"u{i}") for i in range(5)]
        for m in members:
            m.error = discord.NotFound(SimpleNamespace(status=404, reason="x"), {"code": 10011, "message": "Unknown Role"})
        mgr, g, role, members, _ = make(members=members)
        j = await _start_and_wait(mgr, role, 5)
        assert j["status"] == "failed" and "existiert nicht mehr" in j["note"]
    run(go())


def test_4xx_not_retried():
    async def go():
        mgr, g, role, members, _ = make()
        members[0].error = discord.HTTPException(_resp(400), "bad")
        j = await _start_and_wait(mgr, role, 5)
        assert members[0].calls == 1 and j["failed"] == 1
    run(go())


def test_incomplete_member_cache_blocks():
    async def go():
        mgr, g, role, *_ = make()
        g.member_count = 500       # Cache kennt nur 5
        try:
            mgr.preview("50001", False)
        except MassRoleError as e:
            assert e.status == 503 and e.payload["code"] == "members_incomplete"
        else:
            raise AssertionError
    run(go())


def test_include_bots_must_be_bool():
    async def go():
        mgr, g, role, *_ = make()
        app = __import__("aiohttp").web.Application()
        mass_role.register_routes(app, {"TURNIER_SERVICE_TOKEN": TOKEN, "GUILD_ID": GUILD_ID}, mgr.bot,
                                  lambda r, e: r.headers.get("X-Service-Token") == e, manager=mgr)
        async with TestClient(TestServer(app)) as c:
            r = await c.post("/internal/mass-role/preview", json={"role_id": "50001", "include_bots": "false"},
                             headers={"X-Service-Token": TOKEN})
            assert r.status == 400
    run(go())


def test_no_blocking_sleep():
    src = open(os.path.join(os.path.dirname(__file__) or ".", "mass_role.py"), encoding="utf-8").read()
    assert "time.sleep" not in src


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("OK  ", name)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print("FAIL", name, repr(exc))
    sys.exit(1 if failed else 0)
