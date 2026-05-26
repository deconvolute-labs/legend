import logging
import uuid
from types import TracebackType
from typing import Literal, Self, overload

from legend.core.entities import Boundary
from legend.core.models import DetectedSpan
from legend.detection.pipeline import DetectionPipeline
from legend.entity_map.memory import InMemoryEntityMap
from legend.exceptions import SessionError
from legend.observability.emitter import EventEmitter
from legend.replacement.engine import ReplacementEngine
from legend.revert.pass_ import RevertPass

logger = logging.getLogger(__name__)


class PseudonymContext:
    """Async context manager providing the four pseudonymization boundaries.

    DetectionPipeline, ReplacementEngine, and EventEmitter are initialized
    once by the caller and passed in. Session-specific state (entity map and
    session_id) is created at __aenter__ and destroyed at __aexit__.

    Example:
        pipeline = DetectionPipeline()   # initialize once
        engine = ReplacementEngine()     # initialize once

        async with PseudonymContext(pipeline=pipeline, engine=engine) as ctx:
            sanitized = await ctx.sanitize_prompt(user_prompt)
            clean_response = await ctx.revert(agent_response)
    """

    def __init__(
        self,
        pipeline: DetectionPipeline,
        engine: ReplacementEngine,
        emitter: EventEmitter | None = None,
    ) -> None:
        """Store long-lived components. Session state is not created here.

        Args:
            pipeline: A pre-initialized DetectionPipeline.
            engine: A pre-initialized ReplacementEngine.
            emitter: Optional EventEmitter. A no-op instance is used if omitted.
        """
        self._pipeline = pipeline
        self._engine = engine
        self._emitter = emitter if emitter is not None else EventEmitter()
        self._revert_pass = RevertPass()
        self._entity_map: InMemoryEntityMap | None = None
        self._session_id: str | None = None

    async def __aenter__(self) -> Self:
        """Create a fresh entity map and session_id for this session.

        Returns:
            Self, for use as the context manager target.
        """
        self._entity_map = InMemoryEntityMap()
        self._session_id = str(uuid.uuid4())
        logger.info("session start session_id=%s", self._session_id)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Explicitly clear the entity map on all exit paths.

        This is a hard guarantee: no entity map state survives the async with
        block regardless of whether the block exited normally or via exception.
        """
        if self._entity_map is not None:
            await self._entity_map.clear()
        logger.info("session end session_id=%s", self._session_id)
        self._entity_map = None
        self._session_id = None

    def _require_session(self) -> tuple[InMemoryEntityMap, str]:
        """Return the active entity map and session_id, or raise SessionError.

        Returns:
            Tuple of (entity_map, session_id).

        Raises:
            SessionError: If called outside an active async with block.
        """
        if self._entity_map is None or self._session_id is None:
            raise SessionError(
                "PseudonymContext must be used as an async context manager"
            )
        return self._entity_map, self._session_id

    @overload
    async def sanitize_prompt(
        self, text: str, *, return_spans: Literal[False] = ...
    ) -> str: ...

    @overload
    async def sanitize_prompt(
        self, text: str, *, return_spans: Literal[True]
    ) -> tuple[str, list[DetectedSpan]]: ...

    async def sanitize_prompt(
        self,
        text: str,
        *,
        return_spans: bool = False,
    ) -> str | tuple[str, list[DetectedSpan]]:
        """Boundary A: detect and replace PII in the user prompt.

        Runs detection and replacement before the prompt enters the agent
        context. Initializes new entity map entries for all detected PII.

        Args:
            text: The raw user prompt containing real values.
            return_spans: If True, also return the list of detected spans.
                Each span exposes start, end, entity_type, confidence, and
                detector fields. Defaults to False.

        Returns:
            The sanitized prompt string when return_spans is False.
            A (sanitized_text, spans) tuple when return_spans is True.
        """
        entity_map, session_id = self._require_session()
        spans = await self._pipeline.detect(
            text, entity_map, session_id, Boundary.A, self._emitter
        )
        sanitized = await self._engine.replace(
            spans, text, entity_map, session_id, Boundary.A, self._emitter
        )
        if return_spans:
            return sanitized, spans
        return sanitized

    async def sanitize_tool_args(self, payload: str | dict) -> str | dict:  # type: ignore[type-arg]
        """Boundary B: detect and replace PII in tool call arguments.

        Defense-in-depth catch for false negatives from Boundary A or PII
        introduced via system prompts or injected context. Known pseudonyms
        in the entity map are recognized and left unchanged.

        Args:
            payload: A string or dict representing tool call arguments.
                Dict values are scanned recursively; structure is preserved.

        Returns:
            The payload with detected PII replaced by pseudonyms.
        """
        entity_map, session_id = self._require_session()
        return await self._sanitize_payload(payload, entity_map, session_id, Boundary.B)

    async def sanitize_tool_result(self, payload: str | dict) -> str | dict:  # type: ignore[type-arg]
        """Boundary C: detect and replace PII in tool results.

        Prevents PII fetched from external systems from entering the agent
        context. Known pseudonyms are recognized and left unchanged.

        Args:
            payload: A string or dict representing the tool result.
                Dict values are scanned recursively; structure is preserved.

        Returns:
            The payload with detected PII replaced by pseudonyms.
        """
        entity_map, session_id = self._require_session()
        return await self._sanitize_payload(payload, entity_map, session_id, Boundary.C)

    async def revert(self, text: str) -> str:
        """Boundary D: restore all pseudonyms in the agent response to real values.

        No detection runs at this boundary. The entity map is used exclusively
        for lookup.

        Args:
            text: The agent's final response containing pseudonyms.

        Returns:
            The response with all recognized pseudonyms replaced by real values.
        """
        entity_map, session_id = self._require_session()
        return await self._revert_pass.revert(
            text, entity_map, session_id, self._emitter
        )

    async def _sanitize_payload(
        self,
        payload: str | dict,  # type: ignore[type-arg]
        entity_map: InMemoryEntityMap,
        session_id: str,
        boundary: Boundary,
    ) -> str | dict:  # type: ignore[type-arg]
        """Run detection and replacement on a string or dict payload.

        For dict payloads, all string values are scanned and replaced in
        place. Structure and non-string values are preserved. Traversal
        is recursive to handle nested dicts.

        Args:
            payload: The string or dict to sanitize.
            entity_map: The session entity map.
            session_id: The current session identifier.
            boundary: The active boundary (B or C).

        Returns:
            The sanitized payload in the same type as the input.
        """
        if isinstance(payload, str):
            spans = await self._pipeline.detect(
                payload, entity_map, session_id, boundary, self._emitter
            )
            return await self._engine.replace(
                spans, payload, entity_map, session_id, boundary, self._emitter
            )

        if isinstance(payload, dict):
            result: dict = {}  # type: ignore[type-arg]
            for key, value in payload.items():
                if isinstance(value, str):
                    spans = await self._pipeline.detect(
                        value, entity_map, session_id, boundary, self._emitter
                    )
                    result[key] = await self._engine.replace(
                        spans, value, entity_map, session_id, boundary, self._emitter
                    )
                elif isinstance(value, dict):
                    result[key] = await self._sanitize_payload(
                        value, entity_map, session_id, boundary
                    )
                else:
                    result[key] = value
            return result

        return payload
