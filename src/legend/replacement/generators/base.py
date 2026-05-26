from abc import ABC, abstractmethod

from legend.core.entities import EntityType


class GeneratorBase(ABC):
    """Abstract base class for all pseudonym generators."""

    @abstractmethod
    def generate(self, real_value: str, entity_type: EntityType, **kwargs: str) -> str:
        """Generate a pseudonym for the given real value.

        Args:
            real_value: The normalized real value to replace.
            entity_type: The entity type of the value.
            **kwargs: Reserved for forward compatibility. In v1 the engine
                may pass person_pseudonym= to EmailGenerator.

        Returns:
            A generated pseudonym string.
        """
