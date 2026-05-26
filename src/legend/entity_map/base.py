from abc import ABC, abstractmethod

from legend.core.models import EntityMapEntry


class EntityMapBase(ABC):
    """Abstract base class defining the entity map interface."""

    @abstractmethod
    async def get_fake(self, real_normalized: str) -> str | None:
        """Return the fake value for a normalized real value, or None if not found.

        Args:
            real_normalized: The normalized canonical form of the real value.

        Returns:
            The fake pseudonym, or None if the real value has not been seen.
        """

    @abstractmethod
    async def get_real(self, fake: str) -> str | None:
        """Return the real normalized value for a fake value or variant, or None.

        Args:
            fake: A fake value or known surface-form variant.

        Returns:
            The normalized real value, or None if the fake is not in the map.
        """

    @abstractmethod
    async def put(self, entry: EntityMapEntry) -> None:
        """Write an entry to the entity map atomically.

        Args:
            entry: The entity map entry to store.
        """

    @abstractmethod
    async def all_fakes(self) -> list[str]:
        """Return all known fake values and their variants.

        Returns:
            A flat list of all keys in the fake-to-real index.
        """

    @abstractmethod
    async def all_entries(self) -> list[EntityMapEntry]:
        """Return all entity map entries.

        Returns:
            All stored EntityMapEntry instances.
        """

    @abstractmethod
    async def clear(self) -> None:
        """Clear all entries from the entity map."""
