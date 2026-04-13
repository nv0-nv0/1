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


def build_result_pack(product_key: str, plan_name: str, company: str) -> dict[str, Any]:
    target = PRODUCTS[product_key]
    return {
        "title": f"{target['name']} {plan_name} 실행 결과",
        "summary": f"{company or '고객사'} 상황에 맞춘 {target['name']} {plan_name} 플랜 결과 자료가 준비되었습니다.",
        "outputs": [
            {
                "title": item,
                "note": f"{target['name']} 자료 {idx + 1} · {company or '고객사'} 상황 기준 정리 항목",
            }
            for idx, item in enumerate(target.get("outputs", []))
        ],
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
        order["resultPack"] = build_result_pack(order["product"], order["plan"], order.get("company", ""))
        return order
    pubs = create_publications_for_order(order)
    order["publicationIds"] = [item["id"] for item in pubs]
    order["publicationCount"] = len(order["publicationIds"])
    order["resultPack"] = build_result_pack(order["product"], order["plan"], order.get("company", ""))
    return order


def finalize_paid_order(order: dict[str, Any]) -> dict[str, Any]:
    order["paymentStatus"] = "paid"
    order["status"] = "delivered"
    order["resultPack"] = build_result_pack(order["product"], order["plan"], order.get("company", ""))
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
        "resultPack": build_result_pack(product, plan, company) if status == "paid" else None,
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
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
            return {"ok": True, "demo": entry, "state": state_payload()}

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
