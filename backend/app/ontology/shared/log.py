"""Logger port. Messages stay on ``app.ontology.services.ontology_service``."""
from __future__ import annotations

import logging
from typing import Protocol


class OntologyLog(Protocol):
    def debug(self, msg: str, *args: object) -> None: ...
    def info(self, msg: str, *args: object) -> None: ...
    def warning(self, msg: str, *args: object) -> None: ...
    def error(self, msg: str, *args: object) -> None: ...
    def exception(self, msg: str, *args: object) -> None: ...


class LoggingOntologyLog:
    def __init__(self, name: str = "app.ontology.services.ontology_service") -> None:
        self._logger = logging.getLogger(name)

    def debug(self, msg: str, *args: object) -> None:
        self._logger.debug(msg, *args)

    def info(self, msg: str, *args: object) -> None:
        self._logger.info(msg, *args)

    def warning(self, msg: str, *args: object) -> None:
        self._logger.warning(msg, *args)

    def error(self, msg: str, *args: object) -> None:
        self._logger.error(msg, *args)

    def exception(self, msg: str, *args: object) -> None:
        self._logger.exception(msg, *args)
