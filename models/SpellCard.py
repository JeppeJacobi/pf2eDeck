from typing import Optional
from pydantic import BaseModel
from models.CardBase import CardBase


class DegreesOfSuccess(BaseModel):
    critical_success: Optional[str] = None
    success: Optional[str] = None
    failure: Optional[str] = None
    critical_failure: Optional[str] = None


class SpellCard(CardBase):
    _forbidden_fields = {
        "price",
        "bulk",
    }

    duration: Optional[str] = None
    saving_throw: Optional[str] = None

    degrees_of_success: Optional[DegreesOfSuccess] = None
    requirements: Optional[str] = None
