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
    reports: 'nv0-engine-reports',
    publications: 'nv0-engine-publications',
    submissions: 'nv0-public-submissions',
  };
  const AUTH_KEY = 'nv0-admin-token';
  const REPORT_SESSION_KEYS = { veridion:'nv0-veridion-last-report', clearport:'nv0-clearport-last-report', grantops:'nv0-grantops-last-report', draftforge:'nv0-draftforge-last-report' };
  const runtime = { systemConfig: null };
  function getAdminToken(){ try { return sessionStorage.getItem(AUTH_KEY) || ''; } catch { return ''; } }
  function getLastProductReport(key){ try { return JSON.parse(sessionStorage.getItem(REPORT_SESSION_KEYS[key] || '') || 'null'); } catch { return null; } }
  function setLastProductReport(key, value){ try { const storageKey = REPORT_SESSION_KEYS[key]; if (!storageKey) return; if (value) sessionStorage.setItem(storageKey, JSON.stringify(value)); else sessionStorage.removeItem(storageKey); } catch {} }
  function getLastVeridionReport(){ return getLastProductReport('veridion'); }
  function setLastVeridionReport(value){ setLastProductReport('veridion', value); }
  function veridionScanEndpoint(){ return config.integration?.veridion_scan_endpoint || '/api/public/veridion/scan'; }
  function clearportAnalyzeEndpoint(){ return config.integration?.clearport_analyze_endpoint || '/api/public/clearport/analyze'; }
  function grantopsAnalyzeEndpoint(){ return config.integration?.grantops_analyze_endpoint || '/api/public/grantops/analyze'; }
  function draftforgeAnalyzeEndpoint(){ return config.integration?.draftforge_analyze_endpoint || '/api/public/draftforge/analyze'; }
  function ensureHiddenField(form, name, value){ if (!form) return; let input = form.querySelector(`input[name="${name}"]`); if (!input) { input = document.createElement('input'); input.type = 'hidden'; input.name = name; form.appendChild(input); } input.value = value || ''; }
  function structuredVeridionNote(values, report){ const issues = (report?.issues || []).slice(0,3).map((item)=> item.title).join(', '); return ['체험 목표: ' + (values.focus || '준법 리스크 우선순위 정리'), values.website ? `점검 URL: ${values.website}` : '', values.industry ? `업종: ${values.industry}` : '', values.market ? `운영 국가: ${values.market}` : '', report?.code ? `리포트 코드: ${report.code}` : '', report?.id ? `리포트 ID: ${report.id}` : '', report?.stats?.explorationRate !== undefined ? `탐색률: ${report.stats.explorationRate}%` : '', report?.stats?.priorityCoverage !== undefined ? `핵심 페이지 커버리지: ${report.stats.priorityCoverage}%` : '', issues ? `추가 요청: ${issues}` : ''].filter(Boolean).join('\n'); }
  function structuredClearportNote(values, report){ const issues = (report?.issues || []).slice(0,3).map((item)=> item.title).join(', '); return ['체험 목표: 제출 누락과 회신 지연 줄이기', values.submissionType ? `제출 유형: ${values.submissionType}` : '', values.targetOrg ? `제출처: ${values.targetOrg}` : '', report?.code ? `리포트 코드: ${report.code}` : '', report?.id ? `리포트 ID: ${report.id}` : '', report?.stats?.readinessRate !== undefined ? `준비도: ${report.stats.readinessRate}%` : '', report?.stats?.criticalMissing !== undefined ? `핵심 누락: ${report.stats.criticalMissing}건` : '', issues ? `추가 요청: ${issues}` : ''].filter(Boolean).join('\n'); }
  function structuredGrantopsNote(values, report){ const issues = (report?.issues || []).slice(0,3).map((item)=> item.title).join(', '); return ['체험 목표: 제출 일정 안정화', values.projectName ? `사업/공모명: ${values.projectName}` : '', values.progress ? `현재 진행률: ${values.progress}` : '', report?.code ? `리포트 코드: ${report.code}` : '', report?.id ? `리포트 ID: ${report.id}` : '', report?.stats?.readinessScore !== undefined ? `준비도: ${report.stats.readinessScore}점` : '', report?.stats?.daysLeft !== undefined ? `마감 상태: D-${report.stats.daysLeft}` : '', issues ? `추가 요청: ${issues}` : ''].filter(Boolean).join('\n'); }
  function structuredDraftforgeNote(values, report){ const issues = (report?.issues || []).slice(0,3).map((item)=> item.title).join(', '); return ['체험 목표: 최종본 기준 확정', values.docType ? `문서 종류: ${values.docType}` : '', values.approvalSteps ? `승인 단계: ${values.approvalSteps}` : '', report?.code ? `리포트 코드: ${report.code}` : '', report?.id ? `리포트 ID: ${report.id}` : '', report?.stats?.controlScore !== undefined ? `문서 통제 점수: ${report.stats.controlScore}점` : '', report?.stats?.handoffRisk ? `인계 위험: ${report.stats.handoffRisk}` : '', issues ? `추가 요청: ${issues}` : ''].filter(Boolean).join('\n'); }
  function structuredProductReportNote(key, values, report){ return key === 'veridion' ? structuredVeridionNote(values, report) : key === 'clearport' ? structuredClearportNote(values, report) : key === 'grantops' ? structuredGrantopsNote(values, report) : structuredDraftforgeNote(values, report); }
  function applyProductReportToCheckout(key, values, report){ const form = document.getElementById('product-checkout-form'); if (!form) return; ensureHiddenField(form, 'reportId', report?.id || ''); ensureHiddenField(form, 'reportCode', report?.code || ''); const noteInput = form.querySelector('input[name="note"]'); if (noteInput) noteInput.value = structuredProductReportNote(key, values || {}, report || {}); const linkInput = form.querySelector('input[name="link"]'); if (linkInput && values?.website) linkInput.value = values.website; }
  function applyVeridionReportToCheckout(values, report){ applyProductReportToCheckout('veridion', values, report); }
  function renderVeridionRemoteReport(report, values){ const stats = report?.stats || {}; const issues = Array.isArray(report?.issues) ? report.issues : []; const pages = Array.isArray(report?.pages) ? report.pages : []; const copies = Array.isArray(report?.copySuggestions) ? report.copySuggestions : []; const quality = Array.isArray(report?.quality?.gates) ? report.quality.gates : []; return `<div class="demo-result-shell">${demoSummaryHeader('Veridion 실제 탐색 결과', report?.summary || `${values?.website || '입력 URL'} 기준으로 실제 공개 페이지를 읽어 만든 결과입니다.`, Math.max(0, Math.min(100, Math.round(Number(stats.priorityCoverage || stats.explorationRate || 0)))))}${renderKpis([{ value:`${stats.explorationRate ?? 0}%`, label:'탐색률', note:`발견 ${stats.discovered ?? 0}개 중 실제 읽은 ${stats.fetched ?? 0}개 기준입니다.` },{ value:`${stats.priorityCoverage ?? 0}%`, label:'핵심 페이지 커버리지', note:`홈·정책·결제·문의 같은 우선 구간 기준입니다.` },{ value:`${issues.filter((item)=>item.level==='high').length}건`, label:'즉시 조치', note:`리포트 코드 ${esc(report?.code || '-')}` }])}<div class="demo-section-stack"><h4>먼저 손볼 이슈</h4>${renderDemoAlerts(issues.map((item)=>({ level:item.level, title:item.title, detail:item.detail })))}<h4>문구 수정안</h4>${renderCopyCards(copies.map((item)=>({ label:item.label || '수정안', copy:`적용 위치: ${item.pageUrl || values?.website || '-'}\nBefore: ${item.before || '-'}\nAfter: ${item.after || '-'}` })))}<h4>페이지별 점검 결과</h4>${renderDemoTable(pages.slice(0,6).map((item)=>[item.title || item.url, `${item.pageType || 'content'} · 폼 ${item.forms || 0}개 · 내부링크 ${item.internalLinks || 0}개`]))}<h4>리포트 발행 상태</h4><div class="demo-table">${quality.map((item)=>`<div class="demo-table-row"><strong>${esc(item.label)}</strong><span>${esc(item.ok ? '통과 · ' + item.detail : '보완 필요 · ' + item.detail)}</span></div>`).join('')}</div></div><div class="demo-save-box"><strong>리포트 발행 준비</strong><br>${esc(report?.issuance?.readyReason || '리포트 발행 상태를 확인했습니다.')}<br>리포트 코드 <span class="inline-code">${esc(report?.code || '-')}</span></div></div>`; }
  function renderClearportRemoteReport(report, values){ const stats = report?.stats || {}; const issues = Array.isArray(report?.issues) ? report.issues : []; const checklist = Array.isArray(report?.documentChecklist) ? report.documentChecklist : []; const copies = Array.isArray(report?.copySuggestions) ? report.copySuggestions : []; const quality = Array.isArray(report?.quality?.gates) ? report.quality.gates : []; return `<div class="demo-result-shell">${demoSummaryHeader('ClearPort 실제 제출 준비 결과', report?.summary || `${values?.targetOrg || '제출처'} 기준 제출 준비도를 계산한 결과입니다.`, Math.round(Number(stats.readinessRate || 0)))}${renderKpis([{ value:`${stats.readinessRate ?? 0}%`, label:'준비도', note:`확보 ${stats.securedDocs ?? 0}종 / 기준 ${stats.requiredDocs ?? 0}종` },{ value:`${stats.criticalMissing ?? 0}건`, label:'핵심 누락', note:`접수를 멈추는 축을 먼저 분리했습니다.` },{ value:stats.daysLeft === null || stats.daysLeft === undefined ? '미입력' : `D-${stats.daysLeft}`, label:'마감 상태', note:`리포트 코드 ${esc(report?.code || '-')}` }])}<div class="demo-section-stack"><h4>먼저 손볼 이슈</h4>${renderDemoAlerts(issues.map((item)=>({ level:item.level, title:item.title, detail:item.detail })))}<h4>서류 체크리스트</h4>${renderDemoTable(checklist.map((item)=>[item.label, `${item.status} · ${item.priority} · ${item.detail}`]))}<h4>바로 쓸 회신 문장</h4>${renderCopyCards(copies.map((item)=>({ label:item.label || '템플릿', copy:`적용 대상: ${item.appliesTo || '-'}\nBefore: ${item.before || '-'}\nAfter: ${item.after || '-'}` })))}<h4>리포트 발행 상태</h4><div class="demo-table">${quality.map((item)=>`<div class="demo-table-row"><strong>${esc(item.label)}</strong><span>${esc(item.ok ? '통과 · ' + item.detail : '보완 필요 · ' + item.detail)}</span></div>`).join('')}</div></div><div class="demo-save-box"><strong>리포트 발행 준비</strong><br>${esc(report?.issuance?.readyReason || '리포트 발행 상태를 확인했습니다.')}<br>리포트 코드 <span class="inline-code">${esc(report?.code || '-')}</span></div></div>`; }
  function renderGrantopsRemoteReport(report, values){ const stats = report?.stats || {}; const issues = Array.isArray(report?.issues) ? report.issues : []; const schedule = Array.isArray(report?.schedule) ? report.schedule : []; const roles = Array.isArray(report?.rolePlan) ? report.rolePlan : []; const copies = Array.isArray(report?.copySuggestions) ? report.copySuggestions : []; const quality = Array.isArray(report?.quality?.gates) ? report.quality.gates : []; return `<div class="demo-result-shell">${demoSummaryHeader('GrantOps 실제 제출 운영 결과', report?.summary || `${values?.projectName || '입력 사업'} 기준 역산 일정 결과입니다.`, Math.round(Number(stats.readinessScore || 0)))}${renderKpis([{ value:`${stats.readinessScore ?? 0}점`, label:'준비도', note:`마감과 진행률을 함께 반영했습니다.` },{ value:stats.daysLeft === null || stats.daysLeft === undefined ? '미입력' : `D-${stats.daysLeft}`, label:'마감 상태', note:`핵심 경로 ${stats.criticalPathSteps ?? 0}단계` },{ value:`${stats.riskLevel || '확인'}`, label:'제출 리스크', note:`리포트 코드 ${esc(report?.code || '-')}` }])}<div class="demo-section-stack"><h4>먼저 손볼 이슈</h4>${renderDemoAlerts(issues.map((item)=>({ level:item.level, title:item.title, detail:item.detail })))}<h4>역산 일정</h4>${renderDemoTable(schedule.map((item)=>[item.label, `${item.date || '-'} · ${item.detail || ''}`]))}<h4>역할 분담</h4>${renderDemoTable(roles.map((item)=>[item.label, `${item.owner || '-'} · ${item.detail || ''}`]))}<h4>요청 문장</h4>${renderCopyCards(copies.map((item)=>({ label:item.label || '템플릿', copy:`적용 대상: ${item.appliesTo || '-'}\nBefore: ${item.before || '-'}\nAfter: ${item.after || '-'}` })))}<h4>리포트 발행 상태</h4><div class="demo-table">${quality.map((item)=>`<div class="demo-table-row"><strong>${esc(item.label)}</strong><span>${esc(item.ok ? '통과 · ' + item.detail : '보완 필요 · ' + item.detail)}</span></div>`).join('')}</div></div><div class="demo-save-box"><strong>리포트 발행 준비</strong><br>${esc(report?.issuance?.readyReason || '리포트 발행 상태를 확인했습니다.')}<br>리포트 코드 <span class="inline-code">${esc(report?.code || '-')}</span></div></div>`; }
  function renderDraftforgeRemoteReport(report, values){ const stats = report?.stats || {}; const issues = Array.isArray(report?.issues) ? report.issues : []; const matrix = Array.isArray(report?.versionMatrix) ? report.versionMatrix : []; const copies = Array.isArray(report?.copySuggestions) ? report.copySuggestions : []; const quality = Array.isArray(report?.quality?.gates) ? report.quality.gates : []; return `<div class="demo-result-shell">${demoSummaryHeader('DraftForge 실제 문서 운영 결과', report?.summary || `${values?.docType || '입력 문서'} 기준 버전 운영 결과입니다.`, Math.round(Number(stats.controlScore || 0)))}${renderKpis([{ value:`${stats.controlScore ?? 0}점`, label:'문서 통제 점수', note:`최신본 기준과 승인 구조를 반영했습니다.` },{ value:`${stats.approvalSteps ?? 1}단계`, label:'승인 단계', note:`검토/배포 분기 구조입니다.` },{ value:`${stats.handoffRisk || '확인'}`, label:'인계 위험', note:`리포트 코드 ${esc(report?.code || '-')}` }])}<div class="demo-section-stack"><h4>먼저 손볼 이슈</h4>${renderDemoAlerts(issues.map((item)=>({ level:item.level, title:item.title, detail:item.detail })))}<h4>버전 관리 기준표</h4>${renderDemoTable(matrix.map((item)=>[item.label, `${item.rule || '-'} · ${item.detail || ''}`]))}<h4>검토/발송 문장</h4>${renderCopyCards(copies.map((item)=>({ label:item.label || '템플릿', copy:`적용 대상: ${item.appliesTo || '-'}\nBefore: ${item.before || '-'}\nAfter: ${item.after || '-'}` })))}<h4>리포트 발행 상태</h4><div class="demo-table">${quality.map((item)=>`<div class="demo-table-row"><strong>${esc(item.label)}</strong><span>${esc(item.ok ? '통과 · ' + item.detail : '보완 필요 · ' + item.detail)}</span></div>`).join('')}</div></div><div class="demo-save-box"><strong>리포트 발행 준비</strong><br>${esc(report?.issuance?.readyReason || '리포트 발행 상태를 확인했습니다.')}<br>리포트 코드 <span class="inline-code">${esc(report?.code || '-')}</span></div></div>`; }
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
  async function verifyAdminTokenForEntry(){
    const token = clean(getAdminToken());
    if (!token) return false;
    const url = config.integration?.admin_validate_endpoint || config.integration?.admin_state_endpoint || '';
    if (!url) return true;
    try {
      const res = await fetch(url, { headers: headersFor(url, { 'Accept':'application/json' }) });
      return res.ok;
    } catch {
      return false;
    }
  }
  async function requestAdminAccess(redirect = true){
    const current = getAdminToken();
    const input = window.prompt('관리자 비밀키를 입력하세요.', current || '');
    if (input === null) return false;
    const token = clean(input);
    if (!token) { window.alert('비밀키를 입력해야 관리자 화면으로 들어갈 수 있습니다.'); return false; }
    setAdminToken(token);
    const ok = await verifyAdminTokenForEntry();
    if (!ok) {
      setAdminToken('');
      window.alert('비밀키가 맞지 않습니다. 다시 확인해 주세요.');
      return false;
    }
    if (redirect) window.location.href = `${base}admin/index.html`;
    return true;
  }
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
    if (Array.isArray(state.reports)) write(STORE.reports, state.reports);
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
  function bindAdminTokenControls(){
    const input = document.getElementById('admin-token-input');
    const save = document.getElementById('admin-token-save');
    const clear = document.getElementById('admin-token-clear');
    if (input) input.value = getAdminToken();
    if (save) save.addEventListener('click', async () => {
      setAdminToken(input?.value || '');
      await bootstrapAdminGate();
      renderAdminSummary();
      renderPublicBoard();
      renderProductBoard();
      renderLiveStats();
      renderWorkspaceCards();
      const shell = document.getElementById('admin-shell');
      if (shell && shell.style.display === 'none') {
        showResult('admin-action-result', '관리자 비밀키를 다시 확인해 주세요.');
      }
    });
    if (clear) clear.addEventListener('click', async () => {
      setAdminToken('');
      if (input) input.value = '';
      await bootstrapAdminGate();
      showResult('admin-action-result', '관리자 비밀키를 지웠습니다.');
    });
  }

  async function bootstrapAdminGate(){
    const shell = document.getElementById('admin-shell');
    const gate = document.getElementById('admin-gate-result');
    if (!shell) return true;
    const adminCfg = runtime.systemConfig?.admin || {};
    const required = Boolean(adminCfg.required);
    const hasToken = Boolean(getAdminToken());
    if (!required) {
      shell.style.display = '';
      if (gate) gate.innerHTML = hasToken ? '운영 메뉴를 열었습니다. 현재 저장 상태를 불러왔습니다.' : '로컬 검토용 운영 메뉴가 열려 있습니다. 운영 배포에서는 비밀키로 보호됩니다.';
      if (hasToken) await syncRemoteState();
      return true;
    }
    if (!hasToken) {
      shell.style.display = 'none';
      if (gate) gate.innerHTML = '관리자 비밀키를 입력하면 운영 메뉴가 열립니다.';
      return false;
    }
    const synced = await syncRemoteState();
    if (!synced) {
      shell.style.display = 'none';
      if (gate) gate.innerHTML = '관리자 비밀키가 없거나 맞지 않습니다. 다시 입력해 주세요.';
      return false;
    }
    shell.style.display = '';
    if (gate) gate.innerHTML = '운영 메뉴를 열었습니다. 서버 상태를 불러왔습니다.';
    return true;
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
      summary: `${target?.name || ''} 결제 이후 확인해야 할 자료와 전달 흐름이 자동으로 준비되었습니다. 결제 직후 바로 확인하고 활용할 수 있습니다.`,
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
    const selected = topics.length ? topics.map((title, idx) => ({ title: idx === 0 ? `${target.name || order.product} ${order.company || order.email || '고객'} 맞춤 제안` : title, summary: idx === 0 ? `${order.company || order.email || '고객'} 상황에 맞춰 ${target.name || order.product} ${order.plan} 플랜의 진행 흐름과 전달 범위를 글 형식으로 정리했습니다.` : `${target.summary || ''} 조회 코드 ${order.code} 기준으로 함께 확인할 수 있는 관련 안내 글입니다.`, ctaText: automation.cta_label || '제품 설명 보기' })) : [{ title: `${target.name || order.product} 도입 전에 먼저 확인하면 좋은 기준`, summary: `${order.company || order.email} 상황에 맞춘 핵심 결과와 다음 행동을 함께 정리했습니다.`, ctaText: automation.cta_label || '제품 설명 보기' }, { title: `${target.name || order.product}으로 지금 줄일 수 있는 반복 작업`, summary: `체험 이후 바로 적용할 수 있는 포인트를 블로그 형식으로 정리한 글입니다.`, ctaText: automation.cta_label || '제품 보기' }];
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
      reportId: data.reportId || '',
      reportCode: data.reportCode || '',
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
    const item = { id: uid('demo'), code: makePublicCode('DEMO', data.product), product: data.product, productName: productName(data.product), company: data.company, name: data.name, email: normalizeEmail(data.email), team: data.team || '', need: data.need || '', keywords: data.keywords || '', plan: data.plan || '', reportId: data.reportId || '', reportCode: data.reportCode || '', createdAt, updatedAt: createdAt };
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
    header.innerHTML = `<button class="admin-fab" type="button" data-admin-entry="1" title="비밀키가 있어야 열립니다">관리자</button><div class="container nav-wrap"><div class="nav-left"><a class="brand" href="${base}index.html"><span class="brand-mark">N0</span><span class="brand-copy"><strong>${config.brand?.name || 'NV0'}</strong><span>${config.brand?.tagline || ''}</span></span></a></div><nav class="nav-links">${navItems.map(([label, href, key]) => `<a href="${href}" class="${pageKey === key ? 'active' : ''}">${label}</a>`).join('')}<a class="button secondary" href="${base}demo/index.html">즉시 데모</a><a class="button" href="${base}pricing/index.html">가격 보기</a></nav></div><div class="container subnav">${quickLinks}</div>`;
  }
  function bindAdminEntry(){
    document.querySelectorAll('[data-admin-entry]').forEach((trigger) => {
      if (trigger.dataset.bound === '1') return;
      trigger.dataset.bound = '1';
      trigger.addEventListener('click', async (event) => {
        event.preventDefault();
        if (path.includes('/admin/')) return;
        await requestAdminAccess(true);
      });
    });
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
  function renderPublicBoard() { const root = document.getElementById('public-board-grid'); if (!root) return; ensureSeedData(); const items = read(STORE.publications).sort((a,b) => (a.createdAt < b.createdAt ? 1 : -1)); if (!items.length) { root.innerHTML = '<div class="empty-box">아직 공개된 글이 없습니다. 조금 뒤 다시 확인하시거나 제품 상세에서 먼저 방향을 살펴보실 수 있습니다.</div>'; return; } root.innerHTML = items.slice(0, 12).map((item, idx) => `<article class="board-card board-card-blog"><span class="tag">관련 글 ${idx + 1}</span><h3>${esc(item.title)}</h3><p>${esc(item.summary)}</p><div class="board-meta"><span>${esc(item.productName || productName(item.product))}</span><span>${esc(String(item.readMinutes || 3))}분 읽기</span><span>${esc(item.format || 'ai-hybrid-blog')}</span></div><div class="small-actions">${boardCtaMarkup(item)}<a href="${publicBoardHref(item.id)}">블로그 글 보기</a><a href="${base}products/${item.product}/index.html">제품 상세</a></div></article>`).join(''); renderPublicationDetail('public-post-detail', items); }
  function renderProductBoard() { const root = document.getElementById('product-board-grid'); if (!root || !product) return; ensureSeedData(); const dynamic = read(STORE.publications).filter((item) => item.product === product.key); const automation = product.board_automation || {}; const seedCards = (automation.topics || []).map((topic, idx) => buildPublicationRecord({ product: product.key, title: topic.title, summary: topic.summary, source:'topic-seed', code:'', createdAt: stamp(), ctaLabel: topic.ctaText || automation.cta_label || '제품 보기', ctaHref: buildCtaHref(automation.cta_href, product.key), topicSummary: topic.summary, id:`topic-${idx}` })); const items = [...dynamic, ...seedCards].sort((a,b)=>a.createdAt < b.createdAt ? 1 : -1); root.innerHTML = items.slice(0, 12).map((item, idx) => `<article class="board-card board-card-blog"><span class="tag">${product.name} 관련 글 ${idx + 1}</span><h3>${esc(item.title)}</h3><p>${esc(item.summary)}</p><div class="board-meta"><span>${esc(String(item.readMinutes || 3))}분 읽기</span><span>${esc(item.format || 'ai-hybrid-blog')}</span></div><div class="small-actions">${boardCtaMarkup(item)}<a href="${productBoardHref(product.key, item.id)}">블로그 글 보기</a><a href="${base}products/${product.key}/index.html#order">결제 진행</a></div></article>`).join(''); renderPublicationDetail('product-post-detail', items); }
  async function loadBoardFeed(){ const url = config.integration?.board_feed_endpoint; if (!url) return false; try { const res = await fetch(url, { headers: { 'Accept':'application/json' } }); if (!res.ok) return false; const payload = await res.json(); if (Array.isArray(payload?.items)) write(STORE.publications, payload.items); return Array.isArray(payload?.items); } catch { return false; } }
  function setPrefills(){ const params = new URLSearchParams(location.search); const productField = document.querySelector('input[name="product"], select[name="product"]'); if (productField && params.get('product')) productField.value = params.get('product'); const planField = document.querySelector('select[name="plan"][data-prefill="plan"]'); if (planField && params.get('plan')) planField.value = params.get('plan'); if (product?.key) { const report = getLastProductReport(product.key); if (report) applyProductReportToCheckout(product.key, report, report); } }
  function renderAdminSummary(){ const orders = read(STORE.orders); const demos = read(STORE.demos); const contacts = read(STORE.contacts); const publications = read(STORE.publications); const reports = read(STORE.reports); const summary = document.getElementById('admin-summary'); if (summary) summary.innerHTML = `<article class="record-card"><span class="tag">주문</span><h4>${orders.length}</h4><p>저장된 결제·주문 건수</p></article><article class="record-card"><span class="tag">데모</span><h4>${demos.length}</h4><p>저장된 제품 데모 요청</p></article><article class="record-card"><span class="tag">문의</span><h4>${contacts.length}</h4><p>추가 확인 요청 건수</p></article><article class="record-card"><span class="tag">Veridion 리포트</span><h4>${reports.filter((item)=>item.product==='veridion').length}</h4><p>실제 탐색 기반 발행 리포트</p></article>`; const automation = document.getElementById('admin-automation-grid'); if (automation) { const latest = reports.filter((item)=>item.product==='veridion').sort((a,b)=> String(a.createdAt||'') < String(b.createdAt||'') ? 1 : -1)[0]; automation.innerHTML = `<article class="record-card"><span class="tag">자동발행</span><h4>${publications.length}개 공개 글</h4><p>제품 게시판과 전체 게시판에서 같은 기록을 함께 사용합니다.</p></article><article class="record-card"><span class="tag">Veridion 스캔</span><h4>${latest?.stats?.explorationRate ?? '-'}%</h4><p>${latest ? `최근 리포트 ${esc(latest.code)} · 핵심 페이지 ${esc(String(latest.stats?.priorityCoverage ?? '-'))}%` : '아직 실제 탐색 리포트가 없습니다.'}</p></article><article class="record-card"><span class="tag">발행 준비</span><h4>${orders.filter((item)=>item.status==='delivered').length}건</h4><p>결과 전달 또는 발행 완료 상태 기준입니다.</p></article>`; } const orderRoot = document.getElementById('admin-orders'); if (orderRoot) orderRoot.innerHTML = orders.length ? orders.slice(0,12).map((item)=>`<article class="record-card"><span class="tag">${esc(item.productName || productName(item.product))}</span><h4>${esc(item.company || item.email)}</h4><p>플랜 ${esc(item.plan)} · 결제 ${esc(paymentStatusLabel(item.paymentStatus))} · 상태 ${esc(orderStatusLabel(item.status))}</p><p>조회 코드 <span class="inline-code">${esc(item.code)}</span>${item.reportCode ? ` · 리포트 ${esc(item.reportCode)}` : ''}</p><div class="small-actions"><button class="button secondary" type="button" data-admin-action="toggle-payment" data-order-id="${esc(item.id)}">결제 전환</button><button class="button ghost" type="button" data-admin-action="advance" data-order-id="${esc(item.id)}">전달 완료</button><button class="button ghost" type="button" data-admin-action="republish" data-order-id="${esc(item.id)}">재발행</button></div></article>`).join('') : '<div class="empty-box">저장된 주문이 없습니다.</div>'; const requestRoot = document.getElementById('admin-requests'); if (requestRoot) requestRoot.innerHTML = ([...demos.map((item)=>`<article class="record-card"><span class="tag">데모</span><h4>${esc(item.company || item.email)}</h4><p>${esc(item.productName)} · ${esc(item.need || '')}</p><p>코드 <span class="inline-code">${esc(item.code)}</span>${item.reportCode ? ` · 리포트 ${esc(item.reportCode)}` : ''}</p></article>`), ...contacts.map((item)=>`<article class="record-card"><span class="tag">문의</span><h4>${esc(item.company || item.email)}</h4><p>${esc(item.productName)} · ${esc(item.issue || '')}</p><p>코드 <span class="inline-code">${esc(item.code)}</span></p></article>`)]).slice(0,12).join('') || '<div class="empty-box">저장된 요청이 없습니다.</div>'; const pubRoot = document.getElementById('admin-publications'); if (pubRoot) pubRoot.innerHTML = publications.length ? publications.slice(0,12).map((item)=>`<article class="record-card"><span class="tag">${esc(item.productName || productName(item.product))}</span><h4>${esc(item.title)}</h4><p>${esc(item.summary)}</p><div class="small-actions"><a href="${publicBoardHref(item.id)}">전체 글</a><a href="${productBoardHref(item.product, item.id)}">제품 글</a></div></article>`).join('') : '<div class="empty-box">발행된 글이 없습니다.</div>'; const feed = document.getElementById('admin-feed'); if (feed) { const latest = reports.filter((item)=>item.product==='veridion').sort((a,b)=> String(a.createdAt||'') < String(b.createdAt||'') ? 1 : -1)[0]; feed.innerHTML = latest ? `<div class="mock-step"><strong>최근 Veridion 리포트</strong><span>${esc(latest.code)} · 탐색률 ${esc(String(latest.stats?.explorationRate ?? '-'))}% · 핵심 페이지 ${esc(String(latest.stats?.priorityCoverage ?? '-'))}%</span></div>${(latest.issues || []).slice(0,4).map((item)=>`<div class="mock-step"><strong>${esc(item.title)}</strong><span>${esc(item.detail)}</span></div>`).join('')}` : '<div class="empty-box">아직 Veridion 탐색 리포트가 없습니다.</div>'; } }
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
      const payload = { product: String(data.get('product') || product.key), plan: String(data.get('plan') || 'Starter'), billing: String(data.get('billing') || 'one-time'), paymentMethod: String(data.get('paymentMethod') || 'toss'), company: String(data.get('company') || ''), name: String(data.get('name') || ''), email: String(data.get('email') || ''), note: memo, reportId: String(data.get('reportId') || ''), reportCode: String(data.get('reportCode') || '') };
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

  const PRODUCT_DEMO_CONFIG = {
    veridion: {
      intro: 'URL과 업종만 넣으면, 공개 페이지 기준으로 법적·운영상 먼저 손봐야 할 항목을 우선순위로 정리합니다.',
      fields: `
        <div><label>점검할 URL</label><input name="website" type="url" placeholder="https://example.com" value="${esc(product?.demo_defaults?.website || '')}"></div>
        <div><label>업종</label><select name="industry"><option value="healthcare">의료·건강</option><option value="beauty">뷰티·웰니스</option><option value="commerce">이커머스</option><option value="education">교육·서비스</option><option value="saas">B2B SaaS</option></select></div>
        <div><label>운영 국가</label><select name="market"><option>대한민국</option><option>한국 + 일본</option><option>한국 + 미국</option></select></div>
        <div><label>현재 상태</label><select name="maturity"><option>초안 상태</option><option>운영 중인데 점검 안 됨</option><option>광고 집행 전 최종 점검 필요</option></select></div>
        <div class="full"><label>꼭 보는 페이지</label><input name="pages" placeholder="메인, 상품상세, 회원가입, 결제, 개인정보처리방침" value="메인, 상품상세, 회원가입, 결제, 개인정보처리방침"></div>
        <div class="full"><label>걱정되는 부분</label><input name="focus" placeholder="예: 과장 표현, 개인정보 안내, 환불정책, 자동결제 고지"></div>
      `,
      checks: [
        ['claims', '광고·표현 리스크를 먼저 보고 싶습니다'],
        ['privacy', '개인정보 수집·보관·동의 흐름을 함께 점검합니다'],
        ['commerce', '결제·환불·자동결제 고지까지 같이 봅니다'],
        ['copy', '수정 문구 샘플까지 같이 받습니다']
      ]
    },
    clearport: {
      intro: '제출 유형과 보유 서류를 선택하면, 누락 서류·보완 포인트·대외 안내 문구까지 바로 만듭니다.',
      fields: `
        <div><label>제출 유형</label><select name="submissionType"><option>입점 심사</option><option>파트너 등록</option><option>입찰·제안 제출</option><option>정부·기관 서류 제출</option></select></div>
        <div><label>제출 마감</label><input name="deadline" type="date"></div>
        <div><label>기관/거래처명</label><input name="targetOrg" placeholder="예: A기관, B유통사"></div>
        <div><label>담당 팀 규모</label><select name="teamSize"><option>1명</option><option>2~3명</option><option>4명 이상</option></select></div>
        <div class="full"><label>현재 가장 막히는 부분</label><input name="blocker" placeholder="예: 필수 서류 누락, 파일 버전 혼선, 인감/날인 지연"></div>
      `,
      checks: [
        ['bizreg', '사업자등록증은 확보되어 있습니다'],
        ['bank', '통장사본 또는 정산 정보가 있습니다'],
        ['seal', '인감/사용인감 관련 자료가 있습니다'],
        ['policy', '개인정보·보안 관련 확인서가 필요할 수 있습니다'],
        ['portfolio', '회사소개서 또는 수행실적 자료가 있습니다'],
        ['contactdoc', '담당자 연락처·회신 창구가 정리되어 있습니다']
      ]
    },
    grantops: {
      intro: '마감일과 현재 진행률을 넣으면, 역산 일정·역할 분담·지금 늦는 항목을 바로 보여줍니다.',
      fields: `
        <div><label>사업/공모명</label><input name="projectName" placeholder="예: 2026 지원사업 신청"></div>
        <div><label>최종 마감일</label><input name="deadline" type="date"></div>
        <div><label>현재 진행률</label><select name="progress"><option>자료 수집 전</option><option>초안 작성 중</option><option>검토 단계</option><option>제출 직전</option></select></div>
        <div><label>참여 인원</label><select name="contributors"><option>1명</option><option>2명</option><option>3명</option><option>4명 이상</option></select></div>
        <div class="full"><label>가장 자주 밀리는 작업</label><input name="delayPoint" placeholder="예: 증빙 수집, 대표 승인, 예산표 정리, 최종 업로드"></div>
      `,
      checks: [
        ['schedule', '역산 일정표가 필요합니다'],
        ['roles', '누가 뭘 마감하는지 역할 분리가 필요합니다'],
        ['review', '대표/결재자 검토 시간이 필요합니다'],
        ['evidence', '증빙자료 누락 여부를 같이 확인합니다']
      ]
    },
    draftforge: {
      intro: '검토 중인 초안 종류와 승인 단계를 넣으면, 버전 정리·결재 흐름·최종본 기준을 바로 설계합니다.',
      fields: `
        <div><label>문서 종류</label><select name="docType"><option>제안서</option><option>정책/운영 문서</option><option>대외 공문</option><option>계약·부속 문서</option><option>브랜드/서비스 소개서</option></select></div>
        <div><label>현재 버전 상태</label><select name="versionState"><option>초안만 있음</option><option>수정본이 여러 개 흩어져 있음</option><option>거의 완료인데 마지막 검토 필요</option></select></div>
        <div><label>승인 단계 수</label><select name="approvalSteps"><option>1단계</option><option>2단계</option><option>3단계 이상</option></select></div>
        <div><label>주 사용 채널</label><select name="channel"><option>이메일</option><option>메신저 + 파일공유</option><option>문서 툴 + 메신저</option></select></div>
        <div class="full"><label>지금 가장 큰 문제</label><input name="draftPain" placeholder="예: 최신본 불명확, 승인자 코멘트 누락, 최종 파일명 혼선"></div>
      `,
      checks: [
        ['naming', '버전명 규칙을 같이 정리합니다'],
        ['approval', '검토자/승인자 단계를 분리합니다'],
        ['qa', '최종본 배포 전 체크리스트가 필요합니다'],
        ['handoff', '대외 발송용 문구까지 맞춥니다']
      ]
    }
  };

  function productPageHref(key, hash){ return `${base}products/${key}/index.html${hash || ''}`; }
  function clampNumber(value, min, max){ return Math.min(max, Math.max(min, Number(value) || 0)); }
  function checkedValues(form, prefix){ return [...form.querySelectorAll(`input[name^="${prefix}."]:checked`)].map((input)=>input.value); }
  function parseDateDiff(value){
    if (!value) return null;
    const date = new Date(value + 'T23:59:59');
    const diff = Math.ceil((date.getTime() - Date.now()) / 86400000);
    return Number.isFinite(diff) ? diff : null;
  }
  function severityLabel(level){ return ({high:'즉시 조치', medium:'이번 주 안', low:'운영 중 병행'})[level] || '확인'; }
  function uniqueCompact(items){ return [...new Set((items || []).map((item)=>clean(item)).filter(Boolean))]; }
  function buildDemoSaveBox(entry, remoteSaved){
    if (!entry) return '<div class="demo-save-box"><strong>현재 결과는 화면에서 바로 확인하는 샘플입니다.</strong><br>회사명, 담당자명, 이메일을 함께 입력하면 같은 결과를 저장하고 후속 안내 기준으로 이어서 사용할 수 있습니다.</div>';
    return `<div class="demo-save-box"><strong>데모 결과가 저장되었습니다.</strong><br>조회 코드 <span class="inline-code">${esc(entry.code)}</span> 기준으로 후속 상담과 결제 요청을 바로 이어갈 수 있습니다.${remoteSaved ? '<br>서버 저장까지 완료되었습니다.' : '<br>현재 브라우저에도 함께 저장되었습니다.'}</div>`;
  }
  function demoContactFields(defaults){
    return `
      <div><label>회사명</label><input name="company" placeholder="회사명" value="${esc(defaults.company || '')}"></div>
      <div><label>담당자명</label><input name="name" placeholder="담당자명" value="${esc(defaults.name || '')}"></div>
      <div class="full"><label>이메일</label><input name="email" type="email" placeholder="email@company.com" value="${esc(defaults.email || '')}"></div>
    `;
  }
  function renderProductDemoWorkspace(){
    const root = document.getElementById('product-demo-shell');
    if (!root || !product) return;
    const cfg = PRODUCT_DEMO_CONFIG[product.key];
    if (!cfg) return;
    root.innerHTML = `
      <form id="product-demo-form" class="demo-workspace stack-form">
        <div class="demo-form-grid">
          ${cfg.fields}
        </div>
        <div class="demo-section-stack">
          <div>
            <label>함께 반영할 항목</label>
            <div class="demo-check-grid">
              ${cfg.checks.map(([value, label]) => `<label class="demo-check"><input type="checkbox" name="option.${value}" value="${value}" checked><span>${label}</span></label>`).join('')}
            </div>
            <div class="demo-helper">${esc(cfg.intro)}</div>
          </div>
          <div>
            <label>결과 저장용 정보</label>
            <div class="demo-form-grid">${demoContactFields(product.demo_defaults || {})}</div>
            <div class="demo-helper">연락처를 넣지 않아도 화면 결과는 볼 수 있습니다. 저장이 필요할 때만 입력하면 됩니다.</div>
          </div>
        </div>
        <div class="demo-actions">
          <button class="button" type="submit">실제 결과 보기</button>
          <a class="button secondary" href="#order">이 조건으로 바로 결제</a>
        </div>
      </form>
    `;
  }
  function fillCheckoutFromDemo(values){
    const form = document.getElementById('product-checkout-form');
    if (!form) return;
    const companyInput = form.querySelector('input[name="company"]');
    const nameInput = form.querySelector('input[name="name"]');
    const emailInput = form.querySelector('input[name="email"]');
    if (companyInput && values.company) companyInput.value = values.company;
    if (nameInput && values.name) nameInput.value = values.name;
    if (emailInput && values.email) emailInput.value = values.email;
    const noteInput = form.querySelector('input[name="note"]');
    if (noteInput && values.note && (product?.key === 'veridion' || !noteInput.value)) noteInput.value = values.note;
    companyInput?.dispatchEvent(new Event('input', { bubbles: true }));
    nameInput?.dispatchEvent(new Event('input', { bubbles: true }));
    emailInput?.dispatchEvent(new Event('input', { bubbles: true }));
  }
  function renderDemoTable(rows){ return `<div class="demo-table">${rows.map(([a,b])=>`<div class="demo-table-row"><strong>${esc(a)}</strong><span>${esc(b)}</span></div>`).join('')}</div>`; }
  function renderDemoAlerts(items){ return `<div class="demo-alert-grid">${items.map((item)=>`<article class="demo-alert ${item.level}"><div class="demo-badge">${severityLabel(item.level)}</div><h4>${esc(item.title)}</h4><small>${esc(item.detail)}</small></article>`).join('')}</div>`; }
  function renderCopyCards(items){ return `<div class="demo-copy-grid">${items.map((item)=>`<article class="demo-copy-card"><div class="demo-badge">${esc(item.label)}</div><pre>${esc(item.copy)}</pre></article>`).join('')}</div>`; }
  function renderKpis(items){ return `<div class="demo-kpi-grid">${items.map((item)=>`<article class="demo-kpi"><strong>${esc(item.value)}</strong><span>${esc(item.label)}</span><small>${esc(item.note || '')}</small></article>`).join('')}</div>`; }
  function demoSummaryHeader(title, summary, score){ return `<div class="demo-result-top"><div><div class="demo-result-headline">${esc(title)}</div><p>${esc(summary)}</p></div><div class="demo-mini-card"><div class="demo-badge">현재 점수 ${esc(String(score))} / 100</div><div class="demo-scorebar"><span style="width:${clampNumber(score, 0, 100)}%"></span></div></div></div>`; }

  function veridionResult(values){
    const options = uniqueCompact(values.options);
    const industryMap = { healthcare:'의료·건강', beauty:'뷰티·웰니스', commerce:'이커머스', education:'교육·서비스', saas:'B2B SaaS' };
    const alerts = [];
    let score = 74;
    if (options.includes('claims')) { alerts.push({ level:'high', title:'광고·효능 표현 기준 확인 필요', detail:`${industryMap[values.industry] || '해당 업종'} 특성상 효능 단정, 과장 표현, 비교 우위 문구를 먼저 점검해야 합니다.` }); score -= 8; }
    if (options.includes('privacy')) { alerts.push({ level:'high', title:'개인정보 고지 흐름 보강 필요', detail:'회원가입·문의·구독 폼이 있다면 수집 항목, 보관 기간, 제3자 제공 여부를 화면에서 바로 확인할 수 있어야 합니다.' }); score -= 7; }
    if (options.includes('commerce')) { alerts.push({ level:'medium', title:'결제·환불 안내 문구 정리 필요', detail:'결제 전 확인사항, 청약철회·환불 기준, 자동결제 유무는 구매 직전 화면과 정책 문서가 서로 맞아야 합니다.' }); score -= 5; }
    if (!alerts.length) alerts.push({ level:'medium', title:'핵심 리스크는 적지만 사전 점검 권장', detail:'현재 입력 기준으로는 표현·정책·결제 안내를 가볍게 정리해 두는 수준입니다.' });
    const pages = uniqueCompact(String(values.pages || '').split(','));
    const pageRows = pages.slice(0, 5).map((page, idx) => [page, idx === 0 ? '메시지·표현 리스크 우선 점검' : idx === 1 ? '구매 전 필수 고지 확인' : idx === 2 ? '개인정보 동의 문구 확인' : idx === 3 ? '환불·결제 정보 일치 여부 확인' : '정책 문서 링크 연결 여부 확인']);
    const copyCards = [
      { label:'메인 카피 수정안', copy:`기존 문구를 강한 단정 대신 사실 기반 표현으로 바꿉니다.\n예: "누구에게나 바로 효과" → "사용 환경과 목적에 따라 체감은 달라질 수 있습니다."` },
      { label:'결제 전 안내문', copy:`결제 전 확인해주세요.\n제공 범위, 환불 기준, 자동 갱신 여부, 문의 채널을 이 화면에서 바로 확인하실 수 있습니다.` }
    ];
    return {
      headline:'준법 점검 샘플 결과',
      summary:`${values.website || '입력한 URL'} 기준으로 공개 화면 점검 우선순위를 정리했습니다. 먼저 수정할 부분과 바로 쓸 수 있는 문구 예시를 함께 보여줍니다.`,
      score,
      kpis:[
        { value:`${alerts.length}건`, label:'즉시 확인 항목', note:'운영 전에 먼저 정리해야 하는 화면 기준입니다.' },
        { value:`${pageRows.length}페이지`, label:'우선 점검 범위', note:'메인·구매·정책 화면부터 보는 구조입니다.' },
        { value: options.includes('copy') ? '2종' : '1종', label:'수정 문구 샘플', note:'실제 수정 방향을 바로 잡을 수 있습니다.' }
      ],
      alerts,
      extra:`<div class="demo-section-stack"><h4>페이지별 점검 우선순위</h4>${renderDemoTable(pageRows)}<h4>바로 적용 가능한 문구 예시</h4>${renderCopyCards(copyCards)}</div>`,
      note:`${industryMap[values.industry] || '해당 업종'} · ${values.market || '대한민국'} 기준으로 점검했습니다.`
    };
  }

  function clearportResult(values){
    const days = parseDateDiff(values.deadline);
    const docs = values.options || [];
    const missing = [];
    if (!docs.includes('bizreg')) missing.push('사업자등록증');
    if (!docs.includes('bank')) missing.push('통장사본/정산정보');
    if (!docs.includes('seal')) missing.push('인감 또는 사용인감 자료');
    if (!docs.includes('contactdoc')) missing.push('담당자 회신 정보');
    let score = 88 - missing.length * 12;
    if (days !== null && days <= 3) score -= 10;
    const alerts = [];
    if (missing.length) alerts.push({ level:'high', title:'필수 서류 누락 가능성', detail:`현재 입력 기준으로 ${missing.join(', ')} 보완이 우선입니다.` });
    if (docs.includes('policy')) alerts.push({ level:'medium', title:'보안·개인정보 확인서 확인 필요', detail:'기관 또는 거래처에 따라 양식이 별도일 수 있어 사전 확인이 필요합니다.' });
    if (days !== null && days <= 3) alerts.push({ level:'high', title:'마감 임박', detail:`남은 일정이 ${days}일 수준이라 내부 결재와 날인 일정을 역산해서 바로 묶어야 합니다.` });
    if (!alerts.length) alerts.push({ level:'low', title:'구성은 안정적', detail:'기본 제출 세트가 갖춰져 있어 형식 통일과 파일명 정리 위주로 진행하면 됩니다.' });
    const rows = [
      ['제출 대상', values.targetOrg || '미입력'],
      ['제출 유형', values.submissionType || '미입력'],
      ['가장 먼저 보완할 것', missing[0] || '파일명·날인·최종본 통일'],
      ['고객 안내 문구', `${values.targetOrg || '제출처'} 요청 기준으로 누락 서류와 보완본 제출 일정을 오늘 안에 회신드립니다.`]
    ];
    const copyCards = [
      { label:'대외 회신 문구', copy:`안녕하세요.\n현재 제출 서류를 최종 점검 중이며, 누락 여부를 확인한 뒤 보완본 제출 가능 시점을 바로 회신드리겠습니다.` },
      { label:'내부 전달 메모', copy:`오늘 안에 확인할 항목: ${missing[0] || '파일명 통일'}\n담당자별 준비 자료와 날인 필요 서류를 분리해서 다시 정리합니다.` }
    ];
    return {
      headline:'서류 제출 정리 샘플 결과',
      summary:'누락 서류, 마감 위험도, 대외 회신 문구를 한 번에 정리하는 흐름으로 설계했습니다.',
      score: clampNumber(score, 35, 96),
      kpis:[
        { value:`${missing.length}건`, label:'우선 보완 서류', note:'없으면 형식 통일 중심으로 진행합니다.' },
        { value: days === null ? '미입력' : `${days}일`, label:'마감까지 남은 일정', note:'3일 이하이면 결재·날인 일정이 핵심입니다.' },
        { value: docs.length ? `${docs.length}종` : '0종', label:'확보된 자료 범위', note:'현재 체크한 보유 서류 기준입니다.' }
      ],
      alerts,
      extra:`<div class="demo-section-stack"><h4>제출 운영 요약</h4>${renderDemoTable(rows)}<h4>바로 쓸 수 있는 안내문</h4>${renderCopyCards(copyCards)}</div>`,
      note:`담당 팀 ${values.teamSize || '미입력'} · 기관 ${values.targetOrg || '미입력'}`
    };
  }

  function grantopsResult(values){
    const days = parseDateDiff(values.deadline);
    let risk = 0;
    if (days !== null && days <= 3) risk += 35; else if (days !== null && days <= 7) risk += 20;
    if (values.progress === '자료 수집 전') risk += 30;
    if (values.progress === '초안 작성 중') risk += 18;
    if ((values.delayPoint || '').length > 0) risk += 10;
    if ((values.options || []).includes('review')) risk += 8;
    const score = clampNumber(92 - risk, 28, 95);
    const alerts = [
      { level: score < 60 ? 'high' : 'medium', title:'역산 일정 재정렬 필요', detail:`현재 상태가 ${values.progress || '미입력'} 이고 마감이 ${days === null ? '미입력' : days + '일 남음'} 수준이라 제출 전 검토 구간을 먼저 확보해야 합니다.` },
      { level:(values.options || []).includes('evidence') ? 'medium' : 'low', title:'증빙자료 체크포인트', detail:`${values.delayPoint || '증빙 수집'} 단계에서 가장 자주 일정이 밀릴 가능성이 있습니다.` }
    ];
    const tasks = [
      'D-7 이전: 필수 자료 확정 및 부족 증빙 요청',
      'D-5 이전: 서술 초안 1차 완료',
      'D-3 이전: 예산·증빙·첨부파일 교차검토',
      'D-1 이전: 업로드 테스트와 최종 승인 완료'
    ];
    const roleRows = [
      ['실무 담당', '초안 작성, 자료 수집, 업로드 준비'],
      ['검토 담당', '문장·수치·증빙 일치 여부 확인'],
      ['승인 담당', '최종 제출 승인 및 대외 제출 확정'],
      ['백업 담당', '파일명, 버전, 업로드 오류 대응']
    ];
    return {
      headline:'제출 운영 샘플 결과',
      summary:'마감 역산 기준으로 지금 늦는 항목과 역할 분담을 바로 보이게 구성했습니다.',
      score,
      kpis:[
        { value: days === null ? '미입력' : `D-${Math.max(days, 0)}`, label:'남은 일정', note:'마감일 기준 자동 역산입니다.' },
        { value: values.contributors || '미입력', label:'참여 인원', note:'검토/승인 분리가 되는지 보는 기준입니다.' },
        { value: score < 60 ? '높음' : score < 75 ? '중간' : '안정', label:'제출 리스크', note:'진행률과 마감일을 함께 반영했습니다.' }
      ],
      alerts,
      extra:`<div class="demo-section-stack"><h4>권장 역산 일정</h4><ol class="demo-number-list">${tasks.map((item)=>`<li>${esc(item)}</li>`).join('')}</ol><h4>역할 분담 기준</h4>${renderDemoTable(roleRows)}</div>`,
      note:`사업명 ${values.projectName || '미입력'} · 지연 포인트 ${values.delayPoint || '미입력'}`
    };
  }

  function draftforgeResult(values){
    const steps = Number((values.approvalSteps || '1단계').match(/\d+/)?.[0] || 1);
    let score = 90 - steps * 8;
    if (values.versionState === '수정본이 여러 개 흩어져 있음') score -= 18;
    if (values.versionState === '초안만 있음') score -= 10;
    if ((values.options || []).includes('qa')) score -= 4;
    const alerts = [
      { level: values.versionState === '수정본이 여러 개 흩어져 있음' ? 'high' : 'medium', title:'최신본 기준 확정 필요', detail:'파일이 여러 채널에 흩어져 있으면 승인 코멘트 누락과 역버전 발송 가능성이 커집니다.' },
      { level: steps >= 3 ? 'medium' : 'low', title:'승인 단계 정리 필요', detail:`현재 ${values.approvalSteps || '1단계'} 승인 구조라면 검토용/결재용/최종배포용 버전을 분리해야 합니다.` }
    ];
    const copyCards = [
      { label:'파일명 규칙', copy:`예: ${values.docType || '문서'}_YYYYMMDD_v01_작성\n검토 완료본은 _rv, 최종 배포본은 _final만 사용합니다.` },
      { label:'최종 발송 메모', copy:`최종 승인 완료본 전달드립니다.\n본문 수정 이력과 첨부파일명을 일치시켰고, 외부 발송용 기준으로 다시 검토했습니다.` }
    ];
    const rows = [
      ['문서 종류', values.docType || '미입력'],
      ['현재 상태', values.versionState || '미입력'],
      ['주 채널', values.channel || '미입력'],
      ['가장 큰 문제', values.draftPain || '미입력']
    ];
    return {
      headline:'문서 확정 운영 샘플 결과',
      summary:'초안 작성보다 검토·승인·최종본 배포가 엉키지 않도록 운영 기준을 먼저 세우는 구조입니다.',
      score: clampNumber(score, 34, 95),
      kpis:[
        { value:`${steps}단계`, label:'승인 구조', note:'단계가 많을수록 버전 관리 기준이 중요합니다.' },
        { value: values.versionState === '수정본이 여러 개 흩어져 있음' ? '높음' : '보통', label:'버전 혼선 위험', note:'최신본 단일화 여부가 핵심입니다.' },
        { value: '3종', label:'바로 필요한 운영 기준', note:'파일명 규칙, 승인 단계, 최종 QA 기준입니다.' }
      ],
      alerts,
      extra:`<div class="demo-section-stack"><h4>현재 문서 운영 상태</h4>${renderDemoTable(rows)}<h4>바로 적용할 운영 문구</h4>${renderCopyCards(copyCards)}</div>`,
      note:`문서 종류 ${values.docType || '미입력'} · 승인 ${values.approvalSteps || '미입력'}`
    };
  }

  function buildProductSpecificDemoResult(values){
    const result = product.key === 'veridion' ? veridionResult(values)
      : product.key === 'clearport' ? clearportResult(values)
      : product.key === 'grantops' ? grantopsResult(values)
      : draftforgeResult(values);
    return `
      <div class="demo-result-shell">
        ${demoSummaryHeader(result.headline, result.summary, result.score)}
        ${renderKpis(result.kpis)}
        ${renderDemoAlerts(result.alerts)}
        ${result.extra}
        <div class="demo-save-box"><strong>이번 결과 한 줄 요약</strong><br>${esc(result.note || '')}</div>
      </div>
    `;
  }

  function buildHomeProducts() {
    const root = document.getElementById('product-grid');
    if (!root) return;
    root.innerHTML = Object.values(products).map((item) => `
      <article class="card product-card strong ${item.theme}">
        <span class="tag theme-chip">${esc(item.label)}</span>
        <h3>${esc(item.name)}</h3>
        <p>${esc(item.problem || item.headline || '')}</p>
        <ul class="clean">${(item.value_points || []).slice(0, 3).map((text) => `<li>${esc(text)}</li>`).join('')}</ul>
        <div class="muted-box" style="margin-top:18px">${esc(item.pricing_basis || '')}</div>
        <div class="actions">
          <a class="button" href="${productPageHref(item.key, '#demo')}">실제 데모 보기</a>
          <a class="button secondary" href="${productPageHref(item.key, '#intro')}">제품 설명</a>
          <a class="button ghost" href="${productPageHref(item.key, '#order')}">플랜/결제</a>
        </div>
      </article>
    `).join('');
  }

  function buildModuleMatrix() {
    const root = document.getElementById('module-matrix');
    if (!root) return;
    root.innerHTML = Object.values(products).map((item) => `
      <article class="story-card ${item.theme}">
        <span class="tag theme-chip">${esc(item.tag || item.label)}</span>
        <h3>${esc(item.name)}</h3>
        <p>${esc(item.summary || item.problem || '')}</p>
        <div class="actions">
          <a class="button soft" href="${productPageHref(item.key, '#demo')}">입력하고 결과 보기</a>
          <a class="button ghost" href="${productPageHref(item.key, '#delivery')}">전달 범위 보기</a>
        </div>
      </article>
    `).join('');
  }

  function fillProductSlots() {
    if (!product) return;
    document.querySelectorAll('[data-fill="product-name"]').forEach((el) => el.textContent = product.name);
    document.querySelectorAll('[data-fill="product-headline"]').forEach((el) => el.textContent = product.headline);
    document.querySelectorAll('[data-fill="product-summary"]').forEach((el) => el.textContent = product.summary);
    document.querySelectorAll('[data-fill="product-problem"]').forEach((el) => el.textContent = product.problem);
    document.querySelectorAll('[data-fill="product-pricing"]').forEach((el) => el.textContent = currencyPlan(product.key));
    const valueRoot = document.getElementById('product-values');
    if (valueRoot) valueRoot.innerHTML = (product.value_points || []).map((item) => `<li>${esc(item)}</li>`).join('');
    const outputRoot = document.getElementById('product-outputs');
    if (outputRoot) outputRoot.innerHTML = (product.outputs || []).map((item) => `<li>${esc(item)}</li>`).join('');
    const workflowRoot = document.getElementById('product-workflow');
    if (workflowRoot) workflowRoot.innerHTML = (product.workflow || []).map((item) => `<li>${esc(item)}</li>`).join('');
    const demoRoot = document.getElementById('product-demo-scenarios');
    if (demoRoot) demoRoot.innerHTML = (product.demo_scenarios || []).map((item) => `<li>${esc(item)}</li>`).join('');
    const relatedRoot = document.getElementById('product-related-modules');
    if (relatedRoot) relatedRoot.innerHTML = (product.related_modules || []).map((key) => products[key]).filter(Boolean).map((item) => `<article class="story-card ${item.theme}"><span class="tag theme-chip">${esc(item.label)}</span><h3>${esc(item.name)}</h3><p>${esc(item.summary)}</p><div class="small-actions"><a href="${productPageHref(item.key, '#demo')}">실제 데모 보기</a><a href="${productPageHref(item.key, '#intro')}">제품 설명 보기</a></div></article>`).join('') || '<div class="empty-box">바로 이어서 비교할 제품이 아직 없습니다.</div>';
    const faqRoot = document.getElementById('product-faq');
    if (faqRoot) faqRoot.innerHTML = (product.faqs || []).map((item) => `<article class="faq-card"><span class="tag">Q</span><h3>${esc(item.q)}</h3><p>${esc(item.a)}</p></article>`).join('');
    const actions = document.getElementById('product-actions');
    if (actions) actions.innerHTML = `<a class="button" href="#demo">실제 데모</a><a class="button secondary" href="#order">플랜/결제</a><a class="button ghost" href="#delivery">전달 범위</a><a class="button ghost" href="${base}products/${product.key}/board/index.html">관련 글</a>`;
    const basis = document.getElementById('product-pricing-basis');
    if (basis) basis.textContent = product.pricing_basis || '';
    renderProductDemoWorkspace();
  }

  async function bindProductDemoForm(){
    const form = document.getElementById('product-demo-form');
    if (!form || !product) return;
    form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
      const data = new FormData(form);
      const values = Object.fromEntries(data.entries());
      values.options = checkedValues(form, 'option');
      if (product.key === 'veridion') assert(clean(values.website), '점검할 URL을 입력하세요.');
      let remoteReport = null;
      if (product.key === 'veridion') {
        const scanPayload = { website: values.website, industry: values.industry, market: values.market, maturity: values.maturity, pages: values.pages, focus: values.focus, options: values.options, company: values.company };
        const scan = await postIfConfigured(veridionScanEndpoint(), scanPayload);
        if (scan.mode === 'remote' && scan.ok && scan.json?.report) { applyStatePayload(scan.json?.state); remoteReport = scan.json.report; setLastProductReport('veridion', remoteReport); }
        else if (scan.mode === 'remote') throw new Error(scan.json?.detail || scan.text || '실제 탐색 기반 점검을 준비하지 못했습니다.');
      } else if (product.key === 'clearport') {
        const res = await postIfConfigured(clearportAnalyzeEndpoint(), { submissionType: values.submissionType, deadline: values.deadline, targetOrg: values.targetOrg, teamSize: values.teamSize, blocker: values.blocker, options: values.options, company: values.company });
        if (res.mode === 'remote' && res.ok && res.json?.report) { applyStatePayload(res.json?.state); remoteReport = res.json.report; setLastProductReport('clearport', remoteReport); }
        else if (res.mode === 'remote') throw new Error(res.json?.detail || res.text || '제출 준비 리포트를 만들지 못했습니다.');
      } else if (product.key === 'grantops') {
        const res = await postIfConfigured(grantopsAnalyzeEndpoint(), { projectName: values.projectName, deadline: values.deadline, progress: values.progress, contributors: values.contributors, delayPoint: values.delayPoint, options: values.options, company: values.company });
        if (res.mode === 'remote' && res.ok && res.json?.report) { applyStatePayload(res.json?.state); remoteReport = res.json.report; setLastProductReport('grantops', remoteReport); }
        else if (res.mode === 'remote') throw new Error(res.json?.detail || res.text || '제출 운영 리포트를 만들지 못했습니다.');
      } else {
        const res = await postIfConfigured(draftforgeAnalyzeEndpoint(), { docType: values.docType, versionState: values.versionState, approvalSteps: values.approvalSteps, channel: values.channel, draftPain: values.draftPain, options: values.options, company: values.company });
        if (res.mode === 'remote' && res.ok && res.json?.report) { applyStatePayload(res.json?.state); remoteReport = res.json.report; setLastProductReport('draftforge', remoteReport); }
        else if (res.mode === 'remote') throw new Error(res.json?.detail || res.text || '문서 운영 리포트를 만들지 못했습니다.');
      }
      const fallbackNote = product.key === 'clearport' ? [values.submissionType, values.targetOrg, values.blocker].filter(Boolean).join(' / ') : product.key === 'grantops' ? [values.projectName, values.progress, values.delayPoint].filter(Boolean).join(' / ') : product.key === 'draftforge' ? [values.docType, values.versionState, values.draftPain].filter(Boolean).join(' / ') : [values.website, values.focus].filter(Boolean).join(' / ');
      const note = remoteReport ? structuredProductReportNote(product.key, values, remoteReport) : fallbackNote;
      let entry = null; let remoteSaved = false;
      const canSave = clean(values.company) && clean(values.name) && validateEmail(values.email || '');
      if (canSave) {
        const demoPayload = { product: product.key, company: values.company, name: values.name, email: values.email, team: values.teamSize || values.contributors || values.approvalSteps || values.market || '', need: note, keywords: (values.options || []).join(', '), reportId: remoteReport?.id || '', reportCode: remoteReport?.code || '' };
        const remote = await postIfConfigured(config.integration?.demo_endpoint, demoPayload);
        if (remote.mode === 'remote' && remote.ok && remote.json?.demo) { applyStatePayload(remote.json?.state); await syncRemoteState(); entry = remote.json.demo; remoteSaved = true; }
        else if (remote.mode === 'remote' && !remote.ok) throw new Error(remote.json?.detail || remote.text || '데모 저장에 실패했습니다.');
        else entry = createDemo(demoPayload);
      }
      const remoteHtml = product.key === 'veridion' ? renderVeridionRemoteReport(remoteReport, values) : product.key === 'clearport' ? renderClearportRemoteReport(remoteReport, values) : product.key === 'grantops' ? renderGrantopsRemoteReport(remoteReport, values) : renderDraftforgeRemoteReport(remoteReport, values);
      const html = ((remoteReport ? remoteHtml : buildProductSpecificDemoResult(values)) || buildProductSpecificDemoResult(values)) + buildDemoSaveBox(entry, remoteSaved);
      showResult('product-demo-result', html);
      fillCheckoutFromDemo({ company: values.company, name: values.name, email: values.email, note });
      if (remoteReport) applyProductReportToCheckout(product.key, values, remoteReport);
      renderAdminSummary(); renderLiveStats(); renderWorkspaceCards();
    }); });
  }

  document.addEventListener('DOMContentLoaded', async () => { await loadSystemConfig(); if ((pageKey === 'checkout' || pageKey === 'product') && paymentRuntime()?.enabled && !paymentRuntime()?.mock) await loadTossScript(); const stateSynced = await syncRemoteState(); if (!stateSynced) { const boardSynced = await loadBoardFeed(); if (!boardSynced) ensureSeedData(); } else if (!read(STORE.publications).length) { const boardSynced = await loadBoardFeed(); if (!boardSynced) ensureSeedData(); } else { ensureSeedData(); } renderHeader(); bindAdminEntry(); renderFooter(); buildHomeProducts(); buildModuleMatrix(); fillProductSlots(); buildPlans(); setPrefills(); renderPublicBoard(); renderProductBoard(); renderLiveStats(); renderWorkspaceCards(); renderProductServices(); renderServiceCatalog(); bindProductDemoForm(); await bindProductCheckoutForm(); bindDemoForm(); bindCheckoutForm(); bindContactForm(); bindPortalLookup(); bindAdminTokenControls(); bindQuickDemoButtons(); await bindPaymentResultPages(); await bootstrapAdminGate(); renderAdminSummary(); bindAdminActions(); });
  window.NV0App = { read, write, lookupOrder, createOrder, createDemo, createContact, createLookup, ensureSeedData, renderAdminSummary, advanceOrder, toggleOrderPayment, republishOrder, validateEmail, validateProduct, validatePlan, setAdminToken, getAdminToken, loadSystemConfig, publicBoardHref, productBoardHref, portalHref };
})();