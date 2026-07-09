"""Ripartition engine (SPEC 4) — the core.

Everything is computed on *gross* consumption so the photovoltaic self-
consumption never mixes bases: the bill is only the "€ pot" to divide, and the
split ratios come from the gross meter deltas. See SPEC 4 for the derivation.

``compute()`` is pure: it takes the bill figures and the period deltas and
returns the allocation + full breakdown. Persistence is the caller's job.
"""


def _val(deltas: dict, key: str):
    d = deltas.get(key)
    return d["value"] if d else None


def _missing(deltas: dict, keys: list[str]) -> list[str]:
    return [k for k in keys if _val(deltas, k) is None]


def compute_electric(billed: float, cost_total: float, canone_rai: float,
                     deltas: dict) -> dict:
    req = ["shelly_app_andrea", "pv_purchased", "pv_self_consumption",
           "zenner_andrea", "zenner_genitori"]
    missing = _missing(deltas, req)
    if missing:
        return {"ok": False, "missing": missing}
    if billed <= 0:
        return {"ok": False, "error": "kWh fatturati non positivi"}

    a_app = _val(deltas, "shelly_app_andrea")
    imp = _val(deltas, "pv_purchased")
    self_pv = _val(deltas, "pv_self_consumption")
    z_a = _val(deltas, "zenner_andrea")
    z_g = _val(deltas, "zenner_genitori")

    warnings = []
    L = imp + self_pv                      # carico lordo totale del POD
    S = L - a_app                          # bucket condiviso (non-appartamento)
    if L <= 0:
        return {"ok": False, "error": "carico lordo L non positivo"}
    if S < 0:
        warnings.append("S negativo: l'appartamento risulta > carico totale — "
                        "controlla pinze Shelly / sensori FV")

    denom_z = z_a + z_g
    if denom_z > 0:
        f_a = z_a / denom_z
    else:
        f_a = 0.5
        warnings.append("Zenner totale = 0 nel periodo: quota impostata a 50/50")
    f_g = 1 - f_a

    andrea_lordo = a_app + f_a * S
    genitori_lordo = f_g * S
    base = cost_total - canone_rai
    andrea_amount = base * andrea_lordo / L + canone_rai
    genitori_amount = base * genitori_lordo / L
    price = base / billed

    # Diagnostics (do not affect the split).
    prod = _val(deltas, "pv_ac_output")
    feed = _val(deltas, "pv_feed_in")
    clima = _val(deltas, "shelly_clima")
    diagnostics = {
        "imp_minus_billed": round(imp - billed, 2),
        "production_residual":
            round(prod - (feed + self_pv), 2) if prod is not None and feed is not None else None,
        "unmetered_load": round(L - a_app - clima, 2) if clima is not None else None,
    }

    return {
        "ok": True,
        "andrea_amount": round(andrea_amount, 2),
        "genitori_amount": round(genitori_amount, 2),
        "andrea_qty": round(andrea_lordo, 1),
        "genitori_qty": round(genitori_lordo, 1),
        "f_andrea": round(f_a, 4),
        "warnings": warnings,
        "breakdown": {
            "type": "electric",
            "A_app": round(a_app, 2), "imp": round(imp, 2),
            "self_pv": round(self_pv, 2), "L": round(L, 2), "S": round(S, 2),
            "zenner_andrea": round(z_a, 2), "zenner_genitori": round(z_g, 2),
            "f_andrea": round(f_a, 4), "f_genitori": round(f_g, 4),
            "andrea_lordo": round(andrea_lordo, 2),
            "genitori_lordo": round(genitori_lordo, 2),
            "price_eur_kwh": round(price, 4),
            "canone_rai": round(canone_rai, 2),
            "cost_total": round(cost_total, 2), "billed_kwh": billed,
            "diagnostics": diagnostics,
        },
    }


def compute_gas(billed: float, cost_total: float, deltas: dict) -> dict:
    req = ["zenner_andrea", "zenner_genitori"]
    missing = _missing(deltas, req)
    if missing:
        return {"ok": False, "missing": missing}

    z_a = _val(deltas, "zenner_andrea")
    z_g = _val(deltas, "zenner_genitori")
    warnings = []
    denom_z = z_a + z_g
    if denom_z > 0:
        f_a = z_a / denom_z
    else:
        f_a = 0.5
        warnings.append("Zenner totale = 0 nel periodo: quota impostata a 50/50")
    f_g = 1 - f_a

    return {
        "ok": True,
        "andrea_amount": round(cost_total * f_a, 2),
        "genitori_amount": round(cost_total * f_g, 2),
        "andrea_qty": round(f_a * billed, 1),
        "genitori_qty": round(f_g * billed, 1),
        "f_andrea": round(f_a, 4),
        "warnings": warnings,
        "breakdown": {
            "type": "gas",
            "zenner_andrea": round(z_a, 2), "zenner_genitori": round(z_g, 2),
            "f_andrea": round(f_a, 4), "f_genitori": round(f_g, 4),
            "cost_total": round(cost_total, 2), "billed_smc": billed,
        },
    }


def compute(bill_type: str, billed: float, cost_total: float,
            canone_rai: float, deltas: dict) -> dict:
    if bill_type == "electric":
        return compute_electric(billed, cost_total, canone_rai, deltas)
    if bill_type == "gas":
        return compute_gas(billed, cost_total, deltas)
    return {"ok": False, "error": f"tipo bolletta sconosciuto: {bill_type}"}
