from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlparse

import uvicorn
from dotenv import load_dotenv

LOCAL_HOSTS = {"127.0.0.1", "localhost", "0.0.0.0", "::1"}


def load_env_files() -> None:
    root = Path(__file__).resolve().parent
    for name in (".env", ".env.local", ".env.production"):
        candidate = root / name
        if candidate.exists():
            load_dotenv(candidate, override=False)



def clean(value: str | None) -> str:
    return (value or "").strip()


def is_true(value: str | None) -> bool:
    return clean(value).lower() in {"1", "true", "yes", "on"}


def is_local_base() -> bool:
    host = (urlparse(clean(os.getenv("NV0_BASE_URL")) or "http://127.0.0.1").hostname or '').lower()
    return host in LOCAL_HOSTS


def ensure(name: str, value: str) -> None:
    os.environ[name] = value


def maybe_set_default(name: str, value: str) -> None:
    if not clean(os.getenv(name)):
        os.environ[name] = value


def log(msg: str) -> None:
    print(f"[startup] {msg}", flush=True)


def int_env(name: str, default: int | None = None) -> int | None:
    raw = clean(os.getenv(name))
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if value <= 0:
        return None
    return value


def main() -> None:
    load_env_files()
    port = clean(os.getenv("PORT")) or "8000"
    maybe_set_default("NV0_BASE_URL", f"http://127.0.0.1:{port}")
    parsed = urlparse(os.getenv("NV0_BASE_URL", ""))
    base_host = parsed.hostname or "127.0.0.1"
    maybe_set_default("NV0_ALLOWED_HOSTS", f"{base_host},localhost,127.0.0.1")
    scheme = parsed.scheme or "http"
    netloc = parsed.netloc or f"127.0.0.1:{port}"
    maybe_set_default("NV0_ALLOWED_ORIGINS", f"{scheme}://{netloc}")

    board_only = is_true(os.getenv("NV0_BOARD_ONLY_MODE"))
    toss_mock = is_true(os.getenv("NV0_TOSS_MOCK"))
    local_base = is_local_base()
    strict_startup = is_true(os.getenv("NV0_STRICT_STARTUP"))

    if not local_base:
        admin = clean(os.getenv("NV0_ADMIN_TOKEN"))
        if len(admin) < 32:
            if strict_startup:
                raise RuntimeError("NV0_ADMIN_TOKEN must be at least 32 characters in strict startup mode.")
            ensure("NV0_ADMIN_TOKEN", secrets.token_urlsafe(32))
            log("NV0_ADMIN_TOKEN was missing or too short. Generated an ephemeral token so the app can boot.")

        backup = clean(os.getenv("NV0_BACKUP_PASSPHRASE"))
        if len(backup) < 24:
            if strict_startup:
                raise RuntimeError("NV0_BACKUP_PASSPHRASE must be at least 24 characters in strict startup mode.")
            ensure("NV0_BACKUP_PASSPHRASE", secrets.token_urlsafe(24))
            log("NV0_BACKUP_PASSPHRASE was missing or too short. Generated an ephemeral passphrase so the app can boot.")

        payment_provider = clean(os.getenv("NV0_PAYMENT_PROVIDER") or "toss").lower()
        if not board_only and payment_provider == "toss" and not toss_mock:
            has_ck = bool(clean(os.getenv("NV0_TOSS_CLIENT_KEY")))
            has_sk = bool(clean(os.getenv("NV0_TOSS_SECRET_KEY")))
            if not (has_ck and has_sk):
                if strict_startup:
                    raise RuntimeError("Toss live keys are required in strict startup mode when NV0_TOSS_MOCK=0.")
                ensure("NV0_TOSS_MOCK", "1")
                log("Toss live keys were missing. Switched NV0_TOSS_MOCK=1 automatically to avoid startup failure.")

    proxy_headers = is_true(os.getenv("UVICORN_PROXY_HEADERS", "1" if not local_base else "0"))
    forwarded_allow_ips = clean(os.getenv("FORWARDED_ALLOW_IPS")) or ("*" if proxy_headers and not local_base else "127.0.0.1")
    server_header = is_true(os.getenv("UVICORN_SERVER_HEADER", "0"))
    date_header = is_true(os.getenv("UVICORN_DATE_HEADER", "0"))
    timeout_keep_alive = int_env("UVICORN_TIMEOUT_KEEP_ALIVE", 5) or 5
    limit_concurrency = int_env("UVICORN_LIMIT_CONCURRENCY")
    limit_max_requests = int_env("UVICORN_LIMIT_MAX_REQUESTS")
    timeout_graceful_shutdown = int_env("UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN")

    log(f"Starting uvicorn on 0.0.0.0:{port}")
    uvicorn.run(
        "server_app:app",
        host="0.0.0.0",
        port=int(port),
        log_level=os.getenv("UVICORN_LOG_LEVEL", "info"),
        proxy_headers=proxy_headers,
        forwarded_allow_ips=forwarded_allow_ips,
        server_header=server_header,
        date_header=date_header,
        timeout_keep_alive=timeout_keep_alive,
        limit_concurrency=limit_concurrency,
        limit_max_requests=limit_max_requests,
        timeout_graceful_shutdown=timeout_graceful_shutdown,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[startup] fatal: {exc}", file=sys.stderr, flush=True)
        raise
