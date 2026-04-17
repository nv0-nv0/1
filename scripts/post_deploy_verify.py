from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

DEFAULT_PRODUCTS = ('veridion', 'clearport', 'grantops', 'draftforge')

class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

NO_REDIRECT = build_opener(NoRedirectHandler)


def fetch(method: str, url: str, payload: dict | None = None, *, headers: dict[str, str] | None = None, follow_redirects: bool = True, timeout: int = 20):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = Request(url, data=data, method=method)
    if data is not None:
        req.add_header('Content-Type', 'application/json')
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    opener = None if follow_redirects else NO_REDIRECT
    try:
        if opener is None:
            with urlopen(req, timeout=timeout) as res:
                return res.status, res.read(), {str(k).lower(): str(v) for k, v in res.headers.items()}
        with opener.open(req, timeout=timeout) as res:  # type: ignore[arg-type]
            return res.status, res.read(), {str(k).lower(): str(v) for k, v in res.headers.items()}
    except HTTPError as exc:
        return exc.code, exc.read(), {str(k).lower(): str(v) for k, v in exc.headers.items()}
    except URLError as exc:
        raise RuntimeError(f'network error for {url}: {exc}') from exc


def ensure(status: int, expected: int | tuple[int, ...], label: str) -> None:
    allowed = expected if isinstance(expected, tuple) else (expected,)
    if status not in allowed:
        raise AssertionError(f'{label}: expected {allowed}, got {status}')


def must_contain(body: bytes, needle: str, label: str) -> None:
    text = body.decode('utf-8', errors='replace')
    if needle not in text:
        raise AssertionError(f'{label}: missing {needle!r}')


def canonical_root(base_url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError('base-url must include scheme and host, for example https://nv0.kr')
    return parsed.scheme, parsed.netloc


def main() -> int:
    parser = argparse.ArgumentParser(description='Verify deployed NV0 site end-to-end against a live base URL.')
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--admin-token', default=os.getenv('NV0_ADMIN_TOKEN', ''))
    parser.add_argument('--products', default=','.join(DEFAULT_PRODUCTS))
    parser.add_argument('--skip-www-redirect', action='store_true')
    args = parser.parse_args()

    scheme, host = canonical_root(args.base_url.rstrip('/'))
    base_url = f'{scheme}://{host}'
    products = [item.strip() for item in args.products.split(',') if item.strip()]
    admin_headers = {'X-Admin-Token': args.admin_token} if args.admin_token else {}

    results: list[str] = []

    # Public surfaces
    pages = [
        ('/', 'id="product-grid"'),
        ('/products/', 'id="product-grid"'),
        ('/pricing/', 'data-page="pricing"'),
        ('/docs/', 'data-page="docs"'),
        ('/board/', 'id="public-board-grid"'),
        ('/demo/', 'id="demo-form"'),
        ('/checkout/', 'id="checkout-form"'),
        ('/portal/', 'id="portal-lookup-form"'),
        ('/engine/', 'id="product-grid"'),
        ('/admin/', 'data-page="admin"'),
    ]
    for path, needle in pages:
        status, body, _ = fetch('GET', base_url + path)
        ensure(status, 200, f'GET {path}')
        must_contain(body, needle, f'GET {path}')
        results.append(f'OK {path}')

    # Product surfaces and board/docs
    for product in products:
        targets = [
            (f'/products/{product}/', 'data-page="product"'),
            (f'/products/{product}/', 'id="product-demo-shell"'),
            (f'/products/{product}/', 'id="product-checkout-form"'),
            (f'/products/{product}/demo/', 'id="product-demo-form"'),
            (f'/products/{product}/plans/', 'data-page="product-plans"'),
            (f'/products/{product}/delivery/', 'data-page="product-delivery"'),
            (f'/products/{product}/faq/', 'data-page="product-faq"'),
            (f'/products/{product}/board/', 'id="product-board-grid"'),
            (f'/docs/{product}/', 'data-page="docs-detail"'),
        ]
        seen = set()
        for path, needle in targets:
            key = (path, needle)
            if key in seen:
                continue
            seen.add(key)
            status, body, _ = fetch('GET', base_url + path)
            ensure(status, 200, f'GET {path}')
            must_contain(body, needle, f'GET {path}')
        results.append(f'OK product:{product}')

    # Health
    for path in ('/livez', '/readyz', '/api/health'):
        status, body, _ = fetch('GET', base_url + path)
        ensure(status, 200, f'GET {path}')
        payload = json.loads(body.decode('utf-8'))
        if payload.get('ok') is not True:
            raise AssertionError(f'{path} ok=false')
        results.append(f'OK {path}')

    # Canonical redirect
    if not args.skip_www_redirect and host.startswith('nv0.'):
        www_url = f'{scheme}://www.{host[4:]}'
        status, _, headers = fetch('GET', www_url + '/api/health', follow_redirects=False)
        ensure(status, (301, 302, 307, 308), 'GET www redirect')
        location = headers.get('location', '')
        expected = base_url + '/api/health'
        if location != expected:
            raise AssertionError(f'www redirect mismatch: {location!r} != {expected!r}')
        results.append('OK canonical:www-redirect')

    # Public API flow
    demo_payload = {
        'product': products[0],
        'company': 'Deploy Verify Co',
        'name': 'Verifier',
        'email': 'verify@example.com',
        'team': '1인 운영',
        'need': '배포 후 전역 검증',
        'keywords': '검증,연동,발행',
    }
    status, body, _ = fetch('POST', base_url + '/api/public/demo-requests', demo_payload)
    ensure(status, 200, 'POST /api/public/demo-requests')
    demo_json = json.loads(body.decode('utf-8'))
    demo_code = demo_json.get('demo', {}).get('code')
    if not demo_code:
        raise AssertionError('demo material missing')
    results.append('OK api:demo')

    contact_payload = {
        'product': products[0],
        'company': 'Deploy Verify Co',
        'email': 'verify@example.com',
        'issue': '배포 후 문의 저장 확인',
    }
    status, _, _ = fetch('POST', base_url + '/api/public/contact-requests', contact_payload)
    ensure(status, 200, 'POST /api/public/contact-requests')
    results.append('OK api:contact')

    order_payload = {
        'product': products[0],
        'plan': 'Starter',
        'billing': 'one-time',
        'paymentMethod': 'toss',
    }
    status, body, _ = fetch('POST', base_url + '/api/public/orders/reserve', order_payload)
    ensure(status, 200, 'POST /api/public/orders/reserve')
    reserve = json.loads(body.decode('utf-8')).get('order', {})
    order_id = reserve.get('id')
    amount = reserve.get('amount')
    portal_code = reserve.get('code')
    if not order_id or amount is None or not portal_code:
        raise AssertionError('order reserve payload incomplete')
    results.append('OK api:reserve')

    status, body, _ = fetch('POST', base_url + '/api/public/payments/toss/confirm', {
        'paymentKey': f'mock_{order_id}',
        'orderId': order_id,
        'amount': amount,
    })
    ensure(status, 200, 'POST /api/public/payments/toss/confirm')
    order = json.loads(body.decode('utf-8')).get('order', {})
    if order.get('paymentStatus') != 'paid':
        raise AssertionError('payment confirm did not mark paymentStatus=paid')
    if order.get('status') != 'intake_required':
        raise AssertionError(f"payment confirm returned unexpected order status: {order.get('status')!r}")
    results.append('OK api:payment-confirm')

    status, body, _ = fetch('POST', base_url + f'/api/public/orders/{order_id}/intake', {
        'company': 'Deploy Verify Co',
        'name': 'Verifier',
        'email': 'verify@example.com',
        'website': 'https://example.com',
        'note': f'post-deploy verify / {demo_code}',
    })
    ensure(status, 200, 'POST /api/public/orders/{id}/intake')
    intake_order = json.loads(body.decode('utf-8')).get('order', {})
    if intake_order.get('status') not in {'delivered', 'published'}:
        raise AssertionError(f"order intake returned unexpected status: {intake_order.get('status')!r}")
    results.append('OK api:intake')

    status, body, _ = fetch('POST', base_url + '/api/public/portal/lookup', {
        'email': 'verify@example.com',
        'code': portal_code,
    })
    ensure(status, 200, 'POST /api/public/portal/lookup')
    portal = json.loads(body.decode('utf-8')).get('order', {})
    if portal.get('id') != order_id:
        raise AssertionError('portal lookup order mismatch')
    results.append('OK api:portal-lookup')

    if admin_headers:
        status, body, _ = fetch('GET', base_url + '/api/admin/state', headers=admin_headers)
        ensure(status, 200, 'GET /api/admin/state')
        state = json.loads(body.decode('utf-8')).get('state', {})
        if not state.get('orders'):
            raise AssertionError('admin state missing orders')
        if not state.get('demos'):
            raise AssertionError('admin state missing demos')
        results.append('OK api:admin-state')

    print('POST_DEPLOY_VERIFY_OK')
    for item in results:
        print(item)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
