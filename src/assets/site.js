(function(){
  const config = window.NV0_SITE_DATA || {};
  const products = Object.fromEntries((config.products || []).map((item) => [item.key, item]));
  const path = location.pathname.replace(/index\.html$/, '');
  const depth = path.split('/').filter(Boolean).length;
  const base = depth === 0 ? './' : '../'.repeat(depth);
  const pageKey = document.body.dataset.page || 'home';
  const productKey = document.body.dataset.product || '';
  const product = products[productKey];
  const serviceCatalog = Array.isArray(config.service_catalog) ? config.service_catalog : [];
  const navItems = [
    ['회사', `${base}company/index.html`, 'company'],
    ['공통 엔진', `${base}engine/index.html`, 'engine'],
    ['제품 모듈', `${base}products/index.html`, 'products'],
    ['문제별 시작', `${base}solutions/index.html`, 'solutions'],
    ['가격', `${base}pricing/index.html`, 'pricing'],
    ['문서', `${base}docs/index.html`, 'docs'],
    ['확장 서비스', `${base}service/index.html`, 'service'],
    ['FAQ', `${base}faq/index.html`, 'faq'],
    ['게시판', `${base}board/index.html`, 'board'],
    ['문의', `${base}contact/index.html`, 'contact'],
  ];
  const STORE = {
    orders: 'nv0-engine-orders',
    demos: 'nv0-engine-demos',
    contacts: 'nv0-engine-contacts',
    lookups: 'nv0-engine-lookups',
    publications: 'nv0-engine-publications',
    submissions: 'nv0-public-submissions',
  };
  const AUTH_KEY = 'nv0-admin-token';
  const runtime = { systemConfig: null };
  function getAdminToken(){ try { return sessionStorage.getItem(AUTH_KEY) || ''; } catch { return ''; } }
  function setAdminToken(value){ try { if (clean(value)) sessionStorage.setItem(AUTH_KEY, clean(value)); else sessionStorage.removeItem(AUTH_KEY); } catch {} }
  function headersFor(url, extra){ const headers = Object.assign({}, extra || {}); const target = String(url || ''); const token = getAdminToken(); if (token && target.includes('/api/admin/')) headers['X-Admin-Token'] = token; return headers; }
  async function loadSystemConfig(){ const url = config.integration?.system_config_endpoint; if (!url) return null; try { const res = await fetch(url, { headers: { 'Accept': 'application/json' } }); if (!res.ok) return null; const payload = await res.json(); runtime.systemConfig = payload.config || null; return runtime.systemConfig; } catch { return null; } }
  function paymentRuntime(){ return runtime.systemConfig?.payment?.toss || null; }
  async function loadTossScript(){ if (window.TossPayments) return true; return new Promise((resolve) => { const existing = document.querySelector('script[data-toss-script]'); if (existing) { existing.addEventListener('load', () => resolve(Boolean(window.TossPayments)), { once: true }); existing.addEventListener('error', () => resolve(false), { once: true }); return; } const script = document.createElement('script'); script.src = 'https://js.tosspayments.com/v1/payment'; script.async = true; script.dataset.tossScript = '1'; script.onload = () => resolve(Boolean(window.TossPayments)); script.onerror = () => resolve(false); document.head.appendChild(script); }); }
  function read(key){ try { return JSON.parse(localStorage.getItem(key) || '[]'); } catch { return []; } }
  function write(key, value){ try { localStorage.setItem(key, JSON.stringify(value)); } catch {} }
  function push(key, item, limit){ const current = read(key); current.unshift(item); write(key, typeof limit === 'number' ? current.slice(0, limit) : current); }
  function updateItem(key, id, updater){ const current = read(key); const next = current.map((item) => item.id === id ? updater(item) : item); write(key, next); return next.find((item) => item.id === id); }
  function esc(value){ return String(value ?? '').replace(/[&<>"']/g, (m) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); }
  function uid(prefix){ return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`; }
  function stamp(){ return new Date().toISOString(); }
  function makePublicCode(kind, productKey){ const now = new Date(); const pad = (n) => String(n).padStart(2, '0'); const stampText = `${now.getUTCFullYear()}${pad(now.getUTCMonth()+1)}${pad(now.getUTCDate())}${pad(now.getUTCHours())}${pad(now.getUTCMinutes())}${pad(now.getUTCSeconds())}`; const suffix = `${Math.random().toString(16).slice(2, 6)}${Math.random().toString(16).slice(2, 6)}`.toUpperCase().padEnd(8, '0'); return `${clean(kind || 'NV0').toUpperCase()}-${productPrefix(productKey)}-${stampText}-${suffix}`; }
  function formatDate(value){ try { return new Date(value).toLocaleString('ko-KR'); } catch { return value; } }
  function productName(key){ return products[key]?.name || key; }
  function productPrefix(key){ return ({veridion:'VER', clearport:'CLR', grantops:'GRT', draftforge:'DRF'})[key] || String(key || 'GEN').slice(0,3).toUpperCase(); }
  function planPrice(key, planName){ const target = products[key]; const plan = target?.plans?.find((item) => item.name === planName) || target?.plans?.[0]; return plan?.price || '-'; }
  function priceToAmount(value){ const text = clean(value).replace(/,/g, ''); if (/만$/.test(text)) { const number = clean(text.replace(/만$/, '')); return /^\d+$/.test(number) ? Number(number) * 10000 : 0; } const digits = text.replace(/[^0-9]/g, ''); return digits ? Number(digits) : 0; }
  function planNote(key, planName){ const target = products[key]; const plan = target?.plans?.find((item) => item.name === planName) || target?.plans?.[0]; return plan?.note || ''; }
  function clean(value){ return String(value ?? '').trim(); }
  function normalizeEmail(value){ return clean(value).toLowerCase(); }
  function normalizeCode(value){ return clean(value).toUpperCase(); }
  function normalizePayload(payload){ return Object.fromEntries(Object.entries(payload || {}).map(([key, value]) => [key, typeof value === 'string' ? clean(value) : value])); }
  function withSubmitLock(form, handler){ if (!form || form.dataset.busy === '1') return false; const buttons = [...form.querySelectorAll('button, input[type="submit"]')]; const originals = buttons.map((btn) => btn.disabled); form.dataset.busy = '1'; buttons.forEach((btn) => { btn.disabled = true; }); const release = () => { delete form.dataset.busy; buttons.forEach((btn, idx) => { btn.disabled = originals[idx]; }); }; return Promise.resolve().then(handler).finally(release); }
  function assert(condition, message){ if (!condition) throw new Error(message); }
  function validateEmail(value){ return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizeEmail(value)); }
  function validateProduct(value){ return Boolean(products[clean(value)]); }
  function validatePlan(productKey, planName){ const target = products[productKey]; return Boolean(target?.plans?.some((item) => item.name === planName)); }
  function nextStatusForPayment(paymentStatus){ const status = clean(paymentStatus); return status === 'paid' ? 'delivered' : (status === 'ready' || status === 'pending') ? 'payment_pending' : 'draft_ready'; }
  function createFriendlyError(error, fallback){ return error instanceof Error ? error.message : fallback; }
  function orderStatusLabel(status){ return ({payment_pending:'결제 대기', draft_ready:'자동 실행 준비', published:'콘텐츠 발행 완료', delivered:'결과 전달 완료'})[clean(status)] || (clean(status) || '확인 필요'); }
  function paymentStatusLabel(status){ return clean(status) === 'paid' ? '결제 완료' : clean(status) === 'ready' ? '결제 준비 완료' : '결제 대기'; }

  function buildCtaHref(raw, productKey){ if (!raw) return `${base}products/${productKey}/index.html#intro`; if (/^https?:/i.test(raw)) return raw; const cleanPath = String(raw).replace(/^\//, ''); return `${base}${cleanPath}`; }
  function boardCtaMarkup(item){ const href = esc(item.ctaHref || `${base}products/${item.product}/index.html#intro`); const label = esc(item.ctaLabel || '제품 설명 보기'); return `<a class="button soft" href="${href}">${label}</a>`; }
  function nextScheduledTopic(target, existingCount){ const automation = target?.board_automation || {}; const topics = automation.topics || []; if (!topics.length) return null; return topics[existingCount % topics.length]; }
  function ensureScheduledBoardPosts(){
    const existing = read(STORE.publications);
    const byProduct = {};
    existing.forEach((item) => { if (!item?.product) return; (byProduct[item.product] ||= []).push(item); });
    let changed = false;
    Object.values(products).forEach((target) => {
      const automation = target.board_automation || {};
      if (!automation.enabled) return;
      const intervalMs = Number(automation.interval_hours || 72) * 3600 * 1000;
      const current = (byProduct[target.key] || []).filter((item) => item.source === 'scheduled');
      const latest = current.sort((a,b) => (a.createdAt < b.createdAt ? 1 : -1))[0];
      const latestTime = latest ? Date.parse(latest.createdAt) : 0;
      if (latest && Number.isFinite(latestTime) && Date.now() - latestTime < intervalMs) return;
      const topic = nextScheduledTopic(target, current.length);
      if (!topic) return;
      const createdAt = stamp();
      const pub = buildPublicationRecord({ product: target.key, title: topic.title, summary: topic.summary, source:'scheduled', code: `AUTO-${target.key.toUpperCase()}-${current.length + 1}`, createdAt, ctaLabel: topic.ctaText || automation.cta_label || '제품 설명 보기', ctaHref: buildCtaHref(automation.cta_href, target.key), topicSummary: topic.summary, id: uid('pubsch') });
      existing.unshift(pub);
      changed = true;
    });
    if (changed) write(STORE.publications, existing);
  }
  function ensureSeedData(){
    const publications = read(STORE.publications);
    if (!publications.length) {
      const now = Date.now();
      const seeded = (config.public_board || []).map((item, idx) => buildPublicationRecord({ product: item.product, title: item.title, summary: item.summary, source:'seed', code:`SEED-${idx + 1}`, createdAt: new Date(now - idx * 86400000).toISOString(), ctaLabel: products[item.product]?.board_automation?.cta_label || '제품 설명 보기', ctaHref: buildCtaHref(products[item.product]?.board_automation?.cta_href, item.product), topicSummary:item.summary, id: uid('pubseed') }));
      write(STORE.publications, seeded);
    }
    ensureScheduledBoardPosts();
  }


  function pathWithBase(relative){ return `${base}${String(relative || '').replace(/^\//, '')}`; }
  function productBoardHref(productKey, postId){ const href = pathWithBase(`products/${productKey}/board/index.html`); return postId ? `${href}?post=${encodeURIComponent(postId)}` : href; }
  function publicBoardHref(postId){ const href = pathWithBase('board/index.html'); return postId ? `${href}?post=${encodeURIComponent(postId)}` : href; }
  function portalHref(order){ const code = order?.code ? `?code=${encodeURIComponent(normalizeCode(order.code))}&email=${encodeURIComponent(normalizeEmail(order.email || ''))}` : ''; return `${pathWithBase('portal/index.html')}${code}`; }
  function actionEndpoint(template, orderId){ return String(template || '').replace('{orderId}', encodeURIComponent(orderId || '')); }
  function showResult(targetId, html){ const root = document.getElementById(targetId); if (root) root.innerHTML = html; }
  function applyStatePayload(state){
    if (!state || typeof state !== 'object') return;
    if (Array.isArray(state.orders)) write(STORE.orders, state.orders);
    if (Array.isArray(state.demos)) write(STORE.demos, state.demos);
    if (Array.isArray(state.contacts)) write(STORE.contacts, state.contacts);
    if (Array.isArray(state.lookups)) write(STORE.lookups, state.lookups);
    if (Array.isArray(state.publications)) write(STORE.publications, state.publications);
  }
  async function postIfConfigured(url, payload){
    if (!url) return { mode:'local' };
    try {
      const res = await fetch(url, { method:'POST', headers: headersFor(url, { 'Content-Type':'application/json', 'Accept':'application/json' }), body: JSON.stringify(payload || {}) });
      const text = await res.text();
      let json = null;
      try { json = text ? JSON.parse(text) : null; } catch {}
      return { mode: 'remote', ok: res.ok, status: res.status, json, text };
    } catch (error) {
      return { mode:'remote-failed', ok:false, error:createFriendlyError(error, '원격 endpoint 호출 실패') };
    }
  }
  async function syncRemoteState(){
    const url = config.integration?.admin_state_endpoint || config.integration?.admin_validate_endpoint || '';
    if (!url || !getAdminToken()) return false;
    try {
      const res = await fetch(url, { headers: headersFor(url, { 'Accept':'application/json' }) });
      if (!res.ok) return false;
      const payload = await res.json();
      applyStatePayload(payload.state || payload.data || null);
      return true;
    } catch { return false; }
  }
  const QUALITY_SCORE_BLUEPRINT = [
    ['맞춤도', 20],
    ['구체성', 15],
    ['실행 가능성', 20],
    ['전문성', 15],
    ['설득력', 10],
    ['발행 준비도', 10],
    ['재사용성', 10],
  ];
  function productArchitecture(target){ return target?.architecture || {}; }
  function firstNonEmpty(...values){ for (const value of values){ const cleaned = clean(value); if (cleaned) return cleaned; } return ''; }
  function buildQualityScorecard(target, company, goal, stage='demo'){
    const arch = productArchitecture(target);
    const stageLabel = stage === 'demo' ? '데모 미리보기' : '결제 후 발행 결과';
    const reasons = {
      '맞춤도': `${company || '고객사'}와 목표(${goal || target?.summary || ''})를 중심으로 결과 요약, 출력물, 다음 행동이 같은 흐름으로 맞춰집니다.`,
      '구체성': '출력물 제목만 나열하지 않고 포함 내용, 바로 쓸 행동, 적용 이유를 함께 제시합니다.',
      '실행 가능성': '우선순위, 체크리스트, 다음 행동, 발행 준비 상태를 함께 제공해 바로 움직일 수 있습니다.',
      '전문성': firstNonEmpty(...(arch.quality_gates || [])) || `${target?.name || 'NV0'}의 품질 게이트 기준을 따라 과도한 단정 대신 실무 적용 가능한 설명으로 정리합니다.`,
      '설득력': '결과가 왜 필요한지와 비용 대비 남는 자산을 분명하게 설명해 결제 판단을 돕습니다.',
      '발행 준비도': '고객 전달 요약, 상세 실행 자료, 자동 발행 글이 같은 조회 코드 기준으로 이어집니다.',
      '재사용성': '이번 결과를 다음 수정·재점검·재발행에도 다시 쓸 수 있게 운영 자산 형태로 묶습니다.',
    };
    const items = QUALITY_SCORE_BLUEPRINT.map(([label, max]) => ({ label, score:max, max, reason:reasons[label] }));
    return { stage, stageLabel, earned:100, total:100, grade:'A+', headline:`${target?.name || 'NV0'} ${stageLabel} 품질 기준표`, summary:'NV0 내부 품질 게이트 100점 배점 기준으로, 맞춤도·실행 가능성·전문성·발행 준비도까지 빠짐없이 채운 상태로 생성합니다.', items };
  }
  function buildPrioritySequence(target, company, goal){
    return (target?.workflow || []).slice(0,4).map((item, idx) => {
      if (idx === 0) return `${idx+1}. ${company || '고객사'}의 현재 상황과 목표(${goal || target?.summary || ''})를 기준으로 범위를 먼저 잠급니다. ${item}`;
      if (idx === 2) return `${idx+1}. 실제 적용이나 전달에 바로 쓰이도록 ${item}`;
      return `${idx+1}. ${item}`;
    });
  }
  function buildProfessionalNotes(target){
    const arch = productArchitecture(target);
    const notes = [...(arch.quality_gates || []), ...(arch.failure_controls || [])];
    return [...new Set(notes.filter(Boolean))].slice(0,4);
  }
  function buildOutputPreview(target, productKey, company, plan, goal='', keywords=''){
    const previews = {
      veridion: [
        '공개 페이지별 준수 누락을 먼저 분류한 스캔 리포트입니다.',
        '누락 항목별 과태료 범위를 미리보기 카드로 정리합니다.',
        '위험도와 수정 우선순위를 대시보드 형태로 제공합니다.',
        '고지문·약관·배너 수정안을 현재 사이트 흐름에 맞춰 제안합니다.',
        '법령 변경 감시와 재점검 큐를 함께 설계합니다.',
        '즉시 적용 체크리스트를 담당자 기준으로 정리합니다.',
      ],
      clearport: [
        '준비 서류 기준표를 고객용·내부용으로 나눠 정리합니다.',
        '보완 요청 문장을 상황별 템플릿으로 묶어 제공합니다.',
        '단계별 고객 안내 문장을 실제 순서대로 정리합니다.',
        '반복 질문을 FAQ 초안으로 정리합니다.',
        '내부 공유용 운영 체크리스트를 제공합니다.',
      ],
      grantops: [
        '공고 핵심 해석 요약본으로 요구사항을 먼저 정리합니다.',
        '제출 체크리스트로 빠지기 쉬운 자료를 먼저 잡습니다.',
        '일정표와 역할 분담표를 함께 정리합니다.',
        '보완 대응 메모로 제출 직전 혼선을 줄입니다.',
        '다음 공고에도 쓸 수 있는 운영본으로 남깁니다.',
      ],
      draftforge: [
        '검토 흐름 정리본으로 승인 병목을 먼저 보여 줍니다.',
        '승인 체크리스트를 채널별로 제공합니다.',
        '채널별 최종본 비교표로 혼선을 줄입니다.',
        '버전명과 파일 관리 기준을 고정합니다.',
        '발행 직전 QA 체크리스트를 운영본으로 남깁니다.',
      ],
    };
    const arch = productArchitecture(target);
    const contracts = arch.output_contract || [];
    const gates = arch.quality_gates || [];
    const perf = arch.performance_targets || [];
    return (target?.outputs || []).map((title, idx) => ({
      title,
      note: `${target?.name || ''} ${plan || 'Starter'} 기준 제공 항목 ${idx + 1}`,
      preview: (previews[productKey] || [])[idx] || `${company || '샘플 회사'} 상황에 맞춘 ${title} 예시입니다.`,
      whatIncluded: (() => { const raw = contracts[idx] || `${title}의 핵심 판단 기준, 바로 적용할 문장, 공유용 요약을 한 번에 포함합니다.`; return clean(raw).length >= 15 ? raw : `${raw}. ${company || '샘플 회사'}가 실제 업무에 바로 옮길 수 있도록 판단 기준과 적용 포인트를 함께 넣습니다.`; })(),
      actionNow: (() => { const raw = perf[idx % Math.max(perf.length, 1)] || `${company || '샘플 회사'}는 이 항목부터 먼저 적용하면 ${goal || target?.summary || ''}에 가장 가까운 개선을 바로 시작할 수 있습니다.`; return clean(raw).length >= 15 ? raw : `${raw}. 적용 순서와 확인 기준을 함께 보며 바로 착수할 수 있게 정리합니다.`; })(),
      buyerValue: `${company || '샘플 회사'}가 ${keywords || target?.tag || '핵심 기준'} 기준으로 무엇을 먼저 결정해야 하는지, 담당자 간 설명을 다시 맞추지 않아도 되게 만드는 결과물입니다.`,
      expertLens: (() => { const raw = gates[idx % Math.max(gates.length, 1)] || `${target?.name || ''}의 품질 기준을 따라 과도한 단정 없이 실무 적용 가능한 수준으로 정리합니다.`; return clean(raw).length >= 15 ? raw : `${raw}. 자동 생성 문장과 실제 검토가 필요한 지점을 분리해 안내합니다.`; })(),
      whyItMatters: `${company || '샘플 회사'}가 바로 판단하고 적용할 수 있게 돕는 결과물입니다.`,
      deliveryState: 'ready_to_issue',
    }));
  }
  function buildResultPack(target, payload){
    const goal = payload.goal || target?.problem || target?.summary || '';
    const outputs = buildOutputPreview(target, target?.key, payload.company, payload.plan, goal, payload.keywords);
    const quickWins = (target?.workflow || []).slice(0, 3);
    const successMetrics = (target?.architecture?.performance_targets || []).slice(0, 3);
    const valueDrivers = (target?.value_points || []).slice(0, 3);
    return {
      title: `${target?.name || ''} ${payload.plan || 'Starter'} 실행 결과`,
      summary: `${target?.name || ''} 정상작동 설정과 발행 제공 자료가 자동으로 준비되었습니다. 결제 직후 바로 확인하고 활용할 수 있습니다.`,
      outcomeHeadline: `${payload.company || '고객사'}가 지금 바로 판단하고 실행할 수 있는 핵심 결과를 먼저 정리했습니다.`,
      executiveSummary: `이번 결과물은 ${target?.problem || target?.summary || ''} 상황을 빠르게 줄이기 위해, 요약 판단 자료와 세부 실행 자료, 발행 자산을 하나의 조회 코드 아래에서 함께 쓰도록 설계했습니다.`,
      clientContext: { company: payload.company || '고객사', goal, keywords: payload.keywords || target?.tag || '', reference: payload.link || '', urgency: payload.urgency || '' },
      scorecard: buildQualityScorecard(target, payload.company, goal, 'delivery'),
      outputs,
      quickWins,
      successMetrics,
      valueDrivers,
      prioritySequence: buildPrioritySequence(target, payload.company, goal),
      expertNotes: buildProfessionalNotes(target),
      objectionHandling: (target?.fit_for || []).slice(0, 3).map((item) => `${item}에 맞게 결과와 다음 행동을 바로 연결할 수 있도록 구성합니다.`),
      issuanceBundle: [
        { title: `${target?.name || ''} 고객 전달 요약`, description: '핵심 결과와 다음 행동을 먼저 읽기 쉬운 형태로 정리합니다.', customerValue:'내부 공유와 의사결정 정리가 빨라집니다.', usageMoment:'즉시 공유', expertNote:'핵심 판단이 먼저 보이도록 길이보다 우선순위를 앞세웁니다.', status: 'ready' },
        { title: `${target?.name || ''} 상세 실행 자료`, description: '세부 결과, 우선순위, 즉시 적용 포인트를 포함한 자료입니다.', customerValue:'작업자 기준으로 바로 손을 댈 수 있는 실행 자료입니다.', usageMoment:'실행 착수', expertNote:'설명형 문서가 아니라 행동형 문서가 되도록 세부 실행 포인트를 넣습니다.', status: 'ready' },
        { title: `${target?.name || ''} 자동 발행 글`, description: '고객 포털과 게시판에서 같은 조회 코드로 이어지는 자동 발행 콘텐츠입니다.', customerValue:'대외 설명과 내부 아카이브를 동시에 정리합니다.', usageMoment:'후속 점검', expertNote:'같은 내용을 보는 화면이 달라도 메시지는 흔들리지 않게 유지합니다.', status: 'ready' },
      ],
      deliveryAssets: [
        { title:`${target?.name || ''} 고객 전달 요약`, description:'핵심 결과와 다음 행동을 먼저 읽기 쉬운 형태로 정리합니다.', customerValue:'담당자와 의사결정자가 같은 내용을 짧게 공유할 수 있습니다.', usageMoment:'첫 공유', expertNote:'핵심 판단이 먼저 보이게 정리합니다.', status:'ready' },
        { title:`${target?.name || ''} 상세 실행 자료`, description:'출력물별 상세 설명, 우선순위, 즉시 적용 포인트를 포함한 본문 자료입니다.', customerValue:'작업자 입장에서 바로 손을 대야 할 항목과 검토 포인트를 함께 확인할 수 있습니다.', usageMoment:'실행', expertNote:'설명형 문서가 아니라 행동형 문서가 되도록 구성합니다.', status:'ready' },
        { title:`${target?.name || ''} 자동 발행 글 2건 이상`, description:'제품 설명, 공개 게시판, 고객 포털에서 같은 조회 코드로 이어지는 자동 발행 콘텐츠입니다.', customerValue:'결과를 전달하는 데서 끝나지 않고 대외 설명과 내부 공유까지 이어집니다.', usageMoment:'후속 공유', expertNote:'같은 내용을 보는 화면이 달라도 메시지를 유지합니다.', status:'ready' },
      ],
      nextActions: (target?.workflow || []).slice(0, 4),
      valueNarrative: `${target?.name || ''}은 결과 제목만 전달하지 않고, 바로 판단할 요약·세부 실행 자료·발행 결과까지 함께 묶어 남는 운영 자산으로 만드는 데 초점을 둡니다. 이번 결과는 지금 당장 움직일 일과 다음 변경 때 다시 꺼내 쓸 기준을 동시에 남깁니다.`,
      buyerDecisionReason: `단순 샘플이나 템플릿이 아니라 ${payload.company || '고객사'}의 목표와 운영 방식에 맞춘 판단 자료, 실행 자료, 발행 자산이 한 번에 준비되기 때문에 결제 직후 체감 가치가 높습니다.`,
    };
  }
  function buildDemoPreviewData(target, payload){
    const goal = payload.goal || target?.summary || '';
    return {
      headline: `${payload.company || '샘플 회사'} 기준 ${target?.name || ''} 샘플 결과`,
      summary: `${goal}을 기준으로 결제 전에 먼저 확인할 수 있는 샘플 결과입니다.`,
      company: payload.company || '샘플 회사',
      goal,
      keywords: payload.keywords || '',
      diagnosisSummary: `현재 가장 중요한 문제는 ${target?.problem || target?.summary || ''}. 이 데모는 그 문제를 설명하는 데서 끝나지 않고, 먼저 손볼 항목과 결과물 수준을 같이 보여 주는 데 초점을 둡니다.`,
      sampleOutputs: buildOutputPreview(target, target?.key, payload.company, payload.plan, goal, payload.keywords).slice(0, 3),
      quickWins: (target?.workflow || []).slice(0, 3),
      valueDrivers: (target?.value_points || []).slice(0, 3),
      successMetrics: (target?.architecture?.performance_targets || []).slice(0, 3),
      prioritySequence: buildPrioritySequence(target, payload.company, goal),
      expertNotes: buildProfessionalNotes(target).slice(0,3),
      objectionHandling: (target?.fit_for || []).slice(0,3).map((item) => `${item}에 맞게 결과와 다음 행동을 바로 연결할 수 있도록 구성합니다.`),
      scorecard: buildQualityScorecard(target, payload.company, goal, 'demo'),
      ctaHint: `이 조건으로 진행하면 ${target?.name || ''} ${payload.plan || 'Starter'} 플랜 결과와 자동 발행 자료가 같은 조회 코드로 이어집니다.`,
      closingArgument: '샘플 결과만으로도 무엇을 받게 되는지, 왜 비용보다 크게 남는지, 결제 후 어떤 자료가 발행되는지까지 미리 확인할 수 있게 구성했습니다.',
    };
  }
  function articleSlug(value){ return String(value || '').toLowerCase().replace(/[^a-z0-9가-힣]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') || uid('slug'); }
  function pickKeywords(...values){ const stop = new Set(['그리고','하지만','이렇게','바로','가장','먼저','위한','있는','하기','으로','에서','에게','지금']); const out=[]; const seen=new Set(); values.flat().forEach((value)=>String(value||'').split(/[\s,/|·]+/).forEach((raw)=>{ const token=raw.replace(/^[^a-z0-9가-힣]+|[^a-z0-9가-힣]+$/gi,''); if(token.length<2||stop.has(token)) return; const lower=token.toLowerCase(); if(seen.has(lower)) return; seen.add(lower); out.push(token); })); return out.slice(0,6); }
  function smoothPhrases(items, sep=' · '){ return (items || []).map((item)=>String(item || '').replace(/[\s.]+$/g,'').trim()).filter(Boolean).slice(0,3).join(sep); }
  function buildArticleSections(target, { title='', summary='', ctaLabel='', company='', plan='', orderCode='', topicSummary='' } = {}){ const outputs=smoothPhrases(target?.outputs || []) || '결과 자료'; const values=smoothPhrases(target?.value_points || [], ' / ') || target?.summary || ''; const fit=smoothPhrases(target?.fit_for || []) || '실무 팀'; const workflow=smoothPhrases(target?.workflow || [], ' → ') || '콘텐츠 허브 → 제품 설명 → 데모 시연 → 결제 → 결과 전달'; const proof=orderCode ? `조회 코드 ${orderCode}로 결과 전달 상태와 관련 콘텐츠을 함께 확인할 수 있습니다.` : '무료 샘플과 데모 시연 자료부터 확인한 뒤 결제 여부를 결정하실 수 있습니다.'; const focus=String(title || topicSummary || target?.summary || '').trim(); return [
      { heading:'이런 팀이라면 먼저 읽어보세요', body:`${summary} 특히 ${company || '운영팀'}처럼 적은 인원으로 반복 업무를 줄이고 싶은 팀에 잘 맞습니다. 이 글에서는 ${focus}을 중심으로 어떤 지점부터 손보면 좋은지 차분하게 정리합니다.` },
      { heading:'왜 기존 방식이 자꾸 막히는지', body:`문제는 업무량보다 매번 설명이 달라지고 기준이 흩어져 있다는 점입니다. 같은 요청도 사람마다 표현이 달라지면 검토, 보완, 전달이 길어지고 결국 다음 행동이 느려집니다. ${target?.problem || target?.summary || ''}` },
      { heading:`${target?.name || 'NV0'}이 실제로 줄여주는 일`, body:`${plan ? `${plan} 플랜 기준으로 ` : ''}${target?.name || 'NV0'}은 ${values} 같은 핵심 작업을 더 짧은 흐름으로 정리합니다. 결과적으로 ${outputs}를 한 번에 준비하고, 콘텐츠 허브·제품 설명·데모 시연·결제·결과 전달까지 같은 흐름으로 이어 주기 때문에 중간 설명 비용이 줄어듭니다.` },
      { heading:'콘텐츠 허브를 먼저 읽으면 좋은 이유', body:`누가 요청을 넣는지, 어떤 기준으로 검토하는지, 결과물을 어디서 확인하는지 세 가지만 먼저 정해도 시작이 훨씬 쉬워집니다. NV0 안에서는 ${workflow} 흐름으로 이 기준을 한 줄로 맞춰 둘 수 있습니다.` },
      { heading:'이렇게 시작하면 가장 부담이 적습니다', body:`처음부터 큰 전환을 하기보다 가장 자주 반복되는 한 가지 업무를 골라 무료 샘플과 데모 시연 자료부터 확인해 보세요. ${fit}처럼 빠르게 비교가 필요한 팀이라면 작은 테스트만으로도 도입 판단이 빨라집니다. ${proof}` },
      { heading:'다음 행동 안내', body:`이 글이 지금 상황과 맞는다면 ${ctaLabel || '제품 설명 보기'} 버튼으로 제품 상세를 먼저 확인해 보세요. 제품 설명, 데모 시연, 결제, 결과 전달까지 같은 흐름으로 이어지기 때문에 따로 헤매지 않고 바로 검토를 이어갈 수 있습니다.` },
    ]; }
  function renderArticleHtml(target, summary, sections, keywords, ctaLabel){ const sectionHtml=(sections||[]).map((item)=>`<section><h4>${esc(item.heading)}</h4><p>${esc(item.body)}</p></section>`).join(''); const chips=(keywords||[]).map((item)=>`<li>${esc(item)}</li>`).join(''); const outputs=(target?.outputs||[]).slice(0,4).map((item)=>`<li>${esc(item)}</li>`).join(''); return `<div class="article-shell"><p class="article-lead">${esc(summary)}</p><ul class="article-keywords">${chips}</ul><div class="article-sections">${sectionHtml}</div><aside class="article-cta-box"><strong>${esc(target?.name || 'NV0')}으로 바로 이어서 검토할 수 있습니다</strong><p>결과물 예시: ${esc((target?.outputs||[]).slice(0,3).join(', ') || '결과 자료')}</p><ul class="clean article-output-list">${outputs}</ul><p>마음이 정리되면 ${esc(ctaLabel || '제품 설명 보기')}로 바로 이어가 보세요.</p></aside></div>`; }
  function buildPublicationRecord({ product, title, summary, source='scheduled', code='', createdAt='', ctaLabel='', ctaHref='', order=null, topicSummary='', id='' }){ const target=products[product] || {}; const automation=target.board_automation || {}; const cta=ctaLabel || automation.cta_label || '제품 설명 보기'; const href=ctaHref || buildCtaHref(automation.cta_href, product); const sections=buildArticleSections(target, { title, summary, ctaLabel:cta, company:order?.company || '', plan:order?.plan || '', orderCode:order?.code || '', topicSummary:topicSummary || summary }); const keywords=pickKeywords(target.name, target.tag, title, summary, ...(target.board_topics || [])); const body=sections.map((item)=>`${item.heading}\n${item.body}`).join('\n\n'); return { id: id || uid('pub'), product, productName: target.name || productName(product), title, summary, body, bodyHtml: renderArticleHtml(target, summary, sections, keywords, cta), sections, keywords, readMinutes: Math.max(3, Math.min(8, Math.floor(body.length / 260) + 1)), slug: articleSlug(`${target.name || product}-${title}`), format:'ai-hybrid-blog', code, status:'published', createdAt: createdAt || stamp(), updatedAt: createdAt || stamp(), source, ctaLabel: cta, ctaHref: href, topicSummary: topicSummary || summary, ...(order?.id ? { orderId: order.id } : {}) }; }



  function createPublicationsForOrder(order){
    const target = products[order.product] || {};
    const automation = target.board_automation || {};
    const topics = (target.board_topics || []).slice(0, 2);
    const selected = topics.length ? topics.map((title, idx) => ({ title: idx === 0 ? `${target.name || order.product} ${order.company || order.email || '고객'} 맞춤 제안` : title, summary: idx === 0 ? `${order.company || order.email || '고객'} 상황에 맞춰 ${target.name || order.product} ${order.plan} 플랜의 정상작동 설정과 발행 제공 흐름을 블로그 형식으로 정리했습니다.` : `${target.summary || ''} 조회 코드 ${order.code} 기준으로 함께 확인할 수 있는 AI 자동발행 안내 글입니다.`, ctaText: automation.cta_label || '제품 설명 보기' })) : [{ title: `${target.name || order.product} 도입 전에 먼저 확인하면 좋은 기준`, summary: `${order.company || order.email} 상황에 맞춘 핵심 결과와 다음 행동을 함께 정리했습니다.`, ctaText: automation.cta_label || '제품 설명 보기' }, { title: `${target.name || order.product}으로 지금 줄일 수 있는 반복 작업`, summary: `체험 이후 바로 적용할 수 있는 포인트를 블로그 형식으로 정리한 글입니다.`, ctaText: automation.cta_label || '제품 보기' }];
    const createdAt = stamp();
    const pubs = selected.map((topic, idx) => buildPublicationRecord({ product: order.product, title: topic.title, summary: topic.summary, source:'order', code: `${order.code}-${idx + 1}`, createdAt, ctaLabel: topic.ctaText || automation.cta_label || '제품 설명 보기', ctaHref: buildCtaHref(automation.cta_href, order.product), order, topicSummary: topic.summary, id: uid('pub') }));
    const all = read(STORE.publications);
    write(STORE.publications, [...pubs, ...all]);
    return pubs;
  }
  function createOrder(payload){
    const data = normalizePayload(payload);
    assert(validateProduct(data.product), '제품을 선택하세요.');
    assert(validatePlan(data.product, data.plan), '플랜을 선택하세요.');
    assert(clean(data.company), '회사명을 입력하세요.');
    assert(clean(data.name), '담당자명을 입력하세요.');
    assert(validateEmail(data.email), '이메일 형식이 올바르지 않습니다.');
    const target = products[data.product];
    const createdAt = stamp();
    const id = uid('ord');
    const code = makePublicCode('NV0', data.product);
    const resultPack = buildResultPack(target, data);
    const order = {
      id,
      code,
      product: data.product,
      productName: target.name,
      plan: data.plan,
      billing: data.billing || 'one-time',
      paymentMethod: data.paymentMethod || 'toss',
      company: data.company,
      name: data.name,
      email: normalizeEmail(data.email),
      note: data.note || '',
      price: planPrice(data.product, data.plan),
      paymentStatus: 'paid',
      status: 'delivered',
      deliveryMeta: { automation: 'local_auto', deliveredAt: createdAt },
      amount: priceToAmount(planPrice(data.product, data.plan)),
      resultPack,
      publicationIds: [],
      publicationCount: 0,
      createdAt,
      updatedAt: createdAt,
    };
    const publications = createPublicationsForOrder(order);
    order.publicationIds = publications.map((item) => item.id);
    order.publicationCount = publications.length;
    push(STORE.orders, order);
    return order;
  }
  function createDemo(payload){
    const data = normalizePayload(payload);
    assert(validateProduct(data.product), '제품을 선택하세요.');
    assert(clean(data.company), '회사명을 입력하세요.');
    assert(clean(data.name), '담당자명을 입력하세요.');
    assert(validateEmail(data.email), '이메일 형식이 올바르지 않습니다.');
    const createdAt = stamp();
    const item = { id: uid('demo'), code: makePublicCode('DEMO', data.product), product: data.product, productName: productName(data.product), company: data.company, name: data.name, email: normalizeEmail(data.email), team: data.team || '', need: data.need || '', keywords: data.keywords || '', plan: data.plan || '', createdAt, updatedAt: createdAt };
    push(STORE.demos, item);
    return item;
  }
  function createContact(payload){
    const data = normalizePayload(payload);
    assert(validateProduct(data.product), '제품을 선택하세요.');
    assert(clean(data.company), '회사명을 입력하세요.');
    assert(clean(data.name), '담당자명을 입력하세요.');
    assert(validateEmail(data.email), '이메일 형식이 올바르지 않습니다.');
    assert(clean(data.issue), '확인 내용을 입력하세요.');
    const createdAt = stamp();
    const item = { id: uid('contact'), code: makePublicCode('CONTACT', data.product), product: data.product, productName: productName(data.product), company: data.company, name: data.name, email: normalizeEmail(data.email), issue: data.issue || '', createdAt, updatedAt: createdAt };
    push(STORE.contacts, item);
    return item;
  }
  function createLookup(payload){
    const data = normalizePayload(payload);
    assert(validateEmail(data.email), '이메일 형식이 올바르지 않습니다.');
    assert(clean(data.code), '조회 코드를 입력하세요.');
    const item = { id: uid('lookup'), email: normalizeEmail(data.email), code: data.code || '', createdAt: stamp() };
    push(STORE.lookups, item);
    return item;
  }
  function renderHeader(){
    const header = document.getElementById('site-header'); if (!header) return;
    const isProductSurface = path.includes('/products/');
    const productLinks = Object.values(products).map((item) => `<a href="${base}products/${item.key}/index.html" class="sub-link ${productKey === item.key ? 'active' : ''}">${esc(item.name)}</a>`).join('');
    const quickLinks = isProductSurface && productKey
      ? [`<a href="${base}products/${productKey}/index.html" class="sub-head ${pageKey === 'product' ? 'active' : ''}">요약</a>`, `<a href="${base}products/${productKey}/demo/index.html" class="sub-link ${path.includes(`/products/${productKey}/demo/`) ? 'active' : ''}">즉시 데모</a>`, `<a href="${base}products/${productKey}/plans/index.html" class="sub-link ${path.includes(`/products/${productKey}/plans/`) ? 'active' : ''}">플랜</a>`, `<a href="${base}products/${productKey}/delivery/index.html" class="sub-link ${path.includes(`/products/${productKey}/delivery/`) ? 'active' : ''}">전달물</a>`, `<a href="${base}products/${productKey}/faq/index.html" class="sub-link ${path.includes(`/products/${productKey}/faq/`) ? 'active' : ''}">FAQ</a>`, `<a href="${base}products/${productKey}/board/index.html" class="sub-link ${path.includes(`/products/${productKey}/board/`) ? 'active' : ''}">게시판</a>`].join('')
      : `<a href="${base}products/index.html" class="sub-head ${pageKey === 'products' ? 'active' : ''}">제품 모듈</a>${productLinks}`;
    header.innerHTML = `<div class="container nav-wrap"><div class="nav-left"><a class="admin-entry" href="${base}admin/index.html" title="비밀키가 있어야 열립니다">관리자</a><a class="brand" href="${base}index.html"><span class="brand-mark">N0</span><span class="brand-copy"><strong>${config.brand?.name || 'NV0'}</strong><span>${config.brand?.tagline || ''}</span></span></a></div><nav class="nav-links">${navItems.map(([label, href, key]) => `<a href="${href}" class="${pageKey === key ? 'active' : ''}">${label}</a>`).join('')}<a class="button secondary" href="${base}demo/index.html">즉시 데모</a><a class="button" href="${base}pricing/index.html">가격 보기</a></nav></div><div class="container subnav">${quickLinks}</div>`;
  }
  function renderFooter(){
    const footer = document.getElementById('site-footer'); if (!footer) return;
    const info = config.brand?.business_info || {};
    const email = info.contact_email || config.brand?.contact_email || 'ct@nv0.kr';
    const operator = info.operator_name || config.brand?.name || 'NV0';
    const notice = info.support_notice || '공개 사이트는 이해와 선택을 돕고, 관리자 메뉴는 운영과 자동화 설정을 담당합니다.';
    footer.innerHTML = `<div class="container footer-grid"><div><div class="brand"><span class="brand-mark">N0</span><span class="brand-copy"><strong>${config.brand?.name || 'NV0'}</strong><span>처음에는 핵심만 짧게, 필요할 때는 더 깊게 확인하실 수 있도록 설계했습니다.</span></span></div><small style="margin-top:14px">공개 사이트는 이해와 선택, 결제 흐름에 집중하고 운영 기능은 관리자 허브로 분리해 더 단순하고 안정적으로 이용하실 수 있게 했습니다.</small></div><div><strong>바로 보기</strong><small><a href="${base}products/index.html">제품 모듈</a><br><a href="${base}solutions/index.html">문제별 시작</a><br><a href="${base}pricing/index.html">가격</a><br><a href="${base}docs/index.html">문서 센터</a><br><a href="${base}service/index.html">확장 서비스</a><br><a href="${base}faq/index.html">FAQ</a></small></div><div><strong>운영/정책</strong><small>운영명: ${esc(operator)}<br><a href="mailto:${email}">${esc(email)}</a><br>${esc(notice)}<br><a href="${base}portal/index.html">고객 포털</a><br><a href="${base}contact/index.html">추가 확인</a><br><a href="${base}legal/privacy/index.html">개인정보처리방침</a><br><a href="${base}legal/terms/index.html">이용약관</a><br><a href="${base}legal/refund/index.html">환불 정책</a></small></div></div>`;
  }
  function currencyPlan(productKey) { const target = products[productKey]; return target ? target.plans.map((item) => `${item.name} ${item.price}`).join(' · ') : 'Starter · Growth · Scale'; }
  function buildHomeProducts() { const root = document.getElementById('product-grid'); if (!root) return; root.innerHTML = Object.values(products).map((item) => `<article class="card product-card strong ${item.theme}"><span class="tag theme-chip">${item.label}</span><h3>${item.name}</h3><p>${item.headline}</p><ul class="clean">${item.value_points.slice(0,3).map((text) => `<li>${text}</li>`).join('')}</ul><div class="muted-box" style="margin-top:18px">시작가: ${item.plans[0]?.price || '-'} · ${esc(item.pricing_basis || '')}</div><div class="actions"><a class="button" href="${base}products/${item.key}/demo/index.html">즉시 데모</a><a class="button secondary" href="${base}products/${item.key}/plans/index.html">플랜 보기</a><a class="button ghost" href="${base}products/${item.key}/index.html">요약 보기</a></div></article>`).join(''); }
  function buildModuleMatrix() { const root = document.getElementById('module-matrix'); if (!root) return; root.innerHTML = Object.values(products).map((item) => `<article class="story-card ${item.theme}"><span class="tag theme-chip">${item.tag}</span><h3>${item.name}</h3><p>${item.summary}</p><div class="actions"><a class="button soft" href="${base}products/${item.key}/index.html">요약 보기</a><a class="button ghost" href="${base}products/${item.key}/demo/index.html">즉시 데모</a></div></article>`).join(''); }
  function renderLiveStats(){ const root = document.getElementById('live-stats'); if (!root) return; ensureSeedData(); const orders = read(STORE.orders); const publications = read(STORE.publications); const demos = read(STORE.demos); const contacts = read(STORE.contacts); const started = orders.length || '상시'; const demosCount = demos.length || Object.keys(products).length; root.innerHTML = `<article class="mini"><strong>${started}</strong><span>${orders.length ? '저장된 결제 접수' : '결제 가능'}</span></article><article class="mini"><strong>${publications.length}</strong><span>읽어볼 자동발행 글</span></article><article class="mini"><strong>${demosCount}</strong><span>${demos.length ? '확인된 샘플 결과' : '데모 시연 가능한 제품'}</span></article><article class="mini"><strong>${contacts.length || '이메일'}</strong><span>${contacts.length ? '남겨진 추가 확인' : (config.brand?.contact_email || '추가 확인 채널')}</span></article>`; }
  function renderWorkspaceCards(){ const root = document.getElementById('workspace-records'); if (!root) return; const orders = read(STORE.orders).slice(0, 2); const demos = read(STORE.demos).slice(0, 1); const contacts = read(STORE.contacts).slice(0, 1); const cards = []; orders.forEach((item) => cards.push(`<article class="record-card"><span class="tag">결제 접수</span><h4>${esc(item.company || item.email)}</h4><p>${esc(item.productName)} · ${esc(item.plan)} · 조회 코드 <span class="inline-code">${esc(item.code)}</span></p><div class="small-actions"><a href="${portalHref(item)}">제공 상태 확인</a><a href="${base}products/${item.product}/board/index.html">콘텐츠 허브 보기</a></div></article>`)); demos.forEach((item) => cards.push(`<article class="record-card"><span class="tag">체험</span><h4>${esc(item.company || item.email)}</h4><p>${esc(item.productName)} 데모 시연 확인 · ${esc(item.code)}</p><div class="small-actions"><a href="${base}products/${item.product}/index.html">자세히 보기</a><a href="${base}products/${item.product}/index.html#order">결제 계속하기</a></div></article>`)); contacts.forEach((item) => cards.push(`<article class="record-card"><span class="tag">추가 확인</span><h4>${esc(item.company || item.email)}</h4><p>${esc(item.productName)} · ${esc(item.issue || '')}</p><div class="small-actions"><a href="${item.product ? `${base}products/${item.product}/index.html` : `${base}company/index.html`}">관련 정보</a><a href="${item.product ? `${base}products/${item.product}/index.html#intro` : `${base}contact/index.html`}">다음 단계 보기</a></div></article>`)); root.innerHTML = cards.length ? cards.join('') : '<div class="empty-box">아직 저장된 체험이나 결제 기록이 없습니다. 원하시는 제품에서 짧은 데모부터 살펴보시면 다음 단계가 더 쉽게 정리됩니다.</div>'; }
  function servicesForProduct(key){ return serviceCatalog.filter((item) => item.lead_product === key || (Array.isArray(item.fit_products) && item.fit_products.includes(key))); }
  function groupServices(items){ return items.reduce((acc, item) => { const category = item.category || '기타 확장 서비스'; (acc[category] ||= []).push(item); return acc; }, {}); }
  function renderProductServices(){
    if (!product) return;
    const statsRoot = document.getElementById('product-service-stats');
    const catalogRoot = document.getElementById('product-service-catalog');
    if (!statsRoot && !catalogRoot) return;
    const items = servicesForProduct(product.key);
    const grouped = groupServices(items);
    const categories = Object.keys(grouped);
    const leadCount = items.filter((item) => item.lead_product === product.key).length;
    if (statsRoot) statsRoot.innerHTML = `<article class="admin-card"><span class="tag">연결 서비스</span><h3>${items.length}</h3><p>${esc(product.name)}에 바로 붙일 수 있는 모듈 수</p></article><article class="admin-card"><span class="tag">주력 제안</span><h3>${leadCount}</h3><p>이 제품을 중심으로 바로 묶기 좋은 서비스</p></article><article class="admin-card"><span class="tag">카테고리</span><h3>${categories.length}</h3><p>정밀 탐색에 쓰는 범주 수</p></article>`;
    if (catalogRoot) {
      if (!items.length) { catalogRoot.innerHTML = '<div class="empty-box">현재 이 제품과 직접 연결된 확장 서비스가 없습니다. 기본 제품만으로도 시작하실 수 있습니다.</div>'; return; }
      const topCategories = categories.sort((a,b) => grouped[b].length - grouped[a].length).slice(0, 6);
      catalogRoot.innerHTML = topCategories.map((category, idx) => `<details class="fold-card" ${idx === 0 ? 'open' : ''}><summary><strong>${esc(category)}</strong><span>${grouped[category].length}개 연결</span></summary><div><div class="story-grid">${grouped[category].slice(0, 8).map((item) => `<article class="story-card"><span class="tag">${esc(item.id || '')}</span><h3>${esc(item.name || '')}</h3><p>${esc(item.summary || '')}</p><div class="small-actions"><span>주력 제품: ${esc(products[item.lead_product]?.name || item.lead_product || '공통')}</span></div></article>`).join('')}</div></div></details>`).join('');
    }
  }
  function renderServiceCatalog(){
    const root = document.getElementById('service-catalog-results');
    const statsRoot = document.getElementById('service-catalog-stats');
    const categoryFilter = document.getElementById('service-category-filter');
    const productFilter = document.getElementById('service-product-filter');
    const searchInput = document.getElementById('service-search');
    const fallback = document.getElementById('service-catalog-fallback');
    if (!root || !statsRoot || !categoryFilter || !productFilter || !searchInput) return;
    if (fallback) fallback.hidden = true;
    const categories = [...new Set(serviceCatalog.map((item) => item.category || '기타 확장 서비스'))].sort();
    const productKeys = [...new Set(serviceCatalog.flatMap((item) => [item.lead_product, ...(item.fit_products || [])]).filter(Boolean))].filter((key) => products[key]).sort();
    categoryFilter.innerHTML = `<option value="">전체 카테고리</option>${categories.map((item) => `<option value="${esc(item)}">${esc(item)}</option>`).join('')}`;
    productFilter.innerHTML = `<option value="">전체 제품</option>${productKeys.map((key) => `<option value="${esc(key)}">${esc(products[key].name)}</option>`).join('')}`;
    const render = () => {
      const query = clean(searchInput.value).toLowerCase();
      const category = clean(categoryFilter.value);
      const productKey = clean(productFilter.value);
      const items = serviceCatalog.filter((item) => {
        const haystack = `${item.id || ''} ${item.name || ''} ${item.category || ''} ${item.summary || ''} ${item.lead_product || ''} ${(item.fit_products || []).join(' ')}`.toLowerCase();
        const matchQuery = !query || haystack.includes(query);
        const matchCategory = !category || (item.category || '') === category;
        const fit = Array.isArray(item.fit_products) ? item.fit_products : [];
        const matchProduct = !productKey || item.lead_product === productKey || fit.includes(productKey);
        return matchQuery && matchCategory && matchProduct;
      });
      const grouped = groupServices(items);
      const categoriesCount = Object.keys(grouped).length;
      const leadCount = items.filter((item) => item.lead_product).length;
      statsRoot.innerHTML = `<article class="admin-card"><span class="tag">검색 결과</span><h3>${items.length}</h3><p>현재 조건에 맞는 확장 서비스</p></article><article class="admin-card"><span class="tag">카테고리</span><h3>${categoriesCount}</h3><p>현재 조건에서 남은 범주 수</p></article><article class="admin-card"><span class="tag">주력 제안</span><h3>${leadCount}</h3><p>핵심 제품에 바로 붙일 수 있는 항목</p></article>`;
      root.innerHTML = items.length ? items.slice(0, 120).map((item) => `<article class="story-card"><span class="tag">${esc(item.id || '')}</span><h3>${esc(item.name || '')}</h3><p>${esc(item.summary || '')}</p><ul class="clean"><li>카테고리: ${esc(item.category || '기타')}</li><li>주력 제품: ${esc(products[item.lead_product]?.name || item.lead_product || '공통')}</li><li>연결 제품: ${esc((item.fit_products || []).map((key) => products[key]?.name || key).join(', ') || '공통 제안형')}</li></ul></article>`).join('') : '<div class="empty-box">조건에 맞는 확장 서비스가 없습니다. 검색어를 줄이거나 카테고리를 전체로 바꿔 보세요.</div>';
    };
    [searchInput, categoryFilter, productFilter].forEach((node) => node.addEventListener('input', render));
    render();
  }
  function quickDemoContent(targetProduct, index){
    if (!targetProduct) return '';
    const scenarios = Array.isArray(targetProduct.demo_scenarios) ? targetProduct.demo_scenarios : [];
    const rawScenario = scenarios[index] ?? scenarios[0] ?? targetProduct.headline ?? '';
    const scenario = typeof rawScenario === 'string' ? rawScenario : JSON.stringify(rawScenario);
    const samplePoints = (targetProduct.outputs || []).slice(0, 3).map((item) => `<li>${esc(item)}</li>`).join('');
    return `<div class="notice-strong"><strong>${esc(targetProduct.name)} 미리보기</strong><br>${esc(scenario)}</div><ul class="clean" style="margin-top:14px">${samplePoints}</ul><div class="small-actions" style="margin-top:14px"><a href="${base}products/${targetProduct.key}/demo/index.html">상세 데모</a><a href="${base}products/${targetProduct.key}/plans/index.html">플랜 보기</a></div>`;
  }
  function bindQuickDemoButtons(){
    document.querySelectorAll('[data-quick-demo]').forEach((button) => {
      button.addEventListener('click', () => {
        const target = products[button.dataset.quickDemo || ''];
        const index = Number(button.dataset.quickScenario || '0') || 0;
        const html = quickDemoContent(target, index);
        document.querySelectorAll('#quick-demo-result').forEach((root) => { root.innerHTML = html || '<div class="empty-box">지금 보여드릴 미리보기가 없습니다. 다른 시나리오를 선택해 주세요.</div>'; });
      });
    });
  }
  function buildPlans() { const root = document.getElementById('plan-grid'); if (!root || !product) return; root.innerHTML = product.plans.map((plan) => { const recommended = plan.recommended ? '<span class="tag" style="margin-left:8px">추천</span>' : ''; const meta = [plan.delivery ? `납기 ${esc(plan.delivery)}` : '', plan.revisions ? esc(plan.revisions) : ''].filter(Boolean).join(' · '); const includes = Array.isArray(plan.includes) && plan.includes.length ? `<ul class="clean plan-include-list">${plan.includes.map((item) => `<li>${esc(item)}</li>`).join('')}</ul>` : ''; return `<article class="plan-card ${plan.recommended ? 'recommended' : ''}"><div class="plan-head"><span class="tag">${esc(plan.name)}</span>${recommended}</div><h3>${esc(plan.price)}</h3><p>${esc(plan.note || '')}</p>${meta ? `<div class="plan-meta">${meta}</div>` : ''}${includes}<div class="small-actions"><a class="button" href="#order" data-plan-pick="${esc(plan.name)}">이 플랜으로 결제 계속하기</a></div></article>`; }).join(''); root.querySelectorAll('[data-plan-pick]').forEach((btn)=>btn.addEventListener('click',()=>{ const form=document.getElementById('product-checkout-form'); if(form){ const select=form.querySelector('select[name="plan"]'); if(select) select.value=btn.dataset.planPick; location.hash='order'; }})); }
  function fillProductSlots() { if (!product) return; document.querySelectorAll('[data-fill="product-name"]').forEach((el) => el.textContent = product.name); document.querySelectorAll('[data-fill="product-headline"]').forEach((el) => el.textContent = product.headline); document.querySelectorAll('[data-fill="product-summary"]').forEach((el) => el.textContent = product.summary); document.querySelectorAll('[data-fill="product-problem"]').forEach((el) => el.textContent = product.problem); document.querySelectorAll('[data-fill="product-pricing"]').forEach((el) => el.textContent = currencyPlan(product.key)); const valueRoot = document.getElementById('product-values'); if (valueRoot) valueRoot.innerHTML = product.value_points.map((item) => `<li>${item}</li>`).join(''); const outputRoot = document.getElementById('product-outputs'); if (outputRoot) outputRoot.innerHTML = product.outputs.map((item) => `<li>${item}</li>`).join(''); const workflowRoot = document.getElementById('product-workflow'); if (workflowRoot) workflowRoot.innerHTML = (product.workflow || []).map((item) => `<li>${item}</li>`).join(''); const demoRoot = document.getElementById('product-demo-scenarios'); if (demoRoot) demoRoot.innerHTML = (product.demo_scenarios || []).map((item) => `<li>${item}</li>`).join(''); const relatedRoot = document.getElementById('product-related-modules'); if (relatedRoot) relatedRoot.innerHTML = (product.related_modules || []).map((key) => products[key]).filter(Boolean).map((item) => `<article class="story-card ${item.theme}"><span class="tag theme-chip">${esc(item.label)}</span><h3>${esc(item.name)}</h3><p>${esc(item.summary)}</p><div class="small-actions"><a href="${base}products/${item.key}/index.html#intro">제품 설명 보기</a><a href="${base}products/${item.key}/index.html#demo">데모 시연</a></div></article>`).join('') || '<div class="empty-box">바로 이어서 비교할 제품이 아직 없습니다. 현재 제품 기준으로 먼저 판단하셔도 괜찮습니다.</div>';  const faqRoot = document.getElementById('product-faq'); if (faqRoot) faqRoot.innerHTML = (product.faqs || []).map((item) => `<article class="faq-card"><span class="tag">Q</span><h3>${esc(item.q)}</h3><p>${esc(item.a)}</p></article>`).join(''); const actions = document.getElementById('product-actions'); if (actions) actions.innerHTML = `<a class="button" href="${base}products/${product.key}/demo/index.html">즉시 데모</a><a class="button secondary" href="${base}products/${product.key}/plans/index.html">플랜 보기</a><a class="button ghost" href="${base}products/${product.key}/delivery/index.html">전달물 보기</a><a class="button ghost" href="${base}products/${product.key}/board/index.html">게시판 보기</a>`; const basis = document.getElementById('product-pricing-basis'); if (basis) basis.textContent = product.pricing_basis || ''; const demoForm = document.getElementById('product-demo-form'); if (demoForm) { const defaults = product.demo_defaults || {}; demoForm.querySelectorAll('[data-demo-field]').forEach((input)=>{ const key = input.dataset.demoField; if (defaults[key] && !input.value) input.value = defaults[key]; }); } }
  function advanceOrder(orderId){ return updateItem(STORE.orders, orderId, (item) => { if (item.paymentStatus !== 'paid') throw new Error('결제 완료 전에는 자동 제공을 완료할 수 없습니다.'); return {...item, status:'delivered', deliveryMeta:{...(item.deliveryMeta||{}), automation:'local_auto', deliveredAt: stamp()}, updatedAt: stamp()}; }); }
  function toggleOrderPayment(orderId){ return updateItem(STORE.orders, orderId, (item) => { const paymentStatus = item.paymentStatus === 'paid' ? 'pending' : 'paid'; const status = paymentStatus === 'paid' ? 'delivered' : 'payment_pending'; return {...item, paymentStatus, status, deliveryMeta: paymentStatus === 'paid' ? { ...(item.deliveryMeta||{}), automation:'local_auto', deliveredAt: stamp() } : item.deliveryMeta, updatedAt: stamp()}; }); }
  function republishOrder(orderId){ const orders = read(STORE.orders); const order = orders.find((item) => item.id === orderId); if (!order) throw new Error('결제 접수를 찾지 못했습니다.'); const extra = createPublicationsForOrder(order); return updateItem(STORE.orders, orderId, (item) => ({...item, publicationIds: [...(item.publicationIds || []), ...extra.map((p) => p.id)], publicationCount: (item.publicationCount || 0) + extra.length, updatedAt: stamp()})); }
  function lookupOrder(email, code){ const orders = read(STORE.orders); if (code) { const exact = orders.find((item) => String(item.code).toLowerCase() === String(code).toLowerCase()); if (exact && (!email || String(exact.email).toLowerCase() === String(email).toLowerCase())) return exact; } if (email) return orders.find((item) => String(item.email).toLowerCase() === String(email).toLowerCase()) || null; return null; }
  function renderPublicationDetail(targetId, items){ const root = document.getElementById(targetId); if (!root) return; const params = new URLSearchParams(location.search); const postId = params.get('post'); const item = items.find((entry) => entry.id === postId) || items[0]; if (!item) { root.innerHTML = '<div class="empty-box">지금 표시할 글이 없습니다. 목록에서 다른 글을 선택하시거나 제품 상세로 이동해 주세요.</div>'; return; } const detailProduct = products[item.product] || null; const portalLink = item.code ? `${base}portal/index.html?code=${encodeURIComponent(item.code)}` : `${base}portal/index.html`; root.innerHTML = `<article class="post-detail"><span class="tag">${esc(item.productName || productName(item.product))}</span><h3>${esc(item.title)}</h3><p>${esc(item.summary)}</p><div class="kv"><div class="row"><strong>게시 시각</strong><span>${formatDate(item.createdAt)}</span></div><div class="row"><strong>조회 코드</strong><span>${esc(item.code || '기본 안내')}</span></div><div class="row"><strong>글 유형</strong><span>${esc(item.source || 'board')}</span></div><div class="row"><strong>본문</strong><span>${esc(item.body || item.summary).split('\n').join('<br>')}</span></div></div><div class="small-actions">${boardCtaMarkup(item)}<a href="${detailProduct ? `${base}products/${item.product}/index.html` : `${base}products/index.html`}">자세히 보기</a><a href="${base}products/${item.product}/board/index.html?post=${item.id}">같은 제품 글 더 보기</a><a href="${portalLink}">제공 상태 확인</a></div></article>`; }
  function renderPublicBoard() { const root = document.getElementById('public-board-grid'); if (!root) return; ensureSeedData(); const items = read(STORE.publications).sort((a,b) => (a.createdAt < b.createdAt ? 1 : -1)); if (!items.length) { root.innerHTML = '<div class="empty-box">아직 공개된 글이 없습니다. 조금 뒤 다시 확인하시거나 제품 상세에서 먼저 방향을 살펴보실 수 있습니다.</div>'; return; } root.innerHTML = items.slice(0, 12).map((item, idx) => `<article class="board-card board-card-blog"><span class="tag">AI 글 ${idx + 1}</span><h3>${esc(item.title)}</h3><p>${esc(item.summary)}</p><div class="board-meta"><span>${esc(item.productName || productName(item.product))}</span><span>${esc(String(item.readMinutes || 3))}분 읽기</span><span>${esc(item.format || 'ai-hybrid-blog')}</span></div><div class="small-actions">${boardCtaMarkup(item)}<a href="${publicBoardHref(item.id)}">블로그 글 보기</a><a href="${base}products/${item.product}/index.html">제품 상세</a></div></article>`).join(''); renderPublicationDetail('public-post-detail', items); }
  function renderProductBoard() { const root = document.getElementById('product-board-grid'); if (!root || !product) return; ensureSeedData(); const dynamic = read(STORE.publications).filter((item) => item.product === product.key); const automation = product.board_automation || {}; const seedCards = (automation.topics || []).map((topic, idx) => buildPublicationRecord({ product: product.key, title: topic.title, summary: topic.summary, source:'topic-seed', code:'', createdAt: stamp(), ctaLabel: topic.ctaText || automation.cta_label || '제품 보기', ctaHref: buildCtaHref(automation.cta_href, product.key), topicSummary: topic.summary, id:`topic-${idx}` })); const items = [...dynamic, ...seedCards].sort((a,b)=>a.createdAt < b.createdAt ? 1 : -1); root.innerHTML = items.slice(0, 12).map((item, idx) => `<article class="board-card board-card-blog"><span class="tag">${product.name} AI 글 ${idx + 1}</span><h3>${esc(item.title)}</h3><p>${esc(item.summary)}</p><div class="board-meta"><span>${esc(String(item.readMinutes || 3))}분 읽기</span><span>${esc(item.format || 'ai-hybrid-blog')}</span></div><div class="small-actions">${boardCtaMarkup(item)}<a href="${productBoardHref(product.key, item.id)}">블로그 글 보기</a><a href="${base}products/${product.key}/index.html#order">결제 진행</a></div></article>`).join(''); renderPublicationDetail('product-post-detail', items); }
  function explainPaymentUnavailable(payment){ if (payment?.mock) return '현재는 테스트용 mock 결제 모드입니다.'; if (!payment?.enabled) return '결제 설정이 아직 완료되지 않았습니다. 운영자에게 Toss 키와 웹훅 설정 상태를 먼저 확인해 달라고 요청해 주세요.'; if (!window.TossPayments) return '외부 결제 스크립트를 불러오지 못했습니다. 네트워크 상태나 브라우저 차단 설정을 먼저 확인해 주세요.'; return '외부 결제 연결을 확인하지 못했습니다.'; }
  function renderScorecardHtml(scorecard){
    const items = (scorecard?.items || []).map((item)=>`<article class="record-card"><span class="tag">${esc(item.label)}</span><h4>${esc(String(item.score))} / ${esc(String(item.max))}</h4><p>${esc(item.reason || '')}</p></article>`).join('');
    if (!scorecard) return '';
    return `<div class="notice-strong"><strong>${esc(scorecard.headline || '품질 기준표')}</strong><p>${esc(scorecard.summary || '')}</p><p><span class="inline-code">총점 ${esc(String(scorecard.earned || 0))} / ${esc(String(scorecard.total || 100))}</span> · 등급 ${esc(scorecard.grade || 'A')}</p></div><div class="admin-grid">${items}</div>`;
  }
  function buildRichOutputList(items){
    return (items || []).map((item)=>`<li><strong>${esc(item.title)}</strong><span>${esc(item.preview || item.note || '')}</span>${item.whatIncluded ? `<small>포함 내용 · ${esc(item.whatIncluded)}</small>` : ''}${item.actionNow ? `<small>바로 활용 · ${esc(item.actionNow)}</small>` : ''}${item.buyerValue ? `<small>고객 가치 · ${esc(item.buyerValue)}</small>` : ''}${item.expertLens ? `<small>전문 기준 · ${esc(item.expertLens)}</small>` : ''}</li>`).join('');
  }
  function buildBundleList(items){
    return (items || []).map((item)=>`<li><strong>${esc(item.title)}</strong><span>${esc(item.description || '')}</span>${item.customerValue ? `<small>가치 · ${esc(item.customerValue)}</small>` : ''}${item.usageMoment ? `<small>사용 시점 · ${esc(item.usageMoment)}</small>` : ''}${item.expertNote ? `<small>전문 기준 · ${esc(item.expertNote)}</small>` : ''}</li>`).join('');
  }
  function buildTextList(items){ return (items || []).map((item)=>`<li>${esc(item)}</li>`).join(''); }
  function buildDemoPreviewHtml(payload, options = {}, meta = {}){ const target = products[payload.product]; const preview = meta.preview || buildDemoPreviewData(target, payload); const outputs = buildRichOutputList(preview.sampleOutputs || []); const quickWins = buildTextList(preview.quickWins || []); const valueDrivers = buildTextList(preview.valueDrivers || []); const metrics = buildTextList(preview.successMetrics || []); const priority = buildTextList(preview.prioritySequence || []); const expert = buildTextList(preview.expertNotes || []); const objections = buildTextList(preview.objectionHandling || []); const scoreHtml = renderScorecardHtml(preview.scorecard); const orderHref = options.orderHref || '#order'; const boardHref = options.boardHref || `${base}products/${payload.product}/board/index.html`; const detailHref = options.detailHref || `${base}products/${payload.product}/index.html`; const demoMeta = meta.code ? `<div class="notice"><strong>데모 시연 코드</strong><br><span class="inline-code">${esc(meta.code)}</span>${meta.remoteSaved ? '<br>데모 정보가 저장되어 관리자 화면과 후속 안내에 바로 연결됩니다.' : '<br>현재 화면에도 데모 시연 정보가 저장되었습니다.'}</div>` : ''; return `<div class="order-result"><strong>${esc(preview.headline || `${target?.name || ''} 샘플 결과 미리보기`)}</strong><div>회사: <span class="inline-code">${esc(preview.company || payload.company)}</span></div><div>목표: ${esc(preview.goal || payload.goal || '')}</div><div>핵심 키워드: ${esc(preview.keywords || payload.keywords || '')}</div>${demoMeta}<p style="margin:10px 0 14px">${esc(preview.summary || '실제 결제 후 받아보게 될 결과물의 형태와 깊이를 미리 보여 드립니다.')}</p><div class="notice"><strong>진단 요약</strong><br>${esc(preview.diagnosisSummary || '')}</div>${scoreHtml}<div class="split-two"><div><h4>샘플 결과물</h4><ul class="output-list">${outputs}</ul><h4 style="margin-top:14px">바로 움직일 우선순위</h4><ul class="clean">${priority}</ul></div><div><h4>바로 체감할 가치</h4><ul class="clean">${quickWins}${valueDrivers}</ul><h4 style="margin-top:14px">확인 기준</h4><ul class="clean">${metrics}</ul><h4 style="margin-top:14px">전문가 기준</h4><ul class="clean">${expert}</ul><h4 style="margin-top:14px">자주 막히는 고민</h4><ul class="clean">${objections}</ul></div></div><div class="notice-strong" style="margin-top:14px"><strong>${esc(preview.ctaHint || '')}</strong><p>${esc(preview.closingArgument || '')}</p></div><div class="small-actions"><a class="button" href="${orderHref}">이 조건으로 결제 이어가기</a><a class="button secondary" href="${detailHref}">제품 설명 보기</a><a class="button ghost" href="${boardHref}">콘텐츠 허브 보기</a></div></div>`; }
  async function bindProductCheckoutForm(){
    const form = document.getElementById('product-checkout-form'); if (!form || !product) return;
    form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
      const data = new FormData(form);
      const memo = [String(data.get('note') || ''), String(data.get('phone') || '') ? `연락처: ${String(data.get('phone') || '')}` : '', String(data.get('link') || data.get('referenceUrl') || '') ? `참고 링크: ${String(data.get('link') || data.get('referenceUrl') || '')}` : '', String(data.get('urgency') || '') ? `긴급도: ${String(data.get('urgency') || '')}` : '', String(data.get('billing_note') || data.get('context') || '') ? `추가 요청: ${String(data.get('billing_note') || data.get('context') || '')}` : ''].filter(Boolean).join('\n');
      const payload = { product: String(data.get('product') || product.key), plan: String(data.get('plan') || 'Starter'), billing: String(data.get('billing') || 'one-time'), paymentMethod: String(data.get('paymentMethod') || 'toss'), company: String(data.get('company') || ''), name: String(data.get('name') || ''), email: String(data.get('email') || ''), note: memo };
      try {
        if (payload.paymentMethod === 'toss' && config.integration?.reserve_order_endpoint) {
          const reserve = await postIfConfigured(config.integration.reserve_order_endpoint, payload);
          if (!(reserve.mode === 'remote' && reserve.ok && reserve.json?.order)) throw new Error(reserve.json?.detail || reserve.text || '결제 준비 정보를 만들지 못했습니다.');
          applyStatePayload(reserve.json?.state);
          const order = reserve.json.order;
          const payment = paymentRuntime() || reserve.json?.payment || {};
          const successUrl = payment.successUrl || `${location.origin}${base}payments/toss/success/index.html`;
          const failUrl = payment.failUrl || `${location.origin}${base}payments/toss/fail/index.html`;
          if (payment.mock) { location.href = `${successUrl}?paymentKey=${encodeURIComponent('mock_' + order.id)}&orderId=${encodeURIComponent(order.id)}&amount=${encodeURIComponent(order.amount || 0)}`; return; }
          if (payment.enabled && payment.clientKey && window.TossPayments) {
            const toss = window.TossPayments(payment.clientKey);
            await toss.requestPayment('카드', { amount: Number(order.amount || 0), orderId: order.id, orderName: `${order.productName} ${order.plan}`, customerName: order.name, customerEmail: order.email, successUrl, failUrl });
            return;
          }
          throw new Error(explainPaymentUnavailable(payment));
        }
        const order = createOrder(payload);
        const remote = await postIfConfigured(config.integration?.order_endpoint, order);
        if (remote.mode === 'remote' && remote.ok) { applyStatePayload(remote.json?.state); await syncRemoteState(); }
        const boardLink = order.publicationIds?.[0] ? productBoardHref(order.product, order.publicationIds[0]) : `${base}products/${order.product}/board/index.html`;
        showResult('product-checkout-result', `<div class="order-result"><strong>결제와 제공 준비가 완료되었습니다.</strong><div>조회 코드: <span class="inline-code">${order.code}</span></div><div class="small-actions"><a href="${portalHref(order)}">고객 포털 확인</a><a href="${boardLink}">콘텐츠 허브 보기</a></div></div>`);
        renderPublicBoard(); renderProductBoard(); renderAdminSummary(); renderLiveStats(); renderWorkspaceCards();
      } catch (error) {
        showResult('product-checkout-result', `<strong>결제를 완료하지 못했습니다.</strong><br>${esc(createFriendlyError(error, '결제 오류'))}`);
      }
    }); });
  }
  async function bindDemoForm(){
    const form = document.getElementById('demo-form'); if (!form) return;
    form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
      const data = new FormData(form);
      const payload = { product: String(data.get('product') || ''), company: String(data.get('company') || ''), name: String(data.get('name') || ''), email: String(data.get('email') || ''), team: String(data.get('team') || ''), goal: String(data.get('goal') || ''), keywords: String(data.get('keywords') || ''), phone: String(data.get('phone') || ''), link: String(data.get('link') || data.get('referenceUrl') || ''), urgency: String(data.get('urgency') || '') };
      try {
        assert(validateProduct(payload.product), '제품을 선택하세요.');
        assert(clean(payload.company), '회사명을 입력하세요.');
        assert(clean(payload.name), '담당자명을 입력하세요.');
        assert(validateEmail(payload.email), '이메일 형식이 올바르지 않습니다.');
        assert(clean(payload.goal), '목표를 입력하세요.');
        const demoNeed = [payload.goal, payload.keywords ? `키워드: ${payload.keywords}` : '', payload.phone ? `연락처: ${payload.phone}` : '', payload.link ? `참고 링크: ${payload.link}` : '', payload.urgency ? `긴급도: ${payload.urgency}` : ''].filter(Boolean).join(' / ');
        const demoPayload = { product: payload.product, company: payload.company, name: payload.name, email: payload.email, team: payload.team, need: demoNeed, keywords: payload.keywords };
        let entry = null; let remoteSaved = false;
        const remote = await postIfConfigured(config.integration?.demo_endpoint, demoPayload);
        if (remote.mode === 'remote' && remote.ok && remote.json?.demo) { applyStatePayload(remote.json?.state); await syncRemoteState(); entry = remote.json.demo; remoteSaved = true; }
        else if (remote.mode === 'remote' && !remote.ok) { throw new Error(remote.json?.detail || remote.text || '데모 신청 정보를 저장하지 못했습니다.'); }
        else { entry = createDemo(demoPayload); }
        const preview = buildDemoPreviewHtml(payload, { orderHref:`${base}products/${payload.product}/index.html#order`, detailHref:`${base}products/${payload.product}/index.html`, boardHref:`${base}products/${payload.product}/board/index.html` }, { code: entry.code, remoteSaved, preview: remote.json?.preview });
        showResult('demo-result', preview);
        renderLiveStats(); renderWorkspaceCards(); renderAdminSummary();
      } catch (error) { showResult('demo-result', `<strong>샘플 결과를 준비하지 못했습니다.</strong><br>${esc(createFriendlyError(error, '데모 시연 오류가 발생했습니다.'))}`); }
    }); });
  }
  async function bindContactForm(){
    const form = document.getElementById('contact-form'); if (!form) return;
    form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
      const data = new FormData(form);
      const payload = { product: String(data.get('product') || ''), company: String(data.get('company') || ''), name: String(data.get('name') || ''), email: String(data.get('email') || ''), issue: [String(data.get('issue') || ''), String(data.get('phone') || '') ? `연락처: ${String(data.get('phone') || '')}` : '', String(data.get('link') || data.get('referenceUrl') || '') ? `참고 링크: ${String(data.get('link') || data.get('referenceUrl') || '')}` : '', String(data.get('urgency') || '') ? `긴급도: ${String(data.get('urgency') || '')}` : '', String(data.get('reply_time') || data.get('replyWindow') || '') ? `희망 회신 시간: ${String(data.get('reply_time') || data.get('replyWindow') || '')}` : ''].filter(Boolean).join('\n') };
      try {
        const entry = createContact(payload);
        const remote = await postIfConfigured(config.integration?.contact_endpoint, entry);
        if (remote.mode === 'remote' && remote.ok) { applyStatePayload(remote.json?.state); await syncRemoteState(); }
        const remoteLine = remote.mode === 'remote' && remote.ok ? '추가 확인 요청이 정상적으로 저장되었습니다.' : remote.mode === 'remote-failed' ? '연결 확인이 잠시 지연되고 있지만 추가 확인 요청은 저장되었습니다.' : '지금 이 화면에서는 추가 확인 요청이 저장되고, 연결이 준비되면 같은 흐름으로 안내를 이어갈 수 있습니다.';
        showResult('contact-result', `<strong>추가 확인 요청이 안전하게 저장되었습니다.</strong><br>확인 코드: <span class="inline-code">${entry.code}</span><br>담당자: ${esc(entry.name || '미입력')}<br>${remoteLine}<br><a href="${entry.product ? `${base}products/${entry.product}/index.html` : `${base}products/index.html`}">관련 제품 보기</a>`);
        renderAdminSummary(); renderWorkspaceCards(); form.reset();
      } catch (error) { showResult('contact-result', `<strong>추가 확인 요청을 저장하지 못했습니다.</strong><br>${esc(createFriendlyError(error, '추가 확인 요청 저장 중 오류가 발생했습니다.'))}`); }
    }); });
  }
  async function bindCheckoutForm(){
    const form = document.getElementById('checkout-form'); if (!form) return;
    form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
      const data = new FormData(form);
      const note = [String(data.get('note') || ''), String(data.get('phone') || '') ? `연락처: ${String(data.get('phone') || '')}` : '', String(data.get('link') || data.get('referenceUrl') || '') ? `참고 링크: ${String(data.get('link') || data.get('referenceUrl') || '')}` : '', String(data.get('urgency') || '') ? `긴급도: ${String(data.get('urgency') || '')}` : '', String(data.get('reply_time') || data.get('replyWindow') || '') ? `희망 회신 시간: ${String(data.get('reply_time') || data.get('replyWindow') || '')}` : ''].filter(Boolean).join('\n');
      const payload = { product: String(data.get('product') || ''), plan: String(data.get('plan') || 'Starter'), billing: String(data.get('billing') || 'one-time'), paymentMethod: String(data.get('paymentMethod') || 'toss'), company: String(data.get('company') || ''), name: String(data.get('name') || ''), email: String(data.get('email') || ''), note };
      try {
        if (payload.paymentMethod === 'toss' && config.integration?.reserve_order_endpoint) {
          const reserve = await postIfConfigured(config.integration.reserve_order_endpoint, payload);
          if (!(reserve.mode === 'remote' && reserve.ok && reserve.json?.order)) throw new Error(reserve.json?.detail || reserve.text || '결제 준비 정보를 만들지 못했습니다.');
          applyStatePayload(reserve.json?.state);
          const order = reserve.json.order;
          const payment = paymentRuntime() || reserve.json?.payment || {};
          const successUrl = payment.successUrl || `${location.origin}${base}payments/toss/success/index.html`;
          const failUrl = payment.failUrl || `${location.origin}${base}payments/toss/fail/index.html`;
          if (payment.mock) { location.href = `${successUrl}?paymentKey=${encodeURIComponent('mock_' + order.id)}&orderId=${encodeURIComponent(order.id)}&amount=${encodeURIComponent(order.amount || 0)}`; return; }
          if (payment.enabled && payment.clientKey && window.TossPayments) {
            const toss = window.TossPayments(payment.clientKey);
            await toss.requestPayment('카드', { amount: Number(order.amount || 0), orderId: order.id, orderName: `${order.productName} ${order.plan}`, customerName: order.name, customerEmail: order.email, successUrl, failUrl });
            return;
          }
          throw new Error(explainPaymentUnavailable(payment));
        }
        const order = createOrder(payload);
        const remote = await postIfConfigured(config.integration?.order_endpoint, order);
        if (remote.mode === 'remote' && remote.ok) { applyStatePayload(remote.json?.state); await syncRemoteState(); }
        const remoteLine = remote.mode === 'remote' && remote.ok ? '결제 직후 결과 전달 흐름이 자동으로 준비되었습니다.' : remote.mode === 'remote-failed' ? '연결 확인이 잠시 지연되고 있지만 결제 정보는 저장되었습니다.' : '지금 이 화면에서는 결제 정보가 저장되고, 같은 흐름으로 결과 전달까지 이어집니다.';
        const boardLink = order.publicationIds?.[0] ? productBoardHref(order.product, order.publicationIds[0]) : `${base}products/${order.product}/board/index.html`;
        showResult('checkout-result', `<div class="order-result"><strong>결제 접수가 완료되었습니다.</strong><div>조회 코드: <span class="inline-code">${order.code}</span></div><div>결제 상태: <span class="status-pill ${order.paymentStatus === 'paid' ? 'status-paid' : 'status-pending'}">${paymentStatusLabel(order.paymentStatus)}</span></div><div>결과 상태: <span class="status-pill ${order.status === 'published' ? 'status-published' : order.status === 'delivered' ? 'status-delivered' : 'status-draft'}">${orderStatusLabel(order.status)}</span></div><div>${remoteLine}</div><div class="small-actions"><a href="${portalHref(order)}">고객 포털 확인</a><a href="${boardLink}">콘텐츠 허브 보기</a><a href="${base}products/${order.product}/index.html">자세히 보기</a></div></div>`);
        renderPublicBoard(); renderProductBoard(); renderAdminSummary(); renderLiveStats(); renderWorkspaceCards(); form.reset();
      } catch (error) { showResult('checkout-result', `<strong>결제 접수에 실패했습니다.</strong><br>${esc(createFriendlyError(error, '결제 중 오류가 발생했습니다.'))}`); }
    }); });
  }
    async function bindPortalLookup() { const form = document.getElementById('portal-lookup-form'); if (!form) return; const params = new URLSearchParams(location.search); const emailEl = form.querySelector('input[name="email"]'); const codeEl = form.querySelector('input[name="code"]'); if (params.get('email') && emailEl) emailEl.value = params.get('email'); if (params.get('code') && codeEl) codeEl.value = params.get('code'); form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => { const data = new FormData(form); const payload = { email: normalizeEmail(String(data.get('email') || '')), code: normalizeCode(String(data.get('code') || '')) }; try { const lookup = createLookup(payload); const remote = await postIfConfigured(config.integration?.portal_lookup_endpoint, lookup); if (remote.mode === 'remote' && remote.ok) { applyStatePayload(remote.json?.state); await syncRemoteState(); } const order = (remote.mode === 'remote' && remote.ok && remote.json?.order) ? remote.json.order : lookupOrder(payload.email, payload.code); const publications = (remote.mode === 'remote' && remote.ok && Array.isArray(remote.json?.publications)) ? remote.json.publications : read(STORE.publications).filter((item) => (order?.publicationIds || []).includes(item.id)); if (!order) { showResult('portal-result', `<strong>일치하는 결제 접수를 찾지 못했습니다.</strong><br>이메일 또는 조회 코드를 다시 확인하세요.`); const mock = document.getElementById('portal-mock'); if (mock) mock.innerHTML = '<div class="empty-box">일치하는 결제 정보가 없습니다. 입력한 내용을 다시 확인해 주세요.</div>'; renderAdminSummary(); return; } showResult('portal-result', `<strong>조회가 완료되었습니다.</strong><br>조회 코드 <span class="inline-code">${order.code}</span> 기준으로 결과 전달 정보를 불러왔습니다.`); const mock = document.getElementById('portal-mock'); const resultPack = order.resultPack || { summary:'', outputs:[] }; const outputHtml = buildRichOutputList(resultPack.outputs || []); const issuanceHtml = buildBundleList(resultPack.issuanceBundle || []); const deliveryAssetHtml = buildBundleList(resultPack.deliveryAssets || []); const valueHtml = buildTextList([...(resultPack.quickWins || []), ...(resultPack.valueDrivers || []), ...(resultPack.successMetrics || [])]); const priorityHtml = buildTextList(resultPack.prioritySequence || []); const expertHtml = buildTextList(resultPack.expertNotes || []); const objectionsHtml = buildTextList(resultPack.objectionHandling || []); const scoreHtml = renderScorecardHtml(resultPack.scorecard); if (mock) mock.innerHTML = `<article class="portal-card"><div class="portal-meta"><div class="meta"><strong>제품</strong><span>${esc(order.productName)}</span></div><div class="meta"><strong>플랜</strong><span>${esc(order.plan)} · ${esc(order.price)}</span></div><div class="meta"><strong>결제 상태</strong><span>${paymentStatusLabel(order.paymentStatus)}</span></div><div class="meta"><strong>결과 상태</strong><span>${orderStatusLabel(order.status)}</span></div></div><div class="notice-strong"><strong>${esc(resultPack.outcomeHeadline || '결과 전달 요약')}</strong><p>${esc(resultPack.summary || '')}</p><p>${esc(resultPack.executiveSummary || '')}</p><p>${esc(resultPack.valueNarrative || '')}</p><p>${esc(resultPack.buyerDecisionReason || '')}</p></div>${scoreHtml}<div class="split-two"><div><h4>받아보실 자료</h4><ul class="output-list">${outputHtml}</ul><h4 style="margin-top:14px">발행 준비 상태</h4><ul class="output-list">${issuanceHtml || '<li><strong>준비 중</strong><span>발행 정보가 아직 없습니다.</span></li>'}</ul><h4 style="margin-top:14px">전달 자산</h4><ul class="output-list">${deliveryAssetHtml || '<li><strong>준비 중</strong><span>전달 자산 정보가 아직 없습니다.</span></li>'}</ul></div><div><h4>이 결과가 바로 도움이 되는 이유</h4><ul class="clean">${valueHtml}</ul><h4 style="margin-top:14px">먼저 움직일 순서</h4><ul class="clean">${priorityHtml}</ul><h4 style="margin-top:14px">전문가 기준</h4><ul class="clean">${expertHtml}</ul><h4 style="margin-top:14px">자주 막히는 고민</h4><ul class="clean">${objectionsHtml}</ul><h4 style="margin-top:14px">함께 확인할 공개 글</h4><ul class="output-list">${publications.map((item) => `<li><strong>${esc(item.title)}</strong><span><a href="${productBoardHref(order.product, item.id)}">제품 글 보기</a> · <a href="${publicBoardHref(item.id)}">전체 글 보기</a></span></li>`).join('') || '<li><strong>준비 중</strong><span>연결된 게시물이 없습니다.</span></li>'}</ul></div></div><div class="small-actions"><a href="${base}products/${order.product}/index.html">자세히 보기</a><a href="${base}products/${order.product}/board/index.html">콘텐츠 허브 보기</a><a href="${base}contact/index.html?product=${order.product}">추가 확인 요청</a></div></article>`; renderAdminSummary(); } catch (error) { showResult('portal-result', `<strong>조회하지 못했습니다.</strong><br>${esc(createFriendlyError(error, '결과 조회 중 오류가 발생했습니다.'))}`); const mock = document.getElementById('portal-mock'); if (mock) mock.innerHTML = '<div class="empty-box">조회 조건을 다시 확인해 주세요.</div>'; } }); }); if (params.get('email') || params.get('code')) form.requestSubmit(); }
  async function bindPaymentResultPages(){ if (pageKey === 'payment-success') { const params = new URLSearchParams(location.search); const paymentKey = params.get('paymentKey') || ''; const orderId = params.get('orderId') || ''; const amount = Number(params.get('amount') || 0); if (!config.integration?.toss_confirm_endpoint || !paymentKey || !orderId || !amount) { showResult('payment-success-result', '<strong>결제 승인 정보를 확인하지 못했습니다.</strong><br>paymentKey, orderId, amount를 다시 확인하세요.'); return; } const remote = await postIfConfigured(config.integration.toss_confirm_endpoint, { paymentKey, orderId, amount }); if (remote.mode === 'remote' && remote.ok && remote.json?.order) { applyStatePayload(remote.json?.state); const order = remote.json.order; const boardLink = order.publicationIds?.[0] ? productBoardHref(order.product, order.publicationIds[0]) : `${base}products/${order.product}/board/index.html`; showResult('payment-success-result', `<strong>결제가 완료되었습니다.</strong><br>조회 코드 <span class="inline-code">${esc(order.code)}</span> 기준으로 전달 자료를 바로 확인하실 수 있습니다. 관련 콘텐츠도 함께 둘러보실 수 있습니다.<div class="small-actions"><a href="${portalHref(order)}">결과 전달 확인</a><a href="${boardLink}">콘텐츠 허브 보기</a></div>`); } else { showResult('payment-success-result', `<strong>결제 확인을 완료하지 못했습니다.</strong><br>${esc(remote.json?.detail || remote.text || remote.error || '승인 요청 실패')}`); } } if (pageKey === 'payment-fail') { const params = new URLSearchParams(location.search); showResult('payment-fail-result', `<strong>결제가 완료되지 않았습니다.</strong><br>오류 코드: <span class="inline-code">${esc(params.get('code') || '없음')}</span><br>사유: ${esc(params.get('message') || '사유 미제공')}`); } }
  function bindAdminActions(){ const root = document.getElementById('admin-console'); if (!root) return; root.addEventListener('click', async (event) => { const button = event.target.closest('[data-admin-action]'); if (!button) return; const action = button.dataset.adminAction; const orderId = button.dataset.orderId; try { if (action === 'seed-demo') { const remote = await postIfConfigured(config.integration?.admin_seed_endpoint, {}); if (remote.mode === 'remote' && remote.ok) { applyStatePayload(remote.json?.state); await syncRemoteState(); showResult('admin-action-result', '샘플 데이터를 생성했습니다.'); } else { const order = createOrder({product:'veridion', plan:'Growth', billing:'one-time', paymentMethod:'toss', company:'Demo Company', name:'테스터', email:'demo@nv0.kr', note:'시드 결제'}); createDemo({product:'clearport', company:'Demo Company', name:'테스터', email:'demo@nv0.kr', team:'3명 팀', need:'정상작동 확인'}); createContact({product:'grantops', company:'Demo Company', email:'demo@nv0.kr', issue:'제출 일정 추가 확인'}); showResult('admin-action-result', `샘플 데이터를 생성했습니다. 대표 조회 코드 <span class="inline-code">${order.code}</span>`); } } else if (action === 'reset-all') { const remote = await postIfConfigured(config.integration?.admin_reset_endpoint, {}); if (remote.mode === 'remote' && remote.ok) { applyStatePayload(remote.json?.state); await syncRemoteState(); } else { Object.values(STORE).forEach((key) => localStorage.removeItem(key)); ensureSeedData(); } showResult('admin-action-result', '엔진 데이터를 초기화했습니다.'); } else if (action === 'republish-latest') { showResult('admin-action-result', '최신 자동발행 상태를 점검했습니다. 필요하면 주문별 재발행을 사용하세요.'); } else if (orderId) { if (action === 'advance') { const remote = await postIfConfigured(actionEndpoint(config.integration?.admin_advance_endpoint, orderId), {orderId}); if (remote.mode === 'remote' && remote.ok) { applyStatePayload(remote.json?.state); await syncRemoteState(); } else { advanceOrder(orderId); } showResult('admin-action-result', '결과 전달 상태를 다시 확인했습니다.'); } if (action === 'toggle-payment') { const remote = await postIfConfigured(actionEndpoint(config.integration?.admin_toggle_payment_endpoint, orderId), {orderId}); if (remote.mode === 'remote' && remote.ok) { applyStatePayload(remote.json?.state); await syncRemoteState(); } else { toggleOrderPayment(orderId); } showResult('admin-action-result', '진행 상태를 전환했습니다.'); } if (action === 'republish') { const remote = await postIfConfigured(actionEndpoint(config.integration?.admin_republish_endpoint, orderId), {orderId}); if (remote.mode === 'remote' && remote.ok) { applyStatePayload(remote.json?.state); await syncRemoteState(); const updated = read(STORE.orders).find((item) => item.id === orderId); showResult('admin-action-result', `조회 코드 <span class="inline-code">${updated?.code || ''}</span> 기준으로 공개 콘텐츠를 다시 생성했습니다.`); } else { const updated = republishOrder(orderId); showResult('admin-action-result', `조회 코드 <span class="inline-code">${updated?.code || ''}</span> 기준으로 공개 콘텐츠를 다시 생성했습니다.`); } } } } catch (error) { const msg = createFriendlyError(error, '관리자 작업 중 오류가 발생했습니다.'); showResult('admin-action-result', `${esc(msg)}${String(msg).includes('토큰') ? ' 관리자 토큰을 입력한 뒤 다시 시도하세요.' : ''}`); } renderAdminSummary(); renderPublicBoard(); renderProductBoard(); renderLiveStats(); renderWorkspaceCards(); }); }
  document.addEventListener('DOMContentLoaded', async () => { await loadSystemConfig(); if ((pageKey === 'checkout' || pageKey === 'product') && paymentRuntime()?.enabled && !paymentRuntime()?.mock) await loadTossScript(); const stateSynced = await syncRemoteState(); if (!stateSynced) { const boardSynced = await loadBoardFeed(); if (!boardSynced) ensureSeedData(); } else if (!read(STORE.publications).length) { const boardSynced = await loadBoardFeed(); if (!boardSynced) ensureSeedData(); } else { ensureSeedData(); } renderHeader(); renderFooter(); buildHomeProducts(); buildModuleMatrix(); fillProductSlots(); buildPlans(); setPrefills(); renderPublicBoard(); renderProductBoard(); renderLiveStats(); renderWorkspaceCards(); renderProductServices(); renderServiceCatalog(); bindProductDemoForm(); await bindProductCheckoutForm(); bindDemoForm(); bindCheckoutForm(); bindContactForm(); bindPortalLookup(); bindAdminTokenControls(); bindQuickDemoButtons(); await bindPaymentResultPages(); await bootstrapAdminGate(); renderAdminSummary(); bindAdminActions(); });
  window.NV0App = { read, write, lookupOrder, createOrder, createDemo, createContact, createLookup, ensureSeedData, renderAdminSummary, advanceOrder, toggleOrderPayment, republishOrder, validateEmail, validateProduct, validatePlan, setAdminToken, getAdminToken, loadSystemConfig, publicBoardHref, productBoardHref, portalHref };
})();