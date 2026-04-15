import os
import json
from pathlib import Path
from html import escape
from textwrap import dedent
import shutil
from scripts.generate_compat_pages import generate_compat_pages
from scripts.board_only_postbuild import apply_board_only_overrides
from scripts.page_overrides import apply_page_overrides

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'src'
DIST = ROOT / 'dist'
DATA = json.loads((SRC / 'data' / 'site.json').read_text(encoding='utf-8'))
brand = DATA['brand']
products = DATA['products']
company_profile = DATA.get('company_profile', {})


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def write(path: Path, content: str):
    ensure_dir(path.parent)
    path.write_text(content, encoding='utf-8')


def rel_prefix(depth: int) -> str:
    return './' if depth == 0 else '../' * depth


def page_url(path: str) -> str:
    clean = path if path.startswith('/') else '/' + path
    if clean.endswith('index.html'):
        clean = clean[:-10]
    return brand['domain'].rstrip('/') + clean


def build_page_schema(title: str, description: str, page_path: str, page_key: str, product_key: str | None = None) -> str:
    canonical = page_url(page_path)
    schema = {
        '@context': 'https://schema.org',
        '@type': 'Product' if page_key == 'product' else 'WebPage',
        'name': title.split('|')[0].strip(),
        'description': description,
        'url': canonical,
        'inLanguage': 'ko-KR',
        'isPartOf': {'@type': 'WebSite', 'name': brand.get('name', 'NV0'), 'url': brand.get('domain', '').rstrip('/') + '/'},
    }
    if page_key == 'product' and product_key:
        schema['sku'] = product_key
        schema['brand'] = {'@type': 'Brand', 'name': brand.get('name', 'NV0')}
        schema['category'] = 'Automation SaaS'
    return json.dumps(schema, ensure_ascii=False, separators=(',', ':'))

def doc(title: str, description: str, body_class: str, body: str, depth: int = 0, page_key: str | None = None, product_key: str | None = None, page_path: str = '/'):
    prefix = rel_prefix(depth)
    resolved_key = page_key or body_class
    attrs = [f'class="{body_class}"', f'data-page="{resolved_key}"']
    if product_key:
        attrs.append(f'data-product="{product_key}"')
    canonical = page_url(page_path)
    og_type = 'product' if resolved_key == 'product' else 'website'
    schema_json = build_page_schema(title, description, page_path, resolved_key, product_key)
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


def timeline_markup() -> str:
    return ''.join(
        f'<article class="step"><strong>{escape(step["title"])}</strong><span>{escape(step["body"])}</span></article>'
        for step in DATA['engine']['steps']
    )


def company_sections_markup() -> str:
    return ''.join(
        f'<article class="story-card"><span class="tag">{idx + 1}</span><h3>{escape(item["title"])}</h3><p>{escape(item["body"])}</p></article>'
        for idx, item in enumerate(company_profile.get('sections', []))
    )


def product_shortcuts() -> str:
    return ''.join(
        f'<a class="button soft" href="./products/{escape(item["key"])}.html"></a>'
        for item in products
    )


def home_page() -> str:
    representative = products[0]
    return doc(
        f"{brand['title']}",
        brand['hero_description'],
        'home',
        dedent(f'''
        <main>
          <section class="hero">
            <div class="container hero-grid">
              <div class="card strong">
                <span class="kicker">{escape(brand['tagline'])}</span>
                <h1>{escape(brand['hero_title'])}</h1>
                <p class="lead">{escape(brand['hero_description'])}</p>
                <div class="actions">
                  <a class="button" href="./products/index.html">제품 비교하고 결과 먼저 보기</a>
                  <a class="button secondary" href="./products/{escape(representative['key'])}/index.html#demo">가장 많이 찾는 데모 바로 보기</a>
                  <a class="button ghost" href="./company/index.html">왜 잘 팔리게 보이는지 보기</a>
                </div>
                <div class="live-strip" id="live-stats"></div>
              </div>
              <div class="showcase-grid">
                <article class="card accent">
                  <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">왜 더 쉽게 팔리는가</span>
                  <h3 style="font-size:1.75rem;margin:16px 0 10px">소개보다 결과 확인이 먼저인 판매형 구성</h3>
                  <p>각 제품 페이지에서 실제 입력 예시와 결과 미리보기를 먼저 확인할 수 있습니다. 마음에 들면 가격, 전달 범위, 결제까지 자연스럽게 이어집니다.</p>
                  <div class="inline-list"><span>실제 입력</span><span>즉시 결과</span><span>결제 후 전달물</span></div>
                </article>
                <article class="card strong">
                  <span class="tag">어떻게 고르면 되나</span>
                  <h3>지금 가장 시급한 문제부터 골라 바로 확인하세요</h3>
                  <p class="lead" style="font-size:1rem">사이트 점검, 서류 정리, 제출 준비, 콘텐츠 마감처럼 지금 바로 손봐야 하는 일부터 고르면 됩니다. 제품명이 낯설어도 내 문제에 맞는 결과부터 먼저 확인할 수 있습니다.</p>
                  <div class="badge-row"><span class="badge">문제 선택</span><span class="badge">데모 실행</span><span class="badge">결과 검토</span><span class="badge">결제/전달</span></div>
                </article>
              </div>
            </div>
          </section>
          <section class="section compact"><div class="container"><div class="section-head"><div><h2>{escape(company_profile.get('headline', 'NV0 소개'))}</h2></div><p>{escape(company_profile.get('summary', ''))}</p></div><div class="timeline">{timeline_markup()}</div></div></section>
          <section class="section"><div class="container"><div class="section-head"><div><h2>지금 바로 확인할 수 있는 4개 실행형 제품</h2></div><p>각 카드는 제품 설명만 늘어놓지 않습니다. 어떤 팀에게 맞는지, 어떤 결과를 기대할 수 있는지, 결제 후 무엇을 받는지 한 번에 보이게 정리했습니다.</p></div><div class="product-grid" id="product-grid"></div></div></section>
        </main>
        '''),
        page_key='home',
        page_path='/index.html'
    )

def company_page() -> str:
    prefix = rel_prefix(1)
    principles = ''.join(f'<li>{escape(item)}</li>' for item in company_profile.get('principles', []))
    return doc(f"회사 | {brand['name']}", '엔브이제로 회사 소개', 'company', dedent(f'''
        <main>
          <section class="section">
            <div class="container page-hero">
              <div class="card strong">
                <div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>회사</span></div>
                <span class="kicker">Company</span>
                <h1>{escape(company_profile.get('headline', ''))}</h1>
                <p class="lead">{escape(company_profile.get('summary', ''))}</p>
                <div class="actions">
                  <a class="button" href="{prefix}products/index.html">제품 보러 가기</a>
                  <a class="button ghost" href="mailto:{escape(brand['contact_email'])}">제휴/문의</a>
                </div>
              </div>
              <div class="card accent">
                <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">운영 원칙</span>
                <h3 style="font-size:1.72rem;margin:16px 0 10px">읽기 쉬운 고객 화면과 정확한 운영 화면을 분리합니다</h3>
                <ul class="clean inverse-list">{principles}</ul>
              </div>
            </div>
          </section>
          <section class="section compact"><div class="container"><div class="section-head"><div><h2>NV0가 제품을 설계하는 방식</h2></div><p>홈에서는 문제를, 제품 페이지에서는 실제 데모를, 결제 뒤에는 전달 자료를 바로 보게 만드는 구조입니다.</p></div><div class="story-grid">{company_sections_markup()}</div></div></section>
        </main>
    '''), depth=1, page_key='company', page_path='/company/index.html')

def products_page() -> str:
    prefix = rel_prefix(1)
    return doc(f"제품 | {brand['name']}", 'NV0 제품 목록', 'products', dedent(f'''
      <main>
        <section class="section">
          <div class="container page-hero">
            <div class="card strong">
              <div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>제품</span></div>
              <span class="kicker">Products</span>
              <h1>우리 팀에 맞는 제품을 문제 기준으로 바로 고르세요</h1>
              <p class="lead">각 제품 상세에서 실제 입력 예시와 결과 미리보기를 먼저 보실 수 있습니다. 긴 설명을 읽기 전에 나에게 맞는지부터 빠르게 판단할 수 있습니다.</p>
            </div>
            <div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">공통 흐름</span><h3 style="font-size:1.72rem;margin:16px 0 10px">문제 확인 → 결과 미리보기 → 가격 검토 → 결제 → 전달</h3><p>소개만 읽고 끝나는 페이지가 아니라, 구매 판단과 다음 행동이 자연스럽게 이어지도록 다시 정리했습니다.</p></div>
          </div>
        </section>
        <section class="section compact"><div class="container"><div class="product-grid" id="product-grid"></div></div></section>
      </main>
    '''), depth=1, page_key='products', page_path='/products/index.html')

def board_page() -> str:
    prefix = rel_prefix(1)
    return doc(f"콘텐츠 허브 | {brand['name']}", '전체 제품 콘텐츠 허브', 'board', dedent(f"""
        <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>콘텐츠 허브</span></div><span class="kicker">콘텐츠 허브</span><h1>제품 이해를 돕는 글과 사례를 한곳에서 볼 수 있습니다</h1><p class="lead">처음 보는 분도 제품이 왜 필요한지 쉽게 이해하도록 글과 사례를 모았습니다. 읽다가 바로 제품 설명, 데모, 가격 확인으로 이어질 수 있습니다.</p><div class="actions"><a class="button secondary" href="{prefix}products/index.html">제품 목록</a><a class="button" href="{prefix}products/veridion/index.html#board">대표 제품 글 먼저 보기</a></div></div><div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">읽고 판단하기</span><h3 style="font-size:1.72rem;margin:16px 0 10px">먼저 읽어보고 마음에 들면 바로 제품 확인으로 넘어가면 됩니다</h3><p>게시판은 내부 운영 기록이 아니라 구매 판단을 돕는 콘텐츠 허브입니다. 읽은 뒤 바로 제품 확인과 데모, 가격 검토로 이어질 수 있습니다.</p></div></div></section><section class="section compact"><div class="container"><div class="board-grid" id="public-board-grid"></div><div id="public-post-detail"></div></div></section></main>
    """), depth=1, page_key='board', page_path='/board/index.html')


def demo_page() -> str:
    prefix = rel_prefix(1)
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])} · {escape(item["headline"])}' '</option>' for item in products)
    return doc(f"빠른 체험 | {brand['name']}", '제품 빠른 체험', 'demo', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>데모</span></div><span class="kicker">Quick demo</span><h1>관심 있는 제품을 골라 샘플 결과를 먼저 확인해 보세요</h1><p class="lead">샘플 결과를 먼저 보고 맞는 제품인지 판단하실 수 있습니다. 필요하시면 이어서 제품 상세, 가격, 결제까지 같은 흐름으로 진행하실 수 있습니다.</p><form id="demo-form"><div class="form-grid"><div><label>제품</label><select name="product" data-prefill="product" required>{options}</select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>연락처</label><input name="phone" placeholder="예: 010-1234-5678" inputmode="tel" autocomplete="tel"></div><div><label>팀 규모</label><input name="team" placeholder="예: 3인 운영팀" autocomplete="organization-title"></div><div><label>목표</label><input name="goal" placeholder="예: 첫 화면에서 바로 이해되게" required></div><div><label>핵심 키워드</label><input name="keywords" placeholder="예: 신뢰, CTA, 전환"></div><div><label>참고 링크</label><input name="link" placeholder="예: https://example.com" inputmode="url" autocomplete="url"></div><div><label>긴급도</label><select name="urgency"><option value="">선택</option><option>일반</option><option>이번 주 안</option><option>오늘 필요</option></select></div></div><div class="actions"><button class="button" type="submit">샘플 결과 확인하고 저장하기</button></div></form><div class="result-box" id="demo-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">바로가기</span><h3>맞는 제품을 골라 바로 이어서 확인하세요</h3><div class="story-grid" id="module-matrix"></div></article></div></section></main>
    '''), depth=1, page_key='demo', page_path='/demo/index.html')


def checkout_page() -> str:
    prefix = rel_prefix(1)
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])} · {escape(item["plans"][0]["price"])}부터' '</option>' for item in products)
    return doc(f"결제 | {brand['name']}", '제품 결제 및 결제 진입', 'checkout', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>결제</span></div><span class="kicker">Checkout</span><h1>선택한 제품을 바로 결제하고 전달 상태까지 확인하실 수 있습니다</h1><p class="lead">플랜을 고른 뒤 결제를 진행하시면 전달 자료 준비와 확인 흐름이 바로 이어집니다. 결제 후에는 결과 상태와 관련 자료를 고객 포털에서 확인하실 수 있습니다.</p><form id="checkout-form"><div class="form-grid"><div><label>제품</label><select name="product" data-prefill="product" required>{options}</select></div><div><label>플랜</label><select name="plan" data-prefill="plan" required><option value="Starter">Starter</option><option value="Growth">Growth</option><option value="Scale">Scale</option></select></div><div><label>결제 유형</label><select name="billing"><option value="one-time">1회 결제형</option></select></div><div><label>결제 방식</label><select name="paymentMethod" required><option value="toss">Toss 결제</option></select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>연락처</label><input name="phone" placeholder="예: 010-1234-5678" inputmode="tel" autocomplete="tel"></div><div><label>참고 링크</label><input name="link" placeholder="예: https://example.com" inputmode="url" autocomplete="url"></div><div><label>긴급도</label><select name="urgency"><option value="">선택</option><option>일반</option><option>이번 주 안</option><option>오늘 필요</option></select></div><div><label>희망 회신 시간</label><input name="reply_time" placeholder="예: 평일 오후 2시 이후"></div><div><label>추가 요청</label><input name="note" placeholder="예: 원하는 톤, 꼭 포함할 내용" autocomplete="off"></div></div><div class="actions"><button class="button" type="submit">이 내용으로 결제 진행하기</button></div><p class="micro-copy">결제 전 더 확인할 내용이 있으면 <a href="{prefix}legal/terms/index.html">이용약관</a>, <a href="{prefix}legal/refund/index.html">환불정책</a>, <a href="{prefix}contact/index.html">추가 확인</a>을 먼저 확인해 주세요.</p></form><div class="result-box" id="checkout-result" role="status" aria-live="polite"></div></article><article class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">결제 안내</span><h3 style="font-size:1.72rem;margin:16px 0 10px">결제가 끝나면 확인과 전달 흐름이 바로 이어집니다</h3><ul class="clean inverse-list"><li>플랜 확인</li><li>결제 진행</li><li>결제 완료 확인</li><li>결과물 준비</li><li>전달 상태 확인</li></ul></article></div></section></main>
    '''), depth=1, page_key='checkout', page_path='/checkout/index.html')


def contact_page() -> str:
    prefix = rel_prefix(1)
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])}' '</option>' for item in products)
    return doc(f"추가 확인 | {brand['name']}", '추가 확인', 'contact', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>추가 확인</span></div><span class="kicker">Contact</span><h1>페이지에서 바로 판단하기 어려운 조건만 남겨 주세요</h1><p class="lead">가격, 결과물, 적용 범위처럼 추가 설명이 필요한 조건만 남겨 주세요. 일반적인 비교와 데모는 제품 페이지에서 바로 확인하실 수 있습니다.</p><form id="contact-form"><div class="form-grid"><div><label>관심 제품</label><select name="product" data-prefill="product" required><option value="">선택</option>{options}</select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>연락처</label><input name="phone" placeholder="예: 010-1234-5678" inputmode="tel" autocomplete="tel"></div><div><label>참고 링크</label><input name="link" placeholder="예: https://example.com" inputmode="url" autocomplete="url"></div><div><label>긴급도</label><select name="urgency"><option value="">선택</option><option>일반</option><option>이번 주 안</option><option>오늘 필요</option></select></div><div><label>희망 회신 시간</label><input name="reply_time" placeholder="예: 평일 오전 10시~12시"></div><div><label>확인 내용</label><input name="issue" placeholder="예: 가격, 결과물, 적용 범위, 정산 방식" required></div></div><div class="actions"><button class="button" type="submit">조건 확인 요청 보내기</button></div><p class="micro-copy">특수 조건만 짧게 남겨 주시면 됩니다. 일반적인 비교와 데모는 각 제품 상세에서 바로 진행하실 수 있습니다.</p></form><div class="result-box" id="contact-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">안내</span><p>회사 소개는 회사 메뉴에서, 실제 데모 시연과 결제는 제품 메뉴에서, 자동 흐름에 없는 예외 조건만 이 페이지에서 남기실 수 있습니다.</p></article></div></section></main>
    '''), depth=1, page_key='contact', page_path='/contact/index.html')


def portal_page() -> str:
    prefix = rel_prefix(1)
    return doc(f"고객 포털 | {brand['name']}", '고객 조회 포털', 'portal', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>고객 포털</span></div><span class="kicker">결과 확인</span><h1>결제 후 전달 상태와 자료를 바로 확인해 보세요</h1><p class="lead">이메일과 조회 코드만 입력하면 결제 이후의 진행 상태와 결과 자료를 바로 확인할 수 있습니다. 같은 조회 코드 기준으로 간편하게 다시 찾을 수 있습니다.</p><form id="portal-lookup-form"><div class="form-grid"><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>조회 코드</label><input name="code" placeholder="예: NV0-2026-VER-001" autocapitalize="characters" autocomplete="off" required></div></div><div class="actions"><button class="button" type="submit">전달 상태 확인하기</button></div><p class="micro-copy">조회 코드는 결제 완료 또는 별도 안내 후 메일로 전달됩니다.</p></form><div class="result-box" id="portal-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">확인 결과</span><h3>전달 상태와 자료가 여기에 표시됩니다</h3><div class="mock-progress" id="portal-mock"><div class="mock-step"><strong>확인 전</strong><span>결제 후 받은 이메일과 조회 코드를 입력하면 바로 확인하실 수 있습니다.</span></div></div></article></div></section></main>
    '''), depth=1, page_key='portal', page_path='/portal/index.html')


def admin_page() -> str:
    prefix = rel_prefix(1)
    return doc(f"관리자 허브 | {brand['name']}", '운영 관리자 허브', 'admin', dedent(f'''
        <main id="admin-console">
          <section class="section">
            <div class="container page-hero">
              <div class="card strong">
                <div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>관리자 허브</span></div>
                <span class="kicker">Admin hub</span>
                <h1>관리 기능은 관리자 허브로만 모으고, 공개 화면에서는 감췄습니다</h1>
                <p class="lead">비밀키가 있어야 운영 화면을 열 수 있습니다. 주문·결제·전달·포털 연결은 자동으로 이어지며, 이 화면에서는 자동화 상태 확인과 운영 안전성 점검만 합니다.</p>
                <div class="result-box admin-gate" id="admin-gate-result">관리자 비밀키를 입력하면 운영 메뉴가 열립니다.</div>
                <div class="auth-inline admin-auth-inline">
                  <input id="admin-token-input" placeholder="관리자 비밀키" autocomplete="off" spellcheck="false">
                  <button class="button secondary" type="button" id="admin-token-save">관리자 열기</button>
                  <button class="button ghost" type="button" id="admin-token-clear">토큰 지우기</button>
                </div>
              </div>
              <div class="card accent">
                <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">운영 원칙</span>
                <h3 style="font-size:1.72rem;margin:16px 0 10px">공개 화면은 판매에 집중하고, 운영 화면은 자동화 상태만 확인</h3>
                <p>고객이 보는 화면에서는 데모와 결제만 남기고, 관리자 화면에서는 자동 처리 여부와 장애 징후만 확인합니다.</p>
              </div>
            </div>
          </section>
          <section class="section compact admin-shell" id="admin-shell">
            <div class="container admin-layout">
              <aside class="admin-sidebar card strong">
                <span class="tag">관리 메뉴</span>
                <nav class="admin-side-links">
                  <a href="#admin-overview">개요</a>
                  <a href="#admin-automation">자동발행 설정</a>
                  <a href="#admin-orders-section">주문/결제</a>
                  <a href="#admin-requests-section">요청</a>
                  <a href="#admin-publications-section">공개 글</a>
                </nav>
                <div class="result-box" id="admin-action-result">수동 보정 버튼은 기본 비활성화 상태입니다. 주문·결제·전달·콘텐츠 연결은 자동 흐름으로만 동작합니다.</div>
              </aside>
              <div class="admin-main-stack">
                <section id="admin-overview" class="admin-section"><div class="admin-grid" id="admin-summary"></div></section>
                <section id="admin-automation" class="admin-section"><div class="record-grid" id="admin-automation-grid"></div></section>
                <section id="admin-orders-section" class="admin-section"><div class="admin-stack" id="admin-orders"></div></section>
                <section id="admin-requests-section" class="admin-section"><div class="record-grid" id="admin-requests"></div></section>
                <section id="admin-publications-section" class="admin-section"><div class="record-grid" id="admin-publications"></div><div class="card strong"><div class="mock-progress" id="admin-feed"></div></div></section>
              </div>
            </div>
          </section>
        </main>
    '''), depth=1, page_key='admin', page_path='/admin/index.html')


def toss_success_page() -> str:
    prefix = rel_prefix(3)
    return doc(f"결제 승인 | {brand['name']}", 'Toss 결제 승인 처리', 'payment-success', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>결제 승인</span></div><span class="kicker">결제 완료</span><h1>결제가 완료되면 전달 상태 확인하기 화면으로 바로 이어집니다</h1><p class="lead">결제 승인 정보를 확인한 뒤, 전달 자료와 관련 안내를 바로 보실 수 있게 연결합니다.</p><div class="result-box" id="payment-success-result" style="display:block">결제 정보를 확인하고 있습니다.</div><div class="actions"><a class="button secondary" href="{prefix}portal/index.html">전달 상태 확인하기</a><a class="button ghost" href="{prefix}products/index.html">다른 제품 둘러보기</a></div></article></div></section></main>
    '''), depth=3, page_key='payment-success', page_path='/payments/toss/success/index.html')


def toss_fail_page() -> str:
    prefix = rel_prefix(3)
    return doc(f"결제 실패 | {brand['name']}", 'Toss 결제 실패 안내', 'payment-fail', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>결제 실패</span></div><span class="kicker">Toss fail</span><h1>결제가 아직 완료되지 않았습니다</h1><p class="lead">잠시 후 다시 결제하시거나, 추가 설명이 필요한 조건만 남겨 주세요.</p><div class="result-box" id="payment-fail-result" style="display:block">실패 정보를 확인하고 있습니다.</div><div class="actions"><a class="button" href="{prefix}checkout/index.html">결제 다시 시도하기</a><a class="button ghost" href="{prefix}contact/index.html">조건 확인 남기기</a></div></article></div></section></main>
    '''), depth=3, page_key='payment-fail', page_path='/payments/toss/fail/index.html')


def product_page(product: dict) -> str:
    prefix = rel_prefix(2)
    fit_markup = ''.join(f'<li>{escape(item)}</li>' for item in product.get('fit_for', [])[:3])
    return doc(f"{product['name']} | {brand['name']}", product['summary'], product['theme'], dedent(f'''
        <main>
          <section class="section">
            <div class="container page-hero">
              <div class="card strong">
                <div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><a href="{prefix}products/index.html">제품</a><span class="sep">/</span><span>{escape(product['name'])}</span></div>
                <span class="tag theme-chip">{escape(product['label'])}</span>
                <h1 data-fill="product-name"></h1>
                <p class="lead" data-fill="product-headline"></p>
                <div class="actions" id="product-actions"></div>
                <div class="inline-tabs">
                  <a href="#intro">제품 소개</a>
                  <a href="#demo">실제 데모</a>
                  <a href="#order">플랜/결제</a>
                  <a href="#delivery">전달 범위</a>
                  <a href="#faq">FAQ</a>
                </div>
              </div>
              <div class="card theme-panel">
                <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">이럴 때 쓰는 제품</span>
                <h3 style="font-size:1.75rem;margin:16px 0 10px">{escape(product['problem'])}</h3>
                <p data-fill="product-summary"></p>
                <ul class="clean inverse-list">{fit_markup}</ul>
              </div>
            </div>
          </section>

          <section class="section compact" id="intro">
            <div class="container">
              <div class="section-head"><div><h2>이 제품으로 바로 바뀌는 것</h2></div><p>긴 설명보다 실제로 어떤 결과를 기대할 수 있는지 기준으로 정리했습니다.</p></div>
              <div class="story-grid product-overview-grid">
                <article class="story-card"><span class="tag theme-chip">해결하는 문제</span><h3>지금 가장 먼저 해결할 문제</h3><p data-fill="product-problem"></p></article>
                <article class="story-card"><span class="tag theme-chip">핵심 가치</span><h3>도입하면 바로 체감되는 변화</h3><ul class="clean" id="product-values"></ul></article>
                <article class="story-card"><span class="tag theme-chip">결과물</span><h3>결제 후 받는 자료</h3><ul class="clean" id="product-outputs"></ul></article>
              </div>
            </div>
          </section>

          <section class="section compact" id="demo">
            <div class="container module-layout demo-layout">
              <article class="card strong demo-main-card">
                <span class="tag theme-chip">실제 데모</span>
                <h3>입력하면 어떤 결과가 나오는지 바로 보이게 만들었습니다</h3>
                <p class="lead demo-intro-copy">소개 문장보다, 어떤 입력을 넣었을 때 어떤 결과가 나오는지를 먼저 확인하실 수 있습니다. 저장이 필요할 때만 회사명과 이메일을 남기시면 됩니다.</p>
                <div id="product-demo-shell"></div>
                <div class="result-box" id="product-demo-result" role="status" aria-live="polite"></div>
              </article>
              <article class="card demo-side-card">
                <span class="tag">데모에서 확인되는 것</span>
                <h3>실제 구매 판단에 도움이 되는 결과만 보여드립니다</h3>
                <ul class="clean" id="product-demo-scenarios"></ul>
                <div class="notice notice-light"><strong>가격 기준</strong><br><span data-fill="product-pricing"></span></div>
                <div class="notice"><strong>가격 판단 기준</strong><br><span id="product-pricing-basis"></span></div>
              </article>
            </div>
          </section>

          <section class="section compact" id="order">
            <div class="container module-layout">
              <article class="card strong">
                <span class="tag theme-chip">플랜/결제</span>
                <h3>데모로 맞는지 확인한 뒤 바로 결제할 수 있습니다</h3>
                <form id="product-checkout-form" class="stack-form">
                  <input type="hidden" name="product" value="{escape(product['key'])}">
                  <div class="form-grid">
                    <div><label>플랜</label><select name="plan" data-prefill="plan" required><option value="Starter">Starter</option><option value="Growth">Growth</option><option value="Scale">Scale</option></select></div>
                    <div><label>결제 유형</label><select name="billing"><option value="one-time">1회 결제형</option></select></div>
                    <div><label>결제 방식</label><select name="paymentMethod" required><option value="toss">Toss 결제</option></select></div>
                    <div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div>
                    <div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div>
                    <div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div>
                    <div><label>연락처</label><input name="phone" placeholder="예: 010-1234-5678" inputmode="tel" autocomplete="tel"></div>
                    <div><label>참고 링크</label><input name="link" placeholder="예: https://example.com" inputmode="url" autocomplete="url"></div>
                    <div><label>긴급도</label><select name="urgency"><option value="">선택</option><option>일반</option><option>이번 주 안</option><option>오늘 필요</option></select></div>
                    <div><label>추가 요청</label><input name="note" placeholder="예: 꼭 포함할 기준이나 원하는 결과" autocomplete="off"></div>
                  </div>
                  <div class="consent-panel"><div class="consent-copy"><strong>개인정보 수집·이용 안내</strong><p>입력하신 정보는 제품별 주문 등록, 결제 준비, 결과 제공을 위해 사용합니다. 자세한 내용은 <a href="../../legal/privacy/index.html">개인정보처리방침</a>에서 확인하실 수 있습니다.</p></div><label class="consent-check"><input type="checkbox" name="privacyConsent" value="yes" required data-consent-required="1"> <span>개인정보 수집·이용에 동의합니다.</span></label><small data-consent-message>동의 후에만 주문과 결제를 진행할 수 있습니다.</small></div>
                  <div class="notice" id="product-checkout-plan-summary" data-plan-summary="product" aria-live="polite">선택한 제품과 플랜 요약이 여기에 표시됩니다.</div>
                  <div class="actions"><button class="button" type="submit">이 내용으로 결제 진행하기</button><a class="button secondary" href="#delivery">전달 범위 먼저 보기</a></div>
                  <p class="micro-copy">데모에서 입력한 기본 정보는 결제 단계로 자연스럽게 이어질 수 있습니다.</p>
                </form>
                <div class="result-box" id="product-checkout-result" role="status" aria-live="polite"></div>
              </article>
              <article class="card"><span class="tag">플랜 요약</span><h3>현재 제공 중인 플랜</h3><div class="plan-grid" id="plan-grid"></div></article>
            </div>
          </section>

          <section class="section compact" id="delivery">
            <div class="container module-layout">
              <article class="card strong">
                <span class="tag theme-chip">결제 후 전달 범위</span>
                <h3>샘플 결과에서 본 흐름이 실제 전달 자료로 이어집니다</h3>
                <ol class="flow-list" id="product-workflow"></ol>
                <div class="notice">결제 후에는 결과 요약, 실행 자료, 조회 코드가 연결된 확인 흐름까지 한 번에 이어집니다.</div>
              </article>
              <article class="card strong">
                <span class="tag theme-chip">함께 보면 좋은 제품</span>
                <h3>비슷한 고민이 있다면 함께 보기 좋은 제품</h3>
                <div class="story-grid" id="product-related-modules"></div>
              </article>
            </div>
          </section>

          <section class="section compact" id="board">
            <div class="container"><div class="section-head"><div><h2>{escape(product['name'])} 관련 글</h2></div><p>이 제품이 필요한 상황을 더 읽어보고 싶다면 아래 글을 참고해 주세요. 다만 가장 빠른 판단은 위 데모에서 하실 수 있습니다.</p></div><div class="board-grid" id="product-board-grid"></div><div id="product-post-detail"></div></div>
          </section>

          <section class="section compact" id="faq"><div class="container"><div class="section-head"><div><h2>자주 묻는 질문</h2></div><p>결제 전에 자주 나오는 질문을 한곳에 모아두었습니다.</p></div><div class="faq-grid" id="product-faq"></div></div></section>
        </main>
    '''), depth=2, page_key='product', product_key=product['key'], page_path=f'/products/{product["key"]}/index.html')

def product_board_page(product: dict) -> str:
    return doc(f"{product['name']} 게시판 | {brand['name']}", f"{product['name']} 콘텐츠 허브", product['theme'], dedent(f'''
        <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../../index.html">HOME</a><span class="sep">/</span><a href="../../../products/index.html">제품</a><span class="sep">/</span><a href="../../{escape(product['key'])}/index.html">{escape(product['name'])}</a><span class="sep">/</span><span>게시판</span></div><span class="tag theme-chip">관련 글 모음</span><h1>{escape(product['name'])} 콘텐츠 허브</h1><p class="lead">이 제품과 관련된 글을 먼저 읽고, 바로 제품 설명·실제 데모·결제로 이어질 수 있게 구성했습니다.</p><div class="actions"><a class="button" href="../../{escape(product['key'])}/index.html#demo">데모 시연</a><a class="button secondary" href="../../{escape(product['key'])}/index.html#intro">제품 설명 보기</a><a class="button ghost" href="../../{escape(product['key'])}/index.html#order">결제 진행</a></div></div><div class="card theme-panel"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">게시판 안내</span><h3 style="font-size:1.7rem;margin:16px 0 10px">구매 전 가볍게 읽어보기 좋은 글을 모아두었습니다</h3><p>{escape(product['summary'])}</p></div></div></section><section class="section compact"><div class="container"><div class="board-grid" id="product-board-grid"></div><div id="product-post-detail"></div></div></section></main>
    '''), depth=3, page_key='product-board', product_key=product['key'], page_path=f'/products/{product["key"]}/board/index.html')


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / 'assets').mkdir(parents=True, exist_ok=True)
    write(DIST / 'assets' / 'site.css', (SRC / 'assets' / 'site.css').read_text(encoding='utf-8'))
    write(DIST / 'assets' / 'site.js', (SRC / 'assets' / 'site.js').read_text(encoding='utf-8'))
    write(DIST / 'assets' / 'site-data.js', 'window.NV0_SITE_DATA = ' + json.dumps(DATA, ensure_ascii=False, indent=2) + ';')
    pages = {
        DIST / 'index.html': home_page(),
        DIST / 'company' / 'index.html': company_page(),
        DIST / 'products' / 'index.html': products_page(),
        DIST / 'engine' / 'index.html': products_page(),
        DIST / 'solutions' / 'index.html': products_page(),
        DIST / 'board' / 'index.html': board_page(),
        DIST / 'demo' / 'index.html': demo_page(),
        DIST / 'checkout' / 'index.html': checkout_page(),
        DIST / 'contact' / 'index.html': contact_page(),
        DIST / 'portal' / 'index.html': portal_page(),
        DIST / 'admin' / 'index.html': admin_page(),
        DIST / 'payments' / 'toss' / 'success' / 'index.html': toss_success_page(),
        DIST / 'payments' / 'toss' / 'fail' / 'index.html': toss_fail_page(),
    }
    for path, content in pages.items():
        write(path, content)
    for item in products:
        write(DIST / 'products' / item['key'] / 'index.html', product_page(item))
        write(DIST / 'products' / item['key'] / 'board' / 'index.html', product_board_page(item))
    generate_compat_pages(DIST, DATA)
    apply_page_overrides(DIST, DATA)
    board_only_mode = os.getenv('NV0_BOARD_ONLY_MODE', '0').lower() in {'1', 'true', 'yes', 'on'}
    if board_only_mode:
        apply_board_only_overrides(DIST, DATA, SRC)
    print('Build completed:', DIST, '(board-only)' if board_only_mode else '(full)')


if __name__ == '__main__':
    main()
