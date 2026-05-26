import logging
from importlib.resources import files
from pathlib import Path

import yara

from legend.constants import YARA_DEFAULT_CONFIDENCE
from legend.core.entities import Detector, EntityType
from legend.core.models import DetectedSpan
from legend.exceptions import DetectionError

logger = logging.getLogger(__name__)


class YARADetector:
    """Loads YARA rule files and scans text for pattern-based PII.

    Default rules are shipped with the package and loaded via
    importlib.resources. Additional custom rules may be merged in at
    construction time.
    """

    def __init__(self, custom_rules_dir: Path | None = None) -> None:
        """Initialize the detector by loading and compiling YARA rules.

        Args:
            custom_rules_dir: Optional path to a directory containing
                additional .yar files. Rules are merged with the defaults;
                custom rules take precedence for any rule name collision.

        Raises:
            DetectionError: If any rule file cannot be found or compiled.
        """
        try:
            filepaths: dict[str, str] = {}
            rules_pkg = files("legend.rules")
            for resource in rules_pkg.iterdir():
                name = resource.name
                if name.endswith(".yar"):
                    namespace = name[:-4]  # Consider using regex in future
                    # yara.compile requires a real filesystem path
                    filepaths[namespace] = str(resource)
            if custom_rules_dir is not None:
                for yar_file in sorted(custom_rules_dir.glob("*.yar")):
                    namespace = yar_file.stem
                    filepaths[namespace] = str(yar_file)
                    logger.debug("yara_detector: loaded custom rule %s", yar_file)
            self._rules: yara.Rules = yara.compile(filepaths=filepaths)
            logger.info("yara_detector: compiled %d rule namespaces", len(filepaths))
        except Exception as exc:
            logger.error("yara_detector: failed to compile rules: %s", exc)
            raise DetectionError(f"YARA rule compilation failed: {exc}") from exc

    def detect(self, text: str) -> list[DetectedSpan]:
        """Scan text and return all matching spans.

        Args:
            text: The text to scan.

        Returns:
            A list of DetectedSpan instances, one per match offset.

        Raises:
            DetectionError: If the YARA scan raises an exception.
        """
        try:
            matches: list[yara.Match] = self._rules.match(data=text)
        except Exception as exc:
            logger.error("yara_detector: scan failed: %s", exc)
            raise DetectionError(f"YARA scan failed: {exc}") from exc

        spans: list[DetectedSpan] = []
        for match in matches:
            entity_type_str: str = match.meta.get("entity_type", "")
            try:
                entity_type = EntityType(entity_type_str)
            except ValueError:
                logger.warning(
                    "yara_detector: unknown entity_type %r in rule %s, skipping",
                    entity_type_str,
                    match.rule,
                )
                continue
            raw_confidence = match.meta.get("confidence", YARA_DEFAULT_CONFIDENCE)
            confidence = float(raw_confidence)
            for string_match in match.strings:
                for instance in string_match.instances:
                    end = instance.offset + instance.matched_length
                    matched_text = text[instance.offset : end]
                    spans.append(
                        DetectedSpan(
                            text=matched_text,
                            start=instance.offset,
                            end=end,
                            entity_type=entity_type,
                            confidence=confidence,
                            detector=Detector.YARA,
                        )
                    )
                    logger.debug(
                        "yara_detector: hit entity_type=%s start=%d"
                        " end=%d confidence=%.2f",
                        entity_type,
                        instance.offset,
                        end,
                        confidence,
                    )
        return spans
