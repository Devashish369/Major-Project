"""
services/estimator.py – Runtime task-size estimator (spec §8.6).

Loads ml/artifacts/estimator.joblib (TF-IDF + Ridge, trained offline) and
predicts story_points from a task's title + description.

Runtime conversion (spec §8.6):
    hours = story_points × HOURS_PER_STORY_POINT   (integer from settings)

The model is loaded once at startup into a module-level variable to avoid
re-reading disk on every request.

Design decisions (viva-ready):
  - Model predictions are clipped to [0.5, 40] story points – the same range
    used at training time.  This prevents absurd estimates for very unusual text.
  - We expose a simple function interface (`estimate`) so the router stays thin.
  - If the artifact file is missing (e.g. model not yet trained), we raise a
    RuntimeError with a clear message so the developer knows to run train_estimator.
"""

from pathlib import Path
from typing import Optional

import numpy as np

from app.config import settings

# ── Artefact path ─────────────────────────────────────────────────────────────

# services/estimator.py lives at  backend/app/services/estimator.py
# The model artefact lives at     backend/ml/artifacts/estimator.joblib
# Path: __file__ → services/ → app/ → backend/ → ml/artifacts/
_JOBLIB_PATH = Path(__file__).parent.parent.parent / "ml" / "artifacts" / "estimator.joblib"
_pipeline = None   # loaded lazily on first call


def _load_model():
    """Load the joblib pipeline once and cache it in the module."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    if not _JOBLIB_PATH.exists():
        raise RuntimeError(
            f"Estimator model not found at {_JOBLIB_PATH}. "
            "Run: python -m ml.train_estimator"
        )
    import joblib
    _pipeline = joblib.load(_JOBLIB_PATH)
    return _pipeline


# ── Public API ────────────────────────────────────────────────────────────────

def estimate(title: str, description: Optional[str] = None) -> dict:
    """
    Estimate story points and hours for a task.

    Args:
        title:       Task title (required).
        description: Task description (optional; improves accuracy).

    Returns:
        {
          "story_points": float,   # clipped to [0.5, 40]
          "hours":        float,   # story_points × HOURS_PER_STORY_POINT
          "model":        str,     # model identifier for transparency
        }
    """
    pipe = _load_model()

    text = f"{title} {description or ''}".strip()
    raw = float(pipe.predict([text])[0])
    sp = float(np.clip(raw, 0.5, 40.0))
    hours = round(sp * settings.HOURS_PER_STORY_POINT, 2)

    return {
        "story_points": round(sp, 2),
        "hours": hours,
        "model": "tfidf_ridge_v1",
    }
