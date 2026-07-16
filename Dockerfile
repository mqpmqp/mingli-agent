FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MINGLI_HOST=0.0.0.0 \
    MINGLI_ALLOWED_HOSTS=127.0.0.1:8000,localhost:8000 \
    PORT=8000

WORKDIR /app

RUN groupadd --system mingli \
    && useradd --system --gid mingli --home-dir /app --no-create-home mingli

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir ".[api]" \
    && python -m pip check

USER mingli

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/healthz', timeout=3).read()"]

CMD ["mingli-service"]
