"""Centralized logging setup."""
from __future__ import annotations

import json
import logging
import os
import gzip
import shutil
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


_LOG_RECORD_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


class JsonLikeFormatter(logging.Formatter):
    """Format logs as compact JSON-like strings without extra dependencies."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _LOG_RECORD_RESERVED and not key.startswith("_")
        }
        if extras:
            payload["extra"] = extras
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging() -> None:
    """Configure root logger once for API and background services."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    level_name = (os.getenv("LOG_LEVEL") or "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    formatter = JsonLikeFormatter(datefmt="%Y-%m-%dT%H:%M:%S")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.setLevel(level)
    root_logger.addHandler(stream_handler)

    log_file = (os.getenv("LOG_FILE") or "backend/logs/app.log").strip()
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        retention_days = int((os.getenv("LOG_RETENTION_DAYS") or "180").strip() or "180")
        file_handler = TimedRotatingFileHandler(
            filename=str(path),
            when="midnight",
            interval=1,
            backupCount=max(1, retention_days),
            utc=False,
            encoding="utf-8",
        )
        file_handler.suffix = "%Y-%m-%d"

        def _gzip_namer(default_name: str) -> str:
            return f"{default_name}.gz"

        def _gzip_rotator(source: str, dest: str) -> None:
            with open(source, "rb") as src, gzip.open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
            os.remove(source)

        file_handler.namer = _gzip_namer
        file_handler.rotator = _gzip_rotator
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
