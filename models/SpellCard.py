from typing import Optional
from models.CardBase import CardBase


class SpellCard(CardBase):
    _forbidden_fields = {
        "price",
        "bulk",
    }

    duration: Optional[str] = None
    saving_throw: Optional[str] = None

    heightening: Optional[str] = None
    requirements: Optional[str] = None
