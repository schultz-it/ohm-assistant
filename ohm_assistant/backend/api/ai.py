"""AI API: provider status + extract bill fields from an uploaded PDF (SPEC 8)."""
from fastapi import APIRouter, File, HTTPException, UploadFile

from ..core import ai

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/status")
def status():
    return ai.provider_info()


@router.post("/extract")
async def extract(file: UploadFile = File(...)):
    """Extract a bill proposal from a PDF. Never saves — the user reviews it."""
    data = await file.read()
    try:
        return await ai.extract_bill(data)
    except ai.AiError as e:
        raise HTTPException(422, str(e))
    except Exception as e:  # noqa: BLE001 — surface provider errors to the UI
        raise HTTPException(502, f"estrazione AI fallita: {e}")
