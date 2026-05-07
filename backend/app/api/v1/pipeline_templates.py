"""
Pipeline Templates API — save and reuse generation pipeline configurations.
"""
import json
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.pipeline_template import PipelineTemplate

router = APIRouter()


class PipelineTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    payload: dict = Field(..., description="Opaque JSON config (idea form + per-episode overrides + storyboard preset)")


class PipelineTemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    payload: Optional[dict] = None


class PipelineTemplateRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    payload: dict
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


def _serialize(item: PipelineTemplate) -> PipelineTemplateRead:
    try:
        payload = json.loads(item.payload_json) if item.payload_json else {}
    except json.JSONDecodeError:
        payload = {}
    return PipelineTemplateRead(
        id=item.id,
        name=item.name,
        description=item.description,
        payload=payload,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("/", response_model=List[PipelineTemplateRead])
def list_templates(db: Session = Depends(get_db)):
    items = db.query(PipelineTemplate).order_by(PipelineTemplate.updated_at.desc().nullslast(), PipelineTemplate.created_at.desc()).all()
    return [_serialize(i) for i in items]


@router.post("/", response_model=PipelineTemplateRead)
def create_template(payload: PipelineTemplateCreate, db: Session = Depends(get_db)):
    item = PipelineTemplate(
        name=payload.name,
        description=payload.description,
        payload_json=json.dumps(payload.payload, ensure_ascii=False),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.get("/{template_id}", response_model=PipelineTemplateRead)
def read_template(template_id: int, db: Session = Depends(get_db)):
    item = db.query(PipelineTemplate).filter(PipelineTemplate.id == template_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Template not found")
    return _serialize(item)


@router.put("/{template_id}", response_model=PipelineTemplateRead)
def update_template(template_id: int, patch: PipelineTemplateUpdate, db: Session = Depends(get_db)):
    item = db.query(PipelineTemplate).filter(PipelineTemplate.id == template_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Template not found")
    if patch.name is not None:
        item.name = patch.name
    if patch.description is not None:
        item.description = patch.description
    if patch.payload is not None:
        item.payload_json = json.dumps(patch.payload, ensure_ascii=False)
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.delete("/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    item = db.query(PipelineTemplate).filter(PipelineTemplate.id == template_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(item)
    db.commit()
    return {"success": True}
