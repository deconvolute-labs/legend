import logging
from datetime import UTC, datetime

from legend.core.entities import Boundary
from legend.core.models import PseudonymEvent
from legend.entity_map.base import EntityMapBase
from legend.observability.emitter import REVERT_COMPLETE, EventEmitter

logger = logging.getLogger(__name__)


class RevertPass:
    """De-pseudonymizes text at Boundary D by replacing all known fake values.

    No detection pipeline is invoked. Variants computed at replacement time
    are read from EntityMapEntry.variants and used for surface-form matching.
    """

    async def revert(
        self,
        text: str,
        entity_map: EntityMapBase,
        session_id: str,
        emitter: EventEmitter,
    ) -> str:
        """Replace all pseudonyms in text with their original normalized values.

        Two-pass reversion:
        1. Build a mapping of every known fake surface form to its real value.
        2. Replace all occurrences, sorting by length descending to prevent
           partial-match interference between longer and shorter variants.

        Args:
            text: The agent response containing pseudonyms.
            entity_map: The session entity map.
            session_id: The current session identifier.
            emitter: The event emitter.

        Returns:
            The text with all recognizable pseudonyms restored to real values.
        """
        entries = await entity_map.all_entries()
        if not entries:
            logger.info("revert: entity_map is empty, nothing to revert")
            return text

        # Build surface-form -> real lookup; all variants included.
        surface_map: dict[str, str] = {}
        for entry in entries:
            surface_map[entry.fake] = entry.real_original
            for variant in entry.variants:
                if variant not in surface_map:
                    surface_map[variant] = entry.real_original

        # Sort surface forms longest-first to prevent shorter variants from
        # masking longer ones during sequential replacement.
        sorted_surfaces = sorted(surface_map.keys(), key=len, reverse=True)

        result = text
        match_count = 0
        for surface in sorted_surfaces:
            if surface in result:
                real = surface_map[surface]
                occurrences = result.count(surface)
                result = result.replace(surface, real)
                match_count += occurrences
                logger.debug(
                    "revert: replaced %r -> %r (%d occurrence(s))",
                    surface,
                    real,
                    occurrences,
                )

        logger.info("revert: total replacements=%d", match_count)

        emitter.emit(
            PseudonymEvent(
                session_id=session_id,
                event_type=REVERT_COMPLETE,
                entity_type=None,
                fake_value=None,
                boundary=Boundary.D,
                timestamp=datetime.now(UTC),
            )
        )

        return result
