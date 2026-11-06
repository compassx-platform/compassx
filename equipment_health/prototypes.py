"""Known deviation prototypes, with a distance past which a point is unknown."""
from __future__ import annotations

import numpy as np


class PrototypeLibrary:
    def __init__(self):
        self.names: list[str] = []
        self.vectors: list[np.ndarray] = []

    def add(self, name: str, embedding: np.ndarray) -> None:
        self.names.append(name)
        self.vectors.append(np.asarray(embedding, dtype=np.float64))

    def match(self, embedding: np.ndarray, unknown_distance: float) -> tuple[str, float]:
        if not self.vectors:
            return "unknown", float("inf")
        stacked = np.stack(self.vectors)
        distances = np.linalg.norm(stacked - np.asarray(embedding, dtype=np.float64), axis=-1)
        index = int(distances.argmin())
        distance = float(distances[index])
        if distance > unknown_distance:
            return "unknown", distance
        return self.names[index], distance
