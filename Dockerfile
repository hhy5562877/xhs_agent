FROM m.daocloud.io/docker.io/node:20-alpine AS frontend-builder

WORKDIR /app/frontend

RUN npm config set registry https://registry.npmmirror.com

COPY frontend/package.json frontend/package-lock.json ./

RUN npm ci --legacy-peer-deps

COPY frontend/ ./

RUN npm run build

FROM m.daocloud.io/docker.io/python:3.12-slim AS production

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    PATH="/app/.venv/bin:$PATH"

RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# curl-cffi 需要 libcurl，pyexecjs 需要 nodejs 运行时
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/

COPY pyproject.toml uv.lock ./

# --no-install-project 使依赖层独立缓存，代码变更不触发重新安装
RUN UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple/ \
    uv sync --frozen --no-install-project --no-dev

COPY main.py ./
COPY src/ ./src/
COPY xhs_tools/ ./xhs_tools/

COPY --from=frontend-builder /app/static ./static/

RUN mkdir -p data log

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
