__version__ = "0.1.0"

from legend.api import PseudonymContext
from legend.core.entities import Boundary, Detector, EntityType
from legend.detection.pipeline import DetectionPipeline
from legend.observability.emitter import EventEmitter
from legend.replacement.engine import ReplacementEngine
from legend.setup import ensure_models

__all__ = [
    "PseudonymContext",
    "EntityType",
    "Boundary",
    "Detector",
    "DetectionPipeline",
    "ReplacementEngine",
    "EventEmitter",
    "ensure_models",
]
