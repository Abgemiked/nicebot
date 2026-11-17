"""Massen-Rollenvergabe (nur Voll-Admin, live geprüft).

GET  /api/massrole/roles                — vergebbare Rollen (Farbe, Mitglieder, Blockade)
POST /api/massrole/preview              — {role_id, include_bots} → Zähler/Blockade
POST /api/massrole/start                — {role_id, include_bots, confirm_count}
GET  /api/massrole/jobs/current         — laufender/letzter Job
GET  /api/massrole/jobs/{id}            — Job-Status
POST /api/massrole/jobs/{id}/cancel     — Abbruch
POST /api/massrole/jobs/{id}/resume     — unterbrochenen Job fortsetzen

Die Discord-Logik (Guards, Rate-Limits, Audit) liegt im Bot (mass_role.py).
Akteur-ID/-Name kommen IMMER aus der Session, nie aus dem Request-Body.
"""
import re

from fastapi import APIRouter, Body, Depends, HTTPException

from ..bot_client import BotApiError, massrole_request, massrole_roles
from ..deps import require_full_admin_live

router = APIRouter(prefix="/api/massrole", tags=["massrole"])

_SNOWFLAKE = re.compile(r"^\d{5,25}$")


def _passthrough(status_code, data):
    """Bot-Antwort → HTTPException (Fehlerobjekt {code,message,…} bleibt erhalten)."""
    if status_code == 200:
        return data
    if status_code in (400, 404, 409, 503) and isinstance(data, dict) and data:
        raise HTTPException(status_code=status_code, detail=data)
    raise HTTPException(status_code=502, detail={"code": "bot_error",
                                                  "message": "Bot-Anfrage fehlgeschlagen"})


async def _call(method, path, body=None):
    try:
        status_code, data = await massrole_request(method, path, body)
    except BotApiError as exc:
        raise HTTPException(status_code=502, detail={"code": "bot_unreachable", "message": str(exc)})
    return _passthrough(status_code, data)


def _role_id(payload):
    rid = (payload or {}).get("role_id")
    if not isinstance(rid, str) or not _SNOWFLAKE.match(rid):
        raise HTTPException(status_code=400, detail={"code": "role_invalid", "message": "Ungültige Rollen-ID"})
    return rid


def _include_bots(payload):
    v = (payload or {}).get("include_bots", False)
    if not isinstance(v, bool):
        raise HTTPException(status_code=400, detail={"code": "bad_request", "message": "include_bots muss true/false sein"})
    return v


@router.get("/roles")
async def get_roles(user=Depends(require_full_admin_live)):
    try:
        return {"roles": await massrole_roles()}
    except BotApiError as exc:
        raise HTTPException(status_code=502, detail={"code": "bot_unreachable", "message": str(exc)})


@router.post("/preview")
async def preview(payload: dict = Body(...), user=Depends(require_full_admin_live)):
    return await _call("POST", "/internal/mass-role/preview",
                       {"role_id": _role_id(payload), "include_bots": _include_bots(payload)})


@router.post("/start")
async def start(payload: dict = Body(...), user=Depends(require_full_admin_live)):
    cc = payload.get("confirm_count")
    if not isinstance(cc, int) or isinstance(cc, bool) or cc < 0:
        raise HTTPException(status_code=400, detail={"code": "bad_request", "message": "confirm_count fehlt"})
    return await _call("POST", "/internal/mass-role/start", {
        "role_id": _role_id(payload),
        "include_bots": _include_bots(payload),
        "confirm_count": cc,
        "actor_id": user.get("discord_id"),
        "actor_name": user.get("username"),
    })


@router.get("/jobs/current")
async def current_job(user=Depends(require_full_admin_live)):
    return await _call("GET", "/internal/mass-role/jobs/current")


@router.get("/jobs/{job_id}")
async def get_job(job_id: int, user=Depends(require_full_admin_live)):
    return await _call("GET", f"/internal/mass-role/jobs/{int(job_id)}")


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: int, user=Depends(require_full_admin_live)):
    return await _call("POST", f"/internal/mass-role/jobs/{int(job_id)}/cancel", {})


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: int, user=Depends(require_full_admin_live)):
    return await _call("POST", f"/internal/mass-role/jobs/{int(job_id)}/resume", {})
