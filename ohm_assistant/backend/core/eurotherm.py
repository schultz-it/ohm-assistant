"""Eurotherm Smart365 / SmartComfort365 climate controller over Modbus TCP.

The regulator exposes the whole plant on holding registers: a small block of
system-wide values (outdoor temperature, season, presence mode) plus one block
per zone, laid out at a fixed stride.

    zone N base = ZONE_BASE + (N - 1) * ZONE_STRIDE      # 1200, 1600, 2000, …
    base + 5 → temperature   (int16, ×0.1 °C)
    base + 6 → humidity      (uint16, %)
    base + 8 → setpoint      (int16, ×0.1 °C)
    base + 9 → mode          (enum: off / auto / manual)

Base, stride and register kinds are configurable, so a controller wired with a
different layout can still be mapped from the Setup tab without a code change.
Everything here is **read-only** — Ohm Assistant never writes a setpoint.
"""
import time

from .modbus_tcp import ModbusError, ModbusTcpClient, to_int16

ZONE_BASE = 1200
ZONE_STRIDE = 400
MAX_ZONES = 16

# Sensor-error / not-installed markers the regulator returns on unused channels.
_SENTINELS = {0x8000, 0x7FFF, 0xFFFF}
_TEMP_RANGE = (-60.0, 120.0)
_HUMIDITY_RANGE = (0.0, 100.0)

SEASON = {0: "raffrescamento", 1: "riscaldamento"}
PRESENCE = {0: "casa", 1: "spento", 2: "assente", 3: "vacanza"}
ZONE_MODE = {0: "off", 1: "auto", 2: "manuale", 3: "comfort", 4: "economy"}

# System-wide registers, read as one contiguous block per group.
SYSTEM_REGISTERS: list[dict] = [
    {"key": "external_temp", "address": 58, "kind": "temp",
     "label": "Temperatura esterna", "unit": "°C"},
    {"key": "season", "address": 101, "kind": "enum", "enum": SEASON,
     "label": "Stagione", "unit": ""},
    {"key": "presence", "address": 102, "kind": "enum", "enum": PRESENCE,
     "label": "Presenza", "unit": ""},
    {"key": "air_boost", "address": 103, "kind": "bool",
     "label": "Boost aria", "unit": ""},
]

# Per-zone registers, as offsets from the zone base address.
ZONE_REGISTERS: list[dict] = [
    {"key": "temperature", "offset": 5, "kind": "temp",
     "label": "Temperatura", "unit": "°C"},
    {"key": "humidity", "offset": 6, "kind": "percent",
     "label": "Umidità", "unit": "%"},
    {"key": "setpoint", "offset": 8, "kind": "temp",
     "label": "Setpoint", "unit": "°C"},
    {"key": "mode", "offset": 9, "kind": "enum", "enum": ZONE_MODE,
     "label": "Modo", "unit": ""},
]

DEFAULT_CONFIG: dict = {
    "enabled": False,
    "host": "",
    "port": 502,
    "unit_id": 1,
    "input_type": "holding",   # holding (FC3) | input (FC4)
    "timeout": 5.0,
    "poll_interval": 30,       # seconds; the Live tab polls faster than this
    "zone_base": ZONE_BASE,
    "zone_stride": ZONE_STRIDE,
    # [{"index": 1, "name": "Soggiorno", "enabled": True, "unit": "andrea"}]
    "zones": [],
}

# Which household unit a zone belongs to (display grouping only — Eurotherm
# readings are diagnostics and never feed the bill ripartition).
ZONE_UNITS = ("andrea", "genitori", "comune")

_cache: dict = {"key": None, "at": 0.0, "data": None}


def merged_config(stored: dict | None) -> dict:
    """Effective configuration: defaults with the stored settings applied."""
    cfg = dict(DEFAULT_CONFIG)
    if stored:
        cfg.update({k: v for k, v in stored.items() if k in DEFAULT_CONFIG})
    cfg["zones"] = [_clean_zone(z) for z in (cfg.get("zones") or [])]
    return cfg


def _clean_zone(z: dict) -> dict:
    unit = z.get("unit")
    return {
        "index": int(z.get("index", 1)),
        "name": (z.get("name") or f"Zona {z.get('index', 1)}").strip(),
        "enabled": bool(z.get("enabled", True)),
        "unit": unit if unit in ZONE_UNITS else None,
    }


def zone_base(cfg: dict, index: int) -> int:
    return int(cfg["zone_base"]) + (int(index) - 1) * int(cfg["zone_stride"])


def _decode(spec: dict, word: int) -> dict:
    """Turn a raw register word into a display-ready reading."""
    out = {"key": spec["key"], "label": spec["label"], "unit": spec["unit"],
           "raw": word, "value": None, "text": None, "available": False}
    if word in _SENTINELS:
        return out
    kind = spec["kind"]
    if kind == "temp":
        value = round(to_int16(word) * 0.1, 1)
        if not _TEMP_RANGE[0] <= value <= _TEMP_RANGE[1]:
            return out
        out["value"] = value
    elif kind == "percent":
        value = float(to_int16(word))
        if not _HUMIDITY_RANGE[0] <= value <= _HUMIDITY_RANGE[1]:
            return out
        out["value"] = value
    elif kind == "enum":
        out["value"] = word
        out["text"] = spec["enum"].get(word, f"stato {word}")
    elif kind == "bool":
        out["value"] = word
        out["text"] = "on" if word else "off"
    else:
        out["value"] = float(to_int16(word))
    out["available"] = True
    return out


def _contiguous_groups(addresses: list[int], max_gap: int = 8) -> list[tuple[int, int]]:
    """Group sorted addresses into (start, count) reads, bridging small gaps."""
    groups: list[tuple[int, int]] = []
    start = prev = addresses[0]
    for addr in addresses[1:]:
        if addr - prev > max_gap:
            groups.append((start, prev - start + 1))
            start = addr
        prev = addr
    groups.append((start, prev - start + 1))
    return groups


async def _read_block(client: ModbusTcpClient, cfg: dict,
                      specs: list[dict], addresses: list[int]) -> dict:
    """Read every address behind `specs` and decode it, in as few reads as possible."""
    words: dict[int, int] = {}
    for start, count in _contiguous_groups(sorted(set(addresses))):
        regs = await client.read(start, count, cfg["input_type"])
        words.update({start + i: w for i, w in enumerate(regs)})
    return {spec["key"]: _decode(spec, words[addr])
            for spec, addr in zip(specs, addresses)}


def _active_zones(cfg: dict) -> list[dict]:
    return [z for z in cfg["zones"] if z["enabled"]]


async def read_live(cfg: dict) -> dict:
    """Read system values and every enabled zone. Never raises: errors are data."""
    if not cfg["enabled"]:
        return {"enabled": False, "zones": [], "system": {}, "error": None}
    if not cfg["host"]:
        return {"enabled": True, "zones": [], "system": {},
                "error": "indirizzo del regolatore non configurato"}

    zones_cfg = _active_zones(cfg)
    try:
        async with ModbusTcpClient(cfg["host"], cfg["port"], cfg["unit_id"],
                                   cfg["timeout"]) as client:
            system = await _read_block(
                client, cfg, SYSTEM_REGISTERS,
                [s["address"] for s in SYSTEM_REGISTERS])
            zones = []
            for z in zones_cfg:
                base = zone_base(cfg, z["index"])
                readings = await _read_block(
                    client, cfg, ZONE_REGISTERS,
                    [base + s["offset"] for s in ZONE_REGISTERS])
                zones.append({**z, "base": base, "readings": readings})
    except ModbusError as exc:
        return {"enabled": True, "zones": [], "system": {}, "error": str(exc)}

    return {"enabled": True, "system": system, "zones": zones, "error": None,
            "read_at": time.time()}


def _cache_key(cfg: dict) -> tuple:
    return (cfg["enabled"], cfg["host"], cfg["port"], cfg["unit_id"],
            cfg["input_type"], cfg["zone_base"], cfg["zone_stride"],
            tuple((z["index"], z["name"], z["unit"]) for z in _active_zones(cfg)))


async def read_live_cached(cfg: dict) -> dict:
    """`read_live` behind a TTL so the 5 s Live polling never floods the bus."""
    key = _cache_key(cfg)
    ttl = max(5, int(cfg.get("poll_interval") or 30))
    now = time.monotonic()
    if _cache["key"] == key and _cache["data"] is not None \
            and now - _cache["at"] < ttl:
        return {**_cache["data"], "cached": True}
    data = await read_live(cfg)
    # Don't cache transient failures: a retry on the next poll is cheap.
    if data.get("error") is None:
        _cache.update(key=key, at=now, data=data)
    return {**data, "cached": False}


def invalidate_cache() -> None:
    _cache.update(key=None, at=0.0, data=None)


async def test_connection(cfg: dict) -> dict:
    """Probe the controller: reachable? which system registers answer?"""
    if not cfg["host"]:
        return {"ok": False, "error": "indirizzo del regolatore non configurato"}
    try:
        async with ModbusTcpClient(cfg["host"], cfg["port"], cfg["unit_id"],
                                   cfg["timeout"]) as client:
            system = await _read_block(
                client, cfg, SYSTEM_REGISTERS,
                [s["address"] for s in SYSTEM_REGISTERS])
    except ModbusError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "error": None, "system": system}


async def scan_zones(cfg: dict, max_zones: int = MAX_ZONES) -> dict:
    """Probe zone slots 1..max_zones and report which ones look populated.

    A zone counts as present when its temperature register decodes to a
    plausible reading — unused slots answer with a sentinel or a Modbus
    exception. The result is a *proposal*: the user names and saves the zones.
    """
    if not cfg["host"]:
        return {"ok": False, "error": "indirizzo del regolatore non configurato",
                "zones": []}
    by_index = {z["index"]: z for z in cfg["zones"]}
    found: list[dict] = []
    temp_spec = next(s for s in ZONE_REGISTERS if s["key"] == "temperature")
    try:
        async with ModbusTcpClient(cfg["host"], cfg["port"], cfg["unit_id"],
                                   cfg["timeout"]) as client:
            for index in range(1, int(max_zones) + 1):
                addr = zone_base(cfg, index) + temp_spec["offset"]
                try:
                    regs = await client.read(addr, 1, cfg["input_type"])
                except ModbusError:
                    continue  # unused slot: address out of range on this unit
                reading = _decode(temp_spec, regs[0])
                if not reading["available"]:
                    continue
                known = by_index.get(index)
                found.append({
                    "index": index,
                    "name": known["name"] if known else f"Zona {index}",
                    "enabled": known["enabled"] if known else True,
                    "unit": known["unit"] if known else None,
                    "base": zone_base(cfg, index),
                    "temperature": reading["value"],
                })
    except ModbusError as exc:
        return {"ok": False, "error": str(exc), "zones": found}
    return {"ok": True, "error": None, "zones": found}
