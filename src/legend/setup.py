import logging
import os
import shutil
from pathlib import Path

from legend.constants import DEFAULT_MODEL_DIR, LEGEND_MODEL_DIR_ENV, SPACY_MODEL
from legend.exceptions import DetectionError

logger = logging.getLogger(__name__)


def ensure_models(path: Path | None = None) -> None:
    """Download the spaCy model if not present at the resolved path.

    Safe to call multiple times; no-op if the model is already present.

    Args:
        path: Target directory for the model. If None, resolves via
            LEGEND_MODEL_PATH environment variable, then DEFAULT_MODEL_DIR.

    Raises:
        DetectionError: If the model download or staging fails.
    """
    resolved_dir = _resolve_model_dir(path)
    model_path = resolved_dir / SPACY_MODEL

    if model_path.exists():
        return

    resolved_dir.mkdir(parents=True, exist_ok=True)
    logger.info("setup: staging spaCy model to %s", model_path)

    try:
        import spacy.util

        pkg_path = spacy.util.get_package_path(SPACY_MODEL)
        model_dir = _find_model_dir(pkg_path)
        shutil.copytree(str(model_dir), str(model_path))
    except Exception as exc:
        logger.error("setup: failed to stage model to %s: %s", model_path, exc)
        raise DetectionError(
            f"Failed to stage spaCy model to {model_path}: {exc}"
        ) from exc

    logger.info("setup: spaCy model staged successfully to %s", model_path)


def _resolve_model_dir(path: Path | None) -> Path:
    """Resolve the base directory for the spaCy model.

    Args:
        path: Explicit base directory, or None to use env var / default.

    Returns:
        Resolved base directory Path.
    """
    if path is not None:
        return path
    env = os.environ.get(LEGEND_MODEL_DIR_ENV)
    if env:
        return Path(env)
    return DEFAULT_MODEL_DIR


def _find_model_dir(pkg_path: Path) -> Path:
    """Locate the loadable spaCy model directory containing config.cfg.

    spaCy packages nest the actual model one level inside the package root.
    config.cfg is the authoritative indicator of a loadable model directory;
    meta.json also exists at the package root and cannot be used alone.

    Args:
        pkg_path: Path returned by spacy.util.get_package_path().

    Returns:
        Path to the directory with config.cfg at its root.

    Raises:
        DetectionError: If no directory containing config.cfg is found.
    """
    if (pkg_path / "config.cfg").exists():
        return pkg_path
    candidates = [
        d for d in pkg_path.iterdir() if d.is_dir() and (d / "config.cfg").exists()
    ]
    if not candidates:
        raise DetectionError(
            f"Could not locate model directory with config.cfg inside {pkg_path}"
        )
    return candidates[0]
