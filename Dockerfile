FROM python:3.13-slim
# runtime_vendor contains CPython 3.13 native wheels; keep the image in sync.

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/runtime_vendor \
    PORT=8000 \
    NV0_DATA_DIR=/app/data \
    NV0_ENABLE_DOCS=0

WORKDIR /app

COPY requirements.txt ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt \
    && adduser --disabled-password --gecos '' --uid 10001 appuser

COPY . /app
RUN mkdir -p /app/data /app/backups \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000


HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/readyz' % os.getenv('PORT','8000'), timeout=3)"

# uvicorn server_app:app is launched via start_server.py for Coolify-safe boot
CMD ["python", "start_server.py"]
