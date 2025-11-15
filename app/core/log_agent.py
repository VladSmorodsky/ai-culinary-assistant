from __future__ import annotations
import logging, os, uuid, threading, time
from logging.handlers import TimedRotatingFileHandler
from contextvars import ContextVar
from typing import Any, Optional

_request_id: ContextVar[str] = ContextVar("request_id", default="-")
_init_lock = threading.Lock()
_initialized = False

DEFAULT_LOG_DIR = os.getenv("LOG_DIR", "logs")
DEFAULT_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # always return True
        record.request_id = _request_id.get()
        return True

def set_request_id(rid: str):
    _request_id.set(rid)

def init_logging():
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        os.makedirs(DEFAULT_LOG_DIR, exist_ok=True)
        root = logging.getLogger()
        root.setLevel(getattr(logging, DEFAULT_LOG_LEVEL, logging.INFO))
        fmt = "%(asctime)s | %(levelname)s | %(request_id)s | %(name)s | %(message)s"
        formatter = logging.Formatter(fmt)
        # Console handler
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        ch.addFilter(RequestIdFilter())
        root.addHandler(ch)
        # Rotating file handler (daily rotation, keep 10 backups)
        fh = TimedRotatingFileHandler(os.path.join(DEFAULT_LOG_DIR, "app.log"), when="D", interval=1, backupCount=10, encoding="utf-8")
        fh.setFormatter(formatter)
        fh.addFilter(RequestIdFilter())
        root.addHandler(fh)
        _initialized = True

class LogAgent:
    """Central logging agent for structured step tracing.

    Usage:
        from app.core.log_agent import get_log_agent
        log = get_log_agent()
        log.step("meal_plan", "start", days=req.days)
    """
    def __init__(self):
        init_logging()

    def _logger(self, component: str) -> logging.Logger:
        return logging.getLogger(f"agent.{component}")

    def step(self, component: str, step: str, **fields: Any):
        """Log a progress step with optional structured fields."""
        logger = self._logger(component)
        msg_parts = [f"step={step}"]
        for k, v in fields.items():
            if isinstance(v, (dict, list, tuple)):
                # Avoid giant outputs
                rep = repr(v)
                if len(rep) > 500:
                    rep = rep[:500] + "..."
                msg_parts.append(f"{k}={rep}")
            else:
                msg_parts.append(f"{k}={v}")
        logger.info(" ".join(msg_parts))

    def error(self, component: str, step: str, **fields: Any):
        logger = self._logger(component)
        msg_parts = [f"step={step}"] + [f"{k}={v}" for k, v in fields.items()]
        logger.error(" ".join(msg_parts))

    def exception(self, component: str, step: str, **fields: Any):
        logger = self._logger(component)
        msg_parts = [f"step={step}"] + [f"{k}={v}" for k, v in fields.items()]
        logger.exception(" ".join(msg_parts))

    def timed(self, component: str, step: str):
        """Context manager to time a code block."""
        class _Timer:
            def __enter__(_self):
                _self.start = time.perf_counter()
                self.step(component, f"{step}.start")
                return _self
            def __exit__(_self, exc_type, exc, tb):
                dur = time.perf_counter() - _self.start
                if exc:
                    self.exception(component, f"{step}.error", duration_ms=int(dur*1000), error=repr(exc))
                else:
                    self.step(component, f"{step}.done", duration_ms=int(dur*1000))
        return _Timer()

_log_agent: Optional[LogAgent] = None

def get_log_agent() -> LogAgent:
    global _log_agent
    if _log_agent is None:
        _log_agent = LogAgent()
    return _log_agent

# FastAPI middleware helper
from fastapi import Request
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    set_request_id(rid)
    try:
        return await call_next(request)
    finally:
        # reset
        set_request_id("-")
