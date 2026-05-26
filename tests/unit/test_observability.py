from datetime import UTC, datetime

from legend.core.entities import Boundary, EntityType
from legend.core.models import PseudonymEvent
from legend.observability.emitter import ENTITY_DETECTED, EventEmitter


def _make_event() -> PseudonymEvent:
    return PseudonymEvent(
        session_id="test-session",
        event_type=ENTITY_DETECTED,
        entity_type=EntityType.PERSON,
        fake_value="Jan Jansen",
        boundary=Boundary.A,
        timestamp=datetime.now(UTC),
    )


def test_emit_with_no_subscribers_does_not_raise() -> None:
    emitter = EventEmitter()
    event = _make_event()
    emitter.emit(event)  # should not raise


def test_subscribe_and_emit_single_subscriber_receives_event() -> None:
    emitter = EventEmitter()
    received: list[PseudonymEvent] = []
    emitter.subscribe(lambda e: received.append(e))
    event = _make_event()
    emitter.emit(event)
    assert len(received) == 1
    assert received[0] is event


def test_multiple_subscribers_all_receive_event() -> None:
    emitter = EventEmitter()
    bucket_a: list[PseudonymEvent] = []
    bucket_b: list[PseudonymEvent] = []
    emitter.subscribe(lambda e: bucket_a.append(e))
    emitter.subscribe(lambda e: bucket_b.append(e))
    event = _make_event()
    emitter.emit(event)
    assert len(bucket_a) == 1
    assert len(bucket_b) == 1


def test_bad_subscriber_exception_suppressed() -> None:
    emitter = EventEmitter()

    def bad_subscriber(e: PseudonymEvent) -> None:
        raise RuntimeError("subscriber exploded")

    emitter.subscribe(bad_subscriber)
    # Should not raise even though subscriber fails
    emitter.emit(_make_event())


def test_bad_subscriber_doesnt_prevent_others_from_receiving() -> None:
    emitter = EventEmitter()
    received: list[PseudonymEvent] = []

    def bad_subscriber(e: PseudonymEvent) -> None:
        raise RuntimeError("exploded")

    emitter.subscribe(bad_subscriber)
    emitter.subscribe(lambda e: received.append(e))
    emitter.emit(_make_event())
    assert len(received) == 1


def test_event_fields_passed_intact_to_subscriber() -> None:
    emitter = EventEmitter()
    received: list[PseudonymEvent] = []
    emitter.subscribe(lambda e: received.append(e))
    event = _make_event()
    emitter.emit(event)
    e = received[0]
    assert e.session_id == "test-session"
    assert e.event_type == ENTITY_DETECTED
    assert e.entity_type == EntityType.PERSON
    assert e.fake_value == "Jan Jansen"
    assert e.boundary == Boundary.A


def test_emit_multiple_events_all_delivered() -> None:
    emitter = EventEmitter()
    received: list[PseudonymEvent] = []
    emitter.subscribe(lambda e: received.append(e))
    for _ in range(5):
        emitter.emit(_make_event())
    assert len(received) == 5
