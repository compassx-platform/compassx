"""Window autoencoder trained only on normal equipment data."""
from __future__ import annotations

import numpy as np
import torch
from torch import nn


class WindowAutoencoder(nn.Module):
    """Reconstruct a (window, features) slice from a small latent vector."""

    def __init__(self, n_features: int, window: int, latent: int = 16, hidden: int = 64):
        super().__init__()
        flat = window * n_features
        self.window = window
        self.n_features = n_features
        self.encoder = nn.Sequential(nn.Linear(flat, hidden), nn.ReLU(), nn.Linear(hidden, latent))
        self.decoder = nn.Sequential(nn.Linear(latent, hidden), nn.ReLU(), nn.Linear(hidden, flat))

    def forward(self, windows: torch.Tensor) -> torch.Tensor:
        batch, time, features = windows.shape
        latent = self.encoder(windows.reshape(batch, time * features))
        restored = self.decoder(latent).reshape(batch, time, features)
        return restored


class AutoencoderModel:
    """Fit and freeze a window autoencoder."""

    def __init__(self, n_features: int, window: int, latent: int = 16, hidden: int = 64):
        self.model = WindowAutoencoder(n_features, window, latent=latent, hidden=hidden)
        self.model.eval()

    def fit(
        self,
        windows: np.ndarray,
        epochs: int = 30,
        batch_size: int = 64,
        lr: float = 1e-3,
        seed: int = 0,
    ) -> list[float]:
        torch.manual_seed(seed)
        data = torch.tensor(np.asarray(windows, dtype=np.float32))
        self.model.train()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        losses: list[float] = []
        count = data.shape[0]
        for _ in range(epochs):
            order = torch.randperm(count)
            total = 0.0
            seen = 0
            for start in range(0, count, batch_size):
                batch = data[order[start : start + batch_size]]
                optimizer.zero_grad()
                restored = self.model(batch)
                loss = torch.mean((restored - batch) ** 2)
                loss.backward()
                optimizer.step()
                total += float(loss.detach()) * batch.shape[0]
                seen += batch.shape[0]
            losses.append(total / max(seen, 1))
        self.model.eval()
        return losses

    @torch.no_grad()
    def reconstruct(self, windows: np.ndarray) -> np.ndarray:
        data = torch.tensor(np.asarray(windows, dtype=np.float32))
        self.model.eval()
        return self.model(data).numpy()
