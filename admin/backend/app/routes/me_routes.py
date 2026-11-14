"""Geschützte Identitäts-Endpunkte."""
from fastapi import APIRouter, Depends, Response

from ..config import settings
from ..deps import require_access
from ..rbac import Tier, permissions_for
from ..session import issue_session

router = APIRouter(prefix="/api", tags=["me"])


@router.get("/me")
def me(response: Response, user=Depends(require_access)):
    """Liefert die eigene Identität + Rechte fürs rollenabhängige Frontend.

    Setzt zugleich die nicebot-Session-Cookie — wurde die Identität über die
    SSO-Bridge (zentrale abgemiked_session) aufgelöst, laufen Folge-Requests
    danach über die schnelle Cookie-Prüfung statt erneut über die Bridge.
    """
    tier = Tier(user.get("tier"))
    response.set_cookie(
        settings.SESSION_COOKIE,
        issue_session(user.get("discord_id"), user.get("username"), tier.value),
        max_age=settings.SESSION_MAX_AGE,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return {
        "discord_id": user.get("discord_id"),
        "username": user.get("username"),
        "permissions": permissions_for(tier),
    }
