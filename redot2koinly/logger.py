"""Simple logging and statistics collection."""
import logging
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass
from time import time
from typing import Optional


logger = logging.getLogger("redot2koinly")


@dataclass
class Stats:
    files_processed: int = 0
    files_ignored: int = 0
    records_read: int = 0
    duplicates_removed: int = 0
    record_errors: int = 0
    start_time: float = 0.0

    def start(self):
        self.start_time = time()

    def duration(self) -> float:
        return time() - self.start_time if self.start_time else 0.0


def setup_logging(verbose: bool = False, debug: bool = True, log_file: Optional[str] = None,
                  max_bytes: int = 1000000, backup_count: int = 5, console_output: bool = False):
    """Configure logging to console and rotating file handler.

    - If `debug` or `verbose` is True, set level to DEBUG; otherwise INFO.
    - If `log_file` provided, also write to a rotating file with `max_bytes` and `backup_count`.
    - If `console_output` is True, also log to console; otherwise only to file.
    """
    # Determine level
    level = logging.DEBUG if (debug or verbose) else logging.INFO
    logger.setLevel(level)

    # Clear existing handlers
    for h in list(logger.handlers):
        logger.removeHandler(h)

    # Define formatter for both console and file handlers
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    # Console handler (only if console_output is True)
    if console_output:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    # File handler (rotating)
    if log_file:
        fh = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
