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
        f"<details class='fold-card'><summary><strong>{escape(item['name'])}</strong><span>시작가 {escape(item['plans'][0]['price'])} · 추천 {escape(next((plan['name'] for plan in item['plans'] if plan.get('recommended')), item['plans'][0]['name']))}</span></summary><div><p>{escape(item['pricing_basis'])}</p><ul class='clean'>{''.join(f'<li>{escape(text)}</li>' for text in item.get('samples', [])[:3])}</ul><div class='small-actions'><a href='../products/{escape(item['key'])}/index.html'>제품 보기</a><a href='../products/{escape(item['key'])}/demo/index.html'>즉시 데모</a><a href='../products/{escape(item['key'])}/plans/index.html'>플랜 보기</a></div></div></details>"
        for item in products
    )
    body = dedent(f'''
    <main>
      <section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>가격</span></div><span class="kicker">Pricing</span><h1>가격, 범위, 1회 결제형 전달물을 한 번에 비교하고 바로 시작할 수 있습니다</h1><p class="lead">제품별 시작가와 추천 플랜을 먼저 보여주고, 근거와 샘플 성격은 접힘/펼침으로 확인할 수 있게 정리했습니다. 기업 정산이나 예외 범위는 별도 문의에서 분기합니다.</p><div class="actions"><a class="button" href="../demo/index.html">즉시 데모</a><a class="button secondary" href="../products/index.html">제품 선택</a><a class="button ghost" href="../contact/index.html">예외 문의</a></div></div><div class="card"><span class="tag">핵심 안내</span><ul class="clean"><li>온라인 결제는 현재 1회 결제형 기준입니다.</li><li>플랜별 납기와 수정 횟수는 제품별 플랜 페이지에서 확인합니다.</li><li>세금계산서와 계약 범위 예외는 문의 페이지에서 분기합니다.</li></ul><div class="small-actions"><a href="../legal/refund/index.html">환불 정책</a><a href="../legal/terms/index.html">이용약관</a></div></div></div></section>
      <section class="section compact"><div class="container"><div class="table-wrap"><table><thead><tr><th>제품</th><th>Starter</th><th>Growth</th><th>Scale</th><th>대표 전달물</th></tr></thead><tbody>{rows}</tbody></table></div></div></section>
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
        f"<article class='story-card {escape(item['theme'])}'><span class='tag theme-chip'>{escape(item['label'])}</span><h3>{escape(item['name'])} 시작 안내</h3><p>{escape(item['summary'])}</p><ul class='clean'>{''.join(f'<li>{escape(text)}</li>' for text in item.get('samples', [])[:2])}</ul><div class='small-actions'><a href='../docs/{escape(item['key'])}/index.html'>문서 열기</a><a href='../products/{escape(item['key'])}/index.html'>제품 보기</a></div></article>"
        for item in products
    )
    body = f'<main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>문서 센터</span></div><span class="kicker">Docs</span><h1>판단에 필요한 준비물과 전달물을 먼저 보는 문서 허브입니다</h1><p class="lead">제품 소개를 다 읽지 않아도 준비물, 샘플 성격, 결과물 구조를 먼저 판단할 수 있게 정리했습니다. 각 문서는 제품별 요약 화면과 분리해 과밀을 줄였습니다.</p><div class="actions"><a class="button" href="../products/index.html">제품 보기</a><a class="button secondary" href="../pricing/index.html">가격 보기</a><a class="button ghost" href="../faq/index.html">FAQ</a></div></div></div></section><section class="section compact"><div class="container"><div class="story-grid">{cards}</div></div></section></main>'
    return doc(brand, f"문서 센터 | {brand['name']}", '제품 시작 안내 문서 모음', 'docs', body, depth=1, page_key='docs', page_path='/docs/index.html')

def product_doc_page(brand: dict, product: dict) -> str:
    outputs = ''.join(f"<li>{escape(item)}</li>" for item in product.get('outputs', []))
    workflow = ''.join(f"<li>{escape(item)}</li>" for item in product.get('workflow', []))
    samples = ''.join(f"<li>{escape(item)}</li>" for item in product.get('samples', []))
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../index.html">HOME</a><span class="sep">/</span><a href="../index.html">문서 센터</a><span class="sep">/</span><span>{escape(product['name'])}</span></div><span class="tag theme-chip">{escape(product['label'])}</span><h1>{escape(product['name'])} 시작 안내</h1><p class="lead">준비물과 결과물을 분리해 보여드려, 상세 페이지를 다 읽지 않아도 판단할 수 있게 했습니다.</p><div class="actions"><a class="button" href="../../products/{escape(product['key'])}/index.html">제품 보기</a><a class="button secondary" href="../../products/{escape(product['key'])}/demo/index.html">즉시 데모</a><a class="button ghost" href="../../products/{escape(product['key'])}/plans/index.html">플랜 보기</a></div></div></div></section><section class="section compact"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">준비물과 예시</span><ul class="clean">{samples}</ul></article><article class="card strong"><span class="tag theme-chip">받는 결과</span><ul class="clean">{outputs}</ul></article></div></section><section class="section compact"><div class="container"><article class="card strong"><span class="tag theme-chip">진행 흐름</span><ol class="flow-list">{workflow}</ol></article></div></section></main>
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
    body = f'<main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>FAQ</span></div><span class="kicker">FAQ</span><h1>자주 묻는 질문만 먼저 모아 빠르게 판단하게 했습니다</h1><p class="lead">결제, 제공, 데모, 수정, 범위, 보안과 관련된 반복 질문을 먼저 확인하고, 필요한 경우에만 제품별 상세 FAQ로 들어가면 됩니다.</p><div class="actions"><a class="button" href="../pricing/index.html">가격 보기</a><a class="button secondary" href="../docs/index.html">문서 센터</a><a class="button ghost" href="../contact/index.html">예외 문의</a></div></div></div></section><section class="section compact"><div class="container"><div class="accordion-stack">{cards}</div></div></section></main>'
    return doc(brand, f"FAQ | {brand['name']}", '자주 묻는 질문', 'faq', body, depth=1, page_key='faq', page_path='/faq/index.html')

def legal_privacy_page(brand: dict) -> str:
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../index.html">HOME</a><span class="sep">/</span><span>개인정보처리방침</span></div><h1>개인정보처리방침</h1><p class="lead">NV0는 데모, 결제, 예외 문의, 포털 조회에 필요한 최소 정보만 처리합니다. 공개 화면과 관리자 화면을 분리해 고객용 화면에서 운영용 정보가 불필요하게 드러나지 않도록 관리합니다.</p><div class="small-actions"><a href="mailto:{escape(brand.get('contact_email',''))}">{escape(brand.get('contact_email',''))}</a><a href="../terms/index.html">이용약관</a><a href="../refund/index.html">환불정책</a></div></div></div></section><section class="section compact"><div class="container module-layout"><article class="card strong"><span class="tag">처리 목적</span><div class="kv"><div class="row"><strong>문의/데모</strong><span>요청 접수, 샘플 저장, 후속 안내</span></div><div class="row"><strong>결제</strong><span>주문 등록, 결제 확인, 결과 제공</span></div><div class="row"><strong>포털</strong><span>조회 코드 기반 상태 확인</span></div><div class="row"><strong>운영 기록</strong><span>재발행, 상태 변경, 감사 추적</span></div></div></article><article class="card strong"><span class="tag">주요 항목</span><div class="kv"><div class="row"><strong>기본 항목</strong><span>회사명, 담당자명, 이메일, 선택 제품, 요청 내용</span></div><div class="row"><strong>결제 항목</strong><span>플랜, 결제 상태, 조회 코드, 결제 결과 확인 정보</span></div><div class="row"><strong>선택 항목</strong><span>전화번호, 참고 링크, 일정, 추가 요청 메모</span></div><div class="row"><strong>보관 원칙</strong><span>업무 목적 달성 후 지체 없이 파기하고, 법령상 보존 의무가 있을 때만 별도 보관합니다.</span></div></div></article></div></section><section class="section compact"><div class="container"><article class="card strong"><span class="tag">추가 안내</span><ul class="clean"><li>결제 연동이 활성화된 경우 결제 완료 확인과 정산을 위해 필요한 최소 정보만 결제대행사로 전달될 수 있습니다.</li><li>공개 사이트와 관리자 화면은 분리되어 있으며, 관리자 인증 정보는 관리자 화면에서만 사용됩니다.</li><li>이용자는 언제든지 안내 이메일로 열람·정정·삭제를 요청할 수 있습니다.</li></ul></article></div></section></main>
    ''')
    return doc(brand, f"개인정보처리방침 | {brand['name']}", '개인정보 처리방침', 'legal', body, depth=2, page_key='privacy', page_path='/legal/privacy/index.html')

def legal_refund_page(brand: dict) -> str:
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../index.html">HOME</a><span class="sep">/</span><span>환불정책</span></div><h1>환불정책</h1><p class="lead">업무 착수 전에는 전액 환불을 원칙으로 하고, 맞춤형 산출물 작성이나 외부 비용이 시작된 뒤에는 진행 범위와 제공된 결과물을 기준으로 정산합니다.</p><div class="small-actions"><a href="mailto:{escape(brand.get('contact_email',''))}">{escape(brand.get('contact_email',''))}</a><a href="../terms/index.html">이용약관</a></div></div></div></section><section class="section compact"><div class="container module-layout"><article class="card strong"><span class="tag">환불 기준</span><div class="kv"><div class="row"><strong>착수 전</strong><span>업무 미착수, 외부 비용 없음, 맞춤 산출물 미제공 시 전액 환불 원칙</span></div><div class="row"><strong>착수 후</strong><span>진행 범위, 투입 시간, 외부 비용, 제공 완료 결과물 기준으로 부분 정산</span></div><div class="row"><strong>예상 처리</strong><span>요청 접수 후 확인 순서에 따라 안내 이메일로 처리 기준을 안내합니다.</span></div></div></article><article class="card strong"><span class="tag">예시</span><ul class="clean"><li>결제 직후 바로 취소하고 작업이 시작되지 않은 경우: 전액 환불 원칙</li><li>데모/검토를 마치고 맞춤 산출물이 일부 제공된 경우: 진행분 정산 후 부분 환불 가능</li><li>외부 결제 수수료나 별도 실비가 발생한 경우: 해당 비용은 제외 후 정산</li></ul></article></div></section></main>
    ''')
    return doc(brand, f"환불정책 | {brand['name']}", '환불 및 취소 기준', 'legal', body, depth=2, page_key='refund', page_path='/legal/refund/index.html')

def legal_cookies_page(brand: dict) -> str:
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../index.html">HOME</a><span class="sep">/</span><span>쿠키 및 저장 안내</span></div><h1>쿠키 및 저장 안내</h1><p class="lead">이 사이트는 데모, 문의, 결제 준비, 포털 조회 편의를 위해 브라우저 저장소를 사용할 수 있습니다. 고객용 공개 화면과 관리자용 인증 정보는 저장 목적과 범위를 다르게 관리합니다.</p></div></div></section><section class="section compact"><div class="container module-layout"><article class="card strong"><span class="tag">저장 항목</span><div class="kv"><div class="row"><strong>세션 저장소</strong><span>관리자 화면 접속 시 임시 인증 토큰 저장</span></div><div class="row"><strong>로컬 저장소</strong><span>데모, 문의, 주문, 공개 글 상태의 로컬 캐시</span></div><div class="row"><strong>거부 영향</strong><span>브라우저 저장을 막으면 일부 편의 기능과 상태 유지가 제한될 수 있습니다.</span></div></div></article><article class="card strong"><span class="tag">원칙</span><ul class="clean"><li>관리자 인증 정보는 관리자 화면에서만 사용합니다.</li><li>공개 화면에는 운영 기능을 노출하지 않도록 분리합니다.</li><li>브라우저 저장을 지우면 임시 기록과 편의 기능 상태가 함께 초기화됩니다.</li></ul></article></div></section></main>
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
    <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>결제</span></div><span class="kicker">Checkout</span><h1>결제 전 꼭 필요한 정보만 남기고, 범위 확인은 옆 카드로 분리했습니다</h1><p class="lead">제품, 플랜, 회사명, 담당자명, 이메일만 있으면 결제 준비를 시작할 수 있습니다. 추가 조건은 메모와 선택 항목으로만 받도록 줄였습니다.</p><form id="checkout-form"><div class="form-grid"><div><label>제품</label><select name="product" data-prefill="product" required>{options}</select></div><div><label>플랜</label><select name="plan" data-prefill="plan" required><option value="Starter">Starter</option><option value="Growth">Growth</option><option value="Scale">Scale</option></select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>전화번호 (선택)</label><input name="phone" placeholder="연락 가능한 번호"></div><div><label>참고 링크 (선택)</label><input name="referenceUrl" placeholder="대표 URL 또는 문서 링크"></div><div><label>긴급도 (선택)</label><select name="urgency"><option value="">선택 안 함</option><option value="normal">일반</option><option value="soon">이번 주 내</option><option value="urgent">긴급</option></select></div><div><label>정산 방식</label><select name="billing"><option value="one-time">1회 결제형</option></select></div><div><label>결제 방식</label><select name="paymentMethod" required><option value="toss">Toss 결제</option></select></div><div class="span-2"><label>추가 요청</label><textarea name="note" rows="4" placeholder="원하는 톤, 꼭 포함할 내용, 세금계산서 필요 여부 등"></textarea></div></div><div class="actions"><button class="button" type="submit">결제 진행하기</button><a class="button ghost" href="../pricing/index.html">가격 먼저 보기</a></div></form><div class="result-box" id="checkout-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">핵심 안내</span><details class="fold-card" open><summary><strong>결제 전에 확인할 것</strong><span>환불/약관/포털 흐름을 먼저 확인할 수 있습니다.</span></summary><div><ol class="flow-list"><li>제품과 플랜 확인</li><li>결제 준비 정보 저장</li><li>외부 결제창 이동</li><li>결제 완료 후 포털 조회 코드 확인</li></ol><div class="small-actions"><a href="../legal/refund/index.html">환불 정책</a><a href="../legal/terms/index.html">이용약관</a><a href="../portal/index.html">고객 포털</a></div></div></details></article></div></section></main>
    ''')
    return doc(brand, f"결제 | {brand['name']}", '제품 결제 및 자동 제공 진입', 'checkout', body, depth=1, page_key='checkout', page_path='/checkout/index.html')

def demo_page_override(brand: dict, products: list[dict]) -> str:
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])} · {escape(item["problem"][:28])}</option>' for item in products)
    quick_cards = ''.join(
        f"<article class='story-card {escape(item['theme'])}'><span class='tag theme-chip'>{escape(item['label'])}</span><h3>{escape(item['name'])}</h3><p>{escape(item['headline'])}</p><div class='small-actions'><button type='button' data-quick-demo='{escape(item['key'])}' data-quick-scenario='0'>즉시 미리보기</button><a href='../products/{escape(item['key'])}/demo/index.html'>상세 데모</a></div></article>"
        for item in products
    )
    body = dedent(f'''
    <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>데모</span></div><span class="kicker">Quick demo</span><h1>폼보다 먼저 미리보기를 보여주고, 저장은 선택으로 두었습니다</h1><p class="lead">즉시 미리보기로 방향을 먼저 확인하고, 저장이 필요할 때만 아래 폼을 쓰시면 됩니다. 제품별 상세 데모는 각 모듈 페이지에서 더 깊게 이어집니다.</p><div class="quick-demo-grid">{quick_cards}</div><form id="demo-form"><div class="form-grid"><div><label>제품</label><select name="product" data-prefill="product" required>{options}</select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>팀 규모</label><input name="team" placeholder="예: 3인 운영팀"></div><div><label>목표</label><input name="goal" placeholder="예: 첫 화면에서 바로 이해되게" required></div><div><label>핵심 키워드</label><input name="keywords" placeholder="예: 신뢰, CTA, 전환"></div><div><label>참고 링크 (선택)</label><input name="referenceUrl" placeholder="대표 URL 또는 참고 문서"></div><div class="span-2"><label>추가 메모 (선택)</label><textarea name="context" rows="4" placeholder="꼭 보고 싶은 장면이나 현재 가장 답답한 지점을 적어 주세요"></textarea></div></div><div class="actions"><button class="button" type="submit">샘플 저장하고 데모 시연 자료 받기</button></div></form><div class="result-box" id="demo-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">바로 가기</span><h3>자세한 흐름은 제품별 페이지로 나눴습니다</h3><div class="story-grid" id="module-matrix"></div></article></div></section></main>
    ''')
    return doc(brand, f"빠른 체험 | {brand['name']}", '제품 빠른 체험', 'demo', body, depth=1, page_key='demo', page_path='/demo/index.html')

def contact_page_override(brand: dict, products: list[dict]) -> str:
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])} </option>' for item in products)
    body = dedent(f'''
    <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>예외 문의</span></div><span class="kicker">Contact</span><h1>자동 흐름으로 바로 판단하기 어려운 조건만 따로 남기게 줄였습니다</h1><p class="lead">일반적인 검토는 제품 페이지와 즉시 데모, 결제로 충분합니다. 여기서는 세금계산서, 계약 범위, 특수 일정처럼 예외적인 조건만 받습니다.</p><form id="contact-form"><div class="form-grid"><div><label>관심 제품</label><select name="product" data-prefill="product" required><option value="">선택</option>{options}</select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>전화번호 (선택)</label><input name="phone" placeholder="연락 가능한 번호"></div><div><label>회신 희망 시간 (선택)</label><input name="replyWindow" placeholder="예: 평일 2~5시"></div><div><label>긴급도 (선택)</label><select name="urgency"><option value="">선택 안 함</option><option value="normal">일반</option><option value="soon">이번 주 내</option><option value="urgent">긴급</option></select></div><div><label>참고 링크 (선택)</label><input name="referenceUrl" placeholder="대표 URL 또는 문서 링크"></div><div class="span-2"><label>확인 내용</label><textarea name="issue" rows="4" placeholder="예: 계약서, 세금계산서, 일정 조율, 공개 범위, 보안 요구사항" required></textarea></div></div><div class="actions"><button class="button" type="submit">예외 문의 남기기</button><a class="button ghost" href="../demo/index.html">즉시 데모로 돌아가기</a></div></form><div class="result-box" id="contact-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">권장 경로</span><ul class="clean"><li>먼저 제품 상세 또는 가격 페이지를 확인합니다.</li><li>즉시 데모로 방향을 확인합니다.</li><li>결제가 가능한 경우 바로 진행합니다.</li><li>정말 예외가 있을 때만 이 폼을 사용합니다.</li></ul></article></div></section></main>
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
    sample_points = ''.join(f'<li>{escape(item)}</li>' for item in product.get('samples', []))
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../../index.html">HOME</a><span class="sep">/</span><a href="../../index.html">제품</a><span class="sep">/</span><a href="../index.html">{escape(product['name'])}</a><span class="sep">/</span><span>즉시 데모</span></div><span class="tag theme-chip">{escape(product['label'])}</span><h1>{escape(product['name'])} 즉시 데모</h1><p class="lead">미리보기 버튼으로 방향을 먼저 보고, 저장은 선택으로 두었습니다. 제품별 핵심 예시와 함께 결제로 넘어가기 전에 판단할 포인트를 먼저 보여줍니다.</p>{product_subnav('../../../', product, 'demo')}</div><div class="card theme-panel"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">먼저 볼 예시</span><ul class="clean inverse-list">{sample_points}</ul></div></div></section><section class="section compact"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">빠른 미리보기</span><div class="quick-demo-grid">{''.join(f'<button class="quick-demo-button" type="button" data-quick-demo="{escape(product["key"])}" data-quick-scenario="{idx}">{escape((item if isinstance(item, str) else str(item))[:32])}</button>' for idx, item in enumerate(product.get('demo_scenarios', [])[:4]))}</div><div class="result-box" id="quick-demo-result" role="status" aria-live="polite"></div></article><article class="card strong"><span class="tag theme-chip">저장하기</span><form id="product-demo-form" class="stack-form"><div class="form-grid"><div><label>회사명</label><input name="company" data-demo-field="company" placeholder="샘플 브랜드" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" data-demo-field="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" data-demo-field="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>팀 규모</label><input name="team" data-demo-field="team" placeholder="예: 2인 운영팀"></div><div><label>목표</label><input name="goal" data-demo-field="goal" placeholder="예: CTA 전환 개선" required></div><div><label>핵심 키워드</label><input name="keywords" data-demo-field="keywords" placeholder="예: 랜딩, CTA, 신뢰"></div><div><label>참고 링크 (선택)</label><input name="referenceUrl" placeholder="대표 URL 또는 참고 문서"></div><div><label>플랜 미리보기</label><select name="plan" data-demo-field="plan"><option value="Starter">Starter</option><option value="Growth">Growth</option><option value="Scale">Scale</option></select></div><div class="span-2"><label>추가 메모 (선택)</label><textarea name="context" rows="4" placeholder="꼭 확인하고 싶은 장면을 적어 주세요"></textarea></div></div><div class="actions"><button class="button" type="submit">샘플 저장하기</button><a class="button ghost" href="../plans/index.html">플랜 보기</a></div></form><div class="result-box" id="product-demo-result" role="status" aria-live="polite"></div></article></div></section></main>
    ''')
    return doc(brand, f"{product['name']} 데모 | {brand['name']}", f"{product['name']} 즉시 데모", product['theme'], body, depth=3, page_key='product-demo', page_path=f"/products/{product['key']}/demo/index.html", product_key=product['key'])

def product_plans_page(brand: dict, product: dict) -> str:
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../../index.html">HOME</a><span class="sep">/</span><a href="../../index.html">제품</a><span class="sep">/</span><a href="../index.html">{escape(product['name'])}</a><span class="sep">/</span><span>플랜</span></div><span class="tag theme-chip">{escape(product['label'])}</span><h1>{escape(product['name'])} 플랜</h1><p class="lead">가격과 포함 범위를 별도 페이지로 분리해 길게 스크롤하지 않아도 비교할 수 있게 했습니다. 추천 플랜은 표시하고, 계약·정산 예외는 예외 문의로 분기합니다.</p>{product_subnav('../../../', product, 'plans')}</div><div class="card theme-panel"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">가격 기준</span><h3 style="font-size:1.72rem;margin:16px 0 10px">{escape(product['plans'][0]['price'])}부터 시작합니다</h3><p>{escape(product.get('pricing_basis', ''))}</p><div class="small-actions"><a href="../../../legal/refund/index.html">환불 정책</a><a href="../../../contact/index.html?product={escape(product['key'])}">예외 문의</a></div></div></div></section><section class="section compact"><div class="container"><div class="plan-grid">{''.join(_ for _ in [plan_cards_markup(product, '../../../')])}</div></div></section></main>
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
