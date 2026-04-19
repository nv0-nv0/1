(function(){
  const config = window.NV0_SITE_DATA || {};
  const products = Object.fromEntries((config.products || []).map((item) => [item.key, item]));
  const path = location.pathname.replace(/index\.html$/, '');
  const depth = path.split('/').filter(Boolean).length;
  const base = depth === 0 ? './' : '../'.repeat(depth);
  const pageKey = document.body.dataset.page || 'home';
  const STORE = {
    publications: 'nv0-engine-publications',
    scheduler: 'nv0-engine-scheduler',
  };
  const AUTH_KEY = 'nv0-admin-token';
  const navItems = [
    ['홈', `${base}index.html`, 'home'],
    ['게시판', `${base}board/index.html`, 'board'],
    ['관리자', `${base}admin/index.html`, 'admin'],
    ['개인정보처리방침', `${base}legal/privacy/index.html`, 'privacy'],
  ];

  function esc(value){ return String(value ?? '').replace(/[&<>"']/g, (m) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); }
  function clean(value){ return String(value ?? '').trim(); }
  function stamp(){ return new Date().toISOString(); }
  function formatDate(value){ try { return new Date(value).toLocaleString('ko-KR'); } catch { return value; } }
  function uid(prefix){ return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`; }
  function read(key){ try { return JSON.parse(localStorage.getItem(key) || '[]'); } catch { return []; } }
  function write(key, value){ try { localStorage.setItem(key, JSON.stringify(value)); } catch {} }
  function productName(key){ return products[key]?.name || key; }
  function productPrefix(key){ return ({veridion:'VER', clearport:'CLR', grantops:'GRT', draftforge:'DRF'})[key] || String(key || 'GEN').slice(0,3).toUpperCase(); }
  function getAdminToken(){ try { return sessionStorage.getItem(AUTH_KEY) || ''; } catch { return ''; } }
  function setAdminToken(value){ try { if (clean(value)) sessionStorage.setItem(AUTH_KEY, clean(value)); else sessionStorage.removeItem(AUTH_KEY); } catch {} }
  function headersFor(url, extra){ const headers = Object.assign({}, extra || {}); const token = getAdminToken(); if (token && String(url || '').includes('/api/admin/')) headers['X-Admin-Token'] = token; return headers; }
  function publicBoardHref(postId, productKey){ const href = `${base}board/index.html`; const params = new URLSearchParams(); if (postId) params.set('post', postId); if (productKey) params.set('product', productKey); const qs = params.toString(); return qs ? `${href}?${qs}` : href; }
  function buildCtaHref(item){ return item.ctaHref || `${base}products/${item.product}/index.html#intro`; }
  function boardCtaMarkup(item){ return `<a class="button soft" href="${esc(buildCtaHref(item))}">${esc(item.ctaLabel || '제품 설명 보기')}</a>`; }
  function showResult(targetId, html){ const root = document.getElementById(targetId); if (root) root.innerHTML = html; }

  function seededPublications(){
    const now = Date.now();
    return (config.public_board || []).map((item, idx) => ({
      id: `pubseed-${idx + 1}`,
      product: item.product,
      productName: productName(item.product),
      title: item.title,
      summary: item.summary,
      body: `${item.summary}\n\n${productName(item.product)} 축에서 바로 CTA로 연결되도록 준비한 기본 시드 글입니다.`,
      code: `SEED-${idx + 1}`,
      source: 'seed',
      createdAt: new Date(now - idx * 7200000).toISOString(),
      updatedAt: new Date(now - idx * 7200000).toISOString(),
      ctaLabel: products[item.product]?.board_automation?.cta_label || '제품 설명 보기',
      ctaHref: products[item.product]?.board_automation?.cta_href || '',
    }));
  }

  function ensureSeedData(){
    const publications = read(STORE.publications);
    if (!publications.length) write(STORE.publications, seededPublications());
    const scheduler = read(STORE.scheduler);
    const ensuredScheduler = Object.values(products).map((item) => scheduler.find((entry) => entry.product === item.key) || ({ id: `scheduler-${item.key}`, product: item.key, topicIndex: 0, lastPublishedAt: '' }));
    if (ensuredScheduler.length !== scheduler.length || !scheduler.length) write(STORE.scheduler, ensuredScheduler);
    ensureScheduledBoardPosts();
  }

  function ensureScheduledBoardPosts(){
    const publications = read(STORE.publications);
    const scheduler = read(STORE.scheduler);
    let changed = false;
    Object.values(products).forEach((item) => {
      const automation = item.board_automation || {};
      if (!automation.enabled) return;
      const intervalMs = Number(automation.interval_hours || 72) * 3600 * 1000;
      let state = scheduler.find((entry) => entry.product === item.key);
      if (!state) {
        state = { id: `scheduler-${item.key}`, product: item.key, topicIndex: 0, lastPublishedAt: '' };
        scheduler.push(state);
        changed = true;
      }
      const last = state.lastPublishedAt ? Date.parse(state.lastPublishedAt) : 0;
      if (last && Number.isFinite(last) && Date.now() - last < intervalMs) return;
      const topics = automation.topics || [];
      if (!topics.length) return;
      const index = Number(state.topicIndex || 0) % topics.length;
      const topic = topics[index];
      const createdAt = stamp();
      publications.unshift({
        id: uid('pubsch'),
        product: item.key,
        productName: item.name,
        title: topic.title,
        summary: topic.summary,
        body: `${topic.title}\n\n${topic.summary}\n\n이 글은 CTA 포스팅 자동발행 예시입니다. 바로 문의 버튼으로 이어지게 구성했습니다.`,
        code: `AUTO-${productPrefix(item.key)}-${String(index + 1).padStart(3, '0')}`,
        source: 'scheduled',
        createdAt,
        updatedAt: createdAt,
        ctaLabel: topic.ctaText || automation.cta_label || '제품 설명 보기',
        ctaHref: automation.cta_href || '',
      });
      state.lastPublishedAt = createdAt;
      state.topicIndex = (index + 1) % topics.length;
      changed = true;
    });
    if (changed) {
      write(STORE.publications, publications);
      write(STORE.scheduler, scheduler);
    }
  }

  async function fetchJson(url, options){
    const res = await fetch(url, options);
    const text = await res.text();
    let json = null;
    try { json = text ? JSON.parse(text) : null; } catch {}
    if (!res.ok) throw new Error(json?.detail || text || `${res.status}`);
    return json;
  }

  function applyStatePayload(state){
    if (!state || typeof state !== 'object') return;
    if (Array.isArray(state.publications)) write(STORE.publications, state.publications);
    if (Array.isArray(state.scheduler)) write(STORE.scheduler, state.scheduler);
  }

  async function loadBoardFeed(){
    const url = config.integration?.board_feed_endpoint;
    if (!url) return false;
    try {
      const payload = await fetchJson(url, { headers: headersFor(url, { 'Accept': 'application/json' }) });
      if (Array.isArray(payload?.items)) {
        write(STORE.publications, payload.items);
        return true;
      }
    } catch {}
    return false;
  }

  async function syncRemoteState(){
    const url = config.integration?.state_endpoint;
    if (!url || !getAdminToken()) return false;
    try {
      const payload = await fetchJson(url, { headers: headersFor(url, { 'Accept': 'application/json' }) });
      applyStatePayload(payload?.state);
      return true;
    } catch {
      return false;
    }
  }

  function renderHeader(){
    const header = document.getElementById('site-header'); if (!header) return;
    const selected = clean(new URLSearchParams(location.search).get('product'));
    const chips = Object.values(products).map((item) => `<a href="${publicBoardHref('', item.key)}" class="sub-link ${selected === item.key ? 'active' : ''}">${esc(item.name)}</a>`).join('');
    header.innerHTML = `<div class="container nav-wrap"><a class="brand" href="${base}index.html"><span class="brand-mark">N0</span><span class="brand-copy"><strong>${config.brand?.name || 'NV0'}</strong><span>${config.brand?.tagline || ''}</span></span></a><nav class="nav-links">${navItems.map(([label, href, key]) => `<a href="${href}" class="${pageKey === key ? 'active' : ''}">${label}</a>`).join('')}<a class="button" href="${base}products/${item.key}/index.html#intro">문의</a></nav></div><div class="container subnav"><span class="sub-head">제품별 필터</span>${chips}</div>`;
  }

  function renderFooter(){
    const footer = document.getElementById('site-footer'); if (!footer) return;
    footer.innerHTML = `<div class="container footer-grid"><div><div class="brand"><span class="brand-mark">N0</span><span class="brand-copy"><strong>${config.brand?.name || 'NV0'}</strong><span>공개 콘텐츠 허브</span></span></div><small style="margin-top:14px">공개 허브는 읽기 전용으로 운영하며 실제 발행과 관리 기능은 별도 관리자 화면에서 처리합니다.</small></div><div><strong>바로 보기</strong><small><a href="${base}board/index.html">게시판</a><br><a href="${base}admin/index.html">관리자</a><br><a href="${base}legal/privacy/index.html">개인정보처리방침</a></small></div><div><strong>문의</strong><small><a href="mailto:${config.brand?.contact_email || 'ct@nv0.kr'}">${config.brand?.contact_email || 'ct@nv0.kr'}</a><br>운영 범위: 공개 콘텐츠 허브 전용</small></div></div>`;
  }

  function renderProductGrid(){
    const root = document.getElementById('product-grid'); if (!root) return;
    root.innerHTML = Object.values(products).map((item) => `<article class="card product-card strong ${item.theme}"><span class="tag theme-chip">${esc(item.label)}</span><h3>${esc(item.name)}</h3><p>${esc(item.headline)}</p><ul class="clean">${(item.board_topics || []).slice(0, 3).map((topic) => `<li>${esc(topic)}</li>`).join('')}</ul><div class="muted-box" style="margin-top:18px">자동발행 주제 ${esc(String((item.board_automation?.topics || []).length))}개 · CTA ${esc(item.board_automation?.cta_label || '제품 설명 보기')}</div><div class="actions"><a class="button secondary" href="${publicBoardHref('', item.key)}">같은 축 글 보기</a><a class="button ghost" href="${esc(item.board_automation?.cta_href || `${base}products/${item.key}/index.html#intro`)}">CTA 열기</a></div></article>`).join('');
  }

  function renderLiveStats(){
    const root = document.getElementById('live-stats'); if (!root) return;
    const publications = read(STORE.publications);
    const seed = publications.filter((item) => item.source === 'seed').length;
    const scheduled = publications.filter((item) => item.source === 'scheduled').length;
    root.innerHTML = `<article class="mini"><strong>${Object.keys(products).length}</strong><span>발행 축</span></article><article class="mini"><strong>${publications.length}</strong><span>전체 게시글</span></article><article class="mini"><strong>${seed}</strong><span>시드 글</span></article><article class="mini"><strong>${scheduled}</strong><span>예약 발행 글</span></article>`;
  }

  function renderPublicationDetail(targetId, items){
    const root = document.getElementById(targetId); if (!root) return;
    const params = new URLSearchParams(location.search);
    const postId = clean(params.get('post'));
    const item = items.find((entry) => entry.id === postId) || items[0];
    if (!item) { root.innerHTML = '<div class="empty-box">표시할 글이 없습니다.</div>'; return; }
    root.innerHTML = `<article class="post-detail"><span class="tag">${esc(item.productName || productName(item.product))}</span><h3>${esc(item.title)}</h3><p>${esc(item.summary)}</p><div class="kv"><div class="row"><strong>게시 시각</strong><span>${formatDate(item.createdAt)}</span></div><div class="row"><strong>발행 코드</strong><span>${esc(item.code || '기본 안내')}</span></div><div class="row"><strong>글 유형</strong><span>${esc(item.source || 'board')}</span></div><div class="row"><strong>본문</strong><span>${esc(item.body || item.summary).split('\n').join('<br>')}</span></div></div><div class="small-actions">${boardCtaMarkup(item)}<a href="${publicBoardHref(item.id, item.product)}">현재 글 링크</a><a href="${publicBoardHref('', item.product)}">같은 축 글 더 보기</a></div></article>`;
  }

  function renderPublicBoard(){
    const root = document.getElementById('public-board-grid'); if (!root) return;
    const selectedProduct = clean(new URLSearchParams(location.search).get('product'));
    let items = read(STORE.publications).slice().sort((a,b) => a.createdAt < b.createdAt ? 1 : -1);
    if (selectedProduct && products[selectedProduct]) items = items.filter((item) => item.product === selectedProduct);
    if (!items.length) {
      root.innerHTML = '<div class="empty-box">아직 공개된 글이 없습니다.</div>';
      const detail = document.getElementById('public-post-detail'); if (detail) detail.innerHTML = '';
      return;
    }
    root.innerHTML = items.slice(0, 12).map((item, idx) => `<article class="board-card"><span class="tag">추천 글 ${idx + 1}</span><h3>${esc(item.title)}</h3><p>${esc(item.summary)}</p><div class="small-actions">${boardCtaMarkup(item)}<a href="${publicBoardHref(item.id, selectedProduct || item.product)}">자세히 보기</a><a href="${publicBoardHref('', item.product)}">같은 축 보기</a></div></article>`).join('');
    renderPublicationDetail('public-post-detail', items);
  }

  function renderAdminSummary(){
    const root = document.getElementById('admin-summary');
    const publications = read(STORE.publications);
    const scheduler = read(STORE.scheduler);
    const seedCount = publications.filter((item) => item.source === 'seed').length;
    const scheduledCount = publications.filter((item) => item.source === 'scheduled').length;
    if (root) root.innerHTML = `<article class="admin-card"><span class="tag">전체 글</span><h3>${publications.length}</h3><p>저장된 게시판 글 수</p></article><article class="admin-card"><span class="tag">시드</span><h3>${seedCount}</h3><p>기본 시드 글 수</p></article><article class="admin-card"><span class="tag">예약 발행</span><h3>${scheduledCount}</h3><p>자동 생성된 글 수</p></article><article class="admin-card"><span class="tag">스케줄러</span><h3>${scheduler.length}</h3><p>제품별 발행 상태 수</p></article>`;
    const feed = document.getElementById('admin-feed');
    if (feed) feed.innerHTML = publications.length ? publications.slice().sort((a,b) => a.createdAt < b.createdAt ? 1 : -1).slice(0, 20).map((item) => `<div class="mock-step"><strong>${esc(item.title)}</strong><span>${formatDate(item.createdAt)}</span><span>${esc(item.productName || productName(item.product))} · ${esc(item.source || 'board')}</span></div>`).join('') : '<p class="feed-empty">아직 저장된 발행 로그가 없습니다.</p>';
    const pubRoot = document.getElementById('admin-publications');
    if (pubRoot) pubRoot.innerHTML = publications.length ? publications.slice(0,16).map((item) => `<article class="pub-admin-card"><span class="tag">${esc(item.productName || productName(item.product))}</span><h4>${esc(item.title)}</h4><p>${esc(item.summary)}</p><div class="small-actions">${boardCtaMarkup(item)}<a href="${publicBoardHref(item.id, item.product)}">글 보기</a></div></article>`).join('') : '<div class="empty-box">발행된 글이 없습니다.</div>';
  }

  function bindAdminTokenControls(){
    const input = document.getElementById('admin-token-input');
    const save = document.getElementById('admin-token-save');
    const clear = document.getElementById('admin-token-clear');
    if (input) input.value = getAdminToken();
    if (save) save.addEventListener('click', async () => {
      setAdminToken(input?.value || '');
      const ok = await syncRemoteState();
      showResult('admin-action-result', ok ? '관리자 토큰을 저장하고 상태를 다시 불러왔습니다.' : '관리자 토큰을 저장했습니다.');
      renderAdminSummary();
      renderPublicBoard();
      renderLiveStats();
    });
    if (clear) clear.addEventListener('click', () => {
      setAdminToken('');
      if (input) input.value = '';
      showResult('admin-action-result', '관리자 토큰을 지웠습니다.');
    });
  }

  async function postAdmin(path, payload){
    return fetchJson(path, { method:'POST', headers: headersFor(path, { 'Content-Type':'application/json', 'Accept':'application/json' }), body: JSON.stringify(payload || {}) });
  }

  function bindAdminActions(){
    const root = document.getElementById('admin-console'); if (!root) return;
    root.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-admin-action]'); if (!button) return;
      const action = button.dataset.adminAction;
      try {
        if (action === 'publish-now') {
          const payload = await postAdmin('/api/admin/actions/publish-now', {});
          applyStatePayload(payload.state);
          showResult('admin-action-result', '다음 CTA 포스팅을 즉시 발행했습니다.');
        } else if (action === 'reseed-board') {
          const payload = await postAdmin('/api/admin/actions/reseed-board', {});
          applyStatePayload(payload.state);
          showResult('admin-action-result', '게시판 시드를 다시 만들었습니다.');
        } else if (action === 'reset-all') {
          const payload = await postAdmin('/api/admin/actions/reset', {});
          applyStatePayload(payload.state);
          showResult('admin-action-result', '전체 상태를 초기화하고 기본 시드를 다시 만들었습니다.');
        }
      } catch (error) {
        showResult('admin-action-result', `${esc(error instanceof Error ? error.message : '관리자 작업 중 오류가 발생했습니다.')} 관리자 토큰을 확인하세요.`);
      }
      renderAdminSummary();
      renderPublicBoard();
      renderLiveStats();
    });
  }

  document.addEventListener('DOMContentLoaded', async () => {
    ensureSeedData();
    await loadBoardFeed();
    await syncRemoteState();
    renderHeader();
    renderFooter();
    renderProductGrid();
    renderLiveStats();
    renderPublicBoard();
    renderAdminSummary();
    bindAdminTokenControls();
    bindAdminActions();
  });

  window.NV0App = { read, write, ensureSeedData, renderAdminSummary, setAdminToken, getAdminToken, publicBoardHref };
})();
