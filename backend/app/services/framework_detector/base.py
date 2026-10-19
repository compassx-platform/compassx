"""Base detector contract and abstractions.

Adheres to Open/Closed and Liskov Substitution Principles:
Any new framework or service type can be added by implementing BaseDetector
without modifying existing detector logic.
"""

from abc import ABC, abstractmethod
from typing import Optional, Any, Dict


class BaseDetector(ABC):
    """Abstract base detector interface."""

    @abstractmethod
    def can_detect(self, base_dir: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Return True if this detector recognizes patterns in base_dir."""
        pass

    @abstractmethod
    def detect(self, base_dir: str, context: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """Perform detection and return service specification if found."""
        pass
