"""Massen-Rollenvergabe (NiceBot-Verwaltung).

Vergibt EINE Rolle an alle Mitglieder der Guild — als Hintergrund-Job, der das
Gateway nie blockiert (nur asyncio.sleep), Discord-Rate-Limits beachtet,
idempotent ist (Mitglieder mit Rolle werden übersprungen) und seinen Fortschritt
in SQLite hält (Resume nach Bot-Neustart, KEIN Auto-Resume).

Die HTTP-Endpoints (aiohttp) werden über register_routes() an die interne
Service-API gehängt (X-Service-Token). Aufruf kommt ausschließlich vom
nicebot-admin-Backend, das die Voll-Admin-Berechtigung live prüft.

Endpoints:
    GET  /internal/roles/detail
    POST /internal/mass-role/preview      {role_id, include_bots}
    POST /internal/mass-role/start        {role_id, include_bots, confirm_count,
                                           actor_id, actor_name}
    GET  /internal/mass-role/jobs/current
    GET  /internal/mass-role/jobs/{id}
    POST /internal/mass-role/jobs/{id}/cancel
    POST /internal/mass-role/jobs/{id}/resume
"""
import asyncio
import json
import os
import sqlite3
from datetime import datetime, timezone

import discord
from aiohttp import web

import audit_log

# Rechte, die eine Rolle für die Massenvergabe ausschließen (kein Override).
DANGEROUS_PERMS = {
    "administrator": "Administrator",
    "manage_roles": "Rollen verwalten",
    "manage_channels": "Kanäle verwalten",
    "manage_guild": "Server verwalten",
    "ban_members": "Mitglieder bannen",
    "kick_members": "Mitglieder kicken",
    "manage_webhooks": "Webhooks verwalten",
    "manage_messages": "Nachrichten verwalten",
    "mention_everyone": "@everyone erwähnen",
    "moderate_members": "Mitglieder timeouten",
    "manage_nicknames": "Nicknames verwalten",
    "manage_expressions": "Emojis/Sticker verwalten",
}

# Rollen, die Zugriff auf die Verwaltung geben (Default = RBAC der Verwaltung);
# per ENV überschreibbar. Zusätzlich ALLOWED_ROLE_IDS/DC_MOD_ROLE_IDS aus config.
DEFAULT_PRIVILEGED_ROLE_IDS = {
    669879940296081420, 1130018862990098463, 1078399961496039515,
}

PAUSE_PER_CALL = 0.6        # Sekunden zwischen zwei Rollenänderungen
PAUSE_PER_BATCH = 5.0       # zusätzliche Pause alle BATCH_SIZE Mitglieder
BATCH_SIZE = 50
RETRIES = 3
BACKOFF_BASE = 2.0
MAX_CONSECUTIVE_FORBIDDEN = 5
MAX_FAILURES = 25
MAX_ERROR_SAMPLE = 20

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mass_role_jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    mode         TEXT NOT NULL DEFAULT 'add',
    role_id      TEXT NOT NULL,
    role_name    TEXT,
    include_bots INTEGER NOT NULL DEFAULT 0,
    actor_id     TEXT,
    actor_name   TEXT,
    status       TEXT NOT NULL,
    total        INTEGER NOT NULL DEFAULT 0,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    note         TEXT
);
CREATE TABLE IF NOT EXISTS mass_role_job_items (
    job_id    INTEGER NOT NULL,
    member_id TEXT NOT NULL,
    name      TEXT,
    status    TEXT NOT NULL,
    error     TEXT,
    PRIMARY KEY (job_id, member_id)
);
CREATE INDEX IF NOT EXISTS idx_mrji_status ON mass_role_job_items(job_id, status);
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _privileged_ids(cfg_json):
    ids = set(DEFAULT_PRIVILEGED_ROLE_IDS)
    for key in ("ALLOWED_ROLE_IDS", "DC_MOD_ROLE_IDS"):
        val = cfg_json.get(key) or []
        if isinstance(val, (int, str)):
            val = [val]
        for v in val:
            if str(v).isdigit():
                ids.add(int(v))
    for env in ("FULL_ADMIN_ROLE_IDS", "MOD_ROLE_IDS"):
        for part in os.environ.get(env, "").replace(";", ",").split(","):
            if part.strip().isdigit():
                ids.add(int(part.strip()))
    return ids


def _block(code, message, **extra):
    d = {"code": code, "message": message}
    d.update(extra)
    return d


def role_block(guild, role, privileged_ids):
    """Liefert None (Rolle vergebbar) oder ein Blockade-dict {code, message}."""
    if role is None or role == guild.default_role or getattr(role, "managed", False):
        return _block("role_invalid", "Rolle nicht gefunden oder von einer Integration verwaltet.")
    me = guild.me
    if not me.guild_permissions.manage_roles:
        return _block("bot_no_manage_roles", "Der Bot hat das Recht „Rollen verwalten“ nicht.")
    if role >= me.top_role:
        return _block(
            "role_above_bot",
            f"Diese Rolle steht über der Bot-Rolle. Die Bot-Rolle muss in den "
            f"Server-Einstellungen über „{role.name}“ stehen.",
        )
    if role.id in privileged_ids:
        return _block(
            "role_privileged",
            "Diese Rolle gibt Zugriff auf die Verwaltung und kann nicht massenhaft vergeben werden.",
        )
    perms = role.permissions
    found = [label for attr, label in DANGEROUS_PERMS.items() if getattr(perms, attr, False)]
    if found:
        return _block(
            "role_dangerous",
            f"Diese Rolle enthält gefährliche Rechte ({', '.join(found)}). "
            f"Zur Sicherheit wird sie nicht an alle vergeben.",
            permissions=found,
        )
    return None


def compute_targets(guild, role, include_bots):
    """→ (targets: Mitglieder, die die Rolle noch NICHT haben, already_have:int, total:int)."""
    members = [m for m in guild.members if include_bots or not m.bot]
    have = [m for m in members if role in m.roles]
    have_ids = {m.id for m in have}
    targets = [m for m in members if m.id not in have_ids]
    return targets, len(have), len(members)


def _valid_snowflake(value):
    return isinstance(value, str) and value.isdigit() and 5 <= len(value) <= 25


class MassRoleError(Exception):
    def __init__(self, status, payload):
        super().__init__(payload.get("message", ""))
        self.status = status
        self.payload = payload


class MassRoleManager:
    def __init__(self, cfg_json, bot, db_path=None, sleep=asyncio.sleep):
        self.cfg = cfg_json
        self.bot = bot
        self.db_path = db_path or audit_log.AUDIT_DB_PATH
        self._sleep = sleep
        self._task = None
        self._running_id = None
        self._cancel = False
        self._recovered = False
        self._errors = []  # Fehlerauszug des laufenden/letzten Jobs

    # ---- DB ----
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.executescript(_SCHEMA)
        return conn

    def _exec(self, sql, params=(), fetch=None):
        conn = self._conn()
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            if fetch == "one":
                return cur.fetchone()
            if fetch == "all":
                return cur.fetchall()
            return cur.lastrowid
        finally:
            conn.close()

    def _recover(self):
        """Beim ersten Zugriff: 'running'-Jobs ohne laufenden Task → 'interrupted'."""
        if self._recovered:
            return
        self._recovered = True
        self._exec("UPDATE mass_role_jobs SET status='interrupted' WHERE status='running'")

    # ---- Hilfen ----
    def _guild(self):
        guild = self.bot.get_guild(self.cfg.get("GUILD_ID"))
        if guild is None:
            raise MassRoleError(503, _block("guild_unavailable", "Guild nicht verfügbar"))
        return guild

    def _role_and_check(self, guild, role_id):
        if not _valid_snowflake(role_id):
            raise MassRoleError(400, _block("role_invalid", "Ungültige Rollen-ID"))
        role = guild.get_role(int(role_id))
        blk = role_block(guild, role, _privileged_ids(self.cfg))
        if blk:
            raise MassRoleError(409, blk)
        return role

    def roles_detail(self):
        guild = self._guild()
        priv = _privileged_ids(self.cfg)
        out = []
        for r in guild.roles:
            if r == guild.default_role or getattr(r, "managed", False):
                continue
            blk = role_block(guild, r, priv)
            out.append({
                "id": str(r.id), "name": r.name,
                "color": "#%06x" % r.color.value if getattr(r, "color", None) else "#000000",
                "position": r.position,
                "member_count": len(r.members),
                "blocked": blk,
            })
        out.sort(key=lambda x: -x["position"])
        return out

    def preview(self, role_id, include_bots):
        guild = self._guild()
        if not _valid_snowflake(role_id):
            raise MassRoleError(400, _block("role_invalid", "Ungültige Rollen-ID"))
        role = guild.get_role(int(role_id))
        blk = role_block(guild, role, _privileged_ids(self.cfg))
        if blk:
            return {"blocked": blk, "total_targets": 0, "already_have": 0, "will_receive": 0}
        targets, have, total = compute_targets(guild, role, include_bots)
        return {"blocked": None, "role_name": role.name, "total_targets": total,
                "already_have": have, "will_receive": len(targets)}

    # ---- Job-Status ----
    def _job_dict(self, row):
        counts = {r["status"]: r["c"] for r in self._exec(
            "SELECT status, COUNT(*) c FROM mass_role_job_items WHERE job_id=? GROUP BY status",
            (row["id"],), "all")}
        failed_rows = self._exec(
            "SELECT member_id, name, error FROM mass_role_job_items "
            "WHERE job_id=? AND status='failed' LIMIT ?",
            (row["id"], MAX_ERROR_SAMPLE), "all")
        return {
            "id": row["id"], "mode": row["mode"], "role_id": row["role_id"],
            "role_name": row["role_name"], "include_bots": bool(row["include_bots"]),
            "actor_name": row["actor_name"], "status": row["status"], "total": row["total"],
            "ok": counts.get("ok", 0), "skipped": counts.get("skipped", 0),
            "failed": counts.get("failed", 0), "pending": counts.get("pending", 0),
            "started_at": row["started_at"], "finished_at": row["finished_at"],
            "note": row["note"],
            "errors": [{"id": r["member_id"], "name": r["name"], "error": r["error"]}
                       for r in failed_rows],
        }

    def get_job(self, job_id):
        self._recover()
        row = self._exec("SELECT * FROM mass_role_jobs WHERE id=?", (job_id,), "one")
        return self._job_dict(row) if row else None

    def current_job(self):
        """Laufender Job, sonst der zuletzt gestartete (None wenn es nie einen gab)."""
        self._recover()
        row = self._exec("SELECT * FROM mass_role_jobs ORDER BY id DESC LIMIT 1", (), "one")
        return self._job_dict(row) if row else None

    def _is_running(self):
        return self._task is not None and not self._task.done()

    # ---- Start / Cancel / Resume ----
    def start(self, role_id, include_bots, confirm_count, actor_id, actor_name):
        self._recover()
        if self._is_running():
            raise MassRoleError(409, _block("job_running", "Es läuft bereits eine Massen-Vergabe."))
        guild = self._guild()
        role = self._role_and_check(guild, role_id)
        targets, have, total = compute_targets(guild, role, include_bots)
        if confirm_count != len(targets):
            raise MassRoleError(409, _block(
                "stale", "Die Zahlen haben sich geändert — bitte Vorschau neu laden.",
                will_receive=len(targets)))
        if not targets:
            raise MassRoleError(409, _block("nothing_to_do", "Alle Mitglieder haben die Rolle bereits."))
        job_id = self._exec(
            "INSERT INTO mass_role_jobs (mode, role_id, role_name, include_bots, actor_id, "
            "actor_name, status, total, started_at) VALUES ('add',?,?,?,?,?,'running',?,?)",
            (str(role.id), role.name, int(bool(include_bots)),
             str(actor_id) if actor_id else None, actor_name, len(targets), _now()))
        conn = self._conn()
        try:
            conn.executemany(
                "INSERT OR IGNORE INTO mass_role_job_items (job_id, member_id, name, status) "
                "VALUES (?,?,?,'pending')",
                [(job_id, str(m.id), m.name) for m in targets])
            conn.commit()
        finally:
            conn.close()
        self._audit("start", job_id)
        self._launch(job_id)
        return self.get_job(job_id)

    def cancel(self, job_id):
        if not self._is_running() or self._running_id != job_id:
            raise MassRoleError(409, _block("not_running", "Dieser Job läuft nicht."))
        self._cancel = True
        return self.get_job(job_id)

    def resume(self, job_id):
        self._recover()
        if self._is_running():
            raise MassRoleError(409, _block("job_running", "Es läuft bereits eine Massen-Vergabe."))
        row = self._exec("SELECT * FROM mass_role_jobs WHERE id=?", (job_id,), "one")
        if not row or row["status"] != "interrupted":
            raise MassRoleError(409, _block("not_resumable", "Nur unterbrochene Jobs können fortgesetzt werden."))
        guild = self._guild()
        self._role_and_check(guild, row["role_id"])  # Guards erneut
        self._exec("UPDATE mass_role_jobs SET status='running', finished_at=NULL WHERE id=?", (job_id,))
        self._audit("resume", job_id)
        self._launch(job_id)
        return self.get_job(job_id)

    def _launch(self, job_id):
        self._cancel = False
        self._running_id = job_id
        self._errors = []
        self._task = asyncio.ensure_future(self._run(job_id))

    # ---- Engine ----
    async def _run(self, job_id):
        status, note = "done", None
        try:
            row = self._exec("SELECT * FROM mass_role_jobs WHERE id=?", (job_id,), "one")
            guild = self._guild()
            role = guild.get_role(int(row["role_id"]))
            pending = [r["member_id"] for r in self._exec(
                "SELECT member_id FROM mass_role_job_items WHERE job_id=? AND status='pending' "
                "ORDER BY rowid", (job_id,), "all")]
            reason = f"Massen-Rollenvergabe durch {row['actor_name'] or 'unbekannt'} via NiceBot-Verwaltung"
            consecutive_forbidden = 0
            failures = self._exec(
                "SELECT COUNT(*) c FROM mass_role_job_items WHERE job_id=? AND status='failed'",
                (job_id,), "one")["c"]
            for i, mid in enumerate(pending):
                if self._cancel:
                    status = "cancelled"
                    break
                if i and i % BATCH_SIZE == 0:
                    # Guards zwischendurch erneut prüfen (Rolle/Bot-Recht kann sich ändern)
                    guild = self._guild()
                    role = guild.get_role(int(row["role_id"]))
                    blk = role_block(guild, role, _privileged_ids(self.cfg))
                    if blk:
                        status, note = "failed", blk["message"]
                        break
                    await self._sleep(PAUSE_PER_BATCH)
                result, err = await self._grant(guild, role, int(mid), reason)
                self._exec("UPDATE mass_role_job_items SET status=?, error=? WHERE job_id=? AND member_id=?",
                           (result, err, job_id, mid))
                if result == "failed":
                    failures += 1
                    consecutive_forbidden = consecutive_forbidden + 1 if err == "Forbidden" else 0
                    if consecutive_forbidden >= MAX_CONSECUTIVE_FORBIDDEN:
                        status, note = "failed", "Discord verweigert die Rollenvergabe (Rechte/Hierarchie geändert?)"
                        break
                    if failures > MAX_FAILURES:
                        status, note = "failed", f"Abbruch: mehr als {MAX_FAILURES} Fehler"
                        break
                else:
                    consecutive_forbidden = 0
                if result == "ok":
                    await self._sleep(PAUSE_PER_CALL)
        except asyncio.CancelledError:
            status, note = "interrupted", "Task beendet"
            raise
        except Exception as exc:  # noqa: BLE001 — Job darf nie still hängen bleiben
            status, note = "failed", f"Interner Fehler: {exc}"
        finally:
            self._exec("UPDATE mass_role_jobs SET status=?, finished_at=?, note=? WHERE id=?",
                       (status, _now(), note, job_id))
            self._running_id = None
            self._audit("end", job_id)
            await self._log_channel(job_id)

    async def _grant(self, guild, role, member_id, reason):
        """→ (ok|skipped|failed, fehlertext|None). Idempotent."""
        member = guild.get_member(member_id)
        if member is None:
            return "skipped", "nicht mehr auf dem Server"
        if role in member.roles:
            return "skipped", None
        last = None
        for attempt in range(RETRIES):
            try:
                await member.add_roles(role, reason=reason)
                return "ok", None
            except discord.NotFound:
                return "skipped", "nicht mehr auf dem Server"
            except discord.Forbidden:
                return "failed", "Forbidden"
            except discord.HTTPException as exc:
                last = f"Discord-Fehler: {getattr(exc, 'status', '?')}"
                if attempt < RETRIES - 1:
                    await self._sleep(BACKOFF_BASE * (2 ** attempt))
        return "failed", last

    # ---- Audit / Log-Channel ----
    def _audit(self, phase, job_id):
        try:
            job = self.get_job(job_id)
            audit_log.log_event(
                "admin_override", actor_id=self._actor(job_id), actor_name=job["actor_name"],
                target_id=job["role_id"], target_name=job["role_name"],
                meta={"scope": "mass_role", "phase": phase, "job_id": job_id,
                      "status": job["status"], "total": job["total"], "ok": job["ok"],
                      "skipped": job["skipped"], "failed": job["failed"]})
        except Exception as exc:  # noqa: BLE001
            print(f"[mass_role] audit fehlgeschlagen: {exc}")

    def _actor(self, job_id):
        row = self._exec("SELECT actor_id FROM mass_role_jobs WHERE id=?", (job_id,), "one")
        return row["actor_id"] if row else None

    async def _log_channel(self, job_id):
        try:
            cid = self.cfg.get("LOG_CHANNEL_ID")
            channel = self.bot.get_channel(cid) if cid else None
            if channel is None:
                return
            job = self.get_job(job_id)
            embed = discord.Embed(
                title="Massen-Rollenvergabe",
                description=(f"Rolle **{job['role_name']}** durch **{job['actor_name']}**: "
                             f"Status **{job['status']}**"),
            )
            embed.add_field(name="Ergebnis",
                            value=f"{job['ok']} vergeben · {job['skipped']} übersprungen · "
                                  f"{job['failed']} Fehler (von {job['total']})")
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except Exception as exc:  # noqa: BLE001
            print(f"[mass_role] Log-Channel fehlgeschlagen: {exc}")


def register_routes(app, cfg_json, bot, token_ok, manager=None):
    """Hängt die Massen-Rollen-Endpoints an die Service-API-App."""
    mgr = manager or MassRoleManager(cfg_json, bot)

    def guarded(fn, read_body=False):
        async def handler(request):
            if not token_ok(request, cfg_json.get("TURNIER_SERVICE_TOKEN")):
                return web.json_response({"error": "Ungültiger Service-Token"}, status=401)
            body = {}
            if read_body:
                try:
                    body = await request.json()
                except Exception:
                    return web.json_response({"error": "Ungültiger JSON-Body"}, status=400)
                if not isinstance(body, dict):
                    return web.json_response({"error": "Ungültiger JSON-Body"}, status=400)
            try:
                return web.json_response(fn(request, body))
            except MassRoleError as exc:
                return web.json_response(exc.payload, status=exc.status)
        return handler

    def _job_id(request):
        raw = request.match_info.get("id", "")
        if not raw.isdigit():
            raise MassRoleError(400, _block("bad_id", "Ungültige Job-ID"))
        return int(raw)

    def roles_detail(request, body):
        return {"roles": mgr.roles_detail()}

    def preview(request, body):
        return mgr.preview(body.get("role_id"), bool(body.get("include_bots", False)))

    def start(request, body):
        cc = body.get("confirm_count")
        if not isinstance(cc, int) or isinstance(cc, bool):
            raise MassRoleError(400, _block("bad_request", "confirm_count fehlt"))
        return mgr.start(body.get("role_id"), bool(body.get("include_bots", False)), cc,
                         body.get("actor_id"), str(body.get("actor_name") or "")[:100])

    def current(request, body):
        return {"job": mgr.current_job()}

    def job(request, body):
        j = mgr.get_job(_job_id(request))
        if j is None:
            raise MassRoleError(404, _block("not_found", "Job nicht gefunden"))
        return {"job": j}

    def cancel(request, body):
        return {"job": mgr.cancel(_job_id(request))}

    def resume(request, body):
        return {"job": mgr.resume(_job_id(request))}

    app.router.add_get("/internal/roles/detail", guarded(roles_detail))
    app.router.add_post("/internal/mass-role/preview", guarded(preview, True))
    app.router.add_post("/internal/mass-role/start", guarded(start, True))
    app.router.add_get("/internal/mass-role/jobs/current", guarded(current))
    app.router.add_get("/internal/mass-role/jobs/{id}", guarded(job))
    app.router.add_post("/internal/mass-role/jobs/{id}/cancel", guarded(cancel))
    app.router.add_post("/internal/mass-role/jobs/{id}/resume", guarded(resume))
    return mgr
