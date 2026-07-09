"""Config API: the singleton settings row + effective entity map."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..entities import GROUPS, merged_map

router = APIRouter(prefix="/api", tags=["config"])


def get_or_create(db: Session) -> models.Config:
    cfg = db.get(models.Config, 1)
    if cfg is None:
        cfg = models.Config(id=1, entity_map={})
        db.add(cfg)
        db.commit()
    return cfg


def _out(cfg: models.Config) -> schemas.ConfigOut:
    # Expose the *effective* map (defaults + overrides) so the UI shows real ids.
    return schemas.ConfigOut(
        andrea_name=cfg.andrea_name,
        genitori_name=cfg.genitori_name,
        currency=cfg.currency,
        language=cfg.language,
        canone_rai_default=cfg.canone_rai_default,
        entity_map=merged_map(cfg.entity_map),
    )


@router.get("/config", response_model=schemas.ConfigOut)
def read_config(db: Session = Depends(get_db)):
    return _out(get_or_create(db))


@router.put("/config", response_model=schemas.ConfigOut)
def update_config(patch: schemas.ConfigUpdate, db: Session = Depends(get_db)):
    cfg = get_or_create(db)
    data = patch.model_dump(exclude_unset=True)
    entity_map = data.pop("entity_map", None)
    for k, v in data.items():
        setattr(cfg, k, v)
    if entity_map is not None:
        # Store only real overrides (differ from default is fine to keep too).
        merged = dict(cfg.entity_map or {})
        merged.update({k: v for k, v in entity_map.items() if v is not None})
        cfg.entity_map = merged
    db.commit()
    return _out(cfg)


@router.get("/config/entity_groups")
def entity_groups():
    """Labels/ordering for the Setup UI (static)."""
    return {"groups": GROUPS}
