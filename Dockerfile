FROM python:3.12-slim

WORKDIR /app

# curl-cffi 需要 libcurl，pyexecjs 需要 nodejs 运行时
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv --no-cache-dir

COPY pyproject.toml uv.lock ./

# --no-install-project 使依赖层独立缓存，代码变更不触发重新安装
RUN uv sync --frozen --no-install-project --no-dev

COPY main.py ./
COPY src/ ./src/
COPY static/ ./static/
COPY xhs_tools/ ./xhs_tools/

RUN mkdir -p data log

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
