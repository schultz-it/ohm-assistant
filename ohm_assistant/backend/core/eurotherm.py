"""Eurotherm SmartComfort 365 over Modbus TCP.

Register map from the manufacturer's "SmartComfort 365 — Modbus interface for
home automation", rev. 05 (21/02/2022). One SmartControl365 answers for the
whole plant on a single TCP endpoint; the parts are told apart by address:

    SYSTEM     50…59          serial, clock, external temperature, n. of zones
    ZONE i     100 + i·130    operative mode, zone mode, air boost, module map
    MODULE b   1140 + b·3260  a Smart Base: flow setpoint/temperature, sensors
    ROOM b,r   1140 + b·3260 + 60 + r·400   temperature, humidity, dewpoint, …

"ZONE" in the protocol is a *subsystem* (up to 8), "MODULE" is a **Smart Base**
(up to 8, 8 rooms each). Temperatures are 0.1 °C with the negatives written as
65536 − value.

Everything here is **read-only**: the protocol allows writes (FC 6/16) but Ohm
Assistant only ever reads.
"""
import time

from .modbus_tcp import ModbusError, ModbusTcpClient

# ---- Address layout (rev. 05) ---------------------------------------------
SYSTEM_BASE = 50
ZONE_BASE = 100
ZONE_STRIDE = 130
MAX_SUBSYSTEMS = 8
MODULE_BASE = 1140
MODULE_STRIDE = 3260
MAX_MODULES = 8
ROOM_OFFSET = 60          # first room of a module, relative to the module block
ROOM_STRIDE = 400
ROOMS_PER_MODULE = 8

AIR_MODELS = ["", "Deuclima-VMC 500 V", "Deuclima-VMC 500 S", "SmartAir"]

# ---- Enumerations ----------------------------------------------------------
OPERATIVE_MODE = {0: "raffrescamento", 1: "riscaldamento"}
ZONE_MODE = {0: "casa", 1: "spento", 2: "assente", 3: "vacanza"}
BASE_TYPE = {0: "con controllo di miscelazione", 1: "senza miscelazione"}
SENSOR_TYPE = {1: "temperatura", 2: "temperatura e umidità"}
ROOM_MODE = {0: "off", 1: "automatico", 2: "manuale", 3: "manuale temporaneo",
             4: "party", 5: "early bird", 6: "buonanotte"}
ROOM_ERRORS = {1: "sensore scollegato", 8: "allarme condensa",
               16: "umidità alta, raffrescamento inibito",
               32: "errore misura temperatura", 64: "errore misura umidità",
               256: "umidità fuori scala", 512: "sostituire le batterie"}

_NEGATIVE_ABOVE = 60000   # per the manual: value > 60000 → value − 65536
_TEMP_RANGE = (-60.0, 200.0)


# ---- Register blocks -------------------------------------------------------
SYSTEM_REGISTERS: list[dict] = [
    {"key": "serial_high", "offset": 0, "kind": "uint", "label": "Seriale (alto)", "unit": ""},
    {"key": "serial_low", "offset": 1, "kind": "uint", "label": "Seriale (basso)", "unit": ""},
    {"key": "hour", "offset": 2, "kind": "uint", "label": "Ora", "unit": ""},
    {"key": "minute", "offset": 3, "kind": "uint", "label": "Minuti", "unit": ""},
    {"key": "day", "offset": 4, "kind": "uint", "label": "Giorno", "unit": ""},
    {"key": "month", "offset": 5, "kind": "uint", "label": "Mese", "unit": ""},
    {"key": "year", "offset": 6, "kind": "uint", "label": "Anno", "unit": ""},
    {"key": "external_temp_written", "offset": 7, "kind": "temp",
     "label": "Temperatura esterna (scritta)", "unit": "°C"},
    {"key": "external_temp", "offset": 8, "kind": "temp",
     "label": "Temperatura esterna", "unit": "°C"},
    {"key": "subsystem_count", "offset": 9, "kind": "uint",
     "label": "Numero di zone (sottosistemi)", "unit": ""},
]

ZONE_REGISTERS: list[dict] = [
    {"key": "zone_id", "offset": 0, "kind": "uint", "label": "ID zona", "unit": ""},
    {"key": "operative_mode", "offset": 1, "kind": "enum", "enum": OPERATIVE_MODE,
     "label": "Stagione", "unit": ""},
    {"key": "zone_mode", "offset": 2, "kind": "enum", "enum": ZONE_MODE,
     "label": "Modo zona", "unit": ""},
    {"key": "air_boost", "offset": 3, "kind": "bool",
     "label": "Boost rinnovo aria", "unit": ""},
    {"key": "module_count", "offset": 4, "kind": "uint",
     "label": "Smart Base nella zona", "unit": ""},
    {"key": "module_map", "offset": 5, "kind": "bitmap",
     "label": "Mappa Smart Base", "unit": ""},
]

MODULE_REGISTERS: list[dict] = [
    {"key": "base_id", "offset": 0, "kind": "uint", "label": "ID base", "unit": ""},
    {"key": "zone_id", "offset": 1, "kind": "uint", "label": "ID zona", "unit": ""},
    {"key": "sensor_count", "offset": 2, "kind": "uint",
     "label": "Sensori collegati", "unit": ""},
    {"key": "sensor_errors", "offset": 3, "kind": "sensor_mask",
     "label": "Errori di comunicazione sensori", "unit": ""},
    {"key": "base_type", "offset": 4, "kind": "enum", "enum": BASE_TYPE,
     "label": "Tipo base", "unit": ""},
    {"key": "flow_setpoint", "offset": 5, "kind": "temp",
     "label": "Setpoint di mandata", "unit": "°C"},
    {"key": "flow_temp", "offset": 6, "kind": "temp",
     "label": "Temperatura di mandata", "unit": "°C"},
]

ROOM_REGISTERS: list[dict] = [
    {"key": "room_id", "offset": 0, "kind": "uint", "label": "ID stanza", "unit": ""},
    {"key": "base_id", "offset": 1, "kind": "uint", "label": "ID base", "unit": ""},
    {"key": "zone_id", "offset": 2, "kind": "uint", "label": "ID zona", "unit": ""},
    {"key": "sensor_type", "offset": 3, "kind": "enum", "enum": SENSOR_TYPE,
     "label": "Tipo sensore", "unit": ""},
    {"key": "errors", "offset": 4, "kind": "room_errors",
     "label": "Errori sensore", "unit": ""},
    {"key": "temperature", "offset": 5, "kind": "temp",
     "label": "Temperatura", "unit": "°C"},
    {"key": "humidity", "offset": 6, "kind": "percent",
     "label": "Umidità", "unit": "%"},
    {"key": "dewpoint", "offset": 7, "kind": "temp",
     "label": "Punto di rugiada", "unit": "°C"},
    {"key": "target", "offset": 8, "kind": "temp",
     "label": "Temperatura obiettivo", "unit": "°C"},
    {"key": "mode", "offset": 9, "kind": "enum", "enum": ROOM_MODE,
     "label": "Modo", "unit": ""},
    {"key": "manual_temp", "offset": 10, "kind": "temp",
     "label": "Temperatura manuale", "unit": "°C"},
]

# Which household unit something belongs to (display grouping only — Eurotherm
# readings are diagnostics and never feed the bill ripartition).
UNITS = ("andrea", "genitori", "comune")

# This house: three Smart Base, each with its own air machine. Editable.
DEFAULT_BASES: list[dict] = [
    {"id": 0, "name": "Genitori", "unit": "genitori", "enabled": True,
     "air_model": "Deuclima-VMC 500 V"},
    {"id": 1, "name": "Andrea piano 1", "unit": "andrea", "enabled": True,
     "air_model": "Deuclima-VMC 500 S"},
    {"id": 2, "name": "Andrea piano 2", "unit": "andrea", "enabled": True,
     "air_model": "Deuclima-VMC 500 S"},
]

DEFAULT_CONFIG: dict = {
    "enabled": False,
    "host": "",
    "port": 502,
    "unit_id": 1,           # "MODBUS transaction identifier is ID = 1 by default"
    "input_type": "holding",
    "timeout": 5.0,
    "poll_interval": 30,    # the Live tab polls faster and reuses the cache
    "bases": DEFAULT_BASES,
    # Room names/units, filled by discovery: [{"base":0,"room":0,"name":…}]
    "rooms": [],
    # Registers found with the explorer and pinned to Live:
    # [{"address": 4405, "name": "…", "group": "base:1", "scale": 0.1, …}]
    "custom": [],
}

_cache: dict = {"key": None, "at": 0.0, "data": None}


# ---- Addressing ------------------------------------------------------------
def zone_addr(index: int) -> int:
    """Address of subsystem block `index` (0-based)."""
    return ZONE_BASE + int(index) * ZONE_STRIDE


def module_addr(base_id: int) -> int:
    """Address of the Smart Base block for `base_id` (0-based, as in the bus)."""
    return MODULE_BASE + int(base_id) * MODULE_STRIDE


def room_addr(base_id: int, room_id: int) -> int:
    return module_addr(base_id) + ROOM_OFFSET + int(room_id) * ROOM_STRIDE


# ---- Configuration ---------------------------------------------------------
def merged_config(stored: dict | None) -> dict:
    """Effective configuration: defaults with the stored settings applied."""
    cfg = dict(DEFAULT_CONFIG)
    if stored:
        cfg.update({k: v for k, v in stored.items() if k in DEFAULT_CONFIG})
    cfg["bases"] = [_clean_base(b) for b in (cfg.get("bases") or [])]
    cfg["rooms"] = [_clean_room(r) for r in (cfg.get("rooms") or [])]
    cfg["custom"] = [_clean_custom(c) for c in (cfg.get("custom") or [])]
    return cfg


def _clean_base(b: dict) -> dict:
    unit = b.get("unit")
    bid = int(b.get("id", 0))
    return {
        "id": bid,
        "name": (b.get("name") or f"Smart Base {bid + 1}").strip(),
        "unit": unit if unit in UNITS else None,
        "enabled": bool(b.get("enabled", True)),
        "air_model": (b.get("air_model") or "").strip(),
    }


def _clean_room(r: dict) -> dict:
    unit = r.get("unit")
    base, room = int(r.get("base", 0)), int(r.get("room", 0))
    return {
        "base": base,
        "room": room,
        "name": (r.get("name") or f"Stanza {room + 1}").strip(),
        "enabled": bool(r.get("enabled", True)),
        "unit": unit if unit in UNITS else None,
    }


def _clean_custom(c: dict) -> dict:
    """A register the user identified with the explorer and pinned to Live."""
    kind = c.get("kind")
    addr = int(c.get("address", 0))
    return {
        "address": addr,
        "name": (c.get("name") or f"Registro {addr}").strip(),
        "group": (c.get("group") or "sistema").strip(),
        "scale": float(c.get("scale") or 1.0),
        "unit": (c.get("unit") or "").strip(),
        "kind": kind if kind in ("number", "bool", "temp") else "number",
    }


def enabled_bases(cfg: dict) -> list[dict]:
    return [b for b in cfg["bases"] if b["enabled"]]


def room_meta(cfg: dict, base_id: int, room_id: int) -> dict | None:
    for r in cfg["rooms"]:
        if r["base"] == base_id and r["room"] == room_id:
            return r
    return None


# ---- Decoding --------------------------------------------------------------
def temp_value(word: int) -> float:
    """0.1 °C with the manual's negative convention (value > 60000 → −65536)."""
    signed = word - 65536 if word > _NEGATIVE_ABOVE else word
    return round(signed * 0.1, 1)


def _flags(word: int, table: dict[int, str]) -> list[str]:
    return [text for bit, text in table.items() if word & bit]


def _decode(spec: dict, word: int) -> dict:
    """Turn a raw register word into a display-ready reading."""
    out = {"key": spec["key"], "label": spec["label"], "unit": spec["unit"],
           "raw": word, "value": None, "text": None, "available": True}
    kind = spec["kind"]
    if kind == "temp":
        value = temp_value(word)
        if not _TEMP_RANGE[0] <= value <= _TEMP_RANGE[1]:
            out["available"] = False
            return out
        out["value"] = value
    elif kind == "percent":
        if word > 100:
            out["available"] = False
            return out
        out["value"] = float(word)
    elif kind == "enum":
        out["value"] = word
        out["text"] = spec["enum"].get(word, f"stato {word}")
    elif kind == "bool":
        out["value"] = word
        out["text"] = "attivo" if word else "non attivo"
    elif kind == "bitmap":
        out["value"] = word
        out["text"] = ", ".join(str(i + 1) for i in range(8) if word & (1 << i)) or "—"
    elif kind == "room_errors":
        out["value"] = word
        out["text"] = ", ".join(_flags(word, ROOM_ERRORS)) or "nessun errore"
    elif kind == "sensor_mask":
        out["value"] = word
        bad = [str(i + 1) for i in range(8) if word & (1 << i)]
        out["text"] = ("sensori in errore: " + ", ".join(bad)) if bad else "nessun errore"
    else:
        out["value"] = word
    return out


def _decode_block(specs: list[dict], start: int, words: list[int]) -> dict:
    return {s["key"]: _decode(s, words[s["offset"]]) for s in specs}


def _block_len(specs: list[dict]) -> int:
    return max(s["offset"] for s in specs) + 1


# ---- Reading ---------------------------------------------------------------
def _room_present(readings: dict) -> bool:
    """A room slot is real when its sensor answers with a plausible reading."""
    if readings["sensor_type"]["value"] not in SENSOR_TYPE:
        return False
    if readings["errors"]["raw"] & 1:      # disconnected
        return False
    return readings["temperature"]["available"]


async def _read_block(client: ModbusTcpClient, cfg: dict, specs: list[dict],
                      start: int) -> dict | None:
    """Read one contiguous block; None when the device refuses the address."""
    try:
        words = await client.read(start, _block_len(specs), cfg["input_type"])
    except ModbusError as exc:
        if exc.exception_code is None:
            raise
        return None
    return _decode_block(specs, start, words)


async def _read_subsystems(client: ModbusTcpClient, cfg: dict,
                           count: int) -> list[dict]:
    zones = []
    for i in range(min(int(count or 0), MAX_SUBSYSTEMS)):
        block = await _read_block(client, cfg, ZONE_REGISTERS, zone_addr(i))
        if block is None:
            continue
        zones.append({"index": i, "address": zone_addr(i), "readings": block,
                      "bases": [b for b in range(8)
                                if block["module_map"]["raw"] & (1 << b)]})
    return zones


async def _read_custom(client: ModbusTcpClient, cfg: dict) -> list[dict]:
    """Read every pinned register; a refused address shows as unavailable."""
    out = []
    for spec in cfg["custom"]:
        try:
            words = await client.read(spec["address"], 1, cfg["input_type"])
        except ModbusError as exc:
            if exc.exception_code is None:
                raise
            out.append({**spec, "raw": None, "value": None, "text": None,
                        "available": False})
            continue
        word = words[0]
        if spec["kind"] == "bool":
            out.append({**spec, "raw": word, "value": word,
                        "text": "attivo" if word else "non attivo",
                        "available": True})
        elif spec["kind"] == "temp":
            out.append({**spec, "raw": word, "value": temp_value(word),
                        "text": None, "available": True})
        else:
            value = word * spec["scale"]
            out.append({**spec, "raw": word,
                        "value": round(value, 2) if spec["scale"] != 1 else value,
                        "text": None, "available": True})
    return out


async def read_live(cfg: dict) -> dict:
    """Read system, subsystems, Smart Base and rooms. Errors are data, not raises."""
    empty = {"system": {}, "subsystems": [], "bases": [], "custom": []}
    if not cfg["enabled"]:
        return {"enabled": False, **empty, "error": None}
    if not cfg["host"]:
        return {"enabled": True, **empty,
                "error": "indirizzo del regolatore non configurato"}

    try:
        async with ModbusTcpClient(cfg["host"], cfg["port"], cfg["unit_id"],
                                   cfg["timeout"]) as client:
            system = await _read_block(client, cfg, SYSTEM_REGISTERS, SYSTEM_BASE)
            if system is None:
                return {"enabled": True, **empty,
                        "error": "il dispositivo non risponde ai registri di sistema"}
            subsystems = await _read_subsystems(
                client, cfg, system["subsystem_count"]["value"])

            bases = []
            for b in enabled_bases(cfg):
                block = await _read_block(client, cfg, MODULE_REGISTERS,
                                          module_addr(b["id"]))
                if block is None:
                    bases.append({**b, "address": module_addr(b["id"]),
                                  "available": False, "readings": {},
                                  "rooms": [], "custom": [], "air": None})
                    continue
                rooms = []
                for r in range(ROOMS_PER_MODULE):
                    rb = await _read_block(client, cfg, ROOM_REGISTERS,
                                           room_addr(b["id"], r))
                    if rb is None or not _room_present(rb):
                        continue
                    meta = room_meta(cfg, b["id"], r)
                    if meta and not meta["enabled"]:
                        continue
                    rooms.append({
                        "base": b["id"], "room": r,
                        "address": room_addr(b["id"], r),
                        "name": meta["name"] if meta else f"Stanza {r + 1}",
                        "unit": (meta["unit"] if meta else None) or b["unit"],
                        "readings": rb,
                    })
                bases.append({**b, "address": module_addr(b["id"]),
                              "available": True, "readings": block,
                              "rooms": rooms, "custom": [], "air": None})

            custom = await _read_custom(client, cfg)
    except ModbusError as exc:
        return {"enabled": True, **empty, "error": str(exc)}

    for base in bases:
        base["custom"] = [c for c in custom if c["group"] == f"base:{base['id']}"]
        base["air"] = {"model": base["air_model"],
                       "custom": [c for c in custom
                                  if c["group"] == f"air:{base['id']}"]}

    return {"enabled": True, "system": system, "subsystems": subsystems,
            "bases": bases,
            "custom": [c for c in custom
                       if not c["group"].startswith(("base:", "air:"))],
            "error": None, "read_at": time.time()}


def _cache_key(cfg: dict) -> tuple:
    return (cfg["enabled"], cfg["host"], cfg["port"], cfg["unit_id"],
            cfg["input_type"],
            tuple((b["id"], b["name"], b["air_model"]) for b in enabled_bases(cfg)),
            tuple((r["base"], r["room"], r["name"], r["enabled"], r["unit"])
                  for r in cfg["rooms"]),
            tuple((c["address"], c["name"], c["group"], c["scale"], c["kind"])
                  for c in cfg["custom"]))


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
    """Probe the controller: reachable? does it answer the system block?"""
    if not cfg["host"]:
        return {"ok": False, "error": "indirizzo del regolatore non configurato"}
    try:
        async with ModbusTcpClient(cfg["host"], cfg["port"], cfg["unit_id"],
                                   cfg["timeout"]) as client:
            system = await _read_block(client, cfg, SYSTEM_REGISTERS, SYSTEM_BASE)
    except ModbusError as exc:
        return {"ok": False, "error": str(exc)}
    if system is None:
        return {"ok": False, "error": "nessuna risposta ai registri di sistema"}
    return {"ok": True, "error": None, "system": system}


async def discover(cfg: dict) -> dict:
    """Walk the whole plant: subsystems → Smart Base → rooms.

    The controller publishes its own topology (register 59, the module bitmap in
    each zone block, and the per-room ids), so nothing has to be guessed. The
    result is a *proposal*: names are yours to set before saving.
    """
    if not cfg["host"]:
        return {"ok": False, "error": "indirizzo del regolatore non configurato",
                "bases": [], "subsystems": []}
    try:
        async with ModbusTcpClient(cfg["host"], cfg["port"], cfg["unit_id"],
                                   cfg["timeout"]) as client:
            system = await _read_block(client, cfg, SYSTEM_REGISTERS, SYSTEM_BASE)
            if system is None:
                return {"ok": False, "error": "nessuna risposta ai registri di sistema",
                        "bases": [], "subsystems": []}
            subsystems = await _read_subsystems(
                client, cfg, system["subsystem_count"]["value"])

            seen = sorted({b for z in subsystems for b in z["bases"]})
            if not seen:                    # zone map empty: probe every slot
                seen = list(range(MAX_MODULES))

            bases = []
            for base_id in seen:
                block = await _read_block(client, cfg, MODULE_REGISTERS,
                                          module_addr(base_id))
                if block is None or block["base_id"]["raw"] > 7:
                    continue
                known = next((b for b in cfg["bases"] if b["id"] == base_id), None)
                rooms = []
                for r in range(ROOMS_PER_MODULE):
                    rb = await _read_block(client, cfg, ROOM_REGISTERS,
                                           room_addr(base_id, r))
                    if rb is None or not _room_present(rb):
                        continue
                    meta = room_meta(cfg, base_id, r)
                    rooms.append({
                        "base": base_id, "room": r,
                        "address": room_addr(base_id, r),
                        "name": meta["name"] if meta else f"Stanza {r + 1}",
                        "enabled": meta["enabled"] if meta else True,
                        "unit": (meta["unit"] if meta else None),
                        "temperature": rb["temperature"]["value"],
                        "humidity": rb["humidity"]["value"],
                        "sensor_type": rb["sensor_type"]["text"],
                    })
                bases.append({
                    "id": base_id,
                    "name": known["name"] if known else f"Smart Base {base_id + 1}",
                    "unit": known["unit"] if known else None,
                    "enabled": known["enabled"] if known else True,
                    "air_model": known["air_model"] if known else "",
                    "address": module_addr(base_id),
                    "zone_id": block["zone_id"]["value"],
                    "sensor_count": block["sensor_count"]["value"],
                    "base_type": block["base_type"]["text"],
                    "rooms": rooms,
                })
    except ModbusError as exc:
        return {"ok": False, "error": str(exc), "bases": [], "subsystems": []}
    return {"ok": True, "error": None, "system": system,
            "subsystems": subsystems, "bases": bases}


# ---------------------------------------------------------------------------
# Register explorer
#
# Rev. 05 documents system, zone, Smart Base and room blocks — but nothing for
# the air machines (Deuclima-VMC / SmartAir) beyond the per-zone renewal boost.
# The explorer sweeps an address range so undocumented parameters can still be
# found: unused addresses answer with a Modbus exception, which we isolate by
# bisecting the failing chunk instead of giving up on the whole read.
# ---------------------------------------------------------------------------

EXPLORE_MAX = 2048          # registers per call
_EXPLORE_CHUNK = 64         # registers per Modbus read while sweeping


def explore_presets(cfg: dict) -> list[dict]:
    """Ranges worth sweeping, named after what the manual says lives there."""
    presets = [
        {"key": "system", "label": "Sistema + zone", "start": SYSTEM_BASE,
         "count": 1024, "hint": "50–59 sistema, 100+ blocchi zona (passo 130)"},
    ]
    for b in cfg["bases"]:
        presets.append({
            "key": f"base{b['id']}", "label": f"Base {b['id'] + 1} — {b['name']}",
            "start": module_addr(b["id"]), "count": 64,
            "hint": f"blocco Smart Base a {module_addr(b['id'])}",
        })
        presets.append({
            "key": f"baserooms{b['id']}",
            "label": f"Stanze base {b['id'] + 1}",
            "start": room_addr(b["id"], 0), "count": 2048,
            "hint": "8 stanze, passo 400",
        })
    presets.append({
        "key": "undocumented", "label": "Oltre il documentato (28000+)",
        "start": 28000, "count": 2048,
        "hint": "caccia ai registri non documentati, es. macchine aria",
    })
    return presets


def describe_address(cfg: dict, addr: int) -> str | None:
    """What the manual says lives at `addr`, when it says anything."""
    for pinned in cfg["custom"]:
        if pinned["address"] == addr:
            return f"📌 {pinned['name']}"
    if SYSTEM_BASE <= addr < SYSTEM_BASE + _block_len(SYSTEM_REGISTERS):
        off = addr - SYSTEM_BASE
        return next((s["label"] for s in SYSTEM_REGISTERS if s["offset"] == off), None)
    if ZONE_BASE <= addr < ZONE_BASE + MAX_SUBSYSTEMS * ZONE_STRIDE:
        idx, off = divmod(addr - ZONE_BASE, ZONE_STRIDE)
        label = next((s["label"] for s in ZONE_REGISTERS if s["offset"] == off), None)
        return f"{label} — zona {idx + 1}" if label else None
    if addr >= MODULE_BASE:
        base_id, off = divmod(addr - MODULE_BASE, MODULE_STRIDE)
        if base_id >= MAX_MODULES:
            return None
        base = next((b for b in cfg["bases"] if b["id"] == base_id), None)
        base_name = base["name"] if base else f"base {base_id + 1}"
        label = next((s["label"] for s in MODULE_REGISTERS if s["offset"] == off), None)
        if label:
            return f"{label} — {base_name}"
        if off >= ROOM_OFFSET:
            room, room_off = divmod(off - ROOM_OFFSET, ROOM_STRIDE)
            if room >= ROOMS_PER_MODULE:
                return None
            label = next((s["label"] for s in ROOM_REGISTERS
                          if s["offset"] == room_off), None)
            if label:
                meta = room_meta(cfg, base_id, room)
                name = meta["name"] if meta else f"stanza {room + 1}"
                return f"{label} — {name} ({base_name})"
    return None


async def _sweep(client: ModbusTcpClient, cfg: dict, start: int, count: int,
                 words: dict[int, int], unreadable: list[int]) -> None:
    """Read [start, start+count) splitting around addresses the device refuses."""
    try:
        regs = await client.read(start, count, cfg["input_type"])
    except ModbusError as exc:
        if exc.exception_code is None:
            raise                      # transport is gone: let the caller report
        if count == 1:
            unreadable.append(start)
            return
        half = count // 2
        await _sweep(client, cfg, start, half, words, unreadable)
        await _sweep(client, cfg, start + half, count - half, words, unreadable)
        return
    words.update({start + i: w for i, w in enumerate(regs)})


def _interpretations(word: int) -> dict:
    """Every plausible reading of a raw word, so the user can spot the right one."""
    signed = word - 65536 if word > _NEGATIVE_ABOVE else word
    return {
        "raw": word,
        "hex": f"0x{word:04X}",
        "int16": signed,
        "uint16": word,
        "x0_1": round(signed * 0.1, 1),
        "x0_01": round(signed * 0.01, 2),
        "bits": format(word, "016b"),
    }


def _explored(cfg: dict, words: dict[int, int]) -> list[dict]:
    return [{"address": addr, **_interpretations(word),
             "known": describe_address(cfg, addr)}
            for addr, word in sorted(words.items())]


async def explore(cfg: dict, start: int, count: int) -> dict:
    """Sweep an address range and decode every register that answers."""
    if not cfg["host"]:
        return {"ok": False, "error": "indirizzo del regolatore non configurato",
                "registers": [], "unreadable": []}
    count = max(1, min(int(count), EXPLORE_MAX))
    start = max(0, int(start))
    words: dict[int, int] = {}
    unreadable: list[int] = []
    try:
        async with ModbusTcpClient(cfg["host"], cfg["port"], cfg["unit_id"],
                                   cfg["timeout"]) as client:
            for chunk_start in range(start, start + count, _EXPLORE_CHUNK):
                chunk = min(_EXPLORE_CHUNK, start + count - chunk_start)
                await _sweep(client, cfg, chunk_start, chunk, words, unreadable)
    except ModbusError as exc:
        return {"ok": False, "error": str(exc),
                "registers": _explored(cfg, words), "unreadable": unreadable}
    return {"ok": True, "error": None, "start": start, "count": count,
            "registers": _explored(cfg, words), "unreadable": unreadable}
