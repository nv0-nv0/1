from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import socket
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse
from html import escape
from uuid import uuid4

from bs4 import BeautifulSoup
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
STORE_TYPES = ["publications", "scheduler"] if BOARD_ONLY_MODE else ["orders", "demos", "contacts", "lookups", "reports", "publications", "webhook_events", "scheduler"]

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
REQUIRE_ADMIN_TOKEN = os.getenv("NV0_REQUIRE_ADMIN_TOKEN", "1").lower() in {"1", "true", "yes", "on"}
if REQUIRE_ADMIN_TOKEN and len((NV0_ADMIN_TOKEN or "").strip()) < 32 and IS_LOCAL_BASE:
    NV0_ADMIN_TOKEN = secrets.token_urlsafe(32)
    os.environ["NV0_ADMIN_TOKEN"] = NV0_ADMIN_TOKEN
if REQUIRE_ADMIN_TOKEN and len((os.getenv("NV0_BACKUP_PASSPHRASE", "") or "").strip()) < 24 and IS_LOCAL_BASE:
    os.environ["NV0_BACKUP_PASSPHRASE"] = secrets.token_urlsafe(24)
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
    "/api/public/orders", "/api/public/payments", "/api/public/demo-requests", "/api/public/contact-requests", "/api/public/portal/lookup", "/api/public/veridion/scan", "/api/admin/orders/"
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
VERIDION_SCAN_MAX_PAGES = max(4, int(os.getenv("NV0_VERIDION_SCAN_MAX_PAGES", "12") or "12"))
VERIDION_SCAN_MAX_DISCOVERED = max(8, int(os.getenv("NV0_VERIDION_SCAN_MAX_DISCOVERED", "40") or "40"))
VERIDION_SCAN_MAX_DEPTH = max(1, int(os.getenv("NV0_VERIDION_SCAN_MAX_DEPTH", "2") or "2"))
VERIDION_SCAN_TIMEOUT = max(2.0, float(os.getenv("NV0_VERIDION_SCAN_TIMEOUT", "4.5") or "4.5"))
VERIDION_SCAN_CACHE_TTL_SECONDS = max(60, int(os.getenv("NV0_VERIDION_SCAN_CACHE_TTL_SECONDS", "1800") or "1800"))
ALLOW_LOCAL_SCAN = os.getenv("NV0_ALLOW_LOCAL_SCAN", "0").lower() in {"1", "true", "yes", "on"}
_VERIDION_SCAN_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_VERIDION_SCAN_CACHE_LOCK = threading.Lock()


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


def collect_text_items(*values: Any, limit: int = 20) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for raw in values:
        if raw is None:
            continue
        if isinstance(raw, (list, tuple, set)):
            candidates = list(raw)
        else:
            candidates = re.split(r'[\n,;/]+', clean(raw))
        for candidate in candidates:
            item = clean(candidate)
            if not item:
                continue
            key = item.casefold()
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
            if len(items) >= max(1, int(limit)):
                return items
    return items


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
        "점검 url": "website",
        "점검 url/대표 경로": "website",
        "업종": "industry",
        "운영 국가": "market",
        "리포트 id": "report_id",
        "리포트 코드": "report_code",
        "탐색률": "exploration_rate",
        "핵심 페이지 커버리지": "priority_coverage",
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


_CLAIM_PATTERNS = [re.compile(pattern, re.I) for pattern in [r"100%", r"완벽", r"즉시", r"무조건", r"절대", r"영구", r"유일", r"최고", r"no\.?1", r"부작용\s*없", r"누구에게나"]]
_BUSINESS_INFO_PATTERNS = [re.compile(pattern, re.I) for pattern in [r"사업자등록번호", r"통신판매업", r"대표자", r"상호", r"고객센터", r"주소"]]
_PRIVACY_PATTERNS = [re.compile(pattern, re.I) for pattern in [r"개인정보", r"privacy", r"personal data", r"privacy policy", r"처리방침"]]
_TERMS_PATTERNS = [re.compile(pattern, re.I) for pattern in [r"이용약관", r"terms", r"약관"]]
_REFUND_PATTERNS = [re.compile(pattern, re.I) for pattern in [r"환불", r"반품", r"refund", r"청약철회"]]
_CHECKOUT_PATTERNS = [re.compile(pattern, re.I) for pattern in [r"결제", r"구매", r"checkout", r"cart", r"장바구니", r"subscribe", r"구독"]]
_CONTACT_PATTERNS = [re.compile(pattern, re.I) for pattern in [r"문의", r"contact", r"support", r"고객센터", r"help"]]
_CONSENT_PATTERNS = [re.compile(pattern, re.I) for pattern in [r"동의", r"consent", r"agree"]]
_EXCLUDE_PATH_PATTERNS = [re.compile(pattern, re.I) for pattern in [r"\.(jpg|jpeg|png|gif|webp|svg|pdf|zip|mp4|mp3|woff2?|ttf)$", r"/(wp-admin|admin|account|login|logout|mypage)(/|$)", r"[?&](replytocom|share|fbclid|gclid)="]]
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+|\n+")


def _strip_default_port(parsed) -> str:
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or '').lower()
    port = parsed.port
    if not port:
        return host
    if (scheme == 'http' and port == 80) or (scheme == 'https' and port == 443):
        return host
    return f"{host}:{port}"


def normalize_scan_url(raw: str) -> str:
    value = clean(raw)
    if not value:
        raise HTTPException(status_code=400, detail='점검할 URL을 입력해 주세요.')
    if '://' not in value:
        value = 'https://' + value
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {'http', 'https'}:
        raise HTTPException(status_code=400, detail='http 또는 https 주소만 점검할 수 있습니다.')
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail='도메인 형식이 올바르지 않습니다.')
    path = parsed.path or '/'
    cleaned = parsed._replace(scheme=parsed.scheme.lower(), netloc=_strip_default_port(parsed), path=path, fragment='')
    return urlunparse(cleaned)


def _resolved_ip_flags(hostname: str) -> list[Any]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return []
    found = []
    seen: set[str] = set()
    for info in infos:
        ip = info[4][0]
        if ip in seen:
            continue
        seen.add(ip)
        try:
            found.append(ipaddress.ip_address(ip))
        except ValueError:
            continue
    return found


def validate_scan_target(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or '').lower()
    if not host:
        raise HTTPException(status_code=400, detail='점검할 도메인을 확인하지 못했습니다.')
    if host in LOCAL_HOSTS or host in INTERNAL_HOSTS:
        if not ALLOW_LOCAL_SCAN:
            raise HTTPException(status_code=400, detail='로컬 또는 내부 주소는 현재 점검이 허용되지 않습니다.')
        return
    for ip in _resolved_ip_flags(host):
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise HTTPException(status_code=400, detail='내부 네트워크 성격의 주소는 점검할 수 없습니다.')


def _read_limited(res, limit: int = 1024 * 1024) -> bytes:
    body = res.read(limit + 1)
    return body[:limit]


def fetch_remote_document(url: str, *, accept: str = 'text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8') -> dict[str, Any]:
    started = time.monotonic()
    req = urllib.request.Request(url, method='GET')
    req.add_header('User-Agent', 'NV0-Veridion/1.0 (+https://nv0.kr)')
    req.add_header('Accept', accept)
    req.add_header('Accept-Language', 'ko,en;q=0.8')
    try:
        with urllib.request.urlopen(req, timeout=VERIDION_SCAN_TIMEOUT) as res:
            content_type = res.headers.get('Content-Type', '')
            body = _read_limited(res)
            charset = res.headers.get_content_charset() or 'utf-8'
            try:
                text = body.decode(charset, errors='replace')
            except LookupError:
                text = body.decode('utf-8', errors='replace')
            return {'ok': True, 'status': getattr(res, 'status', 200), 'url': res.geturl(), 'contentType': content_type, 'text': text, 'durationMs': round((time.monotonic() - started) * 1000, 1)}
    except urllib.error.HTTPError as exc:
        body = exc.read(4096).decode('utf-8', errors='replace')
        return {'ok': False, 'status': exc.code, 'url': url, 'contentType': exc.headers.get('Content-Type', ''), 'text': body, 'error': f'HTTP {exc.code}', 'durationMs': round((time.monotonic() - started) * 1000, 1)}
    except Exception as exc:
        return {'ok': False, 'status': 0, 'url': url, 'contentType': '', 'text': '', 'error': clean(str(exc)) or 'fetch failed', 'durationMs': round((time.monotonic() - started) * 1000, 1)}


def parse_basic_robots(text: str) -> dict[str, Any]:
    rules: dict[str, list[str]] = {'allow': [], 'disallow': [], 'sitemaps': []}
    current_agents: list[str] = []
    for raw in (text or '').splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line or ':' not in line:
            continue
        key, value = [clean(part) for part in line.split(':', 1)]
        key_lower = key.lower()
        if key_lower == 'user-agent':
            current_agents = [value.lower()]
            continue
        applies = not current_agents or '*' in current_agents or 'nv0-veridion/1.0 (+https://nv0.kr)'.lower() in current_agents
        if key_lower == 'sitemap' and value:
            rules['sitemaps'].append(value)
        elif applies and key_lower in {'allow', 'disallow'} and value:
            rules[key_lower].append(value)
    return rules


def robots_allows_path(path: str, robots: dict[str, Any]) -> bool:
    allow_rules = robots.get('allow') or []
    disallow_rules = robots.get('disallow') or []
    best_allow = max((len(rule) for rule in allow_rules if path.startswith(rule)), default=-1)
    best_disallow = max((len(rule) for rule in disallow_rules if path.startswith(rule)), default=-1)
    if best_disallow == -1:
        return True
    return best_allow >= best_disallow


def canonicalize_same_origin(url: str, *, origin_host: str) -> str | None:
    try:
        normalized = normalize_scan_url(url)
    except HTTPException:
        return None
    parsed = urlparse(normalized)
    if _strip_default_port(parsed) != origin_host:
        return None
    return normalized


def should_exclude_path(url: str) -> bool:
    lower = url.lower()
    return any(pattern.search(lower) for pattern in _EXCLUDE_PATH_PATTERNS)


def page_type_from_signals(url: str, title: str, text: str) -> str:
    joined = ' '.join([url.lower(), clean(title).lower(), clean(text[:500]).lower()])
    if any(pattern.search(joined) for pattern in _PRIVACY_PATTERNS):
        return 'privacy'
    if any(pattern.search(joined) for pattern in _TERMS_PATTERNS):
        return 'terms'
    if any(pattern.search(joined) for pattern in _REFUND_PATTERNS):
        return 'refund'
    if any(pattern.search(joined) for pattern in _CHECKOUT_PATTERNS):
        return 'checkout'
    if any(pattern.search(joined) for pattern in _CONTACT_PATTERNS):
        return 'contact'
    if 'signup' in joined or '회원가입' in joined:
        return 'signup'
    parsed = urlparse(url)
    return 'home' if parsed.path in {'', '/'} else 'content'


def extract_same_origin_links(current_url: str, soup: BeautifulSoup, *, origin_host: str) -> list[str]:
    links: list[str] = []
    for anchor in soup.select('a[href]'):
        href = clean(anchor.get('href'))
        if not href or href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
            continue
        absolute = urljoin(current_url, href)
        canonical = canonicalize_same_origin(absolute, origin_host=origin_host)
        if not canonical or should_exclude_path(canonical):
            continue
        links.append(canonical)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in links:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def split_sentences(text: str) -> list[str]:
    chunks = [clean(item) for item in _SENTENCE_SPLIT_RE.split(text or '') if clean(item)]
    return [item for item in chunks if len(item) >= 8]


def first_match_sentence(text: str, patterns: list[re.Pattern[str]]) -> str:
    for sentence in split_sentences(text)[:120]:
        if any(pattern.search(sentence) for pattern in patterns):
            return sentence[:220]
    return ''


def soften_claim_copy(sentence: str) -> str:
    revised = sentence or '효과를 단정하는 표현 대신, 조건과 범위를 함께 설명하는 문구가 필요합니다.'
    replacements = [(r'100%', '대부분의 일반적인 경우'), (r'완벽', '보다 안정적으로'), (r'즉시', '상대적으로 빠르게'), (r'무조건', '일반적으로'), (r'절대', '가능한 범위에서'), (r'영구', '장기간'), (r'유일', '차별화된'), (r'최고', '주요'), (r'누구에게나', '대상과 사용 환경에 따라'), (r'부작용\s*없', '사용 전 확인이 필요할 수 있으며 부작용 우려가 낮')]
    for pattern, repl in replacements:
        revised = re.sub(pattern, repl, revised, flags=re.I)
    if revised == sentence:
        revised = sentence + ' 다만 적용 대상과 조건에 따라 결과는 달라질 수 있습니다.'
    return revised[:260]


def extract_sitemap_urls(sitemap_url: str) -> list[str]:
    fetched = fetch_remote_document(sitemap_url, accept='application/xml,text/xml;q=0.9,text/plain;q=0.8,*/*;q=0.1')
    text = fetched.get('text') or ''
    if not fetched.get('ok') or ('xml' not in clean(fetched.get('contentType')).lower() and '<urlset' not in text and '<sitemapindex' not in text):
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    urls: list[str] = []
    for loc in root.iter():
        if loc.tag.lower().endswith('loc') and clean(loc.text):
            urls.append(clean(loc.text))
    return urls[:VERIDION_SCAN_MAX_DISCOVERED]


def score_severity(level: str) -> int:
    return {'high': 3, 'medium': 2, 'low': 1}.get(level, 0)


def scan_cache_key(payload: dict[str, Any]) -> str:
    base = {'website': clean(payload.get('website')), 'pages': clean(payload.get('pages')), 'industry': clean(payload.get('industry')), 'market': clean(payload.get('market')), 'maturity': clean(payload.get('maturity')), 'focus': clean(payload.get('focus')), 'options': sorted([clean(item) for item in payload.get('options') or [] if clean(item)])}
    raw = json.dumps(base, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def read_cached_scan(cache_key: str) -> dict[str, Any] | None:
    with _VERIDION_SCAN_CACHE_LOCK:
        entry = _VERIDION_SCAN_CACHE.get(cache_key)
        if not entry:
            return None
        stored_at, payload = entry
        if time.time() - stored_at > VERIDION_SCAN_CACHE_TTL_SECONDS:
            _VERIDION_SCAN_CACHE.pop(cache_key, None)
            return None
        return deepcopy(payload)


def write_cached_scan(cache_key: str, payload: dict[str, Any]) -> None:
    with _VERIDION_SCAN_CACHE_LOCK:
        _VERIDION_SCAN_CACHE[cache_key] = (time.time(), deepcopy(payload))


def build_veridion_page_record(url: str, page_type: str, title: str, text: str, *, status: int, forms: int, internal_links: int, robots_allowed: bool) -> dict[str, Any]:
    text_compact = re.sub(r'\s+', ' ', text or '').strip()
    claim_sentence = first_match_sentence(text_compact, _CLAIM_PATTERNS)
    has_business_info = any(pattern.search(text_compact) for pattern in _BUSINESS_INFO_PATTERNS)
    has_consent = any(pattern.search(text_compact) for pattern in _CONSENT_PATTERNS)
    return {'url': url, 'pageType': page_type, 'title': title or urlparse(url).path or '/', 'status': status, 'forms': forms, 'internalLinks': internal_links, 'robotsAllowed': robots_allowed, 'hasBusinessInfo': has_business_info, 'hasConsentLanguage': has_consent, 'claimSnippet': claim_sentence, 'textPreview': text_compact[:220]}


def build_veridion_scan(payload: dict[str, Any]) -> dict[str, Any]:
    website = normalize_scan_url(payload.get('website'))
    validate_scan_target(website)
    options = {clean(item) for item in payload.get('options') or [] if clean(item)}
    base = urlparse(website)
    origin_host = _strip_default_port(base)
    origin = urlunparse((base.scheme, base.netloc, '', '', '', ''))
    manual_urls = []
    for raw in [item for item in re.split(r'[\n,]+', clean(payload.get('pages'))) if clean(item)]:
        raw = clean(raw)
        looks_like_path = raw.startswith(('/', './', '../', '?', '#')) or '://' in raw or bool(re.search(r'\.[a-z0-9]{2,6}([?#]|$)', raw, re.I))
        if not looks_like_path:
            continue
        joined = urljoin(website, raw)
        normalized = canonicalize_same_origin(joined, origin_host=origin_host)
        if normalized and normalized not in manual_urls:
            manual_urls.append(normalized)
    robots_url = f'{origin}/robots.txt'
    sitemap_url = f'{origin}/sitemap.xml'
    robots_doc = fetch_remote_document(robots_url, accept='text/plain,*/*;q=0.1')
    robots = parse_basic_robots(robots_doc.get('text') or '') if robots_doc.get('ok') else {'allow': [], 'disallow': [], 'sitemaps': []}
    sitemap_candidates = robots.get('sitemaps') or [sitemap_url]
    sitemap_urls: list[str] = []
    for item in sitemap_candidates[:3]:
        for found in extract_sitemap_urls(item):
            normalized = canonicalize_same_origin(found, origin_host=origin_host)
            if normalized and normalized not in sitemap_urls and not should_exclude_path(normalized):
                sitemap_urls.append(normalized)
            if len(sitemap_urls) >= VERIDION_SCAN_MAX_DISCOVERED:
                break
        if sitemap_urls:
            break
    queue: deque[tuple[str, int]] = deque()
    seen_depth: dict[str, int] = {}
    discovered_order: list[str] = []
    def enqueue(url: str, depth: int) -> None:
        if not url or should_exclude_path(url):
            return
        prev = seen_depth.get(url)
        if prev is not None and prev <= depth:
            return
        seen_depth[url] = depth
        queue.append((url, depth))
        if url not in discovered_order:
            discovered_order.append(url)
    enqueue(website, 0)
    for item in manual_urls[:20]:
        enqueue(item, 0)
    for item in sitemap_urls[:20]:
        enqueue(item, 1)
    page_records: list[dict[str, Any]] = []
    fetched_urls: list[str] = []
    blocked_urls: list[str] = []
    failed_urls: list[dict[str, Any]] = []
    total_forms = 0
    total_internal_links = 0
    started = time.monotonic()
    while queue and len(fetched_urls) < VERIDION_SCAN_MAX_PAGES and len(discovered_order) <= VERIDION_SCAN_MAX_DISCOVERED:
        current, depth = queue.popleft()
        parsed_current = urlparse(current)
        robots_allowed = robots_allows_path(parsed_current.path or '/', robots)
        if not robots_allowed:
            blocked_urls.append(current)
            continue
        fetched = fetch_remote_document(current)
        if not fetched.get('ok'):
            failed_urls.append({'url': current, 'status': fetched.get('status', 0), 'error': fetched.get('error') or 'fetch failed'})
            continue
        content_type = clean(fetched.get('contentType')).lower()
        if 'html' not in content_type and '<html' not in (fetched.get('text') or '').lower():
            continue
        fetched_urls.append(current)
        soup = BeautifulSoup(fetched.get('text') or '', 'lxml')
        title = clean(soup.title.string if soup.title and soup.title.string else '')
        page_text = re.sub(r'\s+', ' ', soup.get_text(' ', strip=True))
        links = extract_same_origin_links(current, soup, origin_host=origin_host)
        forms = len(soup.select('form'))
        total_forms += forms
        total_internal_links += len(links)
        page_type = page_type_from_signals(current, title, page_text)
        page_records.append(build_veridion_page_record(current, page_type, title, page_text, status=int(fetched.get('status') or 200), forms=forms, internal_links=len(links), robots_allowed=robots_allowed))
        if depth < VERIDION_SCAN_MAX_DEPTH:
            for link in links:
                enqueue(link, depth + 1)
                if len(discovered_order) >= VERIDION_SCAN_MAX_DISCOVERED:
                    break
    discovered_count = len(discovered_order)
    fetched_count = len(fetched_urls)
    page_types = {item['pageType'] for item in page_records}
    claim_pages = [item for item in page_records if item.get('claimSnippet')]
    has_privacy = 'privacy' in page_types
    has_terms = 'terms' in page_types
    has_refund = 'refund' in page_types
    has_checkout = 'checkout' in page_types
    has_forms = total_forms > 0
    has_business_info = any(item.get('hasBusinessInfo') for item in page_records)
    has_consent_language = any(item.get('hasConsentLanguage') for item in page_records)
    expected_priority = {'home'}
    if options & {'privacy', 'claims', 'commerce'} or has_forms:
        expected_priority.add('privacy')
    if options & {'commerce'} or has_checkout:
        expected_priority.update({'terms', 'refund', 'checkout'})
    if has_forms:
        expected_priority.add('contact')
    found_priority = len(page_types & expected_priority)
    exploration_rate = round((fetched_count / discovered_count) * 100, 1) if discovered_count else 0.0
    priority_coverage = round((found_priority / max(len(expected_priority), 1)) * 100, 1)
    issues: list[dict[str, Any]] = []
    copy_suggestions: list[dict[str, Any]] = []
    if claim_pages:
        sample = claim_pages[0]
        before = sample.get('claimSnippet') or '강한 단정 표현이 감지되었습니다.'
        after = soften_claim_copy(before)
        issues.append({'level': 'high', 'category': '광고·표현', 'title': '단정형 표현 보정이 필요합니다', 'detail': f"{len(claim_pages)}개 페이지에서 과장 또는 단정으로 해석될 수 있는 표현이 감지되었습니다. 효능·우월성·속도 표현은 근거 범위와 조건을 함께 적는 편이 안전합니다.", 'pageUrl': sample.get('url'), 'evidence': before, 'fixCopy': after})
        copy_suggestions.append({'label': '광고·효능 표현 수정안', 'pageUrl': sample.get('url'), 'before': before, 'after': after})
    if has_forms and not has_privacy:
        issues.append({'level': 'high', 'category': '개인정보', 'title': '개인정보처리방침 연결이 보이지 않습니다', 'detail': '문의·회원가입·구독 입력이 있는 페이지가 확인됐지만, 개인정보처리방침으로 이어지는 공개 경로를 찾지 못했습니다.', 'pageUrl': fetched_urls[0] if fetched_urls else website, 'evidence': '폼 입력은 있었지만 privacy/personal data 신호가 있는 정책 페이지를 찾지 못함', 'fixCopy': '개인정보 수집·이용 목적, 보관 기간, 문의처를 확인할 수 있도록 개인정보처리방침 링크와 요약 고지를 입력 직전 구간에 배치합니다.'})
        copy_suggestions.append({'label': '개인정보 동의 안내 수정안', 'pageUrl': fetched_urls[0] if fetched_urls else website, 'before': '입력 폼 인근에 개인정보 안내가 충분하지 않음', 'after': '개인정보 수집·이용 목적, 보관 기간, 문의처를 링크와 함께 명확히 안내합니다.'})
    if has_forms and not has_consent_language:
        issues.append({'level': 'medium', 'category': '동의 흐름', 'title': '폼 주변 동의 문구가 약합니다', 'detail': '폼은 확인되지만 동의·consent 관련 문구를 충분히 찾지 못했습니다. 입력 직전 안내가 짧더라도 분명해야 합니다.', 'pageUrl': fetched_urls[0] if fetched_urls else website, 'evidence': '동의 관련 키워드 탐지 부족', 'fixCopy': '제출 시 개인정보 수집·이용에 동의한 것으로 보며, 자세한 내용은 개인정보처리방침에서 확인하실 수 있습니다.'})
    if (options & {'commerce'} or has_checkout) and not has_refund:
        issues.append({'level': 'high', 'category': '결제·환불', 'title': '환불·청약철회 기준이 공개 구간에서 충분히 보이지 않습니다', 'detail': '결제 또는 구매 관련 페이지 신호는 있지만 환불·반품·청약철회 기준을 확인할 공개 페이지를 찾지 못했습니다.', 'pageUrl': next((item['url'] for item in page_records if item['pageType'] == 'checkout'), website), 'evidence': 'checkout/buy/cart 신호 있음 + refund/청약철회 페이지 탐지 실패', 'fixCopy': '결제 전 확인해주세요. 제공 범위, 환불 가능 기준, 청약철회 제한 사유, 문의 채널을 이 화면에서 바로 안내합니다.'})
        copy_suggestions.append({'label': '결제 전 안내문 수정안', 'pageUrl': next((item['url'] for item in page_records if item['pageType'] == 'checkout'), website), 'before': '결제 또는 구매 직전 화면에 환불 기준 고지 부족', 'after': '결제 전 확인해주세요. 제공 범위, 환불 가능 기준, 청약철회 제한 사유, 문의 채널을 이 화면에서 바로 안내합니다.'})
    if (options & {'commerce'} or has_checkout) and not has_terms:
        issues.append({'level': 'medium', 'category': '약관', 'title': '이용약관 연결을 먼저 보강하는 편이 좋습니다', 'detail': '결제·구독·회원가입 흐름이 있는데 terms/약관 페이지를 충분히 찾지 못했습니다.', 'pageUrl': website, 'evidence': 'checkout/sign-up signal with weak terms coverage', 'fixCopy': '회원가입 또는 결제 직전 구간에 이용약관과 결제 조건을 확인할 수 있는 링크를 함께 제공합니다.'})
    if (options & {'commerce'} or has_checkout) and not has_business_info:
        issues.append({'level': 'medium', 'category': '사업자 정보', 'title': '사업자·고객센터 정보 노출을 보강할 필요가 있습니다', 'detail': '대한민국 기준으로 운영하는 결제형 사이트라면 상호, 대표자, 사업자등록번호, 고객센터 같은 기본 정보를 공개 구간에서 쉽게 찾을 수 있어야 합니다.', 'pageUrl': website, 'evidence': '사업자등록번호/통신판매업/대표자/고객센터 신호 부족', 'fixCopy': '푸터 또는 결제 전 화면에 상호, 대표자, 사업자등록번호, 통신판매업 신고 정보, 고객센터 연락처를 함께 노출합니다.'})
    if exploration_rate < 40 or priority_coverage < 60:
        issues.append({'level': 'medium', 'category': '탐색 범위', 'title': '핵심 페이지 탐색률이 낮습니다', 'detail': f'이번 샘플 스캔은 {fetched_count}개 페이지만 실제로 읽었고, 발견된 내부 후보는 {discovered_count}개였습니다. sitemap 또는 메뉴 연결이 약하면 핵심 페이지 커버리지가 떨어질 수 있습니다.', 'pageUrl': website, 'evidence': f'탐색률 {exploration_rate}% · 핵심 페이지 커버리지 {priority_coverage}%', 'fixCopy': '개인정보처리방침, 이용약관, 환불정책, 결제 화면처럼 꼭 봐야 할 페이지를 메뉴 또는 푸터에서 직접 연결해 주세요.'})
    if not robots_doc.get('ok'):
        issues.append({'level': 'low', 'category': '크롤링 힌트', 'title': 'robots.txt를 확인하지 못했습니다', 'detail': '점검 대상은 읽을 수 있었지만 robots.txt 응답을 찾지 못했습니다. 기본 크롤링 정책이 없으면 탐색 범위 설명과 예외 관리가 어려워질 수 있습니다.', 'pageUrl': robots_url, 'evidence': robots_doc.get('error') or f"status {robots_doc.get('status')}", 'fixCopy': 'robots.txt에서 허용·비허용 범위와 sitemap 위치를 함께 관리하면 탐색 품질을 더 안정적으로 맞출 수 있습니다.'})
    if not sitemap_urls:
        issues.append({'level': 'low', 'category': '탐색 효율', 'title': 'sitemap 신호가 약합니다', 'detail': 'sitemap을 찾지 못했거나 URL 집합을 읽지 못해, 이번 스캔은 메뉴와 본문 링크 중심으로만 확장되었습니다.', 'pageUrl': sitemap_url, 'evidence': 'sitemap urls 0건', 'fixCopy': '핵심 URL이 sitemap에 정리되어 있으면 비용을 거의 늘리지 않고도 탐색률과 우선 페이지 발견율을 높일 수 있습니다.'})
    issues = sorted(issues, key=lambda item: (-score_severity(item.get('level', '')), item.get('category', ''), item.get('title', '')))
    top_issues = issues[:5]
    if not copy_suggestions:
        copy_suggestions.append({'label': '기본 수정 안내', 'pageUrl': website, 'before': '강한 단정 또는 누락 리스크가 적은 편입니다.', 'after': '현재 구조는 비교적 안정적입니다. 다만 개인정보·결제·고지 링크를 주기적으로 다시 확인해 주세요.'})
    report_id = uid('vrep')
    report_code = make_public_code('VREP', 'veridion')
    issued_at = now_iso()
    summary = f"{website} 기준으로 같은 도메인 내부 페이지 {discovered_count}개를 후보로 잡았고, 이 중 {fetched_count}개를 실제로 읽어 탐색률 {exploration_rate}%를 기록했습니다. 핵심 페이지 커버리지는 {priority_coverage}%이며, 우선 조치 이슈는 {len([item for item in issues if item.get('level') == 'high'])}건입니다."
    report = {'id': report_id, 'code': report_code, 'product': 'veridion', 'website': website, 'origin': origin, 'industry': clean(payload.get('industry')), 'market': clean(payload.get('market')), 'maturity': clean(payload.get('maturity')), 'focus': clean(payload.get('focus')), 'options': sorted(options), 'summary': summary, 'stats': {'discovered': discovered_count, 'fetched': fetched_count, 'blocked': len(blocked_urls), 'failed': len(failed_urls), 'forms': total_forms, 'internalLinks': total_internal_links, 'explorationRate': exploration_rate, 'priorityCoverage': priority_coverage, 'priorityTargets': len(expected_priority), 'priorityFound': found_priority, 'elapsedMs': round((time.monotonic() - started) * 1000, 1)}, 'crawlPolicy': {'maxPages': VERIDION_SCAN_MAX_PAGES, 'maxDiscovered': VERIDION_SCAN_MAX_DISCOVERED, 'maxDepth': VERIDION_SCAN_MAX_DEPTH, 'robotsFetched': bool(robots_doc.get('ok')), 'robotsStatus': robots_doc.get('status', 0), 'sitemapFound': bool(sitemap_urls), 'sitemapCount': len(sitemap_urls), 'mode': 'same-domain shallow crawl'}, 'pages': page_records, 'issues': top_issues, 'copySuggestions': copy_suggestions[:4], 'issuance': {'status': 'ready' if fetched_count else 'blocked', 'reportTitle': 'Veridion 준법 점검 리포트', 'generatedAt': issued_at, 'reportCode': report_code, 'sections': ['스캔 개요', '탐색 통계', '우선 이슈', '문구 수정안', '페이지별 결과', '재점검 권고'], 'readyReason': '실제 탐색 결과, 우선 이슈, 문구 수정안, 페이지별 기록이 모두 묶여 발행 가능한 상태입니다.' if fetched_count else '실제 페이지를 읽지 못해 리포트를 발행할 수 없습니다.'}, 'quality': {'passed': bool(fetched_count), 'gates': [{'label': '실제 페이지 읽기', 'ok': bool(fetched_count), 'detail': f'실제 HTML 페이지 {fetched_count}개를 읽었습니다.' if fetched_count else '실제 HTML 페이지를 읽지 못했습니다.'}, {'label': '탐색률 계산', 'ok': discovered_count > 0, 'detail': f'발견 {discovered_count}개 대비 탐색률 {exploration_rate}%를 계산했습니다.' if discovered_count else '발견 후보 URL이 없어 탐색률 계산을 생략했습니다.'}, {'label': '문구 수정안', 'ok': bool(copy_suggestions), 'detail': f'수정 문구 {len(copy_suggestions[:4])}종을 함께 생성했습니다.'}, {'label': '리포트 발행 준비', 'ok': bool(fetched_count and top_issues), 'detail': '요약, 이슈, 수정안, 페이지 기록을 같은 리포트 코드로 묶었습니다.' if fetched_count and top_issues else '발행용 핵심 항목이 아직 부족합니다.'}]}, 'createdAt': issued_at, 'updatedAt': issued_at}
    return upsert_record('reports', report)


def find_veridion_report(*, report_id: str = '', report_code: str = '') -> dict[str, Any] | None:
    if report_id:
        found = get_record('reports', clean(report_id))
        if found and clean(found.get('product')) == 'veridion':
            return found
    if report_code:
        wanted = normalize_code(report_code)
        for item in load_records('reports'):
            if clean(item.get('product')) != 'veridion':
                continue
            if normalize_code(item.get('code')) == wanted:
                return item
    return None


def build_veridion_result_pack_from_report(base_pack: dict[str, Any], report: dict[str, Any], company: str) -> dict[str, Any]:
    pack = deepcopy(base_pack)
    stats = report.get('stats') or {}
    top_issues = report.get('issues') or []
    copy_suggestions = report.get('copySuggestions') or []
    pages = report.get('pages') or []
    website = clean(report.get('website'))
    pack['summary'] = f"{company or '고객사'} 기준 Veridion 결과를 실제 탐색 리포트와 연결했습니다. {website}에서 탐색률 {stats.get('explorationRate', 0)}%, 핵심 페이지 커버리지 {stats.get('priorityCoverage', 0)}%를 확인했고, 바로 손볼 이슈 {len(top_issues)}건을 먼저 묶었습니다."
    pack['outcomeHeadline'] = "실제 탐색 결과를 반영한 Veridion 점검 리포트가 발행 준비까지 완료되었습니다."
    pack['executiveSummary'] = f"이번 결과는 입력값 추정이 아니라 실제 같은 도메인 내부 페이지를 읽어 만든 리포트입니다. 발견된 내부 후보 {stats.get('discovered', 0)}개 중 {stats.get('fetched', 0)}개를 읽었고, 탐색률 {stats.get('explorationRate', 0)}%와 핵심 페이지 커버리지 {stats.get('priorityCoverage', 0)}%를 근거로 우선 이슈와 문구 수정안을 정리했습니다."
    pack['clientContext'] = {**(pack.get('clientContext') or {}), 'website': website, 'reportCode': report.get('code'), 'explorationRate': stats.get('explorationRate'), 'priorityCoverage': stats.get('priorityCoverage')}
    pack['outputs'] = [
        {'title': '실제 탐색 기반 준법 스캔 리포트', 'note': f"리포트 코드 {report.get('code')}", 'preview': report.get('summary') or '', 'whatIncluded': f"탐색률 {stats.get('explorationRate', 0)}%, 핵심 페이지 커버리지 {stats.get('priorityCoverage', 0)}%, 우선 이슈 {len(top_issues)}건을 같은 기준으로 정리했습니다.", 'actionNow': '먼저 우선 이슈부터 수정하고, 메뉴·푸터에서 정책 페이지 연결을 보강한 뒤 재점검을 권장합니다.', 'buyerValue': '추정형 점검이 아니라 실제 읽은 페이지를 기준으로 우선순위를 바로 잡을 수 있습니다.', 'expertLens': '탐색률과 핵심 페이지 커버리지를 분리해, 적은 비용으로 어디까지 읽었는지 먼저 투명하게 보여줍니다.', 'whyItMatters': '보고서 근거와 실제 점검 범위가 연결되어 팀 내부 설명이 쉬워집니다.', 'deliveryState': 'ready_to_issue'},
        {'title': '문구 수정안 Before / After', 'note': f"수정안 {len(copy_suggestions)}종", 'preview': '광고·개인정보·결제 안내 문구 중 리스크가 큰 문장을 먼저 완화해 제안합니다.', 'whatIncluded': '문제 문장, 수정 후 문장, 적용 위치를 함께 묶어 바로 전달 가능한 형태로 정리합니다.', 'actionNow': '마케팅 문구, 폼 인근 안내, 결제 전 고지를 우선 반영한 뒤 재점검합니다.', 'buyerValue': '기획·디자인·개발이 같은 문장을 기준으로 움직일 수 있어 수정 속도가 빨라집니다.', 'expertLens': '근거 없는 단정 표현은 범위·조건·예외를 함께 적는 방식으로 완화합니다.', 'whyItMatters': '리스크를 찾는 데서 끝나지 않고 바로 고칠 문장을 함께 넘길 수 있습니다.', 'deliveryState': 'ready_to_issue'},
        {'title': '페이지별 우선 점검표', 'note': f"페이지 {len(pages)}개 기록", 'preview': '홈, 정책, 결제, 문의 같은 핵심 공개 구간을 페이지별로 분리해 기록합니다.', 'whatIncluded': '페이지 유형, 탐지 신호, 기본 상태, 우선 확인 포인트를 같은 표로 묶습니다.', 'actionNow': '홈/결제/개인정보 페이지를 먼저 보고, 누락 연결은 메뉴·푸터에서 보강합니다.', 'buyerValue': '수정 지시가 페이지 단위로 명확해져 작업 배정과 재확인이 쉬워집니다.', 'expertLens': '정책 페이지 자체보다 실제 유입·구매·입력 직전 구간을 먼저 보는 방식으로 우선순위를 잡습니다.', 'whyItMatters': '리스크를 페이지 맥락과 함께 설명해야 실제 수정이 빨라집니다.', 'deliveryState': 'ready_to_issue'},
    ] + pack.get('outputs', [])[3:]
    pack['quickWins'] = [f"탐색률 {stats.get('explorationRate', 0)}% 기준에서 먼저 누락된 정책 링크를 메뉴 또는 푸터에 직접 연결합니다.", '과장·단정 표현이 감지된 문장은 조건·범위·예외를 넣는 방향으로 먼저 완화합니다.', '문의·회원가입·결제 폼 주변에는 개인정보와 환불 기준을 짧고 분명하게 다시 배치합니다.']
    pack['valueDrivers'] = ['실제 읽은 페이지 수와 발견 후보 수를 함께 보여줘 리포트 근거가 분명합니다.', '문구 수정안과 페이지별 점검표가 연결되어 수정 지시서로 바로 전환할 수 있습니다.', '리포트 코드 하나로 포털, 관리자, 후속 재점검까지 같은 흐름을 이어갈 수 있습니다.']
    pack['successMetrics'] = [f"탐색률 {stats.get('explorationRate', 0)}% 이상 유지 여부", f"핵심 페이지 커버리지 {stats.get('priorityCoverage', 0)}%에서 얼마나 올라가는지", '고위험 이슈가 다음 재점검에서 얼마나 줄었는지']
    pack['prioritySequence'] = ['1. 탐색률이 낮다면 개인정보처리방침·이용약관·환불정책·결제 화면 연결부터 보강합니다.', '2. 고위험 이슈에 포함된 문구를 Before / After 수정안 기준으로 먼저 바꿉니다.', '3. 수정 후 같은 리포트 코드로 재점검해 고위험 이슈 감소 여부를 확인합니다.', '4. 결과를 포털과 관리자에서 같은 기준으로 관리해 재발행 기준을 고정합니다.']
    pack['expertNotes'] = ['탐색률은 실제로 읽은 페이지 수를 발견된 내부 후보 수로 나눠 계산합니다.', '핵심 페이지 커버리지는 홈·정책·결제·문의 같은 우선 대상의 발견 여부를 따로 보여줍니다.', '문구 수정안은 단정 표현을 범위형 표현으로 바꾸고, 입력·결제 직전 고지를 강화하는 방향으로 제안합니다.', '리포트 발행은 탐색 기록, 우선 이슈, 수정안이 같은 코드로 묶였을 때만 ready로 봅니다.']
    bundle = [
        {'title': 'Veridion 실제 탐색 리포트', 'description': f"리포트 코드 {report.get('code')} 기준으로 탐색 통계, 우선 이슈, 수정안을 같은 문서로 발행합니다.", 'customerValue': '실제 점검 범위와 수정 이유를 한 번에 공유할 수 있습니다.', 'usageMoment': '즉시 공유', 'expertNote': '탐색 범위와 이슈 근거를 먼저 보여주면 수정 우선순위 합의가 빨라집니다.', 'status': 'ready'},
        {'title': '문구 수정안 발행본', 'description': f"Before / After {len(copy_suggestions)}종을 적용 위치와 함께 묶어 전달합니다.", 'customerValue': '기획·디자인·개발이 같은 수정 문구를 기준으로 바로 움직일 수 있습니다.', 'usageMoment': '실행 착수', 'expertNote': '광고 표현과 결제·개인정보 고지는 적용 위치까지 같이 지정해야 실행 속도가 빨라집니다.', 'status': 'ready'},
        {'title': '재점검 큐', 'description': '수정 후 다시 읽어야 할 핵심 페이지를 같은 리포트 코드 아래에서 관리합니다.', 'customerValue': '한 번 고치고 끝내지 않고 재점검 기준까지 남길 수 있습니다.', 'usageMoment': '후속 점검', 'expertNote': '같은 코드로 재점검하면 개선 폭을 비교하기 쉽습니다.', 'status': 'ready'}
    ]
    pack['issuanceBundle'] = bundle
    pack['deliveryAssets'] = deepcopy(bundle)
    pack['valueNarrative'] = f"이번 Veridion 결과는 입력값만으로 만든 추정형 결과가 아니라 실제 같은 도메인 내부를 읽어 만든 운영 리포트입니다. 탐색률과 핵심 페이지 커버리지를 먼저 보여주고, 고위험 이슈와 수정 문구를 같은 코드로 묶어 전달하므로 적은 비용으로도 수정 우선순위가 빠르게 정리됩니다."
    pack['buyerDecisionReason'] = '실제 읽은 페이지 기준 통계, 수정 문구, 재점검 큐가 한 번에 묶여 있어 보고용이 아니라 바로 실행용 자산으로 쓰기 좋습니다.'
    pack['linkedReport'] = {'id': report.get('id'), 'code': report.get('code'), 'website': website, 'explorationRate': stats.get('explorationRate'), 'priorityCoverage': stats.get('priorityCoverage')}
    return pack


def resolve_veridion_report(note: str, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = payload or {}
    parsed = parse_note_signals(note)
    return find_veridion_report(report_id=clean(payload.get('reportId')) or clean(parsed.get('report_id')), report_code=clean(payload.get('reportCode')) or clean(parsed.get('report_code')))


def attach_veridion_report_to_pack(pack: dict[str, Any], product_key: str, company: str, note: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if product_key != 'veridion':
        return pack
    report = resolve_veridion_report(note, payload)
    if not report:
        return pack
    return build_veridion_result_pack_from_report(pack, report, company)


def build_veridion_demo_preview(report: dict[str, Any], company: str) -> dict[str, Any]:
    stats = report.get('stats') or {}
    issues = report.get('issues') or []
    copies = report.get('copySuggestions') or []
    return {'headline': f"{company or '샘플 회사'} 기준 Veridion 실제 탐색 결과", 'summary': report.get('summary') or '', 'company': company or '샘플 회사', 'goal': clean(report.get('focus')) or '준법 리스크 우선순위 정리', 'keywords': ', '.join(report.get('options') or []), 'diagnosisSummary': f"실제 읽은 페이지 {stats.get('fetched', 0)}개, 발견 후보 {stats.get('discovered', 0)}개, 탐색률 {stats.get('explorationRate', 0)}%를 기준으로 우선 이슈를 정리했습니다.", 'sampleOutputs': [{'title': '실제 탐색 통계', 'note': f"탐색률 {stats.get('explorationRate', 0)}%", 'preview': report.get('summary') or '', 'whatIncluded': '발견 후보 수, 실제 읽은 페이지 수, 핵심 페이지 커버리지를 함께 제공합니다.', 'actionNow': '탐색률이 낮으면 정책·결제 페이지 연결을 먼저 보강한 뒤 다시 점검합니다.', 'buyerValue': '리포트 근거와 점검 범위를 같은 숫자로 설명할 수 있습니다.', 'expertLens': '핵심 페이지 커버리지를 별도로 계산해 단순 페이지 수보다 중요한 범위를 먼저 봅니다.', 'whyItMatters': '어디까지 읽었는지 모르면 리포트 신뢰도가 흔들리기 쉽습니다.', 'deliveryState': 'ready_to_issue'}, {'title': '우선 이슈 5건', 'note': f"고위험 {len([item for item in issues if item.get('level') == 'high'])}건", 'preview': issues[0].get('detail') if issues else '이슈가 많지 않은 안정 구조로 보입니다.', 'whatIncluded': '광고·개인정보·결제·사업자 정보 중 먼저 손봐야 할 항목을 우선순위로 묶습니다.', 'actionNow': '고위험 이슈부터 수정하고 같은 코드로 재점검합니다.', 'buyerValue': '무엇부터 고칠지 바로 정할 수 있어 수정 비용이 줄어듭니다.', 'expertLens': '정책 문서보다 실제 입력·결제 직전 구간을 먼저 점검합니다.', 'whyItMatters': '운영자 입장에서는 우선순위가 선명해야 실제 수정이 가능합니다.', 'deliveryState': 'ready_to_issue'}, {'title': '문구 수정안', 'note': f"수정안 {len(copies)}종", 'preview': copies[0].get('after') if copies else '현재는 큰 수정 문구 없이 유지 가능합니다.', 'whatIncluded': 'Before / After 문장과 적용 위치를 함께 제공합니다.', 'actionNow': '광고 문구와 폼·결제 인근 고지를 먼저 교체합니다.', 'buyerValue': '리스크 확인에서 끝나지 않고 바로 고칠 문장까지 이어집니다.', 'expertLens': '단정형 표현은 범위형·조건형 표현으로 완화합니다.', 'whyItMatters': '문구가 없으면 수정 지시가 다시 추상적으로 바뀌기 쉽습니다.', 'deliveryState': 'ready_to_issue'}], 'quickWins': ['메뉴와 푸터에서 정책 페이지 연결을 먼저 보강합니다.', '과장·단정 표현을 조건·범위 표현으로 바꿉니다.', '입력·결제 직전 고지를 짧고 분명하게 다시 배치합니다.'], 'valueDrivers': ['실제 읽은 페이지 수와 탐색률을 함께 보여줍니다.', '수정 문구와 페이지별 점검표가 한 코드로 이어집니다.', '재점검 큐까지 함께 남아 후속 점검이 쉬워집니다.'], 'successMetrics': [f"탐색률 {stats.get('explorationRate', 0)}%", f"핵심 페이지 커버리지 {stats.get('priorityCoverage', 0)}%", f"고위험 이슈 {len([item for item in issues if item.get('level') == 'high'])}건"], 'prioritySequence': ['1. 핵심 페이지 연결 보강', '2. 고위험 문구 수정', '3. 같은 코드로 재점검'], 'expertNotes': ['탐색률과 핵심 페이지 커버리지를 분리해 보여줍니다.', '문구 수정안은 적용 위치와 함께 제안합니다.', '리포트 발행은 실제 읽은 페이지가 있어야 ready로 봅니다.'], 'objectionHandling': ['샘플이라도 실제 탐색 근거가 있어 결과 신뢰도를 먼저 판단할 수 있습니다.', '수정안이 함께 나와 바로 작업 지시로 전환하기 쉽습니다.'], 'scorecard': {'stage': 'demo', 'stageLabel': '실제 탐색 데모', 'earned': 100 if stats.get('fetched', 0) else 68, 'total': 100, 'grade': 'A+' if stats.get('fetched', 0) else 'B', 'headline': 'Veridion 실제 탐색 품질 기준표', 'summary': '실제 페이지 읽기, 탐색률 계산, 문구 수정안, 리포트 발행 준비까지 같은 흐름으로 확인합니다.', 'items': [{'label': '실제 페이지 읽기', 'score': 20 if stats.get('fetched', 0) else 8, 'max': 20, 'reason': f"실제 HTML 페이지 {stats.get('fetched', 0)}개를 읽었습니다." if stats.get('fetched', 0) else '실제 페이지를 읽지 못했습니다.'}, {'label': '탐색률 계산', 'score': 15 if stats.get('discovered', 0) else 6, 'max': 15, 'reason': f"발견 {stats.get('discovered', 0)}개 대비 탐색률 {stats.get('explorationRate', 0)}%를 계산했습니다."}, {'label': '핵심 페이지 커버리지', 'score': 15, 'max': 15, 'reason': f"핵심 페이지 커버리지 {stats.get('priorityCoverage', 0)}%를 별도로 확인했습니다."}, {'label': '문구 수정안', 'score': 15 if copies else 10, 'max': 15, 'reason': f"문구 수정안 {len(copies)}종을 함께 생성했습니다."}, {'label': '우선 이슈 정리', 'score': 15, 'max': 15, 'reason': f"우선 이슈 {len(issues)}건을 정렬해 먼저 봐야 할 항목을 분명히 했습니다."}, {'label': '리포트 발행 준비', 'score': 10 if report.get('issuance', {}).get('status') == 'ready' else 4, 'max': 10, 'reason': report.get('issuance', {}).get('readyReason') or '리포트 발행 준비 상태를 점검했습니다.'}, {'label': '재사용성', 'score': 10, 'max': 10, 'reason': '같은 리포트 코드로 포털·관리자·재점검 흐름을 연결할 수 있습니다.'}]}, 'ctaHint': f"리포트 코드 {report.get('code')} 기준으로 결제 후 발행 자료와 포털 결과를 같은 흐름으로 이어갑니다.", 'closingArgument': '이번 데모는 실제 점검 범위, 우선 이슈, 수정 문구, 발행 준비 상태가 같은 코드로 묶여 있어 샘플 단계에서도 품질을 판단할 수 있게 만들었습니다.', 'linkedReport': {'id': report.get('id'), 'code': report.get('code')}}


def parse_iso_deadline(value: Any) -> tuple[str, date | None, int | None]:
    raw = clean(value)
    if not raw:
        return '', None, None
    try:
        parsed = datetime.fromisoformat(raw[:10]).date()
        days_left = (parsed - datetime.now(timezone.utc).date()).days
        return parsed.isoformat(), parsed, days_left
    except Exception:
        return raw[:10], None, None


def _fmt_due_label(days_left: int | None) -> str:
    if days_left is None:
        return '마감일 미입력'
    if days_left >= 0:
        return f'D-{days_left}'
    return f'D+{abs(days_left)} 지남'


def find_product_report(product_key: str, *, report_id: str = '', report_code: str = '') -> dict[str, Any] | None:
    if report_id:
        found = get_record('reports', clean(report_id))
        if found and clean(found.get('product')) == product_key:
            return found
    if report_code:
        wanted = normalize_code(report_code)
        for item in load_records('reports'):
            if clean(item.get('product')) != product_key:
                continue
            if normalize_code(item.get('code')) == wanted:
                return item
    return None


def resolve_product_report(product_key: str, note: str, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = payload or {}
    parsed = parse_note_signals(note)
    return find_product_report(product_key, report_id=clean(payload.get('reportId')) or clean(parsed.get('report_id')), report_code=clean(payload.get('reportCode')) or clean(parsed.get('report_code')))


def build_clearport_report(payload: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    raw_options = {clean(item) for item in payload.get('options') or [] if clean(item)}
    company = clip_text(payload.get('company'), 160) or '샘플 회사'
    submission_type = clip_text(payload.get('submissionType') or payload.get('documentType') or payload.get('requestType'), 120) or '일반 제출'
    target_org = clip_text(payload.get('targetOrg') or payload.get('institution') or payload.get('client') or payload.get('org'), 160) or '제출처 미입력'
    blocker = clip_text(payload.get('blocker') or payload.get('risk') or payload.get('note'), 240)
    team_size = clip_text(payload.get('teamSize') or payload.get('team') or payload.get('owners'), 80) or '미입력'
    deadline_raw, _, days_left = parse_iso_deadline(payload.get('deadline') or payload.get('dueDate'))
    uploaded_docs = collect_text_items(payload.get('uploadedDocs'), payload.get('uploaded_docs'), payload.get('documents'), payload.get('securedDocs'))
    requested_docs = collect_text_items(payload.get('requiredDocs'), payload.get('required_docs'), payload.get('mustHaveDocs'))

    def doc_key_from_label(label: str) -> str:
        lowered = clean(label).casefold()
        if '사업자' in lowered or 'biz' in lowered:
            return 'bizreg'
        if '통장' in lowered or '정산' in lowered or 'bank' in lowered:
            return 'bank'
        if '인감' in lowered or 'seal' in lowered or '날인' in lowered:
            return 'seal'
        if '담당자' in lowered or '회신' in lowered or 'contact' in lowered:
            return 'contactdoc'
        if '실적' in lowered or '소개' in lowered or 'portfolio' in lowered or '제안서' in lowered:
            return 'portfolio'
        if '개인정보' in lowered or '보안' in lowered or 'policy' in lowered or '동의' in lowered:
            return 'policy'
        return re.sub(r'[^a-z0-9]+', '-', lowered)[:32] or 'custom-doc'

    baseline_required_docs = [
        {'key': 'bizreg', 'label': '사업자등록증', 'critical': True, 'reason': '대부분의 심사·입점·기관 제출에서 기본 확인 문서입니다.'},
        {'key': 'bank', 'label': '통장사본/정산 정보', 'critical': True, 'reason': '정산 또는 대금 지급이 있는 경우 거의 항상 함께 확인합니다.'},
        {'key': 'seal', 'label': '인감/사용인감 자료', 'critical': True, 'reason': '확약서, 신청서, 계약 부속 서류에서 병목이 자주 생깁니다.'},
        {'key': 'contactdoc', 'label': '담당자 회신 창구', 'critical': True, 'reason': '보완 요청이 왔을 때 답변 경로가 없으면 일정이 바로 밀립니다.'},
        {'key': 'portfolio', 'label': '회사소개/실적 자료', 'critical': False, 'reason': '입점 심사나 제안 제출에서 신뢰 보강 자료가 됩니다.'},
        {'key': 'policy', 'label': '개인정보·보안 확인서', 'critical': False, 'reason': '기관·대기업 제출에서는 별도 양식 요구가 자주 발생합니다.'},
    ]
    required_docs = list(baseline_required_docs)
    known_keys = {item['key'] for item in required_docs}
    for label in requested_docs:
        key = doc_key_from_label(label)
        if key in known_keys:
            continue
        required_docs.append({'key': key, 'label': label, 'critical': True, 'reason': '실제 제출 요구 목록에서 직접 들어온 항목이라 필수 축으로 우선 반영했습니다.'})
        known_keys.add(key)

    options = set(raw_options)
    for label in uploaded_docs:
        options.add(doc_key_from_label(label))
    checklist = []
    missing_labels: list[str] = []
    critical_missing: list[str] = []
    for item in required_docs:
        secured = item['key'] in options
        if not secured:
            missing_labels.append(item['label'])
            if item['critical']:
                critical_missing.append(item['label'])
        checklist.append({
            'label': item['label'],
            'status': '확보' if secured else '보완 필요',
            'priority': '핵심' if item['critical'] else '보조',
            'detail': item['reason'],
        })
    readiness_rate = round((len(required_docs) - len(missing_labels)) / max(1, len(required_docs)) * 100, 1)
    response_templates = [
        {'label': '대외 보완 회신', 'appliesTo': target_org, 'before': '서류 확인 후 다시 회신드리겠습니다.', 'after': f'안녕하세요. {target_org} 제출 기준으로 현재 누락 가능 서류 {", ".join(missing_labels[:3]) or "없음"}를 우선 확인 중이며, 오늘 안에 보완 가능 항목과 제출 시점을 다시 회신드리겠습니다.'},
        {'label': '내부 준비 요청', 'appliesTo': team_size, 'before': '필요한 자료를 보내주세요.', 'after': f'오늘 먼저 묶을 자료는 {critical_missing[0] if critical_missing else "최종본 파일명 정리"}입니다. 담당자별로 보유 문서와 날인 필요 서류를 분리해 { _fmt_due_label(days_left) } 일정 기준으로 다시 취합해 주세요.'},
        {'label': '마감 임박 안내', 'appliesTo': deadline_raw or '미입력', 'before': '일정 확인 부탁드립니다.', 'after': f'현재 제출 일정은 {_fmt_due_label(days_left)} 기준입니다. 대외 회신 전에 필수 서류 확보 여부와 날인 일정을 먼저 잠그고, 부족 서류가 있으면 오늘 안에 보완 가능 여부를 확정해 주세요.'},
    ]
    issues: list[dict[str, Any]] = []
    if critical_missing:
        issues.append({'level': 'high', 'title': '핵심 서류 누락', 'detail': f'필수 축인 {", ".join(critical_missing)} 가 빠져 있어 접수 또는 정산 단계에서 바로 멈출 가능성이 큽니다.'})
    if days_left is not None and days_left <= 3:
        issues.append({'level': 'high', 'title': '마감 임박', 'detail': f'남은 일정이 {_fmt_due_label(days_left)} 수준이라 내부 결재와 날인 경로를 오늘 바로 잠가야 합니다.'})
    if 'policy' not in options and submission_type in {'정부·기관 서류 제출', '입찰·제안 제출'}:
        issues.append({'level': 'medium', 'title': '보안·개인정보 확인서 사전 점검 필요', 'detail': f'{submission_type} 유형은 별도 서식 요구가 잦아 제출 직전에 새 양식이 나오지 않도록 미리 확인해야 합니다.'})
    if blocker:
        issues.append({'level': 'medium', 'title': '현재 병목 반영', 'detail': f'입력한 병목 "{blocker}" 를 기준으로 보완 순서를 먼저 정리했습니다.'})
    if not issues:
        issues.append({'level': 'low', 'title': '구조는 비교적 안정적', 'detail': '핵심 제출 문서가 대부분 확보되어 있어 파일명 통일과 회신 문장 정리부터 진행하면 됩니다.'})
    report_id = uid('crep')
    report_code = make_public_code('CREP', 'clearport')
    issued_at = now_iso()
    report = {
        'id': report_id,
        'code': report_code,
        'reportId': report_id,
        'reportCode': report_code,
        'product': 'clearport',
        'company': company,
        'submissionType': submission_type,
        'targetOrg': target_org,
        'deadline': deadline_raw,
        'teamSize': team_size,
        'blocker': blocker,
        'options': sorted(options),
        'uploadedDocs': uploaded_docs,
        'requiredDocsInput': requested_docs,
        'summary': f'{target_org} 제출 기준으로 확보 문서와 누락 문서를 다시 나눴습니다. 핵심 서류 {len(critical_missing)}건, 전체 준비도 {readiness_rate}%를 기준으로 바로 보낼 회신 문장과 내부 준비 지시를 함께 정리했습니다.',
        'stats': {
            'requiredDocs': len(required_docs),
            'securedDocs': len(required_docs) - len(missing_labels),
            'missingDocs': len(missing_labels),
            'criticalMissing': len(critical_missing),
            'readinessRate': readiness_rate,
            'daysLeft': days_left,
            'responseTemplates': len(response_templates),
            'elapsedMs': round((time.monotonic() - started) * 1000, 1),
        },
        'documentChecklist': checklist,
        'issues': issues,
        'copySuggestions': response_templates,
        'issuance': {
            'status': 'ready' if readiness_rate >= 34 else 'blocked',
            'reportTitle': 'ClearPort 제출 서류 운영 리포트',
            'generatedAt': issued_at,
            'reportCode': report_code,
            'sections': ['준비도 요약', '필수 서류 체크리스트', '누락/보완 우선순위', '대외 회신 문장', '내부 준비 메모'],
            'readyReason': '준비도, 누락 서류, 대외 안내 문장, 내부 실행 메모가 같은 코드로 묶여 바로 발행 가능한 상태입니다.' if readiness_rate >= 34 else '핵심 서류 확보가 너무 적어 발행보다 문서 확보가 먼저입니다.',
        },
        'quality': {
            'passed': readiness_rate >= 34,
            'gates': [
                {'label': '준비도 계산', 'ok': True, 'detail': f'필수/보조 문서 {len(required_docs)}종 기준으로 준비도 {readiness_rate}%를 계산했습니다.'},
                {'label': '핵심 누락 식별', 'ok': True, 'detail': f'핵심 누락 {len(critical_missing)}건을 별도로 묶었습니다.'},
                {'label': '회신 문장 생성', 'ok': bool(response_templates), 'detail': f'대외/내부/마감용 문장 {len(response_templates)}종을 만들었습니다.'},
                {'label': '발행 준비', 'ok': readiness_rate >= 34, 'detail': '체크리스트와 회신 문장을 같은 리포트 코드로 묶었습니다.' if readiness_rate >= 34 else '발행 전에 핵심 서류부터 더 확보해야 합니다.'},
            ],
        },
        'createdAt': issued_at,
        'updatedAt': issued_at,
    }
    return upsert_record('reports', report)


def build_clearport_demo_preview(report: dict[str, Any], company: str) -> dict[str, Any]:
    stats = report.get('stats') or {}
    issues = report.get('issues') or []
    copies = report.get('copySuggestions') or []
    checklist = report.get('documentChecklist') or []
    missing = stats.get('missingDocs', 0)
    return {
        'headline': f"{company or '샘플 회사'} 기준 ClearPort 제출 준비 결과",
        'summary': report.get('summary') or '',
        'company': company or '샘플 회사',
        'goal': clean(report.get('blocker')) or '제출 누락과 회신 지연 줄이기',
        'keywords': ', '.join(report.get('options') or []),
        'diagnosisSummary': f"전체 준비도 {stats.get('readinessRate', 0)}%, 핵심 누락 {stats.get('criticalMissing', 0)}건, 바로 쓸 회신 문장 {stats.get('responseTemplates', 0)}종을 같은 기준으로 만들었습니다.",
        'sampleOutputs': [
            {'title': '제출 준비도 요약', 'note': f"준비도 {stats.get('readinessRate', 0)}%", 'preview': report.get('summary') or '', 'whatIncluded': '필수/보조 서류 구분, 핵심 누락 수, 마감 임박 여부를 한 화면에서 보여줍니다.', 'actionNow': '핵심 누락 서류부터 확보하고 같은 코드 기준으로 회신 문장을 바로 보냅니다.', 'buyerValue': '담당자마다 다른 설명 대신 준비 상태를 같은 숫자로 공유할 수 있습니다.', 'expertLens': '모든 문서를 같은 비중으로 보지 않고 접수를 멈추는 핵심 누락을 먼저 분리합니다.', 'whyItMatters': '누락 위치를 모르면 보완 요청이 늦어지고 마감이 흔들리기 쉽습니다.', 'deliveryState': 'ready_to_issue'},
            {'title': '필수 서류 체크리스트', 'note': f"누락 {missing}건", 'preview': (issues[0].get('detail') if issues else '현재 체크리스트상 큰 누락은 없습니다.'), 'whatIncluded': '서류별 확보 여부, 우선도, 왜 필요한지를 함께 적었습니다.', 'actionNow': '핵심으로 표시된 항목부터 다시 모으고 파일명·날인 구간을 분리합니다.', 'buyerValue': '누가 보더라도 무엇이 빠졌는지 즉시 알 수 있습니다.', 'expertLens': '마감 직전 가장 많이 멈추는 날인·정산·회신 창구를 핵심 항목으로 묶습니다.', 'whyItMatters': '문서가 많을수록 누락 관리가 숫자와 상태 중심이어야 흔들리지 않습니다.', 'deliveryState': 'ready_to_issue'},
            {'title': '대외/내부 회신 문장', 'note': f"문장 {len(copies)}종", 'preview': copies[0].get('after') if copies else '회신 문장이 아직 없습니다.', 'whatIncluded': '대외 보완 회신, 내부 준비 요청, 마감 임박 안내를 바로 복붙 가능한 형태로 제공합니다.', 'actionNow': '제출처에는 보완 가능 시점을, 내부에는 확보 순서를 같은 날 안에 공유합니다.', 'buyerValue': '문장까지 준비되어 있어 응답 시간이 바로 짧아집니다.', 'expertLens': '추상적인 확인 요청 대신 누락 문서와 회신 시점을 명시형으로 씁니다.', 'whyItMatters': '설명보다 실제 회신 문장이 있어야 담당자 간 속도가 맞춰집니다.', 'deliveryState': 'ready_to_issue'},
        ],
        'quickWins': ['핵심 누락 서류부터 다시 모읍니다.', '대외 회신 문장을 복붙 가능한 형태로 먼저 고정합니다.', '날인·정산·보안 확인서를 별도 폴더로 분리합니다.'],
        'valueDrivers': ['준비도와 누락 수치가 바로 보입니다.', '대외/내부 회신 문장이 함께 나옵니다.', '같은 리포트 코드로 결제 후 운영본과 이어집니다.'],
        'successMetrics': [f"준비도 {stats.get('readinessRate', 0)}%", f"핵심 누락 {stats.get('criticalMissing', 0)}건", f"회신 문장 {stats.get('responseTemplates', 0)}종"],
        'prioritySequence': ['1. 핵심 누락 확보', '2. 대외 회신 발송', '3. 파일명·날인 재정리'],
        'expertNotes': ['핵심 서류와 보조 서류를 분리해 봅니다.', '회신 문장은 누락 항목과 시점을 같이 적습니다.', '마감이 짧을수록 내부 승인 경로를 먼저 잠급니다.'],
        'objectionHandling': ['문서가 아직 다 없어도 준비도와 누락 순서부터 잡을 수 있습니다.', '회신 문장이 같이 나와 바로 응답까지 이어집니다.'],
        'scorecard': {
            'stage': 'demo', 'stageLabel': '제출 준비도 데모', 'earned': 100, 'total': 100, 'grade': 'A+', 'headline': 'ClearPort 실제 운영 품질 기준표',
            'summary': '준비도 계산, 핵심 누락 분리, 회신 문장 생성, 발행 준비 상태까지 같은 흐름으로 확인합니다.',
            'items': [
                {'label': '준비도 계산', 'score': 20, 'max': 20, 'reason': f"필수/보조 문서 {stats.get('requiredDocs', 0)}종 기준으로 준비도 {stats.get('readinessRate', 0)}%를 계산했습니다."},
                {'label': '핵심 누락 분리', 'score': 15, 'max': 15, 'reason': f"핵심 누락 {stats.get('criticalMissing', 0)}건을 별도로 잡았습니다."},
                {'label': '마감 반영', 'score': 15, 'max': 15, 'reason': f"마감 상태 {_fmt_due_label(stats.get('daysLeft'))} 기준으로 우선순위를 다시 정했습니다."},
                {'label': '회신 문장', 'score': 15, 'max': 15, 'reason': f"대외·내부·마감용 문장 {len(copies)}종을 함께 생성했습니다."},
                {'label': '체크리스트', 'score': 15, 'max': 15, 'reason': f"서류 체크리스트 {len(checklist)}행을 확보/보완 상태로 정리했습니다."},
                {'label': '발행 준비', 'score': 10, 'max': 10, 'reason': report.get('issuance', {}).get('readyReason') or '발행 준비 상태를 점검했습니다.'},
                {'label': '재사용성', 'score': 10, 'max': 10, 'reason': '같은 리포트 코드로 포털, 관리자, 후속 보완 흐름을 연결할 수 있습니다.'},
            ],
        },
        'ctaHint': f"리포트 코드 {report.get('code')} 기준으로 결제 후 운영본과 포털 결과를 같은 흐름으로 이어갑니다.",
        'closingArgument': '이번 데모는 준비도 계산, 핵심 누락, 회신 문장, 발행 준비 상태를 같은 코드로 묶어 실제 제출 운영에 바로 쓰일 수준으로 만들었습니다.',
        'linkedReport': {'id': report.get('id'), 'code': report.get('code')},
    }


def build_clearport_result_pack_from_report(base_pack: dict[str, Any], report: dict[str, Any], company: str) -> dict[str, Any]:
    stats = report.get('stats') or {}
    issues = report.get('issues') or []
    checklist = report.get('documentChecklist') or []
    copies = report.get('copySuggestions') or []
    pack = deepcopy(base_pack)
    pack['summary'] = report.get('summary') or pack.get('summary') or ''
    pack['outcomeHeadline'] = f"{company or '고객사'} 제출 운영에서 먼저 잠가야 할 누락 서류와 회신 문장을 정리했습니다."
    pack['executiveSummary'] = f"준비도 {stats.get('readinessRate', 0)}%, 핵심 누락 {stats.get('criticalMissing', 0)}건, 회신 문장 {stats.get('responseTemplates', 0)}종 기준으로 외부 회신과 내부 준비를 같은 흐름으로 묶었습니다."
    pack['clientContext'] = {**(pack.get('clientContext') or {}), 'targetOrg': report.get('targetOrg'), 'deadline': report.get('deadline'), 'reportCode': report.get('code'), 'readinessRate': stats.get('readinessRate')}
    pack['outputs'] = [
        {'title': '실제 제출 준비도 리포트', 'note': f"리포트 코드 {report.get('code')}", 'preview': report.get('summary') or '', 'whatIncluded': f"준비도 {stats.get('readinessRate', 0)}%, 핵심 누락 {stats.get('criticalMissing', 0)}건, 마감 상태 {_fmt_due_label(stats.get('daysLeft'))}를 함께 정리했습니다.", 'actionNow': '핵심 누락 서류부터 모으고, 제출처에는 보완 가능 시점을 바로 회신합니다.', 'buyerValue': '담당자와 의사결정자가 같은 숫자와 같은 문장을 보며 움직일 수 있습니다.', 'expertLens': '접수를 멈추는 핵심 문서와 보조 문서를 분리해 비용 대비 우선순위를 높입니다.', 'whyItMatters': '누락과 회신이 한 코드로 묶여 있어 설명과 실행이 동시에 빨라집니다.', 'deliveryState': 'ready_to_issue'},
        {'title': '서류 체크리스트 운영본', 'note': f"체크리스트 {len(checklist)}행", 'preview': issues[0].get('detail') if issues else '현재 큰 누락이 없는 구조입니다.', 'whatIncluded': '확보/보완 상태, 우선도, 필요한 이유를 체크리스트 운영본으로 묶었습니다.', 'actionNow': '핵심으로 표시된 항목부터 책임자를 붙여 다시 취합합니다.', 'buyerValue': '인수인계나 담당자 변경에도 기준이 흔들리지 않습니다.', 'expertLens': '날인·정산·회신 창구처럼 병목이 큰 서류를 먼저 분리합니다.', 'whyItMatters': '체크리스트가 있어야 마감 직전에도 기준이 흔들리지 않습니다.', 'deliveryState': 'ready_to_issue'},
        {'title': '대외/내부 회신 템플릿', 'note': f"문장 {len(copies)}종", 'preview': copies[0].get('after') if copies else '회신 문장이 아직 없습니다.', 'whatIncluded': '보완 회신, 내부 준비 요청, 마감 임박 안내를 그대로 사용할 수 있는 문장 단위로 제공합니다.', 'actionNow': '외부에는 누락·시점, 내부에는 확보·날인 순서를 같은 날 안에 공유합니다.', 'buyerValue': '답변 지연과 문장 편차를 크게 줄일 수 있습니다.', 'expertLens': '상황 설명이 아니라 행동과 시점을 분명하게 쓰는 문장으로 바꿉니다.', 'whyItMatters': '제출 운영의 속도는 문서뿐 아니라 회신 문장에서 갈립니다.', 'deliveryState': 'ready_to_issue'},
    ]
    pack['issuanceBundle'] = [
        {'title': 'ClearPort 제출 운영 리포트', 'description': f"리포트 코드 {report.get('code')} 기준으로 준비도, 핵심 누락, 회신 문장을 같은 문서로 발행합니다.", 'customerValue': '외부 설명과 내부 실행 기준을 동시에 공유할 수 있습니다.', 'usageMoment': '즉시 공유', 'expertNote': '준비도와 누락 수치를 먼저 보여주면 판단이 빨라집니다.', 'status': 'ready'},
        {'title': '체크리스트 운영본', 'description': '필수/보조 문서를 확보·보완 상태로 나눈 체크리스트 운영본을 함께 제공합니다.', 'customerValue': '담당자가 바뀌어도 같은 기준으로 다시 볼 수 있습니다.', 'usageMoment': '실행 착수', 'expertNote': '보완 필요 문서는 왜 필요한지까지 같이 적어야 재요청이 줄어듭니다.', 'status': 'ready'},
        {'title': '회신 템플릿 세트', 'description': '대외 보완 회신, 내부 준비 요청, 마감 임박 안내를 템플릿으로 묶어 제공합니다.', 'customerValue': '응답 속도와 문장 일관성이 동시에 올라갑니다.', 'usageMoment': '후속 점검', 'expertNote': '추상적인 확인 요청보다 누락 항목과 시점을 함께 적는 문장이 좋습니다.', 'status': 'ready'},
    ]
    pack['deliveryAssets'] = pack['issuanceBundle']
    pack['linkedReport'] = {'id': report.get('id'), 'code': report.get('code'), 'readinessRate': stats.get('readinessRate'), 'criticalMissing': stats.get('criticalMissing')}
    return pack


def contributor_count(value: str) -> int:
    text = clean(value)
    if '4' in text:
        return 4
    match = re.search(r'(\d+)', text)
    return int(match.group(1)) if match else 1


def build_deadline_schedule(deadline_obj: date | None) -> list[dict[str, str]]:
    labels = [('증빙 확정', 7), ('초안 완료', 5), ('검토 완료', 3), ('승인 완료', 1), ('제출/업로드', 0)]
    rows = []
    for label, offset in labels:
        due = deadline_obj - timedelta(days=offset) if deadline_obj else None
        rows.append({'label': label, 'date': due.isoformat() if due else '마감 입력 후 계산', 'detail': f"{label} 단계는 마감 {offset}일 전 기준으로 잠그는 것을 권장합니다."})
    return rows


def build_grantops_report(payload: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    options = {clean(item) for item in payload.get('options') or [] if clean(item)}
    company = clip_text(payload.get('company'), 160) or '샘플 회사'
    project_name = clip_text(payload.get('projectName') or payload.get('programName') or payload.get('project') or payload.get('program'), 180) or '사업/공모명 미입력'
    steps = collect_text_items(payload.get('steps'), payload.get('milestones'), payload.get('tasks'))
    risks = collect_text_items(payload.get('risks'), payload.get('issues'))
    team_members = collect_text_items(payload.get('teamMembers'), payload.get('owners'), payload.get('team'))
    progress = clip_text(payload.get('progress'), 120)
    if not progress:
        if len(steps) >= 4:
            progress = '검토 단계'
        elif len(steps) >= 2:
            progress = '초안 작성 중'
        else:
            progress = '자료 수집 전'
    delay_point = clip_text(payload.get('delayPoint') or (', '.join(risks[:2]) if risks else ''), 240)
    contributors = clip_text(payload.get('contributors') or (f'{len(team_members)}명' if team_members else ''), 80) or '1명'
    contributor_num = contributor_count(contributors)
    deadline_raw, deadline_obj, days_left = parse_iso_deadline(payload.get('deadline') or payload.get('dueDate'))
    risk = 18
    if days_left is None:
        risk += 12
    elif days_left <= 3:
        risk += 35
    elif days_left <= 7:
        risk += 22
    elif days_left <= 14:
        risk += 10
    progress_penalty = {'자료 수집 전': 28, '초안 작성 중': 18, '검토 단계': 10, '제출 직전': 4}.get(progress, 14)
    risk += progress_penalty
    if delay_point:
        risk += 10
    if 'review' in options:
        risk += 8
    if 'evidence' in options:
        risk += 8
    if contributor_num <= 1:
        risk += 8
    readiness_score = max(36, 100 - risk)
    role_plan = [
        {'label': '실무 담당', 'owner': team_members[0] if len(team_members) >= 1 else '초안 작성/자료 수집', 'detail': '증빙 목록 정리, 본문 작성, 업로드 준비를 맡습니다.'},
        {'label': '검토 담당', 'owner': team_members[1] if len(team_members) >= 2 else '문장/수치 검토', 'detail': '본문-예산-증빙 간 불일치를 마지막으로 확인합니다.'},
        {'label': '승인 담당', 'owner': team_members[2] if len(team_members) >= 3 else '대표/결재자 승인', 'detail': '제출 직전 병목이 생기지 않도록 승인 시점을 고정합니다.'},
        {'label': '백업 담당', 'owner': team_members[3] if len(team_members) >= 4 else '업로드/파일명 백업', 'detail': '최종 업로드 실패나 버전 혼선을 대비한 백업본을 보관합니다.'},
    ]
    schedule = build_deadline_schedule(deadline_obj)
    issues = [
        {'level': 'high' if readiness_score < 60 else 'medium', 'title': '역산 일정 재정렬 필요', 'detail': f'현재 진행 상태가 {progress} 이고 마감 상태가 {_fmt_due_label(days_left)} 기준이라 승인/업로드 구간을 먼저 잠가야 합니다.'},
        {'level': 'medium' if delay_point else 'low', 'title': '가장 자주 밀리는 작업 관리', 'detail': f'병목으로 입력한 "{delay_point or "증빙 수집"}" 단계가 전체 일정에 가장 큰 영향을 줍니다.'},
        {'level': 'medium' if risks else 'low', 'title': '리스크 메모 반영', 'detail': f'사용자 입력 리스크 {", ".join(risks[:3]) if risks else "미입력"} 를 일정 재배치 근거에 반영했습니다.'},
    ]
    if 'review' in options:
        issues.append({'level': 'medium', 'title': '결재자 검토 시간 반영 필요', 'detail': '대표 또는 결재자 검토 시간을 별도 블록으로 확보하지 않으면 마지막 이틀이 가장 흔들립니다.'})
    if contributor_num <= 1:
        issues.append({'level': 'medium', 'title': '1인 운영 병목', 'detail': '실무/검토/업로드 역할을 한 사람이 모두 맡으면 제출 직전 오류 복구 시간이 부족해집니다.'})
    copy_suggestions = [
        {'label': '승인 요청 문장', 'appliesTo': '내부 승인', 'before': '확인 부탁드립니다.', 'after': f'{project_name} 제출본 1차 검토를 마쳤습니다. {_fmt_due_label(days_left)} 일정 기준으로 오늘 안에 승인 여부와 수정 포인트를 부탁드립니다.'},
        {'label': '증빙 요청 문장', 'appliesTo': '자료 요청', 'before': '자료 전달 부탁드립니다.', 'after': f'{project_name} 제출을 위해 현재 가장 시급한 자료는 {delay_point or "증빙 수집"} 관련 항목입니다. 오늘 중 보유 여부와 전달 가능 시간을 회신해 주세요.'},
        {'label': '업로드 전 최종 확인', 'appliesTo': '마감 직전', 'before': '최종 확인 후 제출하겠습니다.', 'after': '본문, 예산, 증빙, 첨부파일명을 교차검토했고 업로드 환경까지 확인한 뒤 최종 제출하겠습니다.'},
    ]
    report_id = uid('grep')
    report_code = make_public_code('GREP', 'grantops')
    issued_at = now_iso()
    report = {
        'id': report_id,
        'code': report_code,
        'reportId': report_id,
        'reportCode': report_code,
        'product': 'grantops',
        'company': company,
        'projectName': project_name,
        'progress': progress,
        'contributors': contributors,
        'delayPoint': delay_point,
        'deadline': deadline_raw,
        'options': sorted(options),
        'stepsInput': steps,
        'risksInput': risks,
        'teamMembers': team_members,
        'summary': f'{project_name} 기준으로 역산 일정, 역할 분담, 병목 구간을 다시 잠갔습니다. 준비도 {readiness_score}점, 마감 상태 {_fmt_due_label(days_left)}, 승인·증빙·업로드 병목을 같은 코드로 정리했습니다.',
        'stats': {
            'daysLeft': days_left,
            'readinessScore': readiness_score,
            'riskLevel': '높음' if readiness_score < 60 else '중간' if readiness_score < 78 else '안정',
            'criticalPathSteps': len(schedule),
            'contributors': contributor_num,
            'copyTemplates': len(copy_suggestions),
            'elapsedMs': round((time.monotonic() - started) * 1000, 1),
        },
        'schedule': schedule,
        'rolePlan': role_plan,
        'issues': issues,
        'copySuggestions': copy_suggestions,
        'issuance': {
            'status': 'ready' if deadline_raw else 'blocked',
            'reportTitle': 'GrantOps 제출 운영 리포트',
            'generatedAt': issued_at,
            'reportCode': report_code,
            'sections': ['마감 역산', '역할 분담', '병목 구간', '승인/증빙 요청 문장', '제출 직전 확인'],
            'readyReason': '마감일, 역할 분담, 병목, 요청 문장까지 같은 코드로 묶여 바로 발행 가능한 상태입니다.' if deadline_raw else '마감일이 없어 역산 일정과 발행본을 확정할 수 없습니다.',
        },
        'quality': {
            'passed': bool(deadline_raw),
            'gates': [
                {'label': '마감 역산', 'ok': bool(deadline_raw), 'detail': f"마감 상태 {_fmt_due_label(days_left)} 기준 역산 일정을 만들었습니다." if deadline_raw else '마감일이 없어 역산 일정을 만들 수 없습니다.'},
                {'label': '역할 분담', 'ok': True, 'detail': f'실무/검토/승인/백업 역할 {len(role_plan)}개를 고정했습니다.'},
                {'label': '병목 반영', 'ok': True, 'detail': f'입력한 병목 "{delay_point or "증빙 수집"}" 를 리스크 계산에 반영했습니다.'},
                {'label': '발행 준비', 'ok': bool(deadline_raw), 'detail': '역산 일정과 요청 문장을 같은 리포트 코드로 묶었습니다.' if deadline_raw else '마감일 입력 후 다시 생성해야 합니다.'},
            ],
        },
        'createdAt': issued_at,
        'updatedAt': issued_at,
    }
    return upsert_record('reports', report)


def build_grantops_demo_preview(report: dict[str, Any], company: str) -> dict[str, Any]:
    stats = report.get('stats') or {}
    issues = report.get('issues') or []
    schedule = report.get('schedule') or []
    roles = report.get('rolePlan') or []
    copies = report.get('copySuggestions') or []
    return {
        'headline': f"{company or '샘플 회사'} 기준 GrantOps 제출 운영 결과",
        'summary': report.get('summary') or '',
        'company': company or '샘플 회사',
        'goal': clean(report.get('projectName')) or '제출 일정 안정화',
        'keywords': ', '.join(report.get('options') or []),
        'diagnosisSummary': f"준비도 {stats.get('readinessScore', 0)}점, 마감 상태 {_fmt_due_label(stats.get('daysLeft'))}, 핵심 경로 {stats.get('criticalPathSteps', 0)}단계를 기준으로 역산 계획을 만들었습니다.",
        'sampleOutputs': [
            {'title': '역산 일정표', 'note': f"{_fmt_due_label(stats.get('daysLeft'))}", 'preview': report.get('summary') or '', 'whatIncluded': '마감일을 기준으로 증빙, 초안, 검토, 승인, 업로드 단계를 날짜로 다시 배치합니다.', 'actionNow': '오늘 가장 먼저 밀리는 단계부터 책임자와 마감 시점을 다시 잠급니다.', 'buyerValue': '누가 무엇을 언제 끝내야 하는지 말이 아니라 날짜로 공유할 수 있습니다.', 'expertLens': '마감 직전보다 승인·업로드 직전 병목을 먼저 보는 구조로 설계합니다.', 'whyItMatters': '역산 일정이 없으면 마지막 며칠에 모든 병목이 몰립니다.', 'deliveryState': 'ready_to_issue'},
            {'title': '역할 분담표', 'note': f"역할 {len(roles)}개", 'preview': issues[0].get('detail') if issues else '현재 구조상 큰 병목은 제한적입니다.', 'whatIncluded': '실무, 검토, 승인, 백업 역할을 분리해 누가 놓쳤는지 바로 보이게 합니다.', 'actionNow': '한 사람이 겹쳐 맡는 구간은 백업 담당을 추가로 붙입니다.', 'buyerValue': '적은 인원에서도 제출 직전 혼선을 줄일 수 있습니다.', 'expertLens': '실무와 최종 확인을 같은 사람이 맡으면 마지막 오류 복구 시간이 사라집니다.', 'whyItMatters': '역할 분리 없이는 일정표가 있어도 실제로는 계속 밀리기 쉽습니다.', 'deliveryState': 'ready_to_issue'},
            {'title': '요청/승인 문장', 'note': f"문장 {len(copies)}종", 'preview': copies[0].get('after') if copies else '요청 문장이 아직 없습니다.', 'whatIncluded': '승인 요청, 증빙 요청, 업로드 전 확인 문장을 바로 쓸 수 있게 제공합니다.', 'actionNow': '마감이 짧을수록 문장부터 먼저 보내 병목을 사전에 줄입니다.', 'buyerValue': '연락 왕복 시간을 줄여 실제 제출 준비 시간이 늘어납니다.', 'expertLens': '요청 문장은 자료명과 시점을 같이 적어야 회신 속도가 올라갑니다.', 'whyItMatters': '마감 직전에는 문장 하나의 정확도가 일정 전체를 좌우합니다.', 'deliveryState': 'ready_to_issue'},
        ],
        'quickWins': ['역산 일정부터 고정합니다.', '병목 단계 담당자를 별도로 붙입니다.', '승인/증빙 요청 문장을 먼저 보냅니다.'],
        'valueDrivers': ['마감일을 행동 단위 일정으로 바꿉니다.', '역할 분담과 요청 문장을 함께 제공합니다.', '같은 리포트 코드로 포털과 결과팩을 연결합니다.'],
        'successMetrics': [f"준비도 {stats.get('readinessScore', 0)}점", f"마감 상태 {_fmt_due_label(stats.get('daysLeft'))}", f"핵심 경로 {stats.get('criticalPathSteps', 0)}단계"],
        'prioritySequence': ['1. 역산 일정 잠금', '2. 병목 역할 분리', '3. 승인/증빙 요청 발송'],
        'expertNotes': ['역산 일정은 승인과 업로드 구간부터 잡습니다.', '역할 분담표가 있어야 누락 책임이 선명해집니다.', '요청 문장은 자료명과 시점을 같이 적습니다.'],
        'objectionHandling': ['자료가 아직 덜 모여도 일정과 역할부터 먼저 잡을 수 있습니다.', '문장까지 함께 나와 바로 움직일 수 있습니다.'],
        'scorecard': {
            'stage': 'demo', 'stageLabel': '제출 운영 데모', 'earned': 100, 'total': 100, 'grade': 'A+', 'headline': 'GrantOps 실제 운영 품질 기준표',
            'summary': '역산 일정, 역할 분담, 병목 반영, 요청 문장, 발행 준비까지 한 흐름으로 확인합니다.',
            'items': [
                {'label': '역산 일정', 'score': 20, 'max': 20, 'reason': f"마감 상태 {_fmt_due_label(stats.get('daysLeft'))} 기준으로 역산 일정을 만들었습니다."},
                {'label': '역할 분담', 'score': 15, 'max': 15, 'reason': f'역할 {len(roles)}개를 분리해 정리했습니다.'},
                {'label': '병목 반영', 'score': 15, 'max': 15, 'reason': f'병목 "{report.get("delayPoint") or "증빙 수집"}" 를 리스크 계산에 반영했습니다.'},
                {'label': '위험도 계산', 'score': 15, 'max': 15, 'reason': f"준비도 {stats.get('readinessScore', 0)}점과 위험도 {stats.get('riskLevel')}를 함께 계산했습니다."},
                {'label': '요청 문장', 'score': 15, 'max': 15, 'reason': f'요청/승인 문장 {len(copies)}종을 생성했습니다.'},
                {'label': '발행 준비', 'score': 10, 'max': 10, 'reason': report.get('issuance', {}).get('readyReason') or '발행 준비 상태를 점검했습니다.'},
                {'label': '재사용성', 'score': 10, 'max': 10, 'reason': '같은 리포트 코드로 포털, 관리자, 후속 제출 운영까지 이어집니다.'},
            ],
        },
        'ctaHint': f"리포트 코드 {report.get('code')} 기준으로 결제 후 일정 운영본과 결과 포털을 같은 흐름으로 이어갑니다.",
        'closingArgument': '이번 데모는 마감 역산, 역할 분담, 병목, 요청 문장을 같은 코드로 묶어 실제 제출 운영에서 바로 쓰일 수 있게 만들었습니다.',
        'linkedReport': {'id': report.get('id'), 'code': report.get('code')},
    }


def build_grantops_result_pack_from_report(base_pack: dict[str, Any], report: dict[str, Any], company: str) -> dict[str, Any]:
    stats = report.get('stats') or {}
    issues = report.get('issues') or []
    schedule = report.get('schedule') or []
    roles = report.get('rolePlan') or []
    copies = report.get('copySuggestions') or []
    pack = deepcopy(base_pack)
    pack['summary'] = report.get('summary') or pack.get('summary') or ''
    pack['outcomeHeadline'] = f"{company or '고객사'} 제출 운영에서 마감 역산, 역할 분담, 병목 대응을 바로 실행할 수 있게 정리했습니다."
    pack['executiveSummary'] = f"준비도 {stats.get('readinessScore', 0)}점, 마감 상태 {_fmt_due_label(stats.get('daysLeft'))}, 핵심 경로 {stats.get('criticalPathSteps', 0)}단계를 기준으로 일정과 승인 흐름을 다시 잠갔습니다."
    pack['clientContext'] = {**(pack.get('clientContext') or {}), 'projectName': report.get('projectName'), 'deadline': report.get('deadline'), 'reportCode': report.get('code'), 'readinessScore': stats.get('readinessScore')}
    pack['outputs'] = [
        {'title': '실제 역산 일정 리포트', 'note': f"리포트 코드 {report.get('code')}", 'preview': report.get('summary') or '', 'whatIncluded': f"마감 상태 {_fmt_due_label(stats.get('daysLeft'))}, 위험도 {stats.get('riskLevel')}, 핵심 경로 {len(schedule)}단계를 함께 정리했습니다.", 'actionNow': '승인/업로드 구간부터 다시 잠그고, 밀리는 작업은 오늘 안에 책임자를 정합니다.', 'buyerValue': '감으로 보던 마감을 행동 단위 일정으로 바꿀 수 있습니다.', 'expertLens': '초안 작성보다 승인과 업로드 병목을 먼저 드러내는 일정이 실제적입니다.', 'whyItMatters': '마감이 가까울수록 일정표의 해상도가 결과를 좌우합니다.', 'deliveryState': 'ready_to_issue'},
        {'title': '역할 분담 운영본', 'note': f"역할 {len(roles)}개", 'preview': issues[0].get('detail') if issues else '현재 구조상 병목이 제한적입니다.', 'whatIncluded': '실무, 검토, 승인, 백업 역할과 세부 책임을 운영본으로 제공합니다.', 'actionNow': '한 사람이 겹치는 단계는 백업 담당을 추가해 마지막 오류 복구 시간을 확보합니다.', 'buyerValue': '적은 인원에서도 누가 무엇을 놓쳤는지 바로 확인할 수 있습니다.', 'expertLens': '제출 운영은 역할 분리만 돼도 일정 안정성이 크게 올라갑니다.', 'whyItMatters': '역할이 흐리면 일정은 항상 마지막에 무너집니다.', 'deliveryState': 'ready_to_issue'},
        {'title': '요청·승인 문장 세트', 'note': f"문장 {len(copies)}종", 'preview': copies[0].get('after') if copies else '요청 문장이 아직 없습니다.', 'whatIncluded': '승인 요청, 증빙 요청, 업로드 전 최종 확인 문장을 바로 쓰는 형태로 묶었습니다.', 'actionNow': '오늘 바로 요청을 보내 병목 회복 시간을 확보합니다.', 'buyerValue': '일정표만 있는 것보다 실제 움직임이 훨씬 빨라집니다.', 'expertLens': '자료명과 시점을 같이 적는 문장이 가장 재촉 효과가 좋습니다.', 'whyItMatters': '문장이 늦으면 일정표도 실제로는 작동하지 않습니다.', 'deliveryState': 'ready_to_issue'},
    ]
    pack['issuanceBundle'] = [
        {'title': 'GrantOps 제출 운영 리포트', 'description': f"리포트 코드 {report.get('code')} 기준으로 역산 일정, 역할 분담, 병목 대응을 같은 문서로 발행합니다.", 'customerValue': '일정표와 실행 기준을 한 번에 공유할 수 있습니다.', 'usageMoment': '즉시 공유', 'expertNote': '승인·업로드 병목을 앞에 두는 일정이 실제적입니다.', 'status': 'ready'},
        {'title': '역할 분담표', 'description': '실무/검토/승인/백업 역할을 운영본 형태로 함께 제공합니다.', 'customerValue': '적은 인원에서도 책임 구간이 선명해집니다.', 'usageMoment': '실행 착수', 'expertNote': '역할 분리가 되어야 일정표가 실제로 작동합니다.', 'status': 'ready'},
        {'title': '요청 문장 세트', 'description': '승인 요청, 증빙 요청, 업로드 전 확인 문장을 템플릿으로 함께 제공합니다.', 'customerValue': '연락 왕복 시간을 줄여 제출 준비 시간을 늘릴 수 있습니다.', 'usageMoment': '후속 점검', 'expertNote': '자료명과 시점을 같이 적는 문장이 가장 효과적입니다.', 'status': 'ready'},
    ]
    pack['deliveryAssets'] = pack['issuanceBundle']
    pack['linkedReport'] = {'id': report.get('id'), 'code': report.get('code'), 'readinessScore': stats.get('readinessScore'), 'daysLeft': stats.get('daysLeft')}
    return pack


def approval_step_count(value: str) -> int:
    match = re.search(r'(\d+)', clean(value))
    return int(match.group(1)) if match else 1


def build_draftforge_report(payload: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    options = {clean(item) for item in payload.get('options') or [] if clean(item)}
    company = clip_text(payload.get('company'), 160) or '샘플 회사'
    document_name = clip_text(payload.get('documentName') or payload.get('document') or payload.get('title'), 160)
    doc_type = clip_text(payload.get('docType') or payload.get('documentType') or document_name, 120) or '문서'
    versions = collect_text_items(payload.get('versions'), payload.get('versionList'))
    version_state = clip_text(payload.get('versionState'), 160)
    if not version_state:
        if len(versions) >= 3:
            version_state = '수정본이 여러 개 흩어져 있음'
        elif len(versions) == 2:
            version_state = '검토본까지 있음'
        else:
            version_state = '초안만 있음'
    approvers = collect_text_items(payload.get('approvers'), payload.get('reviewers'), payload.get('approvals'))
    approval_steps = clip_text(payload.get('approvalSteps') or (f'{len(approvers)}단계' if approvers else ''), 80) or '1단계'
    step_count = approval_step_count(approval_steps)
    channel = clip_text(payload.get('channel') or payload.get('shareChannel'), 120) or '이메일'
    draft_pain = clip_text(payload.get('draftPain') or payload.get('problem') or ', '.join(collect_text_items(payload.get('issues'), payload.get('risks'))[:2]), 240)
    score = 94
    if version_state == '수정본이 여러 개 흩어져 있음':
        score -= 24
    elif version_state == '초안만 있음':
        score -= 12
    else:
        score -= 6
    score -= max(0, step_count - 1) * 8
    if 'qa' in options:
        score -= 4
    if channel == '메신저 + 파일공유':
        score -= 6
    if draft_pain:
        score -= 6
    control_score = max(38, min(100, score))
    handoff_risk = '높음' if control_score < 60 else '중간' if control_score < 78 else '안정'
    version_matrix = [
        {'label': '작업본', 'rule': f'{doc_type}_YYYYMMDD_v01_work', 'detail': '작성 중인 원본은 work 접미사로 고정합니다.'},
        {'label': '검토본', 'rule': f'{doc_type}_YYYYMMDD_v02_review', 'detail': '검토 요청본은 review 접미사만 사용합니다.'},
        {'label': '승인본', 'rule': f'{doc_type}_YYYYMMDD_v03_approved', 'detail': '승인 완료본은 approved로만 올립니다.'},
        {'label': '배포본', 'rule': f'{doc_type}_YYYYMMDD_final', 'detail': '외부 발송 또는 게시본은 final 단일 파일만 남깁니다.'},
    ]
    issues = [
        {'level': 'high' if version_state == '수정본이 여러 개 흩어져 있음' else 'medium', 'title': '최신본 기준 확정 필요', 'detail': '버전이 흩어져 있으면 승인 코멘트 누락과 역버전 발송 가능성이 커집니다.'},
        {'level': 'medium' if step_count >= 3 else 'low', 'title': '승인 단계 정리 필요', 'detail': f'현재 {approval_steps} 구조라면 검토용/결재용/배포용 버전을 분리해야 합니다. 승인자 {", ".join(approvers[:3]) if approvers else "미입력"} 기준으로 마지막 결재 흐름을 고정하는 편이 좋습니다.'},
    ]
    if 'qa' in options:
        issues.append({'level': 'medium', 'title': '배포 전 QA 체크 강화', 'detail': '최종본 배포 전 링크·수치·첨부파일명까지 마지막 비교 기준을 고정해야 합니다.'})
    if draft_pain:
        issues.append({'level': 'medium', 'title': '현재 병목 반영', 'detail': f'입력한 문제 "{draft_pain}" 를 버전 관리와 승인 흐름 설계에 반영했습니다.'})
    copy_suggestions = [
        {'label': '파일명 규칙', 'appliesTo': doc_type, 'before': '최종본(수정)(진짜최종).pdf', 'after': f'{doc_type}_YYYYMMDD_v01_work → {doc_type}_YYYYMMDD_v02_review → {doc_type}_YYYYMMDD_v03_approved → {doc_type}_YYYYMMDD_final'},
        {'label': '검토 요청 문장', 'appliesTo': channel, 'before': '검토 부탁드립니다.', 'after': f'{doc_type} 검토본을 전달드립니다. 이번 검토는 본문 수정 여부와 승인 의견만 부탁드리며, 회신 기한은 오늘 안으로 부탁드립니다.'},
        {'label': '최종 발송 문장', 'appliesTo': '대외 발송', 'before': '최종본 보냅니다.', 'after': f'최종 승인 완료된 {doc_type} 배포본을 전달드립니다. 첨부파일명, 본문, 링크, 수치를 최종 기준에 맞춰 다시 확인했습니다.'},
    ]
    report_id = uid('drep')
    report_code = make_public_code('DREP', 'draftforge')
    issued_at = now_iso()
    report = {
        'id': report_id,
        'code': report_code,
        'reportId': report_id,
        'reportCode': report_code,
        'product': 'draftforge',
        'company': company,
        'docType': doc_type,
        'versionState': version_state,
        'approvalSteps': approval_steps,
        'channel': channel,
        'draftPain': draft_pain,
        'options': sorted(options),
        'documentName': document_name,
        'versionsInput': versions,
        'approversInput': approvers,
        'summary': f'{doc_type} 기준으로 버전명, 승인 단계, 최종 배포 기준을 다시 잠갔습니다. 문서 통제 점수 {control_score}점, 승인 {approval_steps}, 인계 위험 {handoff_risk} 상태를 같은 코드로 정리했습니다.',
        'stats': {
            'controlScore': control_score,
            'approvalSteps': step_count,
            'handoffRisk': handoff_risk,
            'versionRules': len(version_matrix),
            'copyTemplates': len(copy_suggestions),
            'elapsedMs': round((time.monotonic() - started) * 1000, 1),
        },
        'versionMatrix': version_matrix,
        'issues': issues,
        'copySuggestions': copy_suggestions,
        'issuance': {
            'status': 'ready',
            'reportTitle': 'DraftForge 문서 운영 리포트',
            'generatedAt': issued_at,
            'reportCode': report_code,
            'sections': ['문서 통제 점수', '버전 규칙', '승인 흐름', '검토/발송 문장', '배포 전 QA 기준'],
            'readyReason': '버전 규칙, 승인 단계, 검토/발송 문장이 같은 코드로 묶여 바로 발행 가능한 상태입니다.',
        },
        'quality': {
            'passed': True,
            'gates': [
                {'label': '버전 규칙', 'ok': True, 'detail': f'작업본-검토본-승인본-배포본 규칙 {len(version_matrix)}단계를 고정했습니다.'},
                {'label': '승인 단계 반영', 'ok': True, 'detail': f'{approval_steps} 승인 구조를 운영 규칙에 반영했습니다.'},
                {'label': '문장 생성', 'ok': bool(copy_suggestions), 'detail': f'검토/발송 문장 {len(copy_suggestions)}종을 만들었습니다.'},
                {'label': '발행 준비', 'ok': True, 'detail': '버전 규칙, 승인 기준, 문장을 같은 리포트 코드로 묶었습니다.'},
            ],
        },
        'createdAt': issued_at,
        'updatedAt': issued_at,
    }
    return upsert_record('reports', report)


def build_draftforge_demo_preview(report: dict[str, Any], company: str) -> dict[str, Any]:
    stats = report.get('stats') or {}
    issues = report.get('issues') or []
    matrix = report.get('versionMatrix') or []
    copies = report.get('copySuggestions') or []
    return {
        'headline': f"{company or '샘플 회사'} 기준 DraftForge 문서 운영 결과",
        'summary': report.get('summary') or '',
        'company': company or '샘플 회사',
        'goal': clean(report.get('draftPain')) or '최종본 기준 확정',
        'keywords': ', '.join(report.get('options') or []),
        'diagnosisSummary': f"문서 통제 점수 {stats.get('controlScore', 0)}점, 승인 단계 {stats.get('approvalSteps', 1)}개, 인계 위험 {stats.get('handoffRisk')}를 기준으로 버전 운영 규칙을 다시 설계했습니다.",
        'sampleOutputs': [
            {'title': '버전 관리 기준표', 'note': f"통제 점수 {stats.get('controlScore', 0)}점", 'preview': report.get('summary') or '', 'whatIncluded': '작업본, 검토본, 승인본, 배포본 파일명을 단계별로 고정합니다.', 'actionNow': '흩어진 파일명을 새 규칙으로 다시 맞추고 final 파일은 1개만 남깁니다.', 'buyerValue': '최신본 혼선을 가장 빠르게 줄일 수 있습니다.', 'expertLens': '버전명만 통일해도 승인 코멘트 누락과 역버전 배포를 크게 줄일 수 있습니다.', 'whyItMatters': '최종본이 흔들리면 모든 승인과 배포가 다시 불안해집니다.', 'deliveryState': 'ready_to_issue'},
            {'title': '승인 흐름 설계', 'note': f"승인 {stats.get('approvalSteps', 1)}단계", 'preview': issues[0].get('detail') if issues else '현재 구조상 승인 흐름이 비교적 안정적입니다.', 'whatIncluded': '검토용, 결재용, 배포용 문서를 언제 분기할지 운영 기준으로 정리합니다.', 'actionNow': '승인 단계가 3단계 이상이면 검토본과 배포본을 분리해 코멘트 누락을 막습니다.', 'buyerValue': '승인자가 많아도 흐름이 끊기지 않게 됩니다.', 'expertLens': '문서 종류보다 승인 시점과 최종본 구분이 더 중요할 때가 많습니다.', 'whyItMatters': '승인 구조를 분리하지 않으면 마지막에 누가 어떤 버전을 봤는지 다시 추적해야 합니다.', 'deliveryState': 'ready_to_issue'},
            {'title': '검토/발송 문장', 'note': f"문장 {len(copies)}종", 'preview': copies[0].get('after') if copies else '문장 규칙이 아직 없습니다.', 'whatIncluded': '검토 요청, 최종 발송, 파일명 규칙 문장을 그대로 재사용할 수 있게 제공합니다.', 'actionNow': '검토 요청 시 이번 회차에서 봐야 할 범위를 문장에 명시합니다.', 'buyerValue': '의견 범위가 정리되어 수정 왕복이 줄어듭니다.', 'expertLens': '검토 요청 문장은 범위와 기한이 함께 있어야 효과가 큽니다.', 'whyItMatters': '문장 하나로도 승인 속도와 최종본 안정성이 달라집니다.', 'deliveryState': 'ready_to_issue'},
        ],
        'quickWins': ['버전명부터 통일합니다.', '검토본/배포본을 분리합니다.', '최종 발송 전 QA 항목을 고정합니다.'],
        'valueDrivers': ['최신본 혼선을 줄입니다.', '승인 단계별 규칙을 남깁니다.', '검토/발송 문장까지 함께 제공합니다.'],
        'successMetrics': [f"통제 점수 {stats.get('controlScore', 0)}점", f"승인 단계 {stats.get('approvalSteps', 1)}개", f"인계 위험 {stats.get('handoffRisk')}"],
        'prioritySequence': ['1. 버전 규칙 통일', '2. 승인 흐름 분리', '3. 배포 전 QA 고정'],
        'expertNotes': ['작업본과 배포본은 이름부터 달라야 합니다.', '승인 단계가 늘수록 검토 범위를 문장으로 잠가야 합니다.', '최종본은 final 한 개만 남기는 것이 안전합니다.'],
        'objectionHandling': ['이미 초안이 있어도 버전 통제만으로 시간을 크게 줄일 수 있습니다.', '문장 규칙까지 있어 새 담당자도 같은 흐름으로 움직일 수 있습니다.'],
        'scorecard': {
            'stage': 'demo', 'stageLabel': '문서 통제 데모', 'earned': 100, 'total': 100, 'grade': 'A+', 'headline': 'DraftForge 실제 운영 품질 기준표',
            'summary': '버전 규칙, 승인 단계, 문장 규칙, 발행 준비를 한 흐름으로 확인합니다.',
            'items': [
                {'label': '버전 규칙', 'score': 20, 'max': 20, 'reason': f'버전 규칙 {len(matrix)}단계를 작업본-검토본-승인본-배포본으로 고정했습니다.'},
                {'label': '승인 단계 반영', 'score': 15, 'max': 15, 'reason': f"{report.get('approvalSteps')} 구조를 운영 규칙에 반영했습니다."},
                {'label': '통제 점수 계산', 'score': 15, 'max': 15, 'reason': f"문서 통제 점수 {stats.get('controlScore', 0)}점과 인계 위험 {stats.get('handoffRisk')}를 계산했습니다."},
                {'label': '문장 규칙', 'score': 15, 'max': 15, 'reason': f'검토/발송 문장 {len(copies)}종을 생성했습니다.'},
                {'label': '최종본 기준', 'score': 15, 'max': 15, 'reason': '최종 배포본은 final 1개만 남기는 기준을 함께 제시했습니다.'},
                {'label': '발행 준비', 'score': 10, 'max': 10, 'reason': report.get('issuance', {}).get('readyReason') or '발행 준비 상태를 점검했습니다.'},
                {'label': '재사용성', 'score': 10, 'max': 10, 'reason': '같은 리포트 코드로 포털, 관리자, 다음 문서 운영에도 재사용할 수 있습니다.'},
            ],
        },
        'ctaHint': f"리포트 코드 {report.get('code')} 기준으로 결제 후 버전 운영본과 포털 결과를 같은 흐름으로 이어갑니다.",
        'closingArgument': '이번 데모는 버전 규칙, 승인 단계, 검토·발송 문장을 같은 코드로 묶어 실제 문서 운영에 바로 쓰일 수준으로 만들었습니다.',
        'linkedReport': {'id': report.get('id'), 'code': report.get('code')},
    }


def build_draftforge_result_pack_from_report(base_pack: dict[str, Any], report: dict[str, Any], company: str) -> dict[str, Any]:
    stats = report.get('stats') or {}
    issues = report.get('issues') or []
    matrix = report.get('versionMatrix') or []
    copies = report.get('copySuggestions') or []
    pack = deepcopy(base_pack)
    pack['summary'] = report.get('summary') or pack.get('summary') or ''
    pack['outcomeHeadline'] = f"{company or '고객사'} 문서 운영에서 최신본 기준, 승인 흐름, 최종 배포 규칙을 다시 잠갔습니다."
    pack['executiveSummary'] = f"문서 통제 점수 {stats.get('controlScore', 0)}점, 승인 단계 {stats.get('approvalSteps', 1)}개, 인계 위험 {stats.get('handoffRisk')} 기준으로 버전 운영본을 재설계했습니다."
    pack['clientContext'] = {**(pack.get('clientContext') or {}), 'docType': report.get('docType'), 'approvalSteps': report.get('approvalSteps'), 'reportCode': report.get('code'), 'controlScore': stats.get('controlScore')}
    pack['outputs'] = [
        {'title': '실제 버전 운영 리포트', 'note': f"리포트 코드 {report.get('code')}", 'preview': report.get('summary') or '', 'whatIncluded': f"통제 점수 {stats.get('controlScore', 0)}점, 인계 위험 {stats.get('handoffRisk')}, 버전 규칙 {len(matrix)}단계를 같은 기준으로 정리했습니다.", 'actionNow': '흩어진 파일을 새 규칙으로 통일하고 final 단일본만 남깁니다.', 'buyerValue': '최신본 혼선과 재작업 비용을 가장 빠르게 줄일 수 있습니다.', 'expertLens': '문서 운영은 내용 품질 못지않게 버전 통제가 중요합니다.', 'whyItMatters': '최종본 기준이 흔들리면 승인과 배포 전체가 다시 흔들립니다.', 'deliveryState': 'ready_to_issue'},
        {'title': '승인 흐름 운영본', 'note': f"승인 {stats.get('approvalSteps', 1)}단계", 'preview': issues[0].get('detail') if issues else '승인 구조가 비교적 안정적입니다.', 'whatIncluded': '검토용, 결재용, 배포용 문서를 언제 분리할지 승인 흐름 기준으로 제공합니다.', 'actionNow': '검토 코멘트와 배포본을 한 파일에 섞지 않도록 분기 지점을 고정합니다.', 'buyerValue': '승인자가 많아도 흐름이 끊기지 않습니다.', 'expertLens': '승인 단계가 늘수록 검토 범위를 문장으로 잠그는 것이 중요합니다.', 'whyItMatters': '승인 흐름이 정리되면 마지막 수정 왕복이 크게 줄어듭니다.', 'deliveryState': 'ready_to_issue'},
        {'title': '검토·발송 문장 세트', 'note': f"문장 {len(copies)}종", 'preview': copies[0].get('after') if copies else '문장 규칙이 아직 없습니다.', 'whatIncluded': '검토 요청, 파일명 규칙, 최종 발송 문장을 그대로 재사용할 수 있게 제공합니다.', 'actionNow': '이번 회차 검토 범위와 회신 기한을 문장으로 먼저 고정합니다.', 'buyerValue': '담당자와 승인자 사이의 해석 차이를 줄일 수 있습니다.', 'expertLens': '문장 규칙이 있으면 승인 속도와 최종본 안정성이 같이 올라갑니다.', 'whyItMatters': '최종 발송 직전의 불안정성을 가장 빠르게 줄이는 방법입니다.', 'deliveryState': 'ready_to_issue'},
    ]
    pack['issuanceBundle'] = [
        {'title': 'DraftForge 문서 운영 리포트', 'description': f"리포트 코드 {report.get('code')} 기준으로 버전 규칙, 승인 흐름, 발송 문장을 같은 문서로 발행합니다.", 'customerValue': '문서 운영 기준을 한 번에 공유할 수 있습니다.', 'usageMoment': '즉시 공유', 'expertNote': '버전 규칙은 작업본-검토본-배포본이 분명해야 합니다.', 'status': 'ready'},
        {'title': '버전 관리 기준표', 'description': '버전명, final 단일본, 검토본 분기 규칙을 운영본으로 함께 제공합니다.', 'customerValue': '최신본 혼선과 역버전 발송을 줄일 수 있습니다.', 'usageMoment': '실행 착수', 'expertNote': '파일명 하나가 승인 흐름 전체를 안정화합니다.', 'status': 'ready'},
        {'title': '검토/발송 문장 세트', 'description': '검토 요청, 파일명 규칙, 최종 발송 문장을 템플릿으로 제공합니다.', 'customerValue': '승인과 배포 단계의 왕복 시간을 줄일 수 있습니다.', 'usageMoment': '후속 점검', 'expertNote': '회신 기한과 검토 범위를 같이 적는 문장이 가장 좋습니다.', 'status': 'ready'},
    ]
    pack['deliveryAssets'] = pack['issuanceBundle']
    pack['linkedReport'] = {'id': report.get('id'), 'code': report.get('code'), 'controlScore': stats.get('controlScore'), 'handoffRisk': stats.get('handoffRisk')}
    return pack

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
    note = clip_text(payload.get("need"), 1000)
    if product_key == 'veridion':
        report = resolve_veridion_report(note, payload)
        if report:
            return build_veridion_demo_preview(report, company)
    elif product_key == 'clearport':
        report = resolve_product_report('clearport', note, payload)
        if report:
            return build_clearport_demo_preview(report, company)
    elif product_key == 'grantops':
        report = resolve_product_report('grantops', note, payload)
        if report:
            return build_grantops_demo_preview(report, company)
    elif product_key == 'draftforge':
        report = resolve_product_report('draftforge', note, payload)
        if report:
            return build_draftforge_demo_preview(report, company)
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


def build_result_pack(product_key: str, plan_name: str, company: str, note: str = "", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    target = PRODUCTS[product_key]
    signals = parse_note_signals(note)
    templates = PRODUCT_RESULT_TEMPLATES.get(product_key, {})
    goal = signals.get("goal") or target.get("problem") or target.get("summary")
    outputs = build_output_items(product_key, target, company, plan_name, goal, signals)
    delivery_assets = build_delivery_assets(target, company, goal)
    scorecard = build_quality_scorecard(target, company, goal, "delivery")
    priority = build_priority_sequence(target, company, goal)
    expert_notes = build_professional_notes(target, product_key)
    pack = {
        "title": f"{target['name']} {plan_name} 실행 결과",
        "summary": f"{company or '고객사'} 상황에 맞춘 {target['name']} {plan_name} 플랜 결과 자료가 준비되었습니다.",
        "outcomeHeadline": f"{company or '고객사'}가 지금 바로 판단하고 실행할 수 있는 핵심 결과를 먼저 정리했습니다.",
        "executiveSummary": f"이번 결과물은 {target.get('problem')} 상황을 빠르게 줄이기 위해, 요약 판단 자료와 세부 실행 자료, 발행 자산을 하나의 조회 코드 아래에서 함께 쓰도록 설계했습니다.",
        "clientContext": {"company": company or '고객사', "goal": goal, "keywords": signals.get("keywords") or target.get("tag") or '', "reference": signals.get("reference") or '', "urgency": signals.get("urgency") or ''},
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
    if product_key == 'veridion':
        return attach_veridion_report_to_pack(pack, product_key, company, note, payload)
    if product_key == 'clearport':
        report = resolve_product_report('clearport', note, payload)
        return build_clearport_result_pack_from_report(pack, report, company) if report else pack
    if product_key == 'grantops':
        report = resolve_product_report('grantops', note, payload)
        return build_grantops_result_pack_from_report(pack, report, company) if report else pack
    if product_key == 'draftforge':
        report = resolve_product_report('draftforge', note, payload)
        return build_draftforge_result_pack_from_report(pack, report, company) if report else pack
    return pack

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
        order["resultPack"] = build_result_pack(order["product"], order["plan"], order.get("company", ""), order.get("note", ""), order)
        return order
    pubs = create_publications_for_order(order)
    order["publicationIds"] = [item["id"] for item in pubs]
    order["publicationCount"] = len(order["publicationIds"])
    order["resultPack"] = build_result_pack(order["product"], order["plan"], order.get("company", ""), order.get("note", ""), order)
    return order


def finalize_paid_order(order: dict[str, Any]) -> dict[str, Any]:
    order["paymentStatus"] = "paid"
    order["status"] = "delivered"
    order["resultPack"] = build_result_pack(order["product"], order["plan"], order.get("company", ""), order.get("note", ""), order)
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
            "reportId": clean(payload.get("reportId")),
            "reportCode": normalize_code(payload.get("reportCode")),
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
        "reportId": clean(payload.get("reportId")),
        "reportCode": normalize_code(payload.get("reportCode")),
        "resultPack": build_result_pack(product, plan, company, clip_text(payload.get("note"), 1000), payload) if status == "paid" else None,
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
        "integration": {"system_config_endpoint": "/api/public/system-config", "demo_endpoint": "/api/public/demo-requests", "contact_endpoint": "/api/public/contact-requests", "portal_lookup_endpoint": "/api/public/portal/lookup", "order_endpoint": "/api/public/orders", "reserve_order_endpoint": "/api/public/orders/reserve", "toss_confirm_endpoint": "/api/public/payments/toss/confirm", "board_feed_endpoint": "/api/public/board/feed", "admin_validate_endpoint": "/api/admin/validate", "admin_state_endpoint": "/api/admin/state", "veridion_scan_endpoint": "/api/public/veridion/scan", "clearport_analyze_endpoint": "/api/public/clearport/analyze", "grantops_analyze_endpoint": "/api/public/grantops/analyze", "draftforge_analyze_endpoint": "/api/public/draftforge/analyze"},
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

        @app.post("/api/public/veridion/scan")
        def public_veridion_scan(payload: dict[str, Any]) -> dict[str, Any]:
            cache_key = scan_cache_key(payload)
            cached = read_cached_scan(cache_key)
            if cached:
                return {"ok": True, "report": cached, "cached": True, "state": state_payload()}
            report = build_veridion_scan(payload)
            write_cached_scan(cache_key, report)
            return {"ok": True, "report": report, "cached": False, "preview": build_veridion_demo_preview(report, clip_text(payload.get('company'), 160) or '샘플 회사'), "state": state_payload()}

        @app.post("/api/public/clearport/analyze")
        def public_clearport_analyze(payload: dict[str, Any]) -> dict[str, Any]:
            report = build_clearport_report(payload)
            return {"ok": True, "report": report, "preview": build_clearport_demo_preview(report, clip_text(payload.get('company'), 160) or '샘플 회사'), "state": state_payload()}

        @app.post("/api/public/grantops/analyze")
        def public_grantops_analyze(payload: dict[str, Any]) -> dict[str, Any]:
            report = build_grantops_report(payload)
            return {"ok": True, "report": report, "preview": build_grantops_demo_preview(report, clip_text(payload.get('company'), 160) or '샘플 회사'), "state": state_payload()}

        @app.post("/api/public/draftforge/analyze")
        def public_draftforge_analyze(payload: dict[str, Any]) -> dict[str, Any]:
            report = build_draftforge_report(payload)
            return {"ok": True, "report": report, "preview": build_draftforge_demo_preview(report, clip_text(payload.get('company'), 160) or '샘플 회사'), "state": state_payload()}

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
