import logging
from datetime import UTC, datetime

from faker import Faker

from legend.constants import DEFAULT_LOCALE
from legend.core.entities import Boundary, EntityType
from legend.core.models import DetectedSpan, EntityMapEntry, PseudonymEvent
from legend.entity_map.base import EntityMapBase
from legend.exceptions import ReplacementError
from legend.observability.emitter import (
    ENTITY_MAP_HIT,
    PSEUDONYM_CREATED,
    EventEmitter,
)
from legend.replacement.generators.base import GeneratorBase
from legend.replacement.generators.faker_generators import (
    CreditCardGenerator,
    EmailGenerator,
    IPGenerator,
    PersonGenerator,
    PhoneGenerator,
)
from legend.replacement.generators.format_preserving import (
    PassportGenerator,
    SSNGenerator,
)
from legend.replacement.generators.iban import IBANGenerator

logger = logging.getLogger(__name__)

_faker_fallback = Faker(DEFAULT_LOCALE)


def _normalize(value: str, entity_type: EntityType) -> str:
    """Apply normalization rules before entity map lookup.

    Args:
        value: The raw surface-form value.
        entity_type: Determines which normalization rule applies.

    Returns:
        The normalized canonical string.
    """
    if entity_type == EntityType.EMAIL_ADDRESS:
        return value.lower()
    if entity_type == EntityType.IBAN_CODE:
        return value.upper().replace(" ", "")
    if entity_type in (EntityType.PERSON, EntityType.LOCATION, EntityType.ORGANIZATION):
        return value.strip().title()
    if entity_type == EntityType.PHONE_NUMBER:
        return "".join(c for c in value if c.isdigit() or c == "+")
    return value.strip()


def _generate_variants(fake: str, entity_type: EntityType) -> list[str]:
    """Generate known surface-form variants for a fake value.

    This private function is only called during replacement. The revert pass
    reads pre-computed variants from EntityMapEntry.variants and does not
    call this function directly.

    Args:
        fake: The generated pseudonym.
        entity_type: Used to select which variant logic applies.

    Returns:
        A deduplicated list of surface-form variants (may include the original).
    """
    variants: list[str] = [fake]

    if entity_type == EntityType.PERSON:
        variants.append(fake.lower())
        variants.append(fake.upper())
        parts = fake.split()
        if len(parts) >= 2:
            variants.append(parts[0])
            variants.append(parts[-1])

    elif entity_type == EntityType.EMAIL_ADDRESS:
        variants.append(fake.lower())
        variants.append(fake.upper())

    elif entity_type == EntityType.IBAN_CODE:
        # Compact (no spaces) and grouped (every 4 chars)
        compact = fake.replace(" ", "")
        variants.append(compact)
        spaced = " ".join(compact[i : i + 4] for i in range(0, len(compact), 4))
        variants.append(spaced)

    elif entity_type == EntityType.CREDIT_CARD:
        digits = "".join(c for c in fake if c.isdigit())
        variants.append(digits)
        if len(digits) == 16:
            variants.append(f"{digits[:4]}-{digits[4:8]}-{digits[8:12]}-{digits[12:]}")
            variants.append(f"{digits[:4]} {digits[4:8]} {digits[8:12]} {digits[12:]}")
        elif len(digits) == 15:
            variants.append(f"{digits[:4]}-{digits[4:10]}-{digits[10:]}")
            variants.append(f"{digits[:4]} {digits[4:10]} {digits[10:]}")

    elif entity_type == EntityType.PHONE_NUMBER:
        digits_only = "".join(c for c in fake if c.isdigit())
        variants.append(digits_only)
        # Replace separators with spaces and hyphens alternately
        spaced = fake.replace("-", " ").replace(".", " ")
        variants.append(spaced)
        hyphenated = fake.replace(" ", "-").replace(".", "-")
        variants.append(hyphenated)

    elif entity_type == EntityType.US_SSN:
        # With and without hyphens
        digits = "".join(c for c in fake if c.isdigit())
        variants.append(digits)
        if len(digits) == 9:
            variants.append(f"{digits[:3]}-{digits[3:5]}-{digits[5:]}")

    elif entity_type == EntityType.US_PASSPORT:
        variants.append(fake.lower())

    else:
        variants.append(fake.strip())

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


def _faker_generate(entity_type: EntityType) -> str:
    """Fallback generator for entity types without a registered generator.

    Args:
        entity_type: The entity type to generate a pseudonym for.

    Returns:
        A Faker-generated string appropriate for the entity type.
    """
    match entity_type:
        case EntityType.LOCATION:
            return _faker_fallback.city()
        case EntityType.ORGANIZATION:
            return _faker_fallback.company()
        case EntityType.NRP:
            return _faker_fallback.country()
        case EntityType.URL:
            return _faker_fallback.url()
        case EntityType.CRYPTO:
            return "0x" + _faker_fallback.hexify(text="^" * 40)
        case _:
            return _faker_fallback.word()


class ReplacementEngine:
    """Applies the three-step entity-map-first replacement algorithm.

    Stateless with respect to the entity map. The generator registry is
    configured once at construction and reused across all sessions.
    """

    def __init__(
        self,
        custom_generators: dict[str, GeneratorBase] | None = None,
    ) -> None:
        """Build the generator registry from defaults and any overrides.

        Args:
            custom_generators: Optional mapping of entity type name strings to
                GeneratorBase instances. Overrides the built-in defaults for
                matching entity types.
        """
        self._registry: dict[EntityType, GeneratorBase] = {
            EntityType.PERSON: PersonGenerator(),
            EntityType.EMAIL_ADDRESS: EmailGenerator(),
            EntityType.PHONE_NUMBER: PhoneGenerator(),
            EntityType.IBAN_CODE: IBANGenerator(),
            EntityType.CREDIT_CARD: CreditCardGenerator(),
            EntityType.IP_ADDRESS: IPGenerator(),
            EntityType.US_SSN: SSNGenerator(),
            EntityType.US_PASSPORT: PassportGenerator(),
        }
        if custom_generators:
            for name, gen in custom_generators.items():
                try:
                    et = EntityType(name)
                    self._registry[et] = gen
                except ValueError:
                    logger.warning(
                        "replacement_engine: unknown entity type %r"
                        " in custom_generators",
                        name,
                    )

    async def replace(
        self,
        spans: list[DetectedSpan],
        text: str,
        entity_map: EntityMapBase,
        session_id: str,
        boundary: Boundary,
        emitter: EventEmitter,
    ) -> str:
        """Replace all detected spans in text with pseudonyms.

        Applies the three-step lookup for each span (reverse, forward, generate).
        Spans are applied in reverse order of position so earlier offsets remain
        valid after each substitution.

        Args:
            spans: Detected spans sorted by start position.
            text: The original text.
            entity_map: The session entity map.
            session_id: The current session identifier.
            boundary: The active boundary.
            emitter: The event emitter.

        Returns:
            The text with all spans replaced by pseudonyms.

        Raises:
            ReplacementError: If a generator raises an unhandled exception.
        """
        if not spans:
            return text

        result = text
        # Process spans from right to left to keep earlier offsets valid.
        for span in reversed(spans):
            normalized = _normalize(span.text, span.entity_type)

            # Step 1 — reverse lookup: already a pseudonym?
            existing_real = await entity_map.get_real(normalized)
            if existing_real is not None:
                logger.debug(
                    "replacement_engine: boundary=%s reverse-hit,"
                    " span=%r is already a fake",
                    boundary,
                    span.text,
                )
                continue

            # Step 2 — forward lookup: seen this real value before?
            existing_fake = await entity_map.get_fake(normalized)
            if existing_fake is not None:
                logger.debug(
                    "replacement_engine: boundary=%s forward-hit entity_type=%s",
                    boundary,
                    span.entity_type,
                )
                emitter.emit(
                    PseudonymEvent(
                        session_id=session_id,
                        event_type=ENTITY_MAP_HIT,
                        entity_type=span.entity_type,
                        fake_value=existing_fake,
                        boundary=boundary,
                        timestamp=datetime.now(UTC),
                    )
                )
                result = result[: span.start] + existing_fake + result[span.end :]
                continue

            # Step 3 — generate: new real value never seen before.
            if span.entity_type == EntityType.DATE_TIME:
                logger.debug("replacement_engine: DATE_TIME passes through unchanged")
                continue

            try:
                generator = self._registry.get(span.entity_type)
                if generator is not None:
                    fake = generator.generate(normalized, span.entity_type)
                else:
                    logger.warning(
                        "replacement_engine: no generator for %s, using Faker fallback",
                        span.entity_type,
                    )
                    fake = _faker_generate(span.entity_type)
            except Exception as exc:
                logger.error(
                    "replacement_engine: generator raised for %s: %s",
                    span.entity_type,
                    exc,
                )
                raise ReplacementError(
                    f"Generator failed for {span.entity_type}: {exc}"
                ) from exc

            variants = _generate_variants(fake, span.entity_type)
            entry = EntityMapEntry(
                real_normalized=normalized,
                real_original=span.text,
                fake=fake,
                entity_type=span.entity_type,
                variants=variants,
            )
            await entity_map.put(entry)

            emitter.emit(
                PseudonymEvent(
                    session_id=session_id,
                    event_type=PSEUDONYM_CREATED,
                    entity_type=span.entity_type,
                    fake_value=fake,
                    boundary=boundary,
                    timestamp=datetime.now(UTC),
                )
            )

            logger.debug(
                "replacement_engine: boundary=%s created entity_type=%s fake=%r",
                boundary,
                span.entity_type,
                fake,
            )
            result = result[: span.start] + fake + result[span.end :]

        return result
