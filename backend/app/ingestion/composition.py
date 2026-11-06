"""Logger names stay the module names the code used before the split."""
import logging


def execution_logger():
    return logging.getLogger("app.ingestion.execution")


def watermark_logger():
    return logging.getLogger("app.ingestion.watermarks")
