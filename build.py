import os
import json
from pathlib import Path
from html import escape
from textwrap import dedent
import shutil
import subprocess
import sys
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

def static_header_markup(prefix: str, resolved_key: str, page_path: str) -> str:
    product_active = 'active' if resolved_key in {'products', 'product', 'pricing', 'modules'} or '/products/' in page_path or '/modules/' in page_path else ''
    board_active = 'active' if resolved_key == 'board' or '/board/' in page_path else ''
    company_active = 'active' if resolved_key == 'company' or '/company/' in page_path else ''
    auth_active = 'active' if resolved_key == 'auth' or '/auth/' in page_path else ''
    home_active = 'active' if resolved_key == 'home' else ''
    product_sub_guide = 'active' if '/products/veridion/' in page_path and not any(token in page_path for token in ('/plans/', '/board/', '/demo/', '/faq/', '/delivery/')) else ''
    product_sub_plans = 'active' if '/products/veridion/plans/' in page_path or resolved_key == 'pricing' else ''
    product_sub_board = 'active' if '/products/veridion/board/' in page_path else ''
    quick_links = ''.join([
        f'<a href="{prefix}products/veridion/index.html" class="sub-link {product_sub_guide}">안내</a>',
        f'<a href="{prefix}products/veridion/plans/index.html" class="sub-link {product_sub_plans}">가격</a>',
        f'<a href="{prefix}products/veridion/board/index.html" class="sub-link {product_sub_board}">자료실</a>',
    ])
    nav_links = ''.join([
        f'<a href="{prefix}index.html" class="top-link {home_active}">홈</a>',
        f'<a href="{prefix}products/veridion/index.html" class="top-link {product_active}">제품</a>',
        f'<a href="{prefix}board/index.html" class="top-link {board_active}">자료실</a>',
        f'<a href="{prefix}company/index.html" class="top-link {company_active}">회사소개</a>',
        f'<a href="{prefix}auth/index.html" class="top-link {auth_active}">로그인(회원가입)</a>',
    ])
    return f'<div class="container nav-wrap"><div class="nav-left"><button class="mobile-nav-toggle" type="button" aria-expanded="false" aria-controls="mobile-drawer" data-nav-toggle="1">메뉴</button><a class="brand" href="{prefix}index.html"><span class="brand-mark">V</span><span class="brand-copy"><strong>Veridion</strong><span>온라인 개인사업자용 법률·규제 리스크 방어막</span></span></a></div><nav class="nav-links" aria-label="주요 메뉴">{nav_links}<a class="button ghost admin-link-inline" href="{prefix}admin/index.html" data-admin-entry="1" data-admin-href="{prefix}admin/index.html" title="관리 메뉴를 엽니다">관리</a></nav></div><div class="container subnav" aria-label="제품 바로가기"><span class="subnav-label">제품</span>{quick_links}</div>'


def static_side_nav_markup(prefix: str, resolved_key: str, page_path: str) -> str:
    product_active = 'active' if resolved_key in {'products', 'product', 'pricing', 'modules'} or '/products/' in page_path or '/modules/' in page_path else ''
    board_active = 'active' if resolved_key == 'board' or '/board/' in page_path else ''
    company_active = 'active' if resolved_key == 'company' or '/company/' in page_path else ''
    auth_active = 'active' if resolved_key == 'auth' or '/auth/' in page_path else ''
    home_active = 'active' if resolved_key == 'home' else ''
    product_sub_guide = 'active' if '/products/veridion/' in page_path and not any(token in page_path for token in ('/plans/', '/board/', '/demo/', '/faq/', '/delivery/')) else ''
    product_sub_plans = 'active' if '/products/veridion/plans/' in page_path or resolved_key == 'pricing' else ''
    product_sub_board = 'active' if '/products/veridion/board/' in page_path else ''
    demo_active = 'active' if '/products/veridion/demo/' in page_path else ''
    main_links = ''.join([
        f'<a href="{prefix}index.html" class="side-link {home_active}">홈</a>',
        f'<a href="{prefix}products/veridion/index.html" class="side-link {product_active}">제품</a>',
        f'<a href="{prefix}board/index.html" class="side-link {board_active}">자료실</a>',
        f'<a href="{prefix}company/index.html" class="side-link {company_active}">회사소개</a>',
        f'<a href="{prefix}auth/index.html" class="side-link {auth_active}">로그인(회원가입)</a>',
    ])
    product_links = ''.join([
        f'<a href="{prefix}products/veridion/index.html" class="side-sublink {product_sub_guide}">안내</a>',
        f'<a href="{prefix}products/veridion/plans/index.html" class="side-sublink {product_sub_plans}">가격</a>',
        f'<a href="{prefix}products/veridion/board/index.html" class="side-sublink {product_sub_board}">자료실</a>',
        f'<a href="{prefix}products/veridion/demo/index.html" class="side-sublink {demo_active}">즉시 시연</a>',
    ])
    return ''


def static_footer_markup(prefix: str) -> str:
    info = brand.get('business_info', {})
    email = info.get('contact_email') or brand.get('contact_email', 'ct@nv0.kr')
    operator = info.get('operator_name') or brand.get('name', 'NV0')
    notice = info.get('support_notice') or '정책과 제품 안내는 같은 기준으로 제공합니다.'
    representative = info.get('representative_name', '')
    biz_no = info.get('registration_number', '')
    address = info.get('business_address', '')
    return f'<div class="container footer-grid"><div><div class="brand"><span class="brand-mark">N0</span><span class="brand-copy"><strong>{escape(brand.get("name", "NV0"))}</strong><span>데모, 가격, 전달물을 먼저 보고 바로 판단할 수 있게 정리했습니다.</span></span></div><small style="margin-top:14px">공개 화면은 제품 이해와 구매 판단에 집중하고, 내부 운영 기능은 뒤로 분리했습니다.</small></div><div><strong>빠른 이동</strong><small><a href="{prefix}products/index.html">제품</a><br><a href="{prefix}board/index.html">자료실</a><br><a href="{prefix}company/index.html">회사소개</a><br><a href="{prefix}pricing/index.html">가격</a><br><a href="{prefix}faq/index.html">FAQ</a></small></div><div><strong>안내/정책</strong><small>상호: {escape(operator)}<br>{f"대표자: {escape(representative)}<br>" if representative else ""}{f"사업자등록번호: {escape(biz_no)}<br>" if biz_no else ""}<a href="mailto:{escape(email)}">{escape(email)}</a><br>{f"{escape(address)}<br>" if address else ""}{escape(notice)}<br>시행일 2026-04-15 · 최종 개정일 2026-04-15<br><a href="{prefix}portal/index.html">고객 포털</a><br><a href="{prefix}auth/index.html">로그인(회원가입)</a><br><a href="{prefix}legal/privacy/index.html">개인정보처리방침</a><br><a href="{prefix}legal/terms/index.html">이용약관</a><br><a href="{prefix}legal/refund/index.html">환불 정책</a><br><a href="{prefix}legal/cookies/index.html">쿠키 및 저장 안내</a></small></div></div>'


def doc(title: str, description: str, body_class: str, body: str, depth: int = 0, page_key: str | None = None, product_key: str | None = None, page_path: str = '/'):
    prefix = rel_prefix(depth)
    resolved_key = page_key or body_class
    attrs = [f'class="{body_class}"', f'data-page="{resolved_key}"']
    if product_key:
        attrs.append(f'data-product="{product_key}"')
    canonical = page_url(page_path)
    og_type = 'product' if resolved_key == 'product' else 'website'
    schema_json = build_page_schema(title, description, page_path, resolved_key, product_key)
    header_markup = static_header_markup(prefix, resolved_key, page_path)
    side_nav_markup = static_side_nav_markup(prefix, resolved_key, page_path)
    footer_markup = static_footer_markup(prefix)
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
<a class="skip-link" href="#main-content">본문 바로가기</a>
<a class="admin-fab" href="{prefix}admin/index.html" data-admin-entry="1" data-admin-href="{prefix}admin/index.html" aria-label="관리 메뉴 열기">관리</a>
<div id="admin-access-modal-root"></div>
<header class="site-header" id="site-header">{header_markup}</header>
{body}
<footer class="footer" id="site-footer">{footer_markup}</footer>
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
    representative = next((item for item in products if item['key'] == 'veridion'), products[0])
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
                  <a class="button" href="./products/veridion/demo/index.html">무료 데모 바로 실행</a>
                  <a class="button secondary" href="./products/veridion/plans/index.html">가격과 발행 범위 보기</a>
                  <a class="button ghost" href="./board/index.html">자료실 보기</a>
                </div>
                <div class="live-strip" id="live-stats"></div>
              </div>
              <div class="showcase-grid">
                <article class="card accent">
                  <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">무료 데모에서 먼저 보이는 것</span>
                  <h3 style="font-size:1.75rem;margin:16px 0 10px">영역별 건수, 위기 점수, 예상 과태료를 먼저 공개합니다</h3>
                  <p>사이트 주소만 입력하면 공개 화면을 탐색해 어떤 영역이 비어 있는지, 어디가 가장 위험한지, 결제 전에 어느 정도까지 확인할 수 있는지 먼저 보여줍니다.</p>
                  <div class="inline-list"><span>영역별 건수</span><span>위기 점수</span><span>예상 과태료</span></div>
                </article>
                <article class="card strong">
                  <span class="tag">결제 후 열리는 항목</span>
                  <h3>전체 이슈, 맞춤 지침, 문구안, 지난 발행 이력까지 같은 계정으로 이어집니다</h3>
                  <p class="lead" style="font-size:1rem">결제 후에는 전체 리스크 목록, 페이지별 수정 우선순위, 실제 적용할 문구안, 추가 결제형 정밀 리포트, 로그인 이력 조회가 한 흐름으로 연결됩니다.</p>
                  <div class="badge-row"><span class="badge">전체 리포트</span><span class="badge">맞춤 문구안</span><span class="badge">정밀 발행</span><span class="badge">이력 조회</span></div>
                </article>
              </div>
            </div>
          </section>
          <section class="section compact"><div class="container"><div class="section-head"><div><h2>{escape(company_profile.get('headline', 'Veridion 운영 방식'))}</h2></div><p>{escape(company_profile.get('summary', ''))}</p></div><div class="timeline">{timeline_markup()}</div></div></section>
          <section class="section"><div class="container"><div class="section-head"><div><h2>지금 공개 판매와 검증에 집중하는 핵심 제품</h2></div><p>공개 홈에서는 Veridion 한 제품만 전면에 보여 주고, 다른 제품은 분리 모듈 허브에서 관리합니다. 지금은 법률·규제 리스크 점검, 발행, 이력 관리 흐름을 가장 먼저 완성하는 단계입니다.</p></div><div class="product-grid" id="product-grid"></div></div></section>
          <section class="section compact"><div class="container"><div class="section-head"><div><h2>추후 결합 예정인 분리 모듈</h2></div><p>ClearPort, GrantOps, DraftForge는 분리 모듈로 유지합니다. 공개 판매 중심은 Veridion에 두고, 다른 제품은 동일한 품질 수준으로 완성한 뒤 단계적으로 결합합니다.</p></div><div class="story-grid" id="module-matrix"></div><div class="small-actions" style="margin-top:18px"><a href="./modules/index.html">분리 모듈 허브 보기</a></div></div></section>
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
    return doc(f"제품 | {brand['name']}", 'Veridion 공개 제품 허브', 'products', dedent(f'''
      <main>
        <section class="section">
          <div class="container page-hero">
            <div class="card strong">
              <div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>제품</span></div>
              <span class="kicker">Products</span>
              <h1>현재 공개 판매와 검증은 Veridion 한 제품에 집중합니다</h1>
              <p class="lead">상단 메뉴의 제품은 Veridion을 뜻합니다. 무료 데모로 먼저 리스크를 확인하고, 가격과 발행 범위를 본 뒤 결제와 이력 조회까지 같은 흐름으로 이어지게 구성했습니다.</p>
              <div class="actions"><a class="button" href="{prefix}products/veridion/demo/index.html">무료 데모</a><a class="button secondary" href="{prefix}products/veridion/plans/index.html">가격 보기</a><a class="button ghost" href="{prefix}products/veridion/board/index.html">자료실 보기</a></div>
            </div>
            <div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">분리 모듈 원칙</span><h3 style="font-size:1.72rem;margin:16px 0 10px">다른 제품은 숨기지 않고, 다만 공개 판매 흐름에서만 분리합니다</h3><p>ClearPort, GrantOps, DraftForge는 분리 모듈 허브에서 따로 관리합니다. 기능은 유지하되 공개 주력 제품 흐름을 흐리지 않도록 구조를 분리했습니다.</p></div>
          </div>
        </section>
        <section class="section compact"><div class="container"><div class="product-grid" id="product-grid"></div></div></section>
        <section class="section compact"><div class="container"><div class="section-head"><div><h2>분리 모듈 허브</h2></div><p>추후 결합 예정 모듈은 별도 허브에서 관리합니다.</p></div><div class="story-grid" id="module-matrix"></div><div class="small-actions" style="margin-top:18px"><a href="{prefix}modules/index.html">분리 모듈 전체 보기</a></div></div></section>
      </main>
    '''), depth=1, page_key='products', page_path='/products/index.html')

def board_page() -> str:
    prefix = rel_prefix(1)
    return doc(f"자료실 | {brand['name']}", 'Veridion 자료실', 'board', dedent(f'''
        <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>자료실</span></div><span class="kicker">자료실</span><h1>Veridion 자료와 글을 한곳에서 확인합니다</h1><p class="lead">자료실은 구매 판단에 필요한 글과 운영 자료를 한곳에 모아둔 공개 허브입니다. 글을 읽다가 바로 제품 설명, 즉시 데모, 결제로 이어질 수 있게 구성했습니다.</p><div class="actions"><a class="button secondary" href="{prefix}products/veridion/index.html">제품 안내</a><a class="button" href="{prefix}products/veridion/demo/index.html">무료 데모</a><a class="button ghost" href="{prefix}products/veridion/plans/index.html">가격 보기</a></div></div><div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">운영 원칙</span><h3 style="font-size:1.72rem;margin:16px 0 10px">자료실은 Veridion 중심으로 운영하고, 다른 제품 자료도 같은 구조로 확장합니다</h3><p>공개 허브에서는 Veridion 관련 글과 자료를 먼저 보여 주고, 관리자에서는 제품별 CTA 홍보 글과 자료 업로드를 함께 운영할 수 있도록 구성합니다.</p></div></div></section><section class="section compact"><div class="container"><div class="board-grid" id="public-board-grid"></div><div id="public-post-detail"></div><div class="small-actions" style="margin-top:18px"><a href="{prefix}modules/index.html">분리 모듈 허브 보기</a></div></div></section></main>
    '''), depth=1, page_key='board', page_path='/board/index.html')

def modules_page() -> str:
    prefix = rel_prefix(1)
    return doc(f"분리 모듈 허브 | {brand['name']}", 'Veridion 외 분리 모듈 허브', 'modules', dedent(f'''
        <main>
          <section class="section">
            <div class="container page-hero">
              <div class="card strong">
                <div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>분리 모듈</span></div>
                <span class="kicker">Modules</span>
                <h1>추후 결합 예정인 분리 모듈 허브</h1>
                <p class="lead">ClearPort, GrantOps, DraftForge는 기능을 유지한 채 분리 모듈로 보관합니다. 공개 판매와 검증의 중심은 Veridion에 두고, 다른 모듈은 같은 품질 수준으로 완성한 뒤 결합하는 전략입니다.</p>
                <div class="actions"><a class="button" href="{prefix}products/veridion/index.html">Veridion으로 돌아가기</a><a class="button secondary" href="{prefix}company/index.html">회사소개</a></div>
              </div>
              <div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">보관 원칙</span><h3 style="font-size:1.72rem;margin:16px 0 10px">공개 홈에서는 한 제품만, 구조 안에서는 모든 모듈을 유지합니다</h3><p>모듈을 지우지 않고 분리하는 이유는 이후 결합 가능성을 남기기 위해서입니다. 공개 전면 노출만 줄이고, 제품 자체의 기능과 문서는 유지합니다.</p></div>
            </div>
          </section>
          <section class="section compact"><div class="container"><div class="story-grid" id="module-matrix"></div></div></section>
        </main>
    '''), depth=1, page_key='modules', page_path='/modules/index.html')

def auth_page() -> str:
    return doc(f"로그인 · 회원가입 | {brand['name']}", 'Veridion 로그인과 회원가입 페이지', 'auth', dedent(f'''
        <main>
          <section class="hero">
            <div class="container page-hero">
              <div class="card strong">
                <span class="kicker">Portal Access</span>
                <h1>로그인과 회원가입을 한 화면에서 처리합니다</h1>
                <p class="lead">결제 후 발행된 리포트, 조회 코드, 지난 발행 이력을 같은 계정 기준으로 묶어 확인할 수 있게 구성했습니다.</p>
                <div class="notice"><strong>회원가입 안내</strong><br>최초 구매 시 자동 계정이 생성될 수 있습니다. 별도 계정이 필요하면 아래 회원가입으로 바로 만들 수 있습니다.</div>
              </div>
              <div class="card accent">
                <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">계정 활용</span>
                <ul class="inverse-list">
                  <li>지난 발행 이력 일괄 조회</li>
                  <li>조회 코드와 결제 건 묶음 관리</li>
                  <li>정밀 리포트 추가 발행 준비</li>
                </ul>
              </div>
            </div>
          </section>
          <section class="section compact">
            <div class="container auth-grid">
              <article class="card auth-panel">
                <span class="tag">로그인</span>
                <h3>기존 계정으로 접속</h3>
                <form class="stack-form" id="portal-login-form">
                  <label>이메일<input type="email" name="email" placeholder="you@example.com" required></label>
                  <label>비밀번호<input type="password" name="password" placeholder="비밀번호 입력" required></label>
                  <button class="button" type="submit">로그인</button>
                </form>
              </article>
              <article class="card auth-panel">
                <span class="tag">회원가입</span>
                <h3>새 계정 만들기</h3>
                <form class="stack-form" id="portal-signup-form">
                  <label>회사명<input type="text" name="company" placeholder="상호 또는 회사명"></label>
                  <label>이름<input type="text" name="name" placeholder="담당자명" required></label>
                  <label>이메일<input type="email" name="email" placeholder="you@example.com" required></label>
                  <label>비밀번호<input type="password" name="password" placeholder="8자 이상 권장" required></label>
                  <button class="button secondary" type="submit">회원가입</button>
                </form>
              </article>
            </div>
            <div class="container auth-status-stack">
              <div id="auth-status"></div>
              <div id="auth-me"></div>
              <div class="card">
                <div class="section-head"><div><h2>지난 발행 이력</h2></div><div class="small-actions"><button class="button ghost" id="portal-logout-button" type="button">로그아웃</button></div></div>
                <div id="auth-history"><div class="empty-box">로그인 후 지난 발행 이력이 여기에 표시됩니다.</div></div>
              </div>
            </div>
          </section>
        </main>
    '''), depth=1, page_key='auth', page_path='/auth/index.html')



def demo_page() -> str:
    prefix = rel_prefix(1)
    return doc(f"즉시 데모 | {brand['name']}", '사이트 주소를 넣으면 Veridion 위험 요약을 바로 보는 데모', 'demo', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>즉시 데모</span></div><span class="kicker">Instant demo</span><h1>사이트 주소를 넣으면 즉시 위험 요약을 보여드립니다</h1><p class="lead">저장형 폼이 아니라 실제 사이트 기준 즉시 진단 화면입니다. 위기 점수, 예상 과태료, 문제 영역별 건수, 상위 위험 항목을 먼저 확인한 뒤 결제 여부를 판단하실 수 있습니다.</p><form id="demo-form" class="stack-form"><input type="hidden" name="product" value="veridion"><div class="form-grid"><div class="span-2"><label>사이트 주소</label><input name="website" placeholder="https://example.com" inputmode="url" autocomplete="url" required></div><div><label>업종</label><select name="industry"><option value="commerce">이커머스</option><option value="beauty">뷰티·웰니스</option><option value="healthcare">의료·건강</option><option value="education">교육·서비스</option><option value="saas">B2B SaaS</option></select></div><div><label>주요 운영 국가</label><input name="market" placeholder="예: 대한민국"></div><div><label>중점 확인 사항</label><select name="focus" data-demo-field="focus"><option value="전체 리스크 빠르게 보기">전체 리스크 빠르게 보기</option><option value="개인정보·회원가입 동선">개인정보·회원가입 동선</option><option value="결제·환불·청약철회 고지">결제·환불·청약철회 고지</option><option value="광고·표시 문구">광고·표시 문구</option><option value="약관·정책 문서 일치">약관·정책 문서 일치</option><option value="민감 업종·표현 위험">민감 업종·표현 위험</option></select></div></div><div class="actions"><button class="button" type="submit">즉시 분석하기</button><a class="button ghost" href="{prefix}checkout/index.html?product=veridion&plan=Starter">바로 결제</a></div></form><div class="result-box" id="demo-result" role="status" aria-live="polite"></div></article><article class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">무료 데모에서 먼저 보는 항목</span><h3 style="font-size:1.72rem;margin:16px 0 10px">위기 점수, 예상 과태료, 문제 영역 수를 바로 확인합니다</h3><ul class="clean inverse-list"><li>실제 읽은 페이지 기준 요약</li><li>위기 점수와 상위 위험 신호</li><li>예상 노출/과태료 범위</li><li>문제 영역별 건수</li></ul></article></div></section></main>
    '''), depth=1, page_key='demo', page_path='/demo/index.html')



def checkout_page() -> str:
    prefix = rel_prefix(1)
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])} · {escape(item["headline"])}' '</option>' for item in products)
    return doc(f"결제 | {brand['name']}", '제품과 플랜만 고르고 바로 외부 결제로 넘어가는 페이지', 'checkout', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>결제</span></div><span class="kicker">Checkout</span><h1>제품과 플랜만 고르고 바로 외부 결제로 넘어갑니다</h1><p class="lead">결제 전에는 꼭 필요한 선택만 남겼습니다. 회사명, 담당자명, 이메일, 사이트 주소 같은 진행 정보는 결제 완료 후 한 번에 입력하도록 분리했습니다.</p><form id="checkout-form" class="stack-form"><input type="hidden" name="billing" value="one-time"><input type="hidden" name="paymentMethod" value="toss"><div class="form-grid"><div><label>제품</label><select name="product" data-prefill="product" required>{options}</select></div><div><label>플랜</label><select name="plan" data-prefill="plan" required><option value="Lite">Lite</option><option value="Starter">Starter</option><option value="Growth">Growth</option><option value="Scale">Scale</option></select></div></div><div class="consent-panel"><div class="consent-copy"><strong>개인정보 수집·이용 안내</strong><p>결제 준비와 결제 완료 후 진행 정보 수집, 결과 제공, 고객 포털 안내를 위해 필요한 최소 정보만 사용합니다. 자세한 내용은 <a href="{prefix}legal/privacy/index.html">개인정보처리방침</a>에서 확인하실 수 있습니다.</p></div><label class="consent-check"><input type="checkbox" name="privacyConsent" value="yes" required data-consent-required="1"> <span>개인정보 수집·이용에 동의합니다.</span></label><small data-consent-message>동의 후에만 결제를 진행할 수 있습니다.</small></div><div class="notice" id="checkout-plan-summary" data-plan-summary="checkout" aria-live="polite">선택한 제품과 플랜 요약이 여기에 표시됩니다.</div><div class="actions"><button class="button" type="submit">외부 결제로 바로 이동</button></div></form><div class="result-box" id="checkout-result" role="status" aria-live="polite"></div></article><article class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">결제 후 진행 순서</span><h3 style="font-size:1.72rem;margin:16px 0 10px">결제 후 필요한 정보만 입력하고 바로 결과 흐름으로 이어집니다</h3><ul class="clean inverse-list"><li>제품과 플랜 선택</li><li>외부 결제 진행</li><li>회사명·담당자명·이메일·사이트 주소 입력</li><li>결과 준비 및 포털 연결</li></ul></article></div></section></main>
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
    return doc(f"관리 허브 | {brand['name']}", '운영 관리 허브', 'admin', dedent(f'''
        <main id="admin-console">
          <section class="section">
            <div class="container page-hero">
              <div class="card strong">
                <div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>관리 허브</span></div>
                <span class="kicker">Admin hub</span>
                <h1>관리 기능은 관리 허브로만 모으고, 공개 화면에서는 감췄습니다</h1>
                <p class="lead">비밀키가 있어야 운영 화면을 열 수 있습니다. 주문·결제·전달·포털 연결은 자동으로 이어지며, 이 화면에서는 자동화 상태 확인과 운영 안전성 점검만 합니다.</p>
                <div class="result-box admin-gate" id="admin-gate-result">관리 비밀키를 입력하면 운영 메뉴가 열립니다.</div>
                <div class="auth-inline admin-auth-inline">
                  <input id="admin-token-input" placeholder="관리 비밀키" autocomplete="off" spellcheck="false">
                  <button class="button secondary" type="button" id="admin-token-save">관리 열기</button>
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
                  <a href="#admin-automation">자료실 설정</a>
                  <a href="#admin-orders-section">주문/결제</a>
                  <a href="#admin-requests-section">요청</a>
                  <a href="#admin-publications-section">자료실 관리</a>
                </nav>
                <div class="result-box" id="admin-action-result">수동 보정 버튼은 기본 비활성화 상태입니다. 주문·결제·전달·콘텐츠 연결은 자동 흐름으로만 동작합니다.</div>
              </aside>
              <div class="admin-main-stack">
                <section id="admin-overview" class="admin-section"><div class="admin-grid" id="admin-summary"></div></section>
                <section id="admin-automation" class="admin-section"><div class="record-grid" id="admin-automation-grid"></div><div class="card strong"><h3>자료실 CTA 자동 발행 설정</h3><form id="admin-board-settings-form" class="stack-form"><div class="form-grid"><div><label>기본 CTA 문구</label><input name="ctaLabel" placeholder="예: 제품 설명 보기"></div><div><label>기본 CTA 링크</label><input name="ctaHref" placeholder="예: /products/veridion/index.html#intro"></div></div><label class="consent-check"><input type="checkbox" name="autoPublishAllProducts" value="1"> <span>전체 제품에 동일 CTA 자동 발행 적용</span></label><div class="actions"><button class="button" type="submit">설정 저장</button><button class="button ghost" type="button" id="admin-publish-all">전체 제품 글 즉시 발행</button></div></form></div></section>
                <section id="admin-orders-section" class="admin-section"><div class="admin-stack" id="admin-orders"></div></section>
                <section id="admin-requests-section" class="admin-section"><div class="record-grid" id="admin-requests"></div></section>
                <section id="admin-publications-section" class="admin-section"><div class="card strong"><h3>자료 직접 등록</h3><form id="admin-publication-form" class="stack-form"><div class="form-grid"><div><label>제품</label><select name="product"><option value="veridion">Veridion</option><option value="clearport">ClearPort</option><option value="grantops">GrantOps</option><option value="draftforge">DraftForge</option></select></div><div><label>제목</label><input name="title" placeholder="자료 제목"></div><div><label>요약</label><input name="summary" placeholder="짧은 소개"></div><div><label>CTA 문구</label><input name="ctaLabel" placeholder="예: 제품 설명 보기"></div><div><label>CTA 링크</label><input name="ctaHref" placeholder="예: /products/veridion/index.html#intro"></div><div><label>자료 URL(선택)</label><input name="assetUrl" placeholder="업로드 후 자동 입력 가능"></div><div class="span-2"><label>본문</label><textarea name="body" rows="6" placeholder="직접 작성할 글 또는 자료 설명"></textarea></div></div><div class="actions"><button class="button" type="submit">글 등록</button></div></form></div><div class="card strong"><h3>파일 업로드</h3><form id="admin-asset-form" class="stack-form"><div class="form-grid"><div><label>제품</label><select name="product"><option value="veridion">Veridion</option><option value="clearport">ClearPort</option><option value="grantops">GrantOps</option><option value="draftforge">DraftForge</option></select></div><div><label>자료 제목</label><input name="title" placeholder="예: 체크리스트 PDF"></div><div class="span-2"><label>파일 선택</label><input type="file" name="file"></div></div><div class="actions"><button class="button" type="submit">파일 올리기</button></div></form></div><div class="record-grid" id="admin-publications"></div><div class="card strong"><div class="mock-progress" id="admin-feed"></div></div></section>
              </div>
            </div>
          </section>
        </main>
    '''), depth=1, page_key='admin', page_path='/admin/index.html')


def toss_success_page() -> str:
    prefix = rel_prefix(3)
    return doc(f"결제 승인 | {brand['name']}", 'Toss 결제 승인 처리', 'payment-success', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>결제 승인</span></div><span class="kicker">결제 완료</span><h1>결제 승인 후 필요한 진행 정보만 이어서 입력합니다</h1><p class="lead">결제 승인이 끝나면 회사명, 담당자명, 이메일, 사이트 주소 같은 진행 정보를 한 번에 입력하고 바로 결과 흐름으로 이어집니다.</p><div class="result-box" id="payment-success-result" style="display:block">결제 정보를 확인하고 있습니다.</div><div class="actions"><a class="button secondary" href="{prefix}portal/index.html">전달 상태 확인하기</a><a class="button ghost" href="{prefix}products/index.html">다른 제품 둘러보기</a></div></article></div></section></main>
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
                <p class="lead demo-intro-copy">소개 문장보다, 사이트 주소나 핵심 조건을 넣었을 때 어떤 결과가 나오는지를 먼저 확인하실 수 있습니다. Veridion은 URL 즉시 진단형으로 바로 결과를 보여줍니다.</p>
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
      <h3>플랜만 고르고 바로 외부 결제로 넘어갑니다</h3>
      <form id="product-checkout-form" class="stack-form">
        <input type="hidden" name="product" value="{escape(product['key'])}">
        <input type="hidden" name="billing" value="one-time">
        <input type="hidden" name="paymentMethod" value="toss">
        <div class="form-grid">
          <div><label>플랜</label><select name="plan" data-prefill="plan" required><option value="Lite">Lite</option><option value="Starter">Starter</option><option value="Growth">Growth</option><option value="Scale">Scale</option></select></div>
        </div>
        <div class="consent-panel"><div class="consent-copy"><strong>개인정보 수집·이용 안내</strong><p>결제 준비와 결제 완료 후 진행 정보 수집, 결과 제공을 위해 필요한 최소 정보만 사용합니다. 자세한 내용은 <a href="../../legal/privacy/index.html">개인정보처리방침</a>에서 확인하실 수 있습니다.</p></div><label class="consent-check"><input type="checkbox" name="privacyConsent" value="yes" required data-consent-required="1"> <span>개인정보 수집·이용에 동의합니다.</span></label><small data-consent-message>동의 후에만 결제를 진행할 수 있습니다.</small></div>
        <div class="notice" id="product-checkout-plan-summary" data-plan-summary="product" aria-live="polite">선택한 제품과 플랜 요약이 여기에 표시됩니다.</div>
        <div class="actions"><button class="button" type="submit">외부 결제로 바로 이동</button><a class="button secondary" href="#delivery">전달 범위 먼저 보기</a></div>
        <p class="micro-copy">결제 후 회사명, 담당자명, 이메일, 사이트 주소 같은 진행 정보만 한 번에 입력하시면 됩니다.</p>
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
            <div class="container"><div class="section-head"><div><h2>{escape(product['name'])} 자료실</h2></div><p>이 제품이 필요한 상황을 더 읽어보고 싶다면 아래 글과 자료를 참고해 주세요. 가장 빠른 판단은 위 즉시 데모에서 하실 수 있습니다.</p></div><div class="board-grid" id="product-board-grid"></div><div id="product-post-detail"></div></div>
          </section>

          <section class="section compact" id="faq"><div class="container"><div class="section-head"><div><h2>자주 묻는 질문</h2></div><p>결제 전에 자주 나오는 질문을 한곳에 모아두었습니다.</p></div><div class="faq-grid" id="product-faq"></div></div></section>
        </main>
    '''), depth=2, page_key='product', product_key=product['key'], page_path=f'/products/{product["key"]}/index.html')

def product_board_page(product: dict) -> str:
    return doc(f"{product['name']} 자료실 | {brand['name']}", f"{product['name']} 자료실", product['theme'], dedent(f'''
        <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../../index.html">HOME</a><span class="sep">/</span><a href="../../../products/index.html">제품</a><span class="sep">/</span><a href="../../{escape(product['key'])}/index.html">{escape(product['name'])}</a><span class="sep">/</span><span>자료실</span></div><span class="tag theme-chip">자료실</span><h1>{escape(product['name'])} 자료실</h1><p class="lead">이 제품과 관련된 글과 자료를 먼저 확인하고, 바로 제품 설명·실제 데모·결제로 이어질 수 있게 구성했습니다.</p><div class="actions"><a class="button" href="../../{escape(product['key'])}/index.html#demo">데모 시연</a><a class="button secondary" href="../../{escape(product['key'])}/index.html#intro">제품 설명 보기</a><a class="button ghost" href="../../{escape(product['key'])}/index.html#order">결제 진행</a></div></div><div class="card theme-panel"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">자료실 안내</span><h3 style="font-size:1.7rem;margin:16px 0 10px">구매 전 참고할 글과 자료를 함께 모아두었습니다</h3><p>{escape(product['summary'])}</p></div></div></section><section class="section compact"><div class="container"><div class="board-grid" id="product-board-grid"></div><div id="product-post-detail"></div></div></section></main>
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
        DIST / 'modules' / 'index.html': modules_page(),
        DIST / 'auth' / 'index.html': auth_page(),
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
    subprocess.run([sys.executable, str(ROOT / "scripts" / "finalize_dist_patch.py")], check=True)
    board_only_mode = os.getenv('NV0_BOARD_ONLY_MODE', '0').lower() in {'1', 'true', 'yes', 'on'}
    if board_only_mode:
        apply_board_only_overrides(DIST, DATA, SRC)
    print('Build completed:', DIST, '(board-only)' if board_only_mode else '(full)')


if __name__ == '__main__':
    main()
