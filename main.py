import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from src.xhs_agent.api.router import router
from src.xhs_agent.middleware import log_requests
from src.xhs_agent.db import init_db
from src.xhs_agent.services.scheduler_service import start_scheduler, reload_pending_jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()
    await reload_pending_jobs()
    yield


app = FastAPI(title="XHS Agent", description="小红书内容自动生成 Agent", lifespan=lifespan)

app.add_middleware(BaseHTTPMiddleware, dispatch=log_requests)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")


def main():
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
