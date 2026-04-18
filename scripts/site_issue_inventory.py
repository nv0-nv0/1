from __future__ import annotations

import json
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
DATA = json.loads((ROOT / 'src' / 'data' / 'site.json').read_text(encoding='utf-8'))


def load(rel: str) -> BeautifulSoup:
    return BeautifulSoup((DIST / rel).read_text(encoding='utf-8'), 'html.parser')


def has_text(soup: BeautifulSoup, selector: str) -> bool:
    el = soup.select_one(selector)
    return bool(el and el.get_text(' ', strip=True))


def count_product_static_issues() -> list[str]:
    issues = []
    for product in DATA['products']:
        rel = f"products/{product['key']}/index.html"
        soup = load(rel)
        checks = {
            'hero_h1': has_text(soup, 'h1'),
            'hero_lead': has_text(soup, '.lead'),
            'actions': len(soup.select('#product-actions a')) >= 2,
            'overview': len(soup.select('#product-overview-folds details')) >= 5 or len(soup.select('#intro article, #product-values li')) >= 3,
            'workflow': len(soup.select('#product-workflow li')) >= 2,
            'outputs': len(soup.select('#product-outputs li')) >= 2,
        }
        for key, ok in checks.items():
            if not ok:
                issues.append(f'{rel}:{key}')
        placeholder_count = len(soup.select('[data-fill]'))
        if placeholder_count:
            issues.append(f'{rel}:unresolved_data_fill:{placeholder_count}')
    return issues


def count_policy_issues() -> list[str]:
    issues = []
    privacy = load('legal/privacy/index.html').get_text(' ', strip=True)
    refund = load('legal/refund/index.html').get_text(' ', strip=True)
    cookies = load('legal/cookies/index.html').get_text(' ', strip=True)
    company = load('company/index.html').get_text(' ', strip=True)
    privacy_keywords = ['제3자', '위탁', '열람', '정정', '삭제', '처리 중단', '안전성', '권익 침해', '보관', '파기']
    refund_keywords = ['청약철회', '부분', '착수 전', '착수 후', '실비', '환급']
    cookie_keywords = ['세션 저장소', '로컬 저장소', '거부 영향', '보유 기간']
    company_keywords = ['운영명', '안내 이메일']
    for kw in privacy_keywords:
        if kw not in privacy:
            issues.append(f'privacy:missing:{kw}')
    for kw in refund_keywords:
        if kw not in refund:
            issues.append(f'refund:missing:{kw}')
    for kw in cookie_keywords:
        if kw not in cookies:
            issues.append(f'cookies:missing:{kw}')
    for kw in company_keywords:
        if kw not in company:
            issues.append(f'company:missing:{kw}')
    return issues


def count_sitewide_issues() -> list[str]:
    issues = []
    htmls = list(DIST.rglob('*.html'))
    for path in htmls:
        soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
        if not has_text(soup, 'title'):
            issues.append(f'{path.relative_to(DIST)}:missing_title')
        if not has_text(soup, 'h1') and '404' not in path.name:
            issues.append(f'{path.relative_to(DIST)}:missing_h1')
    return issues


def main() -> None:
    product_issues = count_product_static_issues()
    policy_issues = count_policy_issues()
    sitewide_issues = count_sitewide_issues()
    all_issues = product_issues + policy_issues + sitewide_issues
    summary = {
        'total_detectable_issues': len(all_issues),
        'product_static_issues': len(product_issues),
        'policy_issues': len(policy_issues),
        'sitewide_issues': len(sitewide_issues),
        'issues': all_issues,
    }
    out_json = ROOT / 'SITE_ISSUE_INVENTORY.json'
    out_md = ROOT / 'SITE_ISSUE_INVENTORY_KO.md'
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = [
        '# NV0 감지 가능 문제 인벤토리',
        '',
        f"- 감지 범위 기준 총 문제 수: {len(all_issues)}",
        f"- 제품 정적 렌더링 문제: {len(product_issues)}",
        f"- 정책/고지 문제: {len(policy_issues)}",
        f"- 사이트 공통 문제: {len(sitewide_issues)}",
        '',
        '## 세부 목록',
    ]
    lines.extend(f'- {item}' for item in all_issues)
    out_md.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(out_json)
    print(out_md)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
