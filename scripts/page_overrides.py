
import base64
import json
from pathlib import Path
from html import escape
from textwrap import dedent

POLICY_EFFECTIVE_DATE = '2026-04-15'
POLICY_UPDATED_DATE = '2026-04-15'
BIZ_NOTICE_UPDATED_DATE = '2026-04-15'


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


def static_header_markup(prefix: str, page_key: str, page_path: str) -> str:
    product_active = 'active' if page_key in {'products', 'product', 'pricing', 'modules'} or '/products/' in page_path or '/modules/' in page_path else ''
    board_active = 'active' if page_key == 'board' or '/board/' in page_path else ''
    company_active = 'active' if page_key == 'company' or '/company/' in page_path else ''
    auth_active = 'active' if page_key == 'auth' or '/auth/' in page_path else ''
    home_active = 'active' if page_key == 'home' else ''
    product_sub_guide = 'active' if '/products/veridion/' in page_path and not any(token in page_path for token in ('/plans/', '/board/', '/demo/', '/faq/', '/delivery/')) else ''
    product_sub_plans = 'active' if '/products/veridion/plans/' in page_path or page_key == 'pricing' else ''
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
    return f'<button class="admin-fab" type="button" data-admin-entry="1" title="권한 확인 후 관리자 메뉴로 들어갑니다">관계자</button><div class="container nav-wrap"><div class="nav-left"><button class="mobile-nav-toggle" type="button" aria-expanded="false" aria-controls="mobile-drawer" data-nav-toggle="1">메뉴</button><a class="brand" href="{prefix}index.html"><span class="brand-mark">V</span><span class="brand-copy"><strong>Veridion</strong><span>온라인 개인사업자용 법률·규제 리스크 방어막</span></span></a></div><nav class="nav-links">{nav_links}</nav></div><div class="container subnav"><span class="subnav-label">제품</span>{quick_links}</div>'


def static_side_nav_markup(prefix: str, page_key: str, page_path: str) -> str:
    product_active = 'active' if page_key in {'products', 'product', 'pricing', 'modules'} or '/products/' in page_path or '/modules/' in page_path else ''
    board_active = 'active' if page_key == 'board' or '/board/' in page_path else ''
    company_active = 'active' if page_key == 'company' or '/company/' in page_path else ''
    auth_active = 'active' if page_key == 'auth' or '/auth/' in page_path else ''
    home_active = 'active' if page_key == 'home' else ''
    product_sub_guide = 'active' if '/products/veridion/' in page_path and not any(token in page_path for token in ('/plans/', '/board/', '/demo/', '/faq/', '/delivery/')) else ''
    product_sub_plans = 'active' if '/products/veridion/plans/' in page_path or page_key == 'pricing' else ''
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


def static_footer_markup(brand: dict, prefix: str) -> str:
    info = (brand or {}).get('business_info') or {}
    email = info.get('contact_email') or brand.get('contact_email', 'ct@nv0.kr')
    operator = info.get('operator_name') or brand.get('name', 'NV0')
    notice = info.get('support_notice') or '정책과 제품 안내는 같은 기준으로 제공합니다.'
    representative = info.get('representative_name', '')
    biz_no = info.get('registration_number', '')
    address = info.get('business_address', '')
    return f'<div class="container footer-grid"><div><div class="brand"><span class="brand-mark">N0</span><span class="brand-copy"><strong>{escape(brand.get("name", "NV0"))}</strong><span>데모, 가격, 전달물을 먼저 보고 바로 판단할 수 있게 정리했습니다.</span></span></div><small style="margin-top:14px">공개 화면은 제품 이해와 구매 판단에 집중하고, 내부 운영 기능은 뒤로 분리했습니다.</small></div><div><strong>빠른 이동</strong><small><a href="{prefix}products/index.html">제품</a><br><a href="{prefix}board/index.html">자료실</a><br><a href="{prefix}company/index.html">회사소개</a><br><a href="{prefix}pricing/index.html">가격</a><br><a href="{prefix}faq/index.html">FAQ</a></small></div><div><strong>안내/정책</strong><small>상호: {escape(operator)}<br>{f"대표자: {escape(representative)}<br>" if representative else ""}{f"사업자등록번호: {escape(biz_no)}<br>" if biz_no else ""}<a href="mailto:{escape(email)}">{escape(email)}</a><br>{f"{escape(address)}<br>" if address else ""}{escape(notice)}<br>시행일 {POLICY_EFFECTIVE_DATE} · 최종 개정일 {POLICY_UPDATED_DATE}<br><a href="{prefix}portal/index.html">고객 포털</a><br><a href="{prefix}auth/index.html">로그인(회원가입)</a><br><a href="{prefix}legal/privacy/index.html">개인정보처리방침</a><br><a href="{prefix}legal/terms/index.html">이용약관</a><br><a href="{prefix}legal/refund/index.html">환불 정책</a><br><a href="{prefix}legal/cookies/index.html">쿠키 및 저장 안내</a></small></div></div>'


def doc(brand: dict, title: str, description: str, body_class: str, body: str, *, depth: int, page_key: str, page_path: str, product_key: str | None = None) -> str:
    prefix = rel_prefix(depth)
    attrs = [f'class="{body_class}"', f'data-page="{page_key}"']
    if product_key:
        attrs.append(f'data-product="{product_key}"')
    canonical = page_url(brand, page_path)
    og_type = 'product' if page_key == 'product' else 'website'
    schema_json = build_page_schema(brand, title, description, page_path, page_key, product_key)
    header_markup = static_header_markup(prefix, page_key, page_path)
    side_nav_markup = static_side_nav_markup(prefix, page_key, page_path)
    footer_markup = static_footer_markup(brand, prefix)
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
<aside id="side-nav-shell" class="side-nav-shell">{side_nav_markup}</aside>
<header class="site-header" id="site-header">{header_markup}</header>
{body}
<footer class="footer" id="site-footer">{footer_markup}</footer>
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


def trust_points_markup(brand: dict) -> str:
    points = (((brand or {}).get('business_info') or {}).get('trust_points') or [])
    return ''.join(f'<li>{escape(item)}</li>' for item in points)


def business_info_markup(brand: dict) -> str:
    info = (brand or {}).get('business_info') or {}
    rows = [
        ('상호', info.get('operator_name') or brand.get('name', 'NV0')),
        ('대표자', info.get('representative_name') or ''),
        ('사업자등록번호', info.get('registration_number') or ''),
        ('개업연월일', info.get('opening_date') or ''),
        ('사업장 소재지', info.get('business_address') or ''),
        ('안내 이메일', info.get('contact_email') or brand.get('contact_email', '')),
        ('과세 유형', info.get('tax_status') or ''),
        ('관할 세무서', info.get('tax_office') or ''),
        ('안내 원칙', info.get('support_notice') or '결제 방식과 계약 안내는 같은 기준으로 제공합니다.'),
    ]
    return ''.join(
        f'<div class="row"><strong>{escape(label)}</strong><span>{escape(value)}</span></div>'
        for label, value in rows if value
    )


def business_license_card_markup(brand: dict, prefix: str) -> str:
    info = (brand or {}).get('business_info') or {}
    image = info.get('license_image') or '/assets/business-registration.png'
    href = image if image.startswith('http') else f"{prefix}{image.lstrip('/')}"
    caption = info.get('registration_number') or ''
    return (
        f'<article class="card strong"><span class="tag">사업자 등록</span>'
        f'<h3>사업자등록 정보와 증빙 이미지</h3>'
        f'<p>공개 화면에서도 운영 주체를 바로 확인하실 수 있도록 기본 사업자 정보를 고지합니다.</p>'
        f'<a href="{escape(href)}" target="_blank" rel="noopener">'
        f'<img src="{escape(href)}" alt="NV0 사업자등록증" style="display:block;width:100%;max-width:420px;border-radius:18px;border:1px solid rgba(148,163,184,.24);margin-top:16px"></a>'
        f'<small style="display:block;margin-top:12px;color:#64748b">사업자등록번호 {escape(caption)} · 최종 반영일 {BIZ_NOTICE_UPDATED_DATE}</small>'
        f'</article>'
    )


def engine_layers_markup(data: dict) -> str:
    return ''.join(f'<span>{escape(layer)}</span>' for layer in data['engine'].get('automation_layers', []))


def product_cards_markup(products: list[dict], prefix: str, *, include_board: bool = True, include_docs: bool = False) -> str:
    cards = []
    for item in products:
        actions = []
        if include_board:
            actions.append(f'<a class="button secondary" href="{prefix}products/{escape(item["key"])}/board/index.html">AI 운영 블로그 허브</a>')
        actions.append(f'<a class="button soft" href="{prefix}products/{escape(item["key"])}/index.html#demo">데모 시연</a>')
        actions.append(f'<a class="button ghost" href="{prefix}products/{escape(item["key"])}/index.html#intro">제품 설명 보기</a>')
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
        ('회사형 메인', '회사 소개와 운영 기준을 먼저 보여 주고, 제품 상세에서만 데모 시연과 결제가 이어지게 분리했습니다.'),
        ('공용 엔진', '결제 저장, 자동 실행, 자동 발행, 고객 포털, 관리자 허브를 같은 기록선으로 묶습니다.'),
        ('제품 상세', '각 제품마다 운영자료실, 설명, 데모 시연, 결제, 정상작동 및 발행 제공이 한 페이지 흐름으로 이어집니다.'),
        ('AI 운영 블로그 허브', '제품별 CTA 글과 연관 주제를 계속 쌓아 유입을 제품 설명과 결제로 연결합니다.'),
        ('문서·사례', '가격, 문서 센터, 적용 사례, FAQ를 따로 두어 검토형 고객도 막히지 않게 했습니다.'),
        ('고객 포털', '결제 후에는 조회 코드 기준으로 정상작동 상태와 발행 제공 자료를 다시 확인할 수 있습니다.'),
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
        ('AI 운영 블로그 허브', f'{prefix}board/index.html', 'AI 자료 글과 제품 연결 흐름을 봅니다.'),
        ('고객 포털', f'{prefix}portal/index.html', '결제 후 조회 코드로 정상작동 상태와 발행 제공 자료를 확인합니다.'),
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




def architecture_list_markup(values: list[str]) -> str:
    return ''.join(f'<li>{escape(item)}</li>' for item in values if item)


def architecture_sections_markup(product: dict) -> str:
    architecture = product.get('architecture') or {}
    if not architecture:
        return '<div class="empty-box">아직 정리된 설계 기준이 없습니다.</div>'
    sections = [
        ('입력 기준', architecture.get('input_contract', [])),
        ('엔진 구조', architecture.get('engine_layers', [])),
        ('결과 계약', architecture.get('output_contract', [])),
        ('품질 게이트', architecture.get('quality_gates', [])),
        ('성능 설계 기준', architecture.get('performance_targets', [])),
        ('실패 대응', architecture.get('failure_controls', [])),
        ('확장 경로', architecture.get('expansion_paths', [])),
    ]
    cards = []
    for title, values in sections:
        if not values:
            continue
        cards.append(f'<article class="story-card"><span class="tag">{escape(title)}</span><ul class="clean">{architecture_list_markup(values)}</ul></article>')
    summary = architecture.get('summary', '')
    summary_html = f'<p style="margin-bottom:16px">{escape(summary)}</p>' if summary else ''
    return summary_html + f'<div class="story-grid">{"".join(cards)}</div>'

def architecture_scorecards_markup(product: dict) -> str:
    architecture = product.get('architecture') or {}
    cards = [
        ('입력 명확성', len(architecture.get('input_contract', [])), '처음에 받아야 할 정보 범위를 먼저 좁혀 재작업을 줄입니다.'),
        ('엔진 계층', len(architecture.get('engine_layers', [])), '자동 처리와 검토 단계를 섞지 않고 분리해 품질을 지킵니다.'),
        ('품질 게이트', len(architecture.get('quality_gates', [])), '결과를 내보내기 전 반드시 걸러야 하는 조건을 둡니다.'),
        ('실패 대응', len(architecture.get('failure_controls', [])), '예외 상황을 감추지 않고 다른 경로로 전환합니다.'),
    ]
    return ''.join(
        f'<article class="admin-card"><span class="tag">{escape(title)}</span><h3>{value}</h3><p>{escape(body)}</p></article>'
        for title, value, body in cards
    )


def architecture_focus_markup(product: dict) -> str:
    architecture = product.get('architecture') or {}
    highlights = [
        ('성능 목표', (architecture.get('performance_targets') or ['지금 가장 먼저 보여야 할 결과를 앞세워 읽는 시간을 줄입니다.'])[0]),
        ('실패 대응', (architecture.get('failure_controls') or ['애매한 판단은 자동 확정 대신 검토 필요 상태로 남깁니다.'])[0]),
        ('확장 경로', (architecture.get('expansion_paths') or ['핵심 구조를 흔들지 않고 필요한 기능만 단계적으로 붙일 수 있게 설계합니다.'])[0]),
    ]
    return ''.join(
        f'<article class="story-card"><span class="tag">{escape(title)}</span><p>{escape(body)}</p></article>'
        for title, body in highlights
    )


def architecture_matrix_markup(products: list[dict], prefix: str) -> str:
    cards = []
    for product in products:
        architecture = product.get('architecture') or {}
        performance = (architecture.get('performance_targets') or ['핵심 판단이 먼저 보이도록 구성했습니다.'])[0]
        failure = (architecture.get('failure_controls') or ['예외 상황은 다른 경로로 분기합니다.'])[0]
        outputs = len(product.get('outputs', []))
        quality = len(architecture.get('quality_gates', []))
        cards.append(
            f'<article class="story-card {escape(product["theme"])}">'
            f'<span class="tag theme-chip">{escape(product["label"])}</span>'
            f'<h3>{escape(product["name"])}</h3>'
            f'<p>{escape(architecture.get("summary") or product.get("summary", ""))}</p>'
            f'<div class="admin-grid" style="margin-top:14px">'
            f'<article class="admin-card"><span class="tag">입력 기준</span><h3>{len(architecture.get("input_contract", []))}</h3><p>처음에 고정하는 정보 항목 수</p></article>'
            f'<article class="admin-card"><span class="tag">결과물</span><h3>{outputs}</h3><p>기본 제공되는 핵심 전달물 수</p></article>'
            f'<article class="admin-card"><span class="tag">품질 게이트</span><h3>{quality}</h3><p>출력 전 반드시 확인하는 기준 수</p></article>'
            f'</div>'
            f'<ul class="clean" style="margin-top:14px"><li>{escape(performance)}</li><li>{escape(failure)}</li></ul>'
            f'<div class="small-actions"><a href="{prefix}products/{escape(product["key"])}/index.html">제품 상세</a><a href="{prefix}products/{escape(product["key"])}/demo/index.html">즉시 데모</a></div>'
            f'</article>'
        )
    return ''.join(cards)


def product_value_list(product: dict, key: str) -> str:
    return ''.join(f'<li>{escape(item)}</li>' for item in product.get(key, []))


def related_modules_markup(product: dict, product_map: dict[str, dict], prefix: str) -> str:
    cards = []
    for key in product.get('related_modules', []):
        item = product_map.get(key)
        if not item:
            continue
        cards.append(
            f'<article class="story-card {escape(item["theme"])}"><span class="tag theme-chip">{escape(item["label"])}</span><h3>{escape(item["name"])}</h3><p>{escape(item["summary"])}</p><div class="small-actions"><a href="{prefix}products/{escape(item["key"])}/index.html#intro">제품 설명 보기</a><a href="{prefix}products/{escape(item["key"])}/index.html#demo">데모 시연</a></div></article>'
        )
    return ''.join(cards) or '<div class="empty-box">연결된 제품이 아직 없습니다.</div>'


def faq_markup(product: dict) -> str:
    return ''.join(
        f'<article class="faq-card"><span class="tag">Q</span><h3>{escape(item["q"])}</h3><p>{escape(item["a"])}</p></article>'
        for item in product.get('faqs', [])
    )


def plan_cards_markup(product: dict) -> str:
    def render_plan(plan: dict) -> str:
        includes = ''.join(f'<li>{escape(item)}</li>' for item in plan.get("includes", []))
        recommended = '<span class="tag" style="margin-left:8px">추천</span>' if plan.get("recommended") else ''
        meta = []
        if plan.get("delivery"):
            meta.append(f'납기 {escape(plan["delivery"])}')
        if plan.get("revisions"):
            meta.append(escape(plan["revisions"]))
        meta_html = f'<div class="plan-meta">{" · ".join(meta)}</div>' if meta else ''
        include_html = f'<ul class="clean plan-include-list">{includes}</ul>' if includes else ''
        card_class = 'plan-card recommended' if plan.get("recommended") else 'plan-card'
        return f'<article class="{card_class}"><div class="plan-head"><span class="tag">{escape(plan["name"])}</span>{recommended}</div><h3>{escape(plan["price"])}</h3><p>{escape(plan.get("note", ""))}</p>{meta_html}{include_html}<div class="small-actions"><a class="button" href="#order" data-plan-pick="{escape(plan["name"])}">이 플랜으로 결제 계속하기</a></div></article>'

    return ''.join(render_plan(plan) for plan in product.get('plans', []))


def build_home_page(data: dict) -> str:
    brand = data['brand']
    products = data['products']
    focus = next((item for item in products if item['key'] == 'veridion'), products[0])
    modules = [item for item in products if item['key'] != 'veridion']
    module_cards = ''.join(
        f'<article class="story-card {escape(item["theme"])}"><span class="tag theme-chip">연결 모듈</span><h3>{escape(item["name"])}</h3><p>{escape(item["summary"])}</p><div class="small-actions"><a href="./products/{escape(item["key"] )}/index.html">모듈 상세</a><a href="./products/{escape(item["key"] )}/board/index.html">모듈 자료실</a></div></article>'
        for item in modules
    )
    body = dedent(f'''    <main>
      <section class="hero">
        <div class="container hero-grid">
          <div class="card strong">
            <span class="kicker">{escape(brand["tagline"])}</span>
            <h1>{escape(brand["hero_title"])}</h1>
            <p class="lead">{escape(brand["hero_description"])}</p>
            <div class="actions">
              <a class="button" href="./products/veridion/demo/index.html">무료 데모 바로 실행</a>
              <a class="button secondary" href="./products/veridion/plans/index.html">가격과 발행 범위 보기</a>
              <a class="button ghost" href="./board/index.html">자료실 보기</a>
            </div>
            <div class="quick-link-grid">
              <a class="quick-link-card" href="./products/veridion/index.html"><strong>제품 안내</strong><span>무엇을 점검하고 무엇을 발행하는지 먼저 봅니다.</span></a>
              <a class="quick-link-card" href="./products/veridion/demo/index.html"><strong>무료 데모</strong><span>사이트 주소를 넣고 위기 점수와 영역별 건수를 먼저 봅니다.</span></a>
              <a class="quick-link-card" href="./products/veridion/plans/index.html"><strong>가격</strong><span>결제 후 열리는 전체 리포트와 추가 발행 범위를 봅니다.</span></a>
              <a class="quick-link-card" href="./auth/index.html"><strong>로그인</strong><span>결제 후 지난 발행 이력과 조회 코드를 계정으로 묶어 봅니다.</span></a>
            </div>
          </div>
          <div class="card accent">
            <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">무료 데모에서 먼저 보이는 것</span>
            <h3 style="font-size:1.72rem;margin:16px 0 10px">영역별 건수, 위기 점수, 예상 과태료를 먼저 공개합니다</h3>
            <div class="quick-demo-grid">
              <button class="quick-demo-button" type="button" data-quick-demo="veridion" data-quick-scenario="0">Veridion 미리보기</button>
            </div>
            <div class="result-box" id="quick-demo-result" role="status" aria-live="polite"></div>
            <div class="notice notice-light" style="margin-top:16px"><strong>대표 흐름</strong><br>사이트 주소 입력 → 무료 데모 → 가격 확인 → 결제 → 발행 → 로그인 이력 조회</div>
          </div>
        </div>
      </section>
      <section class="section compact">
        <div class="container">
          <div class="section-head">
            <div><h2>지금 공개 판매와 검증에 집중하는 핵심 제품</h2></div>
            <p>공개 홈에서는 Veridion 한 제품만 전면에 보여 줍니다. 다른 제품은 연결 모듈 허브에서 유지·검증하며, 추후 같은 품질 수준으로 결합합니다.</p>
          </div>
          <div class="product-grid" id="product-grid"><article class="card product-card strong {escape(focus['theme'])}"><span class="tag theme-chip">공개 핵심 제품</span><h3>{escape(focus['name'])}</h3><p>{escape(focus['problem'])}</p><ul class="clean">{''.join(f'<li>{escape(text)}</li>' for text in focus.get('value_points', [])[:4])}</ul><div class="small-actions"><a href="./products/veridion/index.html">제품 안내</a><a href="./products/veridion/demo/index.html">무료 데모</a><a href="./products/veridion/plans/index.html">가격</a></div></article><article class="card strong"><span class="tag">결제 후 열리는 항목</span><h3>전체 이슈, 맞춤 지침, 문구안, 정밀 리포트 발행</h3><p>무료 데모에서는 상위 이슈와 점수만 보여 주고, 결제 후에는 전체 리포트와 문구안을 엽니다. 추가 결제 시 해당 사이트에 맞춘 정밀 지침과 문구를 별도 리포트로 발행합니다.</p><ul class="clean"><li>전체 리스크 목록</li><li>페이지별 수정 우선순위</li><li>맞춤 문구안</li><li>로그인 이력 조회</li></ul></article></div>
        </div>
      </section>
      <section class="section compact">
        <div class="container">
          <div class="section-head"><div><h2>추후 결합 예정인 연결 모듈</h2></div><p>ClearPort, GrantOps, DraftForge는 별도 허브에서 유지합니다.</p></div>
          <div class="story-grid" id="module-matrix">{module_cards}</div>
          <div class="small-actions" style="margin-top:18px"><a href="./modules/index.html">연결 모듈 허브 보기</a></div>
        </div>
      </section>
      <section class="section compact">
        <div class="container accordion-stack">
          <details class="fold-card" open>
            <summary><strong>작동 흐름</strong><span>무료 데모 → 결제 → 발행 → 포털 → 로그인 이력 조회</span></summary>
            <div><div class="timeline">{timeline_markup(data)}</div></div>
          </details>
          <details class="fold-card">
            <summary><strong>신뢰 기준</strong><span>가격, 범위, 전달물, 조회 코드를 같은 기준으로 운영합니다.</span></summary>
            <div><ul class="clean">{trust_points_markup(brand)}</ul></div>
          </details>
        </div>
      </section>
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
            <p class="lead">처음 방문한 고객은 쉽게 이해해야 하고, 운영자는 흔들리지 않게 관리해야 합니다. 그래서 공개 화면은 단순하게, 운영 화면은 분리해서 만들고, 제품 설명과 결제·제공 기준은 같은 기준으로 맞췄습니다.</p>
            <div class="actions">
              <a class="button" href="{prefix}products/index.html">제품 모듈 보기</a>
              <a class="button secondary" href="{prefix}engine/index.html">공통 엔진 보기</a>
              <a class="button ghost" href="{prefix}docs/index.html">문서 센터</a>
            </div>
          </div>
          <div class="card accent">
            <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">운영 원칙</span>
            <h3 style="font-size:1.72rem;margin:16px 0 10px">고객은 단순하게, 운영은 정확하게</h3>
            <ul class="clean inverse-list">{principles}</ul>
          </div>
        </div>
      </section>
      <section class="section compact"><div class="container"><div class="story-grid">{company_sections_markup(company_profile)}</div></div></section>
      <section class="section compact"><div class="container module-layout"><article class="card strong"><span class="tag">운영 정보</span><h3>결제 전 먼저 확인할 수 있는 사업자 정보</h3><div class="kv">{business_info_markup(brand)}</div></article><article class="card strong"><span class="tag">신뢰 기준</span><h3>공개 화면에서 먼저 밝히는 운영 원칙</h3><ul class="clean">{trust_points_markup(brand)}</ul></article></div></section>
      <section class="section compact"><div class="container module-layout">{business_license_card_markup(brand, prefix)}<article class="card strong"><span class="tag">고지 기준</span><h3>결제, 환불, 개인정보 처리 기준도 함께 공개합니다</h3><ul class="clean"><li>제품 페이지와 결제 화면에서 같은 사업자 주체를 기준으로 운영합니다.</li><li>개인정보처리방침, 환불정책, 이용약관에 사업자 기본 정보를 함께 표시합니다.</li><li>배포 후에도 공개 고지 정보와 실제 정산 주체가 일치하도록 점검합니다.</li></ul></article></div></section>
    </main>
    ''')
    return doc(brand, f'회사 | {brand["name"]}', '엔브이제로 회사 소개', 'company', body, depth=1, page_key='company', page_path='/company/index.html')

def build_products_page(data: dict) -> str:
    brand = data['brand']
    products = data['products']
    prefix = rel_prefix(1)
    focus = next((item for item in products if item['key'] == 'veridion'), products[0])
    modules = [item for item in products if item['key'] != 'veridion']
    module_cards = ''.join(
        f'''        <article class="story-card {escape(item['theme'])}">
          <span class="tag theme-chip">연결 모듈</span>
          <h3>{escape(item['name'])}</h3>
          <p>{escape(item['summary'])}</p>
          <div class="small-actions"><a href="{prefix}products/{escape(item['key'])}/index.html">모듈 상세</a><a href="{prefix}products/{escape(item['key'])}/board/index.html">모듈 자료실</a></div>
        </article>
        '''
        for item in modules
    )
    body = dedent(f'''    <main>
      <section class="section">
        <div class="container page-hero">
          <div class="card strong">
            <div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>제품</span></div>
            <span class="kicker">Products</span>
            <h1>현재 공개 판매와 검증은 Veridion 한 제품에 집중합니다</h1>
            <p class="lead">상단 메뉴의 제품은 Veridion을 뜻합니다. 사이트 주소를 넣어 무료 데모를 먼저 보고, 가격과 발행 범위를 확인한 뒤 결제와 로그인 이력 조회까지 같은 흐름으로 이어지게 구성했습니다.</p>
            <div class="actions"><a class="button" href="{prefix}products/veridion/demo/index.html">무료 데모</a><a class="button secondary" href="{prefix}products/veridion/plans/index.html">가격 보기</a><a class="button ghost" href="{prefix}products/veridion/board/index.html">자료실 보기</a></div>
          </div>
          <div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">연결 모듈 원칙</span><h3 style="font-size:1.72rem;margin:16px 0 10px">다른 제품은 기능을 유지하되 공개 전면 노출만 분리합니다</h3><p>ClearPort, GrantOps, DraftForge는 연결 모듈 허브에서 따로 관리합니다. 기능은 유지하되 공개 주력 제품 흐름을 흐리지 않도록 구조를 분리했습니다.</p></div>
        </div>
      </section>
      <section class="section compact"><div class="container"><div class="product-grid" id="product-grid"><article class="card product-card strong {escape(focus['theme'])}"><span class="tag theme-chip">공개 핵심 제품</span><h3>{escape(focus['name'])}</h3><p>{escape(focus['headline'])}</p><ul class="clean">{''.join(f'<li>{escape(text)}</li>' for text in focus.get('fit_for', [])[:3])}</ul><div class="product-module-grid compact-grid"><a class="quick-link-card" href="{prefix}products/veridion/index.html"><strong>안내</strong><span>무엇을 점검하는지 봅니다.</span></a><a class="quick-link-card" href="{prefix}products/veridion/demo/index.html"><strong>무료 데모</strong><span>점수와 이슈를 먼저 확인합니다.</span></a><a class="quick-link-card" href="{prefix}products/veridion/plans/index.html"><strong>가격</strong><span>플랜과 범위를 비교합니다.</span></a><a class="quick-link-card" href="{prefix}products/veridion/board/index.html"><strong>자료실</strong><span>도움 글을 읽어봅니다.</span></a></div><div class="actions"><a class="button" href="{prefix}products/veridion/demo/index.html">무료 데모</a><a class="button secondary" href="{prefix}products/veridion/plans/index.html">가격 보기</a><a class="button ghost" href="{prefix}docs/veridion/index.html">문서</a></div></article></div></div></section>
      <section class="section compact"><div class="container"><div class="section-head"><div><h2>연결 모듈 허브</h2></div><p>추후 결합 예정 모듈은 별도 허브에서 관리합니다.</p></div><div class="story-grid" id="module-matrix">{module_cards}</div><div class="small-actions" style="margin-top:18px"><a href="{prefix}modules/index.html">연결 모듈 전체 보기</a></div></div></section>
    </main>
    ''')
    return doc(brand, f'제품 | {brand["name"]}', 'Veridion 공개 제품 허브', 'products', body, depth=1, page_key='products', page_path='/products/index.html')

def build_engine_page(data: dict) -> str:
    brand = data['brand']
    prefix = rel_prefix(1)
    body = dedent(f'''
    <main>
      <section class="section">
        <div class="container page-hero">
          <div class="card strong">
            <div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>공통 엔진</span></div>
            <span class="kicker">Common engine</span>
            <h1>공통 엔진 하나로 신청부터 결과 확인까지 같은 기준으로 이어집니다</h1>
            <p class="lead">제품이 늘어나도 신청, 결제, 제공, 포털, 관리자 흐름이 흔들리지 않도록 공통 엔진이 기록과 운영을 맡습니다. 고객은 필요한 제품만 편하게 보고, 운영자는 같은 기준으로 상태와 자동화를 관리할 수 있습니다.</p>
            <div class="actions"><a class="button" href="{prefix}products/index.html">제품 모듈 보기</a><a class="button secondary" href="{prefix}pricing/index.html">가격 기준</a><a class="button ghost" href="{prefix}admin/index.html">관리자 허브</a></div>
          </div>
          <div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">엔진 계층</span><h3 style="font-size:1.72rem;margin:16px 0 10px">제품이 달라도 기본 경험은 같게 유지합니다</h3><p>{escape(data['engine'].get('headline', ''))}</p><div class="inline-list">{engine_layers_markup(data)}</div></div>
        </div>
      </section>
      <section class="section compact"><div class="container accordion-stack"><details class="fold-card" open><summary><strong>핵심 엔진 흐름</strong><span>문제 선택부터 관리자 허브까지 같은 기록선으로 이어집니다.</span></summary><div><div class="timeline">{timeline_markup(data)}</div></div></details><details class="fold-card"><summary><strong>왜 공통 엔진으로 운영하는가</strong><span>가격, 기록, 포털, 상태 변경을 같은 기준으로 관리합니다.</span></summary><div><div class="support-grid">{support_cards_markup()}</div></div></details></div></section>
      <section class="section compact"><div class="container"><div class="section-head"><div><h2>제품 품질·성능 구조 비교</h2></div><p>네 제품 모두 다른 문제를 해결하지만, 입력 기준·품질 게이트·실패 대응을 같은 방식으로 설계해 운영 부담을 낮추고 판단 속도를 높였습니다.</p></div><div class="product-grid" id="product-grid">{architecture_matrix_markup(data['products'], prefix)}</div></div></section>
    </main>
    ''')
    return doc(brand, f'공통 엔진 | {brand["name"]}', '신청부터 제공까지 묶는 공용 엔진 소개', 'engine', body, depth=1, page_key='engine', page_path='/engine/index.html')

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
            <h1>어떤 제품이냐보다, 지금 가장 시급한 장면부터 고를 수 있게 만들었습니다</h1>
            <p class="lead">처음 오셨다면 제품 이름을 모두 기억하실 필요가 없습니다. 지금 가장 답답한 장면이 전환인지, 서류와 안내인지, 지원사업 준비인지, 최종본 정리인지부터 고르시면 그다음 경로를 더 짧고 분명하게 안내해 드립니다.</p>
            <div class="actions"><a class="button" href="{prefix}products/index.html">전체 제품 보기</a><a class="button secondary" href="{prefix}demo/index.html">공통 데모</a><a class="button ghost" href="{prefix}contact/index.html">예외 문의</a></div>
          </div>
          <div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">추천 경로</span><h3 style="font-size:1.72rem;margin:16px 0 10px">처음에는 가볍게, 결정은 충분히</h3><p>먼저 문제를 고르고, 30초 미리보기로 방향을 본 뒤, 마음이 맞을 때만 데모와 플랜을 확인하실 수 있게 설계했습니다. 서두르지 않아도 이해가 빨라지는 흐름을 목표로 했습니다.</p></div>
        </div>
      </section>
      <section class="section compact"><div class="container"><div class="story-grid">{product_fit_cards_markup(products, prefix)}</div></div></section>
    </main>
    ''')
    return doc(brand, f'문제별 시작 | {brand["name"]}', '문제 기준으로 제품을 고르는 안내', 'solutions', body, depth=1, page_key='solutions', page_path='/solutions/index.html')

def build_product_page(data: dict, product: dict) -> str:
    brand = data['brand']
    prefix = rel_prefix(2)
    selected_plan = next((plan['name'] for plan in product.get('plans', []) if plan.get('recommended')), (product.get('plans') or [{}])[0].get('name', 'Starter'))
    quick_links = [
        ('즉시 데모', f'{prefix}products/{product["key"]}/demo/index.html', '가볍게 미리보고 방향을 확인합니다'),
        ('플랜', f'{prefix}products/{product["key"]}/plans/index.html', '가격과 포함 범위를 차분히 비교합니다'),
        ('전달물', f'{prefix}products/{product["key"]}/delivery/index.html', '무엇을 받게 되는지 먼저 확인합니다'),
        ('FAQ', f'{prefix}products/{product["key"]}/faq/index.html', '많이 묻는 내용을 먼저 살펴봅니다'),
        ('자료실', f'{prefix}products/{product["key"]}/board/index.html', '도움 되는 글과 자료를 확인합니다'),
        ('문서', f'{prefix}docs/{product["key"]}/index.html', '준비물과 기준을 정리해서 봅니다'),
    ]
    quick_markup = ''.join(f'<a class="quick-link-card" href="{href}"><strong>{label}</strong><span>{body}</span></a>' for label, href, body in quick_links)
    fit_markup = product_value_list(product, 'fit_for') or product_value_list(product, 'value_points')
    not_for_markup = ''.join(f'<li>{escape(item)}</li>' for item in product.get('not_for', [])) or '<li>범위가 크게 다른 경우는 예외 문의에서 더 정확히 안내해 드립니다.</li>'
    sample_markup = ''.join(f'<li>{escape(item)}</li>' for item in product.get('samples', [])) or product_value_list(product, 'outputs')
    outputs_markup = product_value_list(product, 'outputs')
    workflow_preview = ' → '.join(product.get('workflow', [])[:2]) if product.get('workflow') else '준비 확인 → 실행 → 결과 확인'
    body = dedent(f'''    <main>
      <section class="section">
        <div class="container page-hero">
          <div class="card strong">
            <div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><a href="{prefix}products/index.html">제품</a><span class="sep">/</span><span>{escape(product['name'])}</span></div>
            <span class="tag theme-chip">{escape(product['label'])}</span>
            <h1>{escape(product['name'])}</h1>
            <p class="lead">{escape(product['headline'])}</p>
            <p>{escape(product['summary'])}</p>
            <div class="actions" id="product-actions">
              <a class="button" href="{prefix}products/{escape(product['key'])}/demo/index.html">즉시 데모</a>
              <a class="button secondary" href="{prefix}products/{escape(product['key'])}/plans/index.html">플랜 보기</a>
              <a class="button ghost" href="{prefix}products/{escape(product['key'])}/delivery/index.html">전달물 보기</a>
            </div>
          </div>
          <div class="card theme-panel">
            <span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">추천 시작점</span>
            <h3 style="font-size:1.75rem;margin:16px 0 10px">먼저 30초 데모로 결과 방향을 확인해 보세요</h3>
            <p style="margin-bottom:16px">처음에는 많이 입력하지 않으셔도 됩니다. 가장 가까운 시나리오를 눌러 보고, 느낌이 맞을 때만 데모 저장이나 플랜 비교로 넘어가시면 됩니다.</p>
            <div class="quick-demo-grid">{''.join(f'<button class="quick-demo-button" type="button" data-quick-demo="{escape(product["key"])}" data-quick-scenario="{idx}">{escape((item if isinstance(item, str) else str(item))[:30])}</button>' for idx, item in enumerate(product.get('demo_scenarios', [])[:4]))}</div>
            <div class="result-box" id="quick-demo-result" role="status" aria-live="polite"></div>
            <div class="notice notice-light"><strong>추천 플랜</strong><br><span>{escape(selected_plan)} · {' · '.join(f"{plan['name']} {plan['price']}" for plan in product.get('plans', []))}</span></div>
          </div>
        </div>
      </section>
      <section class="section compact">
        <div class="container">
          <div class="section-head"><div><h2>이 제품에서 바로 확인할 수 있는 핵심 메뉴</h2></div><p>개요 페이지는 제품 적합성 판단에 집중하고, 실제 데모와 가격 비교는 각 세부 화면에서 이어지도록 분리했습니다.</p></div>
          <div class="product-module-grid" id="product-module-grid">{quick_markup}</div>
          <section class="sr-only" aria-hidden="true" style="position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden">
            <div id="product-demo-shell"></div>
            <form id="product-checkout-form" class="stack-form">
              <input type="hidden" name="product" value="{escape(product['key'])}">
              <input type="hidden" name="plan" value="Starter">
              <input type="hidden" name="billing" value="one-time">
              <input type="hidden" name="paymentMethod" value="toss">
              <input type="hidden" name="company" value="Compat Surface">
              <input type="hidden" name="name" value="Compat Surface">
              <input type="hidden" name="email" value="compat@example.com">
              <input type="hidden" name="phone" value="">
              <input type="hidden" name="link" value="">
              <input type="hidden" name="urgency" value="">
              <input type="hidden" name="note" value="">
              <label><input type="checkbox" name="privacyConsent" value="yes" checked data-consent-required="1"><span>compat consent</span></label>
              <small data-consent-message>compat consent</small>
              <button type="submit">compat</button>
            </form>
            <div id="product-checkout-plan-summary"></div>
            <div id="product-checkout-result"></div>
          </section>
        </div>
      </section>
      <section class="section compact">
        <div class="container accordion-stack" id="product-overview-folds">
          <details class="fold-card" open><summary><strong>이 제품이 잘 맞는 상황</strong><span>{escape(product['problem'])}</span></summary><div><p>아래 항목과 현재 상황이 비슷하다면, 이 제품으로 시작하셨을 때 가장 빠르게 효과를 체감하실 가능성이 높습니다.</p><ul class="clean">{fit_markup}</ul></div></details>
          <details class="fold-card"><summary><strong>이 경우에는 다른 경로가 더 적합할 수 있습니다</strong><span>범위를 먼저 걸러 불필요한 문의와 재작업을 줄입니다.</span></summary><div><p>모든 문제를 한 제품으로 해결하는 것보다, 지금 상황에 맞는 경로를 고르는 것이 더 중요합니다. 아래 경우에 해당하면 다른 제품이나 예외 문의가 더 적합할 수 있습니다.</p><ul class="clean">{not_for_markup}</ul></div></details>
          <details class="fold-card"><summary><strong>이 제품이 실제로 도움이 되는 이유</strong><span>접힌 상태에서는 짧게, 펼치면 실제 이점까지 자세히 볼 수 있습니다.</span></summary><div><p id="product-pricing-basis">{escape(product.get('pricing_basis',''))}</p><ul class="clean">{product_value_list(product, 'value_points')}</ul></div></details>
          <details class="fold-card"><summary><strong>품질과 안정성을 위해 어떤 구조로 만들었는지</strong><span>{escape((product.get('architecture') or {}).get('summary', '입력 기준부터 품질 게이트까지 한 번에 봅니다.'))}</span></summary><div>{architecture_sections_markup(product)}</div></details>
          <details class="fold-card"><summary><strong>품질과 운영 안정성 핵심만 먼저 보면</strong><span>입력, 검수, 실패 대응을 얼마나 촘촘하게 잡았는지 짧게 확인할 수 있습니다.</span></summary><div><p>처음에는 긴 설명보다 구조적 안정성이 어느 정도인지부터 확인하시는 편이 빠릅니다. 아래 카드는 이 제품이 얼마나 적은 입력으로 시작하고, 얼마나 분명한 검수 기준과 예외 대응을 두는지 요약해 보여줍니다.</p><div class="admin-grid">{architecture_scorecards_markup(product)}</div><div class="story-grid" style="margin-top:16px">{architecture_focus_markup(product)}</div></div></details>
          <details class="fold-card"><summary><strong>결제 후 무엇을 받게 되는지</strong><span>{escape(workflow_preview)}</span></summary><div><p>진행이 시작되면 아래 흐름에 맞춰 준비와 실행, 결과 확인이 이어집니다. 처음 진행하시는 분도 중간에 막히지 않도록 실제 작업 순서를 함께 보여드립니다.</p><ol class="flow-list" id="product-workflow">{product_workflow_markup(product)}</ol><div class="module-layout" style="margin-top:16px"><article class="card"><span class="tag theme-chip">받는 결과</span><ul class="clean" id="product-outputs">{outputs_markup}</ul></article><article class="card"><span class="tag theme-chip">샘플로 먼저 보기 좋은 것</span><ul class="clean">{sample_markup}</ul></article></div></div></details>
          <details class="fold-card"><summary><strong>필요할 때만 추가하면 되는 확장 서비스</strong><span>핵심 제품 하나에 꼭 필요한 것만 더해 운영 부담을 줄입니다.</span></summary><div><p>모든 기능을 한꺼번에 추가하기보다, 지금 상황에 맞는 서비스만 골라 붙이는 편이 더 효율적입니다. 아래 연결 모듈은 이 제품과 함께 검토하기 좋은 항목입니다.</p><div class="admin-grid" id="product-service-stats"></div><div class="accordion-stack" id="product-service-catalog"></div><div class="small-actions" style="margin-top:14px"><a href="{prefix}service/index.html">전체 확장 서비스 180개 보기</a></div></div></details>
          <details class="fold-card"><summary><strong>같이 비교하면 판단이 쉬운 제품</strong><span>비슷한 문제를 다른 방식으로 풀어야 할 때 비교가 쉬워집니다.</span></summary><div><div class="story-grid" id="product-related-modules"></div></div></details>
          <details class="fold-card"><summary><strong>결정 전에 많이 묻는 질문 먼저 보기</strong><span>결정 전에 가장 많이 궁금해하시는 내용을 먼저 모았습니다.</span></summary><div><div class="faq-grid" id="product-faq"></div></div></details>
        </div>
      </section>
      <section class="section compact" id="board"><div class="container"><div class="section-head"><div><h2>{escape(product['name'])} 자료실 미리보기</h2></div><p>상세한 글은 자료실 전체 페이지에서 충분히 읽으실 수 있고, 이 화면에는 판단에 도움이 되는 미리보기만 남겨 과밀을 줄였습니다.</p></div><div class="board-grid" id="product-board-grid"></div><div class="small-actions" style="margin-top:18px"><a href="{prefix}products/{escape(product['key'])}/board/index.html">자료실 전체 보기</a></div><div id="product-post-detail"></div></div></section>
    </main>
    ''')
    return doc(brand, f'{product["name"]} | {brand["name"]}', product['summary'], product['theme'], body, depth=2, page_key='product', product_key=product['key'], page_path=f'/products/{product["key"]}/index.html')



def product_workflow_markup(product: dict) -> str:
    return ''.join(f'<li>{escape(item)}</li>' for item in product.get('workflow', []))
def build_board_page(data: dict) -> str:
    brand = data['brand']
    prefix = rel_prefix(1)
    body = dedent(f'''    <main>
      <section class="section">
        <div class="container page-hero">
          <div class="card strong">
            <div class="crumbs"><a href="{prefix}index.html">HOME</a><span class="sep">/</span><span>자료실</span></div>
            <span class="kicker">자료실</span>
            <h1>Veridion 자료와 글을 한곳에서 확인합니다</h1>
            <p class="lead">자료실은 구매 판단에 필요한 글과 운영 자료를 한곳에 모아둔 공개 허브입니다. 글을 읽다가 바로 제품 설명, 무료 데모, 가격 확인으로 이어질 수 있도록 설계했습니다.</p>
            <div class="actions"><a class="button secondary" href="{prefix}products/veridion/index.html">제품 안내</a><a class="button" href="{prefix}products/veridion/demo/index.html">무료 데모</a><a class="button ghost" href="{prefix}products/veridion/plans/index.html">가격 보기</a></div>
          </div>
          <div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">운영 원칙</span><h3 style="font-size:1.72rem;margin:16px 0 10px">자료실은 Veridion 중심으로 운영하고, 다른 제품 자료도 같은 구조로 확장합니다</h3><p>공개 허브에서는 Veridion 관련 글과 자료를 먼저 보여 주고, 관리자에서는 제품별 CTA 홍보 글과 자료 업로드를 함께 운영할 수 있도록 구성합니다.</p></div>
        </div>
      </section>
      <section class="section compact"><div class="container"><div class="board-grid" id="public-board-grid"></div><div id="public-post-detail"></div><div class="small-actions" style="margin-top:18px"><a href="{prefix}modules/index.html">연결 모듈 허브 보기</a></div></div></section>
    </main>
    ''')
    return doc(brand, f'자료실 | {brand["name"]}', 'Veridion 자료실', 'board', body, depth=1, page_key='board', page_path='/board/index.html')

def build_terms_page(data: dict) -> str:
    brand = data['brand']
    email = escape(brand.get('contact_email', ''))
    body = dedent(f'''    <main>
      <section class="section">
        <div class="container page-hero">
          <div class="card strong">
            <div class="crumbs"><a href="../../index.html">HOME</a><span class="sep">/</span><span>이용약관</span></div>
            <span class="kicker">Terms</span>
            <h1>서비스 이용 전에 꼭 확인하실 핵심 기준을 정리했습니다</h1>
            <p class="lead">이용약관은 공개 페이지 이용, 제품 결제, 결과 제공, 고객 포털 확인에 적용되는 기본 기준을 정리한 문서입니다.</p>
            <div class="notice policy-meta-box"><strong>시행일</strong> {POLICY_EFFECTIVE_DATE}<br><strong>최종 개정일</strong> {POLICY_UPDATED_DATE}<br><strong>문의</strong> <a href="mailto:{email}">{email}</a><br><strong>사업자등록번호</strong> {escape(((brand.get("business_info") or {}).get("registration_number") or ""))}</div>
          </div>
          <div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">적용 범위</span><h3 style="font-size:1.72rem;margin:16px 0 10px">공개 페이지, 제품 설명, 데모, 결제, 결과 제공, 포털 확인</h3><p>이 약관은 NV0 웹사이트와 제품별 결제·결과 제공·포털 확인 흐름 전체에 적용됩니다.</p></div>
        </div>
      </section>
      <section class="section compact"><div class="container"><div class="story-grid">
        <article class="story-card"><span class="tag">1</span><h3>서비스 성격</h3><p>NV0는 공용 엔진 위에 제품 모듈을 결합해 운영자료실, 설명, 데모 시연, 결제, 발행 제공을 연결하는 서비스형 운영 구조를 제공합니다.</p></article>
        <article class="story-card"><span class="tag">2</span><h3>결제와 자동 제공</h3><p>플랜, 범위, 결제 방식은 각 제품 페이지와 결제 화면에 표시된 조건을 기준으로 합니다. Toss 결제는 외부 결제창으로 이어지며, 기업 정산이 필요할 때에도 동일한 결과 기준을 맞춘 뒤 별도 문의로 이어집니다.</p></article>
        <article class="story-card"><span class="tag">3</span><h3>결과 자료 제공</h3><p>결제 완료 또는 별도 범위 확정 후에는 제품 특성에 맞는 발행 제공 자료, 공개 글, 고객 포털 확인 정보가 제공될 수 있습니다.</p></article>
        <article class="story-card"><span class="tag">4</span><h3>고객 책임</h3><p>고객은 결제 또는 문의 과정에서 제공하는 회사 정보, 이메일, 참고 자료가 자신에게 제공 권한이 있는 내용인지 확인해야 합니다.</p></article>
        <article class="story-card"><span class="tag">5</span><h3>콘텐츠와 자료</h3><p>제품 결과물과 공개 글, 체크리스트는 입력된 정보와 제품 규칙을 바탕으로 생성되며, 최종 적용 전에 고객이 검토해야 합니다.</p></article>
        <article class="story-card"><span class="tag">6</span><h3>환불과 예외</h3><p>환불, 일정, 세금계산서, 예외 범위는 결제 전 정책 및 문의 절차를 따릅니다. 맞춤형 결과물이 일부 제공된 경우에는 진행분 정산 기준이 적용될 수 있습니다.</p></article>
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
            <h1>요청하신 페이지를 찾을 수 없습니다</h1>
            <p class="lead">주소가 바뀌었거나 링크가 이동했을 수 있습니다. 아래 경로에서 제품, 가격, 문서, 포털을 다시 확인하실 수 있습니다.</p>
            <div class="actions">
              <a class="button" href="./index.html">홈으로 이동</a>
              <a class="button secondary" href="./products/index.html">제품 보기</a>
              <a class="button ghost" href="./board/index.html">자료실 보기</a>
            </div>
          </div>
          <div class="card accent"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">바로 찾기</span><h3 style="font-size:1.72rem;margin:16px 0 10px">가격, 문서, 포털로 바로 이동하실 수 있습니다</h3><p>아직 검토 중이라면 가격과 문서부터, 이미 진행하셨다면 고객 포털에서 제공 상태부터 확인하시면 가장 빠릅니다.</p><div class="small-actions"><a href="./pricing/index.html">가격</a><a href="./docs/index.html">문서</a><a href="./portal/index.html">포털</a></div></div>
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
        '/', '/company/', '/engine/', '/products/', '/solutions/', '/pricing/', '/demo/', '/checkout/', '/board/', '/docs/', '/cases/', '/faq/', '/guides/', '/resources/', '/service/', '/portal/', '/contact/', '/onboarding/', '/legal/privacy/', '/legal/refund/', '/legal/terms/', '/legal/cookies/',
    ]
    for product in data.get('products', []):
        key = product['key']
        paths.extend([f'/products/{key}/', f'/products/{key}/demo/', f'/products/{key}/plans/', f'/products/{key}/delivery/', f'/products/{key}/faq/', f'/products/{key}/board/', f'/docs/{key}/'])
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
    return f'Contact: mailto:{email}\nPolicy: {domain}/legal/privacy/\nCanonical: {domain}/.well-known/security.txt\nExpires: 2027-04-15T00:00:00.000Z\nPreferred-Languages: ko, en\n'


def favicon_svg(data: dict) -> str:
    label = escape(data['brand'].get('name', 'NV0')[:2])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="{label}"><rect width="64" height="64" rx="16" fill="#0f172a"/><text x="50%" y="56%" dominant-baseline="middle" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="26" font-weight="700" fill="#e2e8f0">N0</text></svg>'''

def favicon_ico_bytes() -> bytes:
    payload = 'AAABAAMAEBAAAAAAIACUAQAANgAAABgYAAAAACAAKQIAAMoBAAAgIAAAAAAgAFcBAADzAwAAiVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAABN0lEQVR4nM2TMU7DQBBF39k7QcQMCKk4A4kThKkoOAElJSUVR0Ah0dFyAAJCB0hD8Q6QhFFR0QFIC4QSWYl3d7NrbMmy0g4vWbP7vXl7C8D0uL29JQwDx3F49Lq6OvA8f5ZN0zQxpwk8zwvXdV1zHMepjuO46QY4juNhWZaN+76f5DgOALIsq6qqRh3HccYYxpgxDEO8p6cnQghCCLAsa2tr0zRNhBCG4biu2Wy2XC6n1+uFv78/AKCqKkVRxBiD53nM53NGo1EAcDweM45j3/cpFAr0er1kMhmappHruq4QghCC67q4rguA53mSJEmv14PneRRFkWQyGa1WiyzL0ul0aJpGURQAwHUdAKAoiqIoihBCmM1m2WyWcRxHlmUZx3Fks9mk02mYzWaC4ziKouD7Pi6XC5IkEQA8Ho8sy5LJZAKA4zhM08Tj8UjTNOm6jlKpRBAEAJqmQVEU2WyWwWAAANM0GQwGr9crJElCUZQsywIA4jiOqqp6vV6C4zhVVdFoNJKWZWq1Wi6XQ6/XA2Cz2TiO4/1+J7vdLh6Px3EcR57n+XweRVEwGAyA4zgcDoc8z/O4rsvz+TTvPw8AAH8ALbPNTC0JmQ4AAAAASUVORK5CYII='
    return base64.b64decode(payload)


def apply_page_overrides(dist: Path, data: dict):
    return None
