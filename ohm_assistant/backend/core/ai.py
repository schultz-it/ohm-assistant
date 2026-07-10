"""AI extraction of bill fields from a PDF (SPEC 8) — proposal only.

Providers come from the add-on options, exported as env vars by the run script:
``openai`` / ``anthropic`` (direct API with the user's key). The PDF text is
extracted locally (pypdf) and sent to the model, which must return strict JSON.
The result is always a *proposal* the user reviews before saving — the AI never
creates or computes anything.
"""
import io
import json
import os

import httpx
from pypdf import PdfReader

TIMEOUT = 120.0
DEFAULT_MODELS = {"openai": "gpt-4o-mini", "anthropic": "claude-sonnet-5"}
MAX_CHARS = 20000

SYSTEM_PROMPT = """Sei un estrattore di dati da bollette italiane di luce e gas.
Ricevi il testo di una bolletta e restituisci SOLO un oggetto JSON, senza testo
prima o dopo, con esattamente questi campi:
{
  "type": "electric" | "gas",        // "electric" per energia elettrica/luce, "gas" per gas metano
  "period_start": "YYYY-MM-DD",       // inizio periodo di fatturazione/competenza
  "period_end": "YYYY-MM-DD",         // fine periodo
  "billed": number,                   // kWh fatturati (electric) oppure Smc fatturati (gas)
  "cost_total": number,               // totale da pagare della bolletta, in euro
  "canone_rai": number                // canone TV/RAI in euro se presente (solo electric), altrimenti 0
}
Regole: usa il punto come separatore decimale; se un campo non è deducibile
metti null (tranne canone_rai che è 0 se assente). Non inventare valori."""


class AiError(Exception):
    pass


def provider_info() -> dict:
    provider = os.environ.get("AI_PROVIDER", "none")
    model = os.environ.get("AI_MODEL") or DEFAULT_MODELS.get(provider)
    available = provider in ("openai", "anthropic") and bool(os.environ.get("AI_API_KEY"))
    return {"provider": provider, "model": model, "available": available}


def extract_text(pdf_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as e:  # noqa: BLE001
        raise AiError(f"PDF illeggibile: {e}")
    return text[:MAX_CHARS]


async def _call_openai(key: str, model: str, text: str) -> str:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model, "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
            },
        )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


async def _call_anthropic(key: str, model: str, text: str) -> str:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            json={
                "model": model, "max_tokens": 1024,
                "system": SYSTEM_PROMPT + "\nRispondi solo con il JSON.",
                "messages": [{"role": "user", "content": text}],
            },
        )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def _num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace("€", "").replace(",", ".").strip())
    except ValueError:
        return None


def _coerce(raw: dict) -> dict:
    t = (raw.get("type") or "").lower()
    if t not in ("electric", "gas"):
        t = "electric"
    return {
        "type": t,
        "period_start": raw.get("period_start"),
        "period_end": raw.get("period_end"),
        "billed": _num(raw.get("billed")),
        "cost_total": _num(raw.get("cost_total")),
        "canone_rai": _num(raw.get("canone_rai")) or 0.0,
    }


async def extract_bill(pdf_bytes: bytes) -> dict:
    info = provider_info()
    if not info["available"]:
        raise AiError("AI non configurata: imposta ai_provider e ai_api_key nelle opzioni dell'add-on")
    text = extract_text(pdf_bytes)
    if len(text.strip()) < 20:
        raise AiError("PDF senza testo estraibile (probabile scansione): inserisci i dati a mano")

    key = os.environ["AI_API_KEY"]
    model = info["model"]
    if info["provider"] == "openai":
        content = await _call_openai(key, model, text)
    else:
        content = await _call_anthropic(key, model, text)

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Some models wrap JSON in prose/fences; grab the outermost object.
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end == -1:
            raise AiError("Risposta AI non in formato JSON")
        data = json.loads(content[start:end + 1])
    return _coerce(data)
