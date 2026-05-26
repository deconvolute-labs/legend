import random
import string

from legend.core.entities import EntityType
from legend.replacement.generators.base import GeneratorBase

_INVALID_SSN_AREAS = {str(i).zfill(3) for i in range(900, 1000)} | {"000", "666"}


class SSNGenerator(GeneratorBase):
    """Generates format-preserving US Social Security Numbers (XXX-XX-XXXX)."""

    def generate(self, real_value: str, entity_type: EntityType, **kwargs: str) -> str:
        """Generate a random valid-format SSN.

        Excludes area numbers 000, 666, and 900-999 per IRS rules.

        Args:
            real_value: The real SSN (unused for generation).
            entity_type: Must be EntityType.US_SSN.
            **kwargs: Ignored.

        Returns:
            A fake SSN in XXX-XX-XXXX format.
        """
        while True:
            area = str(random.randint(1, 899)).zfill(3)
            if area not in _INVALID_SSN_AREAS:
                break
        group = str(random.randint(1, 99)).zfill(2)
        serial = str(random.randint(1, 9999)).zfill(4)
        return f"{area}-{group}-{serial}"


class PassportGenerator(GeneratorBase):
    """Generates US passport numbers (one uppercase letter + 8 digits)."""

    def generate(self, real_value: str, entity_type: EntityType, **kwargs: str) -> str:
        """Generate a random US passport number.

        Args:
            real_value: The real passport number (unused for generation).
            entity_type: Must be EntityType.US_PASSPORT.
            **kwargs: Ignored.

        Returns:
            A fake passport number: one uppercase letter followed by 8 digits.
        """
        letter = random.choice(string.ascii_uppercase)
        digits = "".join(str(random.randint(0, 9)) for _ in range(8))
        return f"{letter}{digits}"
