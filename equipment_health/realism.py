"""Compare real fault residuals with the synthetic deviations."""
from __future__ import annotations

import numpy as np


def _mean_nearest(query: np.ndarray, gallery: np.ndarray) -> float:
    query = np.asarray(query, dtype=np.float64)
    gallery = np.asarray(gallery, dtype=np.float64)
    distances = np.linalg.norm(query[:, None, :] - gallery[None, :, :], axis=-1)
    return float(distances.min(axis=1).mean())


def realism_gap(real_directions: np.ndarray, synthetic_directions: np.ndarray, holdout: int) -> dict[str, float]:
    """Ratio above 1 means real faults sit outside the synthetic deviations.

    holdout synthetic samples are the control: they should be close to the
    remaining synthetic set. Real fault directions are compared to that same set.
    """
    synthetic = np.asarray(synthetic_directions, dtype=np.float64)
    if holdout < 1 or holdout >= len(synthetic):
        raise ValueError("holdout must leave at least one synthetic sample in the gallery")
    gallery = synthetic[:-holdout]
    held = synthetic[-holdout:]
    real_distance = _mean_nearest(real_directions, gallery)
    holdout_distance = _mean_nearest(held, gallery)
    return {
        "real_to_synthetic": real_distance,
        "holdout_to_synthetic": holdout_distance,
        "ratio": real_distance / max(holdout_distance, 1e-8),
    }
