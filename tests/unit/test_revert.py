from legend.core.entities import Boundary, EntityType
from legend.core.models import EntityMapEntry, PseudonymEvent
from legend.entity_map.memory import InMemoryEntityMap
from legend.observability.emitter import REVERT_COMPLETE, EventEmitter
from legend.revert.pass_ import RevertPass


def _capture_emitter() -> tuple[EventEmitter, list[PseudonymEvent]]:
    events: list[PseudonymEvent] = []
    e = EventEmitter()
    e.subscribe(lambda ev: events.append(ev))
    return e, events


async def test_revert_empty_entity_map_returns_text_unchanged() -> None:
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()
    rp = RevertPass()
    result = await rp.revert("some text", em, "sid", emitter)
    assert result == "some text"


async def test_revert_single_pseudonym_replaced_with_real_original() -> None:
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()
    entry = EntityMapEntry(
        real_normalized="John Smith",
        real_original="John Smith",
        fake="Jan Jansen",
        entity_type=EntityType.PERSON,
        variants=["Jan Jansen", "jan jansen"],
    )
    await em.put(entry)
    rp = RevertPass()
    result = await rp.revert("Hello Jan Jansen!", em, "sid", emitter)
    assert result == "Hello John Smith!"


async def test_revert_multiple_pseudonyms_all_replaced() -> None:
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()

    await em.put(
        EntityMapEntry(
            real_normalized="John Smith",
            real_original="John Smith",
            fake="Jan Jansen",
            entity_type=EntityType.PERSON,
            variants=["Jan Jansen"],
        )
    )
    await em.put(
        EntityMapEntry(
            real_normalized="john.smith@work.com",
            real_original="john.smith@work.com",
            fake="user99@example.com",
            entity_type=EntityType.EMAIL_ADDRESS,
            variants=["user99@example.com", "USER99@EXAMPLE.COM"],
        )
    )

    rp = RevertPass()
    result = await rp.revert(
        "Contact Jan Jansen at user99@example.com", em, "sid", emitter
    )
    assert result == "Contact John Smith at john.smith@work.com"


async def test_revert_variant_form_replaced_with_real_original() -> None:
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()
    entry = EntityMapEntry(
        real_normalized="John Smith",
        real_original="John Smith",
        fake="Jan Jansen",
        entity_type=EntityType.PERSON,
        variants=["Jan Jansen", "jan jansen", "JAN JANSEN"],
    )
    await em.put(entry)
    rp = RevertPass()
    result = await rp.revert("hello jan jansen goodbye", em, "sid", emitter)
    assert result == "hello John Smith goodbye"


async def test_revert_longer_surface_before_shorter_prevents_partial_masking() -> None:
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()
    # "Jan Jansen" and its first-name variant "Jan" are both in variants.
    # If "Jan" is replaced before "Jan Jansen", text becomes "John Jansen is here".
    entry = EntityMapEntry(
        real_normalized="John Smith",
        real_original="John Smith",
        fake="Jan Jansen",
        entity_type=EntityType.PERSON,
        variants=["Jan Jansen", "jan jansen", "JAN JANSEN", "Jan", "Jansen"],
    )
    await em.put(entry)
    rp = RevertPass()
    result = await rp.revert("Jan Jansen is here.", em, "sid", emitter)
    assert result == "John Smith is here."
    assert "Jansen" not in result


async def test_revert_unknown_text_passes_through_unchanged() -> None:
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()
    entry = EntityMapEntry(
        real_normalized="John Smith",
        real_original="John Smith",
        fake="Jan Jansen",
        entity_type=EntityType.PERSON,
        variants=["Jan Jansen"],
    )
    await em.put(entry)
    rp = RevertPass()
    result = await rp.revert("Alice Wonderland is here.", em, "sid", emitter)
    assert result == "Alice Wonderland is here."


async def test_revert_emits_revert_complete_event_at_boundary_d() -> None:
    em = InMemoryEntityMap()
    emitter, events = _capture_emitter()
    entry = EntityMapEntry(
        real_normalized="John Smith",
        real_original="John Smith",
        fake="Jan Jansen",
        entity_type=EntityType.PERSON,
        variants=["Jan Jansen"],
    )
    await em.put(entry)
    rp = RevertPass()
    await rp.revert("Jan Jansen", em, "sid", emitter)
    complete = [e for e in events if e.event_type == REVERT_COMPLETE]
    assert len(complete) == 1
    assert complete[0].boundary == Boundary.D


async def test_revert_multiple_occurrences_of_same_fake_all_replaced() -> None:
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()
    entry = EntityMapEntry(
        real_normalized="John Smith",
        real_original="John Smith",
        fake="Jan Jansen",
        entity_type=EntityType.PERSON,
        variants=["Jan Jansen"],
    )
    await em.put(entry)
    rp = RevertPass()
    result = await rp.revert("Jan Jansen and Jan Jansen met.", em, "sid", emitter)
    assert result == "John Smith and John Smith met."


async def test_revert_uses_real_original_not_real_normalized() -> None:
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()
    # real_normalized differs in case from real_original
    entry = EntityMapEntry(
        real_normalized="john smith",
        real_original="JOHN SMITH",
        fake="Jan Jansen",
        entity_type=EntityType.PERSON,
        variants=["Jan Jansen"],
    )
    await em.put(entry)
    rp = RevertPass()
    result = await rp.revert("Jan Jansen", em, "sid", emitter)
    # Must use real_original, not real_normalized
    assert result == "JOHN SMITH"
    assert result != "john smith"
