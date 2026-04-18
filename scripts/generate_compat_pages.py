import json
from pathlib import Path
from html import escape
from textwrap import dedent


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def write(path: Path, content: str):
    ensure_dir(path.parent)
    path.write_text(content, encoding='utf-8')


def rel_prefix(depth: int) -> str:
    return './' if depth == 0 else '../' * depth


def page_url(brand: dict, path: str) -> str:
    clean = path if path.startswith('/') else '/' + path
    if clean.endswith('index.html'):
        clean = clean[:-10]
    return brand['domain'].rstrip('/') + clean

POLICY_EFFECTIVE_DATE = '2026-04-15'
POLICY_UPDATED_DATE = '2026-04-15'

def build_page_schema(brand: dict, title: str, description: str, page_path: str, page_key: str, product_key: str | None = None):
    canonical = page_url(brand, page_path)
    schema = {
        '@context': 'https://schema.org',
        '@type': 'Product' if page_key.startswith('product') else 'WebPage',
        'name': title.split('|')[0].strip(),
        'description': description,
        'url': canonical,
        'inLanguage': 'ko-KR',
        'isPartOf': {'@type': 'WebSite', 'name': brand.get('name', 'NV0'), 'url': brand.get('domain', '').rstrip('/') + '/'},
    }
    if product_key:
        schema['sku'] = product_key
        schema['brand'] = {'@type': 'Brand', 'name': brand.get('name', 'NV0')}
        schema['category'] = 'Automation SaaS'
    return json.dumps(schema, ensure_ascii=False, separators=(',', ':'))

def short_text(text: str, limit: int = 22) -> str:
    value = str(text or '').strip()
    return value if len(value) <= limit else value[:limit-1].rstrip() + '…'

def consent_notice(prefix: str, kind: str = 'general') -> str:
    scope_map = {
        'checkout': '결제 준비, 주문 등록, 결과 제공, 고객 포털 조회 안내',
        'demo': '샘플 결과 저장, 후속 안내, 제품 데모 기록 관리',
        'contact': '예외 문의 접수, 회신, 일정 조율',
        'product-demo': '제품별 샘플 저장, 후속 안내, 데모 결과 기록 관리',
        'product-checkout': '제품별 주문 등록, 결제 준비, 결과 제공',
    }
    scope = scope_map.get(kind, scope_map['demo'])
    return f'''<div class="consent-panel"><div class="consent-copy"><strong>개인정보 수집·이용 안내</strong><p>입력하신 정보는 {scope}를 위해 사용합니다. 자세한 내용은 <a href="{prefix}legal/privacy/index.html">개인정보처리방침</a>에서 확인하실 수 있습니다.</p></div><label class="consent-check"><input type="checkbox" name="privacyConsent" value="yes" required data-consent-required="1"> <span>개인정보 수집·이용에 동의합니다.</span></label><small data-consent-message>동의 후에만 저장·문의·결제를 진행할 수 있습니다.</small></div>'''


def doc(brand: dict, title: str, description: str, body_class: str, body: str, *, depth: int, page_key: str, page_path: str, product_key: str | None = None):
    prefix = rel_prefix(depth)
    attrs = [f'class="{body_class}"', f'data-page="{page_key}"']
    if product_key:
        attrs.append(f'data-product="{product_key}"')
    canonical = page_url(brand, page_path)
    og_type = 'product' if page_key.startswith('product') else 'website'
    schema_json = build_page_schema(brand, title, description, page_path, page_key, product_key)
    return f'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#0f172a">
  <meta name="format-detection" content="telephone=no,address=no,email=no,date=no">
  <meta name="color-scheme" content="light">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(description)}">
  <meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">
  <meta property="og:locale" content="ko_KR">
  <meta property="og:site_name" content="{escape(brand.get('name', 'NV0'))}">
  <meta property="og:type" content="{og_type}">
  <meta property="og:title" content="{escape(title)}">
  <meta property="og:description" content="{escape(description)}">
  <meta property="og:url" content="{escape(canonical)}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{escape(title)}">
  <meta name="twitter:description" content="{escape(description)}">
  <link rel="canonical" href="{escape(canonical)}">
  <link rel="icon" href="{prefix}assets/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="{prefix}assets/site.css">
  <script type="application/ld+json">{schema_json}</script>
  <script src="{prefix}assets/site-data.js"></script>
  <script defer src="{prefix}assets/site.js"></script>
</head>
<body {' '.join(attrs)}>
<header class="site-header" id="site-header"></header>
{body}
<footer class="footer" id="site-footer"></footer>
</body>
</html>'''


def plan_summary(product: dict) -> str:
    return ' · '.join(f"{plan['name']} {plan['price']}" for plan in product.get('plans', []))


def product_quick_links(prefix: str, product: dict) -> str:
    return (
        f'<div class="small-actions">'
        f'<a href="{prefix}products/{escape(product["key"])}.html"></a>'
        f'</div>'
    )


def product_subnav(prefix: str, product: dict, active: str) -> str:
    links = [
        ('개요', f'{prefix}products/{product["key"]}/index.html', 'overview'),
        ('즉시 데모', f'{prefix}products/{product["key"]}/demo/index.html', 'demo'),
        ('플랜', f'{prefix}products/{product["key"]}/plans/index.html', 'plans'),
        ('제공 흐름', f'{prefix}products/{product["key"]}/delivery/index.html', 'delivery'),
        ('FAQ', f'{prefix}products/{product["key"]}/faq/index.html', 'faq'),
        ('관련 글', f'{prefix}products/{product["key"]}/board/index.html', 'board'),
    ]
    return '<div class="page-subnav">' + ''.join(
        f'<a class="sub-link {"active" if key == active else ""}" href="{href}">{label}</a>'
        for label, href, key in links
    ) + '</div>'



def plan_cards_markup(product: dict, prefix: str) -> str:
    cards = []
    for plan in product.get('plans', []):
        includes = ''.join(f'<li>{escape(item)}</li>' for item in plan.get('includes', []))
        recommended = '<span class="tag" style="margin-left:8px">추천</span>' if plan.get('recommended') else ''
        meta = ' · '.join(part for part in [f"납기 {plan.get('delivery')}" if plan.get('delivery') else '', plan.get('revisions', '')] if part)
        cards.append(
            f"<article class='plan-card {'recommended' if plan.get('recommended') else ''}'><div class='plan-head'><span class='tag'>{escape(plan['name'])}</span>{recommended}</div><h3>{escape(plan['price'])}</h3><p>{escape(plan.get('note', ''))}</p>{f'<div class="plan-meta">{escape(meta)}</div>' if meta else ''}{f'<ul class="clean plan-include-list">{includes}</ul>' if includes else ''}<div class='small-actions'><a class='button' href='{prefix}checkout/index.html?product={escape(product['key'])}&plan={escape(plan['name'])}'>이 플랜으로 진행</a></div></article>"
        )
    return ''.join(cards)

def faq_details(product: dict) -> str:
    return ''.join(
        f'<details class="fold-card"><summary><strong>{escape(item["q"])}</strong><span>접힌 상태에서는 핵심만, 펼치면 배경까지 자세히 확인할 수 있습니다.</span></summary><div><p>{escape(item["a"])}</p></div></details>'
        for item in product.get('faqs', [])
    )


def pricing_page(brand: dict, products: list[dict]) -> str:
    plan_names = []
    for item in products:
        for plan in item.get('plans', []):
            name = plan.get('name')
            if name and name not in plan_names:
                plan_names.append(name)
    headers = ''.join(f'<th>{escape(name)}</th>' for name in plan_names)
    rows = ''
    for item in products:
        plan_map = {plan['name']: plan for plan in item.get('plans', [])}
        cells = ''.join(f"<td>{escape((plan_map.get(name) or {}).get('price', '-'))}</td>" for name in plan_names)
        rows += f"<tr><td><strong>{escape(item['name'])}</strong><br><small>{escape(item['headline'])}</small></td>{cells}<td>{escape(item['outputs'][0])}</td></tr>"
    cards = ''
    for item in products:
        recommended = next((plan['name'] for plan in item.get('plans', []) if plan.get('recommended')), item.get('plans', [{}])[0].get('name', 'Lite'))
        plan_lines = ''.join(f"<li>{escape(plan['name'])} · {escape(plan['price'])} · {escape(plan.get('note', ''))}</li>" for plan in item.get('plans', []))
        cards += f"<details class='fold-card'><summary><strong>{escape(item['name'])}</strong><span>시작가 {escape(item['plans'][0]['price'])} · 추천 {escape(recommended)}</span></summary><div><p>{escape(item['pricing_basis'])}</p><ul class='clean'>{plan_lines}</ul><div class='admin-grid' style='margin:14px 0'><article class='admin-card'><span class='tag'>플랜 수</span><h3>{len(item.get('plans', []))}</h3><p>가격 선택 폭</p></article><article class='admin-card'><span class='tag'>결과물</span><h3>{len(item.get('outputs', []))}</h3><p>기본 제공 핵심 항목</p></article><article class='admin-card'><span class='tag'>실패 대응</span><h3>{len((item.get('architecture') or {}).get('failure_controls', []))}</h3><p>예외 상황 처리 기준</p></article></div><p>{escape(((item.get('architecture') or {}).get('performance_targets') or ['처음에 가장 먼저 봐야 할 결과가 앞으로 오도록 설계했습니다.'])[0])}</p><ul class='clean'>{''.join(f'<li>{escape(text)}</li>' for text in item.get('samples', [])[:3])}</ul><div class='small-actions'><a href='../products/{escape(item['key'])}/index.html'>제품 보기</a><a href='../products/{escape(item['key'])}/demo/index.html'>즉시 데모</a><a href='../products/{escape(item['key'])}/plans/index.html'>플랜 보기</a></div></div></details>"
    body = dedent(f'''
    <main>
      <section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>가격</span></div><span class="kicker">Pricing</span><h1>가격은 더 낮게 시작하고, 필요한 범위만 단계적으로 올릴 수 있게 나눴습니다</h1><p class="lead">모든 제품을 Lite · Starter · Growth · Scale 네 단계로 통일해 처음 진입 가격을 낮췄습니다. 빠르게 판단만 필요한 경우는 Lite·Starter, 실제 운영 적용과 반복 사용까지 필요한 경우는 Growth 이상으로 올리기 쉽게 구성했습니다.</p><div class="actions"><a class="button" href="../demo/index.html">즉시 데모</a><a class="button secondary" href="../products/index.html">제품 선택</a><a class="button ghost" href="../service/index.html">확장 서비스 보기</a></div></div><div class="card"><span class="tag">핵심 안내</span><ul class="clean"><li>Lite는 빠른 판단용, Starter는 입문 적용용, Growth는 실제 실행용, Scale은 반복 운영용입니다.</li><li>플랜별 납기와 수정 범위는 각 제품 플랜 페이지에서 더 자세히 확인하실 수 있습니다.</li><li>별도 계약이나 장기 운영이 필요한 경우는 확장 서비스에서 추가 모듈로 붙일 수 있습니다.</li></ul><div class="small-actions"><a href="../legal/refund/index.html">환불 정책</a><a href="../legal/terms/index.html">이용약관</a></div></div></div></section>
      <section class="section compact"><div class="container"><div class="table-wrap"><table><thead><tr><th>제품</th>{headers}<th>대표 전달물</th></tr></thead><tbody>{rows}</tbody></table></div></div></section>
      <section class="section compact"><div class="container"><div class="accordion-stack">{cards}</div></div></section>
    </main>
    ''')
    return doc(brand, f"가격 | {brand['name']}", '제품별 시작가와 범위를 확인하는 페이지', 'pricing', body, depth=1, page_key='pricing', page_path='/pricing/index.html')


def guides_page(brand: dict, products: list[dict]) -> str:
    cards = ''.join(
        f"<details class='fold-card'><summary><strong>{escape(item['name'])}</strong><span>{escape(item['problem'])}</span></summary><div><p>{escape(item['summary'])}</p><div class='small-actions'><a href='../products/{escape(item['key'])}/index.html'>제품 보기</a><a href='../products/{escape(item['key'])}/demo/index.html'>즉시 데모</a></div></div></details>"
        for item in products
    )
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>가이드</span></div><span class="kicker">Guides</span><h1>처음 방문하셔도 어디서 시작할지 바로 보이도록 3단계로 줄였습니다</h1><p class="lead">제품 선택, 샘플 결과 확인, 가격 비교, 예외 문의만 남겨 처음 방문해도 덜 헤매도록 정리했습니다.</p><div class="actions"><a class="button" href="../products/index.html">제품 선택</a><a class="button secondary" href="../demo/index.html">즉시 데모</a><a class="button ghost" href="../pricing/index.html">가격 보기</a></div></div></div></section><section class="section compact"><div class="container"><div class="accordion-stack">{cards}</div></div></section></main>
    ''')
    return doc(brand, f"가이드 | {brand['name']}", '처음 방문한 팀을 위한 도입 가이드', 'guides', body, depth=1, page_key='guides', page_path='/guides/index.html')


def docs_page(brand: dict, products: list[dict]) -> str:
    cards = ''.join(
        f"<article class='story-card {escape(item['theme'])}'><span class='tag theme-chip'>{escape(item['label'])}</span><h3>{escape(item['name'])} 시작 안내</h3><p>{escape(item['summary'])}</p><ul class='clean'>{''.join(f'<li>{escape(text)}</li>' for text in item.get('samples', [])[:2])}</ul><div class='small-actions'><a href='../docs/{escape(item['key'])}/index.html'>문서 열기</a><a href='../products/{escape(item['key'])}/index.html'>제품 보기</a></div></article>"
        for item in products
    )
    body = f'<main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>문서 센터</span></div><span class="kicker">Docs</span><h1>제품 설명을 길게 읽기 전에, 준비물과 결과물부터 빠르게 확인할 수 있는 문서 허브입니다</h1><p class="lead">제품 소개를 끝까지 읽지 않으셔도 준비물, 샘플 성격, 결과물 구조를 먼저 판단하실 수 있도록 정리했습니다. 필요한 정보만 빠르게 골라 볼 수 있게 문서를 분리했습니다.</p><div class="actions"><a class="button" href="../products/index.html">제품 보기</a><a class="button secondary" href="../pricing/index.html">가격 보기</a><a class="button ghost" href="../faq/index.html">FAQ</a></div></div></div></section><section class="section compact"><div class="container"><div class="story-grid">{cards}</div></div></section></main>'
    return doc(brand, f"문서 센터 | {brand['name']}", '제품 시작 안내 문서 모음', 'docs', body, depth=1, page_key='docs', page_path='/docs/index.html')

def product_doc_page(brand: dict, product: dict) -> str:
    outputs = ''.join(f"<li>{escape(item)}</li>" for item in product.get('outputs', []))
    workflow = ''.join(f"<li>{escape(item)}</li>" for item in product.get('workflow', []))
    samples = ''.join(f"<li>{escape(item)}</li>" for item in product.get('samples', []))
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../index.html">HOME</a><span class="sep">/</span><a href="../index.html">문서 센터</a><span class="sep">/</span><span>{escape(product['name'])}</span></div><span class="tag theme-chip">{escape(product['label'])}</span><h1>{escape(product['name'])} 시작 안내</h1><p class="lead">무엇을 준비하면 되는지와 어떤 결과를 받게 되는지를 나눠 보여드려, 상세 페이지를 길게 읽지 않아도 판단하실 수 있게 했습니다.</p><div class="actions"><a class="button" href="../../products/{escape(product['key'])}/index.html">제품 보기</a><a class="button secondary" href="../../products/{escape(product['key'])}/demo/index.html">즉시 데모</a><a class="button ghost" href="../../products/{escape(product['key'])}/plans/index.html">플랜 보기</a></div></div></div></section><section class="section compact"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">준비물과 예시</span><ul class="clean">{samples}</ul></article><article class="card strong"><span class="tag theme-chip">받는 결과</span><ul class="clean">{outputs}</ul></article></div></section><section class="section compact"><div class="container"><article class="card strong"><span class="tag theme-chip">진행 흐름</span><ol class="flow-list">{workflow}</ol></article></div></section></main>
    ''')
    return doc(brand, f"{product['name']} 시작 안내 | {brand['name']}", f"{product['name']} 도입 준비 안내", 'product-doc', body, depth=2, page_key='docs-detail', page_path=f"/docs/{product['key']}/index.html", product_key=product['key'])

def cases_page(brand: dict, products: list[dict]) -> str:
    cards = []
    for item in products:
        topic = (item.get('board_automation', {}).get('topics') or [{}])[0]
        cards.append(f"<details class='fold-card'><summary><strong>{escape(topic.get('title') or item['name'])}</strong><span>{escape(item['problem'])}</span></summary><div><p>{escape(topic.get('summary') or item['summary'])}</p><div class='small-actions'><a href='../products/{escape(item['key'])}/index.html'>제품 보기</a><a href='../products/{escape(item['key'])}/board/index.html'>관련 글</a></div></div></details>")
    body = f'<main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>적용 사례</span></div><span class="kicker">Cases</span><h1>실제 상황을 먼저 보고 나에게 맞는 제품을 고르실 수 있습니다</h1><p class="lead">비슷한 상황인지 빠르게 확인하고, 필요할 때만 자세한 설명을 펼쳐 볼 수 있게 정리했습니다.</p></div></div></section><section class="section compact"><div class="container"><div class="accordion-stack">{"".join(cards)}</div></div></section></main>'
    return doc(brand, f"적용 사례 | {brand['name']}", '제품별 적용 사례', 'cases', body, depth=1, page_key='cases', page_path='/cases/index.html')


def faq_page(brand: dict, products: list[dict]) -> str:
    cards = ''.join(
        f"<details class='fold-card'><summary><strong>{escape(item['name'])}</strong><span>{escape(faq['q'])}</span></summary><div><p>{escape(faq['a'])}</p><div class='small-actions'><a href='../products/{escape(item['key'])}/faq/index.html'>제품 FAQ 더 보기</a><a href='../products/{escape(item['key'])}/index.html'>제품 보기</a></div></div></details>"
        for item in products for faq in item.get('faqs', [])[:2]
    )
    body = f'<main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>FAQ</span></div><span class="kicker">FAQ</span><h1>자주 묻는 질문만 먼저 모아 빠르게 판단하게 했습니다</h1><p class="lead">결제, 제공, 데모, 수정, 범위, 보안과 관련된 반복 질문을 먼저 확인하고, 필요한 경우에만 제품별 상세 FAQ로 들어가면 됩니다.</p><div class="actions"><a class="button" href="../pricing/index.html">가격 보기</a><a class="button secondary" href="../docs/index.html">문서 센터</a><a class="button ghost" href="../contact/index.html">예외 문의</a></div></div></div></section><section class="section compact"><div class="container"><div class="accordion-stack">{cards}</div></div></section></main>'
    return doc(brand, f"FAQ | {brand['name']}", '자주 묻는 질문', 'faq', body, depth=1, page_key='faq', page_path='/faq/index.html')

def legal_privacy_page(brand: dict) -> str:
    email = escape(brand.get('contact_email', ''))
    body = dedent(f"""    <main>
      <section class=\"section\"><div class=\"container page-hero\"><div class=\"card strong\"><div class=\"crumbs\"><a href=\"../../index.html\">HOME</a><span class=\"sep\">/</span><span>개인정보처리방침</span></div><h1>개인정보처리방침</h1><p class=\"lead\">NV0는 데모 요청, 주문·결제 준비, 결과 제공, 고객 포털 조회, 운영 감사에 필요한 범위 안에서만 개인정보를 처리합니다. 공개 화면과 관리자 화면을 분리하고, 각 단계마다 필요한 정보만 최소한으로 사용합니다.</p><div class=\"notice policy-meta-box\"><strong>시행일</strong> {POLICY_EFFECTIVE_DATE}<br><strong>최종 개정일</strong> {POLICY_UPDATED_DATE}<br><strong>문의</strong> <a href=\"mailto:{email}\">{email}</a></div><div class=\"small-actions\"><a href=\"../terms/index.html\">이용약관</a><a href=\"../refund/index.html\">환불정책</a><a href=\"../cookies/index.html\">쿠키 및 저장 안내</a></div></div></div></section>
      <section class=\"section compact\"><div class=\"container module-layout\"><article class=\"card strong\"><span class=\"tag\">처리 목적</span><div class=\"kv\"><div class=\"row\"><strong>데모/문의</strong><span>요청 접수, 샘플 결과 저장, 후속 안내</span></div><div class=\"row\"><strong>주문/결제</strong><span>주문 등록, 결제 확인, 결과 제공, 세금계산·정산 대응</span></div><div class=\"row\"><strong>고객 포털</strong><span>조회 코드와 이메일 기반 제공 상태 확인</span></div><div class=\"row\"><strong>운영 감사</strong><span>재발행, 상태 변경, 장애 대응, 보안 추적</span></div></div></article><article class=\"card strong\"><span class=\"tag\">수집 항목</span><div class=\"kv\"><div class=\"row\"><strong>필수 항목</strong><span>회사명, 담당자명, 이메일, 선택 제품, 요청 내용 또는 주문 정보</span></div><div class=\"row\"><strong>선택 항목</strong><span>전화번호, 참고 링크, 일정, 추가 요청 메모</span></div><div class=\"row\"><strong>결제 연동 항목</strong><span>플랜, 결제 상태, 조회 코드, 승인 확인에 필요한 기록</span></div><div class=\"row\"><strong>보관 원칙</strong><span>목적 달성 후 지체 없이 파기하며, 법령상 의무가 있는 경우에만 별도 분리 보관합니다.</span></div></div></article></div></section>
      <section class=\"section compact\"><div class=\"container module-layout\"><article class=\"card strong\"><span class=\"tag\">보유 기간·파기</span><ul class=\"clean\"><li>데모/문의 기록은 후속 응대와 분쟁 방지를 위한 최소 기간 동안만 관리합니다.</li><li>주문·결제 관련 정보는 거래 및 정산, 환불 대응에 필요한 범위 안에서만 보관합니다.</li><li>보관 목적이 끝난 정보는 복구가 어렵도록 삭제 또는 파기하며, 법령상 의무 보관분은 일반 운영 데이터와 분리합니다.</li></ul></article><article class=\"card strong\"><span class=\"tag\">제3자 제공·위탁</span><ul class=\"clean\"><li>결제 기능이 활성화된 경우 결제 완료 확인과 정산을 위해 필요한 최소 정보가 결제대행사에 전달될 수 있습니다.</li><li>결제, 발행, 저장, 알림에 외부 도구를 쓰는 경우에도 해당 목적 수행에 필요한 범위만 사용합니다.</li><li>브라우저 저장소는 상태 유지와 편의 기능을 위한 최소 범위에서만 사용합니다.</li></ul></article></div></section>
      <section class=\"section compact\"><div class=\"container module-layout\"><article class=\"card strong\"><span class=\"tag\">이용자 권리</span><ul class=\"clean\"><li>이용자는 언제든지 열람, 정정, 삭제, 처리 중단을 요청할 수 있습니다.</li><li>요청은 안내 이메일로 접수하며, 본인 확인이 필요한 경우 추가 확인을 요청할 수 있습니다.</li><li>처리 목적이 끝난 정보는 지체 없이 정리하고, 법령상 보존 의무 범위 밖의 정보는 별도 요청 없이도 단계적으로 제거합니다.</li></ul></article><article class=\"card strong\"><span class=\"tag\">안전성 확보 조치</span><ul class=\"clean\"><li>공개 화면과 관리자 화면을 분리하고, 관리자 인증 정보는 관리자 화면에서만 사용합니다.</li><li>운영 기록과 백업은 최소 접근 원칙으로 다루며, 변경 추적이 가능하도록 관리합니다.</li><li>보안 사고나 권익 침해 우려가 있는 경우 관련 법령과 내부 절차에 따라 대응합니다.</li></ul></article></div></section>
      <section class=\"section compact\"><div class=\"container\"><article class=\"card strong\"><span class=\"tag\">권익 침해 구제</span><p>개인정보 관련 문의는 먼저 안내 이메일로 접수하실 수 있습니다. 별도 분쟁 조정이나 침해 신고가 필요한 경우에는 개인정보보호위원회, 한국인터넷진흥원 등 관계 기관 절차를 이용하실 수 있습니다.</p></article></div></section>
    </main>
    """)
    return doc(brand, f"개인정보처리방침 | {brand['name']}", '개인정보 처리방침', 'legal', body, depth=2, page_key='privacy', page_path='/legal/privacy/index.html')


def legal_refund_page(brand: dict) -> str:
    email = escape(brand.get('contact_email', ''))
    body = dedent(f"""    <main>
      <section class=\"section\"><div class=\"container page-hero\"><div class=\"card strong\"><div class=\"crumbs\"><a href=\"../../index.html\">HOME</a><span class=\"sep\">/</span><span>환불정책</span></div><h1>환불정책</h1><p class=\"lead\">NV0는 업무 착수 전에는 전액 환불을 원칙으로 하고, 맞춤형 산출물 작성·검토·외부 비용이 이미 시작된 경우에는 진행 범위와 제공 결과물을 기준으로 부분 정산합니다. 결제 전 확인할 수 있도록 기준을 공개 화면에 먼저 정리합니다.</p><div class=\"notice policy-meta-box\"><strong>시행일</strong> {POLICY_EFFECTIVE_DATE}<br><strong>최종 개정일</strong> {POLICY_UPDATED_DATE}<br><strong>문의</strong> <a href=\"mailto:{email}\">{email}</a></div><div class=\"small-actions\"><a href=\"../terms/index.html\">이용약관</a><a href=\"../privacy/index.html\">개인정보처리방침</a></div></div></div></section>
      <section class=\"section compact\"><div class=\"container module-layout\"><article class=\"card strong\"><span class=\"tag\">환불 기준</span><div class=\"kv\"><div class=\"row\"><strong>업무 착수 전</strong><span>업무 미착수, 외부 비용 없음, 맞춤 결과물 미제공 시 전액 환불 원칙</span></div><div class=\"row\"><strong>업무 착수 후</strong><span>진행 범위, 투입 시간, 외부 비용, 제공된 결과물 범위를 기준으로 부분 정산</span></div><div class=\"row\"><strong>결제 수단</strong><span>승인 취소, 부분 취소, 환급 시점은 결제 사업자 및 카드사 정책에 따라 달라질 수 있습니다.</span></div><div class=\"row\"><strong>예외 범위</strong><span>맞춤 제작 성격이 강한 경우 이미 제공된 자료와 실비는 환불 대상에서 제외될 수 있습니다.</span></div></div></article><article class=\"card strong\"><span class=\"tag\">처리 순서</span><ol class=\"flow-list\"><li>환불 요청 접수</li><li>진행 상태·외부 비용·제공 결과물 확인</li><li>정산 기준과 예상 환급 범위 안내</li><li>승인 취소 또는 환급 처리</li></ol></article></div></section>
      <section class=\"section compact\"><div class=\"container module-layout\"><article class=\"card strong\"><span class=\"tag\">부분 정산 판단 예시</span><ul class=\"clean\"><li>결제 직후 바로 취소하고 작업이 시작되지 않은 경우: 전액 환불 원칙</li><li>데모 저장 또는 범위 확인만 끝난 상태에서 맞춤 산출물이 아직 제공되지 않은 경우: 실제 착수 여부 확인 후 전액 또는 소액 실비 정산</li><li>점검표, 수정안, 문구안 등 맞춤 자료가 일부라도 제공된 경우: 제공 범위와 실비를 반영해 부분 환불 가능</li><li>외부 결제 수수료나 별도 실비가 발생한 경우: 해당 비용은 제외 후 정산</li></ul></article><article class=\"card strong\"><span class=\"tag\">청약철회·제한</span><ul class=\"clean\"><li>전자상거래 관련 법령상 청약철회가 제한되는 맞춤 제작 성격의 서비스는 착수 후 범위가 달라질 수 있습니다.</li><li>고객 요청에 따라 개별 범위가 확정된 주문은 공개 정책보다 개별 계약서·견적서·주문 조건이 우선할 수 있습니다.</li><li>환불 가능 여부는 제공 전/후 상태, 이미 전달된 결과물, 외부 실비 발생 여부를 함께 봅니다.</li></ul></article></div></section>
    </main>
    """)
    return doc(brand, f"환불정책 | {brand['name']}", '환불 및 취소 기준', 'legal', body, depth=2, page_key='refund', page_path='/legal/refund/index.html')


def legal_cookies_page(brand: dict) -> str:
    email = escape(brand.get('contact_email', ''))
    body = dedent(f"""    <main>
      <section class=\"section\"><div class=\"container page-hero\"><div class=\"card strong\"><div class=\"crumbs\"><a href=\"../../index.html\">HOME</a><span class=\"sep\">/</span><span>쿠키 및 저장 안내</span></div><h1>쿠키 및 저장 안내</h1><p class=\"lead\">이 사이트는 데모, 문의, 결제 준비, 포털 조회 편의를 위해 브라우저 저장소를 사용할 수 있습니다. 저장 목적과 범위를 공개 화면과 관리자 화면으로 나누어 설명합니다.</p><div class=\"notice policy-meta-box\"><strong>시행일</strong> {POLICY_EFFECTIVE_DATE}<br><strong>최종 개정일</strong> {POLICY_UPDATED_DATE}<br><strong>문의</strong> <a href=\"mailto:{email}\">{email}</a></div></div></div></section>
      <section class=\"section compact\"><div class=\"container module-layout\"><article class=\"card strong\"><span class=\"tag\">저장 항목</span><div class=\"kv\"><div class=\"row\"><strong>세션 저장소</strong><span>관리자 화면의 임시 인증 상태, 일시적 진행 값</span></div><div class=\"row\"><strong>로컬 저장소</strong><span>데모, 문의, 주문, 공개 글 상태의 로컬 캐시와 편의 정보</span></div><div class=\"row\"><strong>보유 기간</strong><span>브라우저 또는 사용자가 직접 삭제할 때까지 유지될 수 있으며, 기능 필요 범위를 넘지 않게 사용합니다.</span></div><div class=\"row\"><strong>거부 영향</strong><span>브라우저 저장을 막으면 일부 편의 기능과 상태 유지가 제한될 수 있습니다.</span></div></div></article><article class=\"card strong\"><span class=\"tag\">원칙</span><ul class=\"clean\"><li>관리자 인증 정보는 관리자 화면에서만 사용하며, 공개 화면 기능과 섞지 않습니다.</li><li>브라우저 저장을 지우면 임시 기록과 편의 기능 상태가 함께 초기화될 수 있습니다.</li><li>추적·광고 목적의 저장이 추가될 경우 공개 정책을 먼저 갱신하고 안내합니다.</li></ul></article></div></section>
    </main>
    """)
    return doc(brand, f"쿠키 및 저장 안내 | {brand['name']}", '쿠키 및 브라우저 저장 안내', 'legal', body, depth=2, page_key='cookies', page_path='/legal/cookies/index.html')


def resources_page(brand: dict) -> str:
    body = dedent('''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>자료 허브</span></div><span class="kicker">Resources</span><h1>처음에는 핵심 자료만 짧게 보고, 더 필요할 때만 깊게 읽을 수 있게 나눴습니다</h1><p class="lead">문서, 사례, FAQ만 모아두는 데서 끝내지 않고, 문제별 시작 경로와 공통 엔진 설명, 확장 서비스까지 함께 이어지도록 정리했습니다. 고객은 길을 잃지 않고, 운영자는 같은 순서로 안내할 수 있습니다.</p><div class="actions"><a class="button" href="../docs/index.html">문서 센터</a><a class="button secondary" href="../solutions/index.html">문제별 시작</a><a class="button ghost" href="../engine/index.html">공통 엔진</a></div></div></div></section><section class="section compact"><div class="container"><div class="story-grid"><article class="story-card"><span class="tag">준비 판단</span><h3>문서 센터</h3><p>준비물, 전달물, 샘플 성격을 먼저 보고 도입 부담을 줄입니다.</p><div class="small-actions"><a href="../docs/index.html">문서 보기</a></div></article><article class="story-card"><span class="tag">문제 기준</span><h3>문제별 시작</h3><p>제품 이름보다 지금 가장 시급한 장면부터 골라 빠르게 방향을 잡습니다.</p><div class="small-actions"><a href="../solutions/index.html">문제별 시작 보기</a></div></article><article class="story-card"><span class="tag">구조 이해</span><h3>공통 엔진</h3><p>신청, 결제, 제공, 포털, 관리자 흐름이 어떻게 같은 기준으로 묶이는지 확인합니다.</p><div class="small-actions"><a href="../engine/index.html">엔진 보기</a></div></article><article class="story-card"><span class="tag">확장 판매</span><h3>확장 서비스</h3><p>핵심 제품에 붙일 수 있는 180개 확장 서비스를 빠르게 탐색합니다.</p><div class="small-actions"><a href="../service/index.html">확장 서비스 보기</a></div></article><article class="story-card"><span class="tag">실제 장면</span><h3>적용 사례</h3><p>실제 상황을 먼저 읽고 비슷한 팀인지부터 판단합니다.</p><div class="small-actions"><a href="../cases/index.html">사례 보기</a></div></article><article class="story-card"><span class="tag">빠른 정리</span><h3>FAQ</h3><p>자주 묻는 질문만 먼저 보고 결정을 늦추는 작은 불안을 줄입니다.</p><div class="small-actions"><a href="../faq/index.html">FAQ 보기</a></div></article></div></div></section></main>
    ''')
    return doc(brand, f"자료 허브 | {brand['name']}", '문서, 사례, FAQ 자료 허브', 'resources', body, depth=1, page_key='resources', page_path='/resources/index.html')


def service_page(brand: dict, data: dict) -> str:
    products = {item['key']: item for item in data.get('products', [])}
    catalog = data.get('service_catalog', [])
    categories = []
    grouped = {}
    for item in catalog:
        category = item.get('category', '기타 확장 서비스')
        if category not in grouped:
            grouped[category] = []
            categories.append(category)
        grouped[category].append(item)
    stats = (
        f"<article class='admin-card'><span class='tag'>확장 서비스</span><h3>{len(catalog)}</h3><p>즉시 판매 가능한 카탈로그 수</p></article>"
        f"<article class='admin-card'><span class='tag'>카테고리</span><h3>{len(categories)}</h3><p>묶음형 제안에 쓰는 범주 수</p></article>"
        f"<article class='admin-card'><span class='tag'>운영 기준</span><h3>1인 운영</h3><p>반복 작업을 자동화하고 예외만 따로 받는 구조</p></article>"
    )
    category_blocks = []
    for category in categories:
        items = grouped.get(category, [])
        cards = []
        for item in items:
            fit = [products[key]['name'] for key in item.get('fit_products', []) if key in products]
            lead = products.get(item.get('lead_product', ''), {}).get('name', item.get('lead_product', ''))
            fit_html = ''.join(f'<li>{escape(name)}</li>' for name in fit[:4]) or '<li>공통 제안형</li>'
            cards.append(
                f"<article class='story-card'><span class='tag'>{escape(item.get('id', ''))}</span><h3>{escape(item.get('name', '확장 서비스'))}</h3><p>{escape(item.get('summary', ''))}</p><ul class='clean'>{fit_html}<li>서비스 단계: {escape(item.get('service_stage', '기본정리'))}</li><li>서비스 유형: {escape(item.get('service_type', '정리형'))}</li><li>시작가: {escape(item.get('price_from', '문의'))}</li></ul><div class='small-actions'><span>주력 제품: {escape(lead or '공통')}</span><span>{escape(item.get('pricing_note', ''))}</span></div></article>"
            )
        category_blocks.append(
            f"<details class='fold-card' {'open' if category == categories[0] else ''}><summary><strong>{escape(category)}</strong><span>{len(items)}개 확장 서비스</span></summary><div><div class='story-grid'>{''.join(cards)}</div></div></details>"
        )
    body = dedent(f"""
    <main>
      <section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>확장 서비스</span></div><span class="kicker">Expansion catalog</span><h1>핵심 제품 1개로 시작하고, 필요한 기능만 확장 서비스로 붙일 수 있게 정리했습니다</h1><p class="lead">Veridion 같은 핵심 제품은 바로 구매하고, 세부 보완은 확장 서비스로 묶어 제안할 수 있게 설계했습니다. 1인 운영 기준으로 반복 업무는 자동화하고, 예외 요청만 문의로 분기하도록 구성했습니다.</p><div class="actions"><a class="button" href="../demo/index.html">즉시 데모</a><a class="button secondary" href="../pricing/index.html">가격 보기</a><a class="button ghost" href="../contact/index.html">예외 문의</a></div></div><div class="admin-grid">{stats}</div></div></section>
      <section class="section compact"><div class="container module-layout"><article class="card strong"><span class="tag">판매 구조</span><ol class="flow-list"><li>핵심 제품으로 문제를 먼저 진단합니다.</li><li>과태료 위험, 법령 변경, 고지 누락처럼 필요한 보완만 확장 서비스로 추가합니다.</li><li>반복 보수와 알림은 자동화하고, 운영자가 직접 보는 예외 건만 최소화합니다.</li><li>결제 후 포털에서 결과물, 발행 상태, 연결된 공개 글을 함께 확인합니다.</li></ol></article><article class="card strong"><span class="tag">추천 묶음</span><ul class="clean"><li>법률 진단 + 예상 과태료 미리보기 + 우선 수정 발행</li><li>법령 API 감시 + 변경 알림 + 즉시 수정 권고</li><li>결제·체크아웃 고지 보완 + 동의·정책 UI 개선</li><li>관리자 자동화 + 보고서/포털 + 재발행 운영</li></ul><div class="small-actions"><a href="../products/veridion/index.html">Veridion 보기</a><a href="../portal/index.html">고객 포털</a></div></article></div></section>
      <section class="section compact"><div class="container"><div class="card strong"><span class="tag">정밀 탐색</span><h2 style="margin:14px 0 10px">180개 확장 서비스를 짧게 훑고, 필요할 때 깊게 찾을 수 있게 정리했습니다</h2><p class="lead" style="font-size:1rem">키워드, 카테고리, 연결 제품 기준으로 빠르게 좁혀 보신 뒤, 바로 묶음 제안까지 이어가실 수 있습니다. 자바스크립트를 끄셔도 아래 전체 카탈로그를 그대로 읽으실 수 있습니다.</p><div class="form-grid service-filter-grid"><div><label for="service-search">검색</label><input id="service-search" type="search" placeholder="예: 과태료, 개인정보, 법령 API, 보고서"></div><div><label for="service-category-filter">카테고리</label><select id="service-category-filter"><option value="">전체 카테고리</option></select></div><div><label for="service-product-filter">연결 제품</label><select id="service-product-filter"><option value="">전체 제품</option></select></div><div><label for="service-stage-filter">서비스 단계</label><select id="service-stage-filter"><option value="">전체 서비스 단계</option></select></div></div><div class="admin-grid" id="service-catalog-stats"></div><div class="story-grid" id="service-catalog-results"></div></div></div></section>
      <section class="section compact"><div class="container"><div class="accordion-stack" id="service-catalog-fallback">{''.join(category_blocks)}</div></div></section>
    </main>
    """)
    return doc(brand, f"확장 서비스 | {brand['name']}", '핵심 제품에 붙여 판매할 수 있는 확장 서비스 카탈로그', 'service', body, depth=1, page_key='service', page_path='/service/index.html')


def onboarding_page(brand: dict) -> str:
    body = dedent('''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>도입 준비</span></div><span class="kicker">Onboarding</span><h1>준비물은 짧고 분명하게 안내하고, 실제 입력은 데모나 결제에서 바로 이어지게 했습니다</h1><p class="lead">대표 URL, 예시 문서, 현재 문장, 공고 링크처럼 핵심 예시 한 가지만 있어도 시작하실 수 있습니다. 처음부터 완벽하게 준비하지 않으셔도 괜찮습니다.</p><div class="actions"><a class="button" href="../demo/index.html">즉시 데모</a><a class="button secondary" href="../checkout/index.html">결제 진행</a></div></div></div></section></main>
    ''')
    return doc(brand, f"도입 준비 | {brand['name']}", '도입 준비 안내', 'onboarding', body, depth=1, page_key='onboarding', page_path='/onboarding/index.html')


def checkout_page_override(brand: dict, products: list[dict]) -> str:
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])} · {escape(item["plans"][0]["price"])}부터</option>' for item in products)
    body = dedent(f'''    <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>결제</span></div><span class="kicker">Checkout</span><h1>제품과 플랜만 고르고 바로 외부 결제로 넘어갑니다</h1><p class="lead">결제 전에는 꼭 필요한 선택만 남겼습니다. 회사명, 담당자명, 이메일, 사이트 주소 같은 진행 정보는 결제 완료 후 한 번에 입력하도록 분리했습니다.</p><form id="checkout-form" class="stack-form"><input type="hidden" name="billing" value="one-time"><input type="hidden" name="paymentMethod" value="toss"><div class="form-grid"><div><label>제품</label><select name="product" data-prefill="product" required>{options}</select></div><div><label>플랜</label><select name="plan" data-prefill="plan" required><option value="Lite">Lite</option><option value="Starter">Starter</option><option value="Growth">Growth</option><option value="Scale">Scale</option></select></div></div>{consent_notice('../', 'checkout')}<div class="notice" id="checkout-plan-summary" data-plan-summary="checkout" aria-live="polite">선택한 제품과 플랜 요약이 여기에 표시됩니다.</div><div class="actions"><button class="button" type="submit">외부 결제로 바로 이동</button></div></form><div class="result-box" id="checkout-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">결제 후 진행 순서</span><ol class="flow-list"><li>제품과 플랜 선택</li><li>외부 결제 진행</li><li>회사명·담당자명·이메일·사이트 주소 입력</li><li>결과 준비 및 포털 연결</li></ol></article></div></section></main>
    ''')
    return doc(brand, f"결제 | {brand['name']}", '제품 결제 및 자동 제공 진입', 'checkout', body, depth=1, page_key='checkout', page_path='/checkout/index.html')


def demo_page_override(brand: dict, products: list[dict]) -> str:
    body = dedent(f'''    <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>즉시 데모</span></div><span class="kicker">Instant demo</span><h1>사이트 주소를 넣으면 즉시 위험 요약을 보여드립니다</h1><p class="lead">저장형 폼이 아니라 실제 사이트 기준 즉시 진단 화면입니다. 위기 점수, 예상 과태료, 문제 영역별 건수, 상위 위험 항목을 먼저 확인한 뒤 결제 여부를 판단하실 수 있습니다.</p><form id="demo-form" class="stack-form"><input type="hidden" name="product" value="veridion"><div class="form-grid"><div class="span-2"><label>사이트 주소</label><input name="website" placeholder="https://example.com" inputmode="url" autocomplete="url" required></div><div><label>업종</label><select name="industry"><option value="commerce">이커머스</option><option value="beauty">뷰티·웰니스</option><option value="healthcare">의료·건강</option><option value="education">교육·서비스</option><option value="saas">B2B SaaS</option></select></div><div><label>주요 운영 국가</label><select name="country"><option value="KR" selected>대한민국</option><option value="US">미국</option><option value="JP">일본</option><option value="CN">중국</option><option value="EU">유럽연합</option><option value="SEA">동남아</option><option value="GLOBAL">글로벌</option></select></div><div><label>중점 확인 사항</label><select name="focus" data-demo-field="focus"><option value="전체 리스크 빠르게 보기">전체 리스크 빠르게 보기</option><option value="개인정보·회원가입 동선">개인정보·회원가입 동선</option><option value="결제·환불·청약철회 고지">결제·환불·청약철회 고지</option><option value="광고·표시 문구">광고·표시 문구</option><option value="약관·정책 문서 일치">약관·정책 문서 일치</option><option value="민감 업종·표현 위험">민감 업종·표현 위험</option></select></div></div><div class="notice notice-light smart-focus-note"><strong>자동 추천 적용</strong><br>대한민국 운영 기준으로 <strong>결제·환불·청약철회 고지</strong>을 우선 점검하도록 맞췄습니다.</div><div class="actions"><button class="button" type="submit">즉시 분석하기</button><a class="button ghost" href="../checkout/index.html?product=veridion&plan=Starter">바로 결제</a></div></form><div class="result-box" id="demo-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">무료 데모에서 먼저 보는 항목</span><ul class="clean"><li>실제 읽은 페이지 기준 요약</li><li>위기 점수와 상위 위험 신호</li><li>예상 노출/과태료 범위</li><li>문제 영역별 건수</li></ul></article></div></section></main>
    ''')
    return doc(brand, f"빠른 체험 | {brand['name']}", '제품 빠른 체험', 'demo', body, depth=1, page_key='demo', page_path='/demo/index.html')


def contact_page_override(brand: dict, products: list[dict]) -> str:
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])} </option>' for item in products)
    body = dedent(f'''    <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>예외 문의</span></div><span class="kicker">Contact</span><h1>자동 흐름으로 바로 판단하기 어려운 조건만 따로 남기실 수 있게 줄였습니다</h1><p class="lead">일반적인 검토는 제품 페이지, 즉시 데모, 결제로 충분하도록 구성했습니다. 이곳에서는 세금계산서, 계약 범위, 특수 일정처럼 예외적인 조건만 따로 남겨 더 빠르게 확인할 수 있습니다.</p><form id="contact-form"><div class="form-grid"><div><label>관심 제품</label><select name="product" data-prefill="product" required><option value="">선택</option>{options}</select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>전화번호 (선택)</label><input name="phone" placeholder="연락 가능한 번호"></div><div><label>회신 희망 시간 (선택)</label><input name="replyWindow" placeholder="예: 평일 2~5시"></div><div><label>긴급도 (선택)</label><select name="urgency"><option value="">선택 안 함</option><option value="normal">일반</option><option value="soon">이번 주 내</option><option value="urgent">긴급</option></select></div><div><label>참고 링크 (선택)</label><input name="link" placeholder="대표 URL 또는 문서 링크"></div><div class="span-2"><label>확인 내용</label><textarea name="issue" rows="4" placeholder="예: 계약서, 세금계산서, 일정 조율, 공개 범위, 보안 요구사항" required></textarea></div></div>{consent_notice('../', 'contact')}<div class="actions"><button class="button" type="submit">예외 문의 남기기</button><a class="button ghost" href="../demo/index.html">즉시 데모로 돌아가기</a></div></form><div class="result-box" id="contact-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">권장 경로</span><ul class="clean"><li>먼저 제품 상세 또는 가격 페이지를 확인합니다.</li><li>즉시 데모로 방향을 확인합니다.</li><li>결제가 가능한 경우 바로 진행합니다.</li><li>정말 예외가 있을 때만 이 폼을 사용합니다.</li></ul></article></div></section></main>
    ''')
    return doc(brand, f"예외 문의 | {brand['name']}", '예외 조건 확인', 'contact', body, depth=1, page_key='contact', page_path='/contact/index.html')


def portal_alias_page(brand: dict) -> str:
    body = dedent('''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>결제 상태 확인</span></div><span class="kicker">Billing</span><h1>결제 상태와 결과 제공 상태는 고객 포털에서 확인하실 수 있습니다</h1><p class="lead">기존 billing 경로 대신 고객 포털로 바로 안내합니다.</p><div class="actions"><a class="button" href="../portal/index.html">고객 포털로 이동</a><a class="button ghost" href="../checkout/index.html">결제 다시 보기</a></div></div></div></section></main>
    ''')
    return doc(brand, f"결제 상태 확인 | {brand['name']}", '결제 상태 확인 안내', 'billing', body, depth=1, page_key='billing', page_path='/billing/index.html')


def board_post_alias_page(brand: dict) -> str:
    body = dedent('''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../index.html">HOME</a><span class="sep">/</span><a href="../index.html">자료실</a><span class="sep">/</span><span>글 보기</span></div><span class="kicker">Board</span><h1>공개 글은 자료실 허브에서 바로 확인하실 수 있습니다</h1><p class="lead">내부 작성 기능은 숨기고, 고객이 읽기 좋은 공개 허브만 남겼습니다.</p><div class="actions"><a class="button" href="../index.html">자료실 허브 보기</a><a class="button secondary" href="../../products/index.html">제품 보기</a></div></div></div></section></main>
    ''')
    return doc(brand, f"자료실 글 | {brand['name']}", '자료실 글 읽기 안내', 'board-post', body, depth=2, page_key='board-post', page_path='/board/post/index.html')


def product_demo_page(brand: dict, product: dict) -> str:
    sample_points = ''.join(f'<li>{escape(item)}</li>' for item in product.get('samples', []))
    demo_form = '<div id="product-demo-shell"></div>'
    if product['key'] == 'veridion':
        demo_form = '''<form id="product-demo-form" class="stack-form"><div class="form-grid"><div class="span-2"><label>사이트 주소</label><input name="website" data-demo-field="website" placeholder="https://example.com" inputmode="url" autocomplete="url" required></div><div><label>업종</label><select name="industry" data-demo-field="industry"><option value="commerce">이커머스</option><option value="beauty">뷰티·웰니스</option><option value="healthcare">의료·건강</option><option value="education">교육·서비스</option><option value="saas">B2B SaaS</option></select></div><div><label>운영 국가</label><select name="country" data-demo-field="country"><option value="KR" selected>대한민국</option><option value="US">미국</option><option value="JP">일본</option><option value="CN">중국</option><option value="EU">유럽연합</option><option value="SEA">동남아</option><option value="GLOBAL">글로벌</option></select></div><div><label>중점 확인 사항</label><select name="focus" data-demo-field="focus"><option value="전체 리스크 빠르게 보기">전체 리스크 빠르게 보기</option><option value="개인정보·회원가입 동선">개인정보·회원가입 동선</option><option value="결제·환불·청약철회 고지">결제·환불·청약철회 고지</option><option value="광고·표시 문구">광고·표시 문구</option><option value="약관·정책 문서 일치">약관·정책 문서 일치</option><option value="민감 업종·표현 위험">민감 업종·표현 위험</option></select></div></div><div class="notice notice-light smart-focus-note"><strong>자동 추천 적용</strong><br>대한민국 운영 기준으로 <strong>결제·환불·청약철회 고지</strong>을 우선 점검하도록 맞췄습니다.</div><div class="actions"><button class="button" type="submit">즉시 분석하기</button><a class="button ghost" href="#order">바로 결제</a></div></form>'''
    elif product['key'] == 'clearport':
        demo_form = '''<form id="product-demo-form" class="stack-form"><div class="form-grid"><div><label>제출 유형</label><input name="submissionType" data-demo-field="submissionType" placeholder="예: 입찰, 등록, 제휴"></div><div><label>마감일</label><input name="deadline" data-demo-field="deadline" type="date"></div><div><label>제출처</label><input name="targetOrg" data-demo-field="targetOrg" placeholder="예: 공공기관, 거래처"></div><div><label>팀 규모</label><input name="teamSize" data-demo-field="teamSize" placeholder="예: 2인 운영팀"></div><div class="span-2"><label>막히는 지점</label><input name="blocker" data-demo-field="blocker" placeholder="예: 서류 누락, 회신 지연"></div></div><div class="actions"><button class="button" type="submit">샘플 결과 보기</button><a class="button ghost" href="#order">바로 결제</a></div></form>'''
    elif product['key'] == 'grantops':
        demo_form = '''<form id="product-demo-form" class="stack-form"><div class="form-grid"><div><label>사업/공모명</label><input name="projectName" data-demo-field="projectName" placeholder="예: 창업 지원사업"></div><div><label>마감일</label><input name="deadline" data-demo-field="deadline" type="date"></div><div><label>현재 진행률</label><select name="progress" data-demo-field="progress"><option>자료 수집 전</option><option>초안 작성 중</option><option>검토 중</option><option>마감 직전</option></select></div><div><label>참여 인원</label><input name="contributors" data-demo-field="contributors" placeholder="예: 3명"></div><div class="span-2"><label>지연 포인트</label><input name="delayPoint" data-demo-field="delayPoint" placeholder="예: 증빙 수집, 승인 지연"></div></div><div class="actions"><button class="button" type="submit">샘플 결과 보기</button><a class="button ghost" href="#order">바로 결제</a></div></form>'''
    elif product['key'] == 'draftforge':
        demo_form = '''<form id="product-demo-form" class="stack-form"><div class="form-grid"><div><label>문서 종류</label><input name="docType" data-demo-field="docType" placeholder="예: 제안서, 보고서"></div><div><label>현재 버전 상태</label><select name="versionState" data-demo-field="versionState"><option>최신본이 정리되어 있음</option><option>초안만 있음</option><option>수정본이 여러 개 흩어져 있음</option></select></div><div><label>승인 단계</label><input name="approvalSteps" data-demo-field="approvalSteps" placeholder="예: 3단계"></div><div><label>주요 채널</label><input name="channel" data-demo-field="channel" placeholder="예: 이메일, 메신저"></div><div class="span-2"><label>가장 큰 문제</label><input name="draftPain" data-demo-field="draftPain" placeholder="예: 최신본 혼선, 승인 지연"></div></div><div class="actions"><button class="button" type="submit">샘플 결과 보기</button><a class="button ghost" href="#order">바로 결제</a></div></form>'''
    body = dedent(f'''    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../../index.html">HOME</a><span class="sep">/</span><a href="../../index.html">제품</a><span class="sep">/</span><a href="../index.html">{escape(product['name'])}</a><span class="sep">/</span><span>즉시 데모</span></div><span class="tag theme-chip">{escape(product['label'])}</span><h1>{escape(product['name'])} 즉시 데모</h1><p class="lead">소개 문장보다 실제 결과를 먼저 보여주는 화면입니다. 저장형 문의가 아니라 즉시 분석 중심으로 바꿨습니다.</p>{product_subnav('../../../', product, 'demo')}</div><div class="card theme-panel"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">먼저 보는 항목</span><ul class="clean inverse-list">{sample_points}</ul></div></div></section><section class="section compact"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">즉시 분석</span>{demo_form}<div class="result-box" id="product-demo-result" role="status" aria-live="polite"></div></article><article class="card strong"><span class="tag theme-chip">분석 후 바로 이어지는 단계</span><ol class="flow-list"><li>핵심 위험 요약 확인</li><li>문제 영역별 건수 확인</li><li>바로 결제 또는 제품 설명 확인</li></ol><div class="small-actions"><a href="../index.html#order">바로 결제</a><a href="../board/index.html">자료실 보기</a></div></article></div></section></main>
    ''')
    return doc(brand, f"{product['name']} 데모 | {brand['name']}", f"{product['name']} 즉시 데모", product['theme'], body, depth=3, page_key='product-demo', page_path=f"/products/{product['key']}/demo/index.html", product_key=product['key'])


def product_plans_page(brand: dict, product: dict) -> str:
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../../index.html">HOME</a><span class="sep">/</span><a href="../../index.html">제품</a><span class="sep">/</span><a href="../index.html">{escape(product['name'])}</a><span class="sep">/</span><span>플랜</span></div><span class="tag theme-chip">{escape(product['label'])}</span><h1>{escape(product['name'])} 플랜</h1><p class="lead">가격과 포함 범위를 별도 페이지로 분리해 길게 스크롤하지 않아도 비교하실 수 있게 했습니다. 추천 플랜은 표시하고, 예외 조건은 별도 문의로 분기합니다.</p>{product_subnav('../../../', product, 'plans')}</div><div class="card theme-panel"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">가격 기준</span><h3 style="font-size:1.72rem;margin:16px 0 10px">{escape(product['plans'][0]['price'])}부터 시작합니다</h3><p>{escape(product.get('pricing_basis', ''))}</p><div class="small-actions"><a href="../../../legal/refund/index.html">환불 정책</a><a href="../../../contact/index.html?product={escape(product['key'])}">예외 문의</a></div></div></div></section><section class="section compact"><div class="container"><div class="plan-grid">{''.join(_ for _ in [plan_cards_markup(product, '../../../')])}</div></div></section></main>
    ''')
    return doc(brand, f"{product['name']} 플랜 | {brand['name']}", f"{product['name']} 플랜 안내", product['theme'], body, depth=3, page_key='product-plans', page_path=f"/products/{product['key']}/plans/index.html", product_key=product['key'])

def product_delivery_page(brand: dict, product: dict) -> str:
    workflow = ''.join(f'<li>{escape(item)}</li>' for item in product.get('workflow', []))
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../../index.html">HOME</a><span class="sep">/</span><a href="../../index.html">제품</a><span class="sep">/</span><a href="../index.html">{escape(product['name'])}</a><span class="sep">/</span><span>제공 흐름</span></div><span class="tag theme-chip">{escape(product['label'])}</span><h1>{escape(product['name'])} 제공 흐름</h1><p class="lead">결제 후 무엇을 받게 되는지 한눈에 이해하실 수 있도록 별도 페이지로 분리했습니다.</p>{product_subnav('../../../', product, 'delivery')}</div></div></section><section class="section compact"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">결과 전달 흐름</span><ol class="flow-list">{workflow}</ol></article><article class="card strong"><span class="tag theme-chip">포털 확인</span><details class="fold-card" open><summary><strong>핵심만 먼저</strong><span>결제 후에는 조회 코드로 결과와 진행 상태를 확인하실 수 있습니다.</span></summary><div><ul class="clean"><li>결제 완료 뒤 조회 코드 발급</li><li>포털에서 전달 상태 확인</li><li>연결된 공개 글과 결과물 다시 확인</li></ul><div class="small-actions"><a href="../../../portal/index.html">고객 포털</a><a href="../plans/index.html">플랜 다시 보기</a></div></div></details></article></div></section></main>
    ''')
    return doc(brand, f"{product['name']} 제공 흐름 | {brand['name']}", f"{product['name']} 제공 흐름", product['theme'], body, depth=3, page_key='product-delivery', page_path=f"/products/{product['key']}/delivery/index.html", product_key=product['key'])


def product_faq_page(brand: dict, product: dict) -> str:
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../../index.html">HOME</a><span class="sep">/</span><a href="../../index.html">제품</a><span class="sep">/</span><a href="../index.html">{escape(product['name'])}</a><span class="sep">/</span><span>FAQ</span></div><span class="tag theme-chip">{escape(product['label'])}</span><h1>{escape(product['name'])} FAQ</h1><p class="lead">질문은 한 곳에 모으고, 답변은 필요한 것만 빠르게 확인할 수 있게 정리했습니다.</p>{product_subnav('../../../', product, 'faq')}</div></div></section><section class="section compact"><div class="container"><div class="accordion-stack">{faq_details(product)}</div></div></section></main>
    ''')
    return doc(brand, f"{product['name']} FAQ | {brand['name']}", f"{product['name']} FAQ", product['theme'], body, depth=3, page_key='product-faq', page_path=f"/products/{product['key']}/faq/index.html", product_key=product['key'])


def generate_compat_pages(dist: Path, data: dict):
    brand = data['brand']
    products = data['products']
    pages = {
        dist / 'pricing' / 'index.html': pricing_page(brand, products),
        dist / 'guides' / 'index.html': guides_page(brand, products),
        dist / 'docs' / 'index.html': docs_page(brand, products),
        dist / 'cases' / 'index.html': cases_page(brand, products),
        dist / 'faq' / 'index.html': faq_page(brand, products),
        dist / 'resources' / 'index.html': resources_page(brand),
        dist / 'service' / 'index.html': service_page(brand, data),
        dist / 'onboarding' / 'index.html': onboarding_page(brand),
        dist / 'legal' / 'privacy' / 'index.html': legal_privacy_page(brand),
        dist / 'legal' / 'refund' / 'index.html': legal_refund_page(brand),
        dist / 'legal' / 'cookies' / 'index.html': legal_cookies_page(brand),
        dist / 'checkout' / 'index.html': checkout_page_override(brand, products),
        dist / 'demo' / 'index.html': demo_page_override(brand, products),
        dist / 'contact' / 'index.html': contact_page_override(brand, products),
        dist / 'billing' / 'index.html': portal_alias_page(brand),
        dist / 'board' / 'post' / 'index.html': board_post_alias_page(brand),
    }
    for path, content in pages.items():
        write(path, content)
    for product in products:
        write(dist / 'docs' / product['key'] / 'index.html', product_doc_page(brand, product))
        write(dist / 'products' / product['key'] / 'demo' / 'index.html', product_demo_page(brand, product))
        write(dist / 'products' / product['key'] / 'plans' / 'index.html', product_plans_page(brand, product))
        write(dist / 'products' / product['key'] / 'delivery' / 'index.html', product_delivery_page(brand, product))
        write(dist / 'products' / product['key'] / 'faq' / 'index.html', product_faq_page(brand, product))


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    generate_compat_pages(root / 'dist', json.loads((root / 'src' / 'data' / 'site.json').read_text(encoding='utf-8')))
