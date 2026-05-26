class LegendError(Exception):
    """Base class for all Legend library errors."""


class DetectionError(LegendError):
    """Raised when YARA or spaCy initialization or scanning fails."""


class EntityMapError(LegendError):
    """Raised on entity map write collision or corruption."""


class ReplacementError(LegendError):
    """Raised when a generator raises an unhandled exception."""


class RevertError(LegendError):
    """Raised when the entity map is empty or corrupted at revert time."""


class SessionError(LegendError):
    """Raised when a boundary method is called outside an active async with block."""
