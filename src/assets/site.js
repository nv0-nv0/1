(function(){
  const config = window.NV0_SITE_DATA || {};
  const products = Object.fromEntries((config.products || []).map((item) => [item.key, item]));
  const path = location.pathname.replace(/index\.html$/, '');
  const depth = path.split('/').filter(Boolean).length;
  const base = depth === 0 ? './' : '../'.repeat(depth);
  const pageKey = document.body.dataset.page || 'home';
  const productKey = document.body.dataset.product || '';
  const product = products[productKey];
  const navItems = [
    ['회사', `${base}company/index.html`, 'company'],
    ['공통 엔진', `${base}engine/index.html`, 'engine'],
    ['제품 모듈', `${base}products/index.html`, 'products'],
    ['문제별 시작', `${base}solutions/index.html`, 'solutions'],
    ['가격', `${base}pricing/index.html`, 'pricing'],
    ['문서', `${base}docs/index.html`, 'docs'],
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
  function buildResultPack(target, payload){
    const outputs = (target?.outputs || []).slice(0, 3).map((title, idx) => ({
      title,
      note: idx === 0 ? `${payload.company || '샘플 회사'} 상황에 맞춘 첫 제안안` : `${payload.plan || 'Starter'} 플랜에 포함된 결과 자료`,
    }));
    return {
      summary: `${target?.name || ''} 정상작동 설정과 발행 제공 자료가 자동으로 준비되었습니다. 결제 직후 바로 확인하고 활용할 수 있습니다.`,
      outputs,
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
    const notice = info.support_notice || '공개 사이트는 읽기와 구매를, 관리자 메뉴는 운영과 자동발행 설정을 담당합니다.';
    footer.innerHTML = `<div class="container footer-grid"><div><div class="brand"><span class="brand-mark">N0</span><span class="brand-copy"><strong>${config.brand?.name || 'NV0'}</strong><span>공통 엔진 하나로 데모, 결제, 제공, 포털, 운영을 묶습니다.</span></span></div><small style="margin-top:14px">공개 사이트는 고객이 읽고 고르고 결제하는 흐름에 집중하고, 자동발행 설정과 운영 메뉴는 관리자 허브에서 따로 관리합니다.</small></div><div><strong>바로 보기</strong><small><a href="${base}products/index.html">제품 모듈</a><br><a href="${base}solutions/index.html">문제별 시작</a><br><a href="${base}pricing/index.html">가격</a><br><a href="${base}docs/index.html">문서 센터</a><br><a href="${base}faq/index.html">FAQ</a></small></div><div><strong>운영/정책</strong><small>운영명: ${esc(operator)}<br><a href="mailto:${email}">${esc(email)}</a><br>${esc(notice)}<br><a href="${base}portal/index.html">고객 포털</a><br><a href="${base}contact/index.html">추가 확인</a><br><a href="${base}legal/privacy/index.html">개인정보처리방침</a><br><a href="${base}legal/terms/index.html">이용약관</a><br><a href="${base}legal/refund/index.html">환불 정책</a></small></div></div>`;
  }
  function currencyPlan(productKey) { const target = products[productKey]; return target ? target.plans.map((item) => `${item.name} ${item.price}`).join(' · ') : 'Starter · Growth · Scale'; }
  function buildHomeProducts() { const root = document.getElementById('product-grid'); if (!root) return; root.innerHTML = Object.values(products).map((item) => `<article class="card product-card strong ${item.theme}"><span class="tag theme-chip">${item.label}</span><h3>${item.name}</h3><p>${item.headline}</p><ul class="clean">${item.value_points.slice(0,3).map((text) => `<li>${text}</li>`).join('')}</ul><div class="muted-box" style="margin-top:18px">시작가: ${item.plans[0]?.price || '-'} · ${esc(item.pricing_basis || '')}</div><div class="actions"><a class="button" href="${base}products/${item.key}/demo/index.html">즉시 데모</a><a class="button secondary" href="${base}products/${item.key}/plans/index.html">플랜 보기</a><a class="button ghost" href="${base}products/${item.key}/index.html">요약 보기</a></div></article>`).join(''); }
  function buildModuleMatrix() { const root = document.getElementById('module-matrix'); if (!root) return; root.innerHTML = Object.values(products).map((item) => `<article class="story-card ${item.theme}"><span class="tag theme-chip">${item.tag}</span><h3>${item.name}</h3><p>${item.summary}</p><div class="actions"><a class="button soft" href="${base}products/${item.key}/index.html">요약 보기</a><a class="button ghost" href="${base}products/${item.key}/demo/index.html">즉시 데모</a></div></article>`).join(''); }
  function renderLiveStats(){ const root = document.getElementById('live-stats'); if (!root) return; ensureSeedData(); const orders = read(STORE.orders); const publications = read(STORE.publications); const demos = read(STORE.demos); const contacts = read(STORE.contacts); const started = orders.length || '상시'; const demosCount = demos.length || Object.keys(products).length; root.innerHTML = `<article class="mini"><strong>${started}</strong><span>${orders.length ? '저장된 결제 접수' : '결제 가능'}</span></article><article class="mini"><strong>${publications.length}</strong><span>읽어볼 자동발행 글</span></article><article class="mini"><strong>${demosCount}</strong><span>${demos.length ? '확인된 샘플 결과' : '데모 시연 가능한 제품'}</span></article><article class="mini"><strong>${contacts.length || '이메일'}</strong><span>${contacts.length ? '남겨진 추가 확인' : (config.brand?.contact_email || '추가 확인 채널')}</span></article>`; }
  function renderWorkspaceCards(){ const root = document.getElementById('workspace-records'); if (!root) return; const orders = read(STORE.orders).slice(0, 2); const demos = read(STORE.demos).slice(0, 1); const contacts = read(STORE.contacts).slice(0, 1); const cards = []; orders.forEach((item) => cards.push(`<article class="record-card"><span class="tag">결제 접수</span><h4>${esc(item.company || item.email)}</h4><p>${esc(item.productName)} · ${esc(item.plan)} · 조회 코드 <span class="inline-code">${esc(item.code)}</span></p><div class="small-actions"><a href="${portalHref(item)}">제공 상태 확인</a><a href="${base}products/${item.product}/board/index.html">콘텐츠 허브 보기</a></div></article>`)); demos.forEach((item) => cards.push(`<article class="record-card"><span class="tag">체험</span><h4>${esc(item.company || item.email)}</h4><p>${esc(item.productName)} 데모 시연 확인 · ${esc(item.code)}</p><div class="small-actions"><a href="${base}products/${item.product}/index.html">자세히 보기</a><a href="${base}products/${item.product}/index.html#order">결제 계속하기</a></div></article>`)); contacts.forEach((item) => cards.push(`<article class="record-card"><span class="tag">추가 확인</span><h4>${esc(item.company || item.email)}</h4><p>${esc(item.productName)} · ${esc(item.issue || '')}</p><div class="small-actions"><a href="${item.product ? `${base}products/${item.product}/index.html` : `${base}company/index.html`}">관련 정보</a><a href="${item.product ? `${base}products/${item.product}/index.html#intro` : `${base}contact/index.html`}">다음 단계 보기</a></div></article>`)); root.innerHTML = cards.length ? cards.join('') : '<div class="empty-box">아직 확인된 데모 시연이나 결제 흐름이 없습니다. 원하는 제품에서 콘텐츠 허브와 데모부터 확인해 보세요.</div>'; }
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
        document.querySelectorAll('#quick-demo-result').forEach((root) => { root.innerHTML = html || '<div class="empty-box">표시할 미리보기가 없습니다.</div>'; });
      });
    });
  }
  function buildPlans() { const root = document.getElementById('plan-grid'); if (!root || !product) return; root.innerHTML = product.plans.map((plan) => { const recommended = plan.recommended ? '<span class="tag" style="margin-left:8px">추천</span>' : ''; const meta = [plan.delivery ? `납기 ${esc(plan.delivery)}` : '', plan.revisions ? esc(plan.revisions) : ''].filter(Boolean).join(' · '); const includes = Array.isArray(plan.includes) && plan.includes.length ? `<ul class="clean plan-include-list">${plan.includes.map((item) => `<li>${esc(item)}</li>`).join('')}</ul>` : ''; return `<article class="plan-card ${plan.recommended ? 'recommended' : ''}"><div class="plan-head"><span class="tag">${esc(plan.name)}</span>${recommended}</div><h3>${esc(plan.price)}</h3><p>${esc(plan.note || '')}</p>${meta ? `<div class="plan-meta">${meta}</div>` : ''}${includes}<div class="small-actions"><a class="button" href="#order" data-plan-pick="${esc(plan.name)}">이 플랜으로 결제 계속하기</a></div></article>`; }).join(''); root.querySelectorAll('[data-plan-pick]').forEach((btn)=>btn.addEventListener('click',()=>{ const form=document.getElementById('product-checkout-form'); if(form){ const select=form.querySelector('select[name="plan"]'); if(select) select.value=btn.dataset.planPick; location.hash='order'; }})); }
  function fillProductSlots() { if (!product) return; document.querySelectorAll('[data-fill="product-name"]').forEach((el) => el.textContent = product.name); document.querySelectorAll('[data-fill="product-headline"]').forEach((el) => el.textContent = product.headline); document.querySelectorAll('[data-fill="product-summary"]').forEach((el) => el.textContent = product.summary); document.querySelectorAll('[data-fill="product-problem"]').forEach((el) => el.textContent = product.problem); document.querySelectorAll('[data-fill="product-pricing"]').forEach((el) => el.textContent = currencyPlan(product.key)); const valueRoot = document.getElementById('product-values'); if (valueRoot) valueRoot.innerHTML = product.value_points.map((item) => `<li>${item}</li>`).join(''); const outputRoot = document.getElementById('product-outputs'); if (outputRoot) outputRoot.innerHTML = product.outputs.map((item) => `<li>${item}</li>`).join(''); const workflowRoot = document.getElementById('product-workflow'); if (workflowRoot) workflowRoot.innerHTML = (product.workflow || []).map((item) => `<li>${item}</li>`).join(''); const demoRoot = document.getElementById('product-demo-scenarios'); if (demoRoot) demoRoot.innerHTML = (product.demo_scenarios || []).map((item) => `<li>${item}</li>`).join(''); const relatedRoot = document.getElementById('product-related-modules'); if (relatedRoot) relatedRoot.innerHTML = (product.related_modules || []).map((key) => products[key]).filter(Boolean).map((item) => `<article class="story-card ${item.theme}"><span class="tag theme-chip">${esc(item.label)}</span><h3>${esc(item.name)}</h3><p>${esc(item.summary)}</p><div class="small-actions"><a href="${base}products/${item.key}/index.html#intro">제품 설명 보기</a><a href="${base}products/${item.key}/index.html#demo">데모 시연</a></div></article>`).join('') || '<div class="empty-box">연결된 제품이 아직 없습니다.</div>'; const faqRoot = document.getElementById('product-faq'); if (faqRoot) faqRoot.innerHTML = (product.faqs || []).map((item) => `<article class="faq-card"><span class="tag">Q</span><h3>${esc(item.q)}</h3><p>${esc(item.a)}</p></article>`).join(''); const actions = document.getElementById('product-actions'); if (actions) actions.innerHTML = `<a class="button" href="${base}products/${product.key}/demo/index.html">즉시 데모</a><a class="button secondary" href="${base}products/${product.key}/plans/index.html">플랜 보기</a><a class="button ghost" href="${base}products/${product.key}/delivery/index.html">전달물 보기</a><a class="button ghost" href="${base}products/${product.key}/board/index.html">게시판 보기</a>`; const basis = document.getElementById('product-pricing-basis'); if (basis) basis.textContent = product.pricing_basis || ''; const demoForm = document.getElementById('product-demo-form'); if (demoForm) { const defaults = product.demo_defaults || {}; demoForm.querySelectorAll('[data-demo-field]').forEach((input)=>{ const key = input.dataset.demoField; if (defaults[key] && !input.value) input.value = defaults[key]; }); } }
  function advanceOrder(orderId){ return updateItem(STORE.orders, orderId, (item) => { if (item.paymentStatus !== 'paid') throw new Error('결제 완료 전에는 자동 제공을 완료할 수 없습니다.'); return {...item, status:'delivered', deliveryMeta:{...(item.deliveryMeta||{}), automation:'local_auto', deliveredAt: stamp()}, updatedAt: stamp()}; }); }
  function toggleOrderPayment(orderId){ return updateItem(STORE.orders, orderId, (item) => { const paymentStatus = item.paymentStatus === 'paid' ? 'pending' : 'paid'; const status = paymentStatus === 'paid' ? 'delivered' : 'payment_pending'; return {...item, paymentStatus, status, deliveryMeta: paymentStatus === 'paid' ? { ...(item.deliveryMeta||{}), automation:'local_auto', deliveredAt: stamp() } : item.deliveryMeta, updatedAt: stamp()}; }); }
  function republishOrder(orderId){ const orders = read(STORE.orders); const order = orders.find((item) => item.id === orderId); if (!order) throw new Error('결제 접수를 찾지 못했습니다.'); const extra = createPublicationsForOrder(order); return updateItem(STORE.orders, orderId, (item) => ({...item, publicationIds: [...(item.publicationIds || []), ...extra.map((p) => p.id)], publicationCount: (item.publicationCount || 0) + extra.length, updatedAt: stamp()})); }
  function lookupOrder(email, code){ const orders = read(STORE.orders); if (code) { const exact = orders.find((item) => String(item.code).toLowerCase() === String(code).toLowerCase()); if (exact && (!email || String(exact.email).toLowerCase() === String(email).toLowerCase())) return exact; } if (email) return orders.find((item) => String(item.email).toLowerCase() === String(email).toLowerCase()) || null; return null; }
  function renderPublicationDetail(targetId, items){ const root = document.getElementById(targetId); if (!root) return; const params = new URLSearchParams(location.search); const postId = params.get('post'); const item = items.find((entry) => entry.id === postId) || items[0]; if (!item) { root.innerHTML = '<div class="empty-box">표시할 글이 없습니다.</div>'; return; } const detailProduct = products[item.product] || null; const portalLink = item.code ? `${base}portal/index.html?code=${encodeURIComponent(item.code)}` : `${base}portal/index.html`; root.innerHTML = `<article class="post-detail"><span class="tag">${esc(item.productName || productName(item.product))}</span><h3>${esc(item.title)}</h3><p>${esc(item.summary)}</p><div class="kv"><div class="row"><strong>게시 시각</strong><span>${formatDate(item.createdAt)}</span></div><div class="row"><strong>조회 코드</strong><span>${esc(item.code || '기본 안내')}</span></div><div class="row"><strong>글 유형</strong><span>${esc(item.source || 'board')}</span></div><div class="row"><strong>본문</strong><span>${esc(item.body || item.summary).split('\n').join('<br>')}</span></div></div><div class="small-actions">${boardCtaMarkup(item)}<a href="${detailProduct ? `${base}products/${item.product}/index.html` : `${base}products/index.html`}">자세히 보기</a><a href="${base}products/${item.product}/board/index.html?post=${item.id}">같은 제품 글 더 보기</a><a href="${portalLink}">제공 상태 확인</a></div></article>`; }
  function renderPublicBoard() { const root = document.getElementById('public-board-grid'); if (!root) return; ensureSeedData(); const items = read(STORE.publications).sort((a,b) => (a.createdAt < b.createdAt ? 1 : -1)); if (!items.length) { root.innerHTML = '<div class="empty-box">아직 공개된 글이 없습니다.</div>'; return; } root.innerHTML = items.slice(0, 12).map((item, idx) => `<article class="board-card board-card-blog"><span class="tag">AI 글 ${idx + 1}</span><h3>${esc(item.title)}</h3><p>${esc(item.summary)}</p><div class="board-meta"><span>${esc(item.productName || productName(item.product))}</span><span>${esc(String(item.readMinutes || 3))}분 읽기</span><span>${esc(item.format || 'ai-hybrid-blog')}</span></div><div class="small-actions">${boardCtaMarkup(item)}<a href="${publicBoardHref(item.id)}">블로그 글 보기</a><a href="${base}products/${item.product}/index.html">제품 상세</a></div></article>`).join(''); renderPublicationDetail('public-post-detail', items); }
  function renderProductBoard() { const root = document.getElementById('product-board-grid'); if (!root || !product) return; ensureSeedData(); const dynamic = read(STORE.publications).filter((item) => item.product === product.key); const automation = product.board_automation || {}; const seedCards = (automation.topics || []).map((topic, idx) => buildPublicationRecord({ product: product.key, title: topic.title, summary: topic.summary, source:'topic-seed', code:'', createdAt: stamp(), ctaLabel: topic.ctaText || automation.cta_label || '제품 보기', ctaHref: buildCtaHref(automation.cta_href, product.key), topicSummary: topic.summary, id:`topic-${idx}` })); const items = [...dynamic, ...seedCards].sort((a,b)=>a.createdAt < b.createdAt ? 1 : -1); root.innerHTML = items.slice(0, 12).map((item, idx) => `<article class="board-card board-card-blog"><span class="tag">${product.name} AI 글 ${idx + 1}</span><h3>${esc(item.title)}</h3><p>${esc(item.summary)}</p><div class="board-meta"><span>${esc(String(item.readMinutes || 3))}분 읽기</span><span>${esc(item.format || 'ai-hybrid-blog')}</span></div><div class="small-actions">${boardCtaMarkup(item)}<a href="${productBoardHref(product.key, item.id)}">블로그 글 보기</a><a href="${base}products/${product.key}/index.html#order">결제 진행</a></div></article>`).join(''); renderPublicationDetail('product-post-detail', items); }
  function explainPaymentUnavailable(payment){ if (payment?.mock) return '현재는 mock 결제 모드입니다.'; if (!payment?.enabled) return '결제 설정이 아직 완료되지 않았습니다. 운영자에게 Toss 키와 웹훅 설정을 확인해 달라고 요청해 주세요.'; if (!window.TossPayments) return '외부 결제 스크립트를 불러오지 못했습니다. 네트워크 또는 브라우저 차단 설정을 확인해 주세요.'; return '외부 결제 연결을 확인하지 못했습니다.'; }
  function buildDemoPreviewHtml(payload, options = {}, meta = {}){ const target = products[payload.product]; const outputs = (target?.outputs || []).slice(0,3).map((item)=>`<li><strong>${esc(item)}</strong><span>${esc(payload.company || '샘플 회사')} · ${esc(payload.goal || '')} · ${esc(payload.keywords || '')}</span></li>`).join(''); const orderHref = options.orderHref || '#order'; const boardHref = options.boardHref || `${base}products/${payload.product}/board/index.html`; const detailHref = options.detailHref || `${base}products/${payload.product}/index.html`; const demoMeta = meta.code ? `<div class="notice"><strong>데모 시연 코드</strong><br><span class="inline-code">${esc(meta.code)}</span>${meta.remoteSaved ? '<br>데모 정보가 저장되어 관리자 화면과 후속 안내에 바로 연결됩니다.' : '<br>현재 화면에도 데모 시연 정보가 저장되었습니다.'}</div>` : ''; return `<div class="order-result"><strong>${esc(target?.name || '')} 샘플 결과 미리보기</strong><div>회사: <span class="inline-code">${esc(payload.company)}</span></div><div>목표: ${esc(payload.goal)}</div><div>핵심 키워드: ${esc(payload.keywords)}</div>${demoMeta}<p style="margin:10px 0 14px">아래 항목은 실제 결제 후 받아보게 될 정상작동 설정과 발행 제공 자료의 톤과 구성을 미리 보여주는 예시입니다.</p><ul class="output-list">${outputs}</ul><div class="small-actions"><a class="button" href="${orderHref}">이 조건으로 결제 이어가기</a><a class="button secondary" href="${detailHref}">제품 설명 보기</a><a class="button ghost" href="${boardHref}">콘텐츠 허브 보기</a></div></div>`; }
  function bindProductDemoForm(){
    const form = document.getElementById('product-demo-form'); if (!form || !product) return;
    form.addEventListener('submit', (event)=>{ event.preventDefault(); withSubmitLock(form, async () => {
      const data=new FormData(form);
      const payload={
        product: product.key,
        company:String(data.get('company')||''),
        name:String(data.get('name')||''),
        email:String(data.get('email')||''),
        team:String(data.get('team')||''),
        goal:String(data.get('goal')||''),
        keywords:String(data.get('keywords')||''),
        phone:String(data.get('phone')||''),
        link:String(data.get('link')||''),
        urgency:String(data.get('urgency')||''),
        plan:String(data.get('plan')||'Starter')
      };
      try {
        assert(payload.company,'회사명을 입력하세요.');
        assert(payload.name,'담당자명을 입력하세요.');
        assert(validateEmail(payload.email),'이메일 형식이 올바르지 않습니다.');
        assert(payload.goal,'목표를 입력하세요.');
        const detailBits = [payload.goal, payload.keywords ? `키워드: ${payload.keywords}` : '', payload.phone ? `연락처: ${payload.phone}` : '', payload.link ? `참고 링크: ${payload.link}` : '', payload.urgency ? `긴급도: ${payload.urgency}` : ''].filter(Boolean);
        const demoNeed = detailBits.join(' / ');
        const demoPayload = { product: payload.product, company: payload.company, name: payload.name, email: payload.email, team: payload.team, need: demoNeed, keywords: payload.keywords, plan: payload.plan };
        let entry = null; let remoteSaved = false;
        const remote = await postIfConfigured(config.integration?.demo_endpoint, demoPayload);
        if (remote.mode === 'remote' && remote.ok && remote.json?.demo) { applyStatePayload(remote.json?.state); await syncRemoteState(); entry = remote.json.demo; remoteSaved = true; }
        else if (remote.mode === 'remote' && !remote.ok) { throw new Error(remote.json?.detail || remote.text || '데모 신청 정보를 저장하지 못했습니다.'); }
        else { entry = createDemo(demoPayload); }
        showResult('product-demo-result', buildDemoPreviewHtml(payload, { orderHref:'#order', detailHref:`${base}products/${product.key}/index.html`, boardHref:`${base}products/${product.key}/board/index.html` }, { code: entry.code, remoteSaved }));
        const orderForm=document.getElementById('product-checkout-form');
        if(orderForm){
          const company=orderForm.querySelector('input[name="company"]');
          const name=orderForm.querySelector('input[name="name"]');
          const email=orderForm.querySelector('input[name="email"]');
          const plan=orderForm.querySelector('select[name="plan"]');
          if(company && !company.value) company.value=payload.company;
          if(name && !name.value) name.value=payload.name;
          if(email && !email.value) email.value=payload.email;
          if(plan) plan.value=payload.plan;
          const note=orderForm.querySelector('textarea[name="note"], input[name="note"]');
          if(note && !note.value) note.value=`데모 시연 코드: ${entry.code}
체험 목표: ${payload.goal}${payload.keywords ? `
키워드: ${payload.keywords}` : ''}${payload.link ? `
참고 링크: ${payload.link}` : ''}${payload.urgency ? `
긴급도: ${payload.urgency}` : ''}`;
        }
        renderAdminSummary(); renderWorkspaceCards();
      } catch(error){ showResult('product-demo-result', `<strong>데모 시연을 준비하지 못했습니다.</strong><br>${esc(createFriendlyError(error,'데모 시연 오류'))}`); }
    }); });
  }
  async async function bindProductCheckoutForm(){
    const form = document.getElementById('product-checkout-form'); if (!form || !product) return;
    form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
      const data = new FormData(form);
      const memo = [String(data.get('note') || ''), String(data.get('phone') || '') ? `연락처: ${String(data.get('phone') || '')}` : '', String(data.get('link') || data.get('referenceUrl') || '') ? `참고 링크: ${String(data.get('link') || data.get('referenceUrl') || '')}` : '', String(data.get('urgency') || '') ? `긴급도: ${String(data.get('urgency') || '')}` : '', String(data.get('billing_note') || data.get('context') || '') ? `추가 요청: ${String(data.get('billing_note') || data.get('context') || '')}` : ''].filter(Boolean).join('
');
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
  async async function bindDemoForm(){
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
        const preview = buildDemoPreviewHtml(payload, { orderHref:`${base}products/${payload.product}/index.html#order`, detailHref:`${base}products/${payload.product}/index.html`, boardHref:`${base}products/${payload.product}/board/index.html` }, { code: entry.code, remoteSaved });
        showResult('demo-result', preview);
        renderLiveStats(); renderWorkspaceCards(); renderAdminSummary();
      } catch (error) { showResult('demo-result', `<strong>샘플 결과를 준비하지 못했습니다.</strong><br>${esc(createFriendlyError(error, '데모 시연 오류가 발생했습니다.'))}`); }
    }); });
  }
  async async function bindContactForm(){
    const form = document.getElementById('contact-form'); if (!form) return;
    form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
      const data = new FormData(form);
      const payload = { product: String(data.get('product') || ''), company: String(data.get('company') || ''), name: String(data.get('name') || ''), email: String(data.get('email') || ''), issue: [String(data.get('issue') || ''), String(data.get('phone') || '') ? `연락처: ${String(data.get('phone') || '')}` : '', String(data.get('link') || data.get('referenceUrl') || '') ? `참고 링크: ${String(data.get('link') || data.get('referenceUrl') || '')}` : '', String(data.get('urgency') || '') ? `긴급도: ${String(data.get('urgency') || '')}` : '', String(data.get('reply_time') || data.get('replyWindow') || '') ? `희망 회신 시간: ${String(data.get('reply_time') || data.get('replyWindow') || '')}` : ''].filter(Boolean).join('
') };
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
  async async function bindCheckoutForm(){
    const form = document.getElementById('checkout-form'); if (!form) return;
    form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
      const data = new FormData(form);
      const note = [String(data.get('note') || ''), String(data.get('phone') || '') ? `연락처: ${String(data.get('phone') || '')}` : '', String(data.get('link') || data.get('referenceUrl') || '') ? `참고 링크: ${String(data.get('link') || data.get('referenceUrl') || '')}` : '', String(data.get('urgency') || '') ? `긴급도: ${String(data.get('urgency') || '')}` : '', String(data.get('reply_time') || data.get('replyWindow') || '') ? `희망 회신 시간: ${String(data.get('reply_time') || data.get('replyWindow') || '')}` : ''].filter(Boolean).join('
');
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
    async function bindPortalLookup() { const form = document.getElementById('portal-lookup-form'); if (!form) return; const params = new URLSearchParams(location.search); const emailEl = form.querySelector('input[name="email"]'); const codeEl = form.querySelector('input[name="code"]'); if (params.get('email') && emailEl) emailEl.value = params.get('email'); if (params.get('code') && codeEl) codeEl.value = params.get('code'); form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => { const data = new FormData(form); const payload = { email: normalizeEmail(String(data.get('email') || '')), code: normalizeCode(String(data.get('code') || '')) }; try { const lookup = createLookup(payload); const remote = await postIfConfigured(config.integration?.portal_lookup_endpoint, lookup); if (remote.mode === 'remote' && remote.ok) { applyStatePayload(remote.json?.state); await syncRemoteState(); } const order = (remote.mode === 'remote' && remote.ok && remote.json?.order) ? remote.json.order : lookupOrder(payload.email, payload.code); const publications = (remote.mode === 'remote' && remote.ok && Array.isArray(remote.json?.publications)) ? remote.json.publications : read(STORE.publications).filter((item) => (order?.publicationIds || []).includes(item.id)); if (!order) { showResult('portal-result', `<strong>일치하는 결제 접수를 찾지 못했습니다.</strong><br>이메일 또는 조회 코드를 다시 확인하세요.`); const mock = document.getElementById('portal-mock'); if (mock) mock.innerHTML = '<div class="empty-box">일치하는 결제 정보가 없습니다. 입력한 내용을 다시 확인해 주세요.</div>'; renderAdminSummary(); return; } showResult('portal-result', `<strong>조회가 완료되었습니다.</strong><br>조회 코드 <span class="inline-code">${order.code}</span> 기준으로 결과 전달 정보를 불러왔습니다.`); const mock = document.getElementById('portal-mock'); if (mock) mock.innerHTML = `<article class="portal-card"><div class="portal-meta"><div class="meta"><strong>제품</strong><span>${esc(order.productName)}</span></div><div class="meta"><strong>플랜</strong><span>${esc(order.plan)} · ${esc(order.price)}</span></div><div class="meta"><strong>결제 상태</strong><span>${paymentStatusLabel(order.paymentStatus)}</span></div><div class="meta"><strong>결과 상태</strong><span>${orderStatusLabel(order.status)}</span></div></div><div class="notice-strong"><strong>결과 전달 요약</strong><p>${esc(order.resultPack.summary)}</p></div><div class="split-two"><div><h4>받아보실 자료</h4><ul class="output-list">${order.resultPack.outputs.map((item) => `<li><strong>${esc(item.title)}</strong><span>${esc(item.note)}</span></li>`).join('')}</ul></div><div><h4>함께 확인할 공개 글</h4><ul class="output-list">${publications.map((item) => `<li><strong>${esc(item.title)}</strong><span><a href="${productBoardHref(order.product, item.id)}">제품 글 보기</a> · <a href="${publicBoardHref(item.id)}">전체 글 보기</a></span></li>`).join('') || '<li><strong>준비 중</strong><span>연결된 게시물이 없습니다.</span></li>'}</ul></div></div><div class="small-actions"><a href="${base}products/${order.product}/index.html">자세히 보기</a><a href="${base}products/${order.product}/board/index.html">콘텐츠 허브 보기</a><a href="${base}contact/index.html?product=${order.product}">추가 확인 요청</a></div></article>`; renderAdminSummary(); } catch (error) { showResult('portal-result', `<strong>조회하지 못했습니다.</strong><br>${esc(createFriendlyError(error, '결과 조회 중 오류가 발생했습니다.'))}`); const mock = document.getElementById('portal-mock'); if (mock) mock.innerHTML = '<div class="empty-box">조회 조건을 다시 확인해 주세요.</div>'; } }); }); if (params.get('email') || params.get('code')) form.requestSubmit(); }
  function setAdminShellVisible(visible){
    const shell = document.getElementById('admin-shell');
    const gate = document.getElementById('admin-gate-result');
    if (shell) shell.style.display = visible ? '' : 'none';
    if (gate) gate.innerHTML = visible ? '관리자 운영 메뉴가 열렸습니다.' : '관리자 비밀키를 입력하면 운영 메뉴가 열립니다.';
  }
  async function validateAdminToken(){
    const token = getAdminToken();
    if (!token) return false;
    const url = config.integration?.admin_validate_endpoint || '';
    if (!url) return true;
    try {
      const res = await fetch(url, { headers: headersFor(url, { 'Accept':'application/json' }) });
      return res.ok;
    } catch { return false; }
  }
  function renderAdminAutomation(){
    const root = document.getElementById('admin-automation-grid');
    if (!root) return;
    root.innerHTML = Object.values(products).map((item) => {
      const automation = item.board_automation || {};
      const topics = Array.isArray(automation.topics) ? automation.topics.length : 0;
      return `<article class="activity-card"><span class="tag">${esc(item.name)}</span><h4>자동발행 설정</h4><p>발행 간격 ${esc(String(automation.interval_hours || '-'))}시간 · 회차당 ${esc(String(automation.publish_count_per_cycle || '-'))}건 · 준비된 주제 ${topics}개</p><div class="small-actions"><a href="${base}products/${item.key}/board/index.html">게시판 보기</a><button data-admin-action="republish-latest" data-product-key="${item.key}">최신 글 점검</button></div></article>`;
    }).join('');
  }
  function renderAdminSummary() { const root = document.getElementById('admin-summary'); const orders = read(STORE.orders); const demos = read(STORE.demos); const contacts = read(STORE.contacts); const lookups = read(STORE.lookups); const publications = read(STORE.publications); if (root) root.innerHTML = `<article class="admin-card"><span class="tag">결제</span><h3>${orders.length}</h3><p>저장된 결제 접수 수</p></article><article class="admin-card"><span class="tag">데모</span><h3>${demos.length}</h3><p>즉시 데모 저장 수</p></article><article class="admin-card"><span class="tag">예외 문의/조회</span><h3>${contacts.length + lookups.length}</h3><p>예외 문의와 포털 조회 수</p></article><article class="admin-card"><span class="tag">발행 카드</span><h3>${publications.length}</h3><p>자동 발행 카드 수</p></article>`; renderAdminAutomation(); const feed = document.getElementById('admin-feed'); if (feed) { const stream = [...orders.map((item) => ({title:`결제접수 ${item.code}`, meta:`${item.productName} · ${item.company || item.email}`, createdAt:item.createdAt})), ...demos.map((item) => ({title:`데모 ${item.code}`, meta:`${item.productName} · ${item.company || item.email}`, createdAt:item.createdAt})), ...contacts.map((item) => ({title:`예외 문의 ${item.code}`, meta:`${item.productName} · ${item.issue}`, createdAt:item.createdAt})), ...lookups.map((item) => ({title:'포털 조회', meta:`${item.email} / ${item.code || '최근 결제 건'}`, createdAt:item.createdAt}))].sort((a,b) => a.createdAt < b.createdAt ? 1 : -1); feed.innerHTML = stream.length ? stream.slice(0,20).map((item) => `<div class="mock-step"><strong>${esc(item.title)}</strong><span>${formatDate(item.createdAt)}</span><span>${esc(item.meta)}</span></div>`).join('') : '<p class="feed-empty">아직 저장된 요청이 없습니다.</p>'; } const orderRoot = document.getElementById('admin-orders'); if (orderRoot) orderRoot.innerHTML = orders.length ? orders.map((item) => `<article class="order-admin-card"><span class="tag">${esc(item.productName)}</span><h4>${esc(item.company || item.email)}</h4><p>조회 코드 <span class="inline-code">${esc(item.code)}</span> · ${esc(item.plan)} · ${esc(item.price)}</p><div class="badge-row">${buildStatusPill(item.paymentStatus === 'paid' ? '결제 완료' : '결제 대기', item.paymentStatus === 'paid' ? 'status-paid' : 'status-pending')}${buildStatusPill(item.status, item.status === 'published' ? 'status-published' : item.status === 'delivered' ? 'status-delivered' : 'status-draft')}</div><div class="small-actions"><button class="primary" data-admin-action="advance" data-order-id="${item.id}">자동 제공 재확인</button><button data-admin-action="toggle-payment" data-order-id="${item.id}">결제 상태 전환</button><button data-admin-action="republish" data-order-id="${item.id}">재발행</button><a href="${portalHref(item)}">포털</a></div></article>`).join('') : '<div class="empty-box">결제 기록이 아직 없습니다.</div>'; const pubRoot = document.getElementById('admin-publications'); if (pubRoot) pubRoot.innerHTML = publications.length ? publications.slice(0,16).map((item) => `<article class="pub-admin-card"><span class="tag">${esc(item.productName || productName(item.product))}</span><h4>${esc(item.title)}</h4><p>${esc(item.summary)}</p><div class="small-actions"><a href="${publicBoardHref(item.id)}">글 보기</a><a href="${base}products/${item.product}/board/index.html?post=${item.id}">제품 글 보기</a></div></article>`).join('') : '<div class="empty-box">발행된 카드가 없습니다.</div>'; const reqRoot = document.getElementById('admin-requests'); if (reqRoot) { const entries = [...demos.map((item) => ({label:'데모', title:item.code, meta:`${item.productName} · ${item.company || item.email}`})), ...contacts.map((item) => ({label:'예외 문의', title:item.code, meta:`${item.productName} · ${item.issue}`}))]; reqRoot.innerHTML = entries.length ? entries.map((item) => `<article class="activity-card"><span class="tag">${esc(item.label)}</span><h4>${esc(item.title)}</h4><p>${esc(item.meta)}</p></article>`).join('') : '<div class="empty-box">데모와 예외 문의 요청이 아직 없습니다.</div>'; } }
  function bindAdminTokenControls(){ const input = document.getElementById('admin-token-input'); const save = document.getElementById('admin-token-save'); const clear = document.getElementById('admin-token-clear'); if (input) input.value = getAdminToken(); setAdminShellVisible(false); if (save) save.addEventListener('click', async () => { setAdminToken(input?.value || ''); const valid = await validateAdminToken(); if (!valid) { setAdminShellVisible(false); showResult('admin-gate-result', '관리자 비밀키가 맞지 않거나 상태를 불러오지 못했습니다.'); return; } await syncRemoteState(); setAdminShellVisible(true); showResult('admin-action-result', '관리자 비밀키를 확인하고 운영 메뉴를 열었습니다.'); renderAdminSummary(); }); if (clear) clear.addEventListener('click', () => { setAdminToken(''); if (input) input.value=''; setAdminShellVisible(false); showResult('admin-gate-result', '관리자 비밀키를 지웠습니다.'); }); }
  async function bootstrapAdminGate(){
    if (pageKey !== 'admin') return;
    const valid = await validateAdminToken();
    if (valid) {
      await syncRemoteState();
      setAdminShellVisible(true);
      renderAdminSummary();
    } else {
      setAdminShellVisible(false);
    }
  }
  async function bindPaymentResultPages(){ if (pageKey === 'payment-success') { const params = new URLSearchParams(location.search); const paymentKey = params.get('paymentKey') || ''; const orderId = params.get('orderId') || ''; const amount = Number(params.get('amount') || 0); if (!config.integration?.toss_confirm_endpoint || !paymentKey || !orderId || !amount) { showResult('payment-success-result', '<strong>결제 승인 정보를 확인하지 못했습니다.</strong><br>paymentKey, orderId, amount를 다시 확인하세요.'); return; } const remote = await postIfConfigured(config.integration.toss_confirm_endpoint, { paymentKey, orderId, amount }); if (remote.mode === 'remote' && remote.ok && remote.json?.order) { applyStatePayload(remote.json?.state); const order = remote.json.order; const boardLink = order.publicationIds?.[0] ? productBoardHref(order.product, order.publicationIds[0]) : `${base}products/${order.product}/board/index.html`; showResult('payment-success-result', `<strong>결제가 완료되었습니다.</strong><br>조회 코드 <span class="inline-code">${esc(order.code)}</span> 기준으로 전달 자료를 바로 확인하실 수 있습니다. 관련 콘텐츠도 함께 둘러보실 수 있습니다.<div class="small-actions"><a href="${portalHref(order)}">결과 전달 확인</a><a href="${boardLink}">콘텐츠 허브 보기</a></div>`); } else { showResult('payment-success-result', `<strong>결제 확인을 완료하지 못했습니다.</strong><br>${esc(remote.json?.detail || remote.text || remote.error || '승인 요청 실패')}`); } } if (pageKey === 'payment-fail') { const params = new URLSearchParams(location.search); showResult('payment-fail-result', `<strong>결제가 완료되지 않았습니다.</strong><br>오류 코드: <span class="inline-code">${esc(params.get('code') || '없음')}</span><br>사유: ${esc(params.get('message') || '사유 미제공')}`); } }
  function bindAdminActions(){ const root = document.getElementById('admin-console'); if (!root) return; root.addEventListener('click', async (event) => { const button = event.target.closest('[data-admin-action]'); if (!button) return; const action = button.dataset.adminAction; const orderId = button.dataset.orderId; try { if (action === 'seed-demo') { const remote = await postIfConfigured(config.integration?.admin_seed_endpoint, {}); if (remote.mode === 'remote' && remote.ok) { applyStatePayload(remote.json?.state); await syncRemoteState(); showResult('admin-action-result', '샘플 데이터를 생성했습니다.'); } else { const order = createOrder({product:'veridion', plan:'Growth', billing:'one-time', paymentMethod:'toss', company:'Demo Company', name:'테스터', email:'demo@nv0.kr', note:'시드 결제'}); createDemo({product:'clearport', company:'Demo Company', name:'테스터', email:'demo@nv0.kr', team:'3명 팀', need:'정상작동 확인'}); createContact({product:'grantops', company:'Demo Company', email:'demo@nv0.kr', issue:'제출 일정 추가 확인'}); showResult('admin-action-result', `샘플 데이터를 생성했습니다. 대표 조회 코드 <span class="inline-code">${order.code}</span>`); } } else if (action === 'reset-all') { const remote = await postIfConfigured(config.integration?.admin_reset_endpoint, {}); if (remote.mode === 'remote' && remote.ok) { applyStatePayload(remote.json?.state); await syncRemoteState(); } else { Object.values(STORE).forEach((key) => localStorage.removeItem(key)); ensureSeedData(); } showResult('admin-action-result', '엔진 데이터를 초기화했습니다.'); } else if (action === 'republish-latest') { showResult('admin-action-result', '최신 자동발행 상태를 점검했습니다. 필요하면 주문별 재발행을 사용하세요.'); } else if (orderId) { if (action === 'advance') { const remote = await postIfConfigured(actionEndpoint(config.integration?.admin_advance_endpoint, orderId), {orderId}); if (remote.mode === 'remote' && remote.ok) { applyStatePayload(remote.json?.state); await syncRemoteState(); } else { advanceOrder(orderId); } showResult('admin-action-result', '결과 전달 상태를 다시 확인했습니다.'); } if (action === 'toggle-payment') { const remote = await postIfConfigured(actionEndpoint(config.integration?.admin_toggle_payment_endpoint, orderId), {orderId}); if (remote.mode === 'remote' && remote.ok) { applyStatePayload(remote.json?.state); await syncRemoteState(); } else { toggleOrderPayment(orderId); } showResult('admin-action-result', '진행 상태를 전환했습니다.'); } if (action === 'republish') { const remote = await postIfConfigured(actionEndpoint(config.integration?.admin_republish_endpoint, orderId), {orderId}); if (remote.mode === 'remote' && remote.ok) { applyStatePayload(remote.json?.state); await syncRemoteState(); const updated = read(STORE.orders).find((item) => item.id === orderId); showResult('admin-action-result', `조회 코드 <span class="inline-code">${updated?.code || ''}</span> 기준으로 공개 콘텐츠를 다시 생성했습니다.`); } else { const updated = republishOrder(orderId); showResult('admin-action-result', `조회 코드 <span class="inline-code">${updated?.code || ''}</span> 기준으로 공개 콘텐츠를 다시 생성했습니다.`); } } } } catch (error) { const msg = createFriendlyError(error, '관리자 작업 중 오류가 발생했습니다.'); showResult('admin-action-result', `${esc(msg)}${String(msg).includes('토큰') ? ' 관리자 토큰을 입력한 뒤 다시 시도하세요.' : ''}`); } renderAdminSummary(); renderPublicBoard(); renderProductBoard(); renderLiveStats(); renderWorkspaceCards(); }); }
  document.addEventListener('DOMContentLoaded', async () => { await loadSystemConfig(); if ((pageKey === 'checkout' || pageKey === 'product') && paymentRuntime()?.enabled && !paymentRuntime()?.mock) await loadTossScript(); const stateSynced = await syncRemoteState(); if (!stateSynced) { const boardSynced = await loadBoardFeed(); if (!boardSynced) ensureSeedData(); } else if (!read(STORE.publications).length) { const boardSynced = await loadBoardFeed(); if (!boardSynced) ensureSeedData(); } else { ensureSeedData(); } renderHeader(); renderFooter(); buildHomeProducts(); buildModuleMatrix(); fillProductSlots(); buildPlans(); setPrefills(); renderPublicBoard(); renderProductBoard(); renderLiveStats(); renderWorkspaceCards(); bindProductDemoForm(); await bindProductCheckoutForm(); bindDemoForm(); bindCheckoutForm(); bindContactForm(); bindPortalLookup(); bindAdminTokenControls(); bindQuickDemoButtons(); await bindPaymentResultPages(); await bootstrapAdminGate(); renderAdminSummary(); bindAdminActions(); });
  window.NV0App = { read, write, lookupOrder, createOrder, createDemo, createContact, createLookup, ensureSeedData, renderAdminSummary, advanceOrder, toggleOrderPayment, republishOrder, validateEmail, validateProduct, validatePlan, setAdminToken, getAdminToken, loadSystemConfig, publicBoardHref, productBoardHref, portalHref };
})();