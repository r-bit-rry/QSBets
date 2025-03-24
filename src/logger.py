"""
Rich-enhanced logging configuration for QSBets.
Provides a centralized logging setup with colorful, formatted output.
"""

import logging
import os
from typing import Optional, Union, Literal

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme
from rich.traceback import install as install_rich_traceback

# Define custom theme for QSBets logs
QSBETS_THEME = Theme(
    {
        "logging.level.debug": "cyan",
        "logging.level.info": "green bold",
        "logging.level.warning": "yellow bold",
        "logging.level.error": "red bold",
        "logging.level.critical": "white on red bold",
        "event.telegram": "magenta",
        "event.stock": "blue",
        "event.analysis": "cyan",
    }
)

# Create console with theme
console = Console(theme=QSBETS_THEME)

# Install rich traceback handler
install_rich_traceback(console=console, show_locals=True)

# Log levels mapping
LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


# Configure logging
def setup_logging(
    level: Union[str, int] = "info",
    log_file: Optional[str] = None,
    module_name: str = "qsbets",
) -> logging.Logger:
    """
    Set up logging with Rich formatting.

    Args:
        level: Log level (debug, info, warning, error, critical)
        log_file: Optional file path for saving logs
        module_name: Name of the module requesting the logger

    Returns:
        Configured logger instance
    """
    # Convert string level to numeric
    if isinstance(level, str):
        level = LOG_LEVELS.get(level.lower(), logging.INFO)

    # Create handlers
    handlers = [
        RichHandler(
            console=console,
            rich_tracebacks=True,
            markup=True,
            enable_link_path=True,
            show_time=True,
            show_path=True,
        )
    ]

    # Add file handler if specified
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=level, format="%(message)s", datefmt="[%X]", handlers=handlers
    )

    # Get logger for the module
    logger = logging.getLogger(module_name)
    return logger


# Shortcut function to get a preconfigured logger
def get_logger(module_name: str = "qsbets") -> logging.Logger:
    """Get a logger for the specified module"""
    return logging.getLogger(module_name)


# Event logging helpers
def log_event(
    logger: logging.Logger,
    event_type: str,
    message: str,
    *args,
    level: Literal["debug", "info", "warning", "error", "critical"] = "info",
    **kwargs,
) -> None:
    """
    Log an event with proper formatting and highlighting

    Args:
        logger: The logger instance
        event_type: Type of event (e.g., 'telegram', 'stock', 'analysis')
        message: Log message
        level: Log level
        *args, **kwargs: Additional arguments for the message
    """
    styled_event = f"[event.{event_type}]{event_type.upper()}[/event.{event_type}]"
    log_method = getattr(logger, level)
    log_method(f"{styled_event}: {message}", *args, **kwargs)


# Initialize default logger
default_logger = setup_logging(
    level=os.environ.get("QSBETS_LOG_LEVEL", "info"),
    log_file=os.environ.get("QSBETS_LOG_FILE"),
)
