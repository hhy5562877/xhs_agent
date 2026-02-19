import logging
import time
from fastapi import Request

logger = logging.getLogger("xhs_agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    body = await request.body()
    logger.info(f"→ {request.method} {request.url.path}  body={body.decode()[:500] or '-'}")

    response = await call_next(request)

    elapsed = (time.perf_counter() - start) * 1000
    logger.info(f"← {request.method} {request.url.path}  status={response.status_code}  {elapsed:.1f}ms")
    return response
