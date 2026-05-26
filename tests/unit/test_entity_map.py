import asyncio
from collections.abc import Callable

import pytest

from legend.core.entities import EntityType
from legend.core.models import EntityMapEntry
from legend.entity_map.memory import InMemoryEntityMap
from legend.exceptions import EntityMapError


async def test_get_fake_returns_none_when_missing(
    entity_map: InMemoryEntityMap,
) -> None:
    result = await entity_map.get_fake("john smith")
    assert result is None


async def test_get_real_returns_none_when_missing(
    entity_map: InMemoryEntityMap,
) -> None:
    result = await entity_map.get_real("Jan Jansen")
    assert result is None


async def test_put_and_get_fake_returns_stored_fake(
    entity_map: InMemoryEntityMap,
    make_entry: Callable[..., EntityMapEntry],
) -> None:
    entry = make_entry(
        "John Smith", "John Smith", "Jan Jansen", EntityType.PERSON, ["Jan Jansen"]
    )
    await entity_map.put(entry)
    result = await entity_map.get_fake("John Smith")
    assert result == "Jan Jansen"


async def test_put_and_get_real_returns_real_normalized(
    entity_map: InMemoryEntityMap,
    make_entry: Callable[..., EntityMapEntry],
) -> None:
    entry = make_entry(
        "John Smith", "John Smith", "Jan Jansen", EntityType.PERSON, ["Jan Jansen"]
    )
    await entity_map.put(entry)
    result = await entity_map.get_real("Jan Jansen")
    assert result == "John Smith"


async def test_put_registers_all_variants_in_reverse_index(
    entity_map: InMemoryEntityMap,
    make_entry: Callable[..., EntityMapEntry],
) -> None:
    entry = make_entry(
        "John Smith",
        "John Smith",
        "Jan Jansen",
        EntityType.PERSON,
        ["Jan Jansen", "jan jansen", "JAN JANSEN", "Jan", "Jansen"],
    )
    await entity_map.put(entry)
    assert await entity_map.get_real("jan jansen") == "John Smith"
    assert await entity_map.get_real("JAN JANSEN") == "John Smith"
    assert await entity_map.get_real("Jan") == "John Smith"
    assert await entity_map.get_real("Jansen") == "John Smith"


async def test_all_fakes_includes_primary_fake_and_all_variants(
    entity_map: InMemoryEntityMap,
    make_entry: Callable[..., EntityMapEntry],
) -> None:
    entry = make_entry(
        "John Smith",
        "John Smith",
        "Jan Jansen",
        EntityType.PERSON,
        ["Jan Jansen", "jan jansen", "JAN JANSEN"],
    )
    await entity_map.put(entry)
    fakes = await entity_map.all_fakes()
    assert "Jan Jansen" in fakes
    assert "jan jansen" in fakes
    assert "JAN JANSEN" in fakes


async def test_all_entries_returns_stored_entries(
    entity_map: InMemoryEntityMap,
    make_entry: Callable[..., EntityMapEntry],
) -> None:
    entry1 = make_entry("John Smith", "John Smith", "Jan Jansen")
    entry2 = make_entry("jane.doe@work.com", "jane.doe@work.com", "user99@example.com")
    await entity_map.put(entry1)
    await entity_map.put(entry2)
    entries = await entity_map.all_entries()
    assert len(entries) == 2


async def test_put_same_entry_twice_is_idempotent(
    entity_map: InMemoryEntityMap,
    make_entry: Callable[..., EntityMapEntry],
) -> None:
    entry = make_entry("John Smith", "John Smith", "Jan Jansen")
    await entity_map.put(entry)
    await entity_map.put(entry)
    result = await entity_map.get_fake("John Smith")
    assert result == "Jan Jansen"


async def test_put_collision_different_fake_raises_entity_map_error(
    entity_map: InMemoryEntityMap,
    make_entry: Callable[..., EntityMapEntry],
) -> None:
    entry1 = make_entry("John Smith", "John Smith", "Jan Jansen")
    entry2 = make_entry("John Smith", "John Smith", "Pieter Pietersen")
    await entity_map.put(entry1)
    with pytest.raises(EntityMapError):
        await entity_map.put(entry2)


async def test_clear_empties_both_indexes(
    entity_map: InMemoryEntityMap,
    make_entry: Callable[..., EntityMapEntry],
) -> None:
    entry = make_entry(
        "John Smith",
        "John Smith",
        "Jan Jansen",
        EntityType.PERSON,
        ["Jan Jansen", "jan jansen"],
    )
    await entity_map.put(entry)
    await entity_map.clear()
    assert await entity_map.all_entries() == []
    assert await entity_map.all_fakes() == []


async def test_get_fake_returns_none_after_clear(
    entity_map: InMemoryEntityMap,
    make_entry: Callable[..., EntityMapEntry],
) -> None:
    entry = make_entry("John Smith", "John Smith", "Jan Jansen")
    await entity_map.put(entry)
    await entity_map.clear()
    assert await entity_map.get_fake("John Smith") is None


async def test_get_real_returns_none_after_clear(
    entity_map: InMemoryEntityMap,
    make_entry: Callable[..., EntityMapEntry],
) -> None:
    entry = make_entry(
        "John Smith",
        "John Smith",
        "Jan Jansen",
        EntityType.PERSON,
        ["Jan Jansen", "jan jansen"],
    )
    await entity_map.put(entry)
    await entity_map.clear()
    assert await entity_map.get_real("Jan Jansen") is None
    assert await entity_map.get_real("jan jansen") is None


async def test_concurrent_puts_distinct_keys_all_succeed() -> None:
    em = InMemoryEntityMap()
    entries = [
        EntityMapEntry(
            real_normalized=f"person{i}",
            real_original=f"Person {i}",
            fake=f"Fake{i}",
            entity_type=EntityType.PERSON,
            variants=[f"Fake{i}", f"fake{i}"],
        )
        for i in range(20)
    ]
    await asyncio.gather(*(em.put(e) for e in entries))
    all_entries = await em.all_entries()
    assert len(all_entries) == 20


async def test_all_fakes_returns_empty_on_fresh_map(
    entity_map: InMemoryEntityMap,
) -> None:
    assert await entity_map.all_fakes() == []


async def test_all_entries_returns_empty_on_fresh_map(
    entity_map: InMemoryEntityMap,
) -> None:
    assert await entity_map.all_entries() == []
