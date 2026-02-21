import logging
import time
from fastapi import Request

logger = logging.getLogger("xhs_agent")


async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    body = await request.body()

    logger.debug(
        f"→ {request.method} {request.url.path}  body={body.decode(errors='replace')[:500] or '-'}"
    )

    response = await call_next(request)

    elapsed = (time.perf_counter() - start) * 1000
    logger.debug(
        f"← {request.method} {request.url.path}  status={response.status_code}  {elapsed:.1f}ms"
    )
    logger.info(
        f"{request.method} {request.url.path} {response.status_code} {elapsed:.0f}ms"
    )
    return response
