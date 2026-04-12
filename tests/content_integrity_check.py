from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def read(rel: str) -> str:
    return (DIST / rel).read_text(encoding='utf-8')


def assert_contains(text: str, needles: list[str], label: str):
    missing = [n for n in needles if n not in text]
    if missing:
        raise AssertionError(f"{label} missing: {missing}")


def assert_not_contains(text: str, needles: list[str], label: str):
    found = [n for n in needles if n in text]
    if found:
        raise AssertionError(f"{label} unexpected: {found}")


def main():
    home = read('index.html')
    assert_contains(home, [
        '회사 소개 보기',
        '제품 보러 가기',
        '대표 제품 즉시 데모',
        'product-grid',
        '바로 체험',
    ], 'home')
    assert_not_contains(home, ['CTA 포스팅 자동발행 게시판만 운영합니다'], 'home')

    products = read('products/index.html')
    assert_contains(products, ['체험 → 플랜 선택 → 외부 결제 → 결과 확인', 'product-grid'], 'products')

    veridion = read('products/veridion/index.html')
    assert_contains(veridion, [
        'id="product-demo-form"',
        'id="product-checkout-form"',
        'Veridion 자동발행게시판',
        '구매 버튼을 누르면 바로 외부 결제창으로 이동합니다',
        '결제 후 결과 자료와 다음 진행이 자연스럽게 이어집니다',
    ], 'veridion')

    checkout = read('checkout/index.html')
    assert_contains(checkout, ['id="checkout-form"', '결제 버튼을 누르면 외부 결제창으로 이동합니다'], 'checkout')

    portal = read('portal/index.html')
    assert_contains(portal, ['id="portal-lookup-form"', '결제 후 진행 상태와 결과 자료를 바로 확인하세요'], 'portal')

    payment = read('payments/toss/success/index.html')
    assert_contains(payment, ['payment-success-result', '결제가 완료되면 결과 확인 화면으로 바로 이어집니다'], 'payment-success')

    for rel in ['company/index.html', 'products/index.html', 'demo/index.html', 'contact/index.html', 'portal/index.html', 'pricing/index.html', 'docs/index.html', 'cases/index.html', 'faq/index.html', 'guides/index.html', 'service/index.html', 'onboarding/index.html']:
        if not (DIST / rel).exists():
            raise AssertionError(f'missing expected page: {rel}')

    data = read('assets/site-data.js')
    assert_contains(data, ['/api/public/orders/reserve', '/api/public/payments/toss/confirm', '/api/public/portal/lookup'], 'site-data')

    script = read('assets/site.js')
    assert_contains(script, ['bindProductDemoForm', 'bindProductCheckoutForm', 'TossPayments', 'portalHref'], 'site-js')
    assert_not_contains(script, ['CTA 포스팅 자동발행 게시판만 운영합니다'], 'site-js')

    print('CONTENT_OK')


if __name__ == '__main__':
    main()
