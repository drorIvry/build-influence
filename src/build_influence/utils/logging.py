import sys
import os
from loguru import logger

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FILE = os.environ.get("LOG_FILE", "logs/build_influence.log")
LOG_ROTATION = os.environ.get("LOG_ROTATION", "10 MB")
LOG_RETENTION = os.environ.get("LOG_RETENTION", "30 days")


def setup_logging():
    """Configures the Loguru logger."""
    logger.remove()  # Remove default handler

    # Console logger
    logger.add(
        sys.stderr,
        level="ERROR",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}:{function}:{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File logger (with rotation and retention)
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    logger.add(
        LOG_FILE,
        level=LOG_LEVEL,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        enqueue=True,  # Make logging asynchronous
        backtrace=True,  # Better error tracebacks
        diagnose=True,  # More detailed exception info
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} - {message}"
        ),
    )

    logger.info("Logging configured")
    logger.info(f"Log level: {LOG_LEVEL}")
    logger.info(f"Log file: {LOG_FILE}")


# Example usage (can be removed later):
if __name__ == "__main__":
    setup_logging()
    logger.debug("This is a debug message.")
    logger.info("This is an info message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")
    logger.critical("This is a critical message.")
    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("Caught an exception!")
