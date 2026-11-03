from __future__ import annotations
import logging
import re

_DROP_PATTERNS = (
    re.compile(r"Received request"),
    re.compile(r"completion response:"),
    re.compile(r"chat completion response:"),
    re.compile(r"prompt=", re.IGNORECASE),
    re.compile(r"generated text", re.IGNORECASE),
)

class _RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        return not any(p.search(msg) for p in _DROP_PATTERNS)

for name in ("vllm", "vllm.entrypoints", "vllm.entrypoints.openai"):
    logging.getLogger(name).addFilter(_RedactFilter())

def _patch_request_logger() -> None:
    try:
        from vllm.entrypoints import logger as _vllm_logger
        RL = _vllm_logger.RequestLogger
    except Exception:
        return

    audit = logging.getLogger("vllm.audit")

    def log_request(self, request, *args, **kwargs):
        model = getattr(request, "model", "unknown")
        messages = getattr(request, "messages", None) or []
        audit.info("request_received model=%s messages=%d", model, len(messages))

    def log_response(self, request_id, content, *args, **kwargs):
        n_chars = len(content or "")
        audit.info("response_sent request_id=%s chars=%d", request_id, n_chars)

    RL.log_request = log_request
    RL.log_response = log_response

_patch_request_logger()
