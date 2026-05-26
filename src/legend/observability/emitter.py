import logging
from collections.abc import Callable

from legend.core.models import PseudonymEvent

logger = logging.getLogger(__name__)

ENTITY_DETECTED: str = "entity_detected"
PSEUDONYM_CREATED: str = "pseudonym_created"
ENTITY_MAP_HIT: str = "entity_map_hit"
REVERT_COMPLETE: str = "revert_complete"


class EventEmitter:
    """Dispatches PseudonymEvent instances to registered subscriber callbacks.

    No-op by default. Subscribers register callables that receive
    PseudonymEvent instances. Real values never appear in any event payload.
    """

    def __init__(self) -> None:
        self._subscribers: list[Callable[[PseudonymEvent], None]] = []

    def subscribe(self, callback: Callable[[PseudonymEvent], None]) -> None:
        """Register a callback to receive all future events.

        Args:
            callback: A callable that accepts a PseudonymEvent.
        """
        self._subscribers.append(callback)

    def emit(self, event: PseudonymEvent) -> None:
        """Dispatch an event to all registered subscribers.

        Errors raised by individual subscribers are logged and suppressed so
        one bad subscriber cannot disrupt the pipeline.

        Args:
            event: The event to dispatch.
        """
        for callback in self._subscribers:
            try:
                callback(event)
            except Exception:
                logger.exception("EventEmitter subscriber raised an exception")
