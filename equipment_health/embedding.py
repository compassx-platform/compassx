"""Embed residual directions, then project them for a 2D plot."""
from __future__ import annotations

import numpy as np
import torch
from torch import nn
import torch.nn.functional as functional


class DeviationEmbedding(nn.Module):
    """Map a residual direction to a vector of embedding_dim, default 32."""

    def __init__(self, n_features: int, embedding_dim: int = 32):
        super().__init__()
        if not 16 <= embedding_dim <= 64:
            raise ValueError("embedding_dim must be from 16 to 64")
        self.net = nn.Sequential(
            nn.Linear(n_features, 128),
            nn.ReLU(),
            nn.Linear(128, embedding_dim),
        )
        self.deviation = nn.Linear(embedding_dim, n_features)

    def forward(self, direction: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        embedding = functional.normalize(self.net(direction), dim=-1)
        predicted = self.deviation(embedding)
        return embedding, predicted


def contrastive_loss(embedding: torch.Tensor, target: torch.Tensor, temperature: float = 0.1) -> torch.Tensor:
    """Pull embeddings together when their deviation targets point the same way."""
    anchor = functional.normalize(embedding, dim=-1)
    goal = functional.normalize(target, dim=-1)
    similarity = anchor @ anchor.T / temperature
    agreement = goal @ goal.T
    positive = agreement > 0.5
    positive.fill_diagonal_(False)
    available = positive.any(dim=1)
    if not bool(available.any()):
        return embedding.new_zeros(())
    logits = similarity - similarity.max(dim=1, keepdim=True).values.detach()
    exp_logits = torch.exp(logits) * (~torch.eye(anchor.shape[0], dtype=torch.bool, device=anchor.device))
    denominator = exp_logits.sum(dim=1).clamp_min(1e-8)
    numerator = (exp_logits * positive).sum(dim=1).clamp_min(1e-8)
    loss = -(numerator.log() - denominator.log())
    return loss[available].mean()


class EmbeddingModel:
    def __init__(self, n_features: int, embedding_dim: int = 32):
        self.model = DeviationEmbedding(n_features, embedding_dim=embedding_dim)
        self.mean = None
        self.components = None

    def fit(
        self,
        directions: np.ndarray,
        targets: np.ndarray,
        epochs: int = 40,
        batch_size: int = 64,
        lr: float = 1e-3,
        seed: int = 0,
    ) -> list[float]:
        torch.manual_seed(seed)
        inputs = torch.tensor(np.asarray(directions, dtype=np.float32))
        goals = torch.tensor(np.asarray(targets, dtype=np.float32))
        self.model.train()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        losses: list[float] = []
        count = inputs.shape[0]
        for _ in range(epochs):
            order = torch.randperm(count)
            total = 0.0
            seen = 0
            for start in range(0, count, batch_size):
                pick = order[start : start + batch_size]
                batch = inputs[pick]
                target = goals[pick]
                optimizer.zero_grad()
                embedding, predicted = self.model(batch)
                cosine = 1.0 - torch.nn.functional.cosine_similarity(predicted, target, dim=-1).mean()
                loss = cosine + contrastive_loss(embedding, target)
                loss.backward()
                optimizer.step()
                total += float(loss.detach()) * batch.shape[0]
                seen += batch.shape[0]
            losses.append(total / max(seen, 1))
        self.model.eval()
        encoded = self.encode(directions)
        self._fit_projection(encoded)
        return losses

    @torch.no_grad()
    def encode(self, directions: np.ndarray) -> np.ndarray:
        data = torch.tensor(np.asarray(directions, dtype=np.float32))
        self.model.eval()
        embedding, _predicted = self.model(data)
        return embedding.numpy()

    def _fit_projection(self, embeddings: np.ndarray) -> None:
        centered = embeddings - embeddings.mean(axis=0, keepdims=True)
        _unused, _values, vectors = np.linalg.svd(centered, full_matrices=False)
        take = min(2, vectors.shape[0])
        components = vectors[:take]
        if take == 1:
            components = np.vstack([components, np.zeros_like(components)])
        self.mean = embeddings.mean(axis=0)
        self.components = components

    def project(self, embeddings: np.ndarray) -> np.ndarray:
        if self.mean is None or self.components is None:
            raise RuntimeError("Fit the embedding before projecting.")
        return (np.asarray(embeddings) - self.mean) @ self.components.T
