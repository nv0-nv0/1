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
        '제품 구조 보기',
        '대표 제품 바로 체험',
        'product-grid',
        '바로 체험',
        'og:title',
        'application/ld+json',
        'favicon.svg',
    ], 'home')
    assert_not_contains(home, ['CTA 포스팅 자동발행 게시판만 운영합니다'], 'home')

    products = read('products/index.html')
    assert_contains(products, ['공용 엔진 위에 붙는 제품 모듈을 문제 기준으로 바로 고를 수 있습니다', '문제에서 시작하는 제품 선택', 'product-grid'], 'products')

    engine = read('engine/index.html')
    assert_contains(engine, ['공용 엔진', '신청 저장, 결제 준비, 자동 발행, 고객 포털을 하나의 기록선으로 묶습니다', '엔진 위에서 반복되는 공통 화면'], 'engine')

    solutions = read('solutions/index.html')
    assert_contains(solutions, ['문제에서 시작해 제품, 가격, 자료까지 바로 이어집니다', '문제별 다음 행동'], 'solutions')

    for key, name in [('veridion', 'Veridion'), ('clearport', 'ClearPort'), ('grantops', 'GrantOps'), ('draftforge', 'DraftForge')]:
        product_html = read(f'products/{key}/index.html')
        assert_contains(product_html, [
            name,
            '문서 보기',
            'id="product-demo-form"',
            'name="name"',
            'name="email"',
            'id="product-checkout-form"',
            '시작하기 버튼을 누르면 바로 외부 결제창으로 이어집니다',
            '결제 후 결과 자료와 다음 진행이 자연스럽게 이어집니다',
        ], key)
        product_board = read(f'products/{key}/board/index.html')
        assert_contains(product_board, [name, 'AI 자동발행 블로그 허브'], f'{key}-board')
        product_doc = read(f'docs/{key}/index.html')
        assert_contains(product_doc, [name], f'{key}-doc')

    demo = read('demo/index.html')
    assert_contains(demo, ['id="demo-form"', 'name="name"', 'name="email"', 'required', 'role="status"', '무료 샘플과 데모 코드 받기'], 'demo')

    checkout = read('checkout/index.html')
    assert_contains(checkout, ['id="checkout-form"', 'name="company"', 'name="email"', 'required', 'role="status"', '시작하기 버튼을 누르면 바로 외부 결제창으로 이어집니다'], 'checkout')

    portal = read('portal/index.html')
    assert_contains(portal, ['id="portal-lookup-form"', 'name="code"', 'required', 'role="status"', '결제 후 진행 상태와 결과 자료를 바로 확인해 보세요'], 'portal')

    payment = read('payments/toss/success/index.html')
    assert_contains(payment, ['payment-success-result', '결제가 완료되면 결과 확인 화면으로 바로 이어집니다'], 'payment-success')

    for rel in ['company/index.html', 'products/index.html', 'demo/index.html', 'contact/index.html', 'portal/index.html', 'pricing/index.html', 'docs/index.html', 'cases/index.html', 'faq/index.html', 'guides/index.html', 'service/index.html', 'onboarding/index.html', 'legal/terms/index.html', '404.html', 'robots.txt', 'sitemap.xml', '.well-known/security.txt', 'assets/favicon.svg', 'favicon.ico']:
        if not (DIST / rel).exists():
            raise AssertionError(f'missing expected page: {rel}')


    robots = read('robots.txt')
    assert_contains(robots, ['User-agent: *', 'Sitemap: /sitemap.xml'], 'robots')

    sitemap = read('sitemap.xml')
    assert_contains(sitemap, ['https://nv0.kr/', '/legal/terms/', '/products/veridion/'], 'sitemap')

    contact = read('contact/index.html')
    assert_contains(contact, ['id="contact-form"', 'name="name"', 'name="issue"', 'required', 'role="status"'], 'contact')

    terms = read('legal/terms/index.html')
    assert_contains(terms, ['서비스 이용 전에 확인하실 핵심 약관을 정리했습니다', '공개 페이지, 제품 체험, 주문, 결제, 발행, 포털 확인'], 'terms')

    data = read('assets/site-data.js')
    assert_contains(data, ['/api/public/orders/reserve', '/api/public/payments/toss/confirm', '/api/public/portal/lookup'], 'site-data')

    script = read('assets/site.js')
    assert_contains(script, ['bindProductDemoForm', 'bindProductCheckoutForm', 'bindDemoForm', 'config.integration?.demo_endpoint', 'TossPayments', 'portalHref', 'buildPublicationRecord', 'ai-hybrid-blog'], 'site-js')
    assert_not_contains(script, ['CTA 포스팅 자동발행 게시판만 운영합니다'], 'site-js')

    print('CONTENT_OK')


if __name__ == '__main__':
    main()
