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
                  <a class="button" href="./products/index.html">제품별 실제 데모 보기</a>
                  <a class="button secondary" href="./products/{escape(representative['key'])}/index.html#demo">대표 데모 바로 실행</a>
                  <a class="button ghost" href="./company/index.html">운영 방식 보기</a>
                </div>
                <div class="live-strip" id="live-stats"></div>
              </div>
              <div class="showcase-grid">
                <article class="card accent">
                  <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">무엇이 다른가</span>
                  <h3 style="font-size:1.75rem;margin:16px 0 10px">설명보다 시연이 먼저인 제품 구조</h3>
                  <p>각 제품 페이지에서 실제 입력값을 넣고 결과를 바로 볼 수 있습니다. 제품 정의, 데모, 결과물, 결제 후 전달 범위가 한 흐름으로 이어집니다.</p>
                  <div class="inline-list"><span>실제 입력</span><span>즉시 결과</span><span>결제 후 전달물</span></div>
                </article>
                <article class="card strong">
                  <span class="tag">어떻게 보나</span>
                  <h3>지금 막힌 업무를 기준으로 바로 고르세요</h3>
                  <p class="lead" style="font-size:1rem">준법 점검, 서류 정리, 지원사업 제출, 콘텐츠 최종화. 무엇을 사야 하는지보다 어떤 일이 막혔는지부터 보고 해당 데모로 바로 들어갈 수 있게 구성했습니다.</p>
                  <div class="badge-row"><span class="badge">문제 선택</span><span class="badge">데모 실행</span><span class="badge">결과 검토</span><span class="badge">결제/전달</span></div>
                </article>
              </div>
            </div>
          </section>
          <section class="section compact"><div class="container"><div class="section-head"><div><h2>{escape(company_profile.get('headline', 'NV0 소개'))}</h2></div><p>{escape(company_profile.get('summary', ''))}</p></div><div class="timeline">{timeline_markup()}</div></div></section>
          <section class="section"><div class="container"><div class="section-head"><div><h2>지금 바로 돌려볼 수 있는 4개 업무 데모</h2></div><p>각 카드는 제품 소개만 하지 않습니다. 어떤 문제를 해결하는지, 데모에서 무엇을 보여주는지, 결제 후 무엇을 받는지를 한 번에 볼 수 있게 다시 구성했습니다.</p></div><div class="product-grid" id="product-grid"></div></div></section>
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
              <h1>막힌 업무를 기준으로 바로 데모를 실행해 보세요</h1>
              <p class="lead">각 제품 상세에는 실제 입력과 결과를 보여주는 데모가 들어 있습니다. 소개 텍스트보다 먼저, 이 제품이 정말 내가 필요한 결과를 내는지 직접 확인할 수 있습니다.</p>
            </div>
            <div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">공통 흐름</span><h3 style="font-size:1.72rem;margin:16px 0 10px">문제 선택 → 데모 실행 → 결과 검토 → 결제 → 전달</h3><p>읽기용 소개 페이지가 아니라 실제 업무 흐름에 맞춰 판단할 수 있도록 다시 설계했습니다.</p></div>
          </div>
        </section>
        <section class="section compact"><div class="container"><div class="product-grid" id="product-grid"></div></div></section>
      </main>
    '''), depth=1, page_key='products', page_path='/products/index.html')

def board_page() -> str:
    prefix = rel_prefix(1)
    return doc(f"콘텐츠 허브 | {brand['name']}", '전체 제품 콘텐츠 허브', 'board', dedent(f"""
        <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>콘텐츠 허브</span></div><span class="kicker">콘텐츠 허브</span><h1>제품과 관련된 글과 사례를 한곳에서 볼 수 있습니다</h1><p class="lead">각 제품에 연결된 글을 먼저 읽고, 필요하면 바로 제품 설명·실제 데모·결제로 이어질 수 있게 구성했습니다.</p><div class="actions"><a class="button secondary" href="{prefix}products/index.html">제품 목록</a><a class="button" href="{prefix}products/veridion/index.html#board">대표 제품 글 먼저 보기</a></div></div><div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">읽고 판단하기</span><h3 style="font-size:1.72rem;margin:16px 0 10px">필요한 글을 먼저 읽고, 맞으면 바로 데모로 넘어가면 됩니다</h3><p>게시판은 홍보 문장 모음이 아니라 제품을 이해하는 데 도움이 되는 글 허브로 작동합니다. 읽은 뒤 바로 제품 설명과 데모, 결제 단계로 이어질 수 있습니다.</p></div></div></section><section class="section compact"><div class="container"><div class="board-grid" id="public-board-grid"></div><div id="public-post-detail"></div></div></section></main>
    """), depth=1, page_key='board', page_path='/board/index.html')


def demo_page() -> str:
    prefix = rel_prefix(1)
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])} · {escape(item["headline"])}' '</option>' for item in products)
    return doc(f"빠른 체험 | {brand['name']}", '제품 빠른 체험', 'demo', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>데모</span></div><span class="kicker">Quick demo</span><h1>관심 있는 제품을 골라 바로 샘플 결과를 확인해 보세요</h1><p class="lead">샘플 결과를 바로 확인하면서 데모 신청 정보도 함께 저장됩니다. 마음에 들면 같은 흐름으로 제품 상세에서 데모 시연과 결제까지 이어가실 수 있습니다.</p><form id="demo-form"><div class="form-grid"><div><label>제품</label><select name="product" data-prefill="product" required>{options}</select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>연락처</label><input name="phone" placeholder="예: 010-1234-5678" inputmode="tel" autocomplete="tel"></div><div><label>팀 규모</label><input name="team" placeholder="예: 3인 운영팀" autocomplete="organization-title"></div><div><label>목표</label><input name="goal" placeholder="예: 첫 화면에서 바로 이해되게" required></div><div><label>핵심 키워드</label><input name="keywords" placeholder="예: 신뢰, CTA, 전환"></div><div><label>참고 링크</label><input name="link" placeholder="예: https://example.com" inputmode="url" autocomplete="url"></div><div><label>긴급도</label><select name="urgency"><option value="">선택</option><option>일반</option><option>이번 주 안</option><option>오늘 필요</option></select></div></div><div class="actions"><button class="button" type="submit">무료 샘플과 데모 시연 자료 받기</button></div></form><div class="result-box" id="demo-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">바로가기</span><h3>마음에 드는 제품으로 바로 이어서 검토하세요</h3><div class="story-grid" id="module-matrix"></div></article></div></section></main>
    '''), depth=1, page_key='demo', page_path='/demo/index.html')


def checkout_page() -> str:
    prefix = rel_prefix(1)
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])} · {escape(item["plans"][0]["price"])}부터' '</option>' for item in products)
    return doc(f"결제 | {brand['name']}", '제품 결제 및 결제 진입', 'checkout', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>결제</span></div><span class="kicker">Checkout</span><h1>선택한 제품을 바로 결제하고 결과 전달 상태까지 확인할 수 있습니다</h1><p class="lead">플랜을 고르고 1회 결제 버튼을 누르면 외부 결제창으로 이동합니다. 결제 완료 뒤에는 전달 자료와 공개 콘텐츠를 바로 확인할 수 있습니다.</p><form id="checkout-form"><div class="form-grid"><div><label>제품</label><select name="product" data-prefill="product" required>{options}</select></div><div><label>플랜</label><select name="plan" data-prefill="plan" required><option value="Starter">Starter</option><option value="Growth">Growth</option><option value="Scale">Scale</option></select></div><div><label>결제 유형</label><select name="billing"><option value="one-time">1회 결제형</option></select></div><div><label>결제 방식</label><select name="paymentMethod" required><option value="toss">Toss 결제</option></select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>연락처</label><input name="phone" placeholder="예: 010-1234-5678" inputmode="tel" autocomplete="tel"></div><div><label>참고 링크</label><input name="link" placeholder="예: https://example.com" inputmode="url" autocomplete="url"></div><div><label>긴급도</label><select name="urgency"><option value="">선택</option><option>일반</option><option>이번 주 안</option><option>오늘 필요</option></select></div><div><label>희망 회신 시간</label><input name="reply_time" placeholder="예: 평일 오후 2시 이후"></div><div><label>추가 요청</label><input name="note" placeholder="예: 원하는 톤, 꼭 포함할 내용" autocomplete="off"></div></div><div class="actions"><button class="button" type="submit">결제 계속하기</button></div><p class="micro-copy">결제 전 더 확인할 내용이 있으면 <a href="{prefix}legal/terms/index.html">이용약관</a>, <a href="{prefix}legal/refund/index.html">환불정책</a>, <a href="{prefix}contact/index.html">추가 확인</a>을 먼저 확인해 주세요.</p></form><div class="result-box" id="checkout-result" role="status" aria-live="polite"></div></article><article class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">결제 안내</span><h3 style="font-size:1.72rem;margin:16px 0 10px">결제가 끝나면 확인과 전달 흐름이 바로 이어집니다</h3><ul class="clean inverse-list"><li>플랜 확인</li><li>결제 진행</li><li>결제 완료 확인</li><li>결과물 준비</li><li>전달 상태 확인</li></ul></article></div></section></main>
    '''), depth=1, page_key='checkout', page_path='/checkout/index.html')


def contact_page() -> str:
    prefix = rel_prefix(1)
    options = ''.join(f'<option value="{escape(item["key"])}">{escape(item["name"])}' '</option>' for item in products)
    return doc(f"추가 확인 | {brand['name']}", '추가 확인', 'contact', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>추가 확인</span></div><span class="kicker">Contact</span><h1>페이지에서 바로 판단하기 어려운 조건만 따로 남겨 주세요</h1><p class="lead">가격, 결과물, 적용 범위처럼 화면만 보고 결정하기 어려운 내용만 이 폼으로 보내실 수 있습니다. 일반적인 비교와 데모는 제품 페이지에서 바로 진행하시면 됩니다.</p><form id="contact-form"><div class="form-grid"><div><label>관심 제품</label><select name="product" data-prefill="product" required><option value="">선택</option>{options}</select></div><div><label>회사명</label><input name="company" placeholder="회사명" autocomplete="organization" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" autocomplete="name" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>연락처</label><input name="phone" placeholder="예: 010-1234-5678" inputmode="tel" autocomplete="tel"></div><div><label>참고 링크</label><input name="link" placeholder="예: https://example.com" inputmode="url" autocomplete="url"></div><div><label>긴급도</label><select name="urgency"><option value="">선택</option><option>일반</option><option>이번 주 안</option><option>오늘 필요</option></select></div><div><label>희망 회신 시간</label><input name="reply_time" placeholder="예: 평일 오전 10시~12시"></div><div><label>확인 내용</label><input name="issue" placeholder="예: 가격, 결과물, 적용 범위, 정산 방식" required></div></div><div class="actions"><button class="button" type="submit">추가 확인 요청 보내기</button></div><p class="micro-copy">예외 조건만 짧게 남겨 주시면 됩니다. 일반적인 비교와 데모는 각 제품 상세에서 바로 진행하실 수 있습니다.</p></form><div class="result-box" id="contact-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">안내</span><p>회사 소개는 회사 메뉴에서, 실제 데모 시연과 결제는 제품 메뉴에서, 자동 흐름에 없는 예외 조건만 이 페이지에서 남기실 수 있습니다.</p></article></div></section></main>
    '''), depth=1, page_key='contact', page_path='/contact/index.html')


def portal_page() -> str:
    prefix = rel_prefix(1)
    return doc(f"고객 포털 | {brand['name']}", '고객 조회 포털', 'portal', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>고객 포털</span></div><span class="kicker">결과 확인</span><h1>결제 후 전달 상태와 자료를 바로 확인해 보세요</h1><p class="lead">이메일과 조회 코드만 입력하면 결제 이후의 전달 상태와 결과 자료를 바로 확인할 수 있습니다. 결제 방식과 관계없이 같은 조회 코드 기준으로 확인합니다.</p><form id="portal-lookup-form"><div class="form-grid"><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" autocomplete="email" inputmode="email" required></div><div><label>조회 코드</label><input name="code" placeholder="예: NV0-2026-VER-001" autocapitalize="characters" autocomplete="off" required></div></div><div class="actions"><button class="button" type="submit">결과 전달 확인</button></div><p class="micro-copy">조회 코드는 결제 완료 또는 추가 확인 접수 이후 안내 메일로 전달됩니다.</p></form><div class="result-box" id="portal-result" role="status" aria-live="polite"></div></article><article class="card"><span class="tag">확인 결과</span><h3>결과 전달 상태와 전달 자료가 여기에 표시됩니다</h3><div class="mock-progress" id="portal-mock"><div class="mock-step"><strong>확인 전</strong><span>결제 후 받은 이메일과 조회 코드를 입력하면 바로 확인하실 수 있습니다.</span></div></div></article></div></section></main>
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
                <p class="lead">비밀키가 있어야 운영 화면을 열 수 있습니다. 자동발행 설정, 결제 상태, 공개 글 재발행, 샘플 데이터, 포털 확인 연결을 모두 이 화면에서 관리합니다.</p>
                <div class="result-box admin-gate" id="admin-gate-result">관리자 비밀키를 입력하면 운영 메뉴가 열립니다.</div>
                <div class="auth-inline admin-auth-inline">
                  <input id="admin-token-input" placeholder="관리자 비밀키" autocomplete="off" spellcheck="false">
                  <button class="button secondary" type="button" id="admin-token-save">관리자 열기</button>
                  <button class="button ghost" type="button" id="admin-token-clear">토큰 지우기</button>
                </div>
              </div>
              <div class="card accent">
                <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">운영 원칙</span>
                <h3 style="font-size:1.72rem;margin:16px 0 10px">공개 화면은 단순하게, 운영 기능은 이곳으로</h3>
                <p>고객이 보는 화면에서는 판매와 이해에 필요한 것만 남기고, 자동발행 재설정과 데이터 조작은 관리자 허브에서만 다룹니다.</p>
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
                <div class="toolbar">
                  <button class="button" data-admin-action="seed-demo">샘플 데이터 생성</button>
                  <button class="button secondary" data-admin-action="reset-all">엔진 데이터 초기화</button>
                </div>
                <div class="result-box" id="admin-action-result"></div>
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
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>결제 승인</span></div><span class="kicker">결제 완료</span><h1>결제가 완료되면 결과 전달 확인 화면으로 바로 이어집니다</h1><p class="lead">결제 승인 정보를 확인한 뒤, 전달 자료와 관련 콘텐츠를 바로 볼 수 있도록 안내합니다.</p><div class="result-box" id="payment-success-result" style="display:block">결제 정보를 확인하고 있습니다.</div><div class="actions"><a class="button secondary" href="{prefix}portal/index.html">결과 전달 확인</a><a class="button ghost" href="{prefix}products/index.html">다른 제품 보기</a></div></article></div></section></main>
    '''), depth=3, page_key='payment-success', page_path='/payments/toss/success/index.html')


def toss_fail_page() -> str:
    prefix = rel_prefix(3)
    return doc(f"결제 실패 | {brand['name']}", 'Toss 결제 실패 안내', 'payment-fail', dedent(f'''
        <main><section class="section"><div class="container form-shell"><article class="card strong"><div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>결제 실패</span></div><span class="kicker">Toss fail</span><h1>결제가 완료되지 않았습니다</h1><p class="lead">잠시 후 다시 결제하시거나, 자동 흐름에 없는 예외 조건만 추가 확인으로 남겨주세요.</p><div class="result-box" id="payment-fail-result" style="display:block">실패 정보를 확인하고 있습니다.</div><div class="actions"><a class="button" href="{prefix}checkout/index.html">다시 시작하기</a><a class="button ghost" href="{prefix}contact/index.html">추가 확인 남기기</a></div></article></div></section></main>
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
              <div class="section-head"><div><h2>이 제품이 하는 일</h2></div><p>길게 설명하지 않고, 실제로 어떤 판단과 결과를 만들어 주는지 기준으로 정리했습니다.</p></div>
              <div class="story-grid product-overview-grid">
                <article class="story-card"><span class="tag theme-chip">해결하는 문제</span><h3>지금 가장 먼저 정리해야 하는 것</h3><p data-fill="product-problem"></p></article>
                <article class="story-card"><span class="tag theme-chip">핵심 가치</span><h3>도입하면 바로 달라지는 점</h3><ul class="clean" id="product-values"></ul></article>
                <article class="story-card"><span class="tag theme-chip">결과물</span><h3>결제 후 받는 자료</h3><ul class="clean" id="product-outputs"></ul></article>
              </div>
            </div>
          </section>

          <section class="section compact" id="demo">
            <div class="container module-layout demo-layout">
              <article class="card strong demo-main-card">
                <span class="tag theme-chip">실제 데모</span>
                <h3>입력하면 바로 결과가 나오는 형태로 다시 만들었습니다</h3>
                <p class="lead demo-intro-copy">소개용 문장이 아니라, 이 제품이 어떤 입력을 받고 어떤 결과를 반환하는지 바로 확인할 수 있습니다. 저장이 필요하면 회사명과 이메일을 같이 남길 수 있습니다.</p>
                <div id="product-demo-shell"></div>
                <div class="result-box" id="product-demo-result" role="status" aria-live="polite"></div>
              </article>
              <article class="card demo-side-card">
                <span class="tag">데모에서 확인되는 것</span>
                <h3>실제 제품 구조와 맞는 결과만 보여줍니다</h3>
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
                <h3>데모로 방향을 잡은 뒤 바로 이어서 결제할 수 있습니다</h3>
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
                  <div class="actions"><button class="button" type="submit">결제 계속하기</button><a class="button secondary" href="#delivery">전달 범위 먼저 보기</a></div>
                  <p class="micro-copy">데모에서 입력한 회사명과 이메일은 결제 폼에 자동으로 이어질 수 있습니다.</p>
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
                <h3>샘플 결과에서 본 구조가 실제 전달 자료로 이어집니다</h3>
                <ol class="flow-list" id="product-workflow"></ol>
                <div class="notice">결제 후에는 결과 요약, 실행 자료, 조회 코드가 연결된 확인 흐름까지 한 번에 이어집니다.</div>
              </article>
              <article class="card strong">
                <span class="tag theme-chip">함께 보면 좋은 제품</span>
                <h3>같은 문제 축에서 이어서 검토할 수 있는 모듈</h3>
                <div class="story-grid" id="product-related-modules"></div>
              </article>
            </div>
          </section>

          <section class="section compact" id="board">
            <div class="container"><div class="section-head"><div><h2>{escape(product['name'])} 관련 글</h2></div><p>이 제품이 필요한 상황을 더 읽어보고 싶다면 아래 글을 참고하세요. 다만 핵심은 글보다 위 데모입니다.</p></div><div class="board-grid" id="product-board-grid"></div><div id="product-post-detail"></div></div>
          </section>

          <section class="section compact" id="faq"><div class="container"><div class="section-head"><div><h2>자주 묻는 질문</h2></div><p>소개보다 시연이 먼저여야 하지만, 결제 전에 자주 나오는 질문도 함께 정리했습니다.</p></div><div class="faq-grid" id="product-faq"></div></div></section>
        </main>
    '''), depth=2, page_key='product', product_key=product['key'], page_path=f'/products/{product["key"]}/index.html')

def product_board_page(product: dict) -> str:
    return doc(f"{product['name']} 게시판 | {brand['name']}", f"{product['name']} 콘텐츠 허브", product['theme'], dedent(f'''
        <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../../index.html">HOME</a><span class="sep">/</span><a href="../../../products/index.html">제품</a><span class="sep">/</span><a href="../../{escape(product['key'])}/index.html">{escape(product['name'])}</a><span class="sep">/</span><span>게시판</span></div><span class="tag theme-chip">관련 글 모음</span><h1>{escape(product['name'])} 콘텐츠 허브</h1><p class="lead">이 제품과 관련된 글을 먼저 읽고, 바로 제품 설명·실제 데모·결제로 이어질 수 있게 구성했습니다.</p><div class="actions"><a class="button" href="../../{escape(product['key'])}/index.html#demo">데모 시연</a><a class="button secondary" href="../../{escape(product['key'])}/index.html#intro">제품 설명 보기</a><a class="button ghost" href="../../{escape(product['key'])}/index.html#order">결제 진행</a></div></div><div class="card theme-panel"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">게시판 안내</span><h3 style="font-size:1.7rem;margin:16px 0 10px">제품을 보기 전에 먼저 둘러보기 좋은 글을 보여드립니다</h3><p>{escape(product['summary'])}</p></div></div></section><section class="section compact"><div class="container"><div class="board-grid" id="product-board-grid"></div><div id="product-post-detail"></div></div></section></main>
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
