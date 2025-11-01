import logging
import os
from logging.handlers import RotatingFileHandler

LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "bot.log")


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("shutupbot")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(module)s.%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    # Rotating file
    file_handler = RotatingFileHandler(LOG_FILE_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def log_delete_failure(logger: logging.Logger, *, chat_id: int, message_id: int, user_id: int, reason: str):
    logger.error(
        "Delete failure | chat_id=%s | message_id=%s | user_id=%s | reason=%s",
        chat_id,
        message_id,
        user_id,
        reason,
    )


def tail_logs(lines: int = 100) -> str:
    if not os.path.exists(LOG_FILE_PATH):
        return "(no logs yet)"
    try:
        with open(LOG_FILE_PATH, "r", encoding="utf-8", errors="ignore") as f:
            data = f.readlines()
        return "".join(data[-lines:])
    except Exception as e:
        return f"Failed to read logs: {e}"


__all__ = ["setup_logging", "log_delete_failure", "tail_logs", "LOG_FILE_PATH"]


