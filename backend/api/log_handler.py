import asyncio
import logging


class QueueLogHandler(logging.Handler):
    """Forwards log records into an asyncio.Queue for SSE streaming."""

    def __init__(self):
        super().__init__()
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=200)

    def emit(self, record: logging.LogRecord):
        try:
            self.queue.put_nowait({
                "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                "level": record.levelname,
                "message": self.format(record),
            })
        except asyncio.QueueFull:
            pass  # Drop if queue is full; non-blocking


# Module-level singleton — imported by main.py and the /logs/stream route
queue_log_handler = QueueLogHandler()
queue_log_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))

root_logger = logging.getLogger()
root_logger.addHandler(queue_log_handler)
root_logger.setLevel(logging.INFO)
