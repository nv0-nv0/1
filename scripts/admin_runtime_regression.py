from __future__ import annotations

import argparse
import base64
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def api(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    data = None
    headers = {'X-Admin-Token': token, 'Accept': 'application/json'}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=20) as res:
            return json.loads(res.read().decode('utf-8'))
    except HTTPError as exc:
        body = exc.read().decode('utf-8', 'replace')
        raise RuntimeError(f'{method} {url} failed: {exc.code} {body}') from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--admin-token', required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    token = args.admin_token

    settings = api('POST', base + '/api/admin/board-settings', token, {
        'ctaLabel': '제품 설명 보기',
        'ctaHref': '/products/veridion/index.html#intro',
        'autoPublishAllProducts': 1,
        'autoPublishEnabled': 1,
        'scheduleType': 'daily',
        'frequencyPerRun': 2,
        'intervalHours': 12,
        'timeSlots': '09:00, 15:00',
        'selectedProducts': 'veridion, clearport',
        'publishMode': 'publish',
    })
    if not settings.get('ok'):
        raise RuntimeError('board settings save failed')

    asset = api('POST', base + '/api/admin/library/assets', token, {
        'product': 'clearport',
        'title': 'admin regression asset',
        'filename': 'admin-regression.txt',
        'mimeType': 'text/plain',
        'contentBase64': base64.b64encode(b'admin regression asset').decode('ascii'),
    }).get('asset')
    if not asset or not asset.get('url'):
        raise RuntimeError('asset upload failed')

    manual = api('POST', base + '/api/admin/library/publications', token, {
        'product': 'clearport',
        'title': '관리자 수동 글',
        'summary': '수동 등록 회귀 확인',
        'body': '관리자 수동 등록 본문입니다.',
        'assetUrl': asset['url'],
    }).get('publication')
    if not manual or manual.get('source') != 'admin-manual' or manual.get('assetUrl') != asset['url']:
        raise RuntimeError('manual publication failed')

    auto = api('POST', base + '/api/admin/library/publications', token, {
        'product': 'veridion',
        'autoGenerate': 1,
        'assetUrl': asset['url'],
    }).get('publication')
    if not auto or auto.get('source') != 'admin-auto' or auto.get('status') != 'published':
        raise RuntimeError('auto publication failed')

    publish_now = api('POST', base + '/api/admin/actions/publish-now', token, {
        'product': 'grantops',
        'count': 2,
    }).get('published') or []
    if len(publish_now) != 2:
        raise RuntimeError(f'publish-now count mismatch: {len(publish_now)}')
    if any(item.get('product') != 'grantops' for item in publish_now):
        raise RuntimeError('publish-now product mismatch')

    print(json.dumps({
        'ok': True,
        'checks': ['board-settings-save', 'asset-upload', 'manual-publication', 'auto-publication', 'publish-now-count'],
        'assetUrl': asset['url'],
        'autoSource': auto.get('source'),
        'publishedCount': len(publish_now),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
