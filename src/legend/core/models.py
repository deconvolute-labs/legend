from datetime import datetime

from pydantic import BaseModel

from legend.core.entities import Boundary, Detector, EntityType


class DetectedSpan(BaseModel):
    """A single PII span detected in text."""

    text: str
    start: int
    end: int
    entity_type: EntityType
    confidence: float
    detector: Detector


class EntityMapEntry(BaseModel):
    """One entry in the session entity map."""

    real_normalized: str
    real_original: str
    fake: str
    entity_type: EntityType
    variants: list[str]


class PseudonymEvent(BaseModel):
    """An observability event emitted during pseudonymization or reversion."""

    session_id: str
    event_type: str
    entity_type: EntityType | None = None
    fake_value: str | None = None
    boundary: Boundary
    timestamp: datetime
