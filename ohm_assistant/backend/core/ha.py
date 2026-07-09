"""Home Assistant Supervisor API client (read-only for Ohm Assistant).

The Supervisor proxy needs no user token: ``SUPERVISOR_TOKEN`` is injected by
HA because the add-on declares ``homeassistant_api: true``.
"""
import os

import httpx

SUPERVISOR = "http://supervisor/core/api"
TIMEOUT = 10.0


def _headers() -> dict:
    return {"Authorization": f"Bearer {os.environ.get('SUPERVISOR_TOKEN', '')}"}


def has_token() -> bool:
    return bool(os.environ.get("SUPERVISOR_TOKEN"))


async def all_states() -> list[dict]:
    """Every entity state object from HA."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{SUPERVISOR}/states", headers=_headers())
    resp.raise_for_status()
    return resp.json()


async def states_by_id() -> dict[str, dict]:
    """All states keyed by entity_id, for quick lookups."""
    return {s["entity_id"]: s for s in await all_states()}


async def get_state(entity_id: str) -> dict | None:
    """A single entity state, or None if HA doesn't know it (404)."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{SUPERVISOR}/states/{entity_id}", headers=_headers())
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()
