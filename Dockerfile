FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/runtime_vendor \
    PORT=8000 \
    NV0_DATA_DIR=/app/data \
    NV0_ENABLE_DOCS=0

# 기존 소스 복사 전후에 아래 내용 추가
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .

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
