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
import ssl
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dotenv import load_dotenv
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
from bs4 import FeatureNotFound
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, Response, UploadFile
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
LIBRARY_ASSET_DIR = APP_DATA_DIR / "library_assets"
LIBRARY_ASSET_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.getenv("NV0_DB_PATH", str(APP_DATA_DIR / "nv0.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SITE_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
PRODUCTS = {item["key"]: item for item in SITE_DATA["products"]}
PUBLIC_BOARD = SITE_DATA.get("public_board", [])
BOARD_ONLY_MODE = os.getenv("NV0_BOARD_ONLY_MODE", "0").lower() in {"1", "true", "yes", "on"}
STORE_TYPES = ["publications", "scheduler", "assets"] if BOARD_ONLY_MODE else ["orders", "demos", "contacts", "lookups", "reports", "publications", "webhook_events", "scheduler", "assets", "accounts", "sessions"]

APP_PORT = str(os.getenv("PORT", "8000") or "8000").strip() or "8000"
NV0_BASE_URL = os.getenv("NV0_BASE_URL", f"http://127.0.0.1:{APP_PORT}").rstrip("/")
NV0_ADMIN_TOKEN = os.getenv("NV0_ADMIN_TOKEN", "")
NV0_PAYMENT_PROVIDER = os.getenv("NV0_PAYMENT_PROVIDER", SITE_DATA.get("integration", {}).get("payment_provider", "toss"))
NV0_TOSS_CLIENT_KEY = os.getenv("NV0_TOSS_CLIENT_KEY", "")
NV0_TOSS_SECRET_KEY = os.getenv("NV0_TOSS_SECRET_KEY", "")
NV0_TOSS_MOCK = os.getenv("NV0_TOSS_MOCK", "0").lower() in {"1", "true", "yes", "on"}
NV0_TOSS_WEBHOOK_SECRET = os.getenv("NV0_TOSS_WEBHOOK_SECRET", "")
NV0_ENABLE_MANUAL_ADMIN_ACTIONS = os.getenv("NV0_ENABLE_MANUAL_ADMIN_ACTIONS", "0").lower() in {"1", "true", "yes", "on"}
NV0_ADMIN_COOKIE_NAME = os.getenv("NV0_ADMIN_COOKIE_NAME", "nv0_admin_session").strip() or "nv0_admin_session"
ADMIN_SESSION_TTL_SECONDS = max(300, int(os.getenv("NV0_ADMIN_SESSION_TTL_SECONDS", "43200") or "43200"))
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
ANALYSIS_CACHE_TTL_SECONDS = max(60, int(os.getenv("NV0_ANALYSIS_CACHE_TTL_SECONDS", "1800") or "1800"))

VERIDION_COUNTRY_OPTIONS: dict[str, dict[str, Any]] = {
    "KR": {"label": "대한민국", "legal_basis": ["전자상거래법", "개인정보 보호법", "정보통신망법", "표시광고법"]},
    "JP": {"label": "일본", "legal_basis": ["특정상거래법", "개인정보보호법(APPI)"]},
    "US": {"label": "미국", "legal_basis": ["FTC 가이드", "주별 개인정보보호 규정"]},
    "EU": {"label": "유럽연합", "legal_basis": ["GDPR", "ePrivacy Directive"]},
    "CN": {"label": "중국", "legal_basis": ["개인정보보호법(PIPL)", "전자상거래법"]},
    "SEA": {"label": "동남아", "legal_basis": ["주요국 전자상거래·개인정보 규정 요약 룰셋"]},
    "GLOBAL": {"label": "글로벌", "legal_basis": ["주요 시장 공통 전자상거래·개인정보 준수 체크셋"]},
}
VERIDION_DEFAULT_COUNTRY = "KR"


def resolve_veridion_country(payload: dict[str, Any]) -> dict[str, Any]:
    raw_code = clean(payload.get('country')).upper() or ''
    raw_market = clean(payload.get('market'))
    if raw_code in VERIDION_COUNTRY_OPTIONS:
        country_code = raw_code
    elif raw_market:
        normalized_market = re.sub(r'\s+', '', raw_market).upper()
        aliases = {
            '대한민국': 'KR', '한국': 'KR', 'KOREA': 'KR', 'SOUTHKOREA': 'KR', 'KR': 'KR',
            '일본': 'JP', 'JAPAN': 'JP', 'JP': 'JP',
            '미국': 'US', 'USA': 'US', 'US': 'US', 'UNITEDSTATES': 'US',
            '유럽연합': 'EU', 'EUROPEANUNION': 'EU', 'EU': 'EU',
            '중국': 'CN', 'CHINA': 'CN', 'CN': 'CN',
            '동남아': 'SEA', 'SOUTHEASTASIA': 'SEA', 'SEA': 'SEA',
            '글로벌': 'GLOBAL', 'GLOBAL': 'GLOBAL',
        }
        country_code = aliases.get(normalized_market, VERIDION_DEFAULT_COUNTRY)
    else:
        country_code = VERIDION_DEFAULT_COUNTRY
    country_meta = deepcopy(VERIDION_COUNTRY_OPTIONS.get(country_code, VERIDION_COUNTRY_OPTIONS[VERIDION_DEFAULT_COUNTRY]))
    country_meta['code'] = country_code
    return country_meta

IDEMPOTENCY_TTL_SECONDS = max(60, int(os.getenv("NV0_IDEMPOTENCY_TTL_SECONDS", "900") or "900"))
ALLOW_LOCAL_SCAN = os.getenv("NV0_ALLOW_LOCAL_SCAN", "0").lower() in {"1", "true", "yes", "on"}
_VERIDION_SCAN_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_VERIDION_SCAN_CACHE_LOCK = threading.Lock()
_ANALYSIS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_ANALYSIS_CACHE_LOCK = threading.Lock()


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
        f"<body><main><div class='card'><h1>이 경로는 운영하지 않습니다</h1><p>현재 NV0는 자료실 중심 운영 화면만 제공합니다.</p><p>요청 경로: <code>{path}</code></p><p><a href='/board/'>자료실로 이동</a> · <a href='/admin/'>관리자 열기</a></p></div></main></body></html>"
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


def normalize_for_cache(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key in sorted(value):
            if str(key).startswith('_'):
                continue
            item = normalize_for_cache(value[key])
            if item in ({}, [], '', None):
                continue
            normalized[str(key)] = item
        return normalized
    if isinstance(value, (list, tuple, set)):
        items = [normalize_for_cache(item) for item in value]
        return [item for item in items if item not in ({}, [], '', None)]
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    return clean(value)


def payload_digest(namespace: str, payload: Any) -> str:
    raw = json.dumps({'ns': namespace, 'payload': normalize_for_cache(payload)}, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def find_recent_record_by_fingerprint(record_type: str, fingerprint: str, *, ttl_seconds: int = IDEMPOTENCY_TTL_SECONDS, allowed_statuses: set[str] | None = None) -> dict[str, Any] | None:
    target = clean(fingerprint)
    if not target:
        return None
    now = datetime.now(timezone.utc)
    for item in load_records(record_type):
        if clean(item.get('fingerprint')) != target:
            continue
        if allowed_statuses is not None:
            status = clean(item.get('paymentStatus') or item.get('status'))
            if status not in allowed_statuses:
                continue
        created = parse_iso(clean(item.get('updatedAt')) or clean(item.get('createdAt')))
        if created is None or (now - created).total_seconds() <= max(1, int(ttl_seconds)):
            return item
    return None


def analysis_cache_key(kind: str, payload: dict[str, Any]) -> str:
    return payload_digest(f'analysis:{clean(kind).lower()}', payload)


def read_cached_analysis(kind: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    cache_key = analysis_cache_key(kind, payload)
    with _ANALYSIS_CACHE_LOCK:
        entry = _ANALYSIS_CACHE.get(cache_key)
        if not entry:
            return None
        expires_at, report = entry
        if time.time() >= expires_at:
            _ANALYSIS_CACHE.pop(cache_key, None)
            return None
        return deepcopy(report)


def write_cached_analysis(kind: str, payload: dict[str, Any], report: dict[str, Any]) -> None:
    with _ANALYSIS_CACHE_LOCK:
        _ANALYSIS_CACHE[analysis_cache_key(kind, payload)] = (time.time() + ANALYSIS_CACHE_TTL_SECONDS, deepcopy(report))


def build_result_pack_artifact_manifest(pack: dict[str, Any]) -> list[dict[str, Any]]:
    outputs = pack.get('outputs') or []
    issuance = pack.get('issuanceBundle') or []
    delivery_assets = pack.get('deliveryAssets') or []
    return [
        {'key': 'executive-summary', 'label': '핵심 요약', 'ready': len(clean(pack.get('executiveSummary'))) >= 40, 'count': 1 if clean(pack.get('executiveSummary')) else 0},
        {'key': 'outputs', 'label': '세부 결과물', 'ready': bool(outputs), 'count': len(outputs)},
        {'key': 'issuance-bundle', 'label': '발행 자산', 'ready': bool(issuance), 'count': len(issuance)},
        {'key': 'delivery-assets', 'label': '전달 자산', 'ready': bool(delivery_assets), 'count': len(delivery_assets)},
        {'key': 'priority-sequence', 'label': '우선순위', 'ready': bool(pack.get('prioritySequence')), 'count': len(pack.get('prioritySequence') or [])},
        {'key': 'expert-notes', 'label': '전문가 노트', 'ready': bool(pack.get('expertNotes')), 'count': len(pack.get('expertNotes') or [])},
    ]


def build_result_pack_quality_validation(pack: dict[str, Any]) -> dict[str, Any]:
    outputs = pack.get('outputs') or []
    issuance = pack.get('issuanceBundle') or []
    delivery_assets = pack.get('deliveryAssets') or []
    scorecard = pack.get('scorecard') or {}
    gates = [
        {'label': '핵심 요약', 'ok': len(clean(pack.get('executiveSummary'))) >= 40, 'detail': '결제 후 즉시 읽을 요약이 충분한지 확인합니다.'},
        {'label': '세부 결과물', 'ok': len(outputs) >= 3, 'detail': '실행용 결과물 3건 이상을 확인합니다.'},
        {'label': '발행 자산', 'ok': len(issuance) >= 3, 'detail': '발행 자산 번들이 3건 이상인지 확인합니다.'},
        {'label': '전달 자산', 'ok': len(delivery_assets) >= 3, 'detail': '전달/공유 자산이 3건 이상인지 확인합니다.'},
        {'label': '품질 점수', 'ok': int(scorecard.get('earned') or 0) == int(scorecard.get('total') or 100), 'detail': '품질 점수카드가 만점 기준인지 확인합니다.'},
        {'label': '다음 행동', 'ok': len(pack.get('prioritySequence') or []) >= 3, 'detail': '즉시 움직일 우선순위가 3개 이상인지 확인합니다.'},
    ]
    passed = all(item['ok'] for item in gates)
    return {'passed': passed, 'grade': 'A+' if passed else 'review', 'gates': gates, 'summary': '결과물, 발행, 전달, 품질 게이트가 모두 채워졌습니다.' if passed else '발행 전 재검토가 필요한 항목이 남아 있습니다.'}


def enrich_result_pack(pack: dict[str, Any], order: dict[str, Any] | None = None) -> dict[str, Any]:
    enriched = deepcopy(pack)
    order = deepcopy(order or {})
    manifest = build_result_pack_artifact_manifest(enriched)
    validation = build_result_pack_quality_validation(enriched)
    publication_ids = [clean(item) for item in (order.get('publicationIds') or []) if clean(item)]
    order_code = clean(order.get('code')) or clean((enriched.get('linkedReport') or {}).get('code'))
    bundle_hash = payload_digest('result-pack', {
        'title': enriched.get('title'), 'summary': enriched.get('summary'), 'outputs': enriched.get('outputs') or [],
        'issuanceBundle': enriched.get('issuanceBundle') or [], 'deliveryAssets': enriched.get('deliveryAssets') or [],
        'linkedReport': enriched.get('linkedReport') or {}, 'orderCode': order_code, 'publicationIds': publication_ids,
    })
    enriched['resultPackVersion'] = '2026.04.v2'
    enriched['artifactManifest'] = manifest
    enriched['qualityValidation'] = validation
    enriched['issuanceReadiness'] = {
        'status': 'ready' if validation.get('passed') else 'review',
        'reportCode': order_code,
        'bundleHash': bundle_hash,
        'publicationCount': len(publication_ids),
        'generatedAt': clean(enriched.get('generatedAt')) or now_iso(),
        'summary': '결과 요약, 실행 자료, 발행 자산, 전달 자산이 같은 코드 기준으로 묶였습니다.' if validation.get('passed') else '발행본 핵심 요소 중 일부가 부족합니다.',
    }
    enriched['supportGuide'] = {
        'portalLookup': '결제 이메일과 조회 코드로 포털에서 다시 확인할 수 있습니다.',
        'reissuePolicy': '같은 주문 코드 기준으로 재발행과 후속 보강을 이어갈 수 있습니다.',
        'qaPolicy': '핵심 요약, 세부 결과물, 발행 자산, 전달 자산, 우선순위를 함께 검증합니다.',
    }
    enriched['recheckPlan'] = [
        {'step': '핵심 요약 재검토', 'detail': '실제 사용자가 바로 이해하는지 핵심 요약과 우선순위를 다시 읽습니다.'},
        {'step': '세부 결과물 적용 확인', 'detail': '체크리스트, 규칙표, 문장 세트가 현업에 바로 맞는지 적용 후 다시 비교합니다.'},
        {'step': '포털/재발행 연결 확인', 'detail': '조회 코드, 발행 자산, 후속 재발행이 같은 흐름으로 이어지는지 확인합니다.'},
    ]
    enriched['stabilityGuards'] = [
        '동일 입력은 짧은 시간 안에 중복 발행하지 않도록 잠급니다.',
        '결과물 무결성 해시와 품질 게이트를 함께 남깁니다.',
        '포털 조회와 발행 자산은 같은 조회 코드 기준으로 연결합니다.',
    ]
    enriched['resultPackDigest'] = bundle_hash
    return enriched


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
    text = clean(price).replace(',', '').replace('/월', '').replace('월', '')
    if text.endswith('만'):
        number = clean(text[:-1])
        if number.isdigit():
            return int(number) * 10000
    digits = ''.join(ch for ch in text if ch.isdigit())
    return int(digits or '0') * (10000 if '만' in text and not text.endswith('만') else 1) if digits else 0


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


def public_state_payload(*record_types: str) -> dict[str, Any]:
    allowed = [clean(name) for name in record_types if clean(name) in {"publications", "reports"}]
    if not allowed:
        return {}
    return {name: load_records(name) for name in allowed}


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


def board_settings_record() -> dict[str, Any]:
    return get_board_settings()


def publication_cta_defaults(product_key: str) -> tuple[str, str]:
    target = PRODUCTS.get(product_key) or {}
    automation = target.get("board_automation") or {}
    settings = get_board_settings()
    global_label = clip_text(settings.get("ctaLabel"), 120)
    global_href = clip_text(settings.get("ctaHref"), 500)
    use_global = bool(settings.get("autoPublishAllProducts"))
    label = global_label if use_global and global_label else clip_text(automation.get("cta_label"), 120) or "제품 설명 보기"
    href = global_href if use_global and global_href else clip_text(automation.get("cta_href"), 500) or f"/products/{product_key}/index.html#intro"
    return label, href


def intake_required_for_order(order: dict[str, Any]) -> bool:
    if not clip_text(order.get("company"), 160):
        return True
    if not clip_text(order.get("name"), 120):
        return True
    if not validate_email(normalize_email(order.get("email"))):
        return True
    if clean(order.get("product")) == "veridion" and not clip_text(order.get("link") or order.get("website"), 500):
        return True
    return False


def finalize_paid_order_or_require_intake(order: dict[str, Any]) -> dict[str, Any]:
    if intake_required_for_order(order):
        order["paymentStatus"] = "paid"
        order["status"] = "intake_required"
        order["resultPack"] = None
        order["publicationIds"] = order.get("publicationIds") or []
        order["publicationCount"] = len(order.get("publicationIds") or [])
        delivery_meta = deepcopy(order.get("deliveryMeta") or {})
        delivery_meta["automation"] = "awaiting_intake"
        delivery_meta.pop("deliveredAt", None)
        order["deliveryMeta"] = delivery_meta
        return order
    return finalize_paid_order(order)


def submit_order_intake(order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with order_lock(order_id):
        order = get_record("orders", order_id)
        if not order:
            raise HTTPException(status_code=404, detail="결제 기록을 찾지 못했습니다.")
        if clean(order.get("paymentStatus")) != "paid":
            raise HTTPException(status_code=400, detail="결제 완료 후에만 진행 정보를 입력할 수 있습니다.")
        order["company"] = clip_text(payload.get("company") or order.get("company"), 160)
        order["name"] = clip_text(payload.get("name") or order.get("name"), 120)
        order["email"] = normalize_email(payload.get("email") or order.get("email"))
        link_value = clip_text(payload.get("website") or payload.get("link") or order.get("link") or order.get("website"), 500)
        if link_value:
            order["link"] = link_value
            order["website"] = link_value
        note = clip_text(payload.get("note"), 1000)
        if note:
            order["note"] = note
        order["updatedAt"] = now_iso()
        updated = finalize_paid_order_or_require_intake(order)
        return upsert_record("orders", updated)


def create_library_publication(payload: dict[str, Any]) -> dict[str, Any]:
    product_key = clean(payload.get("product"))
    validate_product(product_key)
    auto_generate = bool(payload.get("autoGenerate"))
    title = clip_text(payload.get("title"), 200)
    summary = clip_text(payload.get("summary"), 400)
    body = clip_text(payload.get("body"), 20000)
    asset_url = clip_text(payload.get("assetUrl"), 500)
    if auto_generate:
        publication = create_board_publication(product_key, source='admin-auto')
        if asset_url:
            publication["assetUrl"] = asset_url
            publication = upsert_record("publications", publication)
        return publication
    if not title:
        raise HTTPException(status_code=400, detail="자료 제목이 필요합니다.")
    default_label, default_href = publication_cta_defaults(product_key)
    cta_href = clip_text(payload.get("ctaHref"), 500) or asset_url or default_href
    pub = build_publication_payload(
        product_key=product_key,
        title=title,
        summary=summary or body[:180] or f"{product_name(product_key)} 자료",
        source="admin-manual",
        code=f"LIB-{product_prefix(product_key)}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        created_at=now_iso(),
        cta_label=clip_text(payload.get("ctaLabel"), 120) or default_label,
        cta_href=cta_href,
        topic_summary=summary or body[:180] or title,
        publication_id=uid("publib"),
    )
    if body:
        pub["body"] = body
        pub["bodyHtml"] = f"<div class='article-shell'><p class='article-lead'>{escape(summary or title)}</p><div class='article-sections'><section><h4>{escape(title)}</h4><p>{escape(body).replace(chr(10), '<br>')}</p></section></div></div>"
    if asset_url:
        pub["assetUrl"] = asset_url
    return upsert_record("publications", pub)


def create_library_asset(payload: dict[str, Any]) -> dict[str, Any]:
    product_key = clean(payload.get("product"))
    validate_product(product_key)
    title = clip_text(payload.get("title"), 200) or "업로드 자료"
    filename = clean(payload.get("filename")) or f"{uid('asset')}.bin"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip(".-") or f"{uid('asset')}.bin"
    content_b64 = payload.get("contentBase64") or ""
    mime_type = clip_text(payload.get("mimeType"), 120) or "application/octet-stream"
    relative_url = ""
    size = 0
    if content_b64:
        try:
            blob = base64.b64decode(content_b64)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"파일 인코딩이 올바르지 않습니다: {exc}")
        dest = LIBRARY_ASSET_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uid('asset')}-{safe_name}"
        dest.write_bytes(blob)
        relative_url = f"/uploads/{dest.name}"
        size = len(blob)
    elif clip_text(payload.get("url"), 500):
        relative_url = clip_text(payload.get("url"), 500)
    else:
        raise HTTPException(status_code=400, detail="업로드할 파일 내용 또는 URL이 필요합니다.")
    asset = {
        "id": uid("asset"),
        "product": product_key,
        "productName": product_name(product_key),
        "title": title,
        "filename": safe_name,
        "mimeType": mime_type,
        "url": relative_url,
        "size": size,
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
        "source": "admin-upload",
    }
    return upsert_record("assets", asset)


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
    local_scan_allowed = ALLOW_LOCAL_SCAN or _BASE_URL_HOST in LOCAL_HOSTS or _BASE_URL_HOST == '127.0.0.1'
    if host in LOCAL_HOSTS or host in INTERNAL_HOSTS:
        if not local_scan_allowed:
            raise HTTPException(status_code=400, detail='로컬 또는 내부 주소는 현재 점검이 허용되지 않습니다.')
        return
    for ip in _resolved_ip_flags(host):
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            if not local_scan_allowed:
                raise HTTPException(status_code=400, detail='내부 네트워크 성격의 주소는 점검할 수 없습니다.')
            return


def enumerate_scan_entry_urls(url: str) -> list[str]:
    parsed = urlparse(url)
    host = clean(parsed.hostname).lower()
    if not host:
        return [url]
    candidates: list[str] = []
    def add(candidate: str) -> None:
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    normalized = urlunparse((parsed.scheme or 'https', parsed.netloc, parsed.path or '/', '', parsed.query, ''))
    add(normalized)
    if parsed.scheme == 'https':
        add(urlunparse(('http', parsed.netloc, parsed.path or '/', '', parsed.query, '')))
    elif parsed.scheme == 'http':
        add(urlunparse(('https', parsed.netloc, parsed.path or '/', '', parsed.query, '')))
    bare_host = host[4:] if host.startswith('www.') else host
    alt_host = f'www.{bare_host}' if not host.startswith('www.') else bare_host
    if alt_host and alt_host != host:
        alt_netloc = alt_host
        if parsed.port:
            alt_netloc = f'{alt_host}:{parsed.port}'
        add(urlunparse((parsed.scheme or 'https', alt_netloc, parsed.path or '/', '', parsed.query, '')))
        add(urlunparse(('http' if parsed.scheme == 'https' else 'https', alt_netloc, parsed.path or '/', '', parsed.query, '')))
    return candidates


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

def format_krw_manwon(value: int | float | None) -> str:
    amount = int(max(0, round(float(value or 0))))
    if amount >= 100_000_000:
        return f"{amount / 100_000_000:.1f}억원"
    if amount >= 10_000:
        return f"{amount / 10_000:.0f}만원"
    return f"{amount:,}원"


VERIDION_ISSUE_RULES: dict[str, dict[str, Any]] = {
    'claim_soften': {'lawGroup': 'advertising', 'lawLabel': '광고·표현', 'area': '광고 문구', 'penaltyMinKrw': 500_000, 'penaltyMaxKrw': 5_000_000},
    'privacy_policy_missing': {'lawGroup': 'privacy', 'lawLabel': '개인정보', 'area': '정책 고지', 'penaltyMinKrw': 2_000_000, 'penaltyMaxKrw': 24_000_000},
    'consent_language_weak': {'lawGroup': 'privacy', 'lawLabel': '개인정보', 'area': '동의 흐름', 'penaltyMinKrw': 1_000_000, 'penaltyMaxKrw': 12_000_000},
    'refund_missing': {'lawGroup': 'commerce', 'lawLabel': '전자상거래', 'area': '환불·청약철회', 'penaltyMinKrw': 1_000_000, 'penaltyMaxKrw': 10_000_000},
    'terms_missing': {'lawGroup': 'commerce', 'lawLabel': '전자상거래', 'area': '이용약관', 'penaltyMinKrw': 500_000, 'penaltyMaxKrw': 5_000_000},
    'business_info_missing': {'lawGroup': 'commerce', 'lawLabel': '전자상거래', 'area': '사업자 정보', 'penaltyMinKrw': 500_000, 'penaltyMaxKrw': 5_000_000},
    'exploration_low': {'lawGroup': 'crawl', 'lawLabel': '탐색 품질', 'area': '탐색 범위', 'penaltyMinKrw': 0, 'penaltyMaxKrw': 0},
    'robots_missing': {'lawGroup': 'crawl', 'lawLabel': '탐색 품질', 'area': 'robots.txt', 'penaltyMinKrw': 0, 'penaltyMaxKrw': 0},
    'sitemap_missing': {'lawGroup': 'crawl', 'lawLabel': '탐색 품질', 'area': 'sitemap', 'penaltyMinKrw': 0, 'penaltyMaxKrw': 0},
    'live_fetch_limited': {'lawGroup': 'crawl', 'lawLabel': '실시간 연결', 'area': '실시간 탐색', 'penaltyMinKrw': 0, 'penaltyMaxKrw': 0},
}

VERIDION_INDUSTRY_BASELINES: dict[str, dict[str, Any]] = {
    'commerce': {'label': '이커머스', 'baseline': 58, 'spread': 18, 'low': 28, 'high': 82, 'averageComplianceRate': 74, 'top10ComplianceRate': 92, 'bottom30ComplianceRate': 61},
    'beauty': {'label': '뷰티·웰니스', 'baseline': 55, 'spread': 17, 'low': 26, 'high': 80, 'averageComplianceRate': 71, 'top10ComplianceRate': 90, 'bottom30ComplianceRate': 58},
    'healthcare': {'label': '의료·건강', 'baseline': 61, 'spread': 16, 'low': 30, 'high': 84, 'averageComplianceRate': 77, 'top10ComplianceRate': 94, 'bottom30ComplianceRate': 64},
    'education': {'label': '교육·서비스', 'baseline': 51, 'spread': 17, 'low': 24, 'high': 78, 'averageComplianceRate': 72, 'top10ComplianceRate': 91, 'bottom30ComplianceRate': 59},
    'saas': {'label': 'B2B SaaS', 'baseline': 46, 'spread': 15, 'low': 22, 'high': 72, 'averageComplianceRate': 79, 'top10ComplianceRate': 95, 'bottom30ComplianceRate': 67},
    'default': {'label': '일반 온라인 서비스', 'baseline': 52, 'spread': 18, 'low': 24, 'high': 80, 'averageComplianceRate': 73, 'top10ComplianceRate': 91, 'bottom30ComplianceRate': 60},
}

VERIDION_COMPLIANCE_RULES: dict[str, list[dict[str, Any]]] = {
    'default': [
        {'key': 'home_available', 'label': '첫 화면 접근 가능', 'weight': 1.0},
        {'key': 'policy_visibility', 'label': '개인정보처리방침 공개', 'weight': 1.3, 'applies_if': 'forms_or_privacy_focus'},
        {'key': 'consent_language', 'label': '폼 직전 동의 문구', 'weight': 1.1, 'applies_if': 'forms'},
        {'key': 'terms_visibility', 'label': '이용약관/서비스 조건 공개', 'weight': 1.1, 'applies_if': 'checkout_or_forms'},
        {'key': 'refund_visibility', 'label': '환불·청약철회 공개', 'weight': 1.4, 'applies_if': 'checkout'},
        {'key': 'business_info', 'label': '사업자/고객센터 고지', 'weight': 1.2, 'applies_if': 'commerce_kr'},
        {'key': 'claim_controls', 'label': '과장·단정 표현 통제', 'weight': 1.2},
        {'key': 'exploration_quality', 'label': '핵심 페이지 탐색률', 'weight': 0.9},
        {'key': 'sitemap_signal', 'label': 'sitemap 공개', 'weight': 0.6},
        {'key': 'robots_signal', 'label': 'robots.txt 응답', 'weight': 0.4},
    ],
    'commerce': [
        {'key': 'checkout_surface', 'label': '결제/구매 화면 노출', 'weight': 0.8},
        {'key': 'refund_visibility', 'label': '환불·청약철회 공개', 'weight': 1.6, 'applies_if': 'checkout_or_commerce'},
        {'key': 'terms_visibility', 'label': '이용약관/결제 조건 공개', 'weight': 1.3, 'applies_if': 'checkout_or_commerce'},
        {'key': 'business_info', 'label': '사업자 정보 공개', 'weight': 1.4, 'applies_if': 'commerce_kr'},
    ],
    'beauty': [
        {'key': 'claim_controls', 'label': '효능·전후 표현 통제', 'weight': 1.5},
        {'key': 'policy_visibility', 'label': '상담/예약 개인정보 고지', 'weight': 1.2, 'applies_if': 'forms_or_privacy_focus'},
    ],
    'healthcare': [
        {'key': 'claim_controls', 'label': '의료·건강 표현 통제', 'weight': 1.7},
        {'key': 'policy_visibility', 'label': '민감정보 고지', 'weight': 1.3, 'applies_if': 'forms_or_privacy_focus'},
        {'key': 'consent_language', 'label': '상담 신청 동의 문구', 'weight': 1.2, 'applies_if': 'forms'},
    ],
    'education': [
        {'key': 'terms_visibility', 'label': '수강/이용 조건 공개', 'weight': 1.2, 'applies_if': 'checkout_or_forms'},
        {'key': 'refund_visibility', 'label': '환불 기준 공개', 'weight': 1.3, 'applies_if': 'checkout_or_commerce'},
    ],
    'saas': [
        {'key': 'terms_visibility', 'label': '구독/서비스 조건 공개', 'weight': 1.3, 'applies_if': 'checkout_or_forms'},
        {'key': 'policy_visibility', 'label': '무료체험/문의 개인정보 고지', 'weight': 1.2, 'applies_if': 'forms_or_privacy_focus'},
        {'key': 'consent_language', 'label': '데모/문의 폼 동의 문구', 'weight': 1.1, 'applies_if': 'forms'},
    ],
}


def normalize_veridion_industry(value: Any) -> str:
    raw = clean(value).casefold()
    if not raw:
        return 'default'
    mapping = {
        'commerce': 'commerce', 'ecommerce': 'commerce', '쇼핑몰': 'commerce', '커머스': 'commerce', '이커머스': 'commerce',
        'beauty': 'beauty', '뷰티': 'beauty', '웰니스': 'beauty',
        'healthcare': 'healthcare', '의료': 'healthcare', '건강': 'healthcare', '헬스케어': 'healthcare',
        'education': 'education', '교육': 'education', '서비스': 'education',
        'saas': 'saas', 'b2b saas': 'saas',
    }
    for key, target in mapping.items():
        if key in raw:
            return target
    return 'default'


def build_veridion_compliance_profile(*, industry: Any, country: str, has_forms: bool, has_checkout: bool, has_privacy: bool, has_terms: bool, has_refund: bool, has_business_info: bool, has_consent_language: bool, claim_pages: list[dict[str, Any]], exploration_rate: float, priority_coverage: float, robots_ok: bool, sitemap_found: bool, fetched_count: int, options: set[str]) -> dict[str, Any]:
    industry_key = normalize_veridion_industry(industry)
    baseline = VERIDION_INDUSTRY_BASELINES.get(industry_key, VERIDION_INDUSTRY_BASELINES['default'])
    context = {
        'forms': has_forms,
        'checkout': has_checkout,
        'forms_or_privacy_focus': has_forms or bool({'privacy'} & options),
        'checkout_or_forms': has_checkout or has_forms,
        'checkout_or_commerce': has_checkout or industry_key == 'commerce',
        'commerce_kr': clean(country).upper() == 'KR' and (industry_key == 'commerce' or has_checkout),
    }
    pass_state = {
        'home_available': fetched_count > 0,
        'policy_visibility': has_privacy,
        'consent_language': has_consent_language,
        'terms_visibility': has_terms,
        'refund_visibility': has_refund,
        'business_info': has_business_info,
        'claim_controls': len(claim_pages) == 0,
        'exploration_quality': exploration_rate >= 55 and priority_coverage >= 70,
        'sitemap_signal': sitemap_found,
        'robots_signal': robots_ok,
        'checkout_surface': has_checkout,
    }
    all_rules = list(VERIDION_COMPLIANCE_RULES['default']) + list(VERIDION_COMPLIANCE_RULES.get(industry_key, []))
    rows: list[dict[str, Any]] = []
    total_weight = 0.0
    passed_weight = 0.0
    for rule in all_rules:
        applies_if = clean(rule.get('applies_if'))
        applies = context.get(applies_if, True) if applies_if else True
        if not applies:
            continue
        weight = float(rule.get('weight') or 1.0)
        passed = bool(pass_state.get(rule['key'], False))
        total_weight += weight
        if passed:
            passed_weight += weight
        rows.append({
            'key': rule['key'],
            'label': rule['label'],
            'weight': round(weight, 2),
            'passed': passed,
            'status': 'passed' if passed else 'missing',
        })
    applicable = len(rows)
    passed_count = len([row for row in rows if row['passed']])
    missing_count = applicable - passed_count
    compliance_rate = round((passed_weight / total_weight) * 100, 1) if total_weight else 100.0
    average_rate = float(baseline.get('averageComplianceRate') or 73)
    top10_rate = float(baseline.get('top10ComplianceRate') or max(average_rate + 15, 90))
    bottom30_rate = float(baseline.get('bottom30ComplianceRate') or max(average_rate - 13, 55))
    delta = round(compliance_rate - average_rate, 1)
    if compliance_rate >= top10_rate:
        percentile = '상위 10% 수준'
    elif compliance_rate >= average_rate:
        percentile = '평균 이상'
    elif compliance_rate <= bottom30_rate:
        percentile = '하위 30% 수준'
    else:
        percentile = '평균 이하'
    return {
        'industryKey': industry_key,
        'industryLabel': baseline['label'],
        'rate': compliance_rate,
        'applicableRuleCount': applicable,
        'passedRuleCount': passed_count,
        'missingRuleCount': missing_count,
        'averageRate': average_rate,
        'top10Rate': top10_rate,
        'bottom30Rate': bottom30_rate,
        'deltaFromAverage': delta,
        'percentileBand': percentile,
        'summaryLine': f"동종 업계 대비 준수율 {compliance_rate}% · 업계 평균 {average_rate:.0f}% · {percentile}",
        'disclaimer': '동종 업계 공개 페이지 자동 점검 기준의 내부 비교 추정치이며, 실제 행정처분 결과와 동일하지 않습니다.',
        'checklist': rows,
    }



def build_veridion_peer_comparison(*, risk_score: int, issue_count: int, high_count: int, confidence_score: float, industry: Any, compliance: dict[str, Any] | None = None) -> dict[str, Any]:
    industry_key = normalize_veridion_industry(industry)
    baseline = VERIDION_INDUSTRY_BASELINES.get(industry_key, VERIDION_INDUSTRY_BASELINES['default'])
    weighted_score = float(risk_score) + min(14.0, issue_count * 1.6) + high_count * 3.5 - max(0.0, (confidence_score - 60.0) * 0.05)
    distance = weighted_score - float(baseline['baseline'])
    bottom_percent = int(round(50 + (distance / max(1.0, float(baseline['spread']))) * 18))
    compliance_rate = float((compliance or {}).get('rate') or 0)
    average_rate = float((compliance or {}).get('averageRate') or baseline.get('averageComplianceRate') or 73)
    compliance_gap = average_rate - compliance_rate
    if compliance_gap > 0:
        bottom_percent += int(round(compliance_gap * 0.35))
    else:
        bottom_percent += int(round(compliance_gap * 0.12))
    bottom_percent = max(3, min(97, bottom_percent))
    if bottom_percent >= 80:
        band = '하위권'
    elif bottom_percent >= 60:
        band = '주의권'
    elif bottom_percent >= 35:
        band = '중간권'
    else:
        band = '양호권'
    return {
        'industryKey': industry_key,
        'industryLabel': baseline['label'],
        'bottomPercent': bottom_percent,
        'worseThanPercent': bottom_percent,
        'betterThanPercent': max(3, min(97, 100 - bottom_percent)),
        'band': band,
        'benchmarkRange': {'low': baseline['low'], 'high': baseline['high']},
        'complianceRate': compliance_rate,
        'averageComplianceRate': average_rate,
        'deltaComplianceRate': round(compliance_rate - average_rate, 1),
        'disclaimer': '유사 업종 공개 페이지 기준의 내부 비교 추정치이며, 실제 제재 가능성이나 법률 판정과 동일하지 않습니다.',
    }



VERIDION_MONITORING_SOURCES = {
    'KR': ['개인정보보호위원회', '공정거래위원회', '방송통신위원회', '전자상거래 관련 고시'],
    'US': ['FTC', 'State privacy updates', 'Subscription disclosure updates'],
    'JP': ['個人情報保護委員会', '特定商取引法 안내', '景品表示法 관련 공지'],
    'EU': ['GDPR/EDPB updates', 'Consumer rights guidance', 'Cookie consent guidance'],
    'GLOBAL': ['개인정보·전자상거래·광고 공지', '결제/구독 고지 변경', '쿠키·추적 안내 변경'],
}

def build_veridion_monitoring_snapshot(report: dict[str, Any], *, cadence_days: int = 30) -> dict[str, Any]:
    risk = report.get('risk') or {}
    country = clean(report.get('country') or 'KR').upper() or 'KR'
    country_label = report.get('countryLabel') or report.get('market') or country
    law_groups = [item.get('lawLabel') or item.get('lawGroup') for item in (risk.get('lawGroups') or []) if clean(item.get('lawLabel') or item.get('lawGroup'))]
    watch_sources = VERIDION_MONITORING_SOURCES.get(country, VERIDION_MONITORING_SOURCES.get('GLOBAL', []))
    started_at = clean(report.get('updatedAt') or report.get('createdAt')) or now_iso()
    try:
        base_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
    except Exception:
        base_dt = datetime.now(timezone.utc)
    next_check_at = (base_dt + timedelta(days=max(1, cadence_days))).isoformat()
    impact_queue = []
    for item in (report.get('pageActions') or [])[:5]:
        impact_queue.append({
            'url': item.get('url'),
            'pageType': item.get('pageType'),
            'priority': item.get('priority'),
            'reason': f"{item.get('pageType') or 'page'} 구간은 법령 변경 시 재점검 우선순위가 높습니다.",
        })
    compliance = (risk.get('compliance') or {})
    alerts = [
        {'level': 'high' if (risk.get('highRiskCount') or 0) >= 2 else 'medium', 'title': '법령 변경 시 즉시 재점검 필요', 'detail': f"현재 고위험 {risk.get('highRiskCount', 0)}건 기준으로 변경 감시 알림이 켜집니다."},
        {'level': 'medium', 'title': '영향 페이지 큐 자동 생성', 'detail': f"{len(impact_queue)}개 핵심 페이지를 다음 재점검 후보로 묶었습니다."},
        {'level': 'medium' if (compliance.get('deltaFromAverage') or 0) >= 0 else 'high', 'title': '업계 준수율 기준 변화 추적', 'detail': f"현재 준수율 {compliance.get('rate', 0)}%, 업계 평균 {compliance.get('averageRate', 0)}%를 기준값으로 삼아 변동 알림을 보냅니다."},
    ]
    return {
        'enabled': True,
        'planLabel': '서비스 3 · 월 구독형 상시 모니터링',
        'cadenceDays': max(1, cadence_days),
        'cadenceLabel': f'매 {max(1, cadence_days)}일 점검',
        'country': country,
        'countryLabel': country_label,
        'startedAt': started_at,
        'nextCheckAt': next_check_at,
        'watchSources': watch_sources,
        'watchedLawGroups': law_groups[:5],
        'impactQueue': impact_queue,
        'alerts': alerts,
        'changeSignals': ['법령/고시 변경', '정책 문구 차이', '결제·환불 화면 변화', '동종 업계 준수율 기준 변화'],
        'notificationChannels': ['email', 'dashboard', 'webhook'],
        'delivery': ['법령 변경 감지 알림', '영향 페이지 재점검 큐', '월간 요약 스냅샷', '알림 이력 보관', '준수율 변화 추적'],
        'summary': f"{country_label} 기준 법령 변경 감시와 영향 페이지 재점검을 월 구독형으로 이어갈 수 있도록 준비했습니다.",
        'disclaimer': '법령 변경 알림은 공개 고지·규정 변경 감시를 기반으로 하며, 개별 사건 법률 자문을 대신하지 않습니다.',
    }

def build_veridion_service_bundle(report: dict[str, Any]) -> list[dict[str, Any]]:
    risk = report.get('risk') or {}
    issues = report.get('issues') or []
    page_actions = report.get('pageActions') or []
    site_rules = report.get('siteSpecificRules') or []
    copy_suggestions = report.get('copySuggestions') or []
    monitoring = report.get('monitoring') or build_veridion_monitoring_snapshot(report)
    return [
        {
            'serviceNo': 1,
            'key': 'full_detail_audit',
            'title': '서비스 1 · 전체 세부 점검 리포트',
            'summary': f"리포트 코드 {report.get('code')} 기준으로 전체 이슈 {len(issues)}건, 영역별 집계, 페이지별 결과, 예상 최대 노출 범위를 전부 엽니다.",
            'includes': [
                f"전체 이슈 {len(issues)}건 상세 표",
                f"영역별 집계 {len(risk.get('lawGroups') or [])}축",
                f"페이지별 조치 {len(page_actions)}건",
                '고위험/중위험/저위험 우선순위',
                '예상 최대 과태료 및 비금전 리스크 요약',
            ],
            'status': 'ready',
        },
        {
            'serviceNo': 2,
            'key': 'tailored_remediation_report',
            'title': '서비스 2 · 사이트 맞춤형 수정안 리포트',
            'summary': f"{report.get('website') or '해당 사이트'} 화면 구조와 문구 맥락에 맞춘 맞춤형 수정안, 교체 문구, 배치 권고를 발행합니다.",
            'includes': [
                f"맞춤 규칙 {len(site_rules)}종",
                f"문구 수정 제안 {len(copy_suggestions)}종",
                '개인정보·환불·약관·사업자 정보 교체안',
                '화면별 적용 위치 및 우선순위',
                '재점검 체크리스트',
            ],
            'status': 'ready',
        },
        {
            'serviceNo': 3,
            'key': 'monthly_monitoring_subscription',
            'title': '서비스 3 · 월 구독형 상시 모니터링',
            'summary': f"{monitoring.get('countryLabel') or '운영 국가'} 기준 법령 변경 감시, 영향 페이지 큐, 재점검 알림을 월 구독형으로 이어갑니다.",
            'includes': [
                monitoring.get('cadenceLabel') or '월간 점검',
                f"감시 소스 {len(monitoring.get('watchSources') or [])}종",
                f"영향 페이지 큐 {len(monitoring.get('impactQueue') or [])}건",
                '법령 변경 알림과 월간 요약 스냅샷',
                '알림 이력과 운영 체크리스트',
            ],
            'status': 'ready',
        },
    ]



def make_veridion_issue(*, code: str, level: str, category: str, title: str, detail: str, page_url: str, evidence: str, fix_copy: str = '', occurrence_count: int = 1) -> dict[str, Any]:
    meta = VERIDION_ISSUE_RULES.get(code, {})
    item = {
        'code': code,
        'level': level,
        'category': category,
        'title': title,
        'detail': detail,
        'pageUrl': page_url,
        'evidence': clip_text(evidence, 220),
        'fixCopy': clip_text(fix_copy, 260),
        'occurrenceCount': max(1, int(occurrence_count or 1)),
        'lawGroup': meta.get('lawGroup', 'general'),
        'lawLabel': meta.get('lawLabel', category),
        'area': meta.get('area', category),
        'penaltyMinKrw': int(meta.get('penaltyMinKrw', 0) or 0),
        'penaltyMaxKrw': int(meta.get('penaltyMaxKrw', 0) or 0),
    }
    item['penaltyDisplay'] = format_krw_manwon(item['penaltyMinKrw']) + ' ~ ' + format_krw_manwon(item['penaltyMaxKrw']) if item['penaltyMaxKrw'] else '비정량 영역'
    return item


def summarize_veridion_law_groups(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in issues:
        key = clean(item.get('lawGroup')) or 'general'
        bucket = grouped.setdefault(key, {
            'lawGroup': key,
            'lawLabel': item.get('lawLabel') or item.get('category') or key,
            'issueCount': 0,
            'signalCount': 0,
            'highRiskCount': 0,
            'penaltyMinKrw': 0,
            'penaltyMaxKrw': 0,
        })
        bucket['issueCount'] += 1
        bucket['signalCount'] += max(1, int(item.get('occurrenceCount') or 1))
        if clean(item.get('level')) == 'high':
            bucket['highRiskCount'] += 1
        bucket['penaltyMinKrw'] += int(item.get('penaltyMinKrw') or 0)
        bucket['penaltyMaxKrw'] += int(item.get('penaltyMaxKrw') or 0)
    rows = []
    for bucket in grouped.values():
        max_krw = int(bucket.get('penaltyMaxKrw') or 0)
        bucket['penaltyDisplay'] = f"{format_krw_manwon(bucket.get('penaltyMinKrw'))} ~ {format_krw_manwon(max_krw)}" if max_krw else '비정량 영역'
        rows.append(bucket)
    rows.sort(key=lambda item: (-(item.get('penaltyMaxKrw') or 0), -(item.get('highRiskCount') or 0), item.get('lawLabel') or ''))
    return rows


def build_veridion_risk_profile(*, issues: list[dict[str, Any]], stats: dict[str, Any], has_forms: bool, has_checkout: bool, industry: Any = '', country: str = 'KR', has_privacy: bool = False, has_terms: bool = False, has_refund: bool = False, has_business_info: bool = False, has_consent_language: bool = False, claim_pages: list[dict[str, Any]] | None = None, robots_ok: bool = False, sitemap_found: bool = False, options: set[str] | None = None) -> dict[str, Any]:
    high_count = len([item for item in issues if clean(item.get('level')) == 'high'])
    medium_count = len([item for item in issues if clean(item.get('level')) == 'medium'])
    low_count = len([item for item in issues if clean(item.get('level')) == 'low'])
    signal_count = sum(max(1, int(item.get('occurrenceCount') or 1)) for item in issues)
    exploration_rate = float(stats.get('explorationRate') or 0)
    priority_coverage = float(stats.get('priorityCoverage') or 0)
    fetched = int(stats.get('fetched') or 0)
    severity_score = high_count * 18 + medium_count * 10 + low_count * 4
    surface_bonus = (8 if has_forms else 0) + (6 if has_checkout else 0) + min(12, signal_count * 2)
    confidence_raw = min(100.0, priority_coverage * 0.55 + exploration_rate * 0.35 + min(15.0, fetched * 4.0))
    compliance = build_veridion_compliance_profile(
        industry=industry,
        country=country,
        has_forms=has_forms,
        has_checkout=has_checkout,
        has_privacy=has_privacy,
        has_terms=has_terms,
        has_refund=has_refund,
        has_business_info=has_business_info,
        has_consent_language=has_consent_language,
        claim_pages=claim_pages or [],
        exploration_rate=exploration_rate,
        priority_coverage=priority_coverage,
        robots_ok=robots_ok,
        sitemap_found=sitemap_found,
        fetched_count=fetched,
        options=options or set(),
    )
    if confidence_raw >= 88:
        confidence_grade = 'A'
    elif confidence_raw >= 76:
        confidence_grade = 'A-'
    elif confidence_raw >= 64:
        confidence_grade = 'B+'
    elif confidence_raw >= 52:
        confidence_grade = 'B'
    elif confidence_raw >= 40:
        confidence_grade = 'C+'
    else:
        confidence_grade = 'C'
    risk_score = max(8, min(97, severity_score + surface_bonus + (6 if confidence_raw >= 75 else 0)))
    if risk_score >= 86:
        risk_band = 'critical'
        risk_label = '즉시 조치 필요'
    elif risk_score >= 68:
        risk_band = 'high'
        risk_label = '고위험'
    elif risk_score >= 45:
        risk_band = 'medium'
        risk_label = '중위험'
    else:
        risk_band = 'low'
        risk_label = '관찰 필요'
    law_groups = summarize_veridion_law_groups(issues)
    min_krw = sum(int(item.get('penaltyMinKrw') or 0) for item in issues if int(item.get('penaltyMaxKrw') or 0) > 0)
    max_krw = sum(int(item.get('penaltyMaxKrw') or 0) for item in issues if int(item.get('penaltyMaxKrw') or 0) > 0)
    max_krw = min(max_krw, 99_000_000)
    min_krw = min(min_krw, max_krw)
    exposure = {
        'minKrw': min_krw,
        'maxKrw': max_krw,
        'display': f"{format_krw_manwon(min_krw)} ~ {format_krw_manwon(max_krw)}" if max_krw else '비정량 영역 중심',
        'maxDisplay': format_krw_manwon(max_krw) if max_krw else '비정량',
        'confidenceGrade': confidence_grade,
        'disclaimer': '법률 확정 판단이 아니라 공개 페이지 자동 점검을 기반으로 한 노출 추정치입니다.',
        'nonMonetaryRisks': ['시정 권고 또는 고지 보완 요구', '결제 이탈·소비자 분쟁 가능성', '광고 집행·검수 보류 가능성'],
    }
    peer = build_veridion_peer_comparison(risk_score=risk_score, issue_count=len(issues), high_count=high_count, confidence_score=confidence_raw, industry=industry, compliance=compliance)
    diagnostics = [
        {'key': 'policy_coverage', 'label': '정책 고지 완성도', 'score': max(18, min(96, round(priority_coverage))), 'status': 'stable' if priority_coverage >= 80 else 'watch' if priority_coverage >= 55 else 'urgent', 'detail': f"핵심 페이지 커버리지 {priority_coverage}% 기준입니다."},
        {'key': 'privacy_notice', 'label': '개인정보 안내 준비도', 'score': max(15, min(96, 90 - high_count * 8 - medium_count * 4 - (0 if has_forms else 12))), 'status': 'stable' if has_forms and high_count == 0 else 'watch' if medium_count < 2 else 'urgent', 'detail': '폼 직전 고지와 개인정보처리방침 연결 상태를 함께 봅니다.'},
        {'key': 'checkout_disclosure', 'label': '결제·환불 고지 준비도', 'score': max(15, min(96, 92 - (12 if has_checkout else 2) * max(1, high_count or 1) + (6 if has_checkout else 0))), 'status': 'stable' if has_checkout and high_count == 0 else 'watch' if has_checkout else 'stable', 'detail': '결제 직전 환불·청약철회·문의 채널 고지를 우선 확인합니다.'},
        {'key': 'consumer_dispute', 'label': '소비자 분쟁 유발 가능성', 'score': max(8, min(97, round(high_count * 19 + medium_count * 11 + min(18, signal_count * 1.5)))), 'status': 'urgent' if high_count >= 2 else 'watch' if medium_count >= 2 else 'stable', 'detail': '환불/표시/고지 누락이 실제 분쟁으로 번질 가능성을 추정합니다.'},
        {'key': 'industry_compliance_rate', 'label': '동종 업계 대비 준수율', 'score': round(compliance.get('rate') or 0), 'status': 'stable' if (compliance.get('deltaFromAverage') or 0) >= 0 else 'watch' if (compliance.get('deltaFromAverage') or 0) >= -8 else 'urgent', 'detail': compliance.get('summaryLine') or '업계 기준 비교를 준비했습니다.'},
        {'key': 'issuance_readiness', 'label': '발행 작동 준비도', 'score': max(20, min(98, round((priority_coverage * 0.4) + (exploration_rate * 0.25) + (25 if issues else 12) + (10 if fetched else 0)))), 'status': 'stable' if fetched and priority_coverage >= 70 else 'watch' if issues else 'urgent', 'detail': '스캔·리포트·맞춤 규칙·모니터링 연결 가능성을 함께 봅니다.'},
    ]
    return {
        'issueCount': len(issues),
        'highRiskCount': high_count,
        'mediumRiskCount': medium_count,
        'lowRiskCount': low_count,
        'signalCount': signal_count,
        'riskScore': risk_score,
        'crisisScore': risk_score,
        'riskBand': risk_band,
        'riskLabel': risk_label,
        'confidenceGrade': confidence_grade,
        'confidenceScore': round(confidence_raw, 1),
        'estimatedExposure': exposure,
        'lawGroups': law_groups,
        'summaryLine': f"위기 점수 {risk_score}점 · 준수율 {compliance.get('rate', 0)}% · 고위험 {high_count}건 · 예상 노출 {exposure['display']}",
        'peerComparison': peer,
        'compliance': compliance,
        'diagnostics': diagnostics,
    }


def build_veridion_site_rules(report: dict[str, Any]) -> list[dict[str, Any]]:
    stats = report.get('stats') or {}
    website = clean(report.get('website'))
    rules: list[dict[str, Any]] = [
        {'label': '홈/푸터 핵심 링크 고정', 'rule': '개인정보처리방침, 이용약관, 환불정책, 고객센터 링크를 홈·푸터에 동시에 고정합니다.', 'why': f"핵심 페이지 커버리지 {stats.get('priorityCoverage', 0)}% 상태에서는 메뉴·푸터 직링크가 탐색률과 사용자 신뢰를 동시에 올립니다."},
        {'label': '폼 직전 고지 요약', 'rule': '문의·회원가입·구독 폼 바로 위에 개인정보 수집 목적·보관기간·문의처 요약을 2~3줄로 배치합니다.', 'why': '정책 페이지가 있어도 입력 직전 고지가 약하면 실제 사용자 체감과 규제 리스크가 같이 남습니다.'},
        {'label': '결제 직전 환불 요약', 'rule': '결제 버튼 근처에 환불 가능 기준, 청약철회 제한 사유, 문의 채널을 한 번 더 고정합니다.', 'why': '정책 링크만 있고 결제 직전 요약이 없으면 분쟁과 이탈이 같이 커집니다.'},
        {'label': '강한 단정 표현 완화', 'rule': '효과·우월성·속도·안전성 표현에는 범위, 조건, 예외를 같이 씁니다.', 'why': '광고 문구는 한 문장만 과해도 전체 신뢰를 떨어뜨릴 수 있습니다.'},
        {'label': '리포트 코드 기준 재점검', 'rule': f"{report.get('code')} 기준으로 수정 전/후를 같은 코드 체계로 비교 저장합니다.", 'why': f"{website or '해당 사이트'}는 한 번 점검보다 재점검 비교가 운영 효율을 더 크게 만듭니다."},
    ]
    if not any(item.get('penaltyMaxKrw') for item in (report.get('issues') or [])):
        rules.append({'label': '비정량 리스크 메모', 'rule': '금액 추정이 어려운 영역은 시정 요청·검수 보류·분쟁 가능성으로 따로 관리합니다.', 'why': '모든 리스크가 바로 금액으로 환산되지는 않습니다.'})
    return rules[:6]


def build_veridion_page_actions(report: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    page_issue_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in report.get('issues') or []:
        page_issue_map[clean(issue.get('pageUrl'))].append(issue)
    for page in (report.get('pages') or [])[:10]:
        url = clean(page.get('url'))
        linked = page_issue_map.get(url, [])
        actions.append({
            'url': url,
            'pageType': page.get('pageType'),
            'title': page.get('title') or url,
            'priority': 'high' if any(clean(item.get('level')) == 'high' for item in linked) else 'medium' if linked else 'low',
            'issues': len(linked),
            'action': ('결제/입력 직전 고지와 링크를 먼저 보강합니다.' if page.get('pageType') in {'checkout', 'contact', 'signup'} else '정책 링크, 표현 수위, 사업자 정보를 함께 정리합니다.'),
        })
    return actions[:8]


def build_veridion_remediation_plan(report: dict[str, Any]) -> list[dict[str, Any]]:
    risk = report.get('risk') or {}
    issues = report.get('issues') or []
    rules = report.get('siteSpecificRules') or []
    steps = [
        {'step': 1, 'title': '핵심 공개 구간 링크 보강', 'priority': 'high', 'detail': '홈·푸터·결제·폼 직전에서 정책 페이지와 고객센터를 직접 연결합니다.'},
        {'step': 2, 'title': '고위험 문구·고지 수정', 'priority': 'high', 'detail': '광고 표현, 개인정보 안내, 환불/청약철회 안내를 수정안 기준으로 교체합니다.'},
        {'step': 3, 'title': '페이지 단위 점검표 반영', 'priority': 'medium', 'detail': '페이지별 우선순위대로 수정 티켓을 끊고 담당 구간을 분리합니다.'},
        {'step': 4, 'title': '재점검 큐 실행', 'priority': 'medium', 'detail': f"리포트 코드 {report.get('code')} 기준으로 수정 후 다시 스캔해 고위험 {risk.get('highRiskCount', 0)}건 감소 여부를 비교합니다."},
        {'step': 5, 'title': '운영 규칙 고정', 'priority': 'low', 'detail': '새 페이지 추가 시 정책 링크, 고지 위치, 문구 톤 규칙을 출시 체크리스트에 넣습니다.'},
    ]
    if issues and rules:
        steps[1]['detail'] += f" 현재 규칙 {len(rules)}종과 우선 이슈 {len(issues)}건을 기준으로 바로 작업 가능합니다."
    return steps


def build_veridion_public_report(report: dict[str, Any]) -> dict[str, Any]:
    top_issues = (report.get('topIssues') or report.get('issues') or [])[:5]
    safe_issues = [
        {
            'code': item.get('code'),
            'level': item.get('level'),
            'category': item.get('category'),
            'title': item.get('title'),
            'detail': item.get('detail'),
            'occurrenceCount': item.get('occurrenceCount'),
            'lawLabel': item.get('lawLabel'),
            'area': item.get('area'),
            'penaltyDisplay': item.get('penaltyDisplay'),
        }
        for item in top_issues
    ]
    issuance = deepcopy(report.get('issuance') or {})
    issuance.pop('sections', None)
    issuance.pop('readyReason', None)
    return {
        'id': report.get('id'),
        'code': report.get('code'),
        'product': report.get('product'),
        'website': report.get('website'),
        'origin': report.get('origin'),
        'industry': report.get('industry'),
        'country': report.get('country'),
        'countryLabel': report.get('countryLabel') or report.get('market'),
        'market': report.get('market'),
        'legalBasis': report.get('legalBasis') or [],
        'maturity': report.get('maturity'),
        'focus': report.get('focus'),
        'options': report.get('options') or [],
        'summary': report.get('summary'),
        'stats': report.get('stats') or {},
        'risk': report.get('risk') or {},
        'serviceBundle': report.get('serviceBundle') or [],
        'monitoring': report.get('monitoring') or {},
        'crawlPolicy': report.get('crawlPolicy') or {},
        'countsByPageType': report.get('countsByPageType') or {},
        'issues': safe_issues,
        'topIssues': safe_issues,
        'issuance': issuance,
        'quality': report.get('quality') or {},
        'createdAt': report.get('createdAt'),
        'updatedAt': report.get('updatedAt'),
        'publicLocked': {
            'fullIssueCount': len(report.get('issues') or []),
            'fullRuleCount': len(report.get('siteSpecificRules') or []),
            'serviceCount': len(report.get('serviceBundle') or []),
            'message': '전체 영역, 페이지별 조치, 맞춤 규칙, 월 구독형 상시 모니터링 설정은 결제 후 발행본에서 제공합니다.',
        },
    }



def scan_cache_key(payload: dict[str, Any]) -> str:
    country_meta = resolve_veridion_country(payload)
    base = {'website': clean(payload.get('website')), 'pages': clean(payload.get('pages')), 'industry': clean(payload.get('industry')), 'country': country_meta.get('code'), 'market': country_meta.get('label'), 'maturity': clean(payload.get('maturity')), 'focus': clean(payload.get('focus')), 'options': sorted([clean(item) for item in payload.get('options') or [] if clean(item)])}
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
    country_meta = resolve_veridion_country(payload)
    country_code = country_meta.get('code', VERIDION_DEFAULT_COUNTRY)
    country_label = country_meta.get('label', VERIDION_COUNTRY_OPTIONS[VERIDION_DEFAULT_COUNTRY]['label'])
    legal_basis = country_meta.get('legal_basis') or []
    base = urlparse(website)
    origin_host = _strip_default_port(base)
    origin = urlunparse((base.scheme, base.netloc, '', '', '', ''))
    manual_urls: list[str] = []
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
    normalized_sitemap_candidates: list[str] = []
    for raw in sitemap_candidates[:5]:
        absolute = urljoin(origin + '/', clean(raw))
        if absolute and absolute not in normalized_sitemap_candidates:
            normalized_sitemap_candidates.append(absolute)
    sitemap_urls: list[str] = []
    for item in normalized_sitemap_candidates[:3]:
        for found in extract_sitemap_urls(item):
            normalized = canonicalize_same_origin(urljoin(origin + '/', found), origin_host=origin_host)
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

    seed_urls = enumerate_scan_entry_urls(website)
    for idx, item in enumerate(seed_urls[:4]):
        enqueue(item, 0 if idx == 0 else 1)
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
        html_text = fetched.get('text') or ''
        try:
            soup = BeautifulSoup(html_text, 'lxml')
        except FeatureNotFound:
            soup = BeautifulSoup(html_text, 'html.parser')
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
        issues.append(make_veridion_issue(code='claim_soften', level='high', category='광고·표현', title='단정형 표현 보정이 필요합니다', detail=f"{len(claim_pages)}개 페이지에서 과장 또는 단정으로 해석될 수 있는 표현이 감지되었습니다. 효능·우월성·속도 표현은 근거 범위와 조건을 함께 적는 편이 안전합니다.", page_url=sample.get('url') or website, evidence=before, fix_copy=after, occurrence_count=len(claim_pages)))
        copy_suggestions.append({'label': '광고·효능 표현 수정안', 'pageUrl': sample.get('url') or website, 'before': before, 'after': after})
    if has_forms and not has_privacy:
        issues.append(make_veridion_issue(code='privacy_policy_missing', level='high', category='개인정보', title='개인정보처리방침 연결이 보이지 않습니다', detail='문의·회원가입·구독 입력이 있는 페이지가 확인됐지만, 개인정보처리방침으로 이어지는 공개 경로를 찾지 못했습니다.', page_url=fetched_urls[0] if fetched_urls else website, evidence='폼 입력은 있었지만 privacy/personal data 신호가 있는 정책 페이지를 찾지 못함', fix_copy='개인정보 수집·이용 목적, 보관 기간, 문의처를 확인할 수 있도록 개인정보처리방침 링크와 요약 고지를 입력 직전 구간에 배치합니다.'))
        copy_suggestions.append({'label': '개인정보 동의 안내 수정안', 'pageUrl': fetched_urls[0] if fetched_urls else website, 'before': '입력 폼 인근에 개인정보 안내가 충분하지 않음', 'after': '개인정보 수집·이용 목적, 보관 기간, 문의처를 링크와 함께 명확히 안내합니다.'})
    if has_forms and not has_consent_language:
        issues.append(make_veridion_issue(code='consent_language_weak', level='medium', category='동의 흐름', title='폼 주변 동의 문구가 약합니다', detail='폼은 확인되지만 동의·consent 관련 문구를 충분히 찾지 못했습니다. 입력 직전 안내가 짧더라도 분명해야 합니다.', page_url=fetched_urls[0] if fetched_urls else website, evidence='동의 관련 키워드 탐지 부족', fix_copy='제출 시 개인정보 수집·이용에 동의한 것으로 보며, 자세한 내용은 개인정보처리방침에서 확인하실 수 있습니다.'))
    if (options & {'commerce'} or has_checkout) and not has_refund:
        checkout_url = next((item['url'] for item in page_records if item['pageType'] == 'checkout'), website)
        issues.append(make_veridion_issue(code='refund_missing', level='high', category='결제·환불', title='환불·청약철회 기준이 공개 구간에서 충분히 보이지 않습니다', detail='결제 또는 구매 관련 페이지 신호는 있지만 환불·반품·청약철회 기준을 확인할 공개 페이지를 찾지 못했습니다.', page_url=checkout_url, evidence='checkout/buy/cart 신호 있음 + refund/청약철회 페이지 탐지 실패', fix_copy='결제 전 확인해주세요. 제공 범위, 환불 가능 기준, 청약철회 제한 사유, 문의 채널을 이 화면에서 바로 안내합니다.'))
        copy_suggestions.append({'label': '결제 전 안내문 수정안', 'pageUrl': checkout_url, 'before': '결제 또는 구매 직전 화면에 환불 기준 고지 부족', 'after': '결제 전 확인해주세요. 제공 범위, 환불 가능 기준, 청약철회 제한 사유, 문의 채널을 이 화면에서 바로 안내합니다.'})
    if (options & {'commerce'} or has_checkout) and not has_terms:
        issues.append(make_veridion_issue(code='terms_missing', level='medium', category='약관', title='이용약관 연결을 먼저 보강하는 편이 좋습니다', detail='결제·구독·회원가입 흐름이 있는데 terms/약관 페이지를 충분히 찾지 못했습니다.', page_url=website, evidence='checkout/sign-up signal with weak terms coverage', fix_copy='회원가입 또는 결제 직전 구간에 이용약관과 결제 조건을 확인할 수 있는 링크를 함께 제공합니다.'))
    if (options & {'commerce'} or has_checkout) and not has_business_info:
        issues.append(make_veridion_issue(code='business_info_missing', level='medium', category='사업자 정보', title='사업자·고객센터 정보 노출을 보강할 필요가 있습니다', detail='대한민국 기준으로 운영하는 결제형 사이트라면 상호, 대표자, 사업자등록번호, 고객센터 같은 기본 정보를 공개 구간에서 쉽게 찾을 수 있어야 합니다.', page_url=website, evidence='사업자등록번호/통신판매업/대표자/고객센터 신호 부족', fix_copy='푸터 또는 결제 전 화면에 상호, 대표자, 사업자등록번호, 통신판매업 신고 정보, 고객센터 연락처를 함께 노출합니다.'))
    if exploration_rate < 40 or priority_coverage < 60:
        issues.append(make_veridion_issue(code='exploration_low', level='medium', category='탐색 범위', title='핵심 페이지 탐색률이 낮습니다', detail=f'이번 샘플 스캔은 {fetched_count}개 페이지만 실제로 읽었고, 발견된 내부 후보는 {discovered_count}개였습니다. sitemap 또는 메뉴 연결이 약하면 핵심 페이지 커버리지가 떨어질 수 있습니다.', page_url=website, evidence=f'탐색률 {exploration_rate}% · 핵심 페이지 커버리지 {priority_coverage}%', fix_copy='개인정보처리방침, 이용약관, 환불정책, 결제 화면처럼 꼭 봐야 할 페이지를 메뉴 또는 푸터에서 직접 연결해 주세요.'))
    if not robots_doc.get('ok'):
        issues.append(make_veridion_issue(code='robots_missing', level='low', category='크롤링 힌트', title='robots.txt를 확인하지 못했습니다', detail='점검 대상은 읽을 수 있었지만 robots.txt 응답을 찾지 못했습니다. 기본 크롤링 정책이 없으면 탐색 범위 설명과 예외 관리가 어려워질 수 있습니다.', page_url=robots_url, evidence=robots_doc.get('error') or f"status {robots_doc.get('status')}", fix_copy='robots.txt에서 허용·비허용 범위와 sitemap 위치를 함께 관리하면 탐색 품질을 더 안정적으로 맞출 수 있습니다.'))
    if not sitemap_urls:
        issues.append(make_veridion_issue(code='sitemap_missing', level='low', category='탐색 효율', title='sitemap 신호가 약합니다', detail='sitemap을 찾지 못했거나 URL 집합을 읽지 못해, 이번 스캔은 메뉴와 본문 링크 중심으로만 확장되었습니다.', page_url=sitemap_url, evidence='sitemap urls 0건', fix_copy='핵심 URL이 sitemap에 정리되어 있으면 비용을 거의 늘리지 않고도 탐색률과 우선 페이지 발견율을 높일 수 있습니다.'))
    if not fetched_count:
        issues.append(make_veridion_issue(code='live_fetch_limited', level='medium', category='실시간 연결', title='실제 페이지 응답을 안정적으로 읽지 못했습니다', detail='대상 사이트가 봇 차단, TLS 설정, 타임아웃, 지역 제한 중 하나로 응답을 제한했을 수 있습니다. 데모는 입력한 도메인과 업종·운영 국가 기준으로 우선순위를 계속 계산했습니다.', page_url=website, evidence=(failed_urls[0].get('error') if failed_urls else 'fetch unavailable'), fix_copy='robots.txt, sitemap, 공개 정책 링크, 첫 화면 응답 속도를 정리하면 실제 탐색 기반 결과가 더 안정적으로 나옵니다.'))

    issues = sorted(issues, key=lambda item: (-score_severity(item.get('level', '')), -(int(item.get('penaltyMaxKrw') or 0)), item.get('category', ''), item.get('title', '')))
    top_issues = issues[:5]
    if not copy_suggestions:
        copy_suggestions.append({'label': '기본 수정 안내', 'pageUrl': website, 'before': '강한 단정 또는 누락 리스크가 적은 편입니다.', 'after': '현재 구조는 비교적 안정적입니다. 다만 개인정보·결제·고지 링크를 주기적으로 다시 확인해 주세요.'})

    detection_rate = round((((fetched_count + len(blocked_urls)) / max(1, discovered_count)) * 100), 1) if discovered_count else 0.0
    issuance_readiness = round(min(100.0, priority_coverage * 0.45 + exploration_rate * 0.25 + (18 if issues else 8) + (12 if fetched_count else 0) + (8 if bool(sitemap_urls) else 0)), 1)
    stats = {'discovered': discovered_count, 'fetched': fetched_count, 'blocked': len(blocked_urls), 'failed': len(failed_urls), 'forms': total_forms, 'internalLinks': total_internal_links, 'explorationRate': exploration_rate, 'priorityCoverage': priority_coverage, 'priorityTargets': len(expected_priority), 'priorityFound': found_priority, 'detectionRate': detection_rate, 'issuanceReadiness': issuance_readiness, 'elapsedMs': round((time.monotonic() - started) * 1000, 1)}
    risk = build_veridion_risk_profile(
        issues=issues,
        stats=stats,
        has_forms=has_forms,
        has_checkout=has_checkout,
        industry=payload.get('industry'),
        country=country_code,
        has_privacy=has_privacy,
        has_terms=has_terms,
        has_refund=has_refund,
        has_business_info=has_business_info,
        has_consent_language=has_consent_language,
        claim_pages=claim_pages,
        robots_ok=bool(robots_doc.get('ok')),
        sitemap_found=bool(sitemap_urls),
        options=options,
    )
    report_id = uid('vrep')
    report_code = make_public_code('VREP', 'veridion')
    issued_at = now_iso()
    summary = f"{website} 기준으로 같은 도메인 내부 페이지 {discovered_count}개를 후보로 잡았고, 이 중 {fetched_count}개를 실제로 읽어 탐색률 {exploration_rate}%를 기록했습니다. 분석 기준 국가는 {country_label}이며 위기 점수는 {risk.get('riskScore')}점, 고위험 이슈는 {risk.get('highRiskCount')}건, 예상 노출 범위는 {risk.get('estimatedExposure', {}).get('display')}입니다." if fetched_count else f"{website} 기준으로 실시간 공개 화면 응답은 제한적이었지만, 도메인·업종·운영 국가·중점 항목을 바탕으로 우선 점검 결과를 계속 만들었습니다. 분석 기준 국가는 {country_label}이며 현재 위기 점수는 {risk.get('riskScore')}점, 예상 노출 범위는 {risk.get('estimatedExposure', {}).get('display')}입니다."
    report = {'id': report_id, 'code': report_code, 'product': 'veridion', 'website': website, 'origin': origin, 'industry': clean(payload.get('industry')), 'country': country_code, 'countryLabel': country_label, 'market': country_label, 'legalBasis': legal_basis, 'maturity': clean(payload.get('maturity')), 'focus': clean(payload.get('focus')), 'options': sorted(options), 'summary': summary, 'stats': stats, 'risk': risk, 'crawlPolicy': {'maxPages': VERIDION_SCAN_MAX_PAGES, 'maxDiscovered': VERIDION_SCAN_MAX_DISCOVERED, 'maxDepth': VERIDION_SCAN_MAX_DEPTH, 'robotsFetched': bool(robots_doc.get('ok')), 'robotsStatus': robots_doc.get('status', 0), 'sitemapFound': bool(sitemap_urls), 'sitemapCount': len(sitemap_urls), 'mode': 'same-domain shallow crawl'}, 'pages': page_records, 'countsByPageType': {page_type: len([item for item in page_records if item.get('pageType') == page_type]) for page_type in sorted(page_types)}, 'issues': issues, 'topIssues': top_issues, 'copySuggestions': copy_suggestions[:6], 'siteSpecificRules': [], 'pageActions': [], 'remediationPlan': [], 'issuance': {'status': 'ready', 'reportTitle': 'Veridion 준법 점검 리포트', 'generatedAt': issued_at, 'reportCode': report_code, 'sections': ['스캔 개요', '위기 점수', '동종 업계 대비 준수율', '예상 노출 범위', '전체 이슈', '페이지별 결과', '맞춤 규칙', '재점검 권고'], 'readyReason': '실제 탐색 결과, 위기 점수, 전체 이슈, 맞춤 규칙까지 묶여 발행 가능한 상태입니다.' if fetched_count else '실제 페이지 응답이 제한돼도 입력값 기반 우선 점검 결과와 수정 방향을 묶어 발행 가능한 상태입니다.'}, 'quality': {'passed': bool(issues), 'gates': [{'label': '실제 페이지 읽기', 'ok': bool(fetched_count), 'detail': f'실제 HTML 페이지 {fetched_count}개를 읽었습니다.' if fetched_count else '실제 HTML 페이지 응답은 제한적이었습니다. 대신 입력값 기준 점검으로 계속 진행했습니다.'}, {'label': '탐색률 계산', 'ok': discovered_count > 0, 'detail': f'발견 {discovered_count}개 대비 탐색률 {exploration_rate}%를 계산했습니다.' if discovered_count else '발견 후보 URL이 없어 탐색률 계산을 생략했습니다.'}, {'label': '위기 점수 계산', 'ok': bool(issues), 'detail': risk.get('summaryLine') if issues else '발견 이슈가 거의 없어 위기 점수 신호가 제한적입니다.'}, {'label': '리포트 발행 준비', 'ok': bool(issues), 'detail': '요약, 전체 이슈, 페이지 기록, 맞춤 규칙을 같은 리포트 코드로 묶었습니다.' if issues else '발행용 핵심 항목이 아직 부족합니다.'}]}, 'createdAt': issued_at, 'updatedAt': issued_at}
    report['siteSpecificRules'] = build_veridion_site_rules(report)
    report['pageActions'] = build_veridion_page_actions(report)
    report['remediationPlan'] = build_veridion_remediation_plan(report)
    report['monitoring'] = build_veridion_monitoring_snapshot(report)
    report['serviceBundle'] = build_veridion_service_bundle(report)
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
    risk = report.get('risk') or {}
    issues = report.get('issues') or []
    top_issues = report.get('topIssues') or issues[:5]
    site_rules = report.get('siteSpecificRules') or []
    page_actions = report.get('pageActions') or []
    remediation_plan = report.get('remediationPlan') or []
    website = clean(report.get('website'))
    exposure = risk.get('estimatedExposure') or {}
    pack['summary'] = f"{company or '고객사'} 기준 Veridion 결과를 실제 탐색 리포트와 연결했습니다. 위기 점수 {risk.get('riskScore', 0)}점, 준수율 {(risk.get('compliance') or {}).get('rate', 0)}%, 고위험 {risk.get('highRiskCount', 0)}건, 예상 노출 {exposure.get('display', '비정량')}를 먼저 묶었습니다."
    pack['outcomeHeadline'] = '실제 탐색 결과, 전체 이슈, 맞춤 규칙까지 포함한 Veridion 발행본이 준비되었습니다.'
    pack['executiveSummary'] = f"이번 결과는 같은 도메인 내부 페이지를 실제로 읽어 만든 발행본입니다. 발견 후보 {stats.get('discovered', 0)}개 중 {stats.get('fetched', 0)}개를 읽었고, 탐색률 {stats.get('explorationRate', 0)}%, 핵심 페이지 커버리지 {stats.get('priorityCoverage', 0)}%, 위기 점수 {risk.get('riskScore', 0)}점을 기준으로 전체 이슈와 맞춤 규칙을 정리했습니다."
    pack['clientContext'] = {**(pack.get('clientContext') or {}), 'website': website, 'reportCode': report.get('code'), 'explorationRate': stats.get('explorationRate'), 'priorityCoverage': stats.get('priorityCoverage'), 'detectionRate': stats.get('detectionRate'), 'issuanceReadiness': stats.get('issuanceReadiness'), 'riskScore': risk.get('riskScore'), 'confidenceGrade': risk.get('confidenceGrade'), 'complianceRate': (risk.get('compliance') or {}).get('rate')}
    pack['penaltyExposure'] = exposure
    pack['lawGroupSummary'] = risk.get('lawGroups') or []
    pack['siteSpecificRules'] = site_rules
    pack['pageActions'] = page_actions
    pack['remediationPlan'] = remediation_plan
    pack['outputs'] = [
        {'title': '위기 점수·노출 범위 요약', 'note': f"위기 점수 {risk.get('riskScore', 0)}점", 'preview': risk.get('summaryLine') or pack['summary'], 'whatIncluded': f"고위험 {risk.get('highRiskCount', 0)}건, 전체 이슈 {risk.get('issueCount', len(issues))}건, 예상 노출 {exposure.get('display', '비정량')}를 한 번에 묶었습니다.", 'actionNow': '경영진 공유용 한 장 요약으로 먼저 보고하고 즉시 수정 범위를 고정합니다.', 'buyerValue': '보고서 첫 장에서 바로 위험도와 우선순위를 판단할 수 있습니다.', 'expertLens': '탐색률과 커버리지를 같이 보면서도 위기 점수는 별도로 계산해 과소·과대평가를 줄입니다.', 'whyItMatters': '리스크가 숫자로 정리돼야 수정 우선순위와 예산 결정을 빨리 내릴 수 있습니다.', 'deliveryState': 'ready_to_issue'},
        {'title': '전체 이슈·법령군 정리', 'note': f"법령군 {len(risk.get('lawGroups') or [])}축", 'preview': top_issues[0].get('detail') if top_issues else '주요 이슈를 먼저 확인했습니다.', 'whatIncluded': '광고·개인정보·전자상거래·탐색 품질을 구분하고, 이슈 수·신호 수·예상 노출 범위를 같이 묶습니다.', 'actionNow': '고위험부터 작업 티켓으로 분해하고, 낮은 위험은 운영 규칙으로 넘깁니다.', 'buyerValue': '같은 문제를 법령군·페이지군으로 동시에 정리해 담당자 배정이 쉬워집니다.', 'expertLens': '금액 추정이 가능한 영역과 비정량 리스크를 분리해 설명 부담을 줄입니다.', 'whyItMatters': '기술 이슈와 준법 이슈가 섞이면 실제 수정 진행이 느려집니다.', 'deliveryState': 'ready_to_issue'},
        {'title': '사이트 맞춤 규칙·페이지별 조치', 'note': f"맞춤 규칙 {len(site_rules)}종", 'preview': site_rules[0].get('rule') if site_rules else '핵심 공개 구간 규칙을 정리했습니다.', 'whatIncluded': f"맞춤 규칙 {len(site_rules)}종, 페이지별 조치 {len(page_actions)}건, 재점검 단계 {len(remediation_plan)}단계를 함께 제공합니다.", 'actionNow': '디자인·개발·운영이 같은 규칙 문서를 기준으로 수정과 재점검을 진행합니다.', 'buyerValue': '한 번 고친 뒤 같은 문제를 반복하지 않도록 운영 규칙까지 같이 남길 수 있습니다.', 'expertLens': '정책 문서 자체보다 실제 입력·결제 직전 구간과 푸터 구조를 먼저 고정합니다.', 'whyItMatters': '실행 문서가 없으면 보고서는 남아도 수정 품질은 흔들리기 쉽습니다.', 'deliveryState': 'ready_to_issue'},
    ] + pack.get('outputs', [])[3:]
    pack['quickWins'] = [
        f"위기 점수 {risk.get('riskScore', 0)}점 기준으로 홈·푸터·결제 직전 링크를 가장 먼저 보강합니다.",
        f"예상 노출 {exposure.get('display', '비정량')}에 영향을 주는 고위험 {risk.get('highRiskCount', 0)}건을 먼저 수정합니다.",
        '수정 후 같은 리포트 코드로 재점검해 감소폭을 바로 비교합니다.',
    ]
    pack['valueDrivers'] = [
        '무료 데모에서 보여준 숫자와 유료 발행본의 전체 이슈가 같은 리포트 코드로 이어집니다.',
        '전체 이슈, 페이지별 조치, 맞춤 규칙까지 한 번에 받아 바로 실행으로 옮길 수 있습니다.',
        '재점검 단계까지 포함돼 1인 운영에서도 반복 관리 비용을 낮출 수 있습니다.',
    ]
    pack['successMetrics'] = [
        f"위기 점수 {risk.get('riskScore', 0)}점에서 얼마나 낮아졌는지",
        f"동종 업계 대비 준수율 {(risk.get('compliance') or {}).get('rate', 0)}%가 얼마나 올라갔는지",
        f"핵심 페이지 커버리지 {stats.get('priorityCoverage', 0)}%가 얼마나 올라갔는지",
        f"예상 노출 {exposure.get('display', '비정량')} 구간이 어떻게 줄었는지",
    ]
    pack['prioritySequence'] = [item.get('detail') for item in remediation_plan[:4]] or pack.get('prioritySequence', [])
    pack['expertNotes'] = [
        '무료 데모에는 요약과 상위 이슈만 노출하고, 발행본에는 전체 이슈와 맞춤 규칙을 엽니다.',
        '예상 금액은 법률 확정 판단이 아니라 공개 페이지 자동 점검 기반 노출 추정치로 관리합니다.',
        '동종 업계 대비 준수율은 업계 평균·상위 10%·하위 30% 기준으로 함께 설명합니다.',
        '탐색률과 탐지율이 낮더라도 신뢰도 등급을 따로 붙여 숫자 왜곡을 줄입니다.',
        '재점검은 같은 리포트 코드 아래에서 수정 전/후를 비교하는 방식으로 관리합니다.',
    ]
    service_bundle = report.get('serviceBundle') or build_veridion_service_bundle(report)
    bundle = [
        {'title': '위기 점수 요약본', 'description': f"리포트 코드 {report.get('code')} 기준으로 위기 점수, 고위험 건수, 예상 노출 범위를 한 장 요약으로 발행합니다.", 'customerValue': '경영진 공유와 우선순위 합의를 빠르게 끝낼 수 있습니다.', 'usageMoment': '즉시 공유', 'expertNote': '첫 장에서 숫자와 범위를 같이 보여주면 내부 의사결정 속도가 올라갑니다.', 'status': 'ready'},
        {'title': '전체 이슈·페이지별 조치서', 'description': f"전체 이슈 {len(issues)}건과 페이지별 조치 {len(page_actions)}건을 같은 구조로 묶어 전달합니다.", 'customerValue': '디자인·개발·운영이 같은 작업지시서를 보고 움직일 수 있습니다.', 'usageMoment': '실행 착수', 'expertNote': '페이지 단위 조치가 있어야 실제 수정 속도가 빨라집니다.', 'status': 'ready'},
        {'title': '맞춤 규칙·재점검 큐', 'description': f"맞춤 규칙 {len(site_rules)}종과 재점검 단계 {len(remediation_plan)}단계를 운영 기준으로 남깁니다.", 'customerValue': '한 번 수정하고 끝나는 것이 아니라 재발 방지 기준까지 확보할 수 있습니다.', 'usageMoment': '후속 점검', 'expertNote': '운영 규칙까지 남겨야 1인 운영에서도 반복 비용이 줄어듭니다.', 'status': 'ready'}
    ]
    pack['issuanceBundle'] = bundle + [{'title': item.get('title'), 'description': item.get('summary'), 'customerValue': '결제 후 실제로 열리는 납품형 서비스입니다.', 'usageMoment': '결제 완료 후 발행', 'expertNote': ', '.join(item.get('includes')[:2]), 'status': item.get('status', 'ready')} for item in service_bundle]
    pack['deliveryAssets'] = deepcopy(pack['issuanceBundle'])
    pack['postPaymentServices'] = service_bundle
    pack['valueNarrative'] = '이번 Veridion 결과는 무료 데모의 위기 점수·예상 노출 범위를 실제 발행본의 전체 이슈, 페이지별 조치, 맞춤 규칙으로 이어 붙인 구조입니다. 결제 후에는 서비스 1 전체 세부 점검 리포트, 서비스 2 사이트 맞춤형 수정안 리포트, 서비스 3 월 구독형 상시 모니터링까지 같은 코드로 연결해 바로 실행 문서와 운영 기준으로 쓰도록 설계했습니다.'
    pack['buyerDecisionReason'] = '무료 데모에서 본 숫자와 실제 발행본의 전체 이슈가 같은 코드로 이어져, 결제 직후 체감 가치와 실행성이 높습니다.'
    pack['linkedReport'] = {'id': report.get('id'), 'code': report.get('code'), 'website': website, 'explorationRate': stats.get('explorationRate'), 'priorityCoverage': stats.get('priorityCoverage'), 'riskScore': risk.get('riskScore')}
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
    risk = report.get('risk') or {}
    issues = report.get('topIssues') or report.get('issues') or []
    exposure = risk.get('estimatedExposure') or {}
    return {
        'headline': f"{company or '샘플 회사'} 기준 Veridion 실제 탐색 결과",
        'summary': report.get('summary') or '',
        'country': report.get('country') or 'KR',
        'countryLabel': report.get('countryLabel') or report.get('market') or '대한민국',
        'legalBasis': report.get('legalBasis') or [],
        'company': company or '샘플 회사',
        'goal': clean(report.get('focus')) or '준법 리스크 우선순위 정리',
        'keywords': ', '.join(report.get('options') or []),
        'diagnosisSummary': f"분석 기준 국가 {report.get('countryLabel') or report.get('market') or '대한민국'}, 위기 점수 {risk.get('riskScore', 0)}점, 고위험 {risk.get('highRiskCount', 0)}건, 유사 업종 대비 하위 {((risk.get('peerComparison') or {}).get('bottomPercent') or 0)}%, 예상 노출 {exposure.get('display', '비정량')}를 먼저 계산했습니다.",
        'sampleOutputs': [
            {'title': '위기 점수 요약', 'note': f"{risk.get('riskScore', 0)}점 · {risk.get('riskLabel', '확인')}", 'preview': risk.get('summaryLine') or report.get('summary') or '', 'whatIncluded': '고위험 건수, 전체 이슈 수, 예상 노출 범위, 신뢰도 등급을 함께 제공합니다.', 'actionNow': '무료 데모에서는 숫자와 상위 이슈를 먼저 확인하고 결제 후 전체 발행본으로 넘어갑니다.', 'buyerValue': '사이트 상태를 한 번에 설명할 숫자와 범위를 바로 확보할 수 있습니다.', 'expertLens': '탐색률과 커버리지는 따로 두고 위기 점수는 별도로 계산합니다.', 'whyItMatters': '무료 데모 단계에서 위험도를 직관적으로 느껴야 전환이 빨라집니다.', 'deliveryState': 'ready_to_issue'},
            {'title': '상위 이슈 미리보기', 'note': f"상위 {len(issues[:5])}건", 'preview': issues[0].get('detail') if issues else '상위 이슈가 많지 않은 편입니다.', 'whatIncluded': '상위 이슈 제목, 위험 수준, 영역만 먼저 보여주고 전체 목록은 발행본에서 엽니다.', 'actionNow': '결제 후 전체 이슈·페이지별 조치·맞춤 규칙을 발행합니다.', 'buyerValue': '데모에서 과도하게 다 보여주지 않으면서도 구매 판단은 충분히 돕습니다.', 'expertLens': '무료 데모는 위기감, 유료 발행본은 실행 문서에 집중합니다.', 'whyItMatters': '전환 구조가 분리돼야 데모와 유료의 역할이 명확해집니다.', 'deliveryState': 'ready_to_issue'},
            {'title': '발행본 연결', 'note': f"리포트 코드 {report.get('code')}", 'preview': '결제 후에는 전체 영역, 페이지별 조치, 맞춤 규칙, 재점검 단계까지 같은 코드로 연결됩니다.', 'whatIncluded': '전체 이슈, 법령군 요약, 페이지별 조치, 사이트 맞춤 규칙, 재점검 큐를 발행본에서 제공합니다.', 'actionNow': '샘플 결과를 본 뒤 같은 코드로 결제와 포털 전달 흐름을 이어갑니다.', 'buyerValue': '무료 데모와 유료 발행본이 끊기지 않고 같은 코드로 이어집니다.', 'expertLens': '같은 코드 체계가 있어야 데모-결제-포털-재점검의 운영 비용이 낮아집니다.', 'whyItMatters': '보고용이 아니라 납품·운영용 흐름이 연결됩니다.', 'deliveryState': 'ready_to_issue'}
        ],
        'quickWins': ['홈·푸터 정책 링크 보강', '입력/결제 직전 고지 보강', '강한 단정 표현 완화'],
        'valueDrivers': ['위기 점수와 예상 노출 범위를 먼저 보여줍니다.', '유사 업종 대비 상대 위치와 영역별 집계를 함께 보여줍니다.', '결제 후 서비스 1 전체 세부 점검, 서비스 2 맞춤 수정안, 서비스 3 월 구독형 상시 모니터링으로 이어집니다.'],
        'successMetrics': [f"위기 점수 {risk.get('riskScore', 0)}점", f"탐색률 {stats.get('explorationRate', 0)}%", f"예상 노출 {exposure.get('display', '비정량')}"],
        'prioritySequence': ['1. 무료 데모에서 숫자와 상위 이슈 확인', '2. 결제 후 전체 발행본과 맞춤 수정안 열기', '3. 월 구독형 모니터링으로 재점검 알림 이어가기'],
        'expertNotes': ['무료 데모는 상위 이슈만, 발행본은 전체 이슈를 제공합니다.', '예상 금액은 자동 추정치이며 법률 확정 판단이 아닙니다.', '같은 리포트 코드로 발행, 재점검, 월 구독형 모니터링을 연결합니다.'],
        'objectionHandling': ['무료 데모만으로도 위험도를 직관적으로 확인할 수 있습니다.', '결제 후에는 전체 영역과 맞춤 규칙이 바로 열립니다.'],
        'scorecard': {'stage': 'demo', 'stageLabel': '실제 탐색 데모', 'earned': 100 if stats.get('fetched', 0) else 68, 'total': 100, 'grade': 'A+' if stats.get('fetched', 0) else 'B', 'headline': 'Veridion 실제 탐색 품질 기준표', 'summary': '실제 페이지 읽기, 위기 점수 계산, 상위 이슈 추출, 발행 연결 준비까지 같은 흐름으로 확인합니다.', 'items': [{'label': '실제 페이지 읽기', 'score': 20 if stats.get('fetched', 0) else 8, 'max': 20, 'reason': f"실제 HTML 페이지 {stats.get('fetched', 0)}개를 읽었습니다." if stats.get('fetched', 0) else '실제 페이지를 읽지 못했습니다.'}, {'label': '탐색률 계산', 'score': 15 if stats.get('discovered', 0) else 6, 'max': 15, 'reason': f"발견 {stats.get('discovered', 0)}개 대비 탐색률 {stats.get('explorationRate', 0)}%를 계산했습니다."}, {'label': '핵심 페이지 커버리지', 'score': 15, 'max': 15, 'reason': f"핵심 페이지 커버리지 {stats.get('priorityCoverage', 0)}%를 별도로 확인했습니다."}, {'label': '위기 점수 계산', 'score': 15 if risk.get('issueCount', 0) else 8, 'max': 15, 'reason': risk.get('summaryLine') or '위기 점수 계산을 준비했습니다.'}, {'label': '상위 이슈 정리', 'score': 15, 'max': 15, 'reason': f"상위 이슈 {len(issues)}건을 먼저 정렬했습니다."}, {'label': '발행 연결 준비', 'score': 10 if report.get('issuance', {}).get('status') == 'ready' else 4, 'max': 10, 'reason': report.get('issuance', {}).get('readyReason') or '리포트 발행 준비 상태를 점검했습니다.'}, {'label': '재사용성', 'score': 10, 'max': 10, 'reason': '같은 리포트 코드로 포털·관리자·재점검 흐름을 연결할 수 있습니다.'}]},
        'ctaHint': f"리포트 코드 {report.get('code')} 기준으로 결제 후 발행 자료와 포털 결과를 같은 흐름으로 이어갑니다.",
        'closingArgument': '이번 데모는 무료 단계에서 위기감이 분명히 느껴지도록 숫자와 상위 이슈만 보여주고, 결제 후에는 서비스 1 전체 세부 점검, 서비스 2 맞춤 수정안, 서비스 3 월 구독형 상시 모니터링까지 이어지는 구조로 구성했습니다.',
        'linkedReport': {'id': report.get('id'), 'code': report.get('code')},
    }


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




def build_clearport_public_report(report: dict[str, Any]) -> dict[str, Any]:
    stats = report.get('stats') or {}
    safe_issues = []
    for item in (report.get('issues') or [])[:3]:
        safe_issues.append({
            'level': item.get('level'),
            'title': item.get('title'),
            'detail': item.get('detail'),
        })
    checklist = report.get('documentChecklist') or []
    readiness = {
        'requiredDocs': stats.get('requiredDocs', len(checklist)),
        'securedDocs': stats.get('securedDocs', len([row for row in checklist if clean(row.get('status')) == '확보'])),
        'missingDocs': stats.get('missingDocs', len([row for row in checklist if clean(row.get('status')) != '확보'])),
        'criticalMissing': stats.get('criticalMissing', 0),
    }
    highlights = [
        {'label': row.get('label'), 'status': row.get('status'), 'priority': row.get('priority')}
        for row in checklist[:4]
    ]
    issuance = deepcopy(report.get('issuance') or {})
    issuance['sections'] = ['준비도 요약', '상위 이슈', '발행 전 품질 상태']
    return {
        'id': report.get('id'),
        'code': report.get('code'),
        'product': report.get('product'),
        'company': report.get('company'),
        'submissionType': report.get('submissionType'),
        'targetOrg': report.get('targetOrg'),
        'deadline': report.get('deadline'),
        'teamSize': report.get('teamSize'),
        'summary': report.get('summary'),
        'stats': stats,
        'issues': safe_issues,
        'readinessSummary': readiness,
        'checklistHighlights': highlights,
        'issuance': issuance,
        'quality': report.get('quality') or {},
        'createdAt': report.get('createdAt'),
        'updatedAt': report.get('updatedAt'),
        'publicLocked': {
            'fullIssueCount': len(report.get('issues') or []),
            'fullChecklistCount': len(checklist),
            'fullTemplateCount': len(report.get('copySuggestions') or []),
            'message': '전체 체크리스트 행, 대외/내부 회신 템플릿, 실행 순서는 결제 후 운영본에서 제공합니다.',
        },
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
    pack['documentChecklist'] = checklist
    pack['responseTemplates'] = copies
    pack['executionPlan'] = [
        {'step': '핵심 누락 확보', 'owner': '실무 담당', 'detail': f"핵심 누락 {stats.get('criticalMissing', 0)}건부터 먼저 확보합니다."},
        {'step': '대외 회신 발송', 'owner': report.get('targetOrg') or '제출처', 'detail': '보완 가능 시점과 현재 확보 상태를 같은 문장으로 바로 회신합니다.'},
        {'step': '파일명·날인 정리', 'owner': report.get('teamSize') or '내부 운영', 'detail': '날인·정산·보안 확인서를 별도 폴더와 파일명 규칙으로 다시 잠급니다.'},
    ]
    pack['operatingRules'] = [
        '핵심 서류와 보조 서류를 분리해 관리합니다.',
        '대외 회신에는 누락 항목과 회신 시점을 함께 적습니다.',
        '마감이 짧을수록 내부 승인과 날인 경로를 먼저 잠급니다.',
    ]
    pack['qaChecklist'] = [
        {'label': '핵심 서류 확보', 'ok': stats.get('criticalMissing', 0) == 0},
        {'label': '대외 회신 문장 준비', 'ok': bool(copies)},
        {'label': '체크리스트 운영본 준비', 'ok': bool(checklist)},
    ]
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




def build_grantops_public_report(report: dict[str, Any]) -> dict[str, Any]:
    stats = report.get('stats') or {}
    safe_issues = []
    for item in (report.get('issues') or [])[:3]:
        safe_issues.append({
            'level': item.get('level'),
            'title': item.get('title'),
            'detail': item.get('detail'),
        })
    schedule = report.get('schedule') or []
    roles = report.get('rolePlan') or []
    issuance = deepcopy(report.get('issuance') or {})
    issuance['sections'] = ['준비도 요약', '상위 이슈', '핵심 경로 요약', '발행 전 품질 상태']
    return {
        'id': report.get('id'),
        'code': report.get('code'),
        'product': report.get('product'),
        'company': report.get('company'),
        'projectName': report.get('projectName'),
        'progress': report.get('progress'),
        'contributors': report.get('contributors'),
        'delayPoint': report.get('delayPoint'),
        'deadline': report.get('deadline'),
        'summary': report.get('summary'),
        'stats': stats,
        'issues': safe_issues,
        'scheduleHighlights': [
            {'label': row.get('label'), 'date': row.get('date')}
            for row in schedule[:3]
        ],
        'roleHighlights': [
            {'label': row.get('label'), 'owner': row.get('owner')}
            for row in roles[:3]
        ],
        'issuance': issuance,
        'quality': report.get('quality') or {},
        'createdAt': report.get('createdAt'),
        'updatedAt': report.get('updatedAt'),
        'publicLocked': {
            'fullIssueCount': len(report.get('issues') or []),
            'fullScheduleCount': len(schedule),
            'fullTemplateCount': len(report.get('copySuggestions') or []),
            'message': '전체 역산 일정, 역할 운영본, 요청·승인 문장 세트는 결제 후 발행본에서 제공합니다.',
        },
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
    pack['scheduleLocks'] = schedule
    pack['roleAssignments'] = roles
    pack['requestTemplates'] = copies
    pack['criticalPath'] = [row.get('label') for row in schedule]
    pack['executionPlan'] = [
        {'step': '역산 일정 잠금', 'owner': '실무 담당', 'detail': f"마감 {_fmt_due_label(stats.get('daysLeft'))} 기준으로 승인·업로드 구간부터 다시 잠급니다."},
        {'step': '병목 역할 분리', 'owner': '검토/승인 담당', 'detail': f"현재 병목 {report.get('delayPoint') or '증빙 수집'} 구간에 별도 책임자를 붙입니다."},
        {'step': '요청 문장 발송', 'owner': '대내외 커뮤니케이션', 'detail': '승인 요청, 증빙 요청, 업로드 전 확인 문장을 같은 날 안에 발송합니다.'},
    ]
    pack['operatingRules'] = [
        '승인과 업로드 구간을 가장 먼저 잠급니다.',
        '한 사람이 겹쳐 맡는 단계는 백업 담당을 지정합니다.',
        '자료명과 회신 시점을 함께 적는 요청 문장을 사용합니다.',
    ]
    pack['qaChecklist'] = [
        {'label': '역산 일정 준비', 'ok': bool(schedule)},
        {'label': '역할 분담표 준비', 'ok': bool(roles)},
        {'label': '요청 문장 준비', 'ok': bool(copies)},
    ]
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




def build_draftforge_public_report(report: dict[str, Any]) -> dict[str, Any]:
    stats = report.get('stats') or {}
    safe_issues = []
    for item in (report.get('issues') or [])[:3]:
        safe_issues.append({
            'level': item.get('level'),
            'title': item.get('title'),
            'detail': item.get('detail'),
        })
    matrix = report.get('versionMatrix') or []
    issuance = deepcopy(report.get('issuance') or {})
    issuance['sections'] = ['통제 점수 요약', '상위 이슈', '버전 규칙 요약', '발행 전 품질 상태']
    return {
        'id': report.get('id'),
        'code': report.get('code'),
        'product': report.get('product'),
        'company': report.get('company'),
        'docType': report.get('docType'),
        'versionState': report.get('versionState'),
        'approvalSteps': report.get('approvalSteps'),
        'channel': report.get('channel'),
        'summary': report.get('summary'),
        'stats': stats,
        'issues': safe_issues,
        'versionHighlights': [
            {'label': row.get('label'), 'rule': row.get('rule')}
            for row in matrix[:3]
        ],
        'issuance': issuance,
        'quality': report.get('quality') or {},
        'createdAt': report.get('createdAt'),
        'updatedAt': report.get('updatedAt'),
        'publicLocked': {
            'fullIssueCount': len(report.get('issues') or []),
            'fullVersionRuleCount': len(matrix),
            'fullTemplateCount': len(report.get('copySuggestions') or []),
            'message': '전체 버전 규칙표, 승인 운영본, 검토·발송 문장 세트는 결제 후 발행본에서 제공합니다.',
        },
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
    pack['versionRules'] = matrix
    pack['copyTemplates'] = copies
    pack['approvalFlow'] = {
        'approvalSteps': report.get('approvalSteps'),
        'channel': report.get('channel'),
        'handoffRisk': stats.get('handoffRisk'),
    }
    pack['releaseChecklist'] = [
        {'label': '작업본/검토본/배포본 분리', 'ok': bool(matrix)},
        {'label': '검토·발송 문장 준비', 'ok': bool(copies)},
        {'label': '최종본 final 단일화', 'ok': True},
    ]
    pack['executionPlan'] = [
        {'step': '버전 규칙 통일', 'owner': '문서 실무', 'detail': '작업본, 검토본, 승인본, 배포본 파일명을 같은 규칙으로 다시 맞춥니다.'},
        {'step': '승인 흐름 분리', 'owner': '검토/승인 담당', 'detail': '검토용과 배포용 문서를 섞지 않도록 승인 단계별 분기 지점을 고정합니다.'},
        {'step': '최종 발송 전 QA', 'owner': '배포 담당', 'detail': '최종본은 final 1개만 남기고 첨부파일명, 수치, 링크를 마지막으로 교차검토합니다.'},
    ]
    pack['operatingRules'] = [
        '최종 배포본은 final 한 개만 남깁니다.',
        '검토 요청 문장에는 범위와 기한을 함께 적습니다.',
        '검토본과 배포본은 이름부터 다르게 관리합니다.',
    ]
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
            "description": "제품 설명, 공개 자료실, 고객 포털에서 같은 조회 코드로 이어서 확인할 수 있는 자동 발행 콘텐츠입니다.",
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
    payload = payload or {}
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
        pack = attach_veridion_report_to_pack(pack, product_key, company, note, payload)
        addons = {clean(item) for item in (payload.get("addons") or []) if clean(item)}
        if "precision_copy" in addons:
            linked = pack.get("linkedReport") or {}
            website = linked.get("website") or clean(payload.get("link")) or clean(payload.get("website")) or "대표 사이트"
            pack["precisionAddOn"] = {
                "enabled": True,
                "title": "정밀 지침·문구 작성 리포트",
                "summary": f"{company or '고객사'} 사이트 {website}에 맞춘 문구와 운영 지침을 추가 발행했습니다.",
                "items": [
                    {"title": "개인정보 수집·이용 고지", "copy": "수집 항목, 이용 목적, 보관 기간, 문의처를 입력 직전 영역에 요약 고지하고 상세 내용은 개인정보처리방침에서 확인할 수 있도록 연결합니다.", "reason": "폼 전환 직전 구간의 설명 부족으로 인한 리스크를 줄입니다."},
                    {"title": "환불·청약철회 요약 문구", "copy": "결제 전 확인해주세요. 제공 범위, 청약철회 가능 기간, 환불 제외 사유, 고객센터 채널을 이 화면에서 바로 안내합니다.", "reason": "결제형 서비스에서 가장 빈번한 고지 누락을 먼저 막습니다."},
                    {"title": "광고·표현 완화 가이드", "copy": "효과를 단정하기보다 적용 조건, 개인차 가능성, 기준 범위를 함께 적어 해석상 오인을 줄입니다.", "reason": "성과·효능형 카피의 과장 해석 가능성을 낮춥니다."},
                ],
                "delivery": [
                    "페이지별 문구 초안",
                    "고지 배치 위치 제안",
                    "반복 운영용 준수 문장 템플릿",
                ],
            }
            pack.setdefault("issuanceBundle", []).append({"title": "정밀 지침·문구 작성 리포트", "description": f"{website} 기준 맞춤 문구와 운영 지침을 추가 발행합니다.", "customerValue": "복붙 가능한 문구와 배치 기준까지 확보할 수 있습니다.", "usageMoment": "추가 결제 직후", "expertNote": "법률 자문 대체가 아니라 실무 적용 초안을 빠르게 여는 구조입니다.", "status": "ready"})
            pack.setdefault("deliveryAssets", []).append({"title": "정밀 문구 팩", "description": "페이지별 안내문, 배너, 동의 문구 초안", "format": "html+json", "status": "ready"})
        monitoring_requested = clean(payload.get('billing')) == 'monthly' or clean(payload.get('plan')) == 'Monitor'
        if monitoring_requested:
            linked_report = resolve_veridion_report(note, payload) or find_veridion_report(report_id=clean(payload.get('reportId')), report_code=clean(payload.get('reportCode')))
            monitoring = (linked_report or {}).get('monitoring') if linked_report else None
            if not monitoring:
                monitoring = build_veridion_monitoring_snapshot(linked_report or {'country': clean(payload.get('country') or 'KR'), 'countryLabel': clean(payload.get('country') or '대한민국'), 'risk': {}, 'pageActions': [], 'createdAt': now_iso(), 'updatedAt': now_iso()})
            pack['monitoringSubscription'] = {
                'enabled': True,
                'summary': monitoring.get('summary'),
                'cadenceLabel': monitoring.get('cadenceLabel'),
                'nextCheckAt': monitoring.get('nextCheckAt'),
                'watchSources': monitoring.get('watchSources') or [],
                'impactQueue': monitoring.get('impactQueue') or [],
                'alerts': monitoring.get('alerts') or [],
                'changeSignals': monitoring.get('changeSignals') or [],
                'notificationChannels': monitoring.get('notificationChannels') or [],
                'disclaimer': monitoring.get('disclaimer'),
            }
            pack.setdefault('issuanceBundle', []).append({'title': '월 구독형 상시 모니터링', 'description': monitoring.get('summary') or '법령 변경 감시와 재점검 알림을 월 구독형으로 운영합니다.', 'customerValue': '법령이 바뀔 때마다 손으로 다시 찾지 않아도 됩니다.', 'usageMoment': '월 구독 시작 직후', 'expertNote': '영향 페이지 큐와 알림 이력을 함께 남겨 반복 운영 비용을 낮춥니다.', 'status': 'ready'})
            pack.setdefault('deliveryAssets', []).append({'title': '법령 변경 알림 세트', 'description': '알림 기준표, 영향 페이지 큐, 월간 스냅샷', 'format': 'json+html', 'status': 'ready'})
            pack.setdefault('nextActions', []).append('월 구독형 모니터링 알림 수신과 재점검 주기 확인')
        return pack
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
    proof = f"조회 코드 {order_code}로 정상작동 상태와 자료실 발행 글을 함께 확인할 수 있습니다." if order_code else "무료 샘플과 데모 시연 자료부터 확인한 뒤 결제 여부를 결정하실 수 있습니다."
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
            summary = f"{target.get('summary', '')} 조회 코드 {order['code']} 기준으로 함께 확인할 수 있는 자료실 안내 글입니다."
        pub = build_publication_payload(
            product_key=order["product"],
            title=pub_title,
            summary=summary,
            source="order-automation",
            code=order["code"],
            cta_label=publication_cta_defaults(order["product"])[0],
            cta_href=publication_cta_defaults(order["product"])[1],
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
            cta_label=publication_cta_defaults(item["product"])[0],
            cta_href=publication_cta_defaults(item["product"])[1],
            topic_summary=item["summary"],
            publication_id=f"pubseed-{idx + 1}",
        )
        upsert_record("publications", pub)




def scheduled_product_keys(settings: dict[str, Any]) -> list[str]:
    selected = [item for item in (settings.get("selectedProducts") or []) if item in PRODUCTS]
    if selected:
        return selected
    if bool(settings.get("autoPublishAllProducts")):
        return list(PRODUCTS.keys())
    return [key for key, item in PRODUCTS.items() if (item.get("board_automation") or {}).get("enabled")] or list(PRODUCTS.keys())


def scheduler_window_key(now: datetime, settings: dict[str, Any]) -> str:
    schedule_type = clean(settings.get("scheduleType") or "daily")
    if schedule_type == "weekly":
        iso_year, iso_week, _ = now.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    if schedule_type == "interval":
        hours = max(1, int(settings.get("intervalHours") or 24))
        bucket = int(now.timestamp()) // (hours * 3600)
        return f"interval-{hours}-{bucket}"
    return now.strftime("%Y-%m-%d")


def scheduler_allowed_runs(now: datetime, settings: dict[str, Any]) -> int:
    frequency = max(1, int(settings.get("frequencyPerRun") or 1))
    if clean(settings.get("scheduleType") or "daily") == "interval":
        return frequency
    slots = parse_time_slots(settings.get("timeSlots"))
    if not slots:
        return frequency
    current = now.strftime("%H:%M")
    passed = sum(1 for item in slots if item <= current)
    return min(frequency, passed)

def ensure_scheduled_publications() -> None:
    global _LAST_SCHEDULED_CHECK_MONOTONIC
    now_monotonic = time.monotonic()
    if now_monotonic - _LAST_SCHEDULED_CHECK_MONOTONIC < SCHEDULE_CHECK_MIN_INTERVAL_SECONDS:
        return
    with _SCHEDULE_LOCK:
        now_monotonic = time.monotonic()
        if now_monotonic - _LAST_SCHEDULED_CHECK_MONOTONIC < SCHEDULE_CHECK_MIN_INTERVAL_SECONDS:
            return
        _LAST_SCHEDULED_CHECK_MONOTONIC = now_monotonic
        ensure_seed_publications()
        settings = get_board_settings()
        if not bool(settings.get("autoPublishEnabled", True)):
            return
        targets = scheduled_product_keys(settings)
        if not targets:
            return
        now = datetime.now(timezone.utc).astimezone()
        state = get_record("scheduler", "auto-publish-state") or {"id": "auto-publish-state", "windowKey": "", "windowCount": 0, "roundRobinIndex": 0, "lastRunAt": "", "createdAt": now_iso()}
        window_key = scheduler_window_key(now, settings)
        if clean(state.get("windowKey")) != window_key:
            state["windowKey"] = window_key
            state["windowCount"] = 0
        allowed_runs = scheduler_allowed_runs(now, settings)
        due_runs = max(0, allowed_runs - int(state.get("windowCount") or 0))
        if due_runs <= 0:
            upsert_record("scheduler", state)
            return
        for _ in range(due_runs):
            target = targets[int(state.get("roundRobinIndex") or 0) % len(targets)]
            create_board_publication(target, source='scheduled')
            state["roundRobinIndex"] = (int(state.get("roundRobinIndex") or 0) + 1) % len(targets)
            state["windowCount"] = int(state.get("windowCount") or 0) + 1
            state["lastRunAt"] = now_iso()
        state["updatedAt"] = now_iso()
        upsert_record("scheduler", state)


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
        order["resultPack"] = enrich_result_pack(build_result_pack(order["product"], order["plan"], order.get("company", ""), order.get("note", ""), order), order)
        return order
    pubs = create_publications_for_order(order)
    order["publicationIds"] = [item["id"] for item in pubs]
    order["publicationCount"] = len(order["publicationIds"])
    order["resultPack"] = enrich_result_pack(build_result_pack(order["product"], order["plan"], order.get("company", ""), order.get("note", ""), order), order)
    return order


def finalize_paid_order(order: dict[str, Any]) -> dict[str, Any]:
    order["paymentStatus"] = "paid"
    if order_requires_intake(order) or (intake_url_required(order) and not clip_text(order.get("link"), 500)):
        order["status"] = "intake_required"
        order["resultPack"] = None
        return order
    order["status"] = "delivered"
    account, created_access = ensure_account_for_order(order, clean(order.get("portalPassword")))
    order["portalAccount"] = {"email": account.get("email"), "accountId": account.get("id")}
    if created_access:
        order["portalAccess"] = created_access
    order["resultPack"] = build_result_pack(order["product"], order["plan"], order.get("company", ""), order.get("note", ""), order)
    order = ensure_publications_for_order(order)
    order["resultPack"] = enrich_result_pack(order.get("resultPack") or {}, order)
    delivery_meta = deepcopy(order.get("deliveryMeta") or {})
    delivery_meta.setdefault("automation", "full_auto")
    delivery_meta.setdefault("deliveredAt", now_iso())
    delivery_meta["publicationCount"] = len(order.get("publicationIds") or [])
    delivery_meta['resultHash'] = clean((order.get('resultPack') or {}).get('resultPackDigest'))
    delivery_meta['qualityPassed'] = bool(((order.get('resultPack') or {}).get('qualityValidation') or {}).get('passed'))
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
    fingerprint = payload_digest('demo', {
        'product': product,
        'company': company,
        'name': name,
        'email': email,
        'team': clip_text(payload.get('team'), 120),
        'need': clip_text(payload.get('need'), 500),
        'keywords': clip_text(payload.get('keywords'), 240),
        'plan': clip_text(payload.get('plan'), 80),
        'reportId': clean(payload.get('reportId')),
        'reportCode': normalize_code(payload.get('reportCode')),
    })
    if not (payload.get("id") and payload.get("code")):
        existing = find_recent_record_by_fingerprint('demos', fingerprint)
        if existing:
            return existing
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
    entry['fingerprint'] = fingerprint
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
    fingerprint = payload_digest('contact', {'product': product, 'company': company, 'name': name, 'email': email, 'issue': issue})
    if not (payload.get("id") and payload.get("code")):
        existing = find_recent_record_by_fingerprint('contacts', fingerprint)
        if existing:
            return existing
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
    entry['fingerprint'] = fingerprint
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
    allowed_billing = {'one-time'}
    if product == 'veridion' and plan == 'Monitor':
        allowed_billing.add('monthly')
    if billing not in allowed_billing:
        raise HTTPException(status_code=400, detail='현재 선택한 플랜에서 지원하지 않는 결제 방식입니다.')
    plan_meta = plan_info(product, plan)
    status = payment_status or ("paid" if method == "toss" and not NV0_TOSS_CLIENT_KEY and not NV0_TOSS_SECRET_KEY else "pending")
    order_id = clean(payload.get("id")) or uid("ord")
    order_code = normalize_code(payload.get("code")) or make_public_code("NV0", product)
    addons = [clean(item) for item in (payload.get("addons") or []) if clean(item)]
    addon_amount = 290000 if "precision_copy" in addons else 0
    amount_total = plan_meta["amount"] + addon_amount
    price_display = plan_meta["display"] + (" + 정밀 작성 29만" if addon_amount else "")
    link = clip_text(payload.get("link") or payload.get("website"), 500)
    ready_for_delivery = bool(company and name and validate_email(email) and (not intake_url_required({"product": product}) or link))
    return {
        "id": order_id,
        "code": order_code,
        "product": product,
        "productName": product_name(product),
        "plan": plan,
        "price": price_display,
        "amount": amount_total,
        "planNote": plan_meta["note"],
        "addons": addons,
        "portalPassword": clean(payload.get("portalPassword")),
        "portalPasswordConfigured": bool(clean(payload.get("portalPassword"))),
        "billing": billing,
        "subscriptionActive": bool(product == 'veridion' and billing == 'monthly'),
        "paymentMethod": method,
        "paymentStatus": status,
        "status": "delivered" if status == "paid" and ready_for_delivery else ("intake_required" if status == "paid" else next_status_for_payment(status)),
        "company": company,
        "name": name,
        "email": email,
        "link": link,
        "note": clip_text(payload.get("note"), 1000),
        "reportId": clean(payload.get("reportId")),
        "reportCode": normalize_code(payload.get("reportCode")),
        "resultPack": build_result_pack(product, plan, company or "결제 고객", clip_text(payload.get("note"), 1000), payload) if status == "paid" and ready_for_delivery else None,
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
        order = finalize_paid_order_or_require_intake(order)
    return upsert_record("orders", order)


def reserve_toss_order(payload: dict[str, Any]) -> dict[str, Any]:
    if NV0_PAYMENT_PROVIDER != 'toss':
        raise HTTPException(status_code=503, detail='현재 Toss 결제가 비활성화되어 있습니다.')
    effective_mock = NV0_TOSS_MOCK or (IS_LOCAL_BASE and (not NV0_TOSS_CLIENT_KEY or not NV0_TOSS_SECRET_KEY))
    if not effective_mock and (not NV0_TOSS_CLIENT_KEY or not NV0_TOSS_SECRET_KEY):
        raise HTTPException(status_code=503, detail='결제 설정이 아직 완료되지 않았습니다. 운영자에게 Toss 키 설정을 확인해 달라고 요청해 주세요.')
    reserve_fingerprint = payload_digest('reserve-order', {
        'product': clean(payload.get('product')),
        'plan': clean(payload.get('plan') or 'Starter'),
        'company': clip_text(payload.get('company'), 160),
        'name': clip_text(payload.get('name'), 120),
        'email': normalize_email(payload.get('email')),
        'link': clip_text(payload.get('link') or payload.get('website'), 500),
        'note': clip_text(payload.get('note'), 1000),
        'reportId': clean(payload.get('reportId')),
        'reportCode': normalize_code(payload.get('reportCode')),
        'billing': clean(payload.get('billing') or 'one-time'),
        'paymentMethod': 'toss',
    })
    existing = find_recent_record_by_fingerprint('orders', reserve_fingerprint, allowed_statuses={'ready', 'pending'})
    if existing:
        return existing
    order = base_order_entry(payload, payment_method="toss", payment_status="ready")
    order['fingerprint'] = reserve_fingerprint
    order['paymentMode'] = 'mock' if effective_mock else 'live'
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


def hash_secret(value: str) -> str:
    return hashlib.sha256(clean(value).encode("utf-8")).hexdigest()


def account_record_for_email(email: str) -> dict[str, Any] | None:
    wanted = normalize_email(email)
    if not wanted:
        return None
    for account in load_records("accounts"):
        if normalize_email(account.get("email")) == wanted:
            return account
    return None


def safe_account_payload(account: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": account.get("id"),
        "email": account.get("email"),
        "name": account.get("name"),
        "company": account.get("company"),
        "createdAt": account.get("createdAt"),
        "updatedAt": account.get("updatedAt"),
        "lastLoginAt": account.get("lastLoginAt", ""),
    }


def orders_for_email(email: str) -> list[dict[str, Any]]:
    wanted = normalize_email(email)
    if not wanted:
        return []
    orders = [deepcopy(order) for order in load_records("orders") if normalize_email(order.get("email")) == wanted]
    return sorted(orders, key=lambda item: (clean(item.get("createdAt")), clean(item.get("id"))), reverse=True)


def ensure_account_for_order(order: dict[str, Any], password: str = "") -> tuple[dict[str, Any], dict[str, Any] | None]:
    email = normalize_email(order.get("email"))
    if not validate_email(email):
        raise HTTPException(status_code=400, detail="포털 계정 생성에 필요한 이메일이 올바르지 않습니다.")
    existing = account_record_for_email(email)
    created_access = None
    if existing:
        changed = False
        if password and hash_secret(password) != clean(existing.get("passwordHash")):
            existing["passwordHash"] = hash_secret(password)
            existing["updatedAt"] = now_iso()
            changed = True
        existing["company"] = clip_text(order.get("company"), 160) or existing.get("company") or ""
        existing["name"] = clip_text(order.get("name"), 120) or existing.get("name") or ""
        existing.setdefault("source", "order")
        if changed:
            existing = upsert_record("accounts", existing)
        return existing, created_access
    temp_password = password or f"vrd-{secrets.token_hex(4)}"
    account = {
        "id": uid("acc"),
        "email": email,
        "name": clip_text(order.get("name"), 120),
        "company": clip_text(order.get("company"), 160),
        "passwordHash": hash_secret(temp_password),
        "source": "order",
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
        "lastLoginAt": "",
    }
    account = upsert_record("accounts", account)
    created_access = {
        "email": email,
        "temporaryPassword": temp_password,
        "mustRotate": not bool(password),
        "loginHint": "이메일과 비밀번호로 포털에 로그인해 지난 발행 이력을 볼 수 있습니다.",
    }
    return account, created_access


def create_session_for_account(account: dict[str, Any]) -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    session = {
        "id": uid("ses"),
        "token": token,
        "accountId": account.get("id"),
        "email": normalize_email(account.get("email")),
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
        "expiresAt": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "status": "active",
    }
    return upsert_record("sessions", session)


def session_record_from_token(token: str) -> dict[str, Any] | None:
    wanted = clean(token)
    if not wanted:
        return None
    now_dt = datetime.now(timezone.utc)
    for item in load_records("sessions"):
        if clean(item.get("token")) != wanted or clean(item.get("status")) != "active":
            continue
        expires = parse_iso(item.get("expiresAt"))
        if expires and expires < now_dt:
            item["status"] = "expired"
            item["updatedAt"] = now_iso()
            upsert_record("sessions", item)
            continue
        return item
    return None


def require_session(authorization: str | None = Header(default=None), x_session_token: str | None = Header(default=None)) -> dict[str, Any]:
    token = clean(x_session_token)
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = clean(authorization.split(" ", 1)[1])
    session = session_record_from_token(token)
    if not session:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    account = account_record_for_email(session.get("email"))
    if not account:
        raise HTTPException(status_code=401, detail="계정을 찾지 못했습니다.")
    return {"session": session, "account": account}



def register_portal_account(payload: dict[str, Any]) -> dict[str, Any]:
    email = normalize_email(payload.get("email"))
    password = clean(payload.get("password"))
    name = clip_text(payload.get("name"), 120)
    company = clip_text(payload.get("company"), 160)
    if not validate_email(email) or len(password) < 4 or not name:
        raise HTTPException(status_code=400, detail="이름, 이메일, 비밀번호를 확인해 주세요.")
    if account_record_for_email(email):
        raise HTTPException(status_code=409, detail="이미 가입된 이메일입니다. 로그인해 주세요.")
    account = {
        "id": uid("acc"),
        "email": email,
        "name": name,
        "company": company,
        "passwordHash": hash_secret(password),
        "source": "signup",
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
        "lastLoginAt": now_iso(),
    }
    account = upsert_record("accounts", account)
    session = create_session_for_account(account)
    return {
        "token": session.get("token"),
        "session": {"id": session.get("id"), "expiresAt": session.get("expiresAt")},
        "account": safe_account_payload(account),
        "orders": orders_for_email(email),
    }

def login_portal(payload: dict[str, Any]) -> dict[str, Any]:
    email = normalize_email(payload.get("email"))
    password = clean(payload.get("password"))
    if not validate_email(email) or not password:
        raise HTTPException(status_code=400, detail="이메일과 비밀번호를 입력해 주세요.")
    account = account_record_for_email(email)
    if not account or clean(account.get("passwordHash")) != hash_secret(password):
        raise HTTPException(status_code=401, detail="로그인 정보가 일치하지 않습니다.")
    account["lastLoginAt"] = now_iso()
    account["updatedAt"] = now_iso()
    account = upsert_record("accounts", account)
    session = create_session_for_account(account)
    return {
        "token": session.get("token"),
        "session": {"id": session.get("id"), "expiresAt": session.get("expiresAt")},
        "account": safe_account_payload(account),
        "orders": orders_for_email(email),
    }


def logout_portal(token: str) -> None:
    session = session_record_from_token(token)
    if not session:
        return
    session["status"] = "logged_out"
    session["updatedAt"] = now_iso()
    upsert_record("sessions", session)


def update_order(order_id: str, updater) -> dict[str, Any]:
    order = get_record("orders", order_id)
    if not order:
        raise HTTPException(status_code=404, detail="결제 기록을 찾지 못했습니다.")
    updated = updater(deepcopy(order))
    updated["updatedAt"] = now_iso()
    return upsert_record("orders", updated)



def admin_cookie_secure() -> bool:
    return CANONICAL_SCHEME == "https" or NV0_BASE_URL.startswith("https://")


def request_prefers_secure_cookie(request: Request | None) -> bool:
    if request is None:
        return admin_cookie_secure()
    forwarded_proto = clean(request.headers.get("x-forwarded-proto")).lower()
    if forwarded_proto:
        return forwarded_proto.split(",", 1)[0].strip() == "https"
    try:
        return request.url.scheme == "https"
    except Exception:
        return admin_cookie_secure()


def admin_cookie_samesite() -> str:
    return "lax"


def build_admin_login_page(message: str = "") -> str:
    status_html = f"<p class='status'>{escape(message)}</p>" if message else "<p class='status'>관리자 인증 후에만 운영 메뉴와 설정 화면이 열립니다.</p>"
    return f"""<!doctype html>
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <meta name=\"robots\" content=\"noindex,nofollow\">
  <title>NV0 관리자 로그인</title>
  <style>
    :root {{ color-scheme: light; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; min-height:100vh; display:grid; place-items:center; padding:24px; font-family: Inter, Pretendard, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:radial-gradient(circle at top left, rgba(96,165,250,.28) 0, rgba(96,165,250,0) 28%), linear-gradient(180deg,#fbfdff 0%,#eef4fb 100%); color:#0b1220; }}
    .shell {{ width:100%; max-width:500px; background:rgba(255,255,255,.92); border:1px solid rgba(255,255,255,.92); border-radius:28px; box-shadow:0 30px 80px rgba(15,23,42,.16); padding:30px; backdrop-filter:blur(16px); }}
    .eyebrow {{ display:inline-flex; padding:7px 11px; border-radius:999px; background:#eff6ff; color:#1d4ed8; font-size:12px; font-weight:800; letter-spacing:.04em; text-transform:uppercase; box-shadow:0 8px 20px rgba(37,99,235,.08); }}
    h1 {{ margin:14px 0 10px; font-size:31px; line-height:1.15; letter-spacing:-.03em; }}
    p {{ margin:0 0 10px; color:#425466; line-height:1.68; }}
    form {{ display:grid; gap:14px; margin-top:18px; }}
    label {{ display:grid; gap:8px; font-weight:700; font-size:14px; color:#0b1220; }}
    input {{ width:100%; border:1px solid #d6dfeb; border-radius:16px; padding:15px 16px; font:inherit; background:#fff; box-shadow:inset 0 1px 0 rgba(255,255,255,.8); }}
    input:focus {{ outline:none; border-color:#2563eb; box-shadow:0 0 0 4px rgba(37,99,235,.12); }}
    button {{ border:0; border-radius:16px; padding:14px 16px; background:linear-gradient(135deg,#0f172a 0,#1d4ed8 70%,#60a5fa 100%); color:#fff; font:inherit; font-weight:800; cursor:pointer; box-shadow:0 18px 36px rgba(37,99,235,.18); }}
    button.secondary {{ background:#eef2f7; color:#0f172a; box-shadow:none; }}
    .actions {{ display:grid; gap:10px; }}
    .status {{ margin-top:12px; padding:13px 15px; border-radius:16px; background:#f8fbff; border:1px solid #dbeafe; color:#334155; }}
    .meta {{ margin-top:16px; font-size:13px; color:#64748b; }}
  </style>
</head>
<body class=\"admin\" data-page=\"admin\">
  <main class=\"shell\">
    <span class=\"eyebrow\">Admin protected</span>
    <h1>NV0 관리자 로그인</h1>
    <p>관리자 페이지 HTML, 메뉴, 설정값은 인증 완료 후에만 내려갑니다.</p>
    {status_html}
    <form method=\"post\" action=\"/admin/login\">
      <label>관리자 키
        <input type=\"password\" name=\"token\" autocomplete=\"current-password\" placeholder=\"관리자 키 입력\" required>
      </label>
      <input type=\"hidden\" name=\"next\" value=\"/admin/index.html\">
      <div class=\"actions\">
        <button type=\"submit\">관리자 로그인</button>
        <button type=\"button\" class=\"secondary\" onclick=\"window.location.href='/'\">홈으로 이동</button>
      </div>
    </form>
    <div class=\"meta\">로그인 성공 시 HttpOnly 보안 쿠키가 발급되며, API와 관리자 HTML은 같은 세션으로 보호됩니다.</div>
  </main>
</body>
</html>"""


def make_admin_session_cookie_value(expires_at: int) -> str:
    payload = f"{expires_at}"
    signature = hmac.new(NV0_ADMIN_TOKEN.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def parse_admin_session_cookie(token: str) -> bool:
    raw = clean(token)
    if not raw or "." not in raw or not NV0_ADMIN_TOKEN:
        return False
    payload, signature = raw.rsplit(".", 1)
    expected = hmac.new(NV0_ADMIN_TOKEN.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not secrets.compare_digest(signature, expected):
        return False
    if not payload.isdigit():
        return False
    return int(payload) >= int(time.time())


def request_has_admin_session(request: Request | None) -> bool:
    if request is None:
        return False
    return parse_admin_session_cookie(request.cookies.get(NV0_ADMIN_COOKIE_NAME, ""))


def request_has_admin_header(request: Request | None) -> bool:
    if request is None:
        return False
    token = clean(request.headers.get("x-admin-token"))
    authorization = clean(request.headers.get("authorization"))
    if not token and authorization.lower().startswith("bearer "):
        token = clean(authorization.split(" ", 1)[1])
    if not token or not NV0_ADMIN_TOKEN:
        return False
    return secrets.compare_digest(token, NV0_ADMIN_TOKEN)


def request_is_admin_authenticated(request: Request | None) -> bool:
    return request_has_admin_session(request) or request_has_admin_header(request)


def set_admin_session_cookie(response: Response, request: Request | None = None) -> int:
    expires_at = int(time.time()) + ADMIN_SESSION_TTL_SECONDS
    response.set_cookie(
        key=NV0_ADMIN_COOKIE_NAME,
        value=make_admin_session_cookie_value(expires_at),
        max_age=ADMIN_SESSION_TTL_SECONDS,
        expires=expires_at,
        path="/",
        secure=request_prefers_secure_cookie(request),
        httponly=True,
        samesite=admin_cookie_samesite(),
    )
    return expires_at


def clear_admin_session_cookie(response: Response, request: Request | None = None) -> None:
    response.delete_cookie(
        key=NV0_ADMIN_COOKIE_NAME,
        path="/",
        secure=request_prefers_secure_cookie(request),
        httponly=True,
        samesite=admin_cookie_samesite(),
    )

def require_admin(
    request: Request,
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    if request_is_admin_authenticated(request):
        return
    if not NV0_ADMIN_TOKEN and not REQUIRE_ADMIN_TOKEN:
        return
    token = clean(x_admin_token)
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = clean(authorization.split(" ", 1)[1])
    if not token or not secrets.compare_digest(token, NV0_ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="관리자 인증이 필요합니다.")


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
    toss_mock_effective = False if BOARD_ONLY_MODE else (NV0_TOSS_MOCK or (IS_LOCAL_BASE and not toss_enabled))
    return {
        "brand": SITE_DATA.get("brand", {}),
        "payment": {
            "provider": "disabled" if BOARD_ONLY_MODE else NV0_PAYMENT_PROVIDER,
            "toss": {
                "enabled": toss_enabled,
                "clientKey": "" if BOARD_ONLY_MODE else NV0_TOSS_CLIENT_KEY,
                "mock": toss_mock_effective,
                "successUrl": "" if BOARD_ONLY_MODE else f"{NV0_BASE_URL}{SUCCESS_PATH}",
                "failUrl": "" if BOARD_ONLY_MODE else f"{NV0_BASE_URL}{FAIL_PATH}",
            },
        },
        "admin": {"protected": bool(NV0_ADMIN_TOKEN), "required": REQUIRE_ADMIN_TOKEN, "manualActionsEnabled": NV0_ENABLE_MANUAL_ADMIN_ACTIONS, "cookieName": NV0_ADMIN_COOKIE_NAME, "sessionTtlSeconds": ADMIN_SESSION_TTL_SECONDS},
        "backup": {"enabled": True, "encrypted": bool(os.getenv("NV0_BACKUP_PASSPHRASE", ""))},
        "boardAutomation": {
            "enabledProducts": [key for key, item in PRODUCTS.items() if (item.get("board_automation") or {}).get("enabled")],
        },
        "integration": {"system_config_endpoint": "/api/public/system-config", "demo_endpoint": "/api/public/demo-requests", "contact_endpoint": "/api/public/contact-requests", "portal_lookup_endpoint": "/api/public/portal/lookup", "order_endpoint": "/api/public/orders", "reserve_order_endpoint": "/api/public/orders/reserve", "toss_confirm_endpoint": "/api/public/payments/toss/confirm", "board_feed_endpoint": "/api/public/board/feed", "admin_validate_endpoint": "/api/admin/validate", "admin_state_endpoint": "/api/admin/state", "admin_login_endpoint": "/api/admin/login", "admin_logout_endpoint": "/api/admin/logout", "admin_session_endpoint": "/api/admin/session", "veridion_scan_endpoint": "/api/public/veridion/scan", "clearport_analyze_endpoint": "/api/public/clearport/analyze", "grantops_analyze_endpoint": "/api/public/grantops/analyze", "draftforge_analyze_endpoint": "/api/public/draftforge/analyze"},
        "boardOnly": BOARD_ONLY_MODE,
        "disabledFeatures": ["orders", "payments", "demo", "contact", "portal", "pricing", "docs", "cases", "faq"] if BOARD_ONLY_MODE else [],
    }


def board_settings_defaults() -> dict[str, Any]:
    return {
        "id": "board-settings",
        "ctaLabel": "제품 설명 보기",
        "ctaHref": "/products/veridion/index.html#intro",
        "autoPublishAllProducts": True,
        "autoPublishEnabled": True,
        "scheduleType": "daily",
        "frequencyPerRun": 1,
        "timeSlots": ["09:00"],
        "intervalHours": 24,
        "selectedProducts": [],
        "publishMode": "publish",
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }


def get_board_settings() -> dict[str, Any]:
    current = get_record("settings", "board-settings") or get_record("scheduler", "board-settings") or {}
    defaults = board_settings_defaults()
    merged = {**defaults, **current}
    merged.setdefault("id", "board-settings")
    merged["timeSlots"] = parse_time_slots(merged.get("timeSlots"))
    merged["selectedProducts"] = [item for item in (merged.get("selectedProducts") or []) if item in PRODUCTS]
    return merged


def parse_time_slots(raw: Any) -> list[str]:
    if isinstance(raw, list):
        candidates = raw
    else:
        candidates = str(raw or "").split(",")
    result: list[str] = []
    for item in candidates:
        value = clean(item)
        if not value:
            continue
        if re.fullmatch(r"(?:[01]?\d|2[0-3]):[0-5]\d", value):
            result.append(value.zfill(5))
    return sorted(set(result))


def parse_selected_products(raw: Any) -> list[str]:
    if isinstance(raw, list):
        values = [clean(item) for item in raw]
    else:
        values = [clean(item) for item in str(raw or "").split(",")]
    return [item for item in values if item in PRODUCTS]


def save_board_settings(payload: dict[str, Any]) -> dict[str, Any]:
    current = get_board_settings()
    current["ctaLabel"] = clip_text(payload.get("ctaLabel"), 120) or current.get("ctaLabel") or "제품 설명 보기"
    current["ctaHref"] = clip_text(payload.get("ctaHref"), 300) or current.get("ctaHref") or "/products/veridion/index.html#intro"
    current["autoPublishAllProducts"] = bool(payload.get("autoPublishAllProducts"))
    current["autoPublishEnabled"] = bool(payload.get("autoPublishEnabled", True))
    schedule_type = clean(payload.get("scheduleType") or current.get("scheduleType") or "daily").lower()
    current["scheduleType"] = schedule_type if schedule_type in {"daily", "weekly", "interval"} else "daily"
    current["frequencyPerRun"] = max(1, min(24, int(payload.get("frequencyPerRun") or current.get("frequencyPerRun") or 1)))
    current["intervalHours"] = max(1, min(168, int(payload.get("intervalHours") or current.get("intervalHours") or 24)))
    current["timeSlots"] = parse_time_slots(payload.get("timeSlots") or current.get("timeSlots") or ["09:00"]) or ["09:00"]
    current["selectedProducts"] = parse_selected_products(payload.get("selectedProducts") or current.get("selectedProducts") or [])
    current["publishMode"] = "publish" if clean(payload.get("publishMode") or current.get("publishMode") or "publish") != "draft" else "draft"
    current["updatedAt"] = now_iso()
    current.setdefault("createdAt", now_iso())
    return upsert_record("settings", current)


def effective_cta(product_key: str, *, fallback_label: str = "제품 설명 보기", fallback_href: str = "") -> tuple[str, str]:
    settings = get_board_settings()
    auto_all = bool(settings.get("autoPublishAllProducts"))
    target = PRODUCTS.get(product_key) or {}
    automation = target.get("board_automation") or {}
    default_href = fallback_href or f"/products/{product_key}/index.html#intro"
    if auto_all:
        return (
            clip_text(settings.get("ctaLabel"), 120) or fallback_label or automation.get("cta_label") or "제품 설명 보기",
            clip_text(settings.get("ctaHref"), 300) or default_href or automation.get("cta_href") or f"/products/{product_key}/index.html#intro",
        )
    return (
        fallback_label or automation.get("cta_label") or clip_text(settings.get("ctaLabel"), 120) or "제품 설명 보기",
        fallback_href or automation.get("cta_href") or clip_text(settings.get("ctaHref"), 300) or f"/products/{product_key}/index.html#intro",
    )


def order_requires_intake(order: dict[str, Any]) -> bool:
    return not bool(clip_text(order.get("company"), 160) and clip_text(order.get("name"), 120) and validate_email(normalize_email(order.get("email"))))


def intake_url_required(order: dict[str, Any]) -> bool:
    return clean(order.get("product")) == "veridion"


def normalize_order_intake(order: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    company = clip_text(payload.get("company") or order.get("company"), 160)
    name = clip_text(payload.get("name") or order.get("name"), 120)
    email = normalize_email(payload.get("email") or order.get("email"))
    link = clip_text(payload.get("link") or payload.get("website") or order.get("link"), 500)
    note = clip_text(payload.get("note") or order.get("note"), 1000)
    if not company or not name or not validate_email(email):
        raise HTTPException(status_code=400, detail="결제 후 진행에 필요한 회사명, 담당자명, 이메일을 입력해 주세요.")
    if intake_url_required(order) and not link:
        raise HTTPException(status_code=400, detail="Veridion 진행에는 사이트 주소가 필요합니다.")
    order["company"] = company
    order["name"] = name
    order["email"] = email
    order["link"] = link
    order["note"] = note
    order["updatedAt"] = now_iso()
    return order


def create_manual_publication(payload: dict[str, Any]) -> dict[str, Any]:
    product_key = clean(payload.get("product") or "veridion")
    validate_product(product_key)
    title = clip_text(payload.get("title"), 160)
    summary = clip_text(payload.get("summary"), 300)
    body = clean(payload.get("body"))
    if not title or not summary:
        raise HTTPException(status_code=400, detail="자료실 글 등록에는 제목과 요약이 필요합니다.")
    cta_label, cta_href = effective_cta(product_key, fallback_label=clip_text(payload.get("ctaLabel"), 120) or "제품 설명 보기", fallback_href=clip_text(payload.get("ctaHref"), 300) or f"/products/{product_key}/index.html#intro")
    publication = build_publication_payload(
        product_key=product_key,
        title=title,
        summary=summary,
        source="manual",
        code=f"MANUAL-{product_prefix(product_key)}-{int(time.time())}",
        created_at=now_iso(),
        cta_label=cta_label,
        cta_href=cta_href,
        topic_summary=summary,
        publication_id=uid("pubman"),
    )
    if body:
        publication["body"] = body
        publication["bodyHtml"] = "<p>" + "</p><p>".join(escape(chunk) for chunk in body.split("\n") if chunk.strip()) + "</p>"
    asset_url = clip_text(payload.get("assetUrl"), 500)
    if asset_url:
        publication["assetUrl"] = asset_url
    return upsert_record("publications", publication)


def save_library_asset(product_key: str, title: str, upload: UploadFile) -> dict[str, Any]:
    validate_product(product_key)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(upload.filename or "asset.bin").name).strip("-") or "asset.bin"
    asset_id = uid("asset")
    dest = LIBRARY_ASSET_DIR / f"{asset_id}-{safe_name}"
    content = upload.file.read()
    dest.write_bytes(content)
    asset = {
        "id": asset_id,
        "product": product_key,
        "productName": product_name(product_key),
        "title": clip_text(title, 160) or safe_name,
        "filename": safe_name,
        "url": f"/uploads/{dest.name}",
        "contentType": upload.content_type or "application/octet-stream",
        "size": len(content),
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    return upsert_record("assets", asset)


def toss_confirm_remote(payment_key: str, order_id: str, amount: int) -> dict[str, Any]:
    if NV0_TOSS_MOCK or (IS_LOCAL_BASE and (not NV0_TOSS_CLIENT_KEY or not NV0_TOSS_SECRET_KEY)):
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
            order = finalize_paid_order_or_require_intake(order)
            order["updatedAt"] = now_iso()
            return upsert_record("orders", order)

        payment = toss_confirm_remote(payment_key, order_id, amount)
        order["paymentKey"] = payment_key
        order["paymentMeta"] = payment
        order = finalize_paid_order_or_require_intake(order)
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
        order = finalize_paid_order_or_require_intake(order)
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
        cta_label=topic.get('ctaText') or publication_cta_defaults(product_key)[0],
        cta_href=publication_cta_defaults(product_key)[1],
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
    async def strip_response_fingerprint_headers(request: Request, call_next):
        response = await call_next(request)
        for header_name in ("server", "date"):
            for candidate in (header_name, header_name.title()):
                if candidate in response.headers:
                    del response.headers[candidate]
        return response

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
            return board_only_json_response('이 기능은 비활성화되었습니다. 현재는 자료실 허브만 운영합니다.')
        if BOARD_ONLY_MODE and request.method == 'GET' and request.url.path not in HEALTH_ENDPOINTS and not request.url.path.startswith('/api/') and not board_only_path_allowed(request.url.path):
            return board_only_html_response(request.url.path)
        if request.method == 'GET' and request.url.path in {'/admin', '/admin/', '/admin/index.html'} and not request_has_admin_session(request):
            return HTMLResponse(content=build_admin_login_page(), headers={'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex, nofollow'})
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

    @app.get("/admin", include_in_schema=False)
    @app.get("/admin/", include_in_schema=False)
    @app.get("/admin/index.html", include_in_schema=False)
    def admin_index(request: Request) -> Response:
        if not request_has_admin_session(request):
            return HTMLResponse(content=build_admin_login_page(), headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"})
        html = DIST.joinpath("admin", "index.html").read_text(encoding="utf-8").replace('content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1"', 'content="noindex,nofollow"')
        return HTMLResponse(content=html, headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"})

    @app.get("/admin/login", include_in_schema=False)
    @app.get("/admin/login/", include_in_schema=False)
    @app.get("/admin/login/index.html", include_in_schema=False)
    def admin_login_page(request: Request) -> Response:
        if request_has_admin_session(request):
            return Response(status_code=303, headers={"Location": "/admin/index.html"})
        return HTMLResponse(content=build_admin_login_page(), headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"})

    @app.post("/admin/login", include_in_schema=False)
    async def admin_login_submit(request: Request) -> Response:
        form = await request.form()
        token = clean(form.get("token"))
        next_path = clip_text(form.get("next"), 200) or "/admin/index.html"
        if token and secrets.compare_digest(token, NV0_ADMIN_TOKEN):
            response = Response(status_code=303, headers={"Location": next_path})
            set_admin_session_cookie(response, request)
            return response
        return HTMLResponse(content=build_admin_login_page("관리자 키가 맞지 않습니다."), status_code=401, headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"})

    @app.post("/api/admin/login")
    def api_admin_login(payload: dict[str, Any], request: Request, response: Response) -> dict[str, Any]:
        token = clean(payload.get("token"))
        if not token or not secrets.compare_digest(token, NV0_ADMIN_TOKEN):
            raise HTTPException(status_code=401, detail="관리자 키가 맞지 않습니다.")
        expires_at = set_admin_session_cookie(response, request)
        return {"ok": True, "authenticated": True, "expiresAt": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()}

    @app.post("/api/admin/logout")
    def api_admin_logout(request: Request, response: Response) -> dict[str, Any]:
        clear_admin_session_cookie(response, request)
        return {"ok": True, "authenticated": False}

    @app.get("/api/admin/session")
    def api_admin_session(request: Request, response: Response) -> dict[str, Any]:
        authenticated = request_is_admin_authenticated(request)
        if authenticated and not request_has_admin_session(request):
            set_admin_session_cookie(response, request)
        return {"ok": True, "authenticated": authenticated, "via": "cookie" if request_has_admin_session(request) else ("header" if authenticated else "none")}

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
            return {"ok": True, "order": order}

        @app.post("/api/public/orders/reserve")
        def public_reserve_order(payload: dict[str, Any]) -> dict[str, Any]:
            order = reserve_toss_order(payload)
            return {"ok": True, "order": order, "payment": public_config()["payment"]["toss"]}

        @app.post("/api/public/payments/toss/confirm")
        def public_toss_confirm(payload: dict[str, Any]) -> dict[str, Any]:
            order = confirm_toss_payment(payload)
            return {"ok": True, "order": order}

        @app.post("/api/public/orders/{order_id}/intake")
        def public_order_intake(order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
            order = submit_order_intake(order_id, payload)
            return {"ok": True, "order": order}


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
                return {"ok": True, "report": build_veridion_public_report(cached), "cached": True, "preview": build_veridion_demo_preview(cached, clip_text(payload.get('company'), 160) or '샘플 회사')}
            report = build_veridion_scan(payload)
            write_cached_scan(cache_key, report)
            return {"ok": True, "report": build_veridion_public_report(report), "cached": False, "preview": build_veridion_demo_preview(report, clip_text(payload.get('company'), 160) or '샘플 회사')}

        @app.post("/api/public/clearport/analyze")
        def public_clearport_analyze(payload: dict[str, Any]) -> dict[str, Any]:
            cached = read_cached_analysis('clearport', payload)
            if cached:
                return {"ok": True, "report": build_clearport_public_report(cached), "preview": build_clearport_demo_preview(cached, clip_text(payload.get('company'), 160) or '샘플 회사'), "cached": True}
            report = build_clearport_report(payload)
            write_cached_analysis('clearport', payload, report)
            return {"ok": True, "report": build_clearport_public_report(report), "preview": build_clearport_demo_preview(report, clip_text(payload.get('company'), 160) or '샘플 회사'), "cached": False}

        @app.post("/api/public/grantops/analyze")
        def public_grantops_analyze(payload: dict[str, Any]) -> dict[str, Any]:
            cached = read_cached_analysis('grantops', payload)
            if cached:
                return {"ok": True, "report": build_grantops_public_report(cached), "preview": build_grantops_demo_preview(cached, clip_text(payload.get('company'), 160) or '샘플 회사'), "cached": True}
            report = build_grantops_report(payload)
            write_cached_analysis('grantops', payload, report)
            return {"ok": True, "report": build_grantops_public_report(report), "preview": build_grantops_demo_preview(report, clip_text(payload.get('company'), 160) or '샘플 회사'), "cached": False}

        @app.post("/api/public/draftforge/analyze")
        def public_draftforge_analyze(payload: dict[str, Any]) -> dict[str, Any]:
            cached = read_cached_analysis('draftforge', payload)
            if cached:
                return {"ok": True, "report": build_draftforge_public_report(cached), "preview": build_draftforge_demo_preview(cached, clip_text(payload.get('company'), 160) or '샘플 회사'), "cached": True}
            report = build_draftforge_report(payload)
            write_cached_analysis('draftforge', payload, report)
            return {"ok": True, "report": build_draftforge_public_report(report), "preview": build_draftforge_demo_preview(report, clip_text(payload.get('company'), 160) or '샘플 회사'), "cached": False}

        @app.post("/api/public/demo-requests")
        def public_demos(payload: dict[str, Any]) -> dict[str, Any]:
            entry = create_demo_entry(payload)
            preview = build_demo_preview(entry["product"], {**payload, "plan": payload.get("plan") or entry.get("plan") or "Starter"})
            return {"ok": True, "demo": entry, "preview": preview}

        @app.post("/api/public/contact-requests")
        def public_contacts(payload: dict[str, Any]) -> dict[str, Any]:
            entry = create_contact_entry(payload)
            return {"ok": True, "contact": entry}

        @app.post("/api/public/portal/lookup")
        def public_portal_lookup(payload: dict[str, Any]) -> dict[str, Any]:
            lookup = create_lookup_entry(payload)
            order = find_order(clean(payload.get("email")), clean(payload.get("code")))
            publications = [item for item in load_records("publications") if order and item.get("id") in (order.get("publicationIds") or [])]
            return {"ok": True, "lookup": lookup, "order": order, "publications": publications}

        @app.post("/api/public/auth/register")
        def public_auth_register(payload: dict[str, Any]) -> dict[str, Any]:
            result = register_portal_account(payload)
            return {"ok": True, **result}

        @app.post("/api/public/auth/login")
        def public_auth_login(payload: dict[str, Any]) -> dict[str, Any]:
            result = login_portal(payload)
            return {"ok": True, **result}

        @app.post("/api/public/auth/logout")
        def public_auth_logout(ctx: dict[str, Any] = Depends(require_session)) -> dict[str, Any]:
            logout_portal(ctx["session"].get("token"))
            return {"ok": True}

        @app.get("/api/public/auth/me")
        def public_auth_me(ctx: dict[str, Any] = Depends(require_session)) -> dict[str, Any]:
            account = ctx["account"]
            return {"ok": True, "account": safe_account_payload(account), "orders": orders_for_email(account.get("email"))}

        @app.post("/api/public/portal/history")
        def public_portal_history(ctx: dict[str, Any] = Depends(require_session)) -> dict[str, Any]:
            account = ctx["account"]
            return {"ok": True, "account": safe_account_payload(account), "orders": orders_for_email(account.get("email"))}


    @app.get("/api/admin/board-settings")
    def admin_board_settings(_: None = Depends(require_admin)) -> dict[str, Any]:
        return {"ok": True, "settings": get_board_settings(), "state": state_payload()}

    @app.post("/api/admin/board-settings")
    def admin_set_board_settings(payload: dict[str, Any], _: None = Depends(require_admin)) -> dict[str, Any]:
        settings = save_board_settings(payload)
        ensure_scheduled_publications()
        return {"ok": True, "settings": settings, "state": state_payload()}

    @app.post("/api/admin/library/publications")
    def admin_library_publications(payload: dict[str, Any], _: None = Depends(require_admin)) -> dict[str, Any]:
        publication = create_library_publication(payload)
        return {"ok": True, "publication": publication, "state": state_payload()}

    @app.post("/api/admin/library/assets")
    def admin_library_assets(payload: dict[str, Any], _: None = Depends(require_admin)) -> dict[str, Any]:
        asset = create_library_asset(payload)
        return {"ok": True, "asset": asset, "state": state_payload()}

    @app.post("/api/admin/actions/publish-now")
    def admin_publish_now(payload: dict[str, Any] | None = None, _: None = Depends(require_admin)) -> dict[str, Any]:
        requested = clean((payload or {}).get('product'))
        count = max(1, min(24, int((payload or {}).get('count') or 1)))
        settings = get_board_settings()
        if bool(settings.get('autoPublishAllProducts')):
            targets = [key for key in PRODUCTS.keys()] if not requested else [requested]
        else:
            targets = [requested] if requested and requested in PRODUCTS else [key for key, item in PRODUCTS.items() if (item.get('board_automation') or {}).get('enabled')]
        published = []
        for _ in range(count):
            for key in targets:
                published.append(create_board_publication(key, source='manual'))
        return {"ok": True, "published": published, "state": state_payload()}

    @app.post("/api/admin/actions/reseed-board")
    def admin_reseed_board(_: None = Depends(require_admin)) -> dict[str, Any]:
        return {"ok": True, "state": reseed_board_state()}

    if not BOARD_ONLY_MODE and NV0_ENABLE_MANUAL_ADMIN_ACTIONS:
        @app.post("/api/admin/actions/seed-demo")
        def admin_seed_demo(_: None = Depends(require_admin)) -> dict[str, Any]:
            order = upsert_record("orders", base_order_entry({"product": "veridion", "plan": "Growth", "billing": "one-time", "paymentMethod": "toss", "company": "Demo Company", "name": "테스터", "email": "demo@nv0.kr", "note": "시드 결제"}, payment_status="pending"))
            create_demo_entry({"product": "clearport", "company": "Demo Company", "name": "테스터", "email": "demo@nv0.kr", "team": "3명 팀", "need": "정상작동 확인"})
            create_contact_entry({"product": "grantops", "company": "Demo Company", "email": "demo@nv0.kr", "issue": "제출 일정 문의"})
            return {"ok": True, "order": order}

    @app.post("/api/admin/actions/reset")
    def admin_reset(_: None = Depends(require_admin)) -> dict[str, Any]:
        return {"ok": True, "state": reseed_board_state()}

    if not BOARD_ONLY_MODE and NV0_ENABLE_MANUAL_ADMIN_ACTIONS:
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

    app.mount("/uploads", StaticFiles(directory=str(LIBRARY_ASSET_DIR), html=False), name="uploads")
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
    return finalize_paid_order_or_require_intake(order)


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
