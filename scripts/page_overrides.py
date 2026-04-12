
import base64
import json
from pathlib import Path
from html import escape
from textwrap import dedent


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def write(path: Path, content: str):
    ensure_dir(path.parent)
    path.write_text(content, encoding='utf-8')


def write_bytes(path: Path, content: bytes):
    ensure_dir(path.parent)
    path.write_bytes(content)


def rel_prefix(depth: int) -> str:
    return './' if depth == 0 else '../' * depth


def page_url(brand: dict, path: str) -> str:
    clean = path if path.startswith('/') else '/' + path
    if clean.endswith('index.html'):
        clean = clean[:-10]
    return brand['domain'].rstrip('/') + clean


def build_page_schema(brand: dict, title: str, description: str, page_path: str, page_key: str, product_key: str | None = None) -> str:
    canonical = page_url(brand, page_path)
    page_name = title.split('|')[0].strip()
    schema: dict = {
        "@context": "https://schema.org",
        "@type": "Product" if page_key == 'product' else "WebPage",
        "name": page_name,
        "description": description,
        "url": canonical,
        "inLanguage": "ko-KR",
        "isPartOf": {
            "@type": "WebSite",
            "name": brand.get('name', 'NV0'),
            "url": brand.get('domain', '').rstrip('/') + '/',
        },
    }
    if page_key == 'product' and product_key:
        schema["sku"] = product_key
        schema["brand"] = {"@type": "Brand", "name": brand.get('name', 'NV0')}
        schema["category"] = "Automation SaaS"
    return json.dumps(schema, ensure_ascii=False, separators=(',', ':'))


def doc(brand: dict, title: str, description: str, body_class: str, body: str, *, depth: int, page_key: str, page_path: str, product_key: str | None = None) -> str:
    prefix = rel_prefix(depth)
    attrs = [f'class="{body_class}"', f'data-page="{page_key}"']
    if product_key:
        attrs.append(f'data-product="{product_key}"')
    canonical = page_url(brand, page_path)
    og_type = 'product' if page_key == 'product' else 'website'
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


def timeline_markup(data: dict) -> str:
    return ''.join(
        f'<article class="step"><strong>{escape(step["title"])}</strong><span>{escape(step["body"])}</span></article>'
        for step in data['engine']['steps']
    )


def company_sections_markup(company_profile: dict) -> str:
    return ''.join(
        f'<article class="story-card"><span class="tag">{idx + 1}</span><h3>{escape(item["title"])}</h3><p>{escape(item["body"])}</p></article>'
        for idx, item in enumerate(company_profile.get('sections', []))
    )


def engine_layers_markup(data: dict) -> str:
    return ''.join(f'<span>{escape(layer)}</span>' for layer in data['engine'].get('automation_layers', []))


def product_cards_markup(products: list[dict], prefix: str, *, include_board: bool = True, include_docs: bool = False) -> str:
    cards = []
    for item in products:
        actions = []
        if include_board:
            actions.append(f'<a class="button secondary" href="{prefix}products/{escape(item["key"])}/board/index.html">AI 자동발행 블로그 허브</a>')
        actions.append(f'<a class="button soft" href="{prefix}products/{escape(item["key"])}/index.html#demo">바로 체험</a>')
        actions.append(f'<a class="button ghost" href="{prefix}products/{escape(item["key"])}/index.html#order">바로 구매</a>')
        if include_docs:
            actions.append(f'<a class="button ghost" href="{prefix}docs/{escape(item["key"])}/index.html">문서 보기</a>')
        values = ''.join(f'<li>{escape(point)}</li>' for point in item.get('value_points', [])[:3])
        cards.append(
            f'<article class="card product-card strong {escape(item["theme"])}">'
            f'<span class="tag theme-chip">{escape(item["label"])}</span>'
            f'<h3>{escape(item["name"])}</h3>'
            f'<p>{escape(item["headline"])}</p>'
            f'<ul class="clean">{values}</ul>'
            f'<div class="muted-box" style="margin-top:18px">시작가: {escape(item["plans"][0]["price"])} · {escape(item.get("pricing_basis", ""))}</div>'
            f'<div class="actions">{"".join(actions)}</div>'
            f'</article>'
        )
    return ''.join(cards)


def support_cards_markup() -> str:
    cards = [
        ('회사형 메인', '회사 소개와 운영 기준을 먼저 보여 주고, 제품 상세에서만 체험과 결제가 이어지게 분리했습니다.'),
        ('공용 엔진', '신청 저장, 결제 준비, 자동 발행, 고객 포털, 관리자 허브를 같은 기록선으로 묶습니다.'),
        ('제품 상세', '각 제품마다 소개, 데모, 가격, 주문, 결제, 결과 확인이 한 페이지 흐름으로 이어집니다.'),
        ('AI 자동발행 블로그 허브', '제품별 CTA 글과 연관 주제를 계속 쌓아 유입을 제품 상세와 결제로 연결합니다.'),
        ('문서·사례', '가격, 문서 센터, 적용 사례, FAQ를 따로 두어 검토형 고객도 막히지 않게 했습니다.'),
        ('고객 포털', '결제 후에는 조회 코드 기준으로 상태와 결과 자료를 다시 확인할 수 있습니다.'),
    ]
    return ''.join(
        f'<article class="support-card"><span class="tag">{idx + 1}</span><h3>{escape(title)}</h3><p>{escape(body)}</p></article>'
        for idx, (title, body) in enumerate(cards)
    )


def quick_links_markup(prefix: str) -> str:
    links = [
        ('가격 비교', f'{prefix}pricing/index.html', '제품별 시작가와 범위를 바로 비교합니다.'),
        ('문서 센터', f'{prefix}docs/index.html', '도입 전에 준비물과 결과물을 먼저 확인합니다.'),
        ('적용 사례', f'{prefix}cases/index.html', '대표 문제와 기대 결과를 사례형으로 봅니다.'),
        ('FAQ', f'{prefix}faq/index.html', '반복되는 질문을 먼저 확인합니다.'),
        ('AI 자동발행 블로그 허브', f'{prefix}board/index.html', 'AI 자동발행 글과 제품 연결 흐름을 봅니다.'),
        ('고객 포털', f'{prefix}portal/index.html', '결제 후 조회 코드로 결과 자료를 확인합니다.'),
    ]
    return ''.join(
        f'<article class="story-card"><span class="tag">{idx + 1}</span><h3>{escape(title)}</h3><p>{escape(body)}</p><div class="small-actions"><a href="{href}">바로 가기</a></div></article>'
        for idx, (title, href, body) in enumerate(links)
    )


def product_fit_cards_markup(products: list[dict], prefix: str) -> str:
    return ''.join(
        f'<article class="story-card {escape(item["theme"])}"><span class="tag theme-chip">{escape(item["label"])}</span><h3>{escape(item["problem"])}</h3><p>{escape(item["summary"])}</p><div class="small-actions"><a href="{prefix}products/{escape(item["key"])}/index.html">제품 상세</a><a href="{prefix}products/{escape(item["key"])}/index.html#demo">데모</a></div></article>'
        for item in products
    )


def product_value_list(product: dict, key: str) -> str:
    return ''.join(f'<li>{escape(item)}</li>' for item in product.get(key, []))


def related_modules_markup(product: dict, product_map: dict[str, dict], prefix: str) -> str:
    cards = []
    for key in product.get('related_modules', []):
        item = product_map.get(key)
        if not item:
            continue
        cards.append(
            f'<article class="story-card {escape(item["theme"])}"><span class="tag theme-chip">{escape(item["label"])}</span><h3>{escape(item["name"])}</h3><p>{escape(item["summary"])}</p><div class="small-actions"><a href="{prefix}products/{escape(item["key"])}/index.html">자세히 보기</a><a href="{prefix}products/{escape(item["key"])}/index.html#order">바로 시작</a></div></article>'
        )
    return ''.join(cards) or '<div class="empty-box">연결된 제품이 아직 없습니다.</div>'


def faq_markup(product: dict) -> str:
    return ''.join(
        f'<article class="faq-card"><span class="tag">Q</span><h3>{escape(item["q"])}</h3><p>{escape(item["a"])}</p></article>'
        for item in product.get('faqs', [])
    )


def plan_cards_markup(product: dict) -> str:
    return ''.join(
        f'<article class="plan-card"><span class="tag">{escape(plan["name"])}</span><h3>{escape(plan["price"])}</h3><p>{escape(plan.get("note", ""))}</p><div class="small-actions"><a class="button" href="#order" data-plan-pick="{escape(plan["name"])}">이 플랜으로 시작</a></div></article>'
        for plan in product.get('plans', [])
    )


def build_home_page(data: dict) -> str:
    brand = data['brand']
    products = data['products']
    representative = products[0]
    body = dedent(f'''
    <main>
      <section class="hero">
        <div class="container hero-grid">
          <div class="card strong">
            <span class="kicker">{escape(brand["tagline"])}</span>
            <h1>{escape(brand["hero_title"])}</h1>
            <p class="lead">{escape(brand["hero_description"])}</p>
            <div class="actions">
              <a class="button secondary" href="./company/index.html">회사 소개 보기</a>
              <a class="button" href="./products/index.html">제품 구조 보기</a>
              <a class="button ghost" href="./pricing/index.html">가격 먼저 보기</a>
              <a class="button ghost" href="./products/{escape(representative["key"])}/index.html#demo">대표 제품 바로 체험</a>
            </div>
            <div class="live-strip" id="live-stats">
              <article class="mini"><strong>회사형 메인</strong><span>회사 소개와 제품 판매 동선을 분리해 첫 이해를 돕습니다.</span></article>
              <article class="mini"><strong>공용 엔진</strong><span>신청, 결제, 발행, 포털, 관리자 기록을 하나로 묶습니다.</span></article>
              <article class="mini"><strong>모듈형 제품</strong><span>새 제품을 같은 구조에 붙여 빠르게 확장할 수 있습니다.</span></article>
              <article class="mini"><strong>결과 납품</strong><span>결제 후 결과 자료와 공개 글, 포털 확인까지 이어집니다.</span></article>
            </div>
          </div>
          <div class="showcase-grid">
            <article class="card accent">
              <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">공용 엔진</span>
              <h3 style="font-size:1.75rem;margin:16px 0 10px">한 번 만든 엔진 위에 제품 모듈을 계속 붙일 수 있습니다</h3>
              <p>NV0는 회사 소개, 제품 상세, 결제, AI 자동발행 블로그 허브, 고객 포털, 관리자 허브를 하나의 공용 엔진 위에서 관리합니다. 1인 운영 기준으로 새 제품 추가와 운영 반복 비용을 줄이는 구조입니다.</p>
              <div class="inline-list">{engine_layers_markup(data)}</div>
            </article>
            <article class="card strong">
              <span class="tag">각 제품 페이지에서 되는 일</span>
              <h3>소개만 하는 페이지가 아니라 바로 체험하고, 가격을 보고, 결제하고, 결과를 확인하는 페이지입니다</h3>
              <p class="lead" style="font-size:1rem">제품 상세에는 AI 자동발행 블로그 허브, 제품 소개, 데모, 가격/플랜, 주문, 결제, 결과 확인이 모두 같은 흐름으로 들어가 있습니다.</p>
              <div class="badge-row"><span class="badge">게시판</span><span class="badge">제품 소개</span><span class="badge">바로 체험</span><span class="badge">가격 비교</span><span class="badge">결제/판매</span><span class="badge">포털 확인</span></div>
            </article>
          </div>
        </div>
      </section>
      <section class="section compact"><div class="container"><div class="section-head"><div><h2>한 사이트 안에서 회사 소개, 제품 소개, 가격, 결제, 결과 확인이 모두 이어지도록 설계했습니다</h2></div><p>루트 홈은 회사형 메인으로, 제품 상세는 실행형 판매 페이지로, 자료 허브는 검토형 고객용 동선으로 나눠 첫 방문부터 결제 후 확인까지 막힘 없이 이어가도록 구성했습니다.</p></div><div class="timeline">{timeline_markup(data)}</div></div></section>
      <section class="section compact"><div class="container"><div class="section-head"><div><h2>지금 붙어 있는 4개 제품 모듈</h2></div><p>모든 제품은 공용 엔진을 공유하지만 문제 정의, 결과물, CTA, 가격 기준은 각각 다르게 가져갑니다.</p></div><div class="product-grid" id="product-grid">{product_cards_markup(products, './')}</div></div></section>
      <section class="section compact"><div class="container"><div class="section-head"><div><h2>NV0가 실제로 제공하는 화면과 흐름</h2></div><p>광고형 랜딩 한 장이 아니라, 판매·자료·발행·납품 동선이 서로 끊기지 않는 제품 회사 구조를 기준으로 설계했습니다.</p></div><div class="support-grid">{support_cards_markup()}</div></div></section>
      <section class="section compact"><div class="container"><div class="section-head"><div><h2>검토부터 구매와 결과 확인까지 바로 이어지는 메뉴</h2></div><p>가격, 문서, 사례, FAQ, AI 자동발행 블로그 허브, 고객 포털을 별도 메뉴로 두어 읽는 고객과 바로 사는 고객이 모두 막히지 않게 했습니다.</p></div><div class="story-grid">{quick_links_markup('./')}</div></div></section>
    </main>
    ''')
    return doc(brand, brand['title'], brand['hero_description'], 'home', body, depth=0, page_key='home', page_path='/index.html')


def build_company_page(data: dict) -> str:
    brand = data['brand']
    company_profile = data.get('company_profile', {})
    prefix = rel_prefix(1)
    principles = ''.join(f'<li>{escape(item)}</li>' for item in company_profile.get('principles', []))
    body = dedent(f'''
    <main>
      <section class="section">
        <div class="container page-hero">
          <div class="card strong">
            <div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>회사</span></div>
            <span class="kicker">Company</span>
            <h1>{escape(company_profile.get('headline', ''))}</h1>
            <p class="lead">NV0는 회사형 메인에서 브랜드와 운영 기준을 설명하고, 제품 상세에서는 체험·가격·결제·결과 확인을 바로 이어지게 만드는 구조를 지향합니다. 회사 페이지는 그 전체 구조의 기준과 운영 원칙을 보여 주는 곳입니다.</p>
            <div class="actions">
              <a class="button secondary" href="{prefix}engine/index.html">공용 엔진 보기</a>
              <a class="button" href="{prefix}products/index.html">제품 보기</a>
              <a class="button ghost" href="{prefix}pricing/index.html">가격 보기</a>
            </div>
          </div>
          <div class="card accent">
            <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">운영 원칙</span>
            <h3 style="font-size:1.72rem;margin:16px 0 10px">1인 운영에서도 설명보다 결정과 실행이 빠른 구조를 우선합니다</h3>
            <ul class="clean inverse-list">{principles}</ul>
          </div>
        </div>
      </section>
      <section class="section compact"><div class="container"><div class="section-head"><div><h2>회사형 메인으로 운영해도 구매 흐름이 끊기지 않는 이유</h2></div><p>브랜드 소개와 판매 설명을 한 화면에 모두 넣으면 첫 인지가 흐려집니다. 그래서 회사 메뉴는 기준과 구조를, 제품 메뉴는 실제 체험과 구매 흐름을 담당하게 분리했습니다.</p></div><div class="story-grid">{company_sections_markup(company_profile)}<article class="story-card"><span class="tag">4</span><h3>자료 허브</h3><p>가격, 문서, 사례, FAQ, 게시판을 별도 메뉴로 두어 검토형 고객도 바로 필요한 자료를 찾게 했습니다.</p></article><article class="story-card"><span class="tag">5</span><h3>포털/운영</h3><p>결제 후에는 고객 포털과 관리자 허브에서 상태와 결과 자료를 다시 확인할 수 있게 구성했습니다.</p></article><article class="story-card"><span class="tag">6</span><h3>모듈 확장</h3><p>새 제품이 생겨도 공용 엔진과 같은 전환 구조에 붙일 수 있게 설계해 확장 비용을 낮췄습니다.</p></article></div></div></section>
      <section class="section compact"><div class="container"><div class="section-head"><div><h2>공용 엔진이 맡는 역할</h2></div><p>회사 메뉴는 설명에 그치지 않고, 제품 메뉴와 자료 허브, 포털, 관리자 기능이 같은 데이터 흐름을 공유한다는 점을 분명하게 보여 줘야 합니다.</p></div><div class="timeline">{timeline_markup(data)}</div></div></section>
    </main>
    ''')
    return doc(brand, f'회사 | {brand["name"]}', '엔브이제로 회사 소개', 'company', body, depth=1, page_key='company', page_path='/company/index.html')


def build_products_page(data: dict) -> str:
    brand = data['brand']
    products = data['products']
    prefix = rel_prefix(1)
    body = dedent(f'''
    <main>
      <section class="section">
        <div class="container page-hero">
          <div class="card strong">
            <div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>제품</span></div>
            <span class="kicker">Products</span>
            <h1>공용 엔진 위에 붙는 제품 모듈을 문제 기준으로 바로 고를 수 있습니다</h1>
            <p class="lead">각 제품 상세 안에서 소개, AI 자동발행 블로그 허브, 데모, 가격 비교, 주문, 외부 결제, 결과 확인까지 자연스럽게 이어집니다. 문제를 먼저 보고 들어와도, 가격이나 문서를 먼저 보고 들어와도 같은 제품 페이지로 수렴하도록 설계했습니다.</p>
            <div class="actions"><a class="button" href="{prefix}pricing/index.html">가격 비교</a><a class="button secondary" href="{prefix}docs/index.html">문서 센터</a><a class="button ghost" href="{prefix}board/index.html">게시판 보기</a></div>
          </div>
          <div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">구매 흐름</span><h3 style="font-size:1.72rem;margin:16px 0 10px">체험 → 플랜 선택 → 외부 결제 → 결과 확인</h3><p>복잡한 문의 절차보다, 직접 써보고 바로 결정할 수 있는 흐름을 우선합니다. 제품마다 CTA AI 자동발행 블로그 허브과 문서 링크를 함께 둬 검토형 고객도 놓치지 않게 했습니다.</p></div>
        </div>
      </section>
      <section class="section compact"><div class="container"><div class="product-grid" id="product-grid">{product_cards_markup(products, prefix, include_docs=True)}</div></div></section>
      <section class="section compact"><div class="container"><div class="section-head"><div><h2>문제에서 시작하는 제품 선택</h2></div><p>제품명보다 문제를 먼저 떠올리는 고객을 위해 각 제품이 해결하는 대표 장면을 같이 정리했습니다.</p></div><div class="story-grid">{product_fit_cards_markup(products, prefix)}</div></div></section>
    </main>
    ''')
    return doc(brand, f'제품 | {brand["name"]}', 'NV0 제품 목록', 'products', body, depth=1, page_key='products', page_path='/products/index.html')


def build_engine_page(data: dict) -> str:
    brand = data['brand']
    prefix = rel_prefix(1)
    body = dedent(f'''
    <main>
      <section class="section">
        <div class="container page-hero">
          <div class="card strong">
            <div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>공용 엔진</span></div>
            <span class="kicker">Common engine</span>
            <h1>신청 저장, 결제 준비, 자동 발행, 고객 포털을 하나의 기록선으로 묶습니다</h1>
            <p class="lead">NV0의 차별점은 페이지를 많이 만드는 것이 아니라, 회사형 메인과 제품 판매 흐름, 게시판, 포털, 운영 허브가 같은 엔진을 공유한다는 점입니다. 그래서 1인 운영에서도 관리 포인트를 늘리지 않고 새 모듈을 붙일 수 있습니다.</p>
            <div class="actions"><a class="button" href="{prefix}products/index.html">제품 보기</a><a class="button secondary" href="{prefix}board/index.html">게시판 보기</a><a class="button ghost" href="{prefix}portal/index.html">포털 보기</a></div>
          </div>
          <div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">엔진 계층</span><h3 style="font-size:1.72rem;margin:16px 0 10px">한 번 만든 흐름을 제품마다 다시 쓰도록 설계했습니다</h3><p>{escape(data["engine"].get("headline", ""))}</p><div class="inline-list">{engine_layers_markup(data)}</div></div>
        </div>
      </section>
      <section class="section compact"><div class="container"><div class="timeline">{timeline_markup(data)}</div></div></section>
      <section class="section compact"><div class="container"><div class="section-head"><div><h2>엔진 위에서 반복되는 공통 화면</h2></div><p>제품마다 문구와 결과물은 다르지만, 고객이 겪는 핵심 단계는 공통 엔진 안에서 재사용됩니다.</p></div><div class="support-grid">{support_cards_markup()}</div></div></section>
    </main>
    ''')
    return doc(brand, f'공용 엔진 | {brand["name"]}', '신청부터 발행까지 묶는 공용 엔진 소개', 'engine', body, depth=1, page_key='engine', page_path='/engine/index.html')


def build_solutions_page(data: dict) -> str:
    brand = data['brand']
    products = data['products']
    prefix = rel_prefix(1)
    body = dedent(f'''
    <main>
      <section class="section">
        <div class="container page-hero">
          <div class="card strong">
            <div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>문제별 시작</span></div>
            <span class="kicker">Solutions</span>
            <h1>문제에서 시작해 제품, 가격, 자료까지 바로 이어집니다</h1>
            <p class="lead">어떤 이름의 제품을 사야 할지보다, 지금 막히는 장면이 무엇인지가 먼저인 고객을 위해 문제 기준의 시작 페이지를 따로 뒀습니다.</p>
            <div class="actions"><a class="button" href="{prefix}products/index.html">전체 제품 보기</a><a class="button secondary" href="{prefix}pricing/index.html">가격 비교</a><a class="button ghost" href="{prefix}docs/index.html">문서 센터</a></div>
          </div>
          <div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">바로 가는 구조</span><h3 style="font-size:1.72rem;margin:16px 0 10px">문제 이해 → 제품 선택 → 자료 검토 → 데모/구매</h3><p>이 페이지는 영업 문구보다 먼저, 어떤 상황에서 어느 제품을 먼저 봐야 하는지 판단하도록 돕는 허브입니다.</p></div>
        </div>
      </section>
      <section class="section compact"><div class="container"><div class="story-grid">{product_fit_cards_markup(products, prefix)}</div></div></section>
      <section class="section compact"><div class="container"><div class="section-head"><div><h2>문제별 다음 행동</h2></div><p>읽기형 고객은 문서와 사례로, 결정형 고객은 데모와 주문으로 자연스럽게 이어지도록 링크를 배치했습니다.</p></div><div class="story-grid">{quick_links_markup(prefix)}</div></div></section>
    </main>
    ''')
    return doc(brand, f'문제별 시작 | {brand["name"]}', '문제 기준으로 제품을 고르는 안내', 'solutions', body, depth=1, page_key='solutions', page_path='/solutions/index.html')


def build_product_page(data: dict, product: dict) -> str:
    brand = data['brand']
    product_map = {item['key']: item for item in data['products']}
    prefix = rel_prefix(2)
    selected_plan = product.get('demo_defaults', {}).get('plan', 'Starter')
    body = dedent(f'''
    <main>
      <section class="section">
        <div class="container page-hero">
          <div class="card strong">
            <div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><a href="{prefix}products/index.html">제품</a><span class="sep">/</span><span>{escape(product["name"])}</span></div>
            <span class="tag theme-chip">{escape(product["label"])}</span>
            <h1 data-fill="product-name">{escape(product["name"])}</h1>
            <p class="lead" data-fill="product-headline">{escape(product["headline"])}</p>
            <div class="actions" id="product-actions">
              <a class="button ghost" href="#board">관련 글 먼저 보기</a>
              <a class="button" href="#demo">무료로 체험하기</a>
              <a class="button secondary" href="#order">지금 시작하기</a>
              <a class="button ghost" href="{prefix}docs/{escape(product["key"])}/index.html">문서 보기</a>
            </div>
            <div class="inline-tabs">
              <a href="#board">AI 자동발행 블로그 허브</a>
              <a href="#intro">제품 소개</a>
              <a href="#demo">데모</a>
              <a href="#order">주문</a>
              <a href="#payment">결제</a>
              <a href="#delivery">결과 확인</a>
            </div>
          </div>
          <div class="card theme-panel">
            <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">이런 분께 잘 맞습니다</span>
            <h3 style="font-size:1.75rem;margin:16px 0 10px">{escape(product["problem"])}</h3>
            <p data-fill="product-summary">{escape(product["summary"])}</p>
            <div class="notice notice-light"><strong>가격 기준</strong><br><span data-fill="product-pricing">{' · '.join(f"{plan['name']} {plan['price']}" for plan in product.get('plans', []))}</span></div>
          </div>
        </div>
      </section>
      <section class="section compact" id="board"><div class="container"><div class="section-head"><div><h2>{escape(product["name"])} AI 자동발행 블로그 허브</h2></div><p>제품을 자세히 보기 전에 먼저 읽어보면 좋은 글을 모아두었습니다. 관련 글을 먼저 읽고 마음이 생기면 바로 체험과 시작 단계로 이어질 수 있습니다.</p></div><div class="board-grid" id="product-board-grid"></div><div id="product-post-detail"></div></div></section>
      <section class="section compact" id="intro"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">핵심 가치</span><h3>이 제품으로 바로 달라지는 점</h3><ul class="clean" id="product-values">{product_value_list(product, "value_points")}</ul></article><article class="card strong"><span class="tag theme-chip">결과물</span><h3>결제 후 받아보는 자료</h3><ul class="clean" id="product-outputs">{product_value_list(product, "outputs")}</ul></article></div></section>
      <section class="section compact" id="demo"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">바로 체험</span><h3>몇 가지 정보만 입력하면 샘플 결과를 바로 확인하고 데모 코드까지 받을 수 있습니다</h3><form id="product-demo-form" class="stack-form"><div class="form-grid"><div><label>회사명</label><input name="company" data-demo-field="company" placeholder="샘플 브랜드" autocomplete="organization" required value="{escape(product.get("demo_defaults", {}).get("company", ""))}"></div><div><label>담당자명</label><input name="name" data-demo-field="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" data-demo-field="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>팀 규모</label><input name="team" data-demo-field="team" placeholder="예: 2인 운영팀" autocomplete="organization-title"></div><div><label>목표</label><input name="goal" data-demo-field="goal" placeholder="예: CTA 전환 개선" required value="{escape(product.get("demo_defaults", {}).get("goal", ""))}"></div><div><label>핵심 키워드</label><input name="keywords" data-demo-field="keywords" placeholder="예: 랜딩, CTA, 신뢰" value="{escape(product.get("demo_defaults", {}).get("keywords", ""))}"></div><div><label>플랜 미리보기</label><select name="plan" data-demo-field="plan"><option value="Starter"{' selected' if selected_plan == 'Starter' else ''}>Starter</option><option value="Growth"{' selected' if selected_plan == 'Growth' else ''}>Growth</option><option value="Scale"{' selected' if selected_plan == 'Scale' else ''}>Scale</option></select></div></div><div class="actions"><button class="button" type="submit">무료 샘플과 데모 코드 받기</button><a class="button ghost" href="#order">이 조건으로 바로 시작</a></div></form><div class="result-box" id="product-demo-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">체험 포인트</span><h3>데모에서 먼저 보시면 좋은 항목</h3><ul class="clean" id="product-demo-scenarios">{product_value_list(product, "demo_scenarios")}</ul></article></div></section>
      <section class="section compact" id="order"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">주문</span><h3>플랜을 고른 뒤 바로 시작하고 결제할 수 있습니다</h3><form id="product-checkout-form" class="stack-form"><input type="hidden" name="product" value="{escape(product["key"])}"><div class="form-grid"><div><label>플랜</label><select name="plan" data-prefill="plan" required><option value="Starter">Starter</option><option value="Growth">Growth</option><option value="Scale">Scale</option></select></div><div><label>과금 기준</label><select name="billing"><option value="one-time">1회 결제</option><option value="monthly">월 과금</option><option value="project">프로젝트형</option></select></div><div><label>결제 방식</label><select name="paymentMethod" required><option value="toss">Toss 결제</option><option value="invoice">세금계산서/송장</option></select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>추가 요청</label><input name="note" placeholder="예: 원하는 톤, 꼭 포함할 내용" autocomplete="off"></div></div><div class="actions"><button class="button" type="submit">지금 시작하기</button><a class="button secondary" href="#payment">결제 안내 보기</a><a class="button ghost" href="{prefix}pricing/index.html">가격 전체 보기</a></div></form><div class="result-box" id="product-checkout-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">플랜</span><h3>지금 바로 선택할 수 있는 플랜</h3><div class="plan-grid" id="plan-grid">{plan_cards_markup(product)}</div></article></div></section>
      <section class="section compact" id="payment"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">결제</span><h3>시작하기 버튼을 누르면 바로 외부 결제창으로 이어집니다</h3><ol class="flow-list"><li>원하는 플랜과 정보를 확인합니다.</li><li>외부 결제창에서 안전하게 결제를 진행합니다.</li><li>결제가 끝나면 자동으로 결과 확인 화면으로 돌아옵니다.</li><li>완료 즉시 결과 자료를 확인하고 다음 진행을 이어갈 수 있습니다.</li></ol></article><article class="card strong"><span class="tag theme-chip">가격 기준</span><h3>시장 비교 기준</h3><p id="product-pricing-basis">{escape(product.get("pricing_basis", ""))}</p><div class="notice">처음 시작하는 팀도 부담 없이 바로 적용해 볼 수 있는 범위를 기준으로 플랜을 나눴습니다.</div></article></div></section>
      <section class="section compact" id="delivery"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">발행</span><h3>결제 후 결과 자료와 다음 진행이 자연스럽게 이어집니다</h3><ol class="flow-list" id="product-workflow">{product_value_list(product, "workflow")}</ol></article><article class="card strong"><span class="tag theme-chip">함께 보면 좋은 제품</span><h3>비슷한 고민에 이어서 보기 좋은 제품</h3><div class="story-grid" id="product-related-modules">{related_modules_markup(product, product_map, prefix)}</div></article></div></section>
      <section class="section compact"><div class="container"><div class="section-head"><div><h2>자주 묻는 질문</h2></div><p>제품 구매 전에 자주 나오는 질문을 먼저 정리했습니다.</p></div><div class="faq-grid" id="product-faq">{faq_markup(product)}</div></div></section>
    </main>
    ''')
    return doc(brand, f'{product["name"]} | {brand["name"]}', product['summary'], product['theme'], body, depth=2, page_key='product', product_key=product['key'], page_path=f'/products/{product["key"]}/index.html')



def build_terms_page(data: dict) -> str:
    brand = data['brand']
    prefix = rel_prefix(2)
    body = dedent(f'''
    <main>
      <section class="section">
        <div class="container page-hero">
          <div class="card strong">
            <div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><a href="{prefix}company/index.html">회사</a><span class="sep">/</span><span>이용약관</span></div>
            <span class="kicker">Terms</span>
            <h1>서비스 이용 전에 확인하실 핵심 약관을 정리했습니다</h1>
            <p class="lead">NV0는 회사형 메인과 제품별 실행 흐름을 함께 운영합니다. 이용약관은 공개 페이지, 주문·결제 흐름, 결과 확인 포털 이용 기준을 한 화면에 모아두었습니다.</p>
          </div>
          <div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">적용 범위</span><h3 style="font-size:1.72rem;margin:16px 0 10px">공개 페이지, 제품 체험, 주문, 결제, 발행, 포털 확인</h3><p>약관은 NV0가 제공하는 공개 웹사이트와 제품별 주문·결제·결과 자료 제공 흐름 전체에 적용됩니다.</p></div>
        </div>
      </section>
      <section class="section compact"><div class="container"><div class="story-grid">
        <article class="story-card"><span class="tag">1</span><h3>서비스 성격</h3><p>NV0는 공용 엔진 위에 제품 모듈을 결합해 소개, 데모, 주문, 결제, 발행, 결과 확인을 연결하는 서비스형 운영 구조를 제공합니다.</p></article>
        <article class="story-card"><span class="tag">2</span><h3>주문과 결제</h3><p>플랜, 범위, 결제 방식은 각 제품 페이지와 주문 화면에 표시된 조건을 기준으로 합니다. 외부 결제창을 이용하는 경우 해당 결제수단의 약관이 함께 적용될 수 있습니다.</p></article>
        <article class="story-card"><span class="tag">3</span><h3>결과 자료 제공</h3><p>결제 완료 또는 별도 범위 확정 후에는 제품 특성에 맞는 결과 자료와 체크리스트, 공개 글, 고객 포털 확인 정보가 제공될 수 있습니다.</p></article>
        <article class="story-card"><span class="tag">4</span><h3>고객 책임</h3><p>고객은 주문 또는 문의 과정에서 제공하는 회사 정보, 이메일, 참고 자료가 자신에게 제공 권한이 있는 내용인지 확인해야 합니다.</p></article>
        <article class="story-card"><span class="tag">5</span><h3>콘텐츠와 자료</h3><p>제품 결과물과 공개 글, 체크리스트는 입력된 정보와 제품 규칙을 바탕으로 생성되며, 최종 적용 전에 고객이 검토해야 합니다.</p></article>
        <article class="story-card"><span class="tag">6</span><h3>문의 창구</h3><p>약관, 결제, 범위, 결과 자료와 관련한 문의는 공개 문의 폼 또는 {escape(brand.get('contact_email',''))}로 접수할 수 있습니다.</p></article>
      </div></div></section>
    </main>
    ''')
    return doc(brand, f'이용약관 | {brand["name"]}', 'NV0 서비스 이용약관', 'terms', body, depth=2, page_key='terms', page_path='/legal/terms/index.html')


def build_404_page(data: dict) -> str:
    brand = data['brand']
    body = dedent(f'''
    <main>
      <section class="section">
        <div class="container page-hero">
          <div class="card strong">
            <span class="kicker">404</span>
            <h1>찾으시는 페이지가 보이지 않습니다</h1>
            <p class="lead">주소가 바뀌었거나 게시판 글 또는 제품 링크가 이동했을 수 있습니다. 아래 바로가기로 회사 소개, 제품, 가격, 고객 포털을 다시 시작해 보세요.</p>
            <div class="actions">
              <a class="button" href="./index.html">홈으로 이동</a>
              <a class="button secondary" href="./products/index.html">제품 보기</a>
              <a class="button ghost" href="./board/index.html">게시판 보기</a>
            </div>
          </div>
          <div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">바로 찾기</span><h3 style="font-size:1.72rem;margin:16px 0 10px">가격, 문서, 포털로도 바로 이동할 수 있습니다</h3><p>검토 중이라면 가격과 문서, 구매 이후라면 고객 포털부터 확인하시면 됩니다.</p><div class="small-actions"><a href="./pricing/index.html">가격</a><a href="./docs/index.html">문서</a><a href="./portal/index.html">포털</a></div></div>
        </div>
      </section>
    </main>
    ''')
    return doc(brand, f'404 | {brand["name"]}', '페이지를 찾을 수 없습니다.', 'not-found', body, depth=0, page_key='404', page_path='/404.html')


def robots_txt() -> str:
    return 'User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n'


def sitemap_xml(data: dict) -> str:
    brand = data['brand']
    paths = [
        '/', '/company/', '/engine/', '/products/', '/solutions/', '/pricing/', '/demo/', '/checkout/', '/board/', '/docs/', '/cases/', '/faq/', '/guides/', '/resources/', '/service/', '/portal/', '/contact/', '/onboarding/', '/legal/privacy/', '/legal/refund/', '/legal/terms/',
    ]
    for product in data.get('products', []):
        key = product['key']
        paths.extend([f'/products/{key}/', f'/products/{key}/board/', f'/docs/{key}/'])
    unique = []
    seen = set()
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    rows = ''.join(f'<url><loc>{escape(brand["domain"].rstrip("/") + path)}</loc></url>' for path in unique)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>'


def security_txt(data: dict) -> str:
    brand = data['brand']
    domain = brand['domain'].rstrip('/')
    email = brand.get('contact_email', '')
    return f'Contact: mailto:{email}\nPolicy: {domain}/legal/privacy/\nCanonical: {domain}/.well-known/security.txt\nPreferred-Languages: ko, en\n'


def favicon_svg(data: dict) -> str:
    label = escape(data['brand'].get('name', 'NV0')[:2])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="{label}"><rect width="64" height="64" rx="16" fill="#0f172a"/><text x="50%" y="56%" dominant-baseline="middle" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="26" font-weight="700" fill="#e2e8f0">N0</text></svg>'''

def favicon_ico_bytes() -> bytes:
    payload = 'AAABAAMAEBAAAAAAIACUAQAANgAAABgYAAAAACAAKQIAAMoBAAAgIAAAAAAgAFcBAADzAwAAiVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAABN0lEQVR4nM2TMU7DQBBF39k7QcQMCKk4A4kThKkoOAElJSUVR0Ah0dFyAAJCB0hD8Q6QhFFR0QFIC4QSWYl3d7NrbMmy0g4vWbP7vXl7C8D0uL29JQwDx3F49Lq6OvA8f5ZN0zQxpwk8zwvXdV1zHMepjuO46QY4juNhWZaN+76f5DgOALIsq6qqRh3HccYYxpgxDEO8p6cnQghCCLAsa2tr0zRNhBCG4biu2Wy2XC6n1+uFv78/AKCqKkVRxBiD53nM53NGo1EAcDweM45j3/cpFAr0er1kMhmappHruq4QghCC67q4rguA53mSJEmv14PneRRFkWQyGa1WiyzL0ul0aJpGURQAwHUdAKAoiqIoihBCmM1m2WyWcRxHlmUZx3Fks9mk02mYzWaC4ziKouD7Pi6XC5IkEQA8Ho8sy5LJZAKA4zhM08Tj8UjTNOm6jlKpRBAEAJqmQVEU2WyWwWAAANM0GQwGr9crJElCUZQsywIA4jiOqqp6vV6C4zhVVdFoNJKWZWq1Wi6XQ6/XA2Cz2TiO4/1+J7vdLh6Px3EcR57n+XweRVEwGAyA4zgcDoc8z/O4rsvz+TTvPw8AAH8ALbPNTC0JmQ4AAAAASUVORK5CYII='
    return base64.b64decode(payload)


def apply_page_overrides(dist: Path, data: dict):
    write(dist / 'index.html', build_home_page(data))
    write(dist / 'company' / 'index.html', build_company_page(data))
    write(dist / 'products' / 'index.html', build_products_page(data))
    write(dist / 'engine' / 'index.html', build_engine_page(data))
    write(dist / 'solutions' / 'index.html', build_solutions_page(data))
    write(dist / 'legal' / 'terms' / 'index.html', build_terms_page(data))
    write(dist / '404.html', build_404_page(data))
    write(dist / 'robots.txt', robots_txt())
    write(dist / 'sitemap.xml', sitemap_xml(data))
    write(dist / '.well-known' / 'security.txt', security_txt(data))
    write(dist / 'assets' / 'favicon.svg', favicon_svg(data))
    write_bytes(dist / 'favicon.ico', favicon_ico_bytes())
    for product in data['products']:
        write(dist / 'products' / product['key'] / 'index.html', build_product_page(data, product))
