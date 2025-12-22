from pydantic import BaseModel
from typing import Optional

class CharacterBase(BaseModel):
    name: str
    role: str
    description: str

class CharacterCreate(CharacterBase):
    pass

class Character(CharacterBase):
    id: int
    project_id: int
    reference_image_url: Optional[str] = None
    appearance_prompt: Optional[str] = None
    
    class Config:
        from_attributes = True
