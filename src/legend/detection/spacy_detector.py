import logging
import os
from pathlib import Path

import spacy
from spacy.language import Language
from spacy.tokens import Doc

from legend.constants import (
    DEFAULT_MODEL_DIR,
    LEGEND_MODEL_DIR_ENV,
    SPACY_DEFAULT_CONFIDENCE,
    SPACY_MODEL,
)
from legend.core.entities import Detector, EntityType
from legend.core.models import DetectedSpan
from legend.exceptions import DetectionError
from legend.setup import ensure_models

logger = logging.getLogger(__name__)

# Map spaCy NER labels to Legend EntityType values.
_LABEL_MAP: dict[str, EntityType] = {
    "PERSON": EntityType.PERSON,
    "PER": EntityType.PERSON,
    "LOC": EntityType.LOCATION,
    "GPE": EntityType.LOCATION,
    "FAC": EntityType.LOCATION,
    "ORG": EntityType.ORGANIZATION,
    "DATE": EntityType.DATE_TIME,
    "TIME": EntityType.DATE_TIME,
    "NORP": EntityType.NRP,
}


class SpaCyDetector:
    """Runs spaCy NER to detect semantic PII entity types.

    The model is loaded once at construction time. Initialization
    is expensive; create this object once and reuse across sessions.
    """

    def __init__(self, model_path: Path | None = None) -> None:
        """Resolve the model path, download if absent, and load the model.

        Model path resolution order:
            1. Explicit model_path parameter if provided.
            2. LEGEND_MODEL_PATH environment variable if set.
            3. DEFAULT_MODEL_DIR / SPACY_MODEL as the fallback.

        Args:
            model_path: Full path to the spaCy model directory. If None,
                the path is resolved via environment variable or default.

        Raises:
            DetectionError: If the model cannot be downloaded or loaded.
        """
        resolved = _resolve_model_path(model_path)

        if not resolved.exists():
            logger.info(
                "legend.detection: spaCy model not found at %s. Downloading... "
                "(this may take several minutes)",
                resolved,
            )
            ensure_models(resolved.parent)
            logger.info(
                "legend.detection: spaCy model downloaded successfully to %s",
                resolved,
            )

        try:
            self._nlp: Language = spacy.load(resolved)
            logger.info("spacy_detector: loaded model from %s", resolved)
        except Exception as exc:
            logger.error(
                "spacy_detector: failed to load model at %s: %s", resolved, exc
            )
            raise DetectionError(
                f"spaCy model load failed ({resolved}): {exc}"
            ) from exc

    def detect(self, text: str) -> list[DetectedSpan]:
        """Run spaCy NER on text and return matched spans.

        Args:
            text: The text to analyze.

        Returns:
            A list of DetectedSpan instances for recognized entities.

        Raises:
            DetectionError: If the spaCy pipeline raises an exception.
        """
        try:
            doc: Doc = self._nlp(text)
        except Exception as exc:
            logger.error("spacy_detector: NLP pipeline failed: %s", exc)
            raise DetectionError(f"spaCy pipeline failed: {exc}") from exc

        spans: list[DetectedSpan] = []
        for ent in doc.ents:
            entity_type = _LABEL_MAP.get(ent.label_)
            if entity_type is None:
                logger.debug("spacy_detector: unmapped label %r, skipping", ent.label_)
                continue
            spans.append(
                DetectedSpan(
                    text=ent.text,
                    start=ent.start_char,
                    end=ent.end_char,
                    entity_type=entity_type,
                    confidence=SPACY_DEFAULT_CONFIDENCE,
                    detector=Detector.SPACY,
                )
            )
            logger.debug(
                "spacy_detector: hit entity_type=%s start=%d end=%d",
                entity_type,
                ent.start_char,
                ent.end_char,
            )
        return spans


def _resolve_model_path(model_path: Path | None) -> Path:
    """Resolve the full spaCy model path.

    Args:
        model_path: Explicit model path, or None to use env var / default.

    Returns:
        Resolved full path to the model directory.
    """
    if model_path is not None:
        return model_path
    env = os.environ.get(LEGEND_MODEL_DIR_ENV)
    if env:
        return Path(env) / SPACY_MODEL
    return DEFAULT_MODEL_DIR / SPACY_MODEL
