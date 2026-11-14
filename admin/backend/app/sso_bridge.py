"""SSO-Bridge: eine gültige zentrale abgemiked_session als nicebot-Identität übernehmen.

Für die Einbettung unter abgemiked.de/nicebot: Der Nutzer ist bereits über den
zentralen Login (Twitch ODER Discord) angemeldet und hat sein Discord-Konto
verknüpft. Wir lesen die verknüpfte discord_id aus central-auth /auth/me und
lösen die Rolle wie gewohnt live über die Bot-API auf. Kein eigener Discord-OAuth
im iframe nötig.
"""
import re

import httpx

from .bot_client import BotApiError, fetch_member_roles
from .config import settings
from .rbac import Tier, resolve_tier

_COOKIE_RE = re.compile(r"(?:^|;\s*)abgemiked_session=([^;]+)")


async def resolve_from_abgemiked(cookie_header):
    """Liefert {discord_id, username, tier} oder None.

    None = nicht zentral angemeldet, Discord nicht verknüpft, Bot-API-Problem
    oder keine berechtigte Rolle. Wirft NICHT — der Aufrufer behandelt None als
    'kein Zugriff' (401/403).
    """
    if not cookie_header:
        return None
    m = _COOKIE_RE.search(cookie_header)
    if not m:
        return None
    sso = m.group(1)

    # 1) Zentrale Identität + verknüpfte discord_id (autoritativ: central-auth).
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(
                f"{settings.CENTRAL_AUTH_URL}/auth/me",
                headers={"Cookie": f"abgemiked_session={sso}"},
            )
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    if not data.get("authenticated"):
        return None
    user = data.get("user") or {}
    discord_id = user.get("discord_id")
    if not discord_id:
        return None

    # 2) Discord-Rolle live über die Bot-API (Single Source of Truth für Freigabe).
    try:
        is_member, role_ids, bot_username = await fetch_member_roles(str(discord_id))
    except BotApiError:
        return None
    tier = resolve_tier(role_ids, settings.FULL_ADMIN_ROLE_IDS, settings.MOD_ROLE_IDS)
    if not is_member or tier == Tier.NONE:
        return None

    username = bot_username or user.get("discord_username") or "unbekannt"
    return {"discord_id": str(discord_id), "username": username, "tier": tier.value}
