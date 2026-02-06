from pydantic import BaseModel
from typing import List, Optional

class RelationShip(BaseModel):
    source: str
    target: str
    relation_type: str

class LoreEntity(BaseModel):
    name: str
    label: str
    category: Optional[str] = None