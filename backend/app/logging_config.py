import logging
import sys

from pythonjsonlogger import jsonlogger

from app.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(service)s"
    formatter = jsonlogger.JsonFormatter(fmt, rename_fields={"asctime": "timestamp", "levelname": "level"})
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level)

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


class ContextFilter(logging.Filter):
    """Injects request_id/service into every log record so logs can be traced
    end-to-end across the API and worker (correlation across async boundaries)."""

    def __init__(self, service: str):
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        record.service = self.service
        return True
