from collections.abc import Callable

import pytest

from legend.core.entities import Boundary, Detector, EntityType
from legend.core.models import DetectedSpan, EntityMapEntry
from legend.entity_map.memory import InMemoryEntityMap
from legend.observability.emitter import EventEmitter


@pytest.fixture
def entity_map() -> InMemoryEntityMap:
    return InMemoryEntityMap()


@pytest.fixture
def emitter() -> EventEmitter:
    return EventEmitter()


@pytest.fixture
def session_id() -> str:
    return "test-session-id"


@pytest.fixture
def boundary() -> Boundary:
    return Boundary.A


@pytest.fixture
def make_span() -> Callable[..., DetectedSpan]:
    def _make(
        text: str,
        start: int,
        end: int,
        entity_type: EntityType = EntityType.PERSON,
        confidence: float = 0.8,
        detector: Detector = Detector.YARA,
    ) -> DetectedSpan:
        return DetectedSpan(
            text=text,
            start=start,
            end=end,
            entity_type=entity_type,
            confidence=confidence,
            detector=detector,
        )

    return _make


@pytest.fixture
def make_entry() -> Callable[..., EntityMapEntry]:
    def _make(
        real_normalized: str,
        real_original: str,
        fake: str,
        entity_type: EntityType = EntityType.PERSON,
        variants: list[str] | None = None,
    ) -> EntityMapEntry:
        return EntityMapEntry(
            real_normalized=real_normalized,
            real_original=real_original,
            fake=fake,
            entity_type=entity_type,
            variants=variants if variants is not None else [fake],
        )

    return _make
