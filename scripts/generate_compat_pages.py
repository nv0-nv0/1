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


def pricing_page(brand: dict, products: list[dict]) -> str:
    rows = ''.join(
        f"<tr><td><strong>{escape(item['name'])}</strong><br><small>{escape(item['headline'])}</small></td>"
        f"<td>{escape(item['plans'][0]['price'])}</td><td>{escape(item['plans'][1]['price'])}</td><td>{escape(item['plans'][2]['price'])}</td>"
        f"<td>{escape(item['outputs'][0])}</td></tr>"
        for item in products
    )
    cards = ''.join(
        f"<article class='story-card {escape(item['theme'])}'><span class='tag theme-chip'>{escape(item['label'])}</span><h3>{escape(item['name'])}</h3><p>{escape(item['pricing_basis'])}</p><div class='small-actions'><a href='../products/{escape(item['key'])}/index.html'>제품 보기</a><a href='../checkout/index.html?product={escape(item['key'])}'>도입 신청</a></div></article>"
        for item in products
    )
    body = dedent(f'''
    <main>
      <section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>가격</span></div><span class="kicker">Pricing</span><h1>가격, 범위, 결과물을 한 번에 비교할 수 있습니다</h1><p class="lead">제품 정의 데이터와 같은 원천에서 가격을 불러와 제품 상세, 시작 흐름, 가격 안내가 서로 어긋나지 않도록 맞췄습니다.</p><div class="actions"><a class="button" href="../checkout/index.html">도입 신청</a><a class="button secondary" href="../products/index.html">제품 비교</a></div></div><div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">가격 원칙</span><h3 style="font-size:1.72rem;margin:16px 0 10px">숫자를 여러 군데 따로 적지 않습니다</h3><p>시작가와 플랜 설명이 제품 데이터와 같은 소스에서 나오도록 구성해 가격 불일치를 줄였습니다.</p></div></div></section>
      <section class="section compact"><div class="container"><div class="table-wrap"><table><thead><tr><th>제품</th><th>Starter</th><th>Growth</th><th>Scale</th><th>대표 결과물</th></tr></thead><tbody>{rows}</tbody></table></div></div></section>
      <section class="section compact"><div class="container"><div class="section-head"><div><h2>가격 설명</h2></div><p>가격만이 아니라 어떤 결과물을 받는지, 어느 범위부터 시작하는지 같이 확인할 수 있게 정리했습니다.</p></div><div class="story-grid">{cards}</div></div></section>
    </main>
    ''')
    return doc(brand, f"가격 | {brand['name']}", '제품별 시작가와 범위를 확인하는 페이지', 'pricing', body, depth=1, page_key='pricing', page_path='/pricing/index.html')


def guides_page(brand: dict, products: list[dict]) -> str:
    prep_list = ''.join(f"<li><strong>{escape(item['name'])}</strong> · {escape(item['problem'])}</li>" for item in products)
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>가이드</span></div><span class="kicker">Guides</span><h1>문제 → 제품 → 시작 흐름으로 바로 판단할 수 있게 정리했습니다</h1><p class="lead">빠른 도입형, 비교 검토형, 지원 문의형으로 나눠 처음 방문한 팀도 자연스럽게 다음 행동을 고를 수 있게 구성했습니다.</p><div class="actions"><a class="button" href="../products/index.html">문제별 제품 보기</a><a class="button secondary" href="../pricing/index.html">가격 확인</a><a class="button ghost" href="../contact/index.html">고객 지원</a></div></div><div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">준비물</span><h3 style="font-size:1.72rem;margin:16px 0 10px">핵심 예시 1개만 있어도 시작 가능합니다</h3><ul class="clean inverse-list">{prep_list}</ul></div></div></section></main>
    ''')
    return doc(brand, f"가이드 | {brand['name']}", '처음 방문한 팀을 위한 도입 가이드', 'guides', body, depth=1, page_key='guides', page_path='/guides/index.html')


def docs_page(brand: dict, products: list[dict]) -> str:
    cards = ''.join(
        f"<article class='story-card {escape(item['theme'])}'><span class='tag theme-chip'>{escape(item['label'])}</span><h3>{escape(item['name'])} 도입 안내</h3><p>{escape(item['summary'])}</p><div class='small-actions'><a href='../docs/{escape(item['key'])}/index.html'>열기</a><a href='../products/{escape(item['key'])}/index.html'>제품 상세</a></div></article>"
        for item in products
    )
    body = f'<main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>문서 센터</span></div><span class="kicker">Docs</span><h1>홍보 문구보다 실제 판단에 필요한 제품 문서를 먼저 모았습니다</h1><p class="lead">각 제품에서 무엇을 준비하면 좋고, 어떤 결과를 받게 되는지 먼저 확인할 수 있게 구성했습니다.</p></div></div></section><section class="section compact"><div class="container"><div class="story-grid">{cards}</div></div></section></main>'
    return doc(brand, f"문서 센터 | {brand['name']}", '제품 도입 안내 문서 모음', 'docs', body, depth=1, page_key='docs', page_path='/docs/index.html')


def product_doc_page(brand: dict, product: dict) -> str:
    outputs = ''.join(f"<li>{escape(item)}</li>" for item in product.get('outputs', []))
    workflow = ''.join(f"<li>{escape(item)}</li>" for item in product.get('workflow', []))
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../index.html">HOME</a><span class="sep">/</span><a href="../index.html">문서 센터</a><span class="sep">/</span><span>{escape(product['name'])}</span></div><span class="tag theme-chip">{escape(product['label'])}</span><h1>{escape(product['name'])} 도입 안내</h1><p class="lead">{escape(product['summary'])}</p><div class="actions"><a class="button" href="../../products/{escape(product['key'])}/index.html">제품 보기</a><a class="button secondary" href="../../checkout/index.html?product={escape(product['key'])}">도입 신청</a><a class="button ghost" href="../../products/{escape(product['key'])}/board/index.html">관련 글</a></div></div><div class="card theme-panel"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">먼저 맞추는 것</span><h3 style="font-size:1.75rem;margin:16px 0 10px">{escape(product['problem'])}</h3><p>{escape(product['headline'])}</p></div></div></section><section class="section compact"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">받는 결과</span><ul class="clean">{outputs}</ul></article><article class="card strong"><span class="tag theme-chip">진행 흐름</span><ol class="flow-list">{workflow}</ol></article></div></section></main>
    ''')
    return doc(brand, f"{product['name']} 도입 안내 | {brand['name']}", f"{product['name']} 도입 준비 안내", 'product-doc', body, depth=2, page_key='docs-detail', page_path=f"/docs/{product['key']}/index.html", product_key=product['key'])


def cases_page(brand: dict, products: list[dict]) -> str:
    cards = []
    for item in products:
        topic = (item.get('board_automation', {}).get('topics') or [{}])[0]
        cards.append(f"<article class='story-card {escape(item['theme'])}'><span class='tag theme-chip'>{escape(item['label'])}</span><h3>{escape(topic.get('title') or item['name'])}</h3><p>{escape(topic.get('summary') or item['summary'])}</p><div class='small-actions'><a href='../products/{escape(item['key'])}/index.html'>제품 보기</a><a href='../products/{escape(item['key'])}/board/index.html'>관련 글</a></div></article>")
    body = f'<main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>적용 사례</span></div><span class="kicker">Cases</span><h1>설명보다 빨리 이해되는 것은 실제로 쓰이는 장면입니다</h1><p class="lead">어떤 팀이 어떤 문제에서 출발해 어떤 결과를 기대하는지, 제품별 대표 사례를 먼저 정리했습니다.</p></div></div></section><section class="section compact"><div class="container"><div class="story-grid">{"".join(cards)}</div></div></section></main>'
    return doc(brand, f"적용 사례 | {brand['name']}", '제품별 적용 사례', 'cases', body, depth=1, page_key='cases', page_path='/cases/index.html')


def faq_page(brand: dict, products: list[dict]) -> str:
    cards = ''.join(
        f"<article class='faq-card'><span class='tag'>{escape(item['name'])}</span><h3>{escape(faq['q'])}</h3><p>{escape(faq['a'])}</p></article>"
        for item in products for faq in item.get('faqs', [])
    )
    body = f'<main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>FAQ</span></div><span class="kicker">FAQ</span><h1>제품 선택과 시작 전에 자주 나오는 질문을 먼저 모았습니다</h1><p class="lead">같은 질문이 반복되는 것을 줄이기 위해 제품별 자주 묻는 질문을 한곳에 모았습니다.</p></div></div></section><section class="section compact"><div class="container"><div class="faq-grid">{cards}</div></div></section></main>'
    return doc(brand, f"FAQ | {brand['name']}", '자주 묻는 질문', 'faq', body, depth=1, page_key='faq', page_path='/faq/index.html')


def legal_privacy_page(brand: dict) -> str:
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../index.html">HOME</a><span class="sep">/</span><span>개인정보처리방침</span></div><h1>개인정보처리방침</h1><p class="lead">문의, 도입 신청, 포털 조회에 필요한 최소 범위의 정보를 처리합니다. 실제 운영 환경의 위탁사, 보관 기간, 국외 이전 여부는 연동 서비스가 확정되면 이 문서에 즉시 반영해야 합니다.</p><div class="kv"><div class="row"><strong>문의 이메일</strong><span>{escape(brand.get('contact_email',''))}</span></div><div class="row"><strong>주요 처리 목적</strong><span>문의 응대, 도입 신청, 결제/포털 안내, 운영 기록 관리</span></div><div class="row"><strong>기본 보관 원칙</strong><span>업무 목적 달성 후 지체 없이 파기, 법령상 보존 의무 시 별도 분리 보관</span></div></div></div></div></section></main>
    ''')
    return doc(brand, f"개인정보처리방침 | {brand['name']}", '개인정보 처리방침', 'legal', body, depth=2, page_key='privacy', page_path='/legal/privacy/index.html')


def legal_refund_page(brand: dict) -> str:
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../index.html">HOME</a><span class="sep">/</span><span>환불정책</span></div><h1>환불정책</h1><p class="lead">착수 전에는 전액 환불을 원칙으로 하되, 맞춤형 자료 작성·분석·외부 비용이 이미 시작된 뒤에는 진행 범위와 기 제공 산출물을 기준으로 부분 환불 여부를 판단합니다. 소비자 법령이 적용되는 경우 해당 법령을 우선합니다.</p><div class="kv"><div class="row"><strong>착수 전</strong><span>업무 미착수·외부 비용 없음·맞춤 산출물 미작성 시 전액 환불 원칙</span></div><div class="row"><strong>착수 후</strong><span>진행 범위, 작성 시간, 기 제공 결과물, 외부 비용 공제 후 정산</span></div><div class="row"><strong>접수 채널</strong><span>{escape(brand.get('contact_email',''))}</span></div></div></div></div></section></main>
    ''')
    return doc(brand, f"환불정책 | {brand['name']}", '환불 및 취소 기준', 'legal', body, depth=2, page_key='refund', page_path='/legal/refund/index.html')


def resources_page(brand: dict) -> str:
    body = dedent('''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>자료 허브</span></div><span class="kicker">Resources</span><h1>문서, 사례, 공개 글을 한곳에서 바로 이어봅니다</h1><p class="lead">정보성 자료를 따로 모아 두어 영업 문구보다 먼저 검토 자료를 보고 싶은 팀이 빠르게 움직일 수 있게 정리했습니다.</p><div class="actions"><a class="button" href="../docs/index.html">문서 센터</a><a class="button secondary" href="../cases/index.html">적용 사례</a><a class="button ghost" href="../board/index.html">게시판</a></div></div></div></section></main>
    ''')
    return doc(brand, f"자료 허브 | {brand['name']}", '문서, 사례, 게시판 자료 허브', 'resources', body, depth=1, page_key='resources', page_path='/resources/index.html')


def service_page(brand: dict) -> str:
    body = dedent('''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>서비스 제공</span></div><span class="kicker">Service flow</span><h1>도입 후에는 포털 기준으로 진행 상태와 결과 자료를 이어서 확인합니다</h1><p class="lead">사이트 소개에서 끝나지 않고, 신청 저장 → 결제 또는 범위 확정 → 포털 확인 → 결과 자료 전달 순서로 이어지게 설계했습니다.</p><div class="actions"><a class="button" href="../checkout/index.html">도입 신청</a><a class="button secondary" href="../portal/index.html">고객 포털</a><a class="button ghost" href="../contact/index.html">고객 지원</a></div></div></div></section></main>
    ''')
    return doc(brand, f"서비스 제공 | {brand['name']}", '도입 후 제공 흐름', 'service', body, depth=1, page_key='service', page_path='/service/index.html')


def onboarding_page(brand: dict) -> str:
    body = dedent('''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>도입 준비</span></div><span class="kicker">Onboarding</span><h1>무엇을 준비하면 빠르게 시작할 수 있는지 먼저 안내합니다</h1><p class="lead">대표 URL, 품목 설명, 공고 링크, 초안 문서처럼 핵심 예시 1개만 있어도 충분합니다. 실제 등록은 도입 신청 페이지에서 바로 이어집니다.</p><div class="actions"><a class="button" href="../checkout/index.html">도입 신청으로 이동</a><a class="button secondary" href="../guides/index.html">가이드 보기</a></div></div></div></section></main>
    ''')
    return doc(brand, f"도입 준비 | {brand['name']}", '도입 준비 안내', 'onboarding', body, depth=1, page_key='onboarding', page_path='/onboarding/index.html')


def checkout_page_override(brand: dict, products: list[dict]) -> str:
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])} · {escape(item["plans"][0]["price"])}부터</option>' for item in products)
    body = dedent(f'''
    <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>주문</span></div><span class="kicker">Checkout</span><h1>선택한 제품을 바로 결제하고 결과 확인까지 이어갈 수 있습니다</h1><p class="lead">플랜을 고르고 결제 버튼을 누르면 외부 결제창으로 이동합니다. 결제 완료 뒤에는 결과 자료를 바로 확인할 수 있고, 공개 글은 원할 때 별도로 둘러보실 수 있습니다.</p><form id="checkout-form"><div class="form-grid"><div><label>제품</label><select name="product" data-prefill="product">{options}</select></div><div><label>플랜</label><select name="plan" data-prefill="plan"><option value="Starter">Starter</option><option value="Growth">Growth</option><option value="Scale">Scale</option></select></div><div><label>과금 기준</label><select name="billing"><option value="one-time">1회 결제</option><option value="monthly">월 과금</option><option value="project">프로젝트형</option></select></div><div><label>결제 방식</label><select name="paymentMethod"><option value="toss">Toss 결제</option><option value="invoice">세금계산서/송장</option></select></div><div><label>회사명</label><input name="company" placeholder="회사명"></div><div><label>담당자명</label><input name="name" placeholder="담당자명"></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com"></div><div><label>추가 요청</label><input name="note" placeholder="예: 원하는 톤, 꼭 포함할 내용"></div></div><div class="actions"><button class="button" type="submit">결제창 열기</button><a class="button ghost" href="../pricing/index.html">가격 먼저 보기</a></div></form><div class="result-box" id="checkout-result"></div></article><article class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">결제 안내</span><h3 style="font-size:1.72rem;margin:16px 0 10px">지금 구매하기를 누르면 바로 외부 결제창으로 이어집니다</h3><ul class="clean inverse-list"><li>플랜 확인</li><li>외부 결제 진행</li><li>결제 완료 확인</li><li>결과물 준비</li><li>결과 자료 확인</li></ul></article></div></section></main>
    ''')
    return doc(brand, f"주문 | {brand['name']}", '제품 주문 및 결제 진입', 'checkout', body, depth=1, page_key='checkout', page_path='/checkout/index.html')

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
        dist / 'checkout' / 'index.html': checkout_page_override(brand, products),
    }
    for path, content in pages.items():
        write(path, content)
    for product in products:
        write(dist / 'docs' / product['key'] / 'index.html', product_doc_page(brand, product))


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    generate_compat_pages(root / 'dist', json.loads((root / 'src' / 'data' / 'site.json').read_text(encoding='utf-8')))
