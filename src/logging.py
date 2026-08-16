"""Logging setup for XCRDownloader."""
import logging
import sys
from src.config import config

DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = None, format: str = None, date_format: str = None):
    """Configure logging for the application."""
    if level is None:
        level = config.log_level.upper()
    if format is None:
        format = DEFAULT_FORMAT
    if date_format is None:
        date_format = DEFAULT_DATE_FORMAT

    numeric_level = getattr(logging, level, logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format=format,
        datefmt=date_format,
        stream=sys.stdout,
    )

    # Set some noisy libraries to WARNING to avoid clutter
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("yt_dlp").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name."""
    return logging.getLogger(name)