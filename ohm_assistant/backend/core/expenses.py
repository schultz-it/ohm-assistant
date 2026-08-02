"""Shared-expense domain logic (SPEC 12): categories and split maths.

Category proposal is deliberately local and deterministic — a keyword match on
the description, no network call and no API key, so adding an expense stays
instant and free. The proposal is only ever a suggestion the user can override.

The split engine is pure: it takes the amount, the mode and its config and
returns the two shares, which always add up to the amount to the cent.
"""
import re
import unicodedata

# id, label, icon, keywords. Order matters: on a tie the earlier entry wins,
# and the longest matching keyword wins overall (so "canone rai" beats "rai").
# ``weak`` keywords only fire when nothing else matched: "manutenzione" is a
# fallback, but "manutenzione ascensore" belongs to Ascensore.
CATEGORIES: list[dict] = [
    {"id": "luce", "label": "Luce", "icon": "⚡", "keywords": [
        "luce", "elettricita", "energia elettrica", "enel", "servizio elettrico",
        "corrente", "pod", "bolletta luce"]},
    {"id": "gas", "label": "Gas", "icon": "🔥", "keywords": [
        "gas", "metano", "bolletta gas", "pdr"]},
    {"id": "acqua", "label": "Acqua", "icon": "💧", "keywords": [
        "acqua", "acquedotto", "idrico", "fognatura", "depurazione"]},
    {"id": "rifiuti", "label": "Rifiuti", "icon": "🗑️", "keywords": [
        "tari", "rifiuti", "spazzatura", "immondizia", "nettezza urbana",
        "raccolta differenziata"]},
    {"id": "condominio", "label": "Condominio", "icon": "🏢", "keywords": [
        "condominio", "condominiale", "amministratore", "rata condominiale",
        "assemblea", "millesimi", "fondo cassa"]},
    {"id": "manutenzione", "label": "Manutenzione", "icon": "🔧", "keywords": [
        "idraulico", "elettricista", "fabbro", "muratore", "imbianchino",
        "caldaia", "guasto", "perdita", "ricambio", "pompa di calore",
        "condizionatore", "infiltrazione", "tetto", "grondaia", "serramenti",
        "tapparella", "tapparelle"],
     "weak": ["manutenzione", "riparazione", "riparazioni", "revisione",
              "tecnico", "assistenza"]},
    {"id": "pulizie", "label": "Pulizie", "icon": "🧹", "keywords": [
        "pulizia", "pulizie", "scale", "impresa di pulizie",
        "sanificazione", "spazzacamino", "fossa biologica", "disinfestazione",
        "detersivi", "detersivo"]},
    {"id": "giardino", "label": "Giardino", "icon": "🌳", "keywords": [
        "giardino", "giardiniere", "siepe", "potatura", "prato", "irrigazione",
        "orto", "piante", "legna"]},
    {"id": "ascensore", "label": "Ascensore", "icon": "🛗", "keywords": [
        "ascensore", "montacarichi"]},
    {"id": "internet", "label": "Internet & TV", "icon": "📶", "keywords": [
        "internet", "fibra", "adsl", "wifi", "telefono", "tim", "vodafone",
        "fastweb", "iliad", "windtre", "canone rai", "abbonamento tv", "antenna"]},
    {"id": "abbonamenti", "label": "Abbonamenti", "icon": "🔁", "keywords": [
        "netflix", "spotify", "disney", "prime video", "amazon prime", "dazn",
        "now tv", "palestra", "rinnovo", "streaming", "icloud", "google one"],
     "weak": ["abbonamento", "abbonamenti", "mensile", "annuale"]},
    {"id": "assicurazione", "label": "Assicurazione", "icon": "🛡️", "keywords": [
        "assicurazione", "polizza", "rc fabbricato", "premio assicurativo"]},
    {"id": "tasse", "label": "Tasse", "icon": "🏛️", "keywords": [
        "imu", "tasi", "tassa", "tributo", "catasto", "notaio", "bollo"]},
    {"id": "spesa", "label": "Spesa & casa", "icon": "🛒", "keywords": [
        "spesa", "supermercato", "ferramenta", "mobili", "elettrodomestico",
        "lampadine", "arredo"]},
    {"id": "altro", "label": "Altro", "icon": "📌", "keywords": []},
]

CATEGORY_IDS = {c["id"] for c in CATEGORIES}
DEFAULT_CATEGORY = "altro"

SPLIT_MODES = ("equal", "percent", "amount")


class SplitError(ValueError):
    """Invalid split request — the message is shown to the user as-is."""


def _normalize(text: str) -> str:
    """Lowercase and strip accents so 'elettricità' matches 'elettricita'."""
    folded = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _best_match(text: str, field: str) -> tuple[int, str, str] | None:
    best: tuple[int, str, str] | None = None  # (keyword length, category, keyword)
    for cat in CATEGORIES:
        for kw in cat.get(field, ()):
            # Whole words only, so "gas" does not fire on "gasolio".
            if re.search(rf"\b{re.escape(kw)}\b", text):
                if best is None or len(kw) > best[0]:
                    best = (len(kw), cat["id"], kw)
    return best


def suggest_category(description: str) -> dict:
    """Propose a category from the description. Never fails; falls back to 'altro'."""
    text = _normalize(description or "")
    best = _best_match(text, "keywords") or _best_match(text, "weak")
    if best is None:
        return {"category": DEFAULT_CATEGORY, "matched": None}
    return {"category": best[1], "matched": best[2]}


def _num(value, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise SplitError(f"valore non numerico per {field}")


def compute_shares(amount: float, mode: str, config: dict | None) -> tuple[float, float]:
    """Return (andrea_share, genitori_share); they always sum to ``amount``.

    ``config`` holds ``{"andrea": x, "genitori": y}`` — percentages for
    ``percent`` (must total 100), euros for ``amount`` (must total the amount).
    Only Andrea's share is rounded; Genitori's is the remainder, so the two
    always reconcile with the receipt.
    """
    if mode not in SPLIT_MODES:
        raise SplitError(f"modalità di divisione sconosciuta: {mode}")
    amount = round(_num(amount, "importo"), 2)
    cfg = config or {}

    if mode == "equal":
        andrea = round(amount / 2, 2)
    elif mode == "percent":
        pa = _num(cfg.get("andrea", 50), "percentuale Andrea")
        pg = _num(cfg.get("genitori", 100 - pa), "percentuale Genitori")
        if pa < 0 or pg < 0:
            raise SplitError("le percentuali non possono essere negative")
        if abs(pa + pg - 100) > 0.01:
            raise SplitError(f"le percentuali devono sommare a 100 (ora {pa + pg:g})")
        andrea = round(amount * pa / 100, 2)
    else:  # amount
        andrea = round(_num(cfg.get("andrea", 0), "cifra Andrea"), 2)
        genitori = round(_num(cfg.get("genitori", 0), "cifra Genitori"), 2)
        if andrea < 0 or genitori < 0:
            raise SplitError("le cifre non possono essere negative")
        if abs(andrea + genitori - amount) > 0.01:
            raise SplitError(
                f"le cifre sommano a {andrea + genitori:.2f} invece di {amount:.2f}")

    return andrea, round(amount - andrea, 2)


def normalize_category(category: str | None, description: str) -> str:
    """Keep a known category, otherwise propose one from the description."""
    if category in CATEGORY_IDS:
        return category
    return suggest_category(description)["category"]
