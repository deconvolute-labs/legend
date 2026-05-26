import asyncio
import logging

from legend.core.models import EntityMapEntry
from legend.entity_map.base import EntityMapBase
from legend.exceptions import EntityMapError

logger = logging.getLogger(__name__)


class InMemoryEntityMap(EntityMapBase):
    """Session-scoped in-memory entity map with O(1) bidirectional lookups.

    Two dicts provide fast lookup in both directions. An asyncio.Lock
    serializes all write operations. Read operations are lock-free.
    """

    def __init__(self) -> None:
        self._real_to_fake: dict[str, EntityMapEntry] = {}
        self._fake_to_real: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get_fake(self, real_normalized: str) -> str | None:
        """Return the fake value for a normalized real value, or None.

        Args:
            real_normalized: The normalized canonical form of the real value.

        Returns:
            The fake pseudonym, or None if not found.
        """
        entry = self._real_to_fake.get(real_normalized)
        return entry.fake if entry is not None else None

    async def get_real(self, fake: str) -> str | None:
        """Return the real normalized value for a fake value or variant, or None.

        Args:
            fake: A fake value or known surface-form variant.

        Returns:
            The normalized real value, or None if not found.
        """
        return self._fake_to_real.get(fake)

    async def put(self, entry: EntityMapEntry) -> None:
        """Write an entry to both dicts atomically under the asyncio lock.

        Registers all variants into the fake-to-real index so the revert
        pass can match any surface form. Raises EntityMapError if the real
        value already maps to a different fake (should not occur under correct
        lock usage).

        Args:
            entry: The entity map entry to store.

        Raises:
            EntityMapError: If a collision is detected.
        """
        async with self._lock:
            existing = self._real_to_fake.get(entry.real_normalized)
            if existing is not None and existing.fake != entry.fake:
                raise EntityMapError(
                    f"Collision: {entry.real_normalized!r} already maps to"
                    f" {existing.fake!r}, cannot remap to {entry.fake!r}"
                )
            self._real_to_fake[entry.real_normalized] = entry
            self._fake_to_real[entry.fake] = entry.real_normalized
            for variant in entry.variants:
                self._fake_to_real[variant] = entry.real_normalized
        logger.debug(
            "entity_map.put entity_type=%s fake=%r variants=%d",
            entry.entity_type,
            entry.fake,
            len(entry.variants),
        )

    async def all_fakes(self) -> list[str]:
        """Return all keys in the fake-to-real index.

        Returns:
            All fake values and variants currently registered.
        """
        return list(self._fake_to_real.keys())

    async def all_entries(self) -> list[EntityMapEntry]:
        """Return all entity map entries.

        Returns:
            All stored EntityMapEntry instances.
        """
        return list(self._real_to_fake.values())

    async def clear(self) -> None:
        """Clear all entries from both dicts."""
        async with self._lock:
            self._real_to_fake.clear()
            self._fake_to_real.clear()
        logger.debug("entity_map.clear")
