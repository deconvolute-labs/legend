from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest import MonkeyPatch
from pytest_mock import MockerFixture

from legend.constants import DEFAULT_MODEL_DIR, LEGEND_MODEL_DIR_ENV, SPACY_MODEL
from legend.core.entities import Boundary, Detector, EntityType
from legend.core.models import DetectedSpan, PseudonymEvent
from legend.detection.pipeline import DetectionPipeline, _resolve
from legend.detection.spacy_detector import SpaCyDetector, _resolve_model_path
from legend.detection.yara_detector import YARADetector
from legend.entity_map.memory import InMemoryEntityMap
from legend.exceptions import DetectionError
from legend.observability.emitter import ENTITY_DETECTED, EventEmitter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _span(
    text: str,
    start: int,
    end: int,
    entity_type: EntityType,
    confidence: float,
    detector: Detector,
) -> DetectedSpan:
    return DetectedSpan(
        text=text,
        start=start,
        end=end,
        entity_type=entity_type,
        confidence=confidence,
        detector=detector,
    )


def _capture_emitter() -> tuple[EventEmitter, list[PseudonymEvent]]:
    events: list[PseudonymEvent] = []
    e = EventEmitter()
    e.subscribe(lambda ev: events.append(ev))
    return e, events


# ---------------------------------------------------------------------------
# YARADetector — uses real .yar files from importlib.resources
# ---------------------------------------------------------------------------


def test_yara_detector_init_compiles_default_rules() -> None:
    # Should not raise
    detector = YARADetector()
    assert detector is not None


def test_yara_detector_detect_ssn_returns_span_with_correct_entity_type() -> None:
    detector = YARADetector()
    spans = detector.detect("Her SSN is 123-45-6789 on file.")
    ssn_spans = [s for s in spans if s.entity_type == EntityType.US_SSN]
    assert len(ssn_spans) == 1
    assert ssn_spans[0].text == "123-45-6789"


def test_yara_detector_detect_email_returns_span() -> None:
    detector = YARADetector()
    spans = detector.detect("Contact user@example.com for help.")
    email_spans = [s for s in spans if s.entity_type == EntityType.EMAIL_ADDRESS]
    # YARA returns all (overlapping) matches; assert the full address is among them.
    assert len(email_spans) >= 1
    texts = {s.text for s in email_spans}
    assert "user@example.com" in texts


def test_yara_detector_detect_ip_address_returns_span() -> None:
    detector = YARADetector()
    spans = detector.detect("Server at 192.168.0.1 is down.")
    ip_spans = [s for s in spans if s.entity_type == EntityType.IP_ADDRESS]
    assert len(ip_spans) == 1
    assert "192.168.0.1" in ip_spans[0].text


def test_yara_detector_detect_no_match_returns_empty_list() -> None:
    detector = YARADetector()
    spans = detector.detect("No PII here, just ordinary text.")
    assert spans == []


def test_yara_detector_detect_span_start_end_offsets_correct() -> None:
    detector = YARADetector()
    text = "SSN: 123-45-6789 end"
    spans = detector.detect(text)
    ssn_spans = [s for s in spans if s.entity_type == EntityType.US_SSN]
    assert len(ssn_spans) == 1
    span = ssn_spans[0]
    assert text[span.start : span.end] == "123-45-6789"


def test_yara_detector_detect_confidence_from_rule_metadata() -> None:
    detector = YARADetector()
    spans = detector.detect("user@example.com")
    email_spans = [s for s in spans if s.entity_type == EntityType.EMAIL_ADDRESS]
    assert len(email_spans) >= 1
    # All overlapping matches share the same rule metadata confidence
    assert all(s.confidence == pytest.approx(0.9) for s in email_spans)


def test_yara_detector_detect_ssn_confidence_from_rule_metadata() -> None:
    detector = YARADetector()
    spans = detector.detect("123-45-6789")
    ssn_spans = [s for s in spans if s.entity_type == EntityType.US_SSN]
    assert len(ssn_spans) == 1
    assert ssn_spans[0].confidence == pytest.approx(0.85)


def test_yara_detector_detect_unknown_entity_type_in_meta_skips_span(
    tmp_path: Path,
) -> None:
    bad_rule = tmp_path / "bad_rule.yar"
    bad_rule.write_text(
        "rule bad_rule {\n"
        "    meta:\n"
        '        entity_type = "NOT_A_REAL_ENTITY"\n'
        '        confidence = "0.9"\n'
        "    strings:\n"
        '        $tok = "UNIQUETOKEN99"\n'
        "    condition:\n"
        "        $tok\n"
        "}\n"
    )
    detector = YARADetector(custom_rules_dir=tmp_path)
    spans = detector.detect("UNIQUETOKEN99")
    assert spans == []


def test_yara_detector_custom_rules_dir_adds_extra_rules(tmp_path: Path) -> None:
    custom_rule = tmp_path / "custom.yar"
    custom_rule.write_text(
        "rule custom_ssn {\n"
        "    meta:\n"
        '        entity_type = "EMAIL_ADDRESS"\n'
        '        confidence = "0.95"\n'
        "    strings:\n"
        '        $tok = "SPECIALTOKEN123"\n'
        "    condition:\n"
        "        $tok\n"
        "}\n"
    )
    detector = YARADetector(custom_rules_dir=tmp_path)
    spans = detector.detect("SPECIALTOKEN123")
    assert len(spans) == 1
    assert spans[0].entity_type == EntityType.EMAIL_ADDRESS
    assert spans[0].confidence == pytest.approx(0.95)


def test_yara_detector_detect_raises_detection_error_on_scan_failure() -> None:
    detector = YARADetector()
    detector._rules = MagicMock()
    detector._rules.match.side_effect = Exception("scan exploded")
    with pytest.raises(DetectionError, match="scan exploded"):
        detector.detect("some text")


# ---------------------------------------------------------------------------
# SpaCyDetector — mocked spacy.load
# ---------------------------------------------------------------------------


def _make_mock_ent(
    mocker: MockerFixture, label: str, text: str, start: int, end: int
) -> Any:
    ent = mocker.MagicMock()
    ent.label_ = label
    ent.text = text
    ent.start_char = start
    ent.end_char = end
    return ent


def _make_spacy_detector(
    mocker: MockerFixture, tmp_path: Path, ents: list[Any]
) -> SpaCyDetector:
    mock_doc = mocker.MagicMock()
    mock_doc.ents = ents
    mock_nlp = mocker.MagicMock()
    mock_nlp.return_value = mock_doc
    mocker.patch("legend.detection.spacy_detector.spacy.load", return_value=mock_nlp)
    model_path = tmp_path / SPACY_MODEL
    model_path.mkdir()
    return SpaCyDetector(model_path=model_path)


def test_spacy_detector_person_label_maps_correctly(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    ent = _make_mock_ent(mocker, "PERSON", "Alice", 0, 5)
    detector = _make_spacy_detector(mocker, tmp_path, [ent])
    spans = detector.detect("Alice lives here")
    assert len(spans) == 1
    assert spans[0].entity_type == EntityType.PERSON
    assert spans[0].detector == Detector.SPACY


def test_spacy_detector_per_label_maps_to_person(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    ent = _make_mock_ent(mocker, "PER", "Bob", 0, 3)
    detector = _make_spacy_detector(mocker, tmp_path, [ent])
    spans = detector.detect("Bob is here")
    assert spans[0].entity_type == EntityType.PERSON


def test_spacy_detector_loc_label_maps_to_location(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    ent = _make_mock_ent(mocker, "LOC", "Paris", 0, 5)
    detector = _make_spacy_detector(mocker, tmp_path, [ent])
    spans = detector.detect("Paris is beautiful")
    assert spans[0].entity_type == EntityType.LOCATION


def test_spacy_detector_gpe_label_maps_to_location(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    ent = _make_mock_ent(mocker, "GPE", "France", 0, 6)
    detector = _make_spacy_detector(mocker, tmp_path, [ent])
    spans = detector.detect("France is beautiful")
    assert spans[0].entity_type == EntityType.LOCATION


def test_spacy_detector_org_label_maps_to_organization(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    ent = _make_mock_ent(mocker, "ORG", "Acme Corp", 0, 9)
    detector = _make_spacy_detector(mocker, tmp_path, [ent])
    spans = detector.detect("Acme Corp is big")
    assert spans[0].entity_type == EntityType.ORGANIZATION


def test_spacy_detector_date_label_maps_to_date_time(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    ent = _make_mock_ent(mocker, "DATE", "Monday", 0, 6)
    detector = _make_spacy_detector(mocker, tmp_path, [ent])
    spans = detector.detect("Monday morning")
    assert spans[0].entity_type == EntityType.DATE_TIME


def test_spacy_detector_norp_label_maps_to_nrp(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    ent = _make_mock_ent(mocker, "NORP", "Dutch", 0, 5)
    detector = _make_spacy_detector(mocker, tmp_path, [ent])
    spans = detector.detect("Dutch people")
    assert spans[0].entity_type == EntityType.NRP


def test_spacy_detector_unmapped_label_skipped(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    ent = _make_mock_ent(mocker, "CARDINAL", "five", 0, 4)
    detector = _make_spacy_detector(mocker, tmp_path, [ent])
    spans = detector.detect("five apples")
    assert spans == []


def test_spacy_detector_detect_nlp_raises_raises_detection_error(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    mock_nlp = mocker.MagicMock()
    mock_nlp.side_effect = Exception("pipeline failed")
    mocker.patch("legend.detection.spacy_detector.spacy.load", return_value=mock_nlp)
    model_path = tmp_path / SPACY_MODEL
    model_path.mkdir()
    detector = SpaCyDetector(model_path=model_path)
    with pytest.raises(DetectionError, match="pipeline failed"):
        detector.detect("some text")


def test_spacy_detector_detect_returns_correct_offsets(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    ent = _make_mock_ent(mocker, "PERSON", "John Smith", 5, 15)
    detector = _make_spacy_detector(mocker, tmp_path, [ent])
    spans = detector.detect("Call John Smith now.")
    assert len(spans) == 1
    assert spans[0].start == 5
    assert spans[0].end == 15
    assert spans[0].text == "John Smith"


# ---------------------------------------------------------------------------
# _resolve_model_path
# ---------------------------------------------------------------------------


def test_resolve_model_path_explicit_path_returned_as_is() -> None:
    explicit = Path("/custom/path/model")
    result = _resolve_model_path(explicit)
    assert result == explicit


def test_resolve_model_path_env_var_used_when_no_explicit(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv(LEGEND_MODEL_DIR_ENV, "/env/models")
    result = _resolve_model_path(None)
    assert result == Path("/env/models") / SPACY_MODEL


def test_resolve_model_path_default_when_neither_set(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv(LEGEND_MODEL_DIR_ENV, raising=False)
    result = _resolve_model_path(None)
    assert result == DEFAULT_MODEL_DIR / SPACY_MODEL


# ---------------------------------------------------------------------------
# _resolve (pipeline conflict resolution)
# ---------------------------------------------------------------------------


def test_resolve_empty_input_returns_empty() -> None:
    assert _resolve([]) == []


def test_resolve_non_overlapping_spans_all_kept() -> None:
    spans = [
        _span("foo", 0, 3, EntityType.PERSON, 0.9, Detector.YARA),
        _span("bar", 10, 13, EntityType.EMAIL_ADDRESS, 0.85, Detector.YARA),
    ]
    result = _resolve(spans)
    assert len(result) == 2


def test_resolve_same_detector_overlap_keeps_longest() -> None:
    longer = _span("John Smith", 0, 10, EntityType.PERSON, 0.8, Detector.YARA)
    shorter = _span("John", 0, 4, EntityType.PERSON, 0.9, Detector.YARA)
    result = _resolve([longer, shorter])
    assert len(result) == 1
    assert result[0].text == "John Smith"


def test_resolve_same_detector_overlap_equal_length_keeps_existing() -> None:
    s1 = _span("John", 0, 4, EntityType.PERSON, 0.9, Detector.YARA)
    s2 = _span("John", 0, 4, EntityType.PERSON, 0.7, Detector.YARA)
    result = _resolve([s1, s2])
    assert len(result) == 1


def test_resolve_cross_detector_yara_wins_when_adjusted_score_higher() -> None:
    # YARA 0.8 + boost 0.1 = 0.9 > spaCy 0.85 → YARA wins
    yara_span = _span("Alice", 0, 5, EntityType.PERSON, 0.8, Detector.YARA)
    spacy_span = _span("Alice", 0, 5, EntityType.PERSON, 0.85, Detector.SPACY)
    result = _resolve([yara_span, spacy_span])
    assert len(result) == 1
    assert result[0].detector == Detector.YARA


def test_resolve_cross_detector_spacy_wins_when_score_higher_than_adjusted_yara() -> (
    None
):
    # YARA 0.7 + boost 0.1 = 0.8 < spaCy 0.9 → spaCy wins
    yara_span = _span("Alice", 0, 5, EntityType.PERSON, 0.7, Detector.YARA)
    spacy_span = _span("Alice", 0, 5, EntityType.PERSON, 0.9, Detector.SPACY)
    result = _resolve([yara_span, spacy_span])
    assert len(result) == 1
    assert result[0].detector == Detector.SPACY


def test_resolve_output_sorted_by_start_position() -> None:
    s1 = _span("foo", 20, 23, EntityType.PERSON, 0.9, Detector.YARA)
    s2 = _span("bar", 0, 3, EntityType.EMAIL_ADDRESS, 0.9, Detector.YARA)
    s3 = _span("baz", 10, 13, EntityType.US_SSN, 0.9, Detector.YARA)
    result = _resolve([s1, s2, s3])
    assert [r.start for r in result] == [0, 10, 20]


# ---------------------------------------------------------------------------
# DetectionPipeline.detect — both detectors mocked
# ---------------------------------------------------------------------------


def _make_pipeline(
    mocker: MockerFixture,
    yara_spans: list[DetectedSpan] | None = None,
    spacy_spans: list[DetectedSpan] | None = None,
    entities: list[str] | None = None,
) -> DetectionPipeline:
    mock_yara = mocker.MagicMock(spec=YARADetector)
    mock_yara.detect.return_value = yara_spans or []
    mock_spacy = mocker.MagicMock(spec=SpaCyDetector)
    mock_spacy.detect.return_value = spacy_spans or []
    mocker.patch("legend.detection.pipeline.YARADetector", return_value=mock_yara)
    mocker.patch("legend.detection.pipeline.SpaCyDetector", return_value=mock_spacy)
    return DetectionPipeline(entities=entities)


async def test_pipeline_detect_merges_yara_and_spacy_spans(
    mocker: MockerFixture,
) -> None:
    yara_span = _span(
        "user@example.com", 0, 16, EntityType.EMAIL_ADDRESS, 0.9, Detector.YARA
    )
    spacy_span = _span("New York", 20, 28, EntityType.LOCATION, 0.85, Detector.SPACY)
    pipeline = _make_pipeline(mocker, yara_spans=[yara_span], spacy_spans=[spacy_span])
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()
    spans = await pipeline.detect(
        "user@example.com Hi from New York", em, "sid", Boundary.A, emitter
    )
    assert len(spans) == 2
    entity_types = {s.entity_type for s in spans}
    assert EntityType.EMAIL_ADDRESS in entity_types
    assert EntityType.LOCATION in entity_types


async def test_pipeline_detect_filters_by_active_entity_type(
    mocker: MockerFixture,
) -> None:
    yara_span = _span(
        "user@example.com", 0, 16, EntityType.EMAIL_ADDRESS, 0.9, Detector.YARA
    )
    spacy_span = _span("Alice", 20, 25, EntityType.PERSON, 0.85, Detector.SPACY)
    pipeline = _make_pipeline(
        mocker,
        yara_spans=[yara_span],
        spacy_spans=[spacy_span],
        entities=["EMAIL_ADDRESS"],
    )
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()
    spans = await pipeline.detect(
        "user@example.com Hi from Alice", em, "sid", Boundary.A, emitter
    )
    assert len(spans) == 1
    assert spans[0].entity_type == EntityType.EMAIL_ADDRESS


async def test_pipeline_detect_unknown_entity_type_in_filter_logged_warning(
    mocker: MockerFixture,
) -> None:
    pipeline = _make_pipeline(mocker, entities=["UNKNOWN_ENTITY"])
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()
    # Should not raise; the active set will just be empty
    spans = await pipeline.detect("some text", em, "sid", Boundary.A, emitter)
    assert spans == []


async def test_pipeline_detect_emits_entity_detected_event_per_span(
    mocker: MockerFixture,
) -> None:
    yara_span = _span(
        "user@example.com", 0, 16, EntityType.EMAIL_ADDRESS, 0.9, Detector.YARA
    )
    spacy_span = _span("Alice", 20, 25, EntityType.PERSON, 0.85, Detector.SPACY)
    pipeline = _make_pipeline(mocker, yara_spans=[yara_span], spacy_spans=[spacy_span])
    em = InMemoryEntityMap()
    emitter, events = _capture_emitter()
    await pipeline.detect(
        "user@example.com Hi from Alice", em, "sid", Boundary.A, emitter
    )
    detected = [e for e in events if e.event_type == ENTITY_DETECTED]
    assert len(detected) == 2


async def test_pipeline_detect_empty_text_returns_empty(
    mocker: MockerFixture,
) -> None:
    pipeline = _make_pipeline(mocker)
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()
    spans = await pipeline.detect("", em, "sid", Boundary.A, emitter)
    assert spans == []
