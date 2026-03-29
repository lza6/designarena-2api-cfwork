# -*- coding: utf-8 -*-
import json
import logging
import sys
import time
from datetime import datetime

class PlainFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m', 'INFO': '\033[32m', 'WARNING': '\033[33m',
        'ERROR': '\033[31m', 'CRITICAL': '\033[41m'
    }
    RESET = '\033[0m'

    def format(self, record):
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        color = self.COLORS.get(record.levelname, '')
        try:
            # Handle cases where record.msg is a template and args are provided
            message = record.getMessage()
        except Exception:
            # Fallback if getMessage fails due to unexpected uvicorn formatting
            message = str(record.msg)
        return f"[{ts}] {color}{record.levelname:8}{self.RESET} | {message}"

class JsonFormatter(logging.Formatter):
    def format(self, record):
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": msg,
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record, ensure_ascii=False)

def setup_logging():
    # Setup root logger to capture everything
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Wipe existing root handlers
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    
    # Console Handler (Human Readable) - Use stderr
    ch = logging.StreamHandler(sys.stderr)
    ch.setFormatter(PlainFormatter())
    root_logger.addHandler(ch)
    
    # File Handler (JSON)
    try:
        fh = logging.FileHandler("app.log", encoding="utf-8")
        fh.setFormatter(JsonFormatter())
        root_logger.addHandler(fh)
    except Exception:
        pass
    
    # Let libraries propagate to our root logger instead of having their own handlers
    for name in ["uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"]:
        l = logging.getLogger(name)
        l.handlers = []
        l.propagate = True
    
    return root_logger

logger = setup_logging()
