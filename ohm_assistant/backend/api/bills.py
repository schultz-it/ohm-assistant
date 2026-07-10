"""Bills CRUD API. Ripartition computation arrives in M3."""
import shutil
from pathlib import Path

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core import engine, snapshot
from ..db import DATA_DIR, get_db
from .config import get_or_create

router = APIRouter(prefix="/api/bills", tags=["bills"])
PDF_DIR = DATA_DIR / "pdfs"


def _get(db: Session, bill_id: int) -> models.Bill:
    bill = db.get(models.Bill, bill_id)
    if bill is None:
        raise HTTPException(404, "bill not found")
    return bill


@router.get("", response_model=list[schemas.BillOut])
def list_bills(type: str | None = None, db: Session = Depends(get_db)):
    stmt = select(models.Bill).order_by(models.Bill.period_start.desc())
    if type:
        stmt = stmt.where(models.Bill.type == type)
    return db.scalars(stmt).all()


@router.post("", response_model=schemas.BillOut, status_code=201)
def create_bill(data: schemas.BillIn, db: Session = Depends(get_db)):
    if data.period_end < data.period_start:
        raise HTTPException(422, "period_end before period_start")
    bill = models.Bill(**data.model_dump())
    db.add(bill)
    db.commit()
    return bill


@router.get("/{bill_id}", response_model=schemas.BillOut)
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    return _get(db, bill_id)


@router.put("/{bill_id}", response_model=schemas.BillOut)
def update_bill(bill_id: int, patch: schemas.BillUpdate, db: Session = Depends(get_db)):
    bill = _get(db, bill_id)
    for k, v in patch.model_dump(exclude_unset=True).items():
        setattr(bill, k, v)
    db.commit()
    return bill


@router.delete("/{bill_id}", status_code=204)
def delete_bill(bill_id: int, db: Session = Depends(get_db)):
    db.delete(_get(db, bill_id))
    db.commit()


@router.post("/{bill_id}/compute")
def compute_bill(bill_id: int, persist: bool = True, db: Session = Depends(get_db)):
    """Run the ripartition for a bill from the period meter deltas (SPEC 4).

    Returns ``ok=false`` + ``missing`` keys when snapshots don't cover the
    period yet (import history or enter readings first). Persists the allocation
    onto the bill only when the computation succeeds and ``persist`` is set.
    """
    bill = _get(db, bill_id)
    cfg = get_or_create(db)
    deltas = snapshot.period_deltas(db, cfg, bill.period_start, bill.period_end)
    res = engine.compute(bill.type, bill.billed, bill.cost_total,
                         bill.canone_rai, deltas)
    if res.get("ok") and persist:
        bill.andrea_amount = res["andrea_amount"]
        bill.genitori_amount = res["genitori_amount"]
        bill.andrea_qty = res["andrea_qty"]
        bill.genitori_qty = res["genitori_qty"]
        bill.f_andrea = res["f_andrea"]
        bill.breakdown = res["breakdown"]
        db.commit()
    res["deltas"] = {k: (v["value"] if v else None) for k, v in deltas.items()}
    return res


@router.post("/{bill_id}/pdf")
def upload_pdf(bill_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Attach the original bill PDF (stored under /data/pdfs)."""
    bill = _get(db, bill_id)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    dest = PDF_DIR / f"bill_{bill_id}.pdf"
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)
    bill.pdf_path = str(dest)
    db.commit()
    return {"pdf_path": bill.pdf_path}


@router.get("/{bill_id}/pdf")
def get_pdf(bill_id: int, db: Session = Depends(get_db)):
    bill = _get(db, bill_id)
    if not bill.pdf_path or not Path(bill.pdf_path).exists():
        raise HTTPException(404, "nessun PDF allegato")
    return FileResponse(bill.pdf_path, media_type="application/pdf",
                        filename=f"bolletta_{bill_id}.pdf")


def _eur(n) -> str:
    return "—" if n is None else "€ " + f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@router.get("/{bill_id}/report", response_class=HTMLResponse)
def report(bill_id: int, db: Session = Depends(get_db)):
    """Self-contained printable ripartition summary, shareable with the family."""
    bill = _get(db, bill_id)
    cfg = get_or_create(db)
    if bill.andrea_amount is None:
        return HTMLResponse("<p style='font-family:sans-serif'>Bolletta non ancora "
                            "calcolata. Premi «Calcola» prima di stampare.</p>")
    bd = bill.breakdown or {}
    unit = "Smc" if bill.type == "gas" else "kWh"
    kind = "Gas" if bill.type == "gas" else "Luce"

    rows = [("Periodo", f"{bill.period_start} → {bill.period_end}"),
            (f"{kind} fatturati", f"{bill.billed} {unit}"),
            ("Costo totale", _eur(bill.cost_total))]
    if bill.type == "electric":
        rows.append(("Canone RAI (→ %s)" % cfg.andrea_name, _eur(bill.canone_rai)))
        if bd.get("price_eur_kwh") is not None:
            rows.append(("Prezzo medio", f"€ {bd['price_eur_kwh']}/kWh"))
    rows.append(("Quota calore Andrea (Zenner)", f"{round((bill.f_andrea or 0) * 100)}%"))

    detail = "".join(f"<tr><td>{k}</td><td style='text-align:right'>{v}</td></tr>" for k, v in rows)
    return HTMLResponse(f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Riepilogo bolletta</title>
<style>
 body{{font-family:system-ui,sans-serif;max-width:38rem;margin:2rem auto;padding:0 1rem;color:#111}}
 h1{{font-size:1.3rem}} .sub{{color:#666;margin-top:-.4rem}}
 .split{{display:flex;gap:1rem;margin:1.4rem 0}}
 .box{{flex:1;text-align:center;border-radius:.8rem;padding:1rem}}
 .a{{background:#fef3c7}} .g{{background:#e0f2fe}}
 .amt{{font-size:1.8rem;font-weight:700}} .a .amt{{color:#b45309}} .g .amt{{color:#0369a1}}
 table{{width:100%;border-collapse:collapse;font-size:.92rem}}
 td{{padding:.35rem .2rem;border-bottom:1px solid #eee}}
 .foot{{color:#888;font-size:.8rem;margin-top:1.5rem}}
 button{{padding:.5rem 1rem;border:1px solid #ccc;border-radius:.5rem;background:#f7f7f7;cursor:pointer}}
 @media print{{button{{display:none}}}}
</style></head><body>
<h1>⚡ Ripartizione bolletta {kind}</h1>
<p class="sub">{bill.period_start} → {bill.period_end}</p>
<div class="split">
  <div class="box a"><div>{cfg.andrea_name}</div><div class="amt">{_eur(bill.andrea_amount)}</div>
    <div style="color:#666">{bill.andrea_qty} {unit}</div></div>
  <div class="box g"><div>{cfg.genitori_name}</div><div class="amt">{_eur(bill.genitori_amount)}</div>
    <div style="color:#666">{bill.genitori_qty} {unit}</div></div>
</div>
<table>{detail}</table>
<p class="foot">Generato il {date.today().isoformat()} da Ohm Assistant.</p>
<button onclick="window.print()">Stampa / Salva PDF</button>
</body></html>""")
