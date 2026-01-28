from typing import ClassVar, Set, Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict, model_validator

class CardBase(BaseModel):
    """
    Abstract base model for all card-like game entities
    (spells, items, rituals, etc.)
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True
    )

    # Fields forbidden for this card type (override in subclasses)
    _forbidden_fields: ClassVar[Set[str]] = set()

    # --- Required ---
    id: int = Field(..., description="Unique numeric identifier")
    name: str = Field(..., description="Display name")

    # --- Optional common fields ---
    card_type: str = Field(..., description="Card type")
    tier: Optional[int] = None
    actions: Optional[str] = None

    traits: Optional[List[str]] = None
    traditions: Optional[List[str]] = None

    price: Optional[str] = None
    cast_time: Optional[str] = None
    range: Optional[str] = None
    targets: Optional[str] = None
    area: Optional[str] = None

    bulk: Optional[Decimal] = None

    body: Optional[str] = Field(
        None,
        description="Main descriptive rules text, stored as HTML or Markdown"
    )

    source: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def forbid_fields(cls, data):
        if not data:
            return data

        present = cls._forbidden_fields.intersection(data.keys())
        if present:
            raise ValueError(
                f"{cls.__name__} forbids fields: {', '.join(sorted(present))}"
            )
        return data
