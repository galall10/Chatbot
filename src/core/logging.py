"""Structured logging configuration."""

import logging
import sys
from typing import Optional
from contextvars import ContextVar

from src.core.config import settings


# Context variable for request ID tracking
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class ContextualFormatter(logging.Formatter):
    """Custom formatter that includes request_id in log messages."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with request context."""
        request_id = request_id_var.get()
        if request_id:
            record.request_id = request_id
        else:
            record.request_id = "-"
        return super().format(record)


def setup_logging() -> None:
    """Configure application logging."""
    
    # Create logger
    logger = logging.getLogger("chatbot")
    logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Create formatter
    if settings.environment == "production":
        # JSON-like structured format for production
        formatter = ContextualFormatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"request_id": "%(request_id)s", "name": "%(name)s", '
            '"message": "%(message)s"}'
        )
    else:
        # Human-readable format for development
        formatter = ContextualFormatter(
            "%(asctime)s - %(levelname)s - [%(request_id)s] - %(name)s - %(message)s"
        )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(f"chatbot.{name}")


def set_request_id(request_id: str) -> None:
    """Set request ID for the current context."""
    request_id_var.set(request_id)


def clear_request_id() -> None:
    """Clear request ID from the current context."""
    request_id_var.set(None)
