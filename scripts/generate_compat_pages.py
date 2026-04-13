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


def doc(brand: dict, title: str, description: str, body_class: str, body: str, *, depth: int, page_key: str, page_path: str, product_key: str | None = None):
    prefix = rel_prefix(depth)
    attrs = [f'class="{body_class}"', f'data-page="{page_key}"']
    if product_key:
        attrs.append(f'data-product="{product_key}"')
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
  <link rel="canonical" href="{escape(page_url(brand, page_path))}">
  <link rel="stylesheet" href="{prefix}assets/site.css">
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
        f'<details class="fold-card"><summary><strong>{escape(item["q"])}</strong><span>핵심 답을 먼저 확인할 수 있습니다.</span></summary><div><p>{escape(item["a"])}</p></div></details>'
        for item in product.get('faqs', [])
    )


def pricing_page(brand: dict, products: list[dict]) -> str:
    rows = ''.join(
        f"<tr><td><strong>{escape(item['name'])}</strong><br><small>{escape(item['headline'])}</small></td>"
        f"<td>{escape(item['plans'][0]['price'])}</td><td>{escape(item['plans'][1]['price'])}</td><td>{escape(item['plans'][2]['price'])}</td>"
        f"<td>{escape(item['outputs'][0])}</td></tr>"
        for item in products
    )
    cards = ''.join(
        f"<details class='fold-card'><summary><strong>{escape(item['name'])}</strong><span>시작가 {escape(item['plans'][0]['price'])}</span></summary><div><p>{escape(item['pricing_basis'])}</p><div class='small-actions'><a href='../products/{escape(item['key'])}/index.html'>제품 보기</a><a href='../products/{escape(item['key'])}/demo/index.html'>즉시 데모</a><a href='../products/{escape(item['key'])}/plans/index.html'>플랜 보기</a></div></div></details>"
        for item in products
    )
    body = dedent(f'''
    <main>
      <section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>가격</span></div><span class="kicker">Pricing</span><h1>가격, 범위, 1회 결제형 자료를 한 번에 비교하고 바로 시작할 수 있습니다</h1><p class="lead">제품별 시작가와 추천 플랜을 먼저 보여주고, 범위와 근거는 접힘/펼침으로 확인할 수 있게 정리했습니다.</p><div class="actions"><a class="button" href="../demo/index.html">즉시 데모</a><a class="button secondary" href="../products/index.html">제품 선택</a><a class="button ghost" href="../contact/index.html">예외 문의</a></div></div></div></section>
      <section class="section compact"><div class="container"><div class="table-wrap"><table><thead><tr><th>제품</th><th>Starter</th><th>Growth</th><th>Scale</th><th>대표 결과물</th></tr></thead><tbody>{rows}</tbody></table></div></div></section>
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
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>가이드</span></div><span class="kicker">Guides</span><h1>어디서 시작할지 3단계로 줄였습니다</h1><p class="lead">제품 선택, 즉시 데모, 예외 문의만 남기고 불필요한 절차를 줄였습니다.</p><div class="actions"><a class="button" href="../products/index.html">제품 선택</a><a class="button secondary" href="../demo/index.html">즉시 데모</a><a class="button ghost" href="../pricing/index.html">가격 보기</a></div></div></div></section><section class="section compact"><div class="container"><div class="accordion-stack">{cards}</div></div></section></main>
    ''')
    return doc(brand, f"가이드 | {brand['name']}", '처음 방문한 팀을 위한 도입 가이드', 'guides', body, depth=1, page_key='guides', page_path='/guides/index.html')


def docs_page(brand: dict, products: list[dict]) -> str:
    cards = ''.join(
        f"<article class='story-card {escape(item['theme'])}'><span class='tag theme-chip'>{escape(item['label'])}</span><h3>{escape(item['name'])} 시작 안내</h3><p>{escape(item['summary'])}</p><div class='small-actions'><a href='../docs/{escape(item['key'])}/index.html'>문서 열기</a><a href='../products/{escape(item['key'])}/index.html'>제품 보기</a></div></article>"
        for item in products
    )
    body = f'<main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>문서 센터</span></div><span class="kicker">Docs</span><h1>실제 판단에 필요한 문서를 먼저 보실 수 있습니다</h1><p class="lead">준비물과 결과물은 문서 페이지로 분리해 상세 페이지를 다 읽지 않아도 판단할 수 있게 했습니다.</p></div></div></section><section class="section compact"><div class="container"><div class="story-grid">{cards}</div></div></section></main>'
    return doc(brand, f"문서 센터 | {brand['name']}", '제품 시작 안내 문서 모음', 'docs', body, depth=1, page_key='docs', page_path='/docs/index.html')


def product_doc_page(brand: dict, product: dict) -> str:
    outputs = ''.join(f"<li>{escape(item)}</li>" for item in product.get('outputs', []))
    workflow = ''.join(f"<li>{escape(item)}</li>" for item in product.get('workflow', []))
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../index.html">HOME</a><span class="sep">/</span><a href="../index.html">문서 센터</a><span class="sep">/</span><span>{escape(product['name'])}</span></div><span class="tag theme-chip">{escape(product['label'])}</span><h1>{escape(product['name'])} 시작 안내</h1><p class="lead">준비물과 결과물을 분리해 보여드려, 상세 페이지를 다 읽지 않아도 판단할 수 있게 했습니다.</p><div class="actions"><a class="button" href="../../products/{escape(product['key'])}/index.html">제품 보기</a><a class="button secondary" href="../../products/{escape(product['key'])}/demo/index.html">즉시 데모</a><a class="button ghost" href="../../products/{escape(product['key'])}/plans/index.html">플랜 보기</a></div></div></div></section><section class="section compact"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">받는 결과</span><ul class="clean">{outputs}</ul></article><article class="card strong"><span class="tag theme-chip">진행 흐름</span><ol class="flow-list">{workflow}</ol></article></div></section></main>
    ''')
    return doc(brand, f"{product['name']} 시작 안내 | {brand['name']}", f"{product['name']} 도입 준비 안내", 'product-doc', body, depth=2, page_key='docs-detail', page_path=f"/docs/{product['key']}/index.html", product_key=product['key'])


def cases_page(brand: dict, products: list[dict]) -> str:
    cards = []
    for item in products:
        topic = (item.get('board_automation', {}).get('topics') or [{}])[0]
        cards.append(f"<details class='fold-card'><summary><strong>{escape(topic.get('title') or item['name'])}</strong><span>{escape(item['problem'])}</span></summary><div><p>{escape(topic.get('summary') or item['summary'])}</p><div class='small-actions'><a href='../products/{escape(item['key'])}/index.html'>제품 보기</a><a href='../products/{escape(item['key'])}/board/index.html'>관련 글</a></div></div></details>")
    body = f'<main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>적용 사례</span></div><span class="kicker">Cases</span><h1>실제 장면을 먼저 보고 제품을 고르실 수 있습니다</h1><p class="lead">사례는 짧게, 자세한 맥락은 펼쳐서 볼 수 있도록 접힘/펼침 구조로 바꿨습니다.</p></div></div></section><section class="section compact"><div class="container"><div class="accordion-stack">{"".join(cards)}</div></div></section></main>'
    return doc(brand, f"적용 사례 | {brand['name']}", '제품별 적용 사례', 'cases', body, depth=1, page_key='cases', page_path='/cases/index.html')


def faq_page(brand: dict, products: list[dict]) -> str:
    cards = ''.join(
        f"<details class='fold-card'><summary><strong>{escape(item['name'])}</strong><span>{escape(faq['q'])}</span></summary><div><p>{escape(faq['a'])}</p><div class='small-actions'><a href='../products/{escape(item['key'])}/faq/index.html'>제품 FAQ 더 보기</a><a href='../products/{escape(item['key'])}/index.html'>제품 보기</a></div></div></details>"
        for item in products for faq in item.get('faqs', [])[:2]
    )
    body = f'<main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>FAQ</span></div><span class="kicker">FAQ</span><h1>질문은 한곳에 모으고 답은 펼쳐서 보게 했습니다</h1><p class="lead">한 번에 다 보여주지 않고 핵심 질문부터 빠르게 읽을 수 있게 정리했습니다.</p></div></div></section><section class="section compact"><div class="container"><div class="accordion-stack">{cards}</div></div></section></main>'
    return doc(brand, f"FAQ | {brand['name']}", '자주 묻는 질문', 'faq', body, depth=1, page_key='faq', page_path='/faq/index.html')


def legal_privacy_page(brand: dict) -> str:
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../index.html">HOME</a><span class="sep">/</span><span>개인정보처리방침</span></div><h1>개인정보처리방침</h1><p class="lead">추가 확인, 데모 시연, 결제 진행, 포털 조회에 필요한 최소 범위의 정보를 처리합니다. 결제 연동이 활성화된 경우 결제 완료 확인과 정산을 위해 필요한 최소 정보만 결제대행사로 전달될 수 있습니다.</p><div class="kv"><div class="row"><strong>안내 이메일</strong><span>{escape(brand.get('contact_email',''))}</span></div><div class="row"><strong>주요 처리 목적</strong><span>문의 응대, 데모 저장, 결제 진행, 결과 제공, 포털 조회, 운영 기록 관리</span></div><div class="row"><strong>주요 항목</strong><span>회사명, 담당자명, 이메일, 요청 내용, 선택 제품, 결제 상태 확인 정보</span></div><div class="row"><strong>보관 원칙</strong><span>업무 목적 달성 후 지체 없이 파기하고, 법령상 보존 의무가 있을 때만 별도 보관합니다.</span></div></div></div></div></section></main>
    ''')
    return doc(brand, f"개인정보처리방침 | {brand['name']}", '개인정보 처리방침', 'legal', body, depth=2, page_key='privacy', page_path='/legal/privacy/index.html')


def legal_refund_page(brand: dict) -> str:
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../index.html">HOME</a><span class="sep">/</span><span>환불정책</span></div><h1>환불정책</h1><p class="lead">업무 착수 전에는 전액 환불을 원칙으로 하고, 맞춤형 산출물 작성이나 외부 비용이 시작된 뒤에는 진행 범위와 제공된 결과물을 기준으로 정산합니다.</p><div class="kv"><div class="row"><strong>착수 전</strong><span>업무 미착수, 외부 비용 없음, 맞춤 산출물 미제공 시 전액 환불 원칙</span></div><div class="row"><strong>착수 후</strong><span>진행 범위, 투입 시간, 외부 비용, 제공 완료 결과물 기준으로 부분 정산</span></div><div class="row"><strong>접수 채널</strong><span>{escape(brand.get('contact_email',''))}</span></div></div></div></div></section></main>
    ''')
    return doc(brand, f"환불정책 | {brand['name']}", '환불 및 취소 기준', 'legal', body, depth=2, page_key='refund', page_path='/legal/refund/index.html')


def legal_cookies_page(brand: dict) -> str:
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../index.html">HOME</a><span class="sep">/</span><span>쿠키 및 저장 안내</span></div><h1>쿠키 및 저장 안내</h1><p class="lead">이 사이트는 데모·문의·포털 확인 편의를 위해 브라우저 저장소를 사용할 수 있습니다. 관리자 토큰은 세션 저장소를 사용하며 브라우저를 닫으면 사라집니다.</p><div class="kv"><div class="row"><strong>세션 저장소</strong><span>관리자 토큰 임시 저장</span></div><div class="row"><strong>로컬 저장소</strong><span>데모, 문의, 주문, 공개 글 상태의 로컬 캐시</span></div><div class="row"><strong>거부 영향</strong><span>브라우저 저장을 막으면 일부 편의 기능과 상태 유지가 제한될 수 있습니다.</span></div></div></div></div></section></main>
    ''')
    return doc(brand, f"쿠키 및 저장 안내 | {brand['name']}", '쿠키 및 브라우저 저장 안내', 'legal', body, depth=2, page_key='cookies', page_path='/legal/cookies/index.html')


def resources_page(brand: dict) -> str:
    body = dedent('''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>자료 허브</span></div><span class="kicker">Resources</span><h1>문서, 사례, FAQ를 역할별로 나눠 한 번에 몰리지 않게 정리했습니다</h1><p class="lead">자료 허브는 출발점 역할만 담당하고, 실제 상세 내용은 문서·사례·FAQ 페이지로 나눠 보여줍니다.</p><div class="actions"><a class="button" href="../docs/index.html">문서 센터</a><a class="button secondary" href="../cases/index.html">적용 사례</a><a class="button ghost" href="../faq/index.html">FAQ</a></div></div></div></section></main>
    ''')
    return doc(brand, f"자료 허브 | {brand['name']}", '문서, 사례, FAQ 자료 허브', 'resources', body, depth=1, page_key='resources', page_path='/resources/index.html')


def service_page(brand: dict) -> str:
    body = dedent('''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>진행 흐름</span></div><span class="kicker">Service flow</span><h1>시작부터 제공까지 단계를 줄이고 끊김 없이 이어지게 정리했습니다</h1><p class="lead">제품 선택 → 즉시 데모 → 결제 → 포털 확인 흐름만 핵심으로 남기고, 예외 문의는 별도 페이지로 분리했습니다.</p><div class="actions"><a class="button" href="../demo/index.html">즉시 데모</a><a class="button secondary" href="../checkout/index.html">결제 진행</a><a class="button ghost" href="../portal/index.html">고객 포털</a></div></div></div></section></main>
    ''')
    return doc(brand, f"진행 흐름 | {brand['name']}", '시작 후 제공 흐름', 'service', body, depth=1, page_key='service', page_path='/service/index.html')


def onboarding_page(brand: dict) -> str:
    body = dedent('''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>도입 준비</span></div><span class="kicker">Onboarding</span><h1>준비물은 짧게 안내하고 실제 입력은 데모나 결제에서 바로 이어집니다</h1><p class="lead">대표 URL, 예시 문서, 현재 문장이나 공고 링크처럼 핵심 예시 1개만 있어도 충분합니다.</p><div class="actions"><a class="button" href="../demo/index.html">즉시 데모</a><a class="button secondary" href="../checkout/index.html">결제 진행</a></div></div></div></section></main>
    ''')
    return doc(brand, f"도입 준비 | {brand['name']}", '도입 준비 안내', 'onboarding', body, depth=1, page_key='onboarding', page_path='/onboarding/index.html')


def checkout_page_override(brand: dict, products: list[dict]) -> str:
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])} · {escape(item["plans"][0]["price"])}부터</option>' for item in products)
    body = dedent(f'''
    <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>결제</span></div><span class="kicker">Checkout</span><h1>꼭 필요한 항목만 입력하고 바로 결제로 이어지게 바꿨습니다</h1><p class="lead">제품, 플랜, 회사명, 담당자명, 이메일만 있으면 결제 준비를 시작할 수 있습니다. 자세한 맥락은 메모에 한 줄만 남기면 됩니다.</p><form id="checkout-form"><div class="form-grid"><div><label>제품</label><select name="product" data-prefill="product" required>{options}</select></div><div><label>플랜</label><select name="plan" data-prefill="plan" required><option value="Starter">Starter</option><option value="Growth">Growth</option><option value="Scale">Scale</option></select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>추가 요청</label><input name="note" placeholder="선택 입력"></div><div><label>결제 유형</label><select name="billing"><option value="one-time">1회 결제형</option></select></div><div><label>결제 방식</label><select name="paymentMethod" required><option value="toss">Toss 결제</option></select></div></div><div class="actions"><button class="button" type="submit">결제 진행하기</button><a class="button ghost" href="../pricing/index.html">가격 먼저 보기</a></div></form><div class="result-box" id="checkout-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">간단 안내</span><details class="fold-card" open><summary><strong>핵심만 먼저</strong><span>결제 완료 후 포털에서 결과와 제공 상태를 확인합니다.</span></summary><div><ol class="flow-list"><li>결제 준비 정보 저장</li><li>외부 결제창 이동</li><li>결제 완료 확인</li><li>결과물 및 공개 글 연결</li><li>포털 조회 코드 확인</li></ol></div></details></article></div></section></main>
    ''')
    return doc(brand, f"결제 | {brand['name']}", '제품 결제 및 자동 제공 진입', 'checkout', body, depth=1, page_key='checkout', page_path='/checkout/index.html')


def demo_page_override(brand: dict, products: list[dict]) -> str:
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])} · {escape(item["problem"][:28])}</option>' for item in products)
    quick_cards = ''.join(
        f"<article class='story-card {escape(item['theme'])}'><span class='tag theme-chip'>{escape(item['label'])}</span><h3>{escape(item['name'])}</h3><p>{escape(item['headline'])}</p><div class='small-actions'><button type='button' data-quick-demo='{escape(item['key'])}' data-quick-scenario='0'>즉시 미리보기</button><a href='../products/{escape(item['key'])}/demo/index.html'>상세 데모</a></div></article>"
        for item in products
    )
    body = dedent(f'''
    <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>데모</span></div><span class="kicker">Quick demo</span><h1>버튼 한 번으로 샘플을 먼저 보고, 원하면 저장까지 이어가게 바꿨습니다</h1><p class="lead">즉시 미리보기로 방향을 먼저 확인하고, 저장이 필요할 때만 아래 폼을 쓰시면 됩니다.</p><div class="quick-demo-grid">{quick_cards}</div><form id="demo-form"><div class="form-grid"><div><label>제품</label><select name="product" data-prefill="product" required>{options}</select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>팀 규모</label><input name="team" placeholder="예: 3인 운영팀"></div><div><label>목표</label><input name="goal" placeholder="예: 첫 화면에서 바로 이해되게" required></div><div><label>핵심 키워드</label><input name="keywords" placeholder="예: 신뢰, CTA, 전환"></div></div><div class="actions"><button class="button" type="submit">샘플 저장하고 데모 시연 자료 받기</button></div></form><div class="result-box" id="demo-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">바로 가기</span><h3>자세한 흐름은 제품별 페이지로 나눴습니다</h3><div class="story-grid" id="module-matrix"></div></article></div></section></main>
    ''')
    return doc(brand, f"빠른 체험 | {brand['name']}", '제품 빠른 체험', 'demo', body, depth=1, page_key='demo', page_path='/demo/index.html')


def contact_page_override(brand: dict, products: list[dict]) -> str:
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])} </option>' for item in products)
    body = dedent(f'''
    <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>예외 문의</span></div><span class="kicker">Contact</span><h1>자동 흐름으로 바로 판단하기 어려운 경우만 따로 남기도록 줄였습니다</h1><p class="lead">일반적인 검토는 제품 페이지와 즉시 데모, 결제로 충분합니다. 여기서는 세금계산서, 계약 범위, 특수 일정처럼 예외적인 조건만 받습니다.</p><form id="contact-form"><div class="form-grid"><div><label>관심 제품</label><select name="product" data-prefill="product" required><option value="">선택</option>{options}</select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>확인 내용</label><input name="issue" placeholder="예: 계약서, 세금계산서, 일정 조율" required></div></div><div class="actions"><button class="button" type="submit">예외 문의 남기기</button><a class="button ghost" href="../demo/index.html">즉시 데모로 돌아가기</a></div></form><div class="result-box" id="contact-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">권장 경로</span><ul class="clean"><li>먼저 제품 상세 또는 가격 페이지를 확인합니다.</li><li>즉시 데모로 방향을 확인합니다.</li><li>결제가 가능한 경우 바로 진행합니다.</li><li>정말 예외가 있을 때만 이 폼을 사용합니다.</li></ul></article></div></section></main>
    ''')
    return doc(brand, f"예외 문의 | {brand['name']}", '예외 조건 확인', 'contact', body, depth=1, page_key='contact', page_path='/contact/index.html')


def portal_alias_page(brand: dict) -> str:
    body = dedent('''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>결제 상태 확인</span></div><span class="kicker">Billing</span><h1>결제 상태와 결과 제공 상태는 고객 포털에서 확인하실 수 있습니다</h1><p class="lead">기존 billing 경로를 대신해 고객 포털로 안내합니다.</p><div class="actions"><a class="button" href="../portal/index.html">고객 포털로 이동</a><a class="button ghost" href="../checkout/index.html">결제 다시 보기</a></div></div></div></section></main>
    ''')
    return doc(brand, f"결제 상태 확인 | {brand['name']}", '결제 상태 확인 안내', 'billing', body, depth=1, page_key='billing', page_path='/billing/index.html')


def board_post_alias_page(brand: dict) -> str:
    body = dedent('''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../index.html">HOME</a><span class="sep">/</span><a href="../index.html">게시판</a><span class="sep">/</span><span>글 보기</span></div><span class="kicker">Board</span><h1>공개 글은 게시판 허브에서 바로 확인하실 수 있습니다</h1><p class="lead">수동 작성이나 관리용 기능을 공개 경로에 두지 않고, 읽기 중심 허브로 정리했습니다.</p><div class="actions"><a class="button" href="../index.html">게시판 허브 보기</a><a class="button secondary" href="../../products/index.html">제품 보기</a></div></div></div></section></main>
    ''')
    return doc(brand, f"게시판 글 | {brand['name']}", '게시판 글 읽기 안내', 'board-post', body, depth=2, page_key='board-post', page_path='/board/post/index.html')


def product_demo_page(brand: dict, product: dict) -> str:
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../../index.html">HOME</a><span class="sep">/</span><a href="../../index.html">제품</a><span class="sep">/</span><a href="../index.html">{escape(product['name'])}</a><span class="sep">/</span><span>즉시 데모</span></div><span class="tag theme-chip">{escape(product['label'])}</span><h1>{escape(product['name'])} 즉시 데모</h1><p class="lead">미리보기 버튼으로 방향을 먼저 보고, 아래 폼으로 저장까지 이어갈 수 있습니다.</p>{product_subnav('../../../', product, 'demo')}</div></div></section><section class="section compact"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">빠른 미리보기</span><div class="quick-demo-grid">{''.join(f'<button class="quick-demo-button" type="button" data-quick-demo="{escape(product["key"])}" data-quick-scenario="{idx}">{escape((item if isinstance(item, str) else str(item))[:32])}</button>' for idx, item in enumerate(product.get('demo_scenarios', [])[:4]))}</div><div class="result-box" id="quick-demo-result" role="status" aria-live="polite"></div></article><article class="card strong"><span class="tag theme-chip">저장하기</span><form id="product-demo-form" class="stack-form"><div class="form-grid"><div><label>회사명</label><input name="company" data-demo-field="company" placeholder="샘플 브랜드" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" data-demo-field="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" data-demo-field="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>팀 규모</label><input name="team" data-demo-field="team" placeholder="예: 2인 운영팀"></div><div><label>목표</label><input name="goal" data-demo-field="goal" placeholder="예: CTA 전환 개선" required></div><div><label>핵심 키워드</label><input name="keywords" data-demo-field="keywords" placeholder="예: 랜딩, CTA, 신뢰"></div><div><label>플랜 미리보기</label><select name="plan" data-demo-field="plan"><option value="Starter">Starter</option><option value="Growth">Growth</option><option value="Scale">Scale</option></select></div></div><div class="actions"><button class="button" type="submit">샘플 저장하기</button><a class="button ghost" href="../plans/index.html">플랜 보기</a></div></form><div class="result-box" id="product-demo-result" role="status" aria-live="polite"></div></article></div></section></main>
    ''')
    return doc(brand, f"{product['name']} 데모 | {brand['name']}", f"{product['name']} 즉시 데모", product['theme'], body, depth=3, page_key='product-demo', page_path=f"/products/{product['key']}/demo/index.html", product_key=product['key'])


def product_plans_page(brand: dict, product: dict) -> str:
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../../index.html">HOME</a><span class="sep">/</span><a href="../../index.html">제품</a><span class="sep">/</span><a href="../index.html">{escape(product['name'])}</a><span class="sep">/</span><span>플랜</span></div><span class="tag theme-chip">{escape(product['label'])}</span><h1>{escape(product['name'])} 플랜</h1><p class="lead">가격과 범위를 별도 페이지로 분리해 길게 스크롤하지 않아도 비교할 수 있게 했습니다.</p>{product_subnav('../../../', product, 'plans')}</div><div class="card theme-panel"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">가격 기준</span><h3 style="font-size:1.72rem;margin:16px 0 10px">{escape(product['plans'][0]['price'])}부터 시작합니다</h3><p>{escape(product.get('pricing_basis', ''))}</p></div></div></section><section class="section compact"><div class="container"><div class="plan-grid">{''.join(_ for _ in [plan_cards_markup(product, '../../../')])}</div></div></section></main>
    ''')
    return doc(brand, f"{product['name']} 플랜 | {brand['name']}", f"{product['name']} 플랜 안내", product['theme'], body, depth=3, page_key='product-plans', page_path=f"/products/{product['key']}/plans/index.html", product_key=product['key'])


def product_delivery_page(brand: dict, product: dict) -> str:
    workflow = ''.join(f'<li>{escape(item)}</li>' for item in product.get('workflow', []))
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../../index.html">HOME</a><span class="sep">/</span><a href="../../index.html">제품</a><span class="sep">/</span><a href="../index.html">{escape(product['name'])}</a><span class="sep">/</span><span>제공 흐름</span></div><span class="tag theme-chip">{escape(product['label'])}</span><h1>{escape(product['name'])} 제공 흐름</h1><p class="lead">결제 후 무엇이 자동으로 이어지는지 한눈에 보이도록 별도 페이지로 분리했습니다.</p>{product_subnav('../../../', product, 'delivery')}</div></div></section><section class="section compact"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">정상작동 및 발행 제공</span><ol class="flow-list">{workflow}</ol></article><article class="card strong"><span class="tag theme-chip">포털 확인</span><details class="fold-card" open><summary><strong>핵심만 먼저</strong><span>결제 후 조회 코드로 결과를 확인합니다.</span></summary><div><ul class="clean"><li>결제 완료 뒤 조회 코드 발급</li><li>포털에서 제공 상태 확인</li><li>연결된 공개 글과 결과물 다시 확인</li></ul><div class="small-actions"><a href="../../../portal/index.html">고객 포털</a><a href="../plans/index.html">플랜 다시 보기</a></div></div></details></article></div></section></main>
    ''')
    return doc(brand, f"{product['name']} 제공 흐름 | {brand['name']}", f"{product['name']} 제공 흐름", product['theme'], body, depth=3, page_key='product-delivery', page_path=f"/products/{product['key']}/delivery/index.html", product_key=product['key'])


def product_faq_page(brand: dict, product: dict) -> str:
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../../index.html">HOME</a><span class="sep">/</span><a href="../../index.html">제품</a><span class="sep">/</span><a href="../index.html">{escape(product['name'])}</a><span class="sep">/</span><span>FAQ</span></div><span class="tag theme-chip">{escape(product['label'])}</span><h1>{escape(product['name'])} FAQ</h1><p class="lead">질문은 한 곳에 모으고, 답변은 접힘/펼침으로 정리해 한눈에 보기 쉽게 바꿨습니다.</p>{product_subnav('../../../', product, 'faq')}</div></div></section><section class="section compact"><div class="container"><div class="accordion-stack">{faq_details(product)}</div></div></section></main>
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
        dist / 'service' / 'index.html': service_page(brand),
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
