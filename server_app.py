from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict, deque
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from html import escape
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
DIST = ROOT / "dist"
DATA_FILE = SRC / "data" / "site.json"
APP_DATA_DIR = Path(os.getenv("NV0_DATA_DIR", str(ROOT / "data")))
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.getenv("NV0_DB_PATH", str(APP_DATA_DIR / "nv0.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SITE_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
PRODUCTS = {item["key"]: item for item in SITE_DATA["products"]}
PUBLIC_BOARD = SITE_DATA.get("public_board", [])
BOARD_ONLY_MODE = os.getenv("NV0_BOARD_ONLY_MODE", "0").lower() in {"1", "true", "yes", "on"}
STORE_TYPES = ["publications", "scheduler"] if BOARD_ONLY_MODE else ["orders", "demos", "contacts", "lookups", "publications", "webhook_events", "scheduler"]

APP_PORT = str(os.getenv("PORT", "8000") or "8000").strip() or "8000"
NV0_BASE_URL = os.getenv("NV0_BASE_URL", f"http://127.0.0.1:{APP_PORT}").rstrip("/")
NV0_ADMIN_TOKEN = os.getenv("NV0_ADMIN_TOKEN", "")
NV0_PAYMENT_PROVIDER = os.getenv("NV0_PAYMENT_PROVIDER", SITE_DATA.get("integration", {}).get("payment_provider", "toss"))
NV0_TOSS_CLIENT_KEY = os.getenv("NV0_TOSS_CLIENT_KEY", "")
NV0_TOSS_SECRET_KEY = os.getenv("NV0_TOSS_SECRET_KEY", "")
NV0_TOSS_MOCK = os.getenv("NV0_TOSS_MOCK", "0").lower() in {"1", "true", "yes", "on"}
NV0_TOSS_WEBHOOK_SECRET = os.getenv("NV0_TOSS_WEBHOOK_SECRET", "")
TOSS_CONFIRM_URL = os.getenv("NV0_TOSS_CONFIRM_URL", "https://api.tosspayments.com/v1/payments/confirm")
SUCCESS_PATH = "/payments/toss/success/"
FAIL_PATH = "/payments/toss/fail/"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "0.0.0.0", "::1"}


def _parse_csv_env(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(',') if item.strip()]


def _extract_hosts_from_text(value: str) -> list[str]:
    hosts: list[str] = []
    for raw in re.split(r"[,\s]+", (value or "")):
        item = raw.strip()
        if not item:
            continue
        if '://' in item:
            parsed = urlparse(item)
            host = (parsed.hostname or '').strip().lower()
            if host:
                hosts.append(host)
            continue
        host = item.split('/')[0].split(':')[0].strip().lower()
        if host:
            hosts.append(host)
    return hosts


def parse_internal_hosts() -> set[str]:
    hosts = set(LOCAL_HOSTS)
    for item in _parse_csv_env("NV0_INTERNAL_HOSTS"):
        hosts.update(_extract_hosts_from_text(item))
    for env_name in ("HOSTNAME", "COOLIFY_URL", "COOLIFY_FQDN", "SERVICE_FQDN_NV0-COMPANY", "SERVICE_FQDN_NV0-COMPANY_8000"):
        hosts.update(_extract_hosts_from_text(os.getenv(env_name, "")))
    return {host for host in hosts if host}


INTERNAL_HOSTS = parse_internal_hosts()
HEALTH_ENDPOINTS = {"/health", "/healthz", "/live", "/livez", "/ready", "/readyz", "/api/health", "/api/admin/health"}


def parse_allowed_hosts() -> list[str]:
    candidates: list[str] = []
    for item in _parse_csv_env("NV0_ALLOWED_HOSTS"):
        candidates.extend(_extract_hosts_from_text(item))
    base_host = (urlparse(NV0_BASE_URL).hostname or '').strip().lower()
    if base_host:
        candidates.append(base_host)
    for env_name in ("COOLIFY_URL", "COOLIFY_FQDN", "SERVICE_FQDN_NV0-COMPANY", "SERVICE_FQDN_NV0-COMPANY_8000"):
        candidates.extend(_extract_hosts_from_text(os.getenv(env_name, "")))
    candidates.extend(sorted(INTERNAL_HOSTS))
    seen: set[str] = set()
    ordered: list[str] = []
    for item in candidates:
        item = item.lower()
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered or ["127.0.0.1", "localhost", "::1"]


ALLOWED_HOSTS = parse_allowed_hosts()
BASE_HOST = urlparse(NV0_BASE_URL).hostname or ""
IS_LOCAL_BASE = BASE_HOST.lower() in LOCAL_HOSTS
REQUIRE_ADMIN_TOKEN = os.getenv("NV0_REQUIRE_ADMIN_TOKEN", "1" if not IS_LOCAL_BASE else "0").lower() in {"1", "true", "yes", "on"}
ENABLE_DOCS = os.getenv("NV0_ENABLE_DOCS", "0").lower() in {"1", "true", "yes", "on"}
BACKUP_DIR = Path(os.getenv("NV0_BACKUP_DIR", str(APP_DATA_DIR / "backups")))
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
HSTS_ENABLED = os.getenv("NV0_HSTS_ENABLED", "1").lower() in {"1", "true", "yes", "on"}
PUBLIC_HEALTH_VERBOSE = os.getenv("NV0_PUBLIC_HEALTH_VERBOSE", "0").lower() in {"1", "true", "yes", "on"}
_CANONICAL_HOST_ENV = os.getenv("NV0_CANONICAL_HOST", "").strip().lower()
_BASE_URL_HOST = (urlparse(NV0_BASE_URL).hostname or "").strip().lower()
CANONICAL_HOST = _CANONICAL_HOST_ENV or _BASE_URL_HOST
_CANONICAL_DEFAULT = "1" if CANONICAL_HOST and CANONICAL_HOST not in LOCAL_HOSTS else "0"
ENFORCE_CANONICAL_HOST = os.getenv("NV0_ENFORCE_CANONICAL_HOST", _CANONICAL_DEFAULT).lower() in {"1", "true", "yes", "on"}
CANONICAL_SCHEME = (os.getenv("NV0_CANONICAL_SCHEME", urlparse(NV0_BASE_URL).scheme or ("https" if HSTS_ENABLED else "http")) or "").strip().lower()
PUBLIC_RATE_LIMIT_PER_MIN = max(10, int(os.getenv("NV0_PUBLIC_RATE_LIMIT_PER_MIN", "30") or "30"))
ADMIN_RATE_LIMIT_PER_MIN = max(10, int(os.getenv("NV0_ADMIN_RATE_LIMIT_PER_MIN", "60") or "60"))
PORTAL_RATE_LIMIT_PER_MIN = max(10, int(os.getenv("NV0_PORTAL_RATE_LIMIT_PER_MIN", "40") or "40"))
MAX_BODY_BYTES = max(262144, int(os.getenv("NV0_MAX_BODY_BYTES", "1048576") or "1048576"))
BOARD_ONLY_MODE = os.getenv("NV0_BOARD_ONLY_MODE", "0").lower() in {"1", "true", "yes", "on"}
BOARD_ONLY_ALLOWED_PUBLIC_PATHS = ("/", "/index.html", "/board", "/admin", "/legal/privacy", "/assets/", "/robots.txt", "/sitemap.xml", "/.well-known/", "/favicon.ico")
BOARD_ONLY_DISABLED_API_PREFIXES = (
    "/api/public/orders", "/api/public/payments", "/api/public/demo-requests", "/api/public/contact-requests", "/api/public/portal/lookup", "/api/admin/orders/"
)
_WRITE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_RECORD_CACHE: dict[str, list[dict[str, Any]]] = {}
_STATE_CACHE: dict[str, list[dict[str, Any]]] | None = None
_JSON_CACHE: dict[str, bytes] = {}
_CACHE_LOCK = threading.RLock()
_SCHEDULE_LOCK = threading.Lock()
_ORDER_LOCKS: dict[str, threading.Lock] = {}
_ORDER_LOCKS_GUARD = threading.Lock()
_LAST_SCHEDULED_CHECK_MONOTONIC = 0.0
SCHEDULE_CHECK_MIN_INTERVAL_SECONDS = max(1.0, float(os.getenv("NV0_SCHEDULE_CHECK_MIN_INTERVAL_SECONDS", "15") or "15"))


def invalidate_cache(*record_types: str) -> None:
    global _STATE_CACHE, _LAST_SCHEDULED_CHECK_MONOTONIC
    with _CACHE_LOCK:
        if record_types:
            for record_type in record_types:
                _RECORD_CACHE.pop(record_type, None)
        else:
            _RECORD_CACHE.clear()
        _STATE_CACHE = None
        _JSON_CACHE.clear()
    if not record_types or "publications" in record_types or "scheduler" in record_types:
        _LAST_SCHEDULED_CHECK_MONOTONIC = 0.0

def board_only_path_allowed(path: str) -> bool:
    normalized = path or '/'
    for allowed in BOARD_ONLY_ALLOWED_PUBLIC_PATHS:
        if allowed == '/':
            if normalized in {'/', '/index.html'}:
                return True
            continue
        prefix = allowed if allowed.endswith('/') else allowed.rstrip('/')
        if normalized == allowed or normalized.startswith(prefix):
            return True
    return False


def board_only_disabled_api(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in BOARD_ONLY_DISABLED_API_PREFIXES)


def board_only_json_response(detail: str) -> JSONResponse:
    return JSONResponse(status_code=410, content={"ok": False, "detail": detail, "mode": "board_only"})


def board_only_html_response(path: str) -> HTMLResponse:
    return HTMLResponse(status_code=410, content=(
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>410 Gone</title><style>body{font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;margin:0}"
        "main{max-width:760px;margin:8vh auto;padding:24px}.card{background:#111827;border:1px solid #334155;border-radius:20px;padding:24px}a{color:#93c5fd}</style></head>"
        f"<body><main><div class='card'><h1>이 경로는 운영하지 않습니다</h1><p>현재 NV0는 AI 자동발행 블로그 허브 중심으로 운영합니다.</p><p>요청 경로: <code>{path}</code></p><p><a href='/board/'>게시판으로 이동</a> · <a href='/admin/'>관리자 열기</a></p></div></main></body></html>"
    ))


def parse_allowed_origins() -> list[str]:
    candidates: list[str] = []
    base = str(NV0_BASE_URL or "").strip()
    if base.startswith(("http://", "https://")):
        candidates.append(base.rstrip("/"))
    explicit = os.getenv("NV0_ALLOWED_ORIGINS", "")
    for item in explicit.split(","):
        value = str(item or "").strip().rstrip("/")
        if value.startswith(("http://", "https://")):
            candidates.append(value)
    if IS_LOCAL_BASE:
        for fallback in ["http://127.0.0.1:8000", "http://localhost:8000"]:
            candidates.append(fallback)
    seen = set()
    ordered = []
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered or ["http://127.0.0.1:8000", "http://localhost:8000"]


ALLOWED_ORIGINS = parse_allowed_origins()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    try:
        if not value:
            return None
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def uid(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def make_public_code(kind: str, product_key: str | None = None) -> str:
    head = clean(kind).upper() or 'NV0'
    mid = product_prefix(product_key or '') if product_key else 'GEN'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    tail = secrets.token_hex(4).upper()
    return f"{head}-{mid}-{stamp}-{tail}"


def order_lock(order_id: str) -> threading.Lock:
    key = clean(order_id) or '__unknown__'
    with _ORDER_LOCKS_GUARD:
        lock = _ORDER_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _ORDER_LOCKS[key] = lock
        return lock


def clean(value: Any) -> str:
    return str(value or "").strip()


EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)


def normalize_email(value: Any) -> str:
    return clean(value).lower()


def normalize_code(value: Any) -> str:
    return clean(value).upper()


def clip_text(value: Any, limit: int) -> str:
    return clean(value)[: max(0, int(limit))]


def validate_email(value: str) -> bool:
    value = normalize_email(value)
    return bool(value) and bool(EMAIL_RE.match(value))


def signed_payload_hmac(payload_bytes: bytes, secret: str) -> str:
    return hmac.new(secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()


def lower_headers(headers: dict[str, str] | None) -> dict[str, str]:
    return {str(k).lower(): str(v) for k, v in (headers or {}).items()}


def canonical_redirect_target(request: Request) -> str | None:
    if not ENFORCE_CANONICAL_HOST or not CANONICAL_HOST:
        return None
    forwarded_host = clean(request.headers.get('x-forwarded-host')).split(',')[0].strip()
    host_source = forwarded_host or clean(request.headers.get('host'))
    host_header = host_source.split(':')[0].lower()
    if not host_header or host_header in INTERNAL_HOSTS or host_header == CANONICAL_HOST:
        return None
    target_path = request.url.path or '/'
    if request.url.query:
        target_path += f'?{request.url.query}'
    forwarded_proto = clean(request.headers.get('x-forwarded-proto')).split(',')[0].strip().lower()
    scheme = forwarded_proto if forwarded_proto in {'http', 'https'} else (CANONICAL_SCHEME if CANONICAL_SCHEME in {'http', 'https'} else ('https' if HSTS_ENABLED else 'http'))
    return f"{scheme}://{CANONICAL_HOST}{target_path}"


def request_host(request: Request) -> str:
    forwarded_host = clean(request.headers.get('x-forwarded-host')).split(',')[0].strip()
    host_source = forwarded_host or clean(request.headers.get('host'))
    return host_source.split(':')[0].strip().lower()


def host_matches_allowed(host: str, allowed_hosts: list[str]) -> bool:
    host = clean(host).lower()
    if not host:
        return True
    for pattern in allowed_hosts:
        pattern = clean(pattern).lower()
        if not pattern:
            continue
        if pattern == '*' or pattern == host:
            return True
        if pattern.startswith('*.') and host.endswith(pattern[1:]) and host.count('.') >= pattern.count('.'):
            return True
    return False


def invalid_host_response(request: Request) -> Response | None:
    if ALLOWED_HOSTS == ['*']:
        return None
    host = request_host(request)
    if not host or host in INTERNAL_HOSTS or host_matches_allowed(host, ALLOWED_HOSTS):
        return None
    redirect_target = canonical_redirect_target(request)
    if redirect_target and request.method.upper() in {'GET', 'HEAD'}:
        return Response(status_code=308, headers={'Location': redirect_target})
    return JSONResponse(status_code=400, content={"ok": False, "detail": f"허용되지 않은 Host 입니다: {host}"})


def verify_toss_webhook_signature(raw_body: bytes, request_headers: dict[str, str]) -> tuple[bool, str]:
    headers = lower_headers(request_headers)
    signature_header = clean(headers.get('tosspayments-webhook-signature'))
    transmission_time = clean(headers.get('tosspayments-webhook-transmission-time'))
    if not signature_header:
        return False, 'missing_signature'
    if not transmission_time:
        return False, 'missing_transmission_time'
    if not NV0_TOSS_WEBHOOK_SECRET:
        return False, 'missing_webhook_secret'
    if not signature_header.startswith('v1:'):
        return False, 'invalid_signature_format'
    payload = raw_body.decode('utf-8', errors='ignore')
    signed = f"{payload}:{transmission_time}".encode('utf-8')
    expected = signed_payload_hmac(signed, NV0_TOSS_WEBHOOK_SECRET)
    encoded_values = [item.strip() for item in signature_header.split('v1:', 1)[1].split(',') if item.strip()]
    for item in encoded_values:
        try:
            decoded = base64.b64decode(item).decode('utf-8')
        except Exception:
            continue
        if secrets.compare_digest(decoded, expected):
            return True, 'verified_signature'
    return False, 'signature_mismatch'


def verify_toss_payment_secret(raw: dict[str, Any], stored: dict[str, Any] | None) -> tuple[bool, str]:
    data = raw.get('data') if isinstance(raw.get('data'), dict) else {}
    incoming_secret = clean(raw.get('secret') or data.get('secret'))
    known_secret = clean(((stored or {}).get('paymentMeta') or {}).get('secret'))
    if known_secret and incoming_secret and secrets.compare_digest(incoming_secret, known_secret):
        return True, 'verified_payment_secret'
    if known_secret and incoming_secret and incoming_secret != known_secret:
        return False, 'secret_mismatch'
    if known_secret and not incoming_secret:
        return False, 'missing_secret'
    if NV0_TOSS_MOCK:
        return True, 'mock_mode'
    return False, 'unverified_payment_webhook'


def client_ip(request: Request) -> str:
    forwarded = clean(request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for"))
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    return clean(getattr(request.client, "host", "")) or "unknown"


def hit_rate_limit(bucket: str, *, limit: int, window_seconds: int = 60) -> bool:
    now = time.monotonic()
    q = _WRITE_LIMIT_BUCKETS[bucket]
    while q and now - q[0] > window_seconds:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


def maybe_limit_request(request: Request) -> Response | None:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    path = request.url.path
    ip = client_ip(request)
    if path.startswith("/api/admin/"):
        limited = hit_rate_limit(f"admin:{ip}:{path}", limit=ADMIN_RATE_LIMIT_PER_MIN)
    elif path == "/api/public/portal/lookup":
        limited = hit_rate_limit(f"portal:{ip}:{path}", limit=PORTAL_RATE_LIMIT_PER_MIN)
    elif path in {"/api/public/orders", "/api/public/orders/reserve", "/api/public/payments/toss/confirm", "/api/public/demo-requests", "/api/public/contact-requests"}:
        limited = hit_rate_limit(f"public:{ip}:{path}", limit=PUBLIC_RATE_LIMIT_PER_MIN)
    else:
        limited = False
    if not limited:
        return None
    return JSONResponse(status_code=429, content={"ok": False, "detail": "요청이 잠시 몰렸습니다. 잠시 후 다시 시도해 주세요."})


def enforce_body_size(request: Request) -> Response | None:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    raw_length = clean(request.headers.get("content-length"))
    if raw_length.isdigit() and int(raw_length) > MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"ok": False, "detail": "요청 본문이 너무 큽니다."})
    return None


def parse_price_to_amount(price: str) -> int:
    text = clean(price).replace(",", "")
    if text.endswith("만"):
        number = clean(text[:-1])
        if number.isdigit():
            return int(number) * 10000
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits or "0")


def ensure_dist_ready() -> None:
    index_file = DIST / "index.html"
    if index_file.exists():
        return
    build_script = ROOT / "build.py"
    if not build_script.exists():
        raise RuntimeError("dist 폴더와 build.py가 모두 없습니다.")
    subprocess.run(["python3", str(build_script)], check=True, cwd=str(ROOT))
    if not index_file.exists():
        raise RuntimeError("dist 생성에 실패했습니다.")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def init_db() -> None:
    ensure_dist_ready()
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                record_type TEXT NOT NULL,
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_records_type_created ON records(record_type, created_at DESC)")
        conn.commit()
    ensure_seed_publications()


def load_records(record_type: str) -> list[dict[str, Any]]:
    with _CACHE_LOCK:
        cached = _RECORD_CACHE.get(record_type)
        if cached is not None:
            return deepcopy(cached)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT payload FROM records WHERE record_type = ? ORDER BY created_at DESC, id DESC",
            (record_type,),
        ).fetchall()
    records = [json.loads(row["payload"]) for row in rows]
    with _CACHE_LOCK:
        _RECORD_CACHE[record_type] = records
    return deepcopy(records)


def get_record(record_type: str, record_id: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT payload FROM records WHERE record_type = ? AND id = ?",
            (record_type, record_id),
        ).fetchone()
    return json.loads(row["payload"]) if row else None


def upsert_record(record_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(payload)
    payload.setdefault("id", uid(record_type[:3]))
    created_at = payload.get("createdAt") or payload.get("created_at") or now_iso()
    payload["createdAt"] = created_at
    payload.setdefault("updatedAt", created_at)
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO records(record_type, id, payload, created_at) VALUES (?, ?, ?, ?)",
            (record_type, payload["id"], json.dumps(payload, ensure_ascii=False), created_at),
        )
        conn.commit()
    invalidate_cache(record_type)
    return payload


def delete_all_records() -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM records")
        conn.commit()
    invalidate_cache()


def state_payload() -> dict[str, Any]:
    global _STATE_CACHE
    ensure_seed_publications()
    with _CACHE_LOCK:
        if _STATE_CACHE is not None:
            return deepcopy(_STATE_CACHE)
    state = {name: load_records(name) for name in STORE_TYPES}
    with _CACHE_LOCK:
        _STATE_CACHE = state
    return deepcopy(state)


def export_state_payload() -> dict[str, Any]:
    return {
        "exportedAt": now_iso(),
        "db": str(DB_PATH),
        "state": state_payload(),
    }


def cached_json_bytes(cache_key: str, payload_factory) -> bytes:
    with _CACHE_LOCK:
        cached = _JSON_CACHE.get(cache_key)
        if cached is not None:
            return cached
    payload = payload_factory()
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode('utf-8')
    with _CACHE_LOCK:
        _JSON_CACHE[cache_key] = encoded
    return encoded


def import_state_payload(payload: dict[str, Any], *, replace: bool = True) -> dict[str, Any]:
    state = payload.get("state") if isinstance(payload, dict) else None
    if not isinstance(state, dict):
        raise HTTPException(status_code=400, detail="state 형식이 올바르지 않습니다.")
    if replace:
        delete_all_records()
    for record_type in STORE_TYPES:
        for item in state.get(record_type, []) or []:
            if isinstance(item, dict):
                upsert_record(record_type, item)
    ensure_seed_publications()
    return state_payload()


def product_name(key: str) -> str:
    return PRODUCTS.get(key, {}).get("name", key)


def product_prefix(key: str) -> str:
    mapping = {"veridion": "VER", "clearport": "CLR", "grantops": "GRT", "draftforge": "DRF"}
    return mapping.get(key, clean(key)[:3].upper() or "GEN")


def validate_product(key: str) -> None:
    if key not in PRODUCTS:
        raise HTTPException(status_code=400, detail="유효한 제품을 선택하세요.")


def validate_plan(product_key: str, plan_name: str) -> None:
    plans = PRODUCTS.get(product_key, {}).get("plans", [])
    if not any(item["name"] == plan_name for item in plans):
        raise HTTPException(status_code=400, detail="유효한 플랜을 선택하세요.")


def plan_info(product_key: str, plan_name: str) -> dict[str, Any]:
    for item in PRODUCTS.get(product_key, {}).get("plans", []):
        if item["name"] == plan_name:
            return {
                "display": item.get("price", "-"),
                "amount": parse_price_to_amount(item.get("price", "0")),
                "note": item.get("note", ""),
            }
    return {"display": "-", "amount": 0, "note": ""}


def next_status_for_payment(payment_status: str) -> str:
    mapping = {
        "ready": "payment_pending",
        "pending": "payment_pending",
        "paid": "delivered",
        "failed": "payment_failed",
        "cancelled": "payment_cancelled",
        "expired": "payment_failed",
    }
    return mapping.get(payment_status, "payment_pending")


PRODUCT_RESULT_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "veridion": {
        "output_previews": [
            "대표 URL 기준으로 개인정보·전자상거래·표시광고·청소년 보호 구간을 페이지별로 정리한 준수 스캔 결과입니다.",
            "누락 항목별 일반적인 과태료 범위를 비교 카드로 보여 주어 지금 가장 먼저 고칠 항목을 바로 고를 수 있게 합니다.",
            "법적 위험도와 운영 영향도를 함께 본 우선순위 대시보드로, 적은 인원에서도 오늘 바로 움직일 순서를 제시합니다.",
            "개인정보처리방침, 결제 안내, 환불 고지, 광고 표시 문구, 쿠키·추적 동의 문구를 현재 사이트 흐름에 맞게 다시 씁니다.",
            "법령 소스가 갱신될 때 영향을 받을 가능성이 높은 페이지와 재점검 트리거를 함께 묶은 알림 설계입니다.",
            "개발·디자인·운영 담당자가 바로 적용할 수 있도록 화면 위치와 수정 순서를 체크리스트 형태로 정리합니다.",
        ],
        "quick_wins": [
            "필수 고지 누락과 동의 문구 누락을 먼저 잡아 과태료 가능성이 큰 구간부터 줄입니다.",
            "체크아웃·회원가입·문의폼처럼 고객이 바로 마주치는 화면을 우선 정리해 신뢰 손실을 줄입니다.",
            "법령 변경 감시를 붙여 전체 사이트를 다시 뒤지는 시간을 아낍니다.",
        ],
        "value_drivers": [
            "법률 자문 전에 운영자가 먼저 손볼 수 있는 위험 구간을 좁혀 불필요한 왕복을 줄입니다.",
            "무엇이 문제인지보다 무엇부터 고칠지를 먼저 보여 주어 실제 수정 속도를 높입니다.",
            "점검과 수정안, 재점검 큐를 한 묶음으로 받아 다음 변경 때도 재사용할 수 있습니다.",
        ],
        "success_metrics": [
            "핵심 공개 페이지별 준수 상태가 한 화면에서 구분됩니다.",
            "우선 수정 10항목 이내로 즉시 실행 범위가 정리됩니다.",
            "변경 감시 후 재점검 대상 페이지가 자동으로 좁혀집니다.",
        ],
        "issuance": [
            "준수 스캔 리포트와 과태료 미리보기 표를 같은 조회 코드로 묶어 발행합니다.",
            "맞춤 약관·고지·배너 수정안을 바로 적용 가능한 문장 단위로 제공합니다.",
            "법령 변경 감시용 재점검 큐와 운영 체크리스트를 함께 제공합니다.",
        ],
        "professional_angles": [
            "확정 법률 자문과 자동 점검 결과를 구분해 과도한 단정 표현을 피합니다.",
            "과태료는 확정 금액이 아니라 범위형 미리보기로 제시해 실무 판단에 쓰기 쉽게 만듭니다.",
            "페이지 위치와 문구 수정 순서를 같이 제시해 개발·디자인·운영이 같은 화면을 보게 합니다.",
        ],
        "objection_answers": [
            "법을 다 읽기 전에 어디부터 손봐야 하는지부터 보여 주므로 시작 장벽이 낮습니다.",
            "외부 자문 전에도 운영팀이 먼저 줄일 수 있는 위험을 바로 찾을 수 있습니다.",
            "한 번 점검하고 끝나는 문서가 아니라 변경 감시와 재점검 큐까지 함께 남습니다.",
        ],
    },
    "clearport": {
        "output_previews": [
            "준비 서류를 고객용·내부용 기준으로 나눠 어떤 문서가 왜 필요한지 한눈에 정리합니다.",
            "누락 서류와 보완 요청을 바로 복붙해 보낼 수 있도록 상황별 템플릿 묶음으로 제공합니다.",
            "접수 전·검토 중·보완 요청·완료 안내 단계마다 다른 고객 안내 문장을 실제 순서대로 정리합니다.",
            "자주 묻는 질문과 예외 상황 답변 초안까지 묶어 담당자마다 말이 달라지는 문제를 줄입니다.",
            "내부 공유용 운영 체크리스트로 담당자 교체나 인수인계에도 기준이 흔들리지 않게 합니다.",
        ],
        "quick_wins": [
            "가장 자주 빠지는 준비 서류를 한 장 기준표로 고정합니다.",
            "보완 요청 문장을 템플릿화해 응답 시간을 줄입니다.",
            "예외 질문 답변을 미리 정리해 고객 안내 피로를 낮춥니다.",
        ],
        "value_drivers": [
            "담당자마다 다른 설명을 줄여 고객 왕복 횟수와 일정 흔들림을 낮춥니다.",
            "문장까지 표준화해 실제 응대 시간이 눈에 띄게 줄어듭니다.",
            "서류 기준과 안내 문장을 재사용 자산으로 남겨 다음 요청에도 바로 씁니다.",
        ],
        "success_metrics": [
            "준비 서류 기준표 1종과 보완 요청 템플릿 세트가 즉시 사용 가능 상태로 정리됩니다.",
            "고객 안내 단계별 문장이 고정되어 담당자 간 편차가 줄어듭니다.",
            "반복 질문 항목이 FAQ 초안으로 전환됩니다.",
        ],
        "issuance": [
            "준비 서류 기준표와 보완 요청 템플릿을 바로 발행합니다.",
            "고객 안내 문장과 FAQ 초안을 고객용/내부용으로 나눠 제공합니다.",
            "내부 운영 체크리스트를 함께 묶어 재사용 가능 상태로 전달합니다.",
        ],
        "professional_angles": [
            "누가 답해도 같은 안내가 나가도록 기준표와 문장을 분리 설계합니다.",
            "책임 범위와 기한처럼 오해가 생기기 쉬운 문장은 명시형으로 다시 씁니다.",
            "예외 상황은 본문에 섞지 않고 FAQ·예외 메모로 분기해 현장 혼선을 줄입니다.",
        ],
        "objection_answers": [
            "서류가 자주 바뀌더라도 기준표와 예외 메모를 함께 남겨 수정 비용을 줄일 수 있습니다.",
            "한 사람의 노하우에 묶이지 않도록 바로 공유 가능한 문장 체계로 정리됩니다.",
            "고객 안내와 내부 기준을 분리해 인수인계에도 흔들리지 않는 구조를 만듭니다.",
        ],
    },
    "grantops": {
        "output_previews": [
            "공고 본문에서 반드시 챙겨야 할 요구사항과 평가 포인트를 짧은 해석본으로 정리합니다.",
            "제출 전에 빠지기 쉬운 자료를 체크리스트로 묶어 누락 위험을 낮춥니다.",
            "마감 역산 일정표와 역할 분담표로 누가 언제 무엇을 끝내야 하는지 명확히 정리합니다.",
            "보완 요청이나 추가 증빙 요구가 들어왔을 때 바로 대응할 수 있는 메모와 문장 예시를 제공합니다.",
            "다음 공고에도 재사용할 수 있도록 운영본 형태로 정리해 반복 비용을 줄입니다.",
        ],
        "quick_wins": [
            "공고 해석과 제출 준비를 한 문서로 묶어 시작 지연을 줄입니다.",
            "마감 직전 급하게 찾던 필수 자료를 체크리스트로 먼저 고정합니다.",
            "역할 분담을 명확히 해 누가 무엇을 놓쳤는지 바로 보이게 합니다.",
        ],
        "value_drivers": [
            "공고를 읽는 시간보다 실제 제출 구조를 잡는 데 쓰는 시간을 줄입니다.",
            "마감 전 반복되는 자료 확인과 역할 확인 비용을 크게 낮춥니다.",
            "다음 공고에도 재활용할 수 있는 운영본이 남아 누적 가치가 커집니다.",
        ],
        "success_metrics": [
            "제출 체크리스트와 역할 분담표가 동시에 준비됩니다.",
            "마감 역산 일정이 주 단위가 아닌 행동 단위로 보입니다.",
            "보완 대응 포인트가 사전에 정리되어 제출 직전 혼선을 줄입니다.",
        ],
        "issuance": [
            "공고 해석본과 제출 체크리스트를 같은 조회 코드로 묶어 발행합니다.",
            "일정표·역할 분담표·보완 대응 메모를 즉시 공유 가능한 형태로 제공합니다.",
            "다음 공고용 운영본까지 함께 제공해 반복 준비 시간을 줄입니다.",
        ],
        "professional_angles": [
            "필수 제출물과 참고 자료를 혼동하지 않게 우선순위를 분리합니다.",
            "마감 직전 병목인 승인 단계는 별도로 표시해 실제 일정 리스크를 먼저 드러냅니다.",
            "애매한 해석은 단정하지 않고 공고 원문 기준 확인 질문으로 남깁니다.",
        ],
        "objection_answers": [
            "지금 당장 모든 자료가 없어도, 무엇부터 준비하면 되는지 행동 순서부터 잡을 수 있습니다.",
            "이번 공고뿐 아니라 다음 공고에도 재사용할 수 있는 구조로 남기기 때문에 누적 가치가 큽니다.",
            "마감 직전 커뮤니케이션 비용을 줄이는 데 초점을 둬 적은 인원에서도 운영하기 쉽습니다.",
        ],
    },
    "draftforge": {
        "output_previews": [
            "검토 단계가 어디에서 자꾸 멈추는지 흐름 단위로 정리해 병목을 먼저 드러냅니다.",
            "승인 기준이 흔들리지 않도록 체크리스트를 채널별로 나눠 제공합니다.",
            "랜딩, 배너, 메일, 상세페이지 등 채널별 최종본을 비교표로 묶어 혼선을 줄입니다.",
            "버전명과 파일 관리 기준을 고정해 최종본이 뒤바뀌는 사고를 줄입니다.",
            "발행 직전 QA 체크리스트까지 포함해 마지막 검수 시간을 줄입니다.",
        ],
        "quick_wins": [
            "검토와 승인 기준을 먼저 고정해 수정 왕복을 줄입니다.",
            "채널별 최종본 비교표로 최신 파일 혼선을 바로 줄입니다.",
            "발행 직전 QA 항목을 체크리스트화해 실수를 예방합니다.",
        ],
        "value_drivers": [
            "초안 이후 병목 구간을 줄여 콘텐츠 일정 지연을 낮춥니다.",
            "최종본 혼선과 버전 사고를 줄여 재작업 비용을 줄입니다.",
            "검토·승인·발행 기준을 자산화해 새 사람도 같은 기준으로 운영할 수 있습니다.",
        ],
        "success_metrics": [
            "채널별 최종본 비교표와 승인 체크리스트가 함께 정리됩니다.",
            "버전명과 파일 관리 기준이 고정됩니다.",
            "발행 직전 QA 항목이 누락 없이 체크됩니다.",
        ],
        "issuance": [
            "검토 흐름 정리본과 승인 체크리스트를 즉시 발행합니다.",
            "채널별 최종본 비교표와 버전 관리 기준을 함께 제공합니다.",
            "발행 직전 QA 체크리스트를 운영본으로 남겨 반복 사용 가능하게 합니다.",
        ],
        "professional_angles": [
            "반영/보류/제외 사유를 나눠 의견 충돌을 문장으로 정리합니다.",
            "채널별 형식 제약이 다르면 단일 본문 대신 분기 최종본을 만듭니다.",
            "버전명과 게시본이 엇갈리지 않도록 QA 전 마지막 비교 기준을 둡니다.",
        ],
        "objection_answers": [
            "초안이 이미 있어도 승인과 최종본 정리에서 잃는 시간을 크게 줄일 수 있습니다.",
            "버전 사고와 누락을 줄여 한 번의 발행 결과가 더 안정적으로 남습니다.",
            "이번 프로젝트 기준을 다음 작업에도 그대로 재사용할 수 있어 축적 가치가 큽니다.",
        ],
    },
}

QUALITY_SCORE_BLUEPRINT = [
    ("맞춤도", 20),
    ("구체성", 15),
    ("실행 가능성", 20),
    ("전문성", 15),
    ("설득력", 10),
    ("발행 준비도", 10),
    ("재사용성", 10),
]


def parse_note_signals(note: str) -> dict[str, str]:
    text = clip_text(note, 4000)
    lines = [clean(item) for item in re.split(r"[\r\n]+", text) if clean(item)]
    mapped: dict[str, str] = {"raw": text}
    aliases = {
        "키워드": "keywords",
        "참고 링크": "reference",
        "긴급도": "urgency",
        "추가 요청": "request",
        "체험 목표": "goal",
        "연락처": "phone",
    }
    for line in lines:
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        mapped_key = aliases.get(clean(key), clean(key).lower())
        mapped[mapped_key] = clean(value)
    if not mapped.get("goal") and lines:
        mapped["goal"] = lines[0]
    return mapped


def architecture_for(target: dict[str, Any]) -> dict[str, Any]:
    return target.get("architecture") or {}


def first_non_empty(*values: Any) -> str:
    for value in values:
        cleaned = clean(str(value or ""))
        if cleaned:
            return cleaned
    return ""


def build_priority_sequence(target: dict[str, Any], company: str, goal: str) -> list[str]:
    workflow = target.get("workflow") or []
    steps: list[str] = []
    for idx, item in enumerate(workflow[:4], start=1):
        prefix = f"{idx}. "
        if idx == 1:
            steps.append(prefix + f"{company or '고객사'}의 현재 상황과 목표({goal})를 기준으로 범위를 먼저 잠급니다. {item}")
        elif idx == 2:
            steps.append(prefix + item)
        elif idx == 3:
            steps.append(prefix + f"실제 적용이나 전달에 바로 쓰이도록 {item}")
        else:
            steps.append(prefix + item)
    return steps[:4]


def build_quality_scorecard(target: dict[str, Any], company: str, goal: str, stage: str) -> dict[str, Any]:
    arch = architecture_for(target)
    templates = PRODUCT_RESULT_TEMPLATES.get(target.get("key", ""), {})
    stage_label = "데모 미리보기" if stage == "demo" else "결제 후 발행 결과"
    reasons = {
        "맞춤도": f"{company or '고객사'}와 목표({goal})를 중심으로 결과 요약, 출력물, 다음 행동이 같은 흐름으로 맞춰집니다.",
        "구체성": f"출력물 제목만 나열하지 않고 포함 내용, 바로 쓸 행동, 적용 이유를 함께 제시합니다.",
        "실행 가능성": f"우선순위, 체크리스트, 다음 행동, 발행 준비 상태를 함께 제공해 바로 움직일 수 있습니다.",
        "전문성": first_non_empty(*(templates.get('professional_angles') or [])) or first_non_empty(*(arch.get('quality_gates') or [])) or f"{target.get('name')}의 품질 게이트 기준을 따라 과도한 단정 대신 실무 적용 가능한 설명으로 정리합니다.",
        "설득력": f"결과가 왜 필요한지와 비용 대비 남는 자산을 분명하게 설명해 결제 판단을 돕습니다.",
        "발행 준비도": f"고객 전달 요약, 상세 실행 자료, 자동 발행 글이 같은 조회 코드 기준으로 이어집니다.",
        "재사용성": f"이번 결과를 다음 수정·재점검·재발행에도 다시 쓸 수 있게 운영 자산 형태로 묶습니다.",
    }
    items = [{"label": label, "score": weight, "max": weight, "reason": reasons[label]} for label, weight in QUALITY_SCORE_BLUEPRINT]
    return {
        "stage": stage,
        "stageLabel": stage_label,
        "earned": sum(item["score"] for item in items),
        "total": sum(weight for _, weight in QUALITY_SCORE_BLUEPRINT),
        "grade": "A+",
        "headline": f"{target.get('name')} {stage_label} 품질 기준표",
        "items": items,
        "summary": f"NV0 내부 품질 게이트 100점 배점 기준으로, 맞춤도·실행 가능성·전문성·발행 준비도까지 빠짐없이 채운 상태로 생성합니다.",
    }


def build_output_items(product_key: str, target: dict[str, Any], company: str, plan_name: str, goal: str, signals: dict[str, str] | None = None) -> list[dict[str, str]]:
    signals = signals or {}
    templates = PRODUCT_RESULT_TEMPLATES.get(product_key, {})
    arch = architecture_for(target)
    previews = templates.get("output_previews") or []
    contracts = arch.get("output_contract") or []
    quality_gates = arch.get("quality_gates") or []
    performance_targets = arch.get("performance_targets") or []
    outputs: list[dict[str, str]] = []
    keywords = signals.get("keywords") or target.get("tag") or "핵심 기준"
    for idx, item in enumerate(target.get("outputs", [])):
        preview = previews[idx] if idx < len(previews) else f"{company or '고객사'} 상황에 맞춰 {item}을 실제 운영 기준으로 정리합니다."
        what_included = contracts[idx] if idx < len(contracts) else f"{item}의 핵심 판단 기준, 바로 적용할 문장, 공유용 요약을 한 번에 포함합니다."
        if len(clean(what_included)) < 15:
            what_included = f"{what_included}. {company or '고객사'}가 실제 업무에 바로 옮길 수 있도록 판단 기준과 적용 포인트를 함께 넣습니다."
        expert_lens = quality_gates[idx % len(quality_gates)] if quality_gates else f"{target['name']}의 품질 기준을 따라 과도한 단정 없이 실무 적용 가능한 수준으로 정리합니다."
        if len(clean(expert_lens)) < 15:
            expert_lens = f"{expert_lens}. 자동 생성 문장과 실제 검토가 필요한 지점을 분리해 안내합니다."
        action_now = performance_targets[idx % len(performance_targets)] if performance_targets else f"{company or '고객사'}는 이 항목부터 먼저 적용하면 {goal}과 가장 가까운 개선을 바로 시작할 수 있습니다."
        if len(clean(action_now)) < 15:
            action_now = f"{action_now}. 적용 순서와 확인 기준을 함께 보며 바로 착수할 수 있게 정리합니다."
        buyer_value = f"{company or '고객사'}가 {keywords} 기준으로 무엇을 먼저 결정해야 하는지, 담당자 간 설명을 다시 맞추지 않아도 되게 만드는 결과물입니다."
        outputs.append({
            "title": item,
            "note": f"{target['name']} {plan_name} 기준 제공 항목 {idx + 1}",
            "preview": preview,
            "whatIncluded": what_included,
            "actionNow": action_now,
            "buyerValue": buyer_value,
            "expertLens": expert_lens,
            "whyItMatters": f"{company or '고객사'}가 지금 가장 먼저 판단하거나 적용해야 할 포인트를 바로 확인할 수 있게 돕습니다.",
            "deliveryState": "ready_to_issue",
        })
    return outputs


def build_delivery_assets(target: dict[str, Any], company: str, goal: str) -> list[dict[str, str]]:
    templates = PRODUCT_RESULT_TEMPLATES.get(target.get("key", ""), {})
    angles = templates.get("professional_angles") or []
    return [
        {
            "title": f"{target['name']} 고객 전달 요약",
            "description": f"{company or '고객사'} 기준 핵심 결과와 다음 행동을 먼저 읽기 쉬운 형태로 정리합니다.",
            "customerValue": f"담당자와 의사결정자가 같은 내용을 짧게 공유할 수 있어 내부 정리가 빨라집니다.",
            "usageMoment": f"첫 공유, 대표 보고, 내부 의사결정 정리 단계에서 바로 씁니다.",
            "expertNote": angles[0] if angles else f"핵심 판단이 먼저 보이도록 길이보다 우선순위를 앞세웁니다.",
            "status": "ready",
        },
        {
            "title": f"{target['name']} 상세 실행 자료",
            "description": "출력물별 상세 설명, 우선순위, 즉시 적용 포인트를 포함한 본문 자료입니다.",
            "customerValue": f"작업자 입장에서 바로 손을 대야 할 항목과 검토 포인트를 함께 확인할 수 있습니다.",
            "usageMoment": f"실제 수정, 보완, 재작성, 발송 전 검토 단계에서 사용합니다.",
            "expertNote": angles[1] if len(angles) > 1 else f"설명형 문서가 아니라 행동형 문서가 되도록 세부 실행 포인트를 넣습니다.",
            "status": "ready",
        },
        {
            "title": f"{target['name']} 자동 발행 글 2건 이상",
            "description": "제품 설명, 공개 게시판, 고객 포털에서 같은 조회 코드로 이어서 확인할 수 있는 자동 발행 콘텐츠입니다.",
            "customerValue": f"결과를 전달하는 데서 끝나지 않고, 대외 설명과 내부 공유까지 한 번에 이어집니다.",
            "usageMoment": f"고객 설명, 내부 아카이브, 후속 문의 대응에 재사용합니다.",
            "expertNote": angles[2] if len(angles) > 2 else f"같은 내용을 보는 화면이 달라도 메시지는 흔들리지 않게 유지합니다.",
            "status": "ready",
        },
    ]


def build_issuance_bundle(target: dict[str, Any], company: str) -> list[dict[str, str]]:
    templates = PRODUCT_RESULT_TEMPLATES.get(target.get("key", ""), {})
    angles = templates.get("professional_angles") or []
    return [
        {
            "title": f"{target['name']} 발행 준비 {idx + 1}",
            "description": item,
            "customerValue": f"{company or '고객사'}가 받은 자료를 그대로 공유하고 다음 행동으로 이어가기 쉽게 정리합니다.",
            "usageMoment": ["즉시 공유", "실행 착수", "후속 점검"][(idx if idx < 3 else 2)],
            "expertNote": angles[idx % len(angles)] if angles else f"발행 정보가 곧바로 실무 행동으로 이어지도록 구성합니다.",
            "status": "ready",
        }
        for idx, item in enumerate((templates.get("issuance") or [])[:3])
    ]


def build_professional_notes(target: dict[str, Any], product_key: str) -> list[str]:
    templates = PRODUCT_RESULT_TEMPLATES.get(product_key, {})
    arch = architecture_for(target)
    notes = list(templates.get("professional_angles") or []) + list(arch.get("quality_gates") or [])
    unique: list[str] = []
    seen: set[str] = set()
    for item in notes:
        normalized = clean(item)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
        if len(unique) >= 4:
            break
    return unique


def build_demo_preview(product_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    target = PRODUCTS[product_key]
    company = clip_text(payload.get("company"), 160) or "샘플 회사"
    goal = clip_text(payload.get("goal") or payload.get("need"), 240) or target.get("problem") or target.get("summary")
    keywords = clip_text(payload.get("keywords"), 240) or target.get("tag") or "핵심 항목"
    plan_name = clean(payload.get("plan") or "Starter")
    templates = PRODUCT_RESULT_TEMPLATES.get(product_key, {})
    signals = {"goal": goal, "keywords": keywords}
    sample_outputs = build_output_items(product_key, target, company, plan_name, goal, signals)[:3]
    priority = build_priority_sequence(target, company, goal)
    scorecard = build_quality_scorecard(target, company, goal, "demo")
    objections = (templates.get("objection_answers") or [])[:3]
    return {
        "headline": f"{company} 기준 {target['name']} 샘플 결과",
        "summary": f"{goal}을 기준으로 지금 바로 확인할 수 있는 샘플 결과입니다. 결제 전에도 어떤 결과물이 나오는지 형태와 깊이를 먼저 보여 드립니다.",
        "company": company,
        "goal": goal,
        "keywords": keywords,
        "diagnosisSummary": f"현재 가장 중요한 문제는 {target.get('problem')}. 이 데모는 그 문제를 설명하는 데서 끝나지 않고, 먼저 손볼 항목과 결과물 수준을 같이 보여 주는 데 초점을 둡니다.",
        "sampleOutputs": sample_outputs,
        "quickWins": (templates.get("quick_wins") or [])[:3],
        "valueDrivers": (templates.get("value_drivers") or [])[:3],
        "successMetrics": (templates.get("success_metrics") or [])[:3],
        "prioritySequence": priority,
        "expertNotes": build_professional_notes(target, product_key)[:3],
        "objectionHandling": objections,
        "scorecard": scorecard,
        "ctaHint": f"이 조건으로 진행하면 {target['name']} {plan_name} 플랜 결과와 자동 발행 자료가 같은 조회 코드로 이어집니다.",
        "closingArgument": f"샘플 결과만으로도 무엇을 받게 되는지, 왜 비용보다 크게 남는지, 결제 후 어떤 자료가 발행되는지까지 미리 확인할 수 있게 구성했습니다.",
    }


def build_result_pack(product_key: str, plan_name: str, company: str, note: str = "") -> dict[str, Any]:
    target = PRODUCTS[product_key]
    signals = parse_note_signals(note)
    templates = PRODUCT_RESULT_TEMPLATES.get(product_key, {})
    goal = signals.get("goal") or target.get("problem") or target.get("summary")
    outputs = build_output_items(product_key, target, company, plan_name, goal, signals)
    delivery_assets = build_delivery_assets(target, company, goal)
    scorecard = build_quality_scorecard(target, company, goal, "delivery")
    priority = build_priority_sequence(target, company, goal)
    expert_notes = build_professional_notes(target, product_key)
    return {
        "title": f"{target['name']} {plan_name} 실행 결과",
        "summary": f"{company or '고객사'} 상황에 맞춘 {target['name']} {plan_name} 플랜 결과 자료가 준비되었습니다.",
        "outcomeHeadline": f"{company or '고객사'}가 지금 바로 판단하고 실행할 수 있는 핵심 결과를 먼저 정리했습니다.",
        "executiveSummary": f"이번 결과물은 {target.get('problem')} 상황을 빠르게 줄이기 위해, 요약 판단 자료와 세부 실행 자료, 발행 자산을 하나의 조회 코드 아래에서 함께 쓰도록 설계했습니다.",
        "clientContext": {
            "company": company or '고객사',
            "goal": goal,
            "keywords": signals.get("keywords") or target.get("tag") or '',
            "reference": signals.get("reference") or '',
            "urgency": signals.get("urgency") or '',
        },
        "scorecard": scorecard,
        "outputs": outputs,
        "quickWins": (templates.get("quick_wins") or [])[:3],
        "valueDrivers": (templates.get("value_drivers") or [])[:3],
        "successMetrics": (templates.get("success_metrics") or [])[:3],
        "prioritySequence": priority,
        "expertNotes": expert_notes[:4],
        "objectionHandling": (templates.get("objection_answers") or [])[:3],
        "issuanceBundle": build_issuance_bundle(target, company),
        "deliveryAssets": delivery_assets,
        "nextActions": (target.get("workflow") or [])[:4],
        "valueNarrative": f"{target['name']}은 설명용 문서 하나만 전달하는 구조가 아니라, 즉시 판단할 요약·세부 실행 자료·자동 발행 결과를 함께 묶어 받은 비용보다 더 오래 재사용할 수 있는 운영 자산으로 남기도록 설계했습니다. 이번 결과는 지금 당장 움직일 일과 다음 변경 때 다시 꺼내 쓸 기준을 동시에 남깁니다.",
        "buyerDecisionReason": f"단순 샘플이나 템플릿이 아니라 {company or '고객사'}의 목표와 운영 방식에 맞춘 판단 자료, 실행 자료, 발행 자산이 한 번에 준비되기 때문에 결제 직후 체감 가치가 높습니다.",
        "generatedAt": now_iso(),
    }

def article_slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9가-힣]+", "-", clean(text).lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or uuid4().hex[:8]


def compact_keywords(*values: str, limit: int = 6) -> list[str]:
    seen: set[str] = set()
    keywords: list[str] = []
    stop = {"그리고", "하지만", "이렇게", "바로", "가장", "먼저", "위한", "있는", "하기", "으로", "에서", "에게", "입니다", "하기", "지금"}
    for value in values:
        for raw in re.split(r"[\s,/|·]+", clean(value)):
            token = raw.strip("-·:,.!?()[]{}\"'")
            if len(token) < 2 or token in stop:
                continue
            lowered = token.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            keywords.append(token)
            if len(keywords) >= limit:
                return keywords
    return keywords


def smooth_phrases(items: list[str], sep: str = " · ") -> str:
    cleaned = [re.sub(r"[\s.]+$", "", clean(item)) for item in items if clean(item)]
    return sep.join(cleaned[:3])


def build_article_sections(target: dict[str, Any], *, title: str, summary: str, cta_label: str, company: str = "", plan: str = "", order_code: str = "", topic_summary: str = "") -> list[dict[str, str]]:
    outputs = target.get("outputs") or []
    values = target.get("value_points") or []
    fit_for = target.get("fit_for") or []
    workflow = target.get("workflow") or []
    outputs_text = smooth_phrases(outputs) or "결과 자료"
    value_text = smooth_phrases(values, sep=" / ") or target.get("summary", "")
    fit_text = smooth_phrases(fit_for) or "실무 팀"
    workflow_text = smooth_phrases(workflow, sep=" → ") or "콘텐츠 허브 → 제품 설명 → 데모 시연 → 결제 → 결과 전달"
    proof = f"조회 코드 {order_code}로 정상작동 상태와 자동발행 글을 함께 확인할 수 있습니다." if order_code else "무료 샘플과 데모 시연 자료부터 확인한 뒤 결제 여부를 결정하실 수 있습니다."
    audience = company or "운영팀"
    plan_line = f"{plan} 플랜 기준으로 " if plan else ""
    focus = clean(title or topic_summary or target.get("summary", ""))
    return [
        {
            "heading": "이런 팀이라면 먼저 읽어보세요",
            "body": f"{summary} 특히 {audience}처럼 적은 인원으로 반복 업무를 줄이고 싶은 팀에 잘 맞습니다. 이 글에서는 {focus}을 중심으로 어떤 지점부터 손보면 좋은지 차분하게 정리합니다.",
        },
        {
            "heading": "왜 기존 방식이 자꾸 막히는지",
            "body": f"문제는 업무량보다 매번 설명이 달라지고 기준이 흩어져 있다는 점입니다. 같은 요청도 사람마다 표현이 달라지면 검토, 보완, 전달이 길어지고 결국 다음 행동이 느려집니다. {target.get('problem', target.get('summary', ''))}",
        },
        {
            "heading": f"{target.get('name')}이 실제로 줄여주는 일",
            "body": f"{plan_line}{target.get('name')}은 {value_text} 같은 핵심 작업을 더 짧은 흐름으로 정리합니다. 결과적으로 {outputs_text}를 한 번에 준비하고, 콘텐츠 허브·제품 설명·데모 시연·결제·결과 전달까지 같은 흐름으로 이어 주기 때문에 중간 설명 비용이 줄어듭니다.",
        },
        {
            "heading": "콘텐츠 허브를 먼저 읽으면 좋은 이유",
            "body": f"누가 요청을 넣는지, 어떤 기준으로 검토하는지, 결과물을 어디서 확인하는지 세 가지만 먼저 정해도 시작이 훨씬 쉬워집니다. NV0 안에서는 {workflow_text} 흐름으로 이 기준을 한 줄로 맞춰 둘 수 있습니다.",
        },
        {
            "heading": "이렇게 시작하면 가장 부담이 적습니다",
            "body": f"처음부터 큰 전환을 하기보다 가장 자주 반복되는 한 가지 업무를 골라 무료 샘플과 데모 시연 자료부터 확인해 보세요. {fit_text}처럼 빠르게 비교가 필요한 팀이라면 작은 테스트만으로도 도입 판단이 빨라집니다. {proof}",
        },
        {
            "heading": "다음 행동 안내",
            "body": f"이 글이 지금 상황과 맞는다면 {cta_label} 버튼으로 제품 상세를 먼저 확인해 보세요. 제품 설명, 데모 시연, 결제, 결과 전달까지 같은 흐름으로 이어지기 때문에 따로 헤매지 않고 바로 검토를 이어갈 수 있습니다.",
        },
    ]


def render_article_html(target: dict[str, Any], *, summary: str, sections: list[dict[str, str]], keywords: list[str], cta_label: str) -> str:
    chips = ''.join(f'<li>{escape(item)}</li>' for item in keywords)
    section_html = ''.join(
        f"<section><h4>{escape(item['heading'])}</h4><p>{escape(item['body'])}</p></section>"
        for item in sections
    )
    outputs = ''.join(f'<li>{escape(item)}</li>' for item in (target.get('outputs') or [])[:4])
    return (
        f"<div class='article-shell'><p class='article-lead'>{escape(summary)}</p>"
        f"<ul class='article-keywords'>{chips}</ul>"
        f"<div class='article-sections'>{section_html}</div>"
        f"<aside class='article-cta-box'><strong>{escape(target.get('name', 'NV0'))}으로 바로 이어서 검토할 수 있습니다</strong>"
        f"<p>결과물 예시: {escape(', '.join((target.get('outputs') or [])[:3]) or '결과 자료')}</p>"
        f"<ul class='clean article-output-list'>{outputs}</ul>"
        f"<p>마음이 정리되면 {escape(cta_label)}로 바로 이어가 보세요.</p></aside></div>"
    )


def build_publication_payload(*, product_key: str, title: str, summary: str, source: str, code: str, created_at: str | None = None, cta_label: str | None = None, cta_href: str | None = None, order: dict[str, Any] | None = None, topic_summary: str = "", publication_id: str | None = None) -> dict[str, Any]:
    target = PRODUCTS[product_key]
    automation = target.get("board_automation") or {}
    created = created_at or now_iso()
    cta = cta_label or automation.get("cta_label") or "제품 설명 보기"
    href = cta_href or automation.get("cta_href") or f"/products/{product_key}/index.html#intro"
    company = clean((order or {}).get("company"))
    plan = clean((order or {}).get("plan"))
    order_code = clean((order or {}).get("code"))
    sections = build_article_sections(target, title=title, summary=summary, cta_label=cta, company=company, plan=plan, order_code=order_code, topic_summary=topic_summary)
    keywords = compact_keywords(target.get("name", ""), target.get("tag", ""), title, summary, *(target.get("board_topics") or []))
    body = '\n\n'.join(f"{item['heading']}\n{item['body']}" for item in sections)
    article_html = render_article_html(target, summary=summary, sections=sections, keywords=keywords, cta_label=cta)
    return {
        "id": publication_id or uid("pub"),
        "product": product_key,
        "productName": target.get("name"),
        "title": title,
        "summary": summary,
        "body": body,
        "bodyHtml": article_html,
        "sections": sections,
        "keywords": keywords,
        "readMinutes": max(3, min(8, len(body) // 260 + 1)),
        "slug": article_slug(f"{target.get('name','nv0')}-{title}"),
        "format": "ai-hybrid-blog",
        "status": "published",
        "code": code,
        "createdAt": created,
        "updatedAt": created,
        "source": source,
        "ctaLabel": cta,
        "ctaHref": href,
        "topicSummary": topic_summary or summary,
        **({"orderId": order.get("id")} if order and order.get("id") else {}),
    }


def create_publications_for_order(order: dict[str, Any], forced_ids: list[str] | None = None) -> list[dict[str, Any]]:
    target = PRODUCTS[order["product"]]
    topics = (target.get("board_topics") or [])[:2]
    if not topics:
        topics = [
            f"{target['name']} 도입 전에 먼저 확인하면 좋은 기준",
            f"{target['name']}으로 지금 줄일 수 있는 반복 작업",
        ]
    forced_ids = forced_ids or []
    publications = []
    for idx, title in enumerate(topics):
        pub_id = forced_ids[idx] if idx < len(forced_ids) and forced_ids[idx] else uid("pub")
        if idx == 0:
            pub_title = f"{target['name']} {order.get('company') or order.get('email') or '고객'} 맞춤 제안"
            summary = f"{order.get('company') or order.get('email') or '고객'} 상황에 맞춰 {target['name']} {order['plan']} 플랜으로 바로 줄일 수 있는 일과 전자동 발행 제공 결과를 블로그 형식으로 정리했습니다."
        else:
            pub_title = title
            summary = f"{target.get('summary', '')} 조회 코드 {order['code']} 기준으로 함께 확인할 수 있는 AI 자동발행 안내 글입니다."
        pub = build_publication_payload(
            product_key=order["product"],
            title=pub_title,
            summary=summary,
            source="order-automation",
            code=order["code"],
            cta_label=(target.get("board_automation") or {}).get("cta_label") or "제품 설명 보기",
            cta_href=(target.get("board_automation") or {}).get("cta_href") or f"/products/{order['product']}/index.html#intro",
            order=order,
            topic_summary=title,
            publication_id=pub_id,
        )
        upsert_record("publications", pub)
        publications.append(pub)
    return publications


def ensure_seed_publications() -> None:
    if load_records("publications"):
        return
    now = datetime.now(timezone.utc)
    for idx, item in enumerate(PUBLIC_BOARD):
        created = now.replace(microsecond=0).isoformat()
        target = PRODUCTS[item["product"]]
        automation = target.get("board_automation") or {}
        pub = build_publication_payload(
            product_key=item["product"],
            title=item["title"],
            summary=item["summary"],
            source="seed",
            code=f"SEED-{idx + 1}",
            created_at=created,
            cta_label=automation.get("cta_label") or "제품 설명 보기",
            cta_href=automation.get("cta_href") or f"/products/{item['product']}/index.html#intro",
            topic_summary=item["summary"],
            publication_id=f"pubseed-{idx + 1}",
        )
        upsert_record("publications", pub)


def ensure_scheduled_publications() -> None:
    global _LAST_SCHEDULED_CHECK_MONOTONIC
    ensure_seed_publications()
    now_mono = time.monotonic()
    if now_mono - _LAST_SCHEDULED_CHECK_MONOTONIC < SCHEDULE_CHECK_MIN_INTERVAL_SECONDS:
        return
    with _SCHEDULE_LOCK:
        now_mono = time.monotonic()
        if now_mono - _LAST_SCHEDULED_CHECK_MONOTONIC < SCHEDULE_CHECK_MIN_INTERVAL_SECONDS:
            return
        now_dt = datetime.now(timezone.utc)
        for key, target in PRODUCTS.items():
            automation = target.get("board_automation") or {}
            if not automation.get("enabled"):
                continue
            interval_hours = int(automation.get("interval_hours") or 72)
            topics = automation.get("topics") or []
            if not topics:
                continue
            state_id = f"scheduler-{key}"
            state = get_record("scheduler", state_id) or {"id": state_id, "product": key, "lastPublishedAt": "", "topicIndex": 0, "createdAt": now_iso()}
            last_dt = parse_iso(state.get("lastPublishedAt"))
            if last_dt and (now_dt - last_dt).total_seconds() < interval_hours * 3600:
                continue
            topic_index = int(state.get("topicIndex") or 0) % len(topics)
            topic = topics[topic_index]
            created = now_iso()
            pub = build_publication_payload(
                product_key=key,
                title=topic.get("title") or f"{target.get('name')} 참고 글",
                summary=topic.get("summary") or target.get("summary", ""),
                source="scheduled",
                code=f"AUTO-{product_prefix(key)}-{topic_index + 1:03d}",
                created_at=created,
                cta_label=topic.get("ctaText") or automation.get("cta_label") or "제품 설명 보기",
                cta_href=automation.get("cta_href") or f"/products/{key}/index.html#intro",
                topic_summary=topic.get("summary") or target.get("summary", ""),
                publication_id=uid("pubsch"),
            )
            upsert_record("publications", pub)
            state["lastPublishedAt"] = created
            state["topicIndex"] = (topic_index + 1) % len(topics)
            state["updatedAt"] = created
            upsert_record("scheduler", state)
        _LAST_SCHEDULED_CHECK_MONOTONIC = time.monotonic()


def ensure_publications_for_order(order: dict[str, Any]) -> dict[str, Any]:
    publications = load_records("publications")
    publication_ids = [clean(item) for item in (order.get("publicationIds") or []) if clean(item)]
    existing = [item for item in publications if clean(item.get("id")) in publication_ids]
    if not existing and order.get("id"):
        existing = [item for item in publications if clean(item.get("orderId")) == clean(order.get("id"))]
    if not existing and order.get("code"):
        existing = [item for item in publications if clean(item.get("code", "")).startswith(clean(order.get("code")))]
    if existing:
        existing = sorted(existing, key=lambda item: (clean(item.get("createdAt")), clean(item.get("id"))), reverse=True)
        order["publicationIds"] = [item["id"] for item in existing]
        order["publicationCount"] = len(existing)
        order["resultPack"] = build_result_pack(order["product"], order["plan"], order.get("company", ""), order.get("note", ""))
        return order
    pubs = create_publications_for_order(order)
    order["publicationIds"] = [item["id"] for item in pubs]
    order["publicationCount"] = len(order["publicationIds"])
    order["resultPack"] = build_result_pack(order["product"], order["plan"], order.get("company", ""), order.get("note", ""))
    return order


def finalize_paid_order(order: dict[str, Any]) -> dict[str, Any]:
    order["paymentStatus"] = "paid"
    order["status"] = "delivered"
    order["resultPack"] = build_result_pack(order["product"], order["plan"], order.get("company", ""), order.get("note", ""))
    order = ensure_publications_for_order(order)
    delivery_meta = deepcopy(order.get("deliveryMeta") or {})
    delivery_meta.setdefault("automation", "full_auto")
    delivery_meta.setdefault("deliveredAt", now_iso())
    delivery_meta["publicationCount"] = len(order.get("publicationIds") or [])
    order["deliveryMeta"] = delivery_meta
    return order


def create_demo_entry(payload: dict[str, Any]) -> dict[str, Any]:
    product = clean(payload.get("product"))
    validate_product(product)
    name = clip_text(payload.get("name"), 120)
    company = clip_text(payload.get("company"), 160)
    email = normalize_email(payload.get("email"))
    if not name or not company or not validate_email(email):
        raise HTTPException(status_code=400, detail="데모 신청 필수값이 누락되었습니다.")
    if payload.get("id") and payload.get("code"):
        entry = deepcopy(payload)
    else:
        entry = {
            "id": uid("dem"),
            "code": make_public_code("DEMO", product),
            "product": product,
            "productName": product_name(product),
            "company": company,
            "name": name,
            "email": email,
            "team": clip_text(payload.get("team"), 120),
            "need": clip_text(payload.get("need"), 500),
            "keywords": clip_text(payload.get("keywords"), 240),
            "plan": clip_text(payload.get("plan"), 80),
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
        }
    entry.setdefault("productName", product_name(product))
    return upsert_record("demos", entry)


def create_contact_entry(payload: dict[str, Any]) -> dict[str, Any]:
    product = clean(payload.get("product"))
    validate_product(product)
    company = clip_text(payload.get("company"), 160)
    name = clip_text(payload.get("name"), 120)
    email = normalize_email(payload.get("email"))
    issue = clip_text(payload.get("issue"), 500)
    if not company or not issue or not validate_email(email):
        raise HTTPException(status_code=400, detail="문의 필수값이 누락되었습니다.")
    if payload.get("id") and payload.get("code"):
        entry = deepcopy(payload)
    else:
        entry = {
            "id": uid("con"),
            "code": make_public_code("CONTACT", product),
            "product": product,
            "productName": product_name(product),
            "company": company,
            "name": name,
            "email": email,
            "issue": issue,
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
        }
    entry.setdefault("productName", product_name(product))
    return upsert_record("contacts", entry)


def create_lookup_entry(payload: dict[str, Any]) -> dict[str, Any]:
    email = normalize_email(payload.get("email"))
    code = normalize_code(payload.get("code"))
    if not validate_email(email):
        raise HTTPException(status_code=400, detail="결과 전달 확인용 이메일 형식이 올바르지 않습니다.")
    if not code:
        raise HTTPException(status_code=400, detail="조회 코드를 입력해 주세요.")
    if payload.get("id"):
        entry = deepcopy(payload)
        entry.setdefault("createdAt", now_iso())
    else:
        entry = {"id": uid("lkp"), "email": email, "code": code, "createdAt": now_iso(), "updatedAt": now_iso()}
    return upsert_record("lookups", entry)


def base_order_entry(payload: dict[str, Any], *, payment_method: str | None = None, payment_status: str | None = None) -> dict[str, Any]:
    product = clean(payload.get("product"))
    plan = clean(payload.get("plan") or "Starter")
    company = clip_text(payload.get("company"), 160)
    name = clip_text(payload.get("name"), 120)
    email = normalize_email(payload.get("email"))
    method = clean(payment_method or payload.get("paymentMethod") or "toss")
    billing = clean(payload.get("billing") or "one-time")
    validate_product(product)
    validate_plan(product, plan)
    if billing != "one-time":
        raise HTTPException(status_code=400, detail="현재 온라인 결제는 1회 결제형만 지원합니다.")
    if not company or not name or not validate_email(email):
        raise HTTPException(status_code=400, detail="결제 필수값이 누락되었습니다.")
    plan_meta = plan_info(product, plan)
    status = payment_status or ("paid" if method == "toss" and not NV0_TOSS_CLIENT_KEY and not NV0_TOSS_SECRET_KEY else "pending")
    order_id = clean(payload.get("id")) or uid("ord")
    order_code = normalize_code(payload.get("code")) or make_public_code("NV0", product)
    return {
        "id": order_id,
        "code": order_code,
        "product": product,
        "productName": product_name(product),
        "plan": plan,
        "price": plan_meta["display"],
        "amount": plan_meta["amount"],
        "planNote": plan_meta["note"],
        "billing": billing,
        "paymentMethod": method,
        "paymentStatus": status,
        "status": next_status_for_payment(status),
        "company": company,
        "name": name,
        "email": email,
        "note": clip_text(payload.get("note"), 1000),
        "resultPack": build_result_pack(product, plan, company, clip_text(payload.get("note"), 1000)) if status == "paid" else None,
        "publicationIds": payload.get("publicationIds") if isinstance(payload.get("publicationIds"), list) else [],
        "publicationCount": len(payload.get("publicationIds") or []),
        "paymentKey": clean(payload.get("paymentKey")),
        "paymentMeta": payload.get("paymentMeta") or {},
        "createdAt": payload.get("createdAt") or now_iso(),
        "updatedAt": now_iso(),
    }


def create_order_entry(payload: dict[str, Any]) -> dict[str, Any]:
    order = base_order_entry(payload)
    if order["paymentStatus"] == "paid":
        order = finalize_paid_order(order)
    return upsert_record("orders", order)


def reserve_toss_order(payload: dict[str, Any]) -> dict[str, Any]:
    if NV0_PAYMENT_PROVIDER != 'toss':
        raise HTTPException(status_code=503, detail='현재 Toss 결제가 비활성화되어 있습니다.')
    if not NV0_TOSS_MOCK and (not NV0_TOSS_CLIENT_KEY or not NV0_TOSS_SECRET_KEY):
        raise HTTPException(status_code=503, detail='결제 설정이 아직 완료되지 않았습니다. 운영자에게 Toss 키 설정을 확인해 달라고 요청해 주세요.')
    order = base_order_entry(payload, payment_method="toss", payment_status="ready")
    with order_lock(order["id"]):
        stored = get_record("orders", order["id"])
        if stored and clean(stored.get("paymentStatus")) in {"ready", "pending", "paid"}:
            return stored
        return upsert_record("orders", order)


def find_order(email: str, code: str) -> dict[str, Any] | None:
    email = normalize_email(email)
    code = normalize_code(code)
    for order in load_records("orders"):
        if normalize_email(order.get("email")) != email:
            continue
        if not code or normalize_code(order.get("code")) == code:
            return order
    return None


def update_order(order_id: str, updater) -> dict[str, Any]:
    order = get_record("orders", order_id)
    if not order:
        raise HTTPException(status_code=404, detail="결제 기록을 찾지 못했습니다.")
    updated = updater(deepcopy(order))
    updated["updatedAt"] = now_iso()
    return upsert_record("orders", updated)


def require_admin(
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    if not NV0_ADMIN_TOKEN and not REQUIRE_ADMIN_TOKEN:
        return
    token = clean(x_admin_token)
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = clean(authorization.split(" ", 1)[1])
    if not token or not secrets.compare_digest(token, NV0_ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="관리자 토큰이 필요합니다.")


def _health_dependency_snapshot(*, verbose: bool = False) -> dict[str, Any]:
    checks = {
        'distReady': DIST.joinpath('index.html').exists(),
        'dbExists': DB_PATH.exists(),
        'dbParentWritable': os.access(DB_PATH.parent, os.W_OK),
        'backupDirWritable': os.access(BACKUP_DIR, os.W_OK),
    }
    if verbose:
        checks['allowedHostsReady'] = bool(ALLOWED_HOSTS)
        checks['internalHosts'] = sorted(INTERNAL_HOSTS)
    return checks


def readiness_payload(*, verbose: bool = False) -> dict[str, Any]:
    checks = _health_dependency_snapshot(verbose=verbose)
    db_ok = False
    db_error = ''
    try:
        with get_db() as conn:
            conn.execute('SELECT 1').fetchone()
        db_ok = True
    except Exception as exc:
        db_error = str(exc)
    checks['dbQuery'] = db_ok
    ok = all(bool(value) for key, value in checks.items() if isinstance(value, bool))
    payload = {
        'ok': ok,
        'service': 'nv0',
        'status': 'ready' if ok else 'degraded',
        'serviceMode': 'board_only' if BOARD_ONLY_MODE else 'full',
        'checks': checks,
    }
    if db_error:
        payload['error'] = db_error
    return payload


def liveness_payload() -> dict[str, Any]:
    return {
        'ok': True,
        'service': 'nv0',
        'status': 'alive',
        'serviceMode': 'board_only' if BOARD_ONLY_MODE else 'full',
    }


def public_health_payload(*, verbose: bool = False) -> dict[str, Any]:
    payload = {
        'ok': True,
        'service': 'nv0',
        'payment': {'provider': NV0_PAYMENT_PROVIDER, 'tossEnabled': bool(NV0_TOSS_CLIENT_KEY and NV0_TOSS_SECRET_KEY), 'tossMock': NV0_TOSS_MOCK},
        'adminRequired': REQUIRE_ADMIN_TOKEN,
        'serviceMode': 'board_only' if BOARD_ONLY_MODE else 'full',
    }
    if verbose:
        payload.update({
            'db': str(DB_PATH),
            'allowedHosts': ALLOWED_HOSTS,
            'allowedOrigins': ALLOWED_ORIGINS,
            'docsEnabled': ENABLE_DOCS,
            'backup': {'dir': str(BACKUP_DIR), 'encrypted': bool(os.getenv('NV0_BACKUP_PASSPHRASE', '')), 'hsts': HSTS_ENABLED, 'writable': os.access(BACKUP_DIR, os.W_OK)},
            'state': {name: len(load_records(name)) for name in STORE_TYPES},
        })
    return payload


def public_config() -> dict[str, Any]:
    toss_enabled = False if BOARD_ONLY_MODE else bool(NV0_TOSS_CLIENT_KEY and NV0_TOSS_SECRET_KEY)
    return {
        "brand": SITE_DATA.get("brand", {}),
        "payment": {
            "provider": "disabled" if BOARD_ONLY_MODE else NV0_PAYMENT_PROVIDER,
            "toss": {
                "enabled": toss_enabled,
                "clientKey": "" if BOARD_ONLY_MODE else NV0_TOSS_CLIENT_KEY,
                "mock": False if BOARD_ONLY_MODE else NV0_TOSS_MOCK,
                "successUrl": "" if BOARD_ONLY_MODE else f"{NV0_BASE_URL}{SUCCESS_PATH}",
                "failUrl": "" if BOARD_ONLY_MODE else f"{NV0_BASE_URL}{FAIL_PATH}",
            },
        },
        "admin": {"protected": bool(NV0_ADMIN_TOKEN), "required": REQUIRE_ADMIN_TOKEN},
        "backup": {"enabled": True, "encrypted": bool(os.getenv("NV0_BACKUP_PASSPHRASE", ""))},
        "boardAutomation": {
            "enabledProducts": [key for key, item in PRODUCTS.items() if (item.get("board_automation") or {}).get("enabled")],
        },
        "boardOnly": BOARD_ONLY_MODE,
        "disabledFeatures": ["orders", "payments", "demo", "contact", "portal", "pricing", "docs", "cases", "faq"] if BOARD_ONLY_MODE else [],
    }


def toss_confirm_remote(payment_key: str, order_id: str, amount: int) -> dict[str, Any]:
    if NV0_TOSS_MOCK:
        return {
            "paymentKey": payment_key or f"mock_{uid('toss')}",
            "orderId": order_id,
            "totalAmount": amount,
            "method": "카드",
            "status": "DONE",
            "requestedAt": now_iso(),
            "approvedAt": now_iso(),
            "mId": "nv0-mock",
            "secret": f"mock_secret_{order_id}",
        }
    if not NV0_TOSS_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Toss 시크릿 키가 설정되지 않았습니다.")
    body = json.dumps({"paymentKey": payment_key, "orderId": order_id, "amount": amount}).encode("utf-8")
    basic = base64.b64encode(f"{NV0_TOSS_SECRET_KEY}:".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(TOSS_CONFIRM_URL, data=body, method="POST")
    req.add_header("Authorization", f"Basic {basic}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        try:
            parsed = json.loads(detail)
            message = parsed.get("message") or parsed.get("code") or detail
        except Exception:
            message = detail or str(exc)
        raise HTTPException(status_code=502, detail=f"Toss 결제 승인 실패: {message}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Toss 결제 승인 요청 실패: {exc}") from exc


def confirm_toss_payment(payload: dict[str, Any]) -> dict[str, Any]:
    order_id = clean(payload.get("orderId"))
    payment_key = clean(payload.get("paymentKey"))
    amount = int(payload.get("amount") or 0)
    if not order_id or not payment_key or amount <= 0:
        raise HTTPException(status_code=400, detail="결제 승인 필수값이 누락되었습니다.")
    with order_lock(order_id):
        order = get_record("orders", order_id)
        if not order:
            raise HTTPException(status_code=404, detail="결제 준비 정보를 찾지 못했습니다.")
        if int(order.get("amount") or 0) != amount:
            raise HTTPException(status_code=400, detail="결제 금액이 저장된 결제 정보와 일치하지 않습니다.")
        existing_payment_key = clean(order.get("paymentKey"))
        if order.get("paymentStatus") == "paid":
            if existing_payment_key and existing_payment_key != payment_key:
                raise HTTPException(status_code=409, detail="이미 다른 결제 키로 승인된 결제 건입니다.")
            order = finalize_paid_order(order)
            order["updatedAt"] = now_iso()
            return upsert_record("orders", order)

        payment = toss_confirm_remote(payment_key, order_id, amount)
        order["paymentKey"] = payment_key
        order["paymentMeta"] = payment
        order = finalize_paid_order(order)
        order["updatedAt"] = now_iso()
        return upsert_record("orders", order)


def apply_webhook_to_order(order: dict[str, Any], event_type: str, data: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    status = clean(data.get("status") or raw.get("status")).upper()
    payment_key = clean(data.get("paymentKey") or data.get("lastTransactionKey") or order.get("paymentKey"))
    if status in {"DONE", "PAID"}:
        if payment_key:
            order["paymentKey"] = payment_key
        merged_meta = deepcopy(order.get("paymentMeta") or {})
        merged_meta.update(data)
        order["paymentMeta"] = merged_meta
        order = finalize_paid_order(order)
    elif status in {"CANCELED", "PARTIAL_CANCELED"}:
        order["paymentStatus"] = "cancelled"
        order["status"] = "payment_cancelled"
    elif status in {"EXPIRED", "ABORTED", "FAILED"}:
        order["paymentStatus"] = "failed"
        order["status"] = "payment_failed"
    elif status in {"READY", "WAITING_FOR_DEPOSIT", "IN_PROGRESS"}:
        order["paymentStatus"] = "pending"
        order["status"] = "payment_pending"
    order["updatedAt"] = now_iso()
    return upsert_record("orders", order)


def webhook_event_fingerprint(raw: dict[str, Any], lowered_headers: dict[str, str], raw_body: bytes | None = None) -> str:
    for candidate in (
        lowered_headers.get('tosspayments-webhook-id'),
        raw.get('eventId') if isinstance(raw, dict) else '',
        raw.get('eventKey') if isinstance(raw, dict) else '',
        raw.get('id') if isinstance(raw, dict) else '',
    ):
        value = clean(candidate)
        if value:
            return f"ext:{value}"
    payload = raw_body or json.dumps(raw, ensure_ascii=False, sort_keys=True).encode('utf-8')
    return 'sha256:' + hashlib.sha256(payload).hexdigest()


def find_webhook_event_by_fingerprint(fingerprint: str) -> dict[str, Any] | None:
    target = clean(fingerprint)
    if not target:
        return None
    for item in load_records('webhook_events'):
        if clean(item.get('fingerprint')) == target:
            return item
    return None


def handle_toss_webhook(raw: dict[str, Any], request_headers: dict[str, str], raw_body: bytes | None = None) -> dict[str, Any]:
    event_type = clean(raw.get('eventType') or 'UNKNOWN')
    data = raw.get('data') if isinstance(raw.get('data'), dict) else {}
    order_id = clean(raw.get('orderId') or data.get('orderId'))
    stored = get_record('orders', order_id) if order_id else None
    lowered_headers = lower_headers(request_headers)
    fingerprint = webhook_event_fingerprint(raw, lowered_headers, raw_body=raw_body)
    duplicate = find_webhook_event_by_fingerprint(fingerprint)
    if duplicate and clean(duplicate.get('result')) in {'updated', 'duplicate', 'order_not_found'}:
        return {'ok': True, 'ignored': True, 'reason': 'duplicate_webhook'}
    event_record = {
        'id': uid('whk'),
        'fingerprint': fingerprint,
        'eventType': event_type,
        'orderId': order_id,
        'headers': {k: v for k, v in lowered_headers.items() if k.startswith('tosspayments-')},
        'payload': raw,
        'status': clean(data.get('status') or raw.get('status') or 'unknown'),
        'processedAt': now_iso(),
        'verified': True,
        'verificationMethod': 'none',
        'result': 'ignored',
    }

    verified = True
    verification_method = 'none'
    if event_type in {'payout.changed', 'seller.changed'}:
        verified, verification_method = verify_toss_webhook_signature(raw_body or json.dumps(raw, ensure_ascii=False).encode('utf-8'), lowered_headers)
    elif event_type in {'PAYMENT_STATUS_CHANGED', 'DEPOSIT_CALLBACK', 'CANCEL_STATUS_CHANGED'}:
        verified, verification_method = verify_toss_payment_secret(raw, stored)
    event_record['verified'] = verified
    event_record['verificationMethod'] = verification_method

    if not verified:
        event_record['result'] = verification_method
        upsert_record('webhook_events', event_record)
        return {'ok': True, 'ignored': True, 'reason': verification_method}

    if stored:
        with order_lock(stored.get('id') or order_id):
            refreshed = get_record('orders', stored.get('id') or order_id) or stored
            updated = apply_webhook_to_order(refreshed, event_type, data, raw)
        event_record['result'] = 'updated'
        event_record['orderStatus'] = updated.get('status')
        event_record['paymentStatus'] = updated.get('paymentStatus')
        upsert_record('webhook_events', event_record)
        return {'ok': True, 'order': updated, 'ignored': False}

    upsert_record('webhook_events', event_record)
    return {'ok': True, 'ignored': True, 'reason': 'order_not_found'}


def create_board_publication(product_key: str, *, source: str = 'manual', force_topic_index: int | None = None) -> dict[str, Any]:
    target = PRODUCTS[product_key]
    automation = target.get('board_automation') or {}
    topics = automation.get('topics') or []
    if not topics:
        raise HTTPException(status_code=400, detail='발행 가능한 CTA 주제가 없습니다.')
    state_id = f'scheduler-{product_key}'
    state = get_record('scheduler', state_id) or {'id': state_id, 'product': product_key, 'lastPublishedAt': '', 'topicIndex': 0, 'createdAt': now_iso()}
    topic_index = force_topic_index if force_topic_index is not None else int(state.get('topicIndex') or 0) % len(topics)
    topic = topics[topic_index]
    created = now_iso()
    pub = build_publication_payload(
        product_key=product_key,
        title=topic.get('title') or f"{target.get('name')} CTA 글",
        summary=topic.get('summary') or target.get('summary', ''),
        source=source,
        code=f"{source.upper()}-{product_prefix(product_key)}-{topic_index + 1:03d}",
        created_at=created,
        cta_label=topic.get('ctaText') or automation.get('cta_label') or '제품 설명 보기',
        cta_href=automation.get('cta_href') or f"/products/{product_key}/index.html#intro",
        topic_summary=topic.get('summary') or target.get('summary', ''),
        publication_id=uid('pubman' if source == 'manual' else 'pubsch'),
    )
    upsert_record('publications', pub)
    state['lastPublishedAt'] = created
    state['topicIndex'] = (topic_index + 1) % len(topics)
    state['updatedAt'] = created
    upsert_record('scheduler', state)
    return pub


def reseed_board_state() -> dict[str, Any]:
    delete_all_records()
    ensure_seed_publications()
    return state_payload()


def create_app() -> FastAPI:
    ensure_dist_ready()
    app = FastAPI(
        title="NV0 Company Rebuild Deployable",
        docs_url="/api/docs" if ENABLE_DOCS else None,
        redoc_url="/api/redoc" if ENABLE_DOCS else None,
        openapi_url="/api/openapi.json" if ENABLE_DOCS else None,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        host_response = invalid_host_response(request)
        if host_response is not None:
            return host_response
        redirect_target = canonical_redirect_target(request)
        if redirect_target is not None:
            return Response(status_code=308, headers={'Location': redirect_target})
        limited_response = maybe_limit_request(request)
        if limited_response is not None:
            return limited_response
        body_limit_response = enforce_body_size(request)
        if body_limit_response is not None:
            return body_limit_response
        if BOARD_ONLY_MODE and board_only_disabled_api(request.url.path):
            return board_only_json_response('이 기능은 비활성화되었습니다. 현재는 AI 자동발행 블로그 허브만 운영합니다.')
        if BOARD_ONLY_MODE and request.method == 'GET' and request.url.path not in HEALTH_ENDPOINTS and not request.url.path.startswith('/api/') and not board_only_path_allowed(request.url.path):
            return board_only_html_response(request.url.path)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        sensitive_html_prefixes = ("/admin/", "/portal/", "/checkout/", "/payments/toss/")
        asset_suffixes = (".css", ".js", ".svg", ".ico", ".png", ".jpg", ".jpeg", ".webp", ".woff", ".woff2")
        if request.url.path.startswith(("/api/admin/", "/api/docs", "/api/openapi.json", "/api/redoc")) or request.url.path.startswith(sensitive_html_prefixes):
            response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
        if request.url.path.startswith("/api/") or request.url.path.startswith(sensitive_html_prefixes):
            response.headers.setdefault("Cache-Control", "no-store")
        elif request.url.path.startswith("/assets/") or request.url.path.endswith(asset_suffixes):
            response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
        elif request.url.path.endswith(".html") or request.url.path == "/":
            response.headers.setdefault("Cache-Control", "no-cache")
        csp = "default-src 'self' https: data: blob:; script-src 'self' 'unsafe-inline' https:; style-src 'self' 'unsafe-inline' https:; img-src 'self' https: data: blob:; connect-src 'self' https:; font-src 'self' https: data:; frame-ancestors 'self'; base-uri 'self'; form-action 'self' https://api.tosspayments.com https://js.tosspayments.com; object-src 'none'"
        if NV0_BASE_URL.startswith("https://"):
            csp += "; upgrade-insecure-requests"
        response.headers.setdefault("Content-Security-Policy", csp)
        if HSTS_ENABLED and (request.url.scheme == "https" or NV0_BASE_URL.startswith("https://")):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "detail": exc.detail})

    @app.on_event("startup")
    def startup() -> None:
        if REQUIRE_ADMIN_TOKEN and len(clean(NV0_ADMIN_TOKEN)) < 32:
            raise RuntimeError("운영 배포에서는 32자 이상 관리자 토큰이 필요합니다.")
        if REQUIRE_ADMIN_TOKEN and len(clean(os.getenv("NV0_BACKUP_PASSPHRASE", ""))) < 24:
            raise RuntimeError("운영 배포에서는 24자 이상 백업 암호가 필요합니다.")
        if not BOARD_ONLY_MODE and NV0_PAYMENT_PROVIDER == 'toss' and not NV0_TOSS_MOCK and not IS_LOCAL_BASE:
            if not NV0_TOSS_CLIENT_KEY or not NV0_TOSS_SECRET_KEY:
                raise RuntimeError("운영 full 모드에서는 Toss client/secret 키가 모두 필요합니다.")
        init_db()
        ensure_scheduled_publications()

    @app.get("/health", include_in_schema=False)
    @app.get("/healthz", include_in_schema=False)
    def root_health() -> dict[str, Any]:
        return public_health_payload(verbose=PUBLIC_HEALTH_VERBOSE)

    @app.get("/live", include_in_schema=False)
    @app.get("/livez", include_in_schema=False)
    def live() -> dict[str, Any]:
        return liveness_payload()

    @app.get("/ready", include_in_schema=False)
    @app.get("/readyz", include_in_schema=False)
    def ready(response: Response) -> dict[str, Any]:
        payload = readiness_payload(verbose=PUBLIC_HEALTH_VERBOSE)
        if not payload.get('ok'):
            response.status_code = 503
        return payload

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return public_health_payload(verbose=PUBLIC_HEALTH_VERBOSE)

    @app.get("/api/admin/health")
    def admin_health(_: None = Depends(require_admin)) -> dict[str, Any]:
        payload = public_health_payload(verbose=True)
        payload['adminProtected'] = bool(NV0_ADMIN_TOKEN)
        return payload

    @app.get("/api/public/system-config")
    def public_system_config() -> dict[str, Any]:
        return {"ok": True, "config": public_config()}

    @app.get("/api/admin/validate")
    def admin_validate(_: None = Depends(require_admin)) -> dict[str, Any]:
        return {"ok": True, "protected": bool(NV0_ADMIN_TOKEN)}

    @app.get("/api/admin/state")
    def admin_state(_: None = Depends(require_admin)) -> Response:
        return Response(content=cached_json_bytes("admin_state", lambda: {"ok": True, "state": state_payload()}), media_type="application/json")

    @app.get("/api/admin/export")
    def admin_export(_: None = Depends(require_admin)) -> dict[str, Any]:
        return {"ok": True, **export_state_payload()}

    @app.post("/api/admin/import")
    def admin_import(payload: dict[str, Any], _: None = Depends(require_admin)) -> dict[str, Any]:
        state = import_state_payload(payload, replace=bool(payload.get("replace", True)))
        return {"ok": True, "state": state}

    @app.get("/api/public/board/feed")
    def public_board_feed() -> Response:
        ensure_scheduled_publications()
        return Response(content=cached_json_bytes("public_board_feed", lambda: {"ok": True, "items": load_records("publications")}), media_type="application/json")

    if not BOARD_ONLY_MODE:
        @app.post("/api/public/orders")
        def public_orders(payload: dict[str, Any]) -> dict[str, Any]:
            order = create_order_entry(payload)
            return {"ok": True, "order": order, "state": state_payload()}

        @app.post("/api/public/orders/reserve")
        def public_reserve_order(payload: dict[str, Any]) -> dict[str, Any]:
            order = reserve_toss_order(payload)
            return {"ok": True, "order": order, "payment": public_config()["payment"]["toss"], "state": state_payload()}

        @app.post("/api/public/payments/toss/confirm")
        def public_toss_confirm(payload: dict[str, Any]) -> dict[str, Any]:
            order = confirm_toss_payment(payload)
            return {"ok": True, "order": order, "state": state_payload()}

        @app.post("/api/public/payments/toss/webhook")
        async def public_toss_webhook(request: Request) -> dict[str, Any]:
            raw_body = await request.body()
            try:
                raw = json.loads(raw_body.decode('utf-8')) if raw_body else {}
            except Exception:
                raise HTTPException(status_code=400, detail='웹훅 본문 형식이 올바르지 않습니다.')
            result = handle_toss_webhook(raw if isinstance(raw, dict) else {}, dict(request.headers), raw_body=raw_body)
            return result

        @app.post("/api/public/demo-requests")
        def public_demos(payload: dict[str, Any]) -> dict[str, Any]:
            entry = create_demo_entry(payload)
            preview = build_demo_preview(entry["product"], {**payload, "plan": payload.get("plan") or entry.get("plan") or "Starter"})
            return {"ok": True, "demo": entry, "preview": preview, "state": state_payload()}

        @app.post("/api/public/contact-requests")
        def public_contacts(payload: dict[str, Any]) -> dict[str, Any]:
            entry = create_contact_entry(payload)
            return {"ok": True, "contact": entry, "state": state_payload()}

        @app.post("/api/public/portal/lookup")
        def public_portal_lookup(payload: dict[str, Any]) -> dict[str, Any]:
            lookup = create_lookup_entry(payload)
            order = find_order(clean(payload.get("email")), clean(payload.get("code")))
            publications = [item for item in load_records("publications") if order and item.get("id") in (order.get("publicationIds") or [])]
            return {"ok": True, "lookup": lookup, "order": order, "publications": publications, "state": state_payload()}

    @app.post("/api/admin/actions/publish-now")
    def admin_publish_now(payload: dict[str, Any] | None = None, _: None = Depends(require_admin)) -> dict[str, Any]:
        requested = clean((payload or {}).get('product'))
        targets = [requested] if requested and requested in PRODUCTS else [key for key, item in PRODUCTS.items() if (item.get('board_automation') or {}).get('enabled')]
        published = [create_board_publication(key, source='manual') for key in targets]
        return {"ok": True, "published": published, "state": state_payload()}

    @app.post("/api/admin/actions/reseed-board")
    def admin_reseed_board(_: None = Depends(require_admin)) -> dict[str, Any]:
        return {"ok": True, "state": reseed_board_state()}

    if not BOARD_ONLY_MODE:
        @app.post("/api/admin/actions/seed-demo")
        def admin_seed_demo(_: None = Depends(require_admin)) -> dict[str, Any]:
            order = upsert_record("orders", base_order_entry({"product": "veridion", "plan": "Growth", "billing": "one-time", "paymentMethod": "toss", "company": "Demo Company", "name": "테스터", "email": "demo@nv0.kr", "note": "시드 결제"}, payment_status="pending"))
            create_demo_entry({"product": "clearport", "company": "Demo Company", "name": "테스터", "email": "demo@nv0.kr", "team": "3명 팀", "need": "정상작동 확인"})
            create_contact_entry({"product": "grantops", "company": "Demo Company", "email": "demo@nv0.kr", "issue": "제출 일정 문의"})
            return {"ok": True, "order": order, "state": state_payload()}

    @app.post("/api/admin/actions/reset")
    def admin_reset(_: None = Depends(require_admin)) -> dict[str, Any]:
        return {"ok": True, "state": reseed_board_state()}

    if not BOARD_ONLY_MODE:
        @app.post("/api/admin/orders/{order_id}/advance")
        def admin_advance(order_id: str, _: None = Depends(require_admin)) -> dict[str, Any]:
            updated = update_order(order_id, _advance_order)
            return {"ok": True, "order": updated, "state": state_payload()}

        @app.post("/api/admin/orders/{order_id}/toggle-payment")
        def admin_toggle_payment(order_id: str, _: None = Depends(require_admin)) -> dict[str, Any]:
            updated = update_order(order_id, _toggle_payment)
            return {"ok": True, "order": updated, "state": state_payload()}

        @app.post("/api/admin/orders/{order_id}/republish")
        def admin_republish(order_id: str, _: None = Depends(require_admin)) -> dict[str, Any]:
            updated = update_order(order_id, _republish_order)
            return {"ok": True, "order": updated, "state": state_payload()}

    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="static")
    app = CORSMiddleware(
        app=app,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    return app


def _advance_order(order: dict[str, Any]) -> dict[str, Any]:
    current = order.get("status") or next_status_for_payment(order.get("paymentStatus", "pending"))
    if order.get("paymentStatus") != "paid":
        raise HTTPException(status_code=400, detail="결제 완료 전에는 자동 제공을 완료할 수 없습니다.")
    if current == "delivered":
        return order
    return finalize_paid_order(order)


def _toggle_payment(order: dict[str, Any]) -> dict[str, Any]:
    payment_status = "pending" if order.get("paymentStatus") == "paid" else "paid"
    if order.get("status") == "delivered" and payment_status != "paid":
        raise HTTPException(status_code=400, detail="결과 전달 완료 결제 건은 미결제로 되돌릴 수 없습니다.")
    if payment_status == "pending":
        order["paymentStatus"] = payment_status
        order["status"] = "payment_pending"
        return order
    return finalize_paid_order(order)


def _republish_order(order: dict[str, Any]) -> dict[str, Any]:
    if order.get("paymentStatus") != "paid":
        raise HTTPException(status_code=400, detail="결제 완료 후에만 재발행할 수 있습니다.")
    pubs = create_publications_for_order(order)
    order["publicationIds"] = [*(order.get("publicationIds") or []), *[item["id"] for item in pubs]]
    order["publicationCount"] = len(order["publicationIds"])
    return order


app = create_app()
