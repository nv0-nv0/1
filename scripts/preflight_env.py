from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

REQUIRED = [
    "NV0_BASE_URL",
    "NV0_ALLOWED_HOSTS",
    "NV0_ALLOWED_ORIGINS",
]

RECOMMENDED = [
    "NV0_ADMIN_TOKEN",
    "NV0_TOSS_CLIENT_KEY",
    "NV0_TOSS_SECRET_KEY",
    "NV0_TOSS_WEBHOOK_SECRET",
    "NV0_BACKUP_PASSPHRASE",
]

LOCAL_HOSTS = {"127.0.0.1", "localhost", "0.0.0.0"}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def warn(msg: str) -> None:
    print(f"WARN: {msg}")


def ok(msg: str) -> None:
    print(f"OK: {msg}")


def main() -> None:
    values = {key: os.getenv(key, "").strip() for key in REQUIRED + RECOMMENDED}
    for key in REQUIRED:
        if not values[key]:
            fail(f"{key} 값이 비어 있습니다.")
        ok(f"{key} 설정 확인")

    parsed = urlparse(values["NV0_BASE_URL"])
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        fail("NV0_BASE_URL 형식이 올바르지 않습니다.")
    host = parsed.netloc.lower()
    base_host = (parsed.hostname or '').lower()
    is_local = base_host in LOCAL_HOSTS
    board_only = os.getenv("NV0_BOARD_ONLY_MODE", "0").strip().lower() in {"1", "true", "yes", "on"}
    toss_mock = os.getenv("NV0_TOSS_MOCK", "0").strip().lower() in {"1", "true", "yes", "on"}


    allowed_hosts = {item.strip().lower() for item in values["NV0_ALLOWED_HOSTS"].split(',') if item.strip()}
    allowed_origins = {item.strip().rstrip('/').lower() for item in values["NV0_ALLOWED_ORIGINS"].split(',') if item.strip()}

    if '*' in allowed_hosts:
        fail("운영 배포에서는 NV0_ALLOWED_HOSTS=* 를 사용하지 마세요.")
    ok("NV0_ALLOWED_HOSTS 와일드카드 미사용")

    if parsed.hostname and parsed.hostname.lower() not in allowed_hosts:
        fail("NV0_BASE_URL 호스트가 NV0_ALLOWED_HOSTS에 포함되어 있지 않습니다.")
    ok("NV0_BASE_URL 호스트와 NV0_ALLOWED_HOSTS 일치")

    origin = f"{parsed.scheme}://{host}".rstrip('/')
    if origin not in allowed_origins:
        fail("NV0_BASE_URL origin이 NV0_ALLOWED_ORIGINS에 포함되어 있지 않습니다.")
    ok("NV0_BASE_URL origin과 NV0_ALLOWED_ORIGINS 일치")

    if not is_local and parsed.scheme != 'https':
        fail('운영 배포에서는 NV0_BASE_URL 을 https 로 설정해야 합니다.')
    if not board_only and not toss_mock and values['NV0_ALLOWED_ORIGINS'].count(',') > 10:
        warn('NV0_ALLOWED_ORIGINS 항목이 많습니다. 꼭 필요한 origin만 남기는 것이 안전합니다.')

    admin = values["NV0_ADMIN_TOKEN"]
    if not admin or len(admin) < (12 if is_local else 32):
        warn("NV0_ADMIN_TOKEN 길이가 짧거나 비어 있습니다. 운영에서는 32자 이상을 권장합니다.")
    else:
        ok("NV0_ADMIN_TOKEN 길이 확인")

    backup_passphrase = values["NV0_BACKUP_PASSPHRASE"]
    if not backup_passphrase or len(backup_passphrase) < (12 if is_local else 24):
        warn("NV0_BACKUP_PASSPHRASE가 짧거나 비어 있습니다. 운영에서는 24자 이상을 권장합니다.")
    else:
        ok("NV0_BACKUP_PASSPHRASE 길이 확인")

    ck = values["NV0_TOSS_CLIENT_KEY"]
    sk = values["NV0_TOSS_SECRET_KEY"]
    wh = values["NV0_TOSS_WEBHOOK_SECRET"]
    if board_only:
        ok("board-only 모드에서는 결제 키 필수 검사를 건너뜁니다.")
    elif toss_mock:
        if ck and sk:
            test_or_live = {ck.split('_',1)[0], sk.split('_',1)[0]}
            if len(test_or_live) != 1:
                fail("Toss 클라이언트 키와 시크릿 키의 환경(test/live)이 일치하지 않습니다.")
        ok("mock 모드 결제 점검 확인")
    else:
        if not ck or not sk:
            fail("full 모드 실결제에서는 NV0_TOSS_CLIENT_KEY 와 NV0_TOSS_SECRET_KEY 가 모두 필요합니다.")
        test_or_live = {ck.split('_',1)[0], sk.split('_',1)[0]}
        if len(test_or_live) != 1:
            fail("Toss 클라이언트 키와 시크릿 키의 환경(test/live)이 일치하지 않습니다.")
        if not wh:
            fail("실결제 운영에서는 NV0_TOSS_WEBHOOK_SECRET 이 필요합니다.")
        ok("Toss 키/웹훅 시크릿 형식 확인")

    forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "").strip()
    if not is_local and not forwarded_allow_ips:
        fail("운영 배포에서는 FORWARDED_ALLOW_IPS 값을 명시하세요. 신뢰할 프록시 IP 또는 *를 직접 선택해야 합니다.")
    if forwarded_allow_ips == '*':
        warn("FORWARDED_ALLOW_IPS=* 는 신뢰된 프록시 환경에서만 사용하세요. 가능하면 프록시 IP 또는 CIDR로 제한하는 편이 더 안전합니다.")
    elif forwarded_allow_ips:
        ok("FORWARDED_ALLOW_IPS 설정 확인")

    docs = os.getenv("NV0_ENABLE_DOCS", "0").strip()
    if docs in {"1", "true", "yes", "on"}:
        warn("NV0_ENABLE_DOCS가 활성화되어 있습니다. 운영에서는 0 권장입니다.")
    else:
        ok("NV0_ENABLE_DOCS 운영 권장값")

    print("READY: 배포 전 환경변수 점검 통과")


if __name__ == "__main__":
    main()
