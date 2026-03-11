import logging
import time

from fastapi import Request

logger = logging.getLogger(__name__)


async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter_ns()
    response = await call_next(request)
    duration_ms = (time.perf_counter_ns() - start) / 1_000_000
    response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
    logger.info(f"⏱ {request.method} {request.url.path} → {duration_ms:.2f}ms")
    return response
