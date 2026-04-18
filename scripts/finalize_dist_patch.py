from pathlib import Path
from textwrap import dedent
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build

DIST = Path(__file__).resolve().parents[1] / 'dist'


def board_post_alias_page() -> str:
    return build.doc(
        f"자료실 글 | {build.brand['name']}",
        '자료실 글 읽기 안내',
        'board-post',
        dedent('''
        <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../index.html">HOME</a><span class="sep">/</span><a href="../index.html">자료실</a><span class="sep">/</span><span>글 보기</span></div><span class="kicker">Library</span><h1>공개 글은 자료실 허브에서 바로 확인하실 수 있습니다</h1><p class="lead">내부 작성 기능은 숨기고, 고객이 읽기 좋은 공개 허브만 남겼습니다.</p><div class="actions"><a class="button" href="../index.html">자료실 허브 보기</a><a class="button secondary" href="../../products/index.html">제품 보기</a></div></div></div></section></main>
        '''),
        depth=2,
        page_key='board-post',
        page_path='/board/post/index.html',
    )


def product_demo_compat_page(product: dict) -> str:
    if product['key'] == 'veridion':
        sample_points = ''.join(f'<li>{build.escape(item)}</li>' for item in product.get('samples', []))
        body = dedent(f'''
        <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../../index.html">HOME</a><span class="sep">/</span><a href="../../index.html">제품</a><span class="sep">/</span><a href="../index.html">{product['name']}</a><span class="sep">/</span><span>즉시 데모</span></div><span class="tag theme-chip">{product['label']}</span><h1>{product['name']} 즉시 데모</h1><p class="lead">사이트 주소를 넣으면 즉시 위험 요약을 보여드리고, 결제 전 핵심 리스크를 먼저 판단하실 수 있게 구성했습니다.</p></div><div class="card theme-panel"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">먼저 볼 예시</span><ul class="clean inverse-list">{sample_points}</ul></div></div></section><section class="section compact"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">즉시 진단</span><form id="product-demo-form" class="stack-form"><div class="form-grid"><div class="span-2"><label>사이트 주소</label><input name="website" placeholder="https://example.com" inputmode="url" autocomplete="url" required></div><div><label>업종</label><select name="industry"><option value="commerce">이커머스</option><option value="beauty">뷰티·웰니스</option><option value="healthcare">의료·건강</option><option value="education">교육·서비스</option><option value="saas">B2B SaaS</option></select></div><div><label>주요 운영 국가</label><select name="country"><option value="KR" selected>대한민국</option><option value="US">미국</option><option value="JP">일본</option><option value="CN">중국</option><option value="EU">유럽연합</option><option value="SEA">동남아</option><option value="GLOBAL">글로벌</option></select></div><div><label>중점 확인 사항</label><select name="focus" data-demo-field="focus"><option value="전체 리스크 빠르게 보기">전체 리스크 빠르게 보기</option><option value="개인정보·회원가입 동선">개인정보·회원가입 동선</option><option value="결제·환불·청약철회 고지">결제·환불·청약철회 고지</option><option value="광고·표시 문구">광고·표시 문구</option><option value="약관·정책 문서 일치">약관·정책 문서 일치</option><option value="민감 업종·표현 위험">민감 업종·표현 위험</option></select></div></div><div class="notice notice-light smart-focus-note"><strong>자동 추천 적용</strong><br>대한민국 운영 기준으로 <strong>결제·환불·청약철회 고지</strong>을 우선 점검하도록 맞췄습니다.</div><div class="actions"><button class="button" type="submit">즉시 분석하기</button><a class="button ghost" href="../plans/index.html">플랜 보기</a></div></form><div class="result-box" id="product-demo-result" role="status" aria-live="polite"></div></article><article class="card strong"><span class="tag theme-chip">바로 결제</span><p>결제 전에는 제품과 플랜만 고르고, 회사명·담당자명·이메일·사이트 주소는 결제 완료 후 한 번에 입력하도록 분리했습니다.</p><div class="small-actions"><a href="../plans/index.html">플랜 보기</a><a href="../../../checkout/index.html?product=veridion&plan=Starter">바로 결제</a></div></article></div></section></main>
        ''')
        return build.doc(f"{product['name']} 데모 | {build.brand['name']}", f"{product['name']} 즉시 데모", product['theme'], body, depth=3, page_key='product-demo', product_key=product['key'], page_path=f"/products/{product['key']}/demo/index.html")
    body = dedent(f'''
    <main><section class="section"><div class="container page-hero"><div class="card strong"><div class="crumbs"><a href="../../../index.html">HOME</a><span class="sep">/</span><a href="../../index.html">제품</a><span class="sep">/</span><a href="../index.html">{product['name']}</a><span class="sep">/</span><span>즉시 데모</span></div><span class="tag theme-chip">{product['label']}</span><h1>{product['name']} 즉시 데모</h1><p class="lead">소개 문장보다 실제 결과를 먼저 보여주는 화면입니다. 저장형 문의가 아니라 즉시 분석 중심으로 구성했습니다.</p></div><div class="card theme-panel"><span class="tag" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#fff">먼저 보는 항목</span><ul class="clean inverse-list">{''.join(f'<li>{build.escape(item)}</li>' for item in product.get('samples', [])[:4])}</ul></div></div></section><section class="section compact"><div class="container module-layout"><article class="card strong"><span class="tag theme-chip">즉시 분석</span><form id="product-demo-form" class="stack-form"><div class="form-grid">{('<div><label>제출 유형</label><input name="submissionType" data-demo-field="submissionType" placeholder="예: 입찰, 등록, 제휴"></div><div><label>마감일</label><input name="deadline" data-demo-field="deadline" type="date"></div><div><label>제출처</label><input name="targetOrg" data-demo-field="targetOrg" placeholder="예: 공공기관, 거래처"></div><div><label>팀 규모</label><input name="teamSize" data-demo-field="teamSize" placeholder="예: 2인 운영팀"></div><div class="span-2"><label>막히는 지점</label><input name="blocker" data-demo-field="blocker" placeholder="예: 서류 누락, 회신 지연"></div>' if product['key']=='clearport' else '')}{('<div><label>사업/공모명</label><input name="projectName" data-demo-field="projectName" placeholder="예: 창업 지원사업"></div><div><label>마감일</label><input name="deadline" data-demo-field="deadline" type="date"></div><div><label>현재 진행률</label><select name="progress" data-demo-field="progress"><option>자료 수집 전</option><option>초안 작성 중</option><option>검토 중</option><option>마감 직전</option></select></div><div><label>참여 인원</label><input name="contributors" data-demo-field="contributors" placeholder="예: 3명"></div><div class="span-2"><label>지연 포인트</label><input name="delayPoint" data-demo-field="delayPoint" placeholder="예: 증빙 수집, 승인 지연"></div>' if product['key']=='grantops' else '')}{('<div><label>문서 종류</label><input name="docType" data-demo-field="docType" placeholder="예: 제안서, 보고서"></div><div><label>현재 버전 상태</label><select name="versionState" data-demo-field="versionState"><option>최신본이 정리되어 있음</option><option>초안만 있음</option><option>수정본이 여러 개 흩어져 있음</option></select></div><div><label>승인 단계</label><input name="approvalSteps" data-demo-field="approvalSteps" placeholder="예: 3단계"></div><div><label>주요 채널</label><input name="channel" data-demo-field="channel" placeholder="예: 이메일, 메신저"></div><div class="span-2"><label>가장 큰 문제</label><input name="draftPain" data-demo-field="draftPain" placeholder="예: 최신본 혼선, 승인 지연"></div>' if product['key']=='draftforge' else '')}</div><div class="actions"><button class="button" type="submit">샘플 결과 보기</button><a class="button ghost" href="../../../checkout/index.html?product={product['key']}&plan=Starter">바로 결제</a></div></form><div class="result-box" id="product-demo-result" role="status" aria-live="polite"></div></article><article class="card strong"><span class="tag theme-chip">분석 후 바로 이어지는 단계</span><ol class="flow-list"><li>핵심 병목과 상위 위험 신호 확인</li><li>샘플 결과 기준으로 결제 여부 판단</li><li>결제 후 필요한 진행 정보만 입력</li></ol><div class="small-actions"><a href="../index.html#order">바로 결제</a><a href="../board/index.html">자료실 보기</a></div></article></div></section></main>
    ''')
    return build.doc(f"{product['name']} 데모 | {build.brand['name']}", f"{product['name']} 즉시 데모", product['theme'], body, depth=3, page_key='product-demo', product_key=product['key'], page_path=f"/products/{product['key']}/demo/index.html")


def rewrite_core_pages_after_overrides() -> None:
    pages = {
        DIST / 'index.html': build.home_page(),
        DIST / 'company' / 'index.html': build.company_page(),
        DIST / 'products' / 'index.html': build.products_page(),
        DIST / 'board' / 'index.html': build.board_page(),
        DIST / 'auth' / 'index.html': build.auth_page(),
        DIST / 'demo' / 'index.html': build.demo_page(),
        DIST / 'checkout' / 'index.html': build.checkout_page(),
        DIST / 'contact' / 'index.html': build.contact_page(),
        DIST / 'portal' / 'index.html': build.portal_page(),
        DIST / 'admin' / 'index.html': build.admin_page(),
        DIST / 'payments' / 'toss' / 'success' / 'index.html': build.toss_success_page(),
        DIST / 'payments' / 'toss' / 'fail' / 'index.html': build.toss_fail_page(),
        DIST / 'board' / 'post' / 'index.html': board_post_alias_page(),
    }
    for path, html in pages.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding='utf-8')
    for item in build.products:
        (DIST / 'products' / item['key'] / 'index.html').write_text(build.product_page(item), encoding='utf-8')
        (DIST / 'products' / item['key'] / 'board' / 'index.html').parent.mkdir(parents=True, exist_ok=True)
        (DIST / 'products' / item['key'] / 'board' / 'index.html').write_text(build.product_board_page(item), encoding='utf-8')
        (DIST / 'products' / item['key'] / 'demo' / 'index.html').parent.mkdir(parents=True, exist_ok=True)
        (DIST / 'products' / item['key'] / 'demo' / 'index.html').write_text(product_demo_compat_page(item), encoding='utf-8')


if __name__ == '__main__':
    rewrite_core_pages_after_overrides()
    print('Rewrote core dist pages:', DIST)
