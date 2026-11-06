"""Wires the ontology logger into application types."""
from app.ontology.shared.log import LoggingOntologyLog

_log = LoggingOntologyLog()


def ontology_log() -> LoggingOntologyLog:
    return _log
