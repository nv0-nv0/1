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


def doc(title: str, description: str, body_class: str, body: str, depth: int = 0, page_key: str | None = None, product_key: str | None = None, page_path: str = '/'):
    prefix = rel_prefix(depth)
    attrs = [f'class="{body_class}"', f'data-page="{page_key or body_class}"']
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
  <link rel="canonical" href="{escape(page_url(page_path))}">
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
        f"{brand['title']} | Company + Products",
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
                  <a class="button secondary" href="./company/index.html">회사 기준 보기</a>
                  <a class="button" href="./products/index.html">제품 바로 보기</a>
                  <a class="button ghost" href="./products/{escape(representative['key'])}/index.html#demo">대표 제품 데모 시연</a>
                </div>
                <div class="live-strip" id="live-stats"></div>
              </div>
              <div class="showcase-grid">
                <article class="card accent">
                  <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">회사</span>
                  <h3 style="font-size:1.75rem;margin:16px 0 10px">회사 메뉴는 브랜드 기준과 운영 구조를 보여드립니다</h3>
                  <p>회사 메뉴에서는 NV0가 어떤 기준으로 제품을 만들고 운영하는지 간결하게 보여드립니다. 실제 비교와 결제는 제품 메뉴에서 바로 이어집니다.</p>
                  <div class="inline-list"><span>브랜드 소개</span><span>고객 기준</span><span>제휴 안내</span></div>
                </article>
                <article class="card strong">
                  <span class="tag">제품</span>
                  <h3>제품 메뉴 안에서 자동발행게시판부터 결제와 정상작동 및 발행 제공까지 한 번에 이어집니다</h3>
                  <p class="lead" style="font-size:1rem">각 제품 상세는 자동발행게시판을 먼저 보고, 제품 설명을 이해하고, 데모 시연 뒤 결제하면 바로 정상작동 및 발행 제공까지 이어지는 실행형 페이지입니다.</p>
                  <div class="badge-row"><span class="badge">데모 시연</span><span class="badge">결제</span><span class="badge">정상작동 및 발행 제공</span><span class="badge">자동발행 글 함께 보기</span></div>
                </article>
              </div>
            </div>
          </section>
          <section class="section compact"><div class="container"><div class="section-head"><div><h2>{escape(company_profile.get('headline', 'NV0 소개'))}</h2></div><p>{escape(company_profile.get('summary', ''))}</p></div><div class="timeline">{timeline_markup()}</div></div></section>
          <section class="section"><div class="container"><div class="section-head"><div><h2>고객 상황에 맞춰 바로 비교하고 선택할 수 있는 4개 제품</h2></div><p>제품 메뉴를 누르면 각 제품으로 이동해 자동발행게시판·제품 설명·데모 시연·결제·정상작동 및 발행 제공까지 바로 이어집니다. AI 자동발행 블로그 허브는 제품 상세 상단에서 먼저 확인할 수 있습니다.</p></div><div class="product-grid" id="product-grid"></div></div></section>
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
                  <a class="button secondary" href="{prefix}products/index.html">제품 보기</a>
                  <a class="button ghost" href="mailto:{escape(brand['contact_email'])}">제휴/안내</a>
                </div>
              </div>
              <div class="card accent">
                <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">고객 기준</span>
                <h3 style="font-size:1.72rem;margin:16px 0 10px">이해하기 쉽고 결정하기 쉬운 제품 경험을 우선합니다</h3>
                <ul class="clean inverse-list">{principles}</ul>
              </div>
            </div>
          </section>
          <section class="section compact"><div class="container"><div class="section-head"><div><h2>회사 메뉴에서 보실 내용</h2></div><p>이 메뉴는 NV0 소개 전용입니다. 제품 비교와 체험, 결제는 제품 메뉴에서 바로 진행하실 수 있습니다.</p></div><div class="story-grid">{company_sections_markup()}</div></div></section>
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
              <h1>지금 막힌 문제를 기준으로 제품을 고르고 데모 시연해 보세요</h1>
              <p class="lead">각 제품 상세 안에서 자동발행게시판, 제품 설명, 데모 시연, 결제, 정상작동 및 발행 제공까지 자연스럽게 이어집니다. AI 자동발행 블로그 허브는 제품 상세 상단에서 먼저 둘러볼 수 있습니다.</p>
            </div>
            <div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">결제 흐름</span><h3 style="font-size:1.72rem;margin:16px 0 10px">자동발행게시판 → 제품 설명 → 데모 시연 → 결제 → 정상작동 및 발행 제공</h3><p>복잡한 문의 절차보다, 직접 써보고 바로 결정할 수 있는 흐름을 우선합니다.</p></div>
          </div>
        </section>
        <section class="section compact"><div class="container"><div class="product-grid" id="product-grid"></div></div></section>
      </main>
    '''), depth=1, page_key='products', page_path='/products/index.html')


def board_page() -> str:
    prefix = rel_prefix(1)
    return doc(f"AI 자동발행 블로그 허브 | {brand['name']}", '전체 제품 AI 자동발행 블로그 허브', 'board', dedent(f'''
        <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>AI 자동발행 블로그 허브</span></div><span class="kicker">AI 자동발행 글</span><h1>제품을 보기 전에 먼저 읽어보면 좋은 AI 블로그 글을 한곳에서 볼 수 있습니다</h1><p class="lead">각 제품에 맞춘 AI 자동발행 블로그 글을 먼저 읽고, 마음이 생기면 제품 설명·데모 시연·결제 CTA로 이어질 수 있습니다.</p><div class="actions"><a class="button secondary" href="{prefix}products/index.html">제품 목록</a><a class="button" href="{prefix}products/veridion/index.html#board">대표 제품 AI 글 먼저 보기</a></div></div><div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">자동화</span><h3 style="font-size:1.72rem;margin:16px 0 10px">먼저 읽고 공감한 뒤 바로 제품 설명을 보고 데모 시연과 결제로 이어갈 수 있습니다</h3><p>게시판은 짧은 카드 목록이 아니라 AI가 초안을 잡아 준 블로그형 글 허브로 작동합니다. 글을 읽은 뒤 제품 설명과 데모 시연, 결제 단계로 바로 넘어갈 수 있습니다.</p></div></div></section><section class="section compact"><div class="container"><div class="board-grid" id="public-board-grid"></div><div id="public-post-detail"></div></div></section></main>
    '''), depth=1, page_key='board', page_path='/board/index.html')


def demo_page() -> str:
    prefix = rel_prefix(1)
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])} · {escape(item["headline"])}' '</option>' for item in products)
    return doc(f"빠른 체험 | {brand['name']}", '제품 빠른 체험', 'demo', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>데모</span></div><span class="kicker">Quick demo</span><h1>관심 있는 제품을 골라 바로 샘플 결과를 확인해 보세요</h1><p class="lead">샘플 결과를 바로 확인하면서 데모 신청 정보도 함께 저장됩니다. 마음에 들면 같은 흐름으로 제품 상세에서 데모 시연과 결제까지 이어가실 수 있습니다.</p><form id="demo-form"><div class="form-grid"><div><label>제품</label><select name="product" data-prefill="product" required>{options}</select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>팀 규모</label><input name="team" placeholder="예: 3인 운영팀" autocomplete="organization-title"></div><div><label>목표</label><input name="goal" placeholder="예: 첫 화면에서 바로 이해되게" required></div><div><label>핵심 키워드</label><input name="keywords" placeholder="예: 신뢰, CTA, 전환"></div></div><div class="actions"><button class="button" type="submit">무료 샘플과 데모 시연 자료 받기</button></div></form><div class="result-box" id="demo-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">바로가기</span><h3>마음에 드는 제품으로 바로 이어서 검토하세요</h3><div class="story-grid" id="module-matrix"></div></article></div></section></main>
    '''), depth=1, page_key='demo', page_path='/demo/index.html')


def checkout_page() -> str:
    prefix = rel_prefix(1)
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])} · {escape(item["plans"][0]["price"])}부터' '</option>' for item in products)
    return doc(f"결제 | {brand['name']}", '제품 결제 및 결제 진입', 'checkout', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>결제</span></div><span class="kicker">Checkout</span><h1>선택한 제품을 바로 결제하고 정상작동 및 발행 제공까지 확인할 수 있습니다</h1><p class="lead">플랜을 고르고 1회 결제 버튼을 누르면 외부 결제창으로 이동합니다. 결제 완료 뒤에는 정상작동 설정과 발행 제공 자료를 바로 확인할 수 있고, 자동발행 글도 함께 둘러보실 수 있습니다.</p><form id="checkout-form"><div class="form-grid"><div><label>제품</label><select name="product" data-prefill="product" required>{options}</select></div><div><label>플랜</label><select name="plan" data-prefill="plan" required><option value="Starter">Starter</option><option value="Growth">Growth</option><option value="Scale">Scale</option></select></div><div><label>결제 유형</label><select name="billing"><option value="one-time">1회 결제형</option></select></div><div><label>결제 방식</label><select name="paymentMethod" required><option value="toss">Toss 결제</option></select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>추가 요청</label><input name="note" placeholder="예: 원하는 톤, 꼭 포함할 내용" autocomplete="off"></div></div><div class="actions"><button class="button" type="submit">결제 계속하기</button></div></form><div class="result-box" id="checkout-result" role="status" aria-live="polite"></div></article><article class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">결제 안내</span><h3 style="font-size:1.72rem;margin:16px 0 10px">결제가 완료되면 정상작동 설정과 발행 제공이 자동으로 이어집니다</h3><ul class="clean inverse-list"><li>플랜 확인</li><li>전자동 결제 진행</li><li>결제 완료 확인</li><li>결과물 준비</li><li>정상작동 및 제공 상태 확인</li></ul></article></div></section></main>
    '''), depth=1, page_key='checkout', page_path='/checkout/index.html')


def contact_page() -> str:
    prefix = rel_prefix(1)
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])}' '</option>' for item in products)
    return doc(f"추가 확인 | {brand['name']}", '추가 확인', 'contact', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>추가 확인</span></div><span class="kicker">Contact</span><h1>자동 흐름으로 판단하기 어려운 조건만 추가 확인해 보세요</h1><p class="lead">가격, 결과물, 결제 방식처럼 자동 흐름에서 바로 판단하기 어려운 조건만 이 폼으로 남기실 수 있습니다. 전자동 흐름을 우선으로 두고, 예외 조건만 따로 확인하는 용도입니다.</p><form id="contact-form"><div class="form-grid"><div><label>관심 제품</label><select name="product" data-prefill="product" required><option value="">선택</option>{options}</select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>확인 내용</label><input name="issue" placeholder="예: 가격, 결과물, 적용 범위, 정산 방식" required></div></div><div class="actions"><button class="button" type="submit">추가 확인 요청 보내기</button></div></form><div class="result-box" id="contact-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">안내</span><p>회사 소개는 회사 메뉴에서, 실제 데모 시연과 결제는 제품 메뉴에서, 자동 흐름에 없는 예외 조건만 이 페이지에서 남기실 수 있습니다.</p></article></div></section></main>
    '''), depth=1, page_key='contact', page_path='/contact/index.html')


def portal_page() -> str:
    prefix = rel_prefix(1)
    return doc(f"고객 포털 | {brand['name']}", '고객 조회 포털', 'portal', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>고객 포털</span></div><span class="kicker">정상작동 및 발행 제공</span><h1>결제 후 정상작동 상태와 발행 제공 자료를 바로 확인해 보세요</h1><p class="lead">이메일과 조회 코드만 입력하면 결제 이후의 정상작동 상태와 발행 제공 자료를 바로 확인할 수 있습니다. Toss 결제든 세금계산서 안내든 같은 조회 코드 기준으로 확인합니다.</p><form id="portal-lookup-form"><div class="form-grid"><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>조회 코드</label><input name="code" placeholder="예: NV0-2026-VER-001" autocapitalize="characters" autocomplete="off" required></div></div><div class="actions"><button class="button" type="submit">정상작동 및 발행 제공 확인</button></div></form><div class="result-box" id="portal-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">확인 결과</span><h3>정상작동 상태와 발행 제공 자료가 여기에 표시됩니다</h3><div class="mock-progress" id="portal-mock"><div class="mock-step"><strong>확인 전</strong><span>결제 후 받은 이메일과 조회 코드를 입력하면 바로 확인하실 수 있습니다.</span></div></div></article></div></section></main>
    '''), depth=1, page_key='portal', page_path='/portal/index.html')


def admin_page() -> str:
    prefix = rel_prefix(1)
    return doc(f"관리자 허브 | {brand['name']}", '운영 관리자 허브', 'admin', dedent(f'''
        <main id="admin-console"><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>관리자 허브</span></div><span class="kicker">Admin hub</span><h1>결제, 데모, 발행, 포털 상태를 한곳에서 관리합니다</h1><p class="lead">운영자는 이 화면에서 샘플 데이터를 만들고, 결제 상태를 조정하고, AI 자동발행 블로그 허브를 재발행할 수 있습니다.</p><div class="auth-inline"><input id="admin-token-input" placeholder="관리자 토큰" autocomplete="off" spellcheck="false"><button class="button secondary" type="button" id="admin-token-save">토큰 저장</button><button class="button ghost" type="button" id="admin-token-clear">토큰 지우기</button></div><div class="toolbar"><button class="button" data-admin-action="seed-demo">샘플 데이터 생성</button><button class="button secondary" data-admin-action="reset-all">엔진 데이터 초기화</button></div><div class="result-box" id="admin-action-result"></div></div><div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">운영 목적</span><h3 style="font-size:1.72rem;margin:16px 0 10px">1인 운영 기준으로 확인 비용을 줄이는 허브</h3><p>반복 확인을 줄이기 위해 결제, 자동 제공, 발행을 같은 기록선으로 관리합니다.</p></div></div></section><section class="section compact"><div class="container"><div class="admin-grid" id="admin-summary"></div></div></section><section class="section compact"><div class="container"><div class="admin-stack" id="admin-orders"></div></div></section><section class="section compact"><div class="container"><div class="record-grid" id="admin-requests"></div></div></section><section class="section compact"><div class="container"><div class="record-grid" id="admin-publications"></div></div></section><section class="section compact"><div class="container"><div class="card strong"><div class="mock-progress" id="admin-feed"></div></div></div></section></main>
    '''), depth=1, page_key='admin', page_path='/admin/index.html')


def toss_success_page() -> str:
    prefix = rel_prefix(3)
    return doc(f"결제 승인 | {brand['name']}", 'Toss 결제 승인 처리', 'payment-success', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>결제 승인</span></div><span class="kicker">결제 완료</span><h1>결제가 완료되면 정상작동 및 발행 제공 화면으로 바로 이어집니다</h1><p class="lead">결제 승인 정보를 확인한 뒤, 정상작동 설정과 발행 제공 자료를 바로 보여드리고 관련 자동발행 글도 함께 확인할 수 있게 안내합니다.</p><div class="result-box" id="payment-success-result" style="display:block">결제 정보를 확인하고 있습니다.</div><div class="actions"><a class="button secondary" href="{prefix}portal/index.html">정상작동 및 발행 제공 확인</a><a class="button ghost" href="{prefix}products/index.html">다른 제품 보기</a></div></article></div></section></main>
    '''), depth=3, page_key='payment-success', page_path='/payments/toss/success/index.html')


def toss_fail_page() -> str:
    prefix = rel_prefix(3)
    return doc(f"결제 실패 | {brand['name']}", 'Toss 결제 실패 안내', 'payment-fail', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>결제 실패</span></div><span class="kicker">Toss fail</span><h1>결제가 완료되지 않았습니다</h1><p class="lead">잠시 후 다시 결제하시거나, 자동 흐름에 없는 예외 조건만 추가 확인으로 남겨주세요.</p><div class="result-box" id="payment-fail-result" style="display:block">실패 정보를 확인하고 있습니다.</div><div class="actions"><a class="button" href="{prefix}checkout/index.html">다시 시작하기</a><a class="button ghost" href="{prefix}contact/index.html">추가 확인 남기기</a></div></article></div></section></main>
    '''), depth=3, page_key='payment-fail', page_path='/payments/toss/fail/index.html')


def product_page(product: dict) -> str:
    prefix = rel_prefix(2)
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
                  <a href="#board">AI 자동발행 블로그 허브</a>
                  <a href="#intro">제품 소개</a>
                  <a href="#demo">데모</a>
                  <a href="#order">결제 진행</a>
                  <a href="#payment">자동 제공 안내</a>
                  <a href="#delivery">정상작동 및 발행 제공</a>
                </div>
              </div>
              <div class="card theme-panel">
                <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">이런 분께 잘 맞습니다</span>
                <h3 style="font-size:1.75rem;margin:16px 0 10px">{escape(product['problem'])}</h3>
                <p data-fill="product-summary"></p>
                <div class="notice notice-light"><strong>가격 기준</strong><br><span data-fill="product-pricing"></span></div>
              </div>
            </div>
          </section>
          <section class="section compact" id="board"><div class="container"><div class="section-head"><div><h2>{escape(product['name'])} AI 자동발행 블로그 허브</h2></div><p>제품을 자세히 보기 전에 먼저 읽어보면 좋은 AI 자동발행 블로그 홍보 글을 모아두었습니다. 연관 주제 글을 충분히 읽고, 마음이 정리되면 제품 설명·데모 시연·결제로 이어질 수 있습니다.</p></div><div class="board-grid" id="product-board-grid"></div><div id="product-post-detail"></div></div></section>
          <section class="section compact" id="intro"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">핵심 가치</span><h3>이 제품으로 바로 달라지는 점</h3><ul class="clean" id="product-values"></ul></article><article class="card strong"><span class="tag theme-chip">결과물</span><h3>결제 후 받아보는 자료</h3><ul class="clean" id="product-outputs"></ul></article></div></section>
          <section class="section compact" id="demo"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">데모 시연</span><h3>몇 가지 정보만 입력하면 샘플 결과를 바로 보고 데모 시연 자료까지 확인할 수 있습니다</h3><form id="product-demo-form" class="stack-form"><div class="form-grid"><div><label>회사명</label><input name="company" data-demo-field="company" placeholder="샘플 브랜드" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" data-demo-field="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" data-demo-field="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>팀 규모</label><input name="team" data-demo-field="team" placeholder="예: 2인 운영팀" autocomplete="organization-title"></div><div><label>목표</label><input name="goal" data-demo-field="goal" placeholder="예: CTA 전환 개선" required></div><div><label>핵심 키워드</label><input name="keywords" data-demo-field="keywords" placeholder="예: 랜딩, CTA, 신뢰"></div><div><label>플랜 미리보기</label><select name="plan" data-demo-field="plan"><option value="Starter">Starter</option><option value="Growth">Growth</option><option value="Scale">Scale</option></select></div></div><div class="actions"><button class="button" type="submit">데모 시연 시작하기</button><a class="button ghost" href="#order">이 조건으로 결제 계속하기</a></div></form><div class="result-box" id="product-demo-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">체험 포인트</span><h3>데모에서 먼저 보시면 좋은 항목</h3><ul class="clean" id="product-demo-scenarios"></ul></article></div></section>
          <section class="section compact" id="order"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">결제</span><h3>플랜을 고른 뒤 1회 결제 정보를 입력하면 전자동 실행 준비까지 한 번에 정리됩니다</h3><form id="product-checkout-form" class="stack-form"><input type="hidden" name="product" value="{escape(product['key'])}"><div class="form-grid"><div><label>플랜</label><select name="plan" data-prefill="plan" required><option value="Starter">Starter</option><option value="Growth">Growth</option><option value="Scale">Scale</option></select></div><div><label>결제 유형</label><select name="billing"><option value="one-time">1회 결제형</option></select></div><div><label>결제 방식</label><select name="paymentMethod" required><option value="toss">Toss 결제</option></select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>추가 요청</label><input name="note" placeholder="예: 원하는 톤, 꼭 포함할 내용" autocomplete="off"></div></div><div class="actions"><button class="button" type="submit">결제 계속하기</button><a class="button secondary" href="#payment">자동 실행 안내 보기</a></div></form><div class="result-box" id="product-checkout-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">플랜</span><h3>지금 바로 선택할 수 있는 플랜</h3><div class="plan-grid" id="plan-grid"></div></article></div></section>
          <section class="section compact" id="payment"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">자동 제공 안내</span><h3>결제가 완료되면 정상작동 설정과 발행 제공이 자동으로 이어집니다</h3><ol class="flow-list"><li>결제 정보를 먼저 저장합니다.</li><li>Toss 결제를 선택하면 외부 결제창으로 바로 이동합니다.</li><li>전자동 결제가 확인되면 결과 자료와 자동발행 글이 즉시 생성됩니다.</li><li>정상작동 설정과 발행 제공 상태가 같은 조회 코드로 묶입니다.</li><li>포털에서 결과 자료와 자동발행 글을 함께 확인합니다.</li></ol><div class="notice">전자동 실행이 기본입니다. 기업 정산이 필요한 경우에도 먼저 자동 흐름과 동일한 결과 기준을 맞춘 뒤 별도 확인으로 이어집니다.</div></article><article class="card strong"><span class="tag theme-chip">가격 기준</span><h3>시장 비교 기준</h3><p id="product-pricing-basis"></p><div class="notice">처음 시작하는 팀도 부담 없이 바로 적용해 볼 수 있는 범위를 기준으로 플랜을 나눴습니다.</div></article></div></section>
          <section class="section compact" id="delivery"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">발행</span><h3>결제 직후 정상작동 설정과 발행 제공이 자연스럽게 이어집니다</h3><ol class="flow-list" id="product-workflow"></ol></article><article class="card strong"><span class="tag theme-chip">함께 보면 좋은 제품</span><h3>비슷한 고민에 이어서 보기 좋은 제품</h3><div class="story-grid" id="product-related-modules"></div></article></div></section>
                    <section class="section compact"><div class="container"><div class="section-head"><div><h2>자주 묻는 질문</h2></div><p>제품 결제와 자동 제공 전에 자주 나오는 질문을 먼저 정리했습니다.</p></div><div class="faq-grid" id="product-faq"></div></div></section>
        </main>
    '''), depth=2, page_key='product', product_key=product['key'], page_path=f'/products/{product["key"]}/index.html')


def product_board_page(product: dict) -> str:
    return doc(f"{product['name']} 게시판 | {brand['name']}", f"{product['name']} AI 자동발행 블로그 허브", product['theme'], dedent(f'''
        <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../../index.html">HOME</a><span class="sep">/</span><a href="../../../products/index.html">제품</a><span class="sep">/</span><a href="../../{escape(product['key'])}/index.html">{escape(product['name'])}</a><span class="sep">/</span><span>게시판</span></div><span class="tag theme-chip">AI 자동발행 글 모음</span><h1>{escape(product['name'])} AI 자동발행 블로그 허브</h1><p class="lead">제품을 보기 전에 먼저 읽어보면 좋은 글, 바로 이어지는 제품 설명·데모 시연·결제 안내, 실제 결과 기반 카드까지 이 페이지에서 한눈에 볼 수 있습니다.</p><div class="actions"><a class="button" href="../../{escape(product['key'])}/index.html#demo">데모 시연</a><a class="button secondary" href="../../{escape(product['key'])}/index.html#intro">제품 설명 보기</a><a class="button ghost" href="../../{escape(product['key'])}/index.html#order">결제 진행</a></div></div><div class="card theme-panel"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">게시판 안내</span><h3 style="font-size:1.7rem;margin:16px 0 10px">제품을 보기 전에 먼저 둘러보기 좋은 글을 보여드립니다</h3><p>{escape(product['summary'])}</p></div></div></section><section class="section compact"><div class="container"><div class="board-grid" id="product-board-grid"></div><div id="product-post-detail"></div></div></section></main>
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
