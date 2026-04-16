import json
import shutil
from html import escape
from pathlib import Path
from textwrap import dedent

ALLOWED_TOP_LEVEL_DIRS = {'assets', 'admin', 'board', 'legal', '.well-known'}
ALLOWED_ROOT_FILES = {'index.html', 'robots.txt', 'sitemap.xml', 'favicon.ico'}


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


def doc(brand: dict, title: str, description: str, body_class: str, body: str, *, depth: int, page_key: str, page_path: str):
    prefix = rel_prefix(depth)
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
<body class="{body_class}" data-page="{page_key}">
<header class="site-header" id="site-header"></header>
{body}
<footer class="footer" id="site-footer"></footer>
</body>
</html>'''


def home_page(data: dict) -> str:
    brand = data['brand']
    return doc(brand, brand['title'], brand['hero_description'], 'home', dedent(f'''
    <main>
      <section class="hero">
        <div class="container hero-grid">
          <div class="card strong">
            <span class="kicker">{escape(brand['tagline'])}</span>
            <h1>{escape(brand['hero_title'])}</h1>
            <p class="lead">{escape(brand['hero_description'])}</p>
            <div class="actions">
              <a class="button" href="./board/index.html">AI 블로그 허브 보기</a>
              <a class="button secondary" href="./admin/index.html">관리자 열기</a>
              <a class="button ghost" href="./legal/privacy/index.html">개인정보처리방침</a>
            </div>
            <div class="live-strip" id="live-stats"></div>
          </div>
          <div class="showcase-grid">
            <article class="card accent">
              <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">운영 원칙</span>
              <h3 style="font-size:1.75rem;margin:16px 0 10px">CTA 포스팅 자동발행만 남겼습니다</h3>
              <p>검색 유입을 읽히는 포스팅과 CTA로 연결하는 흐름만 남기고, 가격·결제·포털 같은 부가 운영은 비활성화했습니다.</p>
              <div class="inline-list"><span>홈</span><span>게시판</span><span>관리자</span><span>개인정보처리방침</span></div>
            </article>
            <article class="card strong">
              <span class="tag">발행 축</span>
              <h3>Veridion · ClearPort · GrantOps · DraftForge</h3>
              <p class="lead" style="font-size:1rem">제품별 CTA 포스팅 시드와 자동발행 주제는 유지하고, 각 글 끝 CTA는 바로 문의 행동으로 이어지게 맞췄습니다.</p>
              <div class="badge-row"><span class="badge">시드 글 8건</span><span class="badge">주기 자동발행</span><span class="badge">즉시 발행</span><span class="badge">백업/복구</span></div>
            </article>
          </div>
        </div>
      </section>
      <section class="section compact"><div class="container"><div class="section-head"><div><h2>게시판에서 운영하는 4개 CTA 축</h2></div><p>각 제품은 자동발행 주제와 CTA 라벨을 따로 가지고 있어 게시판 한곳에서 분류·발행·클릭 유도를 관리할 수 있습니다.</p></div><div class="product-grid" id="product-grid"></div></div></section>
      <section class="section compact"><div class="container"><div class="section-head"><div><h2>최근 발행 글</h2></div><p>시드 글과 예약 글을 한곳에서 보고, 마음에 드는 CTA 포스팅은 바로 자세히 확인할 수 있습니다.</p></div><div class="board-grid" id="public-board-grid"></div><div id="public-post-detail"></div></div></section>
    </main>
    '''), depth=0, page_key='home', page_path='/index.html')


def board_page(data: dict) -> str:
    brand = data['brand']
    return doc(brand, f"AI 자동발행 블로그 허브 | {brand['name']}", 'AI 자동발행 블로그 허브', 'board', dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>AI 자동발행 블로그 허브</span></div><span class="kicker">AI blog board</span><h1>AI 자동발행 블로그 허브</h1><p class="lead">제품 소개와 전환 페이지로 자연스럽게 이어지는 AI 자동발행 블로그 글을 주기적으로 발행합니다. 각 글은 제품 상세, 데모, 문의 CTA와 함께 끝납니다.</p><div class="actions"><a class="button" href="../index.html">홈으로</a><a class="button secondary" href="../admin/index.html">관리자 열기</a><a class="button ghost" href="mailto:{escape(brand['contact_email'])}">운영 문의</a></div></div><div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">운영 범위</span><h3 style="font-size:1.72rem;margin:16px 0 10px">자동발행 · 재시드 · 즉시 발행 · 백업 복구</h3><p>공개 운영은 블로그 허브 중심으로 유지하고, 필요한 경우에만 관리자에서 발행과 복구를 제어합니다.</p></div></div></section><section class="section compact"><div class="container"><div class="board-grid" id="public-board-grid"></div><div id="public-post-detail"></div></div></section></main>
    '''), depth=1, page_key='board', page_path='/board/index.html')


def admin_page(data: dict) -> str:
    brand = data['brand']
    return doc(brand, f"관리자 허브 | {brand['name']}", '게시판 자동발행 관리자', 'admin', dedent('''
    <main id="admin-console"><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../index.html">HOME</a><span class="sep">/</span><span>관리자 허브</span></div><span class="kicker">Admin hub</span><h1>게시판 자동발행 운영만 관리합니다</h1><p class="lead">이 화면에서는 게시판 시드 재생성, 즉시 발행, 전체 초기화, export/import, 백업 복구만 관리합니다.</p><div class="auth-inline"><input id="admin-token-input" placeholder="관리자 토큰"><button class="button secondary" type="button" id="admin-token-save">토큰 저장</button><button class="button ghost" type="button" id="admin-token-clear">토큰 지우기</button></div><div class="toolbar"><button class="button" data-admin-action="publish-now">즉시 발행</button><button class="button secondary" data-admin-action="reseed-board">재시드</button><button class="button ghost" data-admin-action="reset-all">전체 초기화</button></div><div class="result-box" id="admin-action-result"></div></div><div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">운영 목적</span><h3 style="font-size:1.72rem;margin:16px 0 10px">1인 운영 기준으로 발행과 복구만 빠르게</h3><p>게시판 발행 수, 예약 상태, 최근 발행 로그를 중심으로만 확인할 수 있게 단순화했습니다.</p></div></div></section><section class="section compact"><div class="container"><div class="admin-grid" id="admin-summary"></div></div></section><section class="section compact"><div class="container"><div class="record-grid" id="admin-publications"></div></div></section><section class="section compact"><div class="container"><div class="card strong"><div class="mock-progress" id="admin-feed"></div></div></div></section></main>
    '''), depth=1, page_key='admin', page_path='/admin/index.html')


def privacy_page(data: dict) -> str:
    brand = data['brand']
    return doc(brand, f"개인정보처리방침 | {brand['name']}", '개인정보 처리방침', 'legal', dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../index.html">HOME</a><span class="sep">/</span><span>개인정보처리방침</span></div><h1>개인정보처리방침</h1><p class="lead">현재 사이트는 AI 자동발행 블로그 허브 운영에 필요한 최소 정보만 처리합니다. 관리자 토큰, 게시판 발행 로그, 백업 파일은 운영 목적으로만 사용합니다.</p><div class="kv"><div class="row"><strong>안내 이메일</strong><span>{escape(brand.get('contact_email', ''))}</span></div><div class="row"><strong>주요 처리 목적</strong><span>게시판 운영, 관리자 작업, 백업 복구, 보안 점검</span></div><div class="row"><strong>기본 보관 원칙</strong><span>운영 목적 달성 후 지체 없이 파기, 법령상 보존 의무 시 별도 분리 보관</span></div></div></div></div></section></main>
    '''), depth=2, page_key='privacy', page_path='/legal/privacy/index.html')


def robots_txt() -> str:
    return 'User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n'


def sitemap_xml(data: dict) -> str:
    brand = data['brand']['domain'].rstrip('/')
    urls = ['/', '/board/', '/admin/', '/legal/privacy/']
    rows = ''.join(f'<url><loc>{escape(brand + path)}</loc></url>' for path in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>'


def security_txt(data: dict) -> str:
    email = data['brand'].get('contact_email', 'security@nv0.kr')
    domain = data['brand']['domain'].rstrip('/')
    return f'Contact: mailto:{email}\nPolicy: {domain}/legal/privacy/\nPreferred-Languages: ko, en\nCanonical: {domain}/.well-known/security.txt\n'


def cleanup_dist_for_board_only(dist: Path) -> None:
    for path in list(dist.iterdir()):
        rel = path.relative_to(dist).as_posix()
        if path.is_dir() and rel not in ALLOWED_TOP_LEVEL_DIRS:
            shutil.rmtree(path, ignore_errors=True)
        elif path.is_file() and rel not in ALLOWED_ROOT_FILES:
            path.unlink(missing_ok=True)
    # legal 하위는 privacy만 유지
    legal = dist / 'legal'
    if legal.exists():
        for path in list(legal.iterdir()):
            if path.name != 'privacy':
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink(missing_ok=True)
    # .well-known 하위는 security.txt만 유지
    wk = dist / '.well-known'
    if wk.exists():
        for path in list(wk.iterdir()):
            if path.name != 'security.txt':
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink(missing_ok=True)


def apply_board_only_overrides(dist: Path, data: dict, src: Path) -> None:
    cleanup_dist_for_board_only(dist)
    write(dist / 'index.html', home_page(data))
    write(dist / 'board' / 'index.html', board_page(data))
    write(dist / 'admin' / 'index.html', admin_page(data))
    write(dist / 'legal' / 'privacy' / 'index.html', privacy_page(data))
    write(dist / 'robots.txt', robots_txt())
    write(dist / 'sitemap.xml', sitemap_xml(data))
    write(dist / '.well-known' / 'security.txt', security_txt(data))
    board_js = src / 'assets' / 'site.board-only.js'
    if board_js.exists():
        write(dist / 'assets' / 'site.js', board_js.read_text(encoding='utf-8'))
    write(dist / 'assets' / 'site-data.js', 'window.NV0_SITE_DATA = ' + json.dumps(data, ensure_ascii=False, indent=2) + ';')
