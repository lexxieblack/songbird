"""Structured logging configuration for Songbird using structlog.

Provides structured, contextual logging with consistent formatting across the application.
Supports both development (console) and production (JSON) output formats.
"""

import logging
import sys

import structlog


def setup_logging(log_level: str = "INFO") -> structlog.BoundLogger:
    """Configure structured logging with structlog.

    Sets up structlog with appropriate processors for structured logging:
    - Merges context variables for request-scoped logging
    - Adds log levels to output
    - ISO-format timestamps
    - Console rendering for development (can be swapped to JSON for production)

    Args:
        log_level: Logging level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            Defaults to "INFO".

    Returns:
        Configured structlog logger instance for the application.

    Example:
        >>> logger = setup_logging("DEBUG")
        >>> logger.info("application_started", version="2.0.0")
    """
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )

    # Configure structlog processors
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger("songbird")


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structlog logger instance with the given name.

    Args:
        name: Logger name, typically the module name or component identifier.

    Returns:
        Configured structlog logger bound to the specified name.

    Example:
        >>> logger = get_logger("songbird.commands")
        >>> logger.info("command_executed", command="ping", user_id=12345)
    """
    return structlog.get_logger(name)


# Convenience logger for general application use
logger = get_logger("songbird")
