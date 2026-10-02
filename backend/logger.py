import logging
import json
import time
from fastapi import Request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("yolo_app")

def log_request_info(request_id: str, route: str, method: str, status_code: int, latency: float, extra: dict = None):
    log_payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level": "INFO" if status_code < 400 else "ERROR",
        "request_id": request_id,
        "route": route,
        "method": method,
        "status_code": status_code,
        "latency_ms": round(latency * 1000, 2)
    }
    if extra:
        log_payload.update(extra)
    logger.info(json.dumps(log_payload))