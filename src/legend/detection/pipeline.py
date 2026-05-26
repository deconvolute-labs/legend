import logging
from datetime import UTC, datetime
from pathlib import Path

from legend.constants import YARA_CONFIDENCE_BOOST
from legend.core.entities import Boundary, Detector, EntityType
from legend.core.models import DetectedSpan, PseudonymEvent
from legend.detection.spacy_detector import SpaCyDetector
from legend.detection.yara_detector import YARADetector
from legend.entity_map.base import EntityMapBase
from legend.observability.emitter import ENTITY_DETECTED, EventEmitter

logger = logging.getLogger(__name__)


def _overlaps(a: DetectedSpan, b: DetectedSpan) -> bool:
    return a.start < b.end and b.start < a.end


def _resolve(spans: list[DetectedSpan]) -> list[DetectedSpan]:
    """Merge and deduplicate spans, resolving overlaps by confidence.

    Same-detector overlaps: keep the longest span.
    Cross-detector overlaps: YARA score + YARA_CONFIDENCE_BOOST vs spaCy score;
    highest wins. Non-overlapping spans are all kept.

    Args:
        spans: Raw combined span list from both detectors.

    Returns:
        Deduplicated, sorted list of winning spans.
    """
    # Sort by start, then by length descending for stable ordering.
    sorted_spans = sorted(spans, key=lambda s: (s.start, -(s.end - s.start)))
    winners: list[DetectedSpan] = []

    for candidate in sorted_spans:
        dominated = False
        new_winners: list[DetectedSpan] = []
        for existing in winners:
            if not _overlaps(candidate, existing):
                new_winners.append(existing)
                continue
            # Overlapping — determine winner.
            if existing.detector == candidate.detector:
                # Same detector: keep longest.
                if (existing.end - existing.start) >= (candidate.end - candidate.start):
                    new_winners.append(existing)
                    dominated = True
                else:
                    new_winners.append(candidate)
                    dominated = True
            else:
                # Cross-detector: adjust YARA confidence, compare.
                yara_span = (
                    existing if existing.detector == Detector.YARA else candidate
                )
                spacy_span = (
                    existing if existing.detector == Detector.SPACY else candidate
                )
                yara_adj = yara_span.confidence + YARA_CONFIDENCE_BOOST
                if yara_adj >= spacy_span.confidence:
                    new_winners.append(yara_span)
                else:
                    new_winners.append(spacy_span)
                dominated = True
        if not dominated:
            new_winners.append(candidate)
        winners = new_winners

    return sorted(winners, key=lambda s: s.start)


class DetectionPipeline:
    """Runs YARA and spaCy detectors, merges results, resolves conflicts.

    Initialize once and reuse across sessions. Constructing this object loads
    the spaCy model, which takes several seconds.
    """

    def __init__(
        self,
        entities: list[str] | None = None,
        custom_rules_dir: Path | None = None,
    ) -> None:
        """Initialize both detectors.

        Args:
            entities: Optional allowlist of entity type names. If None, all
                types are active. Pass e.g. ["PERSON", "EMAIL_ADDRESS"] to
                limit detection scope.
            custom_rules_dir: Optional path to additional YARA rule files.

        Raises:
            DetectionError: If either detector fails to initialize.
        """
        self._yara = YARADetector(custom_rules_dir=custom_rules_dir)
        self._spacy = SpaCyDetector()
        self._active: set[EntityType] | None = None
        if entities is not None:
            self._active = set()
            for name in entities:
                try:
                    self._active.add(EntityType(name))
                except ValueError:
                    logger.warning(
                        "pipeline: unknown entity type %r in filter, skipping", name
                    )

    async def detect(
        self,
        text: str,
        entity_map: EntityMapBase,
        session_id: str,
        boundary: Boundary,
        emitter: EventEmitter,
    ) -> list[DetectedSpan]:
        """Detect PII in text using both detectors, merge and resolve conflicts.

        Args:
            text: The text to scan.
            entity_map: The session entity map (used for logging context only).
            session_id: The current session identifier.
            boundary: The boundary at which detection is running.
            emitter: The event emitter for observability events.

        Returns:
            Deduplicated list of DetectedSpan sorted by start position.

        Raises:
            DetectionError: If either underlying detector raises.
        """
        yara_spans = self._yara.detect(text)
        spacy_spans = self._spacy.detect(text)
        all_spans = yara_spans + spacy_spans

        if self._active is not None:
            all_spans = [s for s in all_spans if s.entity_type in self._active]

        resolved = _resolve(all_spans)

        for span in resolved:
            emitter.emit(
                PseudonymEvent(
                    session_id=session_id,
                    event_type=ENTITY_DETECTED,
                    entity_type=span.entity_type,
                    fake_value=None,
                    boundary=boundary,
                    timestamp=datetime.now(UTC),
                )
            )

        logger.info("pipeline: boundary=%s detected=%d spans", boundary, len(resolved))
        return resolved
