import re
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from legend.api import PseudonymContext
from legend.core.entities import Boundary, Detector, EntityType
from legend.core.models import DetectedSpan
from legend.entity_map.base import EntityMapBase
from legend.exceptions import SessionError
from legend.observability.emitter import EventEmitter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_span(
    text: str,
    start: int,
    end: int,
    entity_type: EntityType = EntityType.PERSON,
    confidence: float = 0.9,
    detector: Detector = Detector.YARA,
) -> DetectedSpan:
    return DetectedSpan(
        text=text,
        start=start,
        end=end,
        entity_type=entity_type,
        confidence=confidence,
        detector=detector,
    )


def _mock_components(
    mocker: MockerFixture,
    detected_spans: list[DetectedSpan] | None = None,
    replaced_text: str = "sanitized",
) -> tuple[MagicMock, MagicMock]:
    mock_pipeline = MagicMock()
    mock_pipeline.detect = AsyncMock(return_value=detected_spans or [])
    mock_engine = MagicMock()
    mock_engine.replace = AsyncMock(return_value=replaced_text)
    mocker.patch("legend.api.RevertPass")
    return mock_pipeline, mock_engine


# ---------------------------------------------------------------------------
# Session guard — methods called outside async with
# ---------------------------------------------------------------------------


async def test_sanitize_prompt_outside_context_raises_session_error(
    mocker: MockerFixture,
) -> None:
    mock_pipeline, mock_engine = _mock_components(mocker)
    ctx = PseudonymContext(pipeline=mock_pipeline, engine=mock_engine)
    with pytest.raises(SessionError):
        await ctx.sanitize_prompt("text")


async def test_sanitize_tool_args_outside_context_raises_session_error(
    mocker: MockerFixture,
) -> None:
    mock_pipeline, mock_engine = _mock_components(mocker)
    ctx = PseudonymContext(pipeline=mock_pipeline, engine=mock_engine)
    with pytest.raises(SessionError):
        await ctx.sanitize_tool_args("text")


async def test_sanitize_tool_result_outside_context_raises_session_error(
    mocker: MockerFixture,
) -> None:
    mock_pipeline, mock_engine = _mock_components(mocker)
    ctx = PseudonymContext(pipeline=mock_pipeline, engine=mock_engine)
    with pytest.raises(SessionError):
        await ctx.sanitize_tool_result("text")


async def test_revert_outside_context_raises_session_error(
    mocker: MockerFixture,
) -> None:
    mock_pipeline, mock_engine = _mock_components(mocker)
    ctx = PseudonymContext(pipeline=mock_pipeline, engine=mock_engine)
    with pytest.raises(SessionError):
        await ctx.revert("text")


# ---------------------------------------------------------------------------
# sanitize_prompt
# ---------------------------------------------------------------------------


async def test_sanitize_prompt_returns_str_by_default(mocker: MockerFixture) -> None:
    mock_pipeline, mock_engine = _mock_components(mocker, replaced_text="clean text")
    async with PseudonymContext(pipeline=mock_pipeline, engine=mock_engine) as ctx:
        result = await ctx.sanitize_prompt("raw text")
    assert isinstance(result, str)
    assert result == "clean text"


async def test_sanitize_prompt_return_spans_true_returns_tuple(
    mocker: MockerFixture,
) -> None:
    span = _make_span("Alice", 0, 5)
    mock_pipeline, mock_engine = _mock_components(mocker, detected_spans=[span])
    async with PseudonymContext(pipeline=mock_pipeline, engine=mock_engine) as ctx:
        result = await ctx.sanitize_prompt("Alice is here", return_spans=True)
    assert isinstance(result, tuple)
    sanitized, spans = result
    assert isinstance(sanitized, str)
    assert isinstance(spans, list)


async def test_sanitize_prompt_spans_match_pipeline_output(
    mocker: MockerFixture,
) -> None:
    span = _make_span("Alice", 0, 5)
    mock_pipeline, mock_engine = _mock_components(mocker, detected_spans=[span])
    async with PseudonymContext(pipeline=mock_pipeline, engine=mock_engine) as ctx:
        _, spans = await ctx.sanitize_prompt("Alice is here", return_spans=True)
    assert len(spans) == 1
    assert spans[0].text == "Alice"


# ---------------------------------------------------------------------------
# sanitize_tool_args
# ---------------------------------------------------------------------------


async def test_sanitize_tool_args_string_payload_calls_pipeline_and_engine(
    mocker: MockerFixture,
) -> None:
    mock_pipeline, mock_engine = _mock_components(mocker, replaced_text="clean")
    async with PseudonymContext(pipeline=mock_pipeline, engine=mock_engine) as ctx:
        result = await ctx.sanitize_tool_args("raw string")
    assert result == "clean"
    mock_pipeline.detect.assert_called_once()
    mock_engine.replace.assert_called_once()


async def test_sanitize_tool_args_dict_payload_sanitizes_string_values(
    mocker: MockerFixture,
) -> None:
    call_log: list[str] = []

    async def fake_replace(
        spans: list[DetectedSpan],
        text: str,
        em: EntityMapBase,
        sid: str,
        b: Boundary,
        emitter: EventEmitter,
    ) -> str:
        call_log.append(text)
        return f"[{text}]"

    mock_pipeline = MagicMock()
    mock_pipeline.detect = AsyncMock(return_value=[])
    mock_engine = MagicMock()
    mock_engine.replace = fake_replace
    mocker.patch("legend.api.RevertPass")

    async with PseudonymContext(pipeline=mock_pipeline, engine=mock_engine) as ctx:
        result = await ctx.sanitize_tool_args({"name": "Alice", "city": "London"})

    assert isinstance(result, dict)
    assert result == {"name": "[Alice]", "city": "[London]"}


async def test_sanitize_tool_args_dict_preserves_non_string_values(
    mocker: MockerFixture,
) -> None:
    mock_pipeline, mock_engine = _mock_components(mocker)
    mock_engine.replace = AsyncMock(
        side_effect=lambda spans, text, em, sid, b, em2: text
    )
    async with PseudonymContext(pipeline=mock_pipeline, engine=mock_engine) as ctx:
        result = await ctx.sanitize_tool_args(
            {"name": "Alice", "count": 42, "flag": True}
        )
    assert isinstance(result, dict)
    assert result["count"] == 42
    assert result["flag"] is True


async def test_sanitize_tool_args_nested_dict_sanitizes_recursively(
    mocker: MockerFixture,
) -> None:
    call_log: list[str] = []

    async def fake_replace(
        spans: list[DetectedSpan],
        text: str,
        em: EntityMapBase,
        sid: str,
        b: Boundary,
        emitter: EventEmitter,
    ) -> str:
        call_log.append(text)
        return f"[{text}]"

    mock_pipeline = MagicMock()
    mock_pipeline.detect = AsyncMock(return_value=[])
    mock_engine = MagicMock()
    mock_engine.replace = fake_replace
    mocker.patch("legend.api.RevertPass")

    payload = {"outer": "A", "nested": {"inner": "B"}, "num": 99}

    async with PseudonymContext(pipeline=mock_pipeline, engine=mock_engine) as ctx:
        result = await ctx.sanitize_tool_args(payload)

    assert isinstance(result, dict)
    assert result["outer"] == "[A]"
    assert isinstance(result["nested"], dict)
    assert result["nested"]["inner"] == "[B]"
    assert result["num"] == 99
    assert "A" in call_log
    assert "B" in call_log


# ---------------------------------------------------------------------------
# sanitize_tool_result
# ---------------------------------------------------------------------------


async def test_sanitize_tool_result_string_payload(mocker: MockerFixture) -> None:
    mock_pipeline, mock_engine = _mock_components(mocker, replaced_text="clean result")
    async with PseudonymContext(pipeline=mock_pipeline, engine=mock_engine) as ctx:
        result = await ctx.sanitize_tool_result("raw result")
    assert result == "clean result"


async def test_sanitize_tool_result_dict_payload(mocker: MockerFixture) -> None:
    call_log: list[str] = []

    async def fake_replace(
        spans: list[DetectedSpan],
        text: str,
        em: EntityMapBase,
        sid: str,
        b: Boundary,
        emitter: EventEmitter,
    ) -> str:
        call_log.append(text)
        return f"[{text}]"

    mock_pipeline = MagicMock()
    mock_pipeline.detect = AsyncMock(return_value=[])
    mock_engine = MagicMock()
    mock_engine.replace = fake_replace
    mocker.patch("legend.api.RevertPass")

    async with PseudonymContext(pipeline=mock_pipeline, engine=mock_engine) as ctx:
        result = await ctx.sanitize_tool_result({"value": "secret"})

    assert isinstance(result, dict)
    assert result == {"value": "[secret]"}


# ---------------------------------------------------------------------------
# revert
# ---------------------------------------------------------------------------


async def test_revert_delegates_to_revert_pass(mocker: MockerFixture) -> None:
    mock_pipeline = MagicMock()
    mock_pipeline.detect = AsyncMock(return_value=[])
    mock_engine = MagicMock()
    mock_engine.replace = AsyncMock(return_value="")

    mock_revert_cls = mocker.patch("legend.api.RevertPass")
    mock_revert_instance = mock_revert_cls.return_value
    mock_revert_instance.revert = AsyncMock(return_value="real text restored")

    async with PseudonymContext(pipeline=mock_pipeline, engine=mock_engine) as ctx:
        result = await ctx.revert("fake text here")

    assert result == "real text restored"
    mock_revert_instance.revert.assert_called_once()


# ---------------------------------------------------------------------------
# Session lifecycle — entity map and session_id
# ---------------------------------------------------------------------------


async def test_entity_map_cleared_on_normal_exit(mocker: MockerFixture) -> None:
    mock_pipeline, mock_engine = _mock_components(mocker)
    ctx = PseudonymContext(pipeline=mock_pipeline, engine=mock_engine)
    async with ctx:
        assert ctx._entity_map is not None
    assert ctx._entity_map is None


async def test_entity_map_cleared_on_exception_exit(mocker: MockerFixture) -> None:
    mock_pipeline, mock_engine = _mock_components(mocker)
    ctx = PseudonymContext(pipeline=mock_pipeline, engine=mock_engine)
    try:
        async with ctx:
            raise ValueError("boom")
    except ValueError:
        pass
    assert ctx._entity_map is None


async def test_session_id_is_valid_uuid_format(mocker: MockerFixture) -> None:
    mock_pipeline, mock_engine = _mock_components(mocker)
    async with PseudonymContext(pipeline=mock_pipeline, engine=mock_engine) as ctx:
        assert ctx._session_id is not None
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            ctx._session_id,
        )


async def test_session_id_is_none_after_exit(mocker: MockerFixture) -> None:
    mock_pipeline, mock_engine = _mock_components(mocker)
    ctx = PseudonymContext(pipeline=mock_pipeline, engine=mock_engine)
    async with ctx:
        pass
    assert ctx._session_id is None


# ---------------------------------------------------------------------------
# Emitter wiring
# ---------------------------------------------------------------------------


def test_default_emitter_created_when_none_passed(mocker: MockerFixture) -> None:
    mocker.patch("legend.api.RevertPass")
    mock_pipeline = MagicMock()
    mock_engine = MagicMock()
    ctx = PseudonymContext(pipeline=mock_pipeline, engine=mock_engine)
    assert isinstance(ctx._emitter, EventEmitter)


def test_custom_emitter_passed_through(mocker: MockerFixture) -> None:
    mocker.patch("legend.api.RevertPass")
    mock_pipeline = MagicMock()
    mock_engine = MagicMock()
    custom_emitter = EventEmitter()
    ctx = PseudonymContext(
        pipeline=mock_pipeline, engine=mock_engine, emitter=custom_emitter
    )
    assert ctx._emitter is custom_emitter


# ---------------------------------------------------------------------------
# Boundary routing (B vs C use same _sanitize_payload, different boundary arg)
# ---------------------------------------------------------------------------


async def test_sanitize_tool_args_passes_boundary_b(mocker: MockerFixture) -> None:
    captured: list[Boundary] = []

    async def fake_detect(
        text: str,
        em: EntityMapBase,
        sid: str,
        boundary: Boundary,
        emitter: EventEmitter,
    ) -> list[DetectedSpan]:
        captured.append(boundary)
        return []

    mock_pipeline = MagicMock()
    mock_pipeline.detect = fake_detect
    mock_engine = MagicMock()
    mock_engine.replace = AsyncMock(return_value="x")
    mocker.patch("legend.api.RevertPass")

    async with PseudonymContext(pipeline=mock_pipeline, engine=mock_engine) as ctx:
        await ctx.sanitize_tool_args("some text")

    assert Boundary.B in captured


async def test_sanitize_tool_result_passes_boundary_c(mocker: MockerFixture) -> None:
    captured: list[Boundary] = []

    async def fake_detect(
        text: str,
        em: EntityMapBase,
        sid: str,
        boundary: Boundary,
        emitter: EventEmitter,
    ) -> list[DetectedSpan]:
        captured.append(boundary)
        return []

    mock_pipeline = MagicMock()
    mock_pipeline.detect = fake_detect
    mock_engine = MagicMock()
    mock_engine.replace = AsyncMock(return_value="x")
    mocker.patch("legend.api.RevertPass")

    async with PseudonymContext(pipeline=mock_pipeline, engine=mock_engine) as ctx:
        await ctx.sanitize_tool_result("some text")

    assert Boundary.C in captured
