from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models import Character
from app.schemas.project import Character as CharacterSchema
from typing import List

router = APIRouter()

@router.get("/{project_id}/characters", response_model=List[CharacterSchema])
def get_project_characters(project_id: int, db: Session = Depends(get_db)):
    """Get all characters for a project"""
    characters = db.query(Character).filter(Character.project_id == project_id).all()
    return characters

@router.get("/characters/{character_id}", response_model=CharacterSchema)
def get_character(character_id: int, db: Session = Depends(get_db)):
    """Get a specific character"""
    character = db.query(Character).filter(Character.id == character_id).first()
    return character
