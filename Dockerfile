FROM python:3.13-slim

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


CMD ["sh", "-lc", "uvicorn server_app:app --host 0.0.0.0 --port ${PORT:-8000}"]
