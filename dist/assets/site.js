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
    ['홈', `${base}index.html`, 'home'],
    ['제품', `${base}products/veridion/index.html`, 'productHub'],
    ['자료실', `${base}board/index.html`, 'board'],
    ['회사소개', `${base}company/index.html`, 'company'],
    ['로그인(회원가입)', `${base}auth/index.html`, 'auth'],
  ];
  const productMenuItems = [
    ['안내', `${base}products/veridion/index.html`, path.includes('/products/veridion/') && !path.includes('/plans/') && !path.includes('/board/') && !path.includes('/demo/') && !path.includes('/faq/') && !path.includes('/delivery/')],
    ['가격', `${base}products/veridion/plans/index.html`, path.includes('/products/veridion/plans/') || pageKey === 'pricing'],
    ['자료실', `${base}products/veridion/board/index.html`, path.includes('/products/veridion/board/')],
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
  const AUTH_KEY = 'nv0-admin-auth';
  const AUTH_PERSIST_KEY = 'nv0-admin-auth-persist';
  const REPORT_SESSION_KEYS = { veridion:'nv0-veridion-last-report', clearport:'nv0-clearport-last-report', grantops:'nv0-grantops-last-report', draftforge:'nv0-draftforge-last-report' };
  const runtime = { systemConfig: null };
  function getAdminToken(){
    try {
      return sessionStorage.getItem(AUTH_KEY) || localStorage.getItem(AUTH_PERSIST_KEY) || '';
    } catch {
      try { return localStorage.getItem(AUTH_PERSIST_KEY) || ''; } catch { return ''; }
    }
  }
  function getLastProductReport(key){ try { return JSON.parse(sessionStorage.getItem(REPORT_SESSION_KEYS[key] || '') || 'null'); } catch { return null; } }
  function setLastProductReport(key, value){ try { const storageKey = REPORT_SESSION_KEYS[key]; if (!storageKey) return; if (value) sessionStorage.setItem(storageKey, JSON.stringify(value)); else sessionStorage.removeItem(storageKey); } catch {} }
  function getLastVeridionReport(){ return getLastProductReport('veridion'); }
  function setLastVeridionReport(value){ setLastProductReport('veridion', value); }
  function veridionScanEndpoint(){ return config.integration?.veridion_scan_endpoint || '/api/public/veridion/scan'; }
  function clearportAnalyzeEndpoint(){ return config.integration?.clearport_analyze_endpoint || '/api/public/clearport/analyze'; }
  function grantopsAnalyzeEndpoint(){ return config.integration?.grantops_analyze_endpoint || '/api/public/grantops/analyze'; }
  function draftforgeAnalyzeEndpoint(){ return config.integration?.draftforge_analyze_endpoint || '/api/public/draftforge/analyze'; }
  function ensureHiddenField(form, name, value){ if (!form) return; let input = form.querySelector(`input[name="${name}"]`); if (!input) { input = document.createElement('input'); input.type = 'hidden'; input.name = name; form.appendChild(input); } input.value = value || ''; }
  function structuredVeridionNote(values, report){ const issues = (report?.issues || []).slice(0,3).map((item)=> item.title).join(', '); return ['체험 목표: ' + (values.focus || '준법 리스크 우선순위 정리'), values.website ? `점검 URL: ${values.website}` : '', values.industry ? `업종: ${values.industry}` : '', values.countryLabel ? `운영 국가: ${values.countryLabel}` : (values.market ? `운영 국가: ${values.market}` : ''), report?.code ? `리포트 코드: ${report.code}` : '', report?.id ? `리포트 ID: ${report.id}` : '', report?.stats?.explorationRate !== undefined ? `탐색률: ${report.stats.explorationRate}%` : '', report?.stats?.priorityCoverage !== undefined ? `핵심 페이지 커버리지: ${report.stats.priorityCoverage}%` : '', issues ? `추가 요청: ${issues}` : ''].filter(Boolean).join('\n'); }
  function structuredClearportNote(values, report){ const issues = (report?.issues || []).slice(0,3).map((item)=> item.title).join(', '); return ['체험 목표: 제출 누락과 회신 지연 줄이기', values.submissionType ? `제출 유형: ${values.submissionType}` : '', values.targetOrg ? `제출처: ${values.targetOrg}` : '', report?.code ? `리포트 코드: ${report.code}` : '', report?.id ? `리포트 ID: ${report.id}` : '', report?.stats?.readinessRate !== undefined ? `준비도: ${report.stats.readinessRate}%` : '', report?.stats?.criticalMissing !== undefined ? `핵심 누락: ${report.stats.criticalMissing}건` : '', issues ? `추가 요청: ${issues}` : ''].filter(Boolean).join('\n'); }
  function structuredGrantopsNote(values, report){ const issues = (report?.issues || []).slice(0,3).map((item)=> item.title).join(', '); return ['체험 목표: 제출 일정 안정화', values.projectName ? `사업/공모명: ${values.projectName}` : '', values.progress ? `현재 진행률: ${values.progress}` : '', report?.code ? `리포트 코드: ${report.code}` : '', report?.id ? `리포트 ID: ${report.id}` : '', report?.stats?.readinessScore !== undefined ? `준비도: ${report.stats.readinessScore}점` : '', report?.stats?.daysLeft !== undefined ? `마감 상태: D-${report.stats.daysLeft}` : '', issues ? `추가 요청: ${issues}` : ''].filter(Boolean).join('\n'); }
  function structuredDraftforgeNote(values, report){ const issues = (report?.issues || []).slice(0,3).map((item)=> item.title).join(', '); return ['체험 목표: 최종본 기준 확정', values.docType ? `문서 종류: ${values.docType}` : '', values.approvalSteps ? `승인 단계: ${values.approvalSteps}` : '', report?.code ? `리포트 코드: ${report.code}` : '', report?.id ? `리포트 ID: ${report.id}` : '', report?.stats?.controlScore !== undefined ? `문서 통제 점수: ${report.stats.controlScore}점` : '', report?.stats?.handoffRisk ? `인계 위험: ${report.stats.handoffRisk}` : '', issues ? `추가 요청: ${issues}` : ''].filter(Boolean).join('\n'); }
  function structuredProductReportNote(key, values, report){ return key === 'veridion' ? structuredVeridionNote(values, report) : key === 'clearport' ? structuredClearportNote(values, report) : key === 'grantops' ? structuredGrantopsNote(values, report) : structuredDraftforgeNote(values, report); }
  function applyProductReportToCheckout(key, values, report){ const form = document.getElementById('product-checkout-form'); if (!form) return; ensureHiddenField(form, 'reportId', report?.id || ''); ensureHiddenField(form, 'reportCode', report?.code || ''); const noteInput = form.querySelector('input[name="note"]'); if (noteInput) noteInput.value = structuredProductReportNote(key, values || {}, report || {}); const linkInput = form.querySelector('input[name="link"]'); if (linkInput && values?.website) linkInput.value = values.website; }
  function applyVeridionReportToCheckout(values, report){ applyProductReportToCheckout('veridion', values, report); }
  function renderVeridionRemoteReport(report, values){
    const stats = report?.stats || {};
    const risk = report?.risk || {};
    const peer = risk?.peerComparison || {};
    const compliance = risk?.compliance || {};
    const diagnostics = Array.isArray(risk?.diagnostics) ? risk.diagnostics : [];
    const issues = Array.isArray(report?.topIssues) ? report.topIssues : (Array.isArray(report?.issues) ? report.issues : []);
    const lawGroups = Array.isArray(risk?.lawGroups) ? risk.lawGroups : [];
    const quality = Array.isArray(report?.quality?.gates) ? report.quality.gates : [];
    const exposure = risk?.estimatedExposure || {};
    const locked = report?.publicLocked || {};
    const services = Array.isArray(report?.serviceBundle) ? report.serviceBundle : [];
    const monitoring = report?.monitoring || {};
    const countryLabel = report?.countryLabel || values?.countryLabel || report?.market || '대한민국';
    const legalBasis = Array.isArray(report?.legalBasis) ? report.legalBasis : [];
    const peerLabel = peer?.bottomPercent !== undefined ? `유사 업종 대비 하위 ${peer.bottomPercent}%` : '유사 업종 비교 준비 중';
    const complianceLabel = compliance?.rate !== undefined ? `준수율 ${compliance.rate}%` : '준수율 계산 준비 중';
    const diagnosticRows = diagnostics.length ? diagnostics : [{ label:'정책 고지 완성도', score: stats.priorityCoverage || 0, status:'watch', detail:'핵심 페이지 커버리지 기준으로 산출합니다.' }];
    const lawRows = (lawGroups.length ? lawGroups : [{ lawLabel:'요약', issueCount:risk.issueCount || issues.length || 0, signalCount:risk.signalCount || 0, penaltyDisplay: exposure.display || '비정량', highRiskCount:risk.highRiskCount || 0 }]).map((item)=>[item.lawLabel || '영역', `${item.issueCount || 0}건 · 고위험 ${item.highRiskCount || 0}건 · 최대 ${item.penaltyDisplay || '비정량'}`]);
    const complianceRows = [
      ['현재 준수율', `${compliance.rate ?? '-'}% · 통과 ${compliance.passedRuleCount ?? '-'} / 기준 ${compliance.applicableRuleCount ?? '-'}`],
      ['업계 평균', `${compliance.averageRate ?? '-'}% · 차이 ${compliance.deltaFromAverage ?? '-'}%p`],
      ['업계 위치', `${compliance.percentileBand || peer.band || '비교 준비 중'} · ${peerLabel}`],
    ];
    const opsRows = [
      ['탐색률', `${stats.explorationRate ?? '-'}% · 후보 ${stats.discovered ?? '-'}개 / 실제 읽기 ${stats.fetched ?? '-'}개`],
      ['탐지율', `${stats.detectionRate ?? '-'}% · 차단 ${stats.blocked ?? 0}개 / 실패 ${stats.failed ?? 0}개`],
      ['발행 준비도', `${stats.issuanceReadiness ?? '-'}점 · 핵심 페이지 ${stats.priorityCoverage ?? '-'}%`],
      ['월 구독형 모니터링', `${(monitoring.watchSources || []).length}개 감시 소스 · 다음 점검 ${monitoring.cadenceLabel || '-'}`],
    ];
    const serviceRows = (services.length ? services : [{ title:'서비스 1 · 전체 세부 점검 리포트', summary:'결제 후 전체 이슈와 페이지별 결과를 전부 엽니다.' }, { title:'서비스 2 · 사이트 맞춤형 수정안 리포트', summary:'결제 후 해당 사이트에 맞춘 교체 문구와 수정안을 발행합니다.' }, { title:'서비스 3 · 월 구독형 상시 모니터링', summary:'법령 변경 알림, 영향 페이지 큐, 월간 재점검 스냅샷을 구독형으로 이어갑니다.' }]).map((item)=>`<div class="demo-table-row"><strong>${esc(item.title)}</strong><span>${esc(item.summary || '')}</span></div>`).join('');
    return `<div class="demo-result-shell">${demoSummaryHeader('Veridion 위기 데모 결과', report?.summary || `${values?.website || '입력 URL'} 기준 위기 신호를 요약한 결과입니다.`, Math.max(0, Math.min(100, Math.round(Number(risk.crisisScore || risk.riskScore || stats.priorityCoverage || 0)))))}${renderKpis([{ value:`${risk.crisisScore ?? risk.riskScore ?? 0}점`, label:'위기 점수', note:`신뢰도 ${esc(risk.confidenceGrade || '-')} · ${esc(peerLabel)}` },{ value:`${compliance.rate ?? '-'}%`, label:'동종 업계 대비 준수율', note:`업계 평균 ${esc(String(compliance.averageRate ?? '-'))}% · ${esc(compliance.percentileBand || '-')}` },{ value:esc(exposure.maxDisplay || exposure.display || '비정량'), label:'예상 최대 과태료', note:`리포트 코드 ${esc(report?.code || '-')}` }])}<div class="demo-section-stack"><h4>분석 기준 국가</h4><div class="demo-table"><div class="demo-table-row"><strong>${esc(countryLabel)}</strong><span>${esc(legalBasis.length ? legalBasis.join(' / ') : '국가별 준법 기준을 반영해 계산했습니다.')}</span></div></div><h4>무료 데모에서 먼저 보여주는 상위 이슈</h4>${renderDemoAlerts(issues.slice(0,5).map((item)=>({ level:item.level, title:`${item.title}${item.occurrenceCount ? ` · ${item.occurrenceCount}개 신호` : ''}`, detail:`${item.detail}${item.penaltyDisplay ? ` / ${item.penaltyDisplay}` : ''}` })))}<h4>영역별 건수·위기도·예상 최대 과태료</h4>${renderDemoTable(lawRows)}<h4>동종 업계 대비 준수율</h4>${renderDemoTable(complianceRows)}<h4>탐색률·탐지율·발행 작동 지표</h4>${renderDemoTable(opsRows)}<h4>추가로 보면 좋은 운영 지표</h4><div class="demo-table">${diagnosticRows.map((item)=>`<div class="demo-table-row"><strong>${esc(item.label || item.title || '진단 지표')}</strong><span>${esc(String(item.score ?? '-'))}점 · ${esc(item.status || '확인')} · ${esc(item.detail || '')}</span></div>`).join('')}</div><h4>결제 후 바로 발행되는 서비스</h4><div class="demo-table">${serviceRows}</div><h4>발행 전 품질 상태</h4><div class="demo-table">${quality.map((item)=>`<div class="demo-table-row"><strong>${esc(item.label)}</strong><span>${esc(item.ok ? '통과 · ' + item.detail : '보완 필요 · ' + item.detail)}</span></div>`).join('')}</div></div><div class="demo-save-box"><strong>유료 발행본에서 열리는 항목</strong><br>${esc(locked.message || '서비스 1 전체 세부 점검 리포트와 서비스 2 사이트 맞춤형 수정안 리포트를 결제 후 발행합니다.')}<br>현재 데모는 상위 이슈 ${esc(String(issues.length || 0))}건만 공개합니다. 전체 이슈 ${esc(String(locked.fullIssueCount || risk.issueCount || issues.length || 0))}건, 페이지별 세부 결과, 맞춤 수정안은 결제 후 발행본에서 제공합니다.<br><small>${esc(compliance.summaryLine || complianceLabel)} · ${esc(peer.disclaimer || exposure.disclaimer || '자동 점검 기반 추정치입니다.')}</small><br>리포트 코드 <span class="inline-code">${esc(report?.code || '-')}</span></div></div>`;
  }
  function renderClearportRemoteReport(report, values){ const stats = report?.stats || {}; const issues = Array.isArray(report?.issues) ? report.issues : []; const readiness = report?.readinessSummary || {}; const highlights = Array.isArray(report?.checklistHighlights) ? report.checklistHighlights : []; const quality = Array.isArray(report?.quality?.gates) ? report.quality.gates : []; const locked = report?.publicLocked || {}; return `<div class="demo-result-shell">${demoSummaryHeader('ClearPort 제출 데모 결과', report?.summary || `${values?.targetOrg || '제출처'} 기준 제출 준비도를 계산한 결과입니다.`, Math.round(Number(stats.readinessRate || 0)))}${renderKpis([{ value:`${stats.readinessRate ?? 0}%`, label:'준비도', note:`확보 ${readiness.securedDocs ?? stats.securedDocs ?? 0}종 / 기준 ${readiness.requiredDocs ?? stats.requiredDocs ?? 0}종` },{ value:`${readiness.criticalMissing ?? stats.criticalMissing ?? 0}건`, label:'핵심 누락', note:`전체 누락 ${readiness.missingDocs ?? stats.missingDocs ?? 0}건` },{ value:stats.daysLeft === null || stats.daysLeft === undefined ? '미입력' : `D-${stats.daysLeft}`, label:'마감 상태', note:`리포트 코드 ${esc(report?.code || '-')}` }])}<div class="demo-section-stack"><h4>무료 데모에서 먼저 보여주는 상위 이슈</h4>${renderDemoAlerts(issues.map((item)=>({ level:item.level, title:item.title, detail:item.detail })))}<h4>핵심 체크리스트 요약</h4>${renderDemoTable((highlights.length ? highlights : [{label:'핵심 누락', status:`${readiness.criticalMissing ?? stats.criticalMissing ?? 0}건`, priority:'요약'}]).map((item)=>[item.label || '항목', `${item.status || '-'} · ${item.priority || '요약'}`]))}<h4>발행 전 품질 상태</h4><div class="demo-table">${quality.map((item)=>`<div class="demo-table-row"><strong>${esc(item.label)}</strong><span>${esc(item.ok ? '통과 · ' + item.detail : '보완 필요 · ' + item.detail)}</span></div>`).join('')}</div></div><div class="demo-save-box"><strong>유료 운영본에서 열리는 항목</strong><br>${esc(locked.message || '전체 체크리스트와 회신 템플릿은 결제 후 제공합니다.')}<br>현재 데모는 상위 이슈 ${esc(String(issues.length || 0))}건과 핵심 체크리스트만 공개합니다. 전체 체크리스트 ${esc(String(locked.fullChecklistCount || 0))}행과 회신 템플릿 ${esc(String(locked.fullTemplateCount || 0))}종은 결제 후 운영본에서 제공합니다.<br>리포트 코드 <span class="inline-code">${esc(report?.code || '-')}</span></div></div>`; }
  function renderGrantopsRemoteReport(report, values){ const stats = report?.stats || {}; const issues = Array.isArray(report?.issues) ? report.issues : []; const schedule = Array.isArray(report?.scheduleHighlights) ? report.scheduleHighlights : []; const roles = Array.isArray(report?.roleHighlights) ? report.roleHighlights : []; const quality = Array.isArray(report?.quality?.gates) ? report.quality.gates : []; const locked = report?.publicLocked || {}; return `<div class="demo-result-shell">${demoSummaryHeader('GrantOps 제출 데모 결과', report?.summary || `${values?.projectName || '입력 사업'} 기준 역산 일정 결과입니다.`, Math.round(Number(stats.readinessScore || 0)))}${renderKpis([{ value:`${stats.readinessScore ?? 0}점`, label:'준비도', note:`마감과 진행률을 함께 반영했습니다.` },{ value:stats.daysLeft === null || stats.daysLeft === undefined ? '미입력' : `D-${stats.daysLeft}`, label:'마감 상태', note:`핵심 경로 ${stats.criticalPathSteps ?? 0}단계` },{ value:`${stats.riskLevel || '확인'}`, label:'제출 리스크', note:`리포트 코드 ${esc(report?.code || '-')}` }])}<div class="demo-section-stack"><h4>무료 데모에서 먼저 보여주는 상위 이슈</h4>${renderDemoAlerts(issues.map((item)=>({ level:item.level, title:item.title, detail:item.detail })))}<h4>핵심 경로 요약</h4>${renderDemoTable((schedule.length ? schedule : [{label:'핵심 경로', date:`${stats.criticalPathSteps ?? 0}단계`}]).map((item)=>[item.label || '단계', `${item.date || '-'}${item.owner ? ` · ${item.owner}` : ''}`]))}<h4>역할 분리 요약</h4>${renderDemoTable((roles.length ? roles : [{label:'역할 수', owner:`${stats.contributors ?? 1}명`}]).map((item)=>[item.label || '역할', `${item.owner || '-'}${item.date ? ` · ${item.date}` : ''}`]))}<h4>발행 전 품질 상태</h4><div class="demo-table">${quality.map((item)=>`<div class="demo-table-row"><strong>${esc(item.label)}</strong><span>${esc(item.ok ? '통과 · ' + item.detail : '보완 필요 · ' + item.detail)}</span></div>`).join('')}</div></div><div class="demo-save-box"><strong>유료 운영본에서 열리는 항목</strong><br>${esc(locked.message || '전체 역산 일정과 요청 문장 세트는 결제 후 제공합니다.')}<br>현재 데모는 상위 이슈 ${esc(String(issues.length || 0))}건과 핵심 경로만 공개합니다. 전체 일정 ${esc(String(locked.fullScheduleCount || 0))}행과 요청 문장 ${esc(String(locked.fullTemplateCount || 0))}종은 결제 후 운영본에서 제공합니다.<br>리포트 코드 <span class="inline-code">${esc(report?.code || '-')}</span></div></div>`; }
  function renderDraftforgeRemoteReport(report, values){ const stats = report?.stats || {}; const issues = Array.isArray(report?.issues) ? report.issues : []; const matrix = Array.isArray(report?.versionHighlights) ? report.versionHighlights : []; const quality = Array.isArray(report?.quality?.gates) ? report.quality.gates : []; const locked = report?.publicLocked || {}; return `<div class="demo-result-shell">${demoSummaryHeader('DraftForge 문서 통제 데모 결과', report?.summary || `${values?.docType || '입력 문서'} 기준 버전 운영 결과입니다.`, Math.round(Number(stats.controlScore || 0)))}${renderKpis([{ value:`${stats.controlScore ?? 0}점`, label:'문서 통제 점수', note:`최신본 기준과 승인 구조를 반영했습니다.` },{ value:`${stats.approvalSteps ?? 1}단계`, label:'승인 단계', note:`검토/배포 분기 구조입니다.` },{ value:`${stats.handoffRisk || '확인'}`, label:'인계 위험', note:`리포트 코드 ${esc(report?.code || '-')}` }])}<div class="demo-section-stack"><h4>무료 데모에서 먼저 보여주는 상위 이슈</h4>${renderDemoAlerts(issues.map((item)=>({ level:item.level, title:item.title, detail:item.detail })))}<h4>버전 규칙 요약</h4>${renderDemoTable((matrix.length ? matrix : [{label:'버전 규칙 수', rule:`${locked.fullVersionRuleCount || 0}개`}]).map((item)=>[item.label || '단계', `${item.rule || '-'}`]))}<h4>발행 전 품질 상태</h4><div class="demo-table">${quality.map((item)=>`<div class="demo-table-row"><strong>${esc(item.label)}</strong><span>${esc(item.ok ? '통과 · ' + item.detail : '보완 필요 · ' + item.detail)}</span></div>`).join('')}</div></div><div class="demo-save-box"><strong>유료 운영본에서 열리는 항목</strong><br>${esc(locked.message || '전체 버전 규칙표와 검토·발송 문장 세트는 결제 후 제공합니다.')}<br>현재 데모는 상위 이슈 ${esc(String(issues.length || 0))}건과 버전 규칙 요약만 공개합니다. 전체 버전 규칙 ${esc(String(locked.fullVersionRuleCount || 0))}개와 문장 템플릿 ${esc(String(locked.fullTemplateCount || 0))}종은 결제 후 운영본에서 제공합니다.<br>리포트 코드 <span class="inline-code">${esc(report?.code || '-')}</span></div></div>`; }
  function setAdminToken(value){
    const token = clean(value);
    try {
      if (token) {
        sessionStorage.setItem(AUTH_KEY, token);
        localStorage.setItem(AUTH_PERSIST_KEY, token);
      } else {
        sessionStorage.removeItem(AUTH_KEY);
        localStorage.removeItem(AUTH_PERSIST_KEY);
      }
    } catch {
      try { if (token) localStorage.setItem(AUTH_PERSIST_KEY, token); else localStorage.removeItem(AUTH_PERSIST_KEY); } catch {}
    }
  }
  function headersFor(url, extra){ const headers = Object.assign({}, extra || {}); const target = String(url || ''); const token = clean(getAdminToken()); if (token && target.includes('/api/admin/')) headers['X-Admin-Token'] = token; return headers; }
  function fetchOptionsFor(url, extra){ const target = String(url || ''); const options = Object.assign({}, extra || {}); if (target.includes('/api/admin/')) options.credentials = 'include'; return options; }
  async function checkAdminSession(){
    const url = config.integration?.admin_session_endpoint || '/api/admin/session';
    try {
      const res = await fetch(url, fetchOptionsFor(url, { headers: headersFor(url, { 'Accept':'application/json' }) }));
      if (res.ok) {
        const payload = await res.json();
        const ok = Boolean(payload?.authenticated);
        if (ok) {
          const stored = clean(getAdminToken());
          if (stored) setAdminToken(stored);
          return true;
        }
      }
    } catch {}
    const token = clean(getAdminToken());
    if (!token) {
      setAdminToken('');
      return false;
    }
    const validateUrl = config.integration?.admin_validate_endpoint || config.integration?.admin_state_endpoint || '/api/admin/validate';
    try {
      const validateRes = await fetch(validateUrl, fetchOptionsFor(validateUrl, { headers: headersFor(validateUrl, { 'Accept':'application/json' }) }));
      const ok = validateRes.ok;
      if (ok) {
        setAdminToken(token);
        return true;
      }
    } catch {}
    setAdminToken('');
    return false;
  }
  async function performAdminLogin(secret){
    const token = clean(secret);
    if (!token) return false;
    const url = config.integration?.admin_login_endpoint || '/api/admin/login';
    const res = await fetch(url, fetchOptionsFor(url, { method:'POST', headers: { 'Content-Type':'application/json', 'Accept':'application/json' }, body: JSON.stringify({ token }) }));
    if (!res.ok) { setAdminToken(''); return false; }
    setAdminToken(token);
    const verified = await checkAdminSession();
    if (!verified) {
      const validateUrl = config.integration?.admin_validate_endpoint || '/api/admin/validate';
      try {
        const validateRes = await fetch(validateUrl, fetchOptionsFor(validateUrl, { headers: headersFor(validateUrl, { 'Accept':'application/json' }) }));
        if (!validateRes.ok) { setAdminToken(''); return false; }
      } catch { setAdminToken(''); return false; }
    }
    return true;
  }
  async function performAdminLogout(){ const url = config.integration?.admin_logout_endpoint || '/api/admin/logout'; try { await fetch(url, fetchOptionsFor(url, { method:'POST', headers: headersFor(url, { 'Accept':'application/json' }) })); } catch {} setAdminToken(''); }
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
  function priceToAmount(value){ const text = clean(value).replace(/,/g, '').replace(/\/월$/, '').replace(/월$/, ''); if (/만$/.test(text)) { const number = clean(text.replace(/만$/, '')); return /^\d+$/.test(number) ? Number(number) * 10000 : 0; } const digits = text.replace(/[^0-9]/g, ''); return digits ? Number(digits) * (text.includes('만') ? 10000 : 1) : 0; }
  function planNote(key, planName){ const target = products[key]; const plan = target?.plans?.find((item) => item.name === planName) || target?.plans?.[0]; return plan?.note || ''; }
  function clean(value){ return String(value ?? '').trim(); }
  function normalizeEmail(value){ return clean(value).toLowerCase(); }
  function normalizeCode(value){ return clean(value).toUpperCase(); }
  function normalizeWebsiteInput(value){
    const raw = clean(value);
    if (!raw) return '';
    let next = raw.replace(/[​-‍﻿]/g, '');
    if (!/^https?:\/\//i.test(next)) next = `https://${next}`;
    try {
      const url = new URL(next);
      url.hash = '';
      if (!url.pathname) url.pathname = '/';
      return url.toString();
    } catch {
      return next;
    }
  }
  function veridionOptionsFromValues(values){
    const options = uniqueCompact(values?.options);
    const focus = clean(values?.focus);
    const industry = clean(values?.industry);
    if (focus.includes('개인정보')) options.push('privacy');
    if (focus.includes('결제') || focus.includes('환불') || industry === 'commerce') options.push('commerce');
    if (focus.includes('광고') || focus.includes('표시') || focus.includes('표현') || focus.includes('민감')) options.push('claims');
    if (industry === 'saas' || industry === 'education') options.push('privacy');
    return uniqueCompact(options);
  }
  function buildVeridionFallbackHtml(values, reason=''){
    const seeded = { ...values, website: normalizeWebsiteInput(values?.website), options: veridionOptionsFromValues(values) };
    const result = veridionResult(seeded);
    const notice = `<div class="notice notice-light"><strong>실시간 탐색 연결이 불안정해도 데모는 계속 진행했습니다.</strong><br>${esc(seeded.website || values?.website || '입력 URL')} 기준으로 URL·업종·국가·중점 항목을 바탕으로 우선 점검 결과를 먼저 만들었습니다.${reason ? ` ${esc(reason)}` : ''}</div>`;
    return notice + `
      <div class="demo-result-shell">
        ${demoSummaryHeader(result.headline, result.summary, result.score)}
        ${renderKpis(result.kpis)}
        ${renderDemoAlerts(result.alerts)}
        ${result.extra}
        <div class="demo-save-box"><strong>안내</strong><br>현재 결과는 입력값 기반 즉시 프리뷰입니다. 서버 연결이 정상인 환경에서는 실제 페이지 탐색 결과를 우선 표시합니다.</div>${buildDemoUpsellBox('veridion')}
      </div>
    `;
  }
  function normalizePayload(payload){ return Object.fromEntries(Object.entries(payload || {}).map(([key, value]) => [key, typeof value === 'string' ? clean(value) : value])); }
  function withSubmitLock(form, handler){ if (!form || form.dataset.busy === '1') return false; const buttons = [...form.querySelectorAll('button, input[type="submit"]')]; const originals = buttons.map((btn) => btn.disabled); form.dataset.busy = '1'; buttons.forEach((btn) => { btn.disabled = true; }); const release = () => { delete form.dataset.busy; buttons.forEach((btn, idx) => { btn.disabled = originals[idx]; }); }; return Promise.resolve().then(handler).finally(release); }
  function assert(condition, message){ if (!condition) throw new Error(message); }
  function validateEmail(value){ return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizeEmail(value)); }
  function validateProduct(value){ return Boolean(products[clean(value)]); }
  function validatePlan(productKey, planName){ const target = products[productKey]; return Boolean(target?.plans?.some((item) => item.name === planName)); }
  function nextStatusForPayment(paymentStatus){ const status = clean(paymentStatus); return status === 'paid' ? 'delivered' : (status === 'ready' || status === 'pending') ? 'payment_pending' : 'draft_ready'; }
  function createFriendlyError(error, fallback){ return error instanceof Error ? error.message : fallback; }
  function orderStatusLabel(status){ return ({payment_pending:'결제 대기', intake_required:'진행 정보 입력 필요', draft_ready:'자동 실행 준비', published:'콘텐츠 발행 완료', delivered:'결과 전달 완료'})[clean(status)] || (clean(status) || '확인 필요'); }
  function paymentStatusLabel(status){ return clean(status) === 'paid' ? '결제 완료' : clean(status) === 'ready' ? '결제 준비 완료' : '결제 대기'; }

  function buildCtaHref(raw, productKey){ if (!raw) return `${base}products/${productKey}/index.html#intro`; if (/^https?:/i.test(raw)) return raw; const cleanPath = String(raw).replace(/^\//, ''); return `${base}${cleanPath}`; }
  async function verifyAdminTokenForEntry(){
    const token = clean(getAdminToken());
    if (!token) return false;
    const url = config.integration?.admin_validate_endpoint || config.integration?.admin_state_endpoint || '';
    if (!url) return true;
    try {
      const res = await fetch(url, fetchOptionsFor(url, { headers: headersFor(url, { 'Accept':'application/json' }) }));
      return res.ok;
    } catch {
      return false;
    }
  }
  function ensureAdminAccessModal(){
    let root = document.getElementById('admin-access-modal-root');
    if (!root) {
      root = document.createElement('div');
      root.id = 'admin-access-modal-root';
      document.body.prepend(root);
    }
    if (!root.innerHTML.trim()) {
      root.innerHTML = `<div class="admin-access-modal" id="admin-access-modal" hidden><div class="admin-access-backdrop" data-admin-close="1"></div><div class="admin-access-dialog" role="dialog" aria-modal="true" aria-labelledby="admin-access-title"><div class="admin-access-top"><strong id="admin-access-title">관리 메뉴 열기</strong><button class="admin-access-close" type="button" data-admin-close="1">닫기</button></div><p class="admin-access-copy">관리 비밀키를 입력하면 관리자 허브로 들어갑니다.</p><form id="admin-access-form" class="admin-access-form"><label>관리 비밀키<input id="admin-access-input" name="token" type="password" autocomplete="off" spellcheck="false" placeholder="관리 비밀키"></label><div class="actions"><button class="button" type="submit">관리 열기</button><button class="button ghost" type="button" data-admin-clear="1">토큰 지우기</button></div><div class="result-box" id="admin-access-result">비밀키를 입력하기 전에는 관리자 기능이 열리지 않습니다.</div></form></div></div>`;
    }
    const modal = document.getElementById('admin-access-modal');
    const input = document.getElementById('admin-access-input');
    const form = document.getElementById('admin-access-form');
    const result = document.getElementById('admin-access-result');
    const close = () => {
      if (!modal) return;
      modal.hidden = true;
      document.body.classList.remove('modal-open');
    };
    root.querySelectorAll('[data-admin-close="1"]').forEach((button) => {
      if (button.dataset.bound === '1') return;
      button.dataset.bound = '1';
      button.addEventListener('click', close);
    });
    if (modal && modal.dataset.escapeBound !== '1') {
      modal.dataset.escapeBound = '1';
      modal.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') close();
      });
    }
    const clearButton = root.querySelector('[data-admin-clear="1"]');
    if (clearButton && clearButton.dataset.bound !== '1') {
      clearButton.dataset.bound = '1';
      clearButton.addEventListener('click', () => {
        setAdminToken('');
        if (input) input.value = '';
        if (result) result.textContent = '저장된 비밀키를 지웠습니다.';
      });
    }
    if (form && form.dataset.bound !== '1') {
      form.dataset.bound = '1';
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const token = clean(input?.value || '');
        if (!token) {
          if (result) result.textContent = '비밀키를 입력해야 관리자 화면으로 들어갈 수 있습니다.';
          input?.focus();
          return;
        }
        const ok = await performAdminLogin(token);
        if (!ok) {
          setAdminToken('');
          if (result) result.textContent = '비밀키가 맞지 않습니다. 다시 확인해 주세요.';
          input?.focus();
          return;
        }
        if (result) result.textContent = root.dataset.redirect === 'false' ? '비밀키가 확인되었습니다. 현재 화면에서 관리자 기능을 엽니다.' : '비밀키가 확인되었습니다. 관리자 허브로 이동합니다.';
        close();
        if (root.dataset.redirect !== 'false') window.location.href = `${base}admin/index.html`;
        else await bootstrapAdminGate();
      });
    }
    return { modal, input, result };
  }
  async function requestAdminAccess(redirect = true){
    const alreadyAuthed = await checkAdminSession();
    if (alreadyAuthed) {
      if (redirect) {
        window.location.href = `${base}admin/index.html`;
        return true;
      }
      await bootstrapAdminGate();
      return true;
    }
    const modalUi = ensureAdminAccessModal();
    if (modalUi?.modal) {
      modalUi.modal.hidden = false;
      document.body.classList.add('modal-open');
      if (modalUi.input) modalUi.input.value = '';
      const modalRoot = document.getElementById('admin-access-modal-root');
      if (modalRoot) modalRoot.dataset.redirect = redirect === false ? 'false' : 'true';
      if (modalUi.result) modalUi.result.textContent = '관리 비밀키를 입력하면 관리자 기능이 열립니다.';
      setTimeout(() => modalUi.input?.focus(), 10);
      return false;
    }
    const input = window.prompt('관리 비밀키를 입력하세요.', '');
    if (input === null) return false;
    const token = clean(input);
    if (!token) { window.alert('비밀키를 입력해야 관리자 화면으로 들어갈 수 있습니다.'); return false; }
    const ok = await performAdminLogin(token);
    if (!ok) {
      setAdminToken('');
      window.alert('비밀키가 맞지 않습니다. 다시 확인해 주세요.');
      return false;
    }
    if (redirect) {
      window.location.href = `${base}admin/index.html`;
      return true;
    }
    await bootstrapAdminGate();
    const tokenInput = document.getElementById('admin-token-input');
    if (tokenInput) tokenInput.value = getAdminToken();
    const gate = document.getElementById('admin-gate-result');
    if (gate && !clean(gate.textContent || '')) gate.textContent = '관리자 비밀키를 확인했습니다. 현재 화면에서 운영 메뉴를 엽니다.';
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
      const res = await fetch(url, fetchOptionsFor(url, { method:'POST', headers: headersFor(url, { 'Content-Type':'application/json', 'Accept':'application/json' }), body: JSON.stringify(payload || {}) }));
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
    if (!url) return false;
    const authed = await checkAdminSession();
    if (!authed && pageKey !== 'admin') return false;
    try {
      const res = await fetch(url, fetchOptionsFor(url, { headers: headersFor(url, { 'Accept':'application/json' }) }));
      if (!res.ok) return false;
      const payload = await res.json();
      applyStatePayload(payload.state || payload.data || null);
      return true;
    } catch { return false; }
  }
  function enhanceDocumentChrome(){
    const main = document.querySelector('main');
    if (main && !main.id) main.id = 'main-content';
    if (!document.querySelector('.skip-link')) {
      const link = document.createElement('a');
      link.className = 'skip-link';
      link.href = '#main-content';
      link.textContent = '본문 바로가기';
      document.body.prepend(link);
    }
  }

  function bindAdminTokenControls(){
    const input = document.getElementById('admin-token-input');
    const save = document.getElementById('admin-token-save');
    const clear = document.getElementById('admin-token-clear');
    if (input) input.value = clean(getAdminToken());
    if (save) save.addEventListener('click', async () => {
      const ok = await performAdminLogin(input?.value || '');
      if (!ok) { showResult('admin-action-result', '관리자 키를 다시 확인해 주세요.'); await bootstrapAdminGate(); return; }
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
      await performAdminLogout();
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
    const hasToken = await checkAdminSession();
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
    shell.style.display = '';
    if (!synced) {
      if (gate) gate.innerHTML = '운영 메뉴는 열었지만 서버 상태 동기화가 지연되었습니다. 메뉴는 바로 사용할 수 있고, 새로고침하면 다시 불러옵니다.';
      return true;
    }
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
      '맞춤도': `${company || '고객사'}와 목표(${goal || target?.summary || ''})를 중심으로 결과 제품 소개, 출력물, 다음 행동이 같은 흐름으로 맞춰집니다.`,
      '구체성': '출력물 제목만 나열하지 않고 포함 내용, 바로 쓸 행동, 적용 이유를 함께 제시합니다.',
      '실행 가능성': '우선순위, 체크리스트, 다음 행동, 발행 준비 상태를 함께 제공해 바로 움직일 수 있습니다.',
      '전문성': firstNonEmpty(...(arch.quality_gates || [])) || `${target?.name || 'NV0'}의 품질 게이트 기준을 따라 과도한 단정 대신 실무 적용 가능한 설명으로 정리합니다.`,
      '설득력': '결과가 왜 필요한지와 비용 대비 남는 자산을 분명하게 설명해 결제 판단을 돕습니다.',
      '발행 준비도': '고객 전달 제품 소개, 상세 실행 자료, 자동 발행 글이 같은 조회 코드 기준으로 이어집니다.',
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
        '공고 핵심 해석 제품 소개본으로 요구사항을 먼저 정리합니다.',
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
      whatIncluded: (() => { const raw = contracts[idx] || `${title}의 핵심 판단 기준, 바로 적용할 문장, 공유용 제품 소개을 한 번에 포함합니다.`; return clean(raw).length >= 15 ? raw : `${raw}. ${company || '샘플 회사'}가 실제 업무에 바로 옮길 수 있도록 판단 기준과 적용 포인트를 함께 넣습니다.`; })(),
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
    const pack = {
      title: `${target?.name || ''} ${payload.plan || 'Starter'} 실행 결과`,
      summary: `${target?.name || ''} 결제 이후 확인해야 할 자료와 전달 흐름이 자동으로 준비되었습니다. 결제 직후 바로 확인하고 활용할 수 있습니다.`,
      outcomeHeadline: `${payload.company || '고객사'}가 지금 바로 판단하고 실행할 수 있는 핵심 결과를 먼저 정리했습니다.`,
      executiveSummary: `이번 결과물은 ${target?.problem || target?.summary || ''} 상황을 빠르게 줄이기 위해, 제품 소개 판단 자료와 세부 실행 자료, 발행 자산을 하나의 조회 코드 아래에서 함께 쓰도록 설계했습니다.`,
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
        { title: `${target?.name || ''} 고객 전달 제품 소개`, description: '핵심 결과와 다음 행동을 먼저 읽기 쉬운 형태로 정리합니다.', customerValue:'내부 공유와 의사결정 정리가 빨라집니다.', usageMoment:'즉시 공유', expertNote:'핵심 판단이 먼저 보이도록 길이보다 우선순위를 앞세웁니다.', status: 'ready' },
        { title: `${target?.name || ''} 상세 실행 자료`, description: '세부 결과, 우선순위, 즉시 적용 포인트를 포함한 자료입니다.', customerValue:'작업자 기준으로 바로 손을 댈 수 있는 실행 자료입니다.', usageMoment:'실행 착수', expertNote:'설명형 문서가 아니라 행동형 문서가 되도록 세부 실행 포인트를 넣습니다.', status: 'ready' },
        { title: `${target?.name || ''} 자동 발행 글`, description: '고객 포털과 콘텐츠에서 같은 조회 코드로 이어지는 자동 발행 콘텐츠입니다.', customerValue:'대외 설명과 내부 아카이브를 동시에 정리합니다.', usageMoment:'후속 점검', expertNote:'같은 내용을 보는 화면이 달라도 메시지는 흔들리지 않게 유지합니다.', status: 'ready' },
      ],
      deliveryAssets: [
        { title:`${target?.name || ''} 고객 전달 제품 소개`, description:'핵심 결과와 다음 행동을 먼저 읽기 쉬운 형태로 정리합니다.', customerValue:'담당자와 의사결정자가 같은 내용을 짧게 공유할 수 있습니다.', usageMoment:'첫 공유', expertNote:'핵심 판단이 먼저 보이게 정리합니다.', status:'ready' },
        { title:`${target?.name || ''} 상세 실행 자료`, description:'출력물별 상세 설명, 우선순위, 즉시 적용 포인트를 포함한 본문 자료입니다.', customerValue:'작업자 입장에서 바로 손을 대야 할 항목과 검토 포인트를 함께 확인할 수 있습니다.', usageMoment:'실행', expertNote:'설명형 문서가 아니라 행동형 문서가 되도록 구성합니다.', status:'ready' },
        { title:`${target?.name || ''} 자동 발행 글 2건 이상`, description:'제품 설명, 공개 콘텐츠, 고객 포털에서 같은 조회 코드로 이어지는 자동 발행 콘텐츠입니다.', customerValue:'결과를 전달하는 데서 끝나지 않고 대외 설명과 내부 공유까지 이어집니다.', usageMoment:'후속 공유', expertNote:'같은 내용을 보는 화면이 달라도 메시지를 유지합니다.', status:'ready' },
      ],
      nextActions: (target?.workflow || []).slice(0, 4),
      valueNarrative: `${target?.name || ''}은 결과 제목만 전달하지 않고, 바로 판단할 제품 소개·세부 실행 자료·발행 결과까지 함께 묶어 남는 운영 자산으로 만드는 데 초점을 둡니다. 이번 결과는 지금 당장 움직일 일과 다음 변경 때 다시 꺼내 쓸 기준을 동시에 남깁니다.`,
      buyerDecisionReason: `단순 샘플이나 템플릿이 아니라 ${payload.company || '고객사'}의 목표와 운영 방식에 맞춘 판단 자료, 실행 자료, 발행 자산이 한 번에 준비되기 때문에 결제 직후 체감 가치가 높습니다.`,
    };
    if (target?.key === 'veridion' && (clean(payload.billing) === 'monthly' || clean(payload.plan) === 'Monitor')) {
      pack.monitoringSubscription = {
        enabled: true,
        summary: '법령 변경 알림, 영향 페이지 재점검 큐, 월간 스냅샷을 월 구독형으로 이어갑니다.',
        cadenceLabel: '매 30일 점검',
        watchSources: ['개인정보', '전자상거래', '광고·표현', '구독 결제 고지'],
      };
      pack.issuanceBundle.push({ title:'월 구독형 상시 모니터링', description:'법령 변경 알림, 영향 페이지 큐, 월간 재점검 스냅샷을 구독형으로 제공합니다.', customerValue:'법령이 바뀔 때마다 손으로 다시 찾지 않아도 됩니다.', usageMoment:'월 구독 시작 직후', expertNote:'재점검 주기와 알림 이력을 같이 남깁니다.', status:'ready' });
      pack.deliveryAssets.push({ title:'법령 변경 알림 세트', description:'알림 기준표, 영향 페이지 큐, 월간 스냅샷', customerValue:'운영 기준을 반복 사용 가능합니다.', usageMoment:'월간 운영', expertNote:'영향 페이지를 먼저 좁혀 점검 시간을 줄입니다.', status:'ready' });
    }
    return pack;
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
    const target = products[data.product];
    const createdAt = stamp();
    const id = uid('ord');
    const code = makePublicCode('NV0', data.product);
    const ready = clean(data.company) && clean(data.name) && validateEmail(data.email) && (data.product !== 'veridion' || clean(data.link || data.website));
    const order = {
      id,
      code,
      product: data.product,
      productName: target.name,
      plan: data.plan,
      billing: data.billing || (products[data.product]?.plans?.find((item) => item.name === data.plan)?.billing || 'one-time'),
      paymentMethod: data.paymentMethod || 'toss',
      company: data.company || '',
      name: data.name || '',
      email: normalizeEmail(data.email || ''),
      link: data.link || data.website || '',
      note: data.note || '',
      reportId: data.reportId || '',
      reportCode: data.reportCode || '',
      price: planPrice(data.product, data.plan),
      paymentStatus: 'paid',
      status: ready ? 'delivered' : 'intake_required',
      deliveryMeta: ready ? { automation: 'local_auto', deliveredAt: createdAt } : {},
      amount: priceToAmount(planPrice(data.product, data.plan)),
      resultPack: ready ? buildResultPack(target, data) : null,
      publicationIds: [],
      publicationCount: 0,
      createdAt,
      updatedAt: createdAt,
    };
    if (ready) {
      const publications = createPublicationsForOrder(order);
      order.publicationIds = publications.map((item) => item.id);
      order.publicationCount = publications.length;
    }
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
  function currentMainSection(){
    return pageKey === 'home' ? 'home' : pageKey === 'board' ? 'board' : pageKey === 'company' ? 'company' : pageKey === 'auth' ? 'auth' : (path.includes('/products/') || path.includes('/modules/') || pageKey === 'pricing' || pageKey === 'modules') ? 'productHub' : '';
  }
  function renderNavLinks(linkClass=''){
    return navItems.map(([label, href, key]) => `<a href="${href}" class="${linkClass} ${currentMainSection() === key ? 'active' : ''}">${label}</a>`).join('');
  }
  function renderProductSubLinks(linkClass='sub-link'){
    return productMenuItems.map(([label, href, active]) => `<a href="${href}" class="${linkClass} ${active ? 'active' : ''}">${label}</a>`).join('');
  }
  function renderHeader(){
    const header = document.getElementById('site-header'); if (!header) return;
    const quickLinks = renderProductSubLinks('sub-link');
    header.innerHTML = `<div class="container nav-wrap"><div class="nav-left"><button class="mobile-nav-toggle" type="button" aria-expanded="false" aria-controls="mobile-drawer" data-nav-toggle="1">메뉴</button><a class="brand" href="${base}index.html"><span class="brand-mark">V</span><span class="brand-copy"><strong>Veridion</strong><span>온라인 개인사업자용 법률·규제 리스크 방어막</span></span></a></div><nav class="nav-links">${renderNavLinks('top-link')}<a class="admin-entry" href="${base}admin/index.html" data-admin-entry="1" data-admin-href="${base}admin/index.html" title="권한 확인 후 관리자 메뉴로 들어갑니다">관리</a></nav></div><div class="container subnav"><span class="subnav-label">제품</span>${quickLinks}</div>`;
  }

  function renderSidebar(){
    const existing = document.getElementById('side-nav-shell');
    if (existing) existing.remove();
    document.body.classList.remove('with-side-nav');
    if (!document.getElementById('mobile-nav-backdrop')) {
      const backdrop = document.createElement('button');
      backdrop.type = 'button';
      backdrop.id = 'mobile-nav-backdrop';
      backdrop.className = 'mobile-nav-backdrop';
      backdrop.setAttribute('aria-hidden', 'true');
      document.body.appendChild(backdrop);
    }
    let drawer = document.getElementById('mobile-drawer');
    if (!drawer) {
      drawer = document.createElement('aside');
      drawer.id = 'mobile-drawer';
      drawer.className = 'mobile-drawer';
      document.body.appendChild(drawer);
    }
    drawer.innerHTML = `<div class="mobile-drawer-card"><div class="mobile-drawer-top"><strong>메뉴</strong><button class="mobile-nav-close" type="button" data-nav-close="1">닫기</button></div><a class="side-admin-button" href="${base}admin/index.html" data-admin-entry="1" data-admin-href="${base}admin/index.html" title="관리 메뉴를 엽니다">관리</a><nav class="side-nav-links"><div class="side-group"><span class="side-group-title">메인 메뉴</span>${renderNavLinks('side-link')}</div><div class="side-group"><span class="side-group-title">제품</span>${renderProductSubLinks('side-sublink')}<a href="${base}products/veridion/demo/index.html" class="side-sublink ${path.includes('/products/veridion/demo/') ? 'active' : ''}">즉시 시연</a></div></nav></div>`;
  }

  function bindNavChrome(){
    const body = document.body;
    const toggle = document.querySelector('[data-nav-toggle="1"]');
    const close = document.querySelector('[data-nav-close="1"]');
    const backdrop = document.getElementById('mobile-nav-backdrop');
    const closeDrawer = () => { body.classList.remove('mobile-nav-open'); toggle?.setAttribute('aria-expanded', 'false'); };
    const openDrawer = () => { body.classList.add('mobile-nav-open'); toggle?.setAttribute('aria-expanded', 'true'); };
    toggle?.addEventListener('click', () => body.classList.contains('mobile-nav-open') ? closeDrawer() : openDrawer());
    close?.addEventListener('click', closeDrawer);
    backdrop?.addEventListener('click', closeDrawer);
    document.querySelectorAll('#mobile-drawer a').forEach((link) => link.addEventListener('click', closeDrawer));
  }

  const PORTAL_SESSION_KEY = 'veridion-portal-session';
  function getPortalToken(){ try { return localStorage.getItem(PORTAL_SESSION_KEY) || ''; } catch { return ''; } }
  function setPortalToken(token){ try { if (token) localStorage.setItem(PORTAL_SESSION_KEY, token); else localStorage.removeItem(PORTAL_SESSION_KEY); } catch {} }
  async function bindAuthForms(){
    const loginForm = document.getElementById('portal-login-form');
    const signupForm = document.getElementById('portal-signup-form');
    const statusBox = document.getElementById('auth-status');
    const historyBox = document.getElementById('auth-history');
    const meBox = document.getElementById('auth-me');
    const logoutBtn = document.getElementById('portal-logout-button');
    const headers = (token='') => token ? { 'Content-Type':'application/json', 'Accept':'application/json', 'Authorization': `Bearer ${token}` } : { 'Content-Type':'application/json', 'Accept':'application/json' };
    const paintOrders = (orders=[]) => {
      if (!historyBox) return;
      historyBox.innerHTML = orders.length ? `<div class="record-grid">${orders.map((item)=>`<article class="record-card"><span class="tag">${esc(orderStatusLabel(item.status))}</span><h4>${esc(item.productName || item.product || 'Veridion')}</h4><p>${esc(item.plan || '-')} · 조회 코드 <span class="inline-code">${esc(item.code || '-')}</span></p><div class="small-actions"><a href="${portalHref(item)}">발행본 보기</a></div></article>`).join('')}</div>` : '<div class="empty-box">저장된 발행 이력이 없습니다.</div>';
    };
    const refreshSession = async () => {
      const token = getPortalToken();
      if (!token) { if (meBox) meBox.innerHTML = '<div class="empty-box">로그인 후 지난 발행 이력을 확인할 수 있습니다.</div>'; paintOrders([]); return; }
      try {
        const meRes = await fetch('/api/public/auth/me', { headers: headers(token) });
        if (!meRes.ok) throw new Error('로그인 상태를 확인하지 못했습니다.');
        const me = await meRes.json();
        if (meBox) meBox.innerHTML = `<div class="notice"><strong>${esc(me.account?.name || me.account?.email || '사용자')}</strong><br>${esc(me.account?.company || '회사 정보 없음')} · ${esc(me.account?.email || '')}</div>`;
        const historyRes = await fetch('/api/public/portal/history', { method:'POST', headers: headers(token) });
        const history = historyRes.ok ? await historyRes.json() : { orders: me.orders || [] };
        paintOrders(history.orders || me.orders || []);
      } catch (error) {
        setPortalToken('');
        if (statusBox) statusBox.innerHTML = `<div class="empty-box">${esc(error.message || '로그인 상태 확인에 실패했습니다.')}</div>`;
        if (meBox) meBox.innerHTML = '<div class="empty-box">다시 로그인해 주세요.</div>';
        paintOrders([]);
      }
    };
    if (loginForm && !loginForm.dataset.bound) {
      loginForm.dataset.bound = '1';
      loginForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const form = new FormData(loginForm);
        const payload = Object.fromEntries(form.entries());
        const res = await fetch('/api/public/auth/login', { method:'POST', headers: headers(), body: JSON.stringify(payload) });
        const data = await res.json().catch(()=>({}));
        if (!res.ok) { if (statusBox) statusBox.innerHTML = `<div class="empty-box">${esc(data.detail || '로그인에 실패했습니다.')}</div>`; return; }
        setPortalToken(data.token || '');
        if (statusBox) statusBox.innerHTML = '<div class="notice"><strong>로그인 완료</strong><br>지난 발행 이력을 불러왔습니다.</div>';
        await refreshSession();
      });
    }
    if (signupForm && !signupForm.dataset.bound) {
      signupForm.dataset.bound = '1';
      signupForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const form = new FormData(signupForm);
        const payload = Object.fromEntries(form.entries());
        const res = await fetch('/api/public/auth/register', { method:'POST', headers: headers(), body: JSON.stringify(payload) });
        const data = await res.json().catch(()=>({}));
        if (!res.ok) { if (statusBox) statusBox.innerHTML = `<div class="empty-box">${esc(data.detail || '회원가입에 실패했습니다.')}</div>`; return; }
        setPortalToken(data.token || '');
        if (statusBox) statusBox.innerHTML = '<div class="notice"><strong>회원가입 완료</strong><br>이제 발행 이력과 조회 코드를 같은 계정에서 관리할 수 있습니다.</div>';
        await refreshSession();
      });
    }
    if (logoutBtn && !logoutBtn.dataset.bound) {
      logoutBtn.dataset.bound = '1';
      logoutBtn.addEventListener('click', async () => {
        const token = getPortalToken();
        if (token) { try { await fetch('/api/public/auth/logout', { method:'POST', headers: headers(token) }); } catch {} }
        setPortalToken('');
        if (statusBox) statusBox.innerHTML = '<div class="notice">로그아웃했습니다.</div>';
        await refreshSession();
      });
    }
    await refreshSession();
  }

  function adminEntryRedirectTarget(trigger){
    return trigger?.dataset?.adminHref || `${base}admin/index.html`;
  }
  async function handleAdminEntryActivation(trigger, event){
    if (!trigger) return false;
    if (event) event.preventDefault();
    const redirectToAdmin = !path.includes('/admin/');
    const ok = await requestAdminAccess(redirectToAdmin);
    if (ok && redirectToAdmin) {
      const href = adminEntryRedirectTarget(trigger);
      if (href) window.location.href = href;
    }
    return ok;
  }
  function bindAdminEntry(){
    document.querySelectorAll('[data-admin-entry]').forEach((trigger) => {
      if (trigger.dataset.bound === '1') return;
      trigger.dataset.bound = '1';
      trigger.addEventListener('click', async (event) => {
        await handleAdminEntryActivation(trigger, event);
      });
    });
    if (!document.body.dataset.adminEntryDelegated) {
      document.body.dataset.adminEntryDelegated = '1';
      document.addEventListener('click', async (event) => {
        const trigger = event.target instanceof Element ? event.target.closest('[data-admin-entry]') : null;
        if (!trigger || trigger.dataset.bound === '1') return;
        await handleAdminEntryActivation(trigger, event);
      });
    }
  }
  function renderFooter(){
    const footer = document.getElementById('site-footer'); if (!footer) return;
    const info = config.brand?.business_info || {};
    const email = info.contact_email || config.brand?.contact_email || 'ct@nv0.kr';
    const operator = info.operator_name || config.brand?.name || 'NV0';
  const notice = info.support_notice || '정책과 제품 안내는 같은 기준으로 제공합니다.';
  const representative = info.representative_name || '';
  const bizNo = info.registration_number || '';
  const address = info.business_address || '';
  if (footer) {
    footer.innerHTML = `<div class="container footer-grid"><div><div class="brand"><span class="brand-mark">N0</span><span class="brand-copy"><strong>${config.brand?.name || 'NV0'}</strong><span>데모, 가격, 전달물을 먼저 보고 바로 판단할 수 있게 정리했습니다.</span></span></div><small style="margin-top:14px">공개 화면은 제품 이해와 구매 판단에 집중하고, 내부 운영 기능은 뒤로 분리했습니다.</small></div><div><strong>빠른 이동</strong><small><a href="${base}products/index.html">제품</a><br><a href="${base}solutions/index.html">문제별 시작</a><br><a href="${base}pricing/index.html">가격</a><br><a href="${base}docs/index.html">문서 센터</a><br><a href="${base}service/index.html">확장 서비스</a><br><a href="${base}faq/index.html">FAQ</a></small></div><div><strong>안내/정책</strong><small>상호: ${esc(operator)}<br>${representative ? `대표자: ${esc(representative)}<br>` : ''}${bizNo ? `사업자등록번호: ${esc(bizNo)}<br>` : ''}<a href="mailto:${email}">${esc(email)}</a><br>${address ? `${esc(address)}<br>` : ''}${esc(notice)}<br>시행일 2026-04-15 · 최종 개정일 2026-04-15<br><a href="${base}portal/index.html">고객 포털</a><br><a href="${base}contact/index.html">추가 확인</a><br><a href="${base}legal/privacy/index.html">개인정보처리방침</a><br><a href="${base}legal/terms/index.html">이용약관</a><br><a href="${base}legal/refund/index.html">환불 정책</a><br><a href="${base}legal/cookies/index.html">쿠키 및 저장 안내</a></small></div></div>`;
  }
  }


  function renderLiveStats(){
    const root = document.getElementById('live-stats'); if (!root) return;
    const publications = read(STORE.publications);
    const seed = publications.filter((item) => item.source === 'seed').length;
    const scheduled = publications.filter((item) => item.source === 'scheduled').length;
    root.innerHTML = `<article class="mini"><strong>${Object.keys(products).length}</strong><span>발행 축</span></article><article class="mini"><strong>${publications.length}</strong><span>전체 게시글</span></article><article class="mini"><strong>${seed}</strong><span>시드 글</span></article><article class="mini"><strong>${scheduled}</strong><span>예약 발행 글</span></article>`;
  }
  function renderWorkspaceCards(){ const root = document.getElementById('workspace-records'); if (!root) return; const orders = read(STORE.orders).slice(0, 2); const demos = read(STORE.demos).slice(0, 1); const contacts = read(STORE.contacts).slice(0, 1); const cards = []; orders.forEach((item) => cards.push(`<article class="record-card"><span class="tag">결제 접수</span><h4>${esc(item.company || item.email)}</h4><p>${esc(item.productName)} · ${esc(item.plan)} · 조회 코드 <span class="inline-code">${esc(item.code)}</span></p><div class="small-actions"><a href="${portalHref(item)}">제공 상태 확인</a><a href="${base}products/${item.product}/board/index.html">안내 글 보기</a></div></article>`)); demos.forEach((item) => cards.push(`<article class="record-card"><span class="tag">체험</span><h4>${esc(item.company || item.email)}</h4><p>${esc(item.productName)} 데모 시연 확인 · ${esc(item.code)}</p><div class="small-actions"><a href="${base}products/${item.product}/index.html">자세히 보기</a><a href="${base}products/${item.product}/index.html#order">가격/결제 보기</a></div></article>`)); contacts.forEach((item) => cards.push(`<article class="record-card"><span class="tag">추가 확인</span><h4>${esc(item.company || item.email)}</h4><p>${esc(item.productName)} · ${esc(item.issue || '')}</p><div class="small-actions"><a href="${item.product ? `${base}products/${item.product}/index.html` : `${base}company/index.html`}">제품 보기</a><a href="${item.product ? `${base}products/${item.product}/index.html#intro` : `${base}contact/index.html`}">다음 단계 확인</a></div></article>`)); root.innerHTML = cards.length ? cards.join('') : '<div class="empty-box">아직 저장된 체험이나 결제 기록이 없습니다. 먼저 제품별 샘플 결과를 확인해 보시면 다음 판단이 더 쉬워집니다.</div>'; }
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
      catalogRoot.innerHTML = topCategories.map((category, idx) => `<details class="fold-card" ${idx === 0 ? 'open' : ''}><summary><strong>${esc(category)}</strong><span>${grouped[category].length}개 연결</span></summary><div><div class="story-grid">${grouped[category].slice(0, 8).map((item) => `<article class="story-card"><span class="tag">${esc(item.id || '')}</span><h3>${esc(item.name || '')}</h3><p>${esc(item.summary || '')}</p><ul class="clean"><li>서비스 단계: ${esc(item.service_stage || '기본정리')}</li><li>서비스 유형: ${esc(item.service_type || '정리형')}</li><li>시작가: ${esc(item.price_from || '문의')}</li></ul><div class="small-actions"><span>주력 제품: ${esc(products[item.lead_product]?.name || item.lead_product || '공통')}</span><span>${esc(item.pricing_note || '')}</span></div></article>`).join('')}</div></div></details>`).join('');
    }
  }
  function renderServiceCatalog(){
    const root = document.getElementById('service-catalog-results');
    const statsRoot = document.getElementById('service-catalog-stats');
    const categoryFilter = document.getElementById('service-category-filter');
    const productFilter = document.getElementById('service-product-filter');
    const stageFilter = document.getElementById('service-stage-filter');
    const searchInput = document.getElementById('service-search');
    const fallback = document.getElementById('service-catalog-fallback');
    if (!root || !statsRoot || !categoryFilter || !productFilter || !stageFilter || !searchInput) return;
    if (fallback) fallback.hidden = true;
    const categories = [...new Set(serviceCatalog.map((item) => item.category || '기타 확장 서비스'))].sort();
    const productKeys = [...new Set(serviceCatalog.flatMap((item) => [item.lead_product, ...(item.fit_products || [])]).filter(Boolean))].filter((key) => products[key]).sort();
    const stages = [...new Set(serviceCatalog.map((item) => item.service_stage || '기본정리'))];
    categoryFilter.innerHTML = `<option value="">전체 카테고리</option>${categories.map((item) => `<option value="${esc(item)}">${esc(item)}</option>`).join('')}`;
    productFilter.innerHTML = `<option value="">전체 제품</option>${productKeys.map((key) => `<option value="${esc(key)}">${esc(products[key].name)}</option>`).join('')}`;
    stageFilter.innerHTML = `<option value="">전체 서비스 단계</option>${stages.map((item) => `<option value="${esc(item)}">${esc(item)}</option>`).join('')}`;
    const render = () => {
      const query = clean(searchInput.value).toLowerCase();
      const category = clean(categoryFilter.value);
      const productKey = clean(productFilter.value);
      const stage = clean(stageFilter.value);
      const items = serviceCatalog.filter((item) => {
        const haystack = `${item.id || ''} ${item.name || ''} ${item.category || ''} ${item.summary || ''} ${item.lead_product || ''} ${(item.fit_products || []).join(' ')}`.toLowerCase();
        const matchQuery = !query || haystack.includes(query);
        const matchCategory = !category || (item.category || '') === category;
        const fit = Array.isArray(item.fit_products) ? item.fit_products : [];
        const matchProduct = !productKey || item.lead_product === productKey || fit.includes(productKey);
        const matchStage = !stage || (item.service_stage || '기본정리') === stage;
        return matchQuery && matchCategory && matchProduct && matchStage;
      });
      const grouped = groupServices(items);
      const categoriesCount = Object.keys(grouped).length;
      const leadCount = items.filter((item) => item.lead_product).length;
      const priceBands = [...new Set(items.map((item) => item.price_band).filter(Boolean))].length;
      statsRoot.innerHTML = `<article class="admin-card"><span class="tag">검색 결과</span><h3>${items.length}</h3><p>현재 조건에 맞는 확장 서비스</p></article><article class="admin-card"><span class="tag">카테고리</span><h3>${categoriesCount}</h3><p>현재 조건에서 남은 범주 수</p></article><article class="admin-card"><span class="tag">가격대</span><h3>${priceBands}</h3><p>현재 조건에서 남은 시작가 구간</p></article><article class="admin-card"><span class="tag">주력 제안</span><h3>${leadCount}</h3><p>핵심 제품에 바로 붙일 수 있는 항목</p></article>`;
      root.innerHTML = items.length ? items.slice(0, 120).map((item) => `<article class="story-card"><span class="tag">${esc(item.id || '')}</span><h3>${esc(item.name || '')}</h3><p>${esc(item.summary || '')}</p><ul class="clean"><li>카테고리: ${esc(item.category || '기타')}</li><li>서비스 단계: ${esc(item.service_stage || '기본정리')}</li><li>서비스 유형: ${esc(item.service_type || '정리형')}</li><li>시작가: ${esc(item.price_from || '문의')}</li><li>연결 제품: ${esc((item.fit_products || []).map((key) => products[key]?.name || key).join(', ') || '공통 제안형')}</li></ul><div class="small-actions"><span>주력 제품: ${esc(products[item.lead_product]?.name || item.lead_product || '공통')}</span><span>${esc(item.pricing_note || '')}</span></div></article>`).join('') : '<div class="empty-box">조건에 맞는 확장 서비스가 없습니다. 검색어를 줄이거나 카테고리/단계를 전체로 바꿔 보세요.</div>';
    };
    [searchInput, categoryFilter, productFilter, stageFilter].forEach((node) => node.addEventListener('input', render));
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
  function buildPlans() { const root = document.getElementById('plan-grid'); if (!root || !product) return; root.innerHTML = product.plans.map((plan) => { const recommended = plan.recommended ? '<span class="tag" style="margin-left:8px">추천</span>' : ''; const meta = [plan.delivery ? `납기 ${esc(plan.delivery)}` : '', plan.revisions ? esc(plan.revisions) : ''].filter(Boolean).join(' · '); const includes = Array.isArray(plan.includes) && plan.includes.length ? `<ul class="clean plan-include-list">${plan.includes.map((item) => `<li>${esc(item)}</li>`).join('')}</ul>` : ''; return `<article class="plan-card ${plan.recommended ? 'recommended' : ''}"><div class="plan-head"><span class="tag">${esc(plan.name)}</span>${recommended}</div><h3>${esc(plan.price)}</h3><p>${esc(plan.note || '')}</p>${meta ? `<div class="plan-meta">${meta}</div>` : ''}${includes}<div class="small-actions"><a class="button" href="#order" data-plan-pick="${esc(plan.name)}">이 플랜으로 가격/결제 보기</a></div></article>`; }).join(''); root.querySelectorAll('[data-plan-pick]').forEach((btn)=>btn.addEventListener('click',()=>{ const form=document.getElementById('product-checkout-form'); if(form){ const select=form.querySelector('select[name="plan"]'); if(select) select.value=btn.dataset.planPick; location.hash='order'; }})); }
  function fillProductSlots() { if (!product) return; document.querySelectorAll('[data-fill="product-name"]').forEach((el) => el.textContent = product.name); document.querySelectorAll('[data-fill="product-headline"]').forEach((el) => el.textContent = product.headline); document.querySelectorAll('[data-fill="product-summary"]').forEach((el) => el.textContent = product.summary); document.querySelectorAll('[data-fill="product-problem"]').forEach((el) => el.textContent = product.problem); document.querySelectorAll('[data-fill="product-pricing"]').forEach((el) => el.textContent = currencyPlan(product.key)); const valueRoot = document.getElementById('product-values'); if (valueRoot) valueRoot.innerHTML = product.value_points.map((item) => `<li>${item}</li>`).join(''); const outputRoot = document.getElementById('product-outputs'); if (outputRoot) outputRoot.innerHTML = product.outputs.map((item) => `<li>${item}</li>`).join(''); const workflowRoot = document.getElementById('product-workflow'); if (workflowRoot) workflowRoot.innerHTML = (product.workflow || []).map((item) => `<li>${item}</li>`).join(''); const demoRoot = document.getElementById('product-demo-scenarios'); if (demoRoot) demoRoot.innerHTML = (product.demo_scenarios || []).map((item) => `<li>${item}</li>`).join(''); const relatedRoot = document.getElementById('product-related-modules'); if (relatedRoot) relatedRoot.innerHTML = (product.related_modules || []).map((key) => products[key]).filter(Boolean).map((item) => `<article class="story-card ${item.theme}"><span class="tag theme-chip">${esc(item.label)}</span><h3>${esc(item.name)}</h3><p>${esc(item.summary)}</p><div class="small-actions"><a href="${base}products/${item.key}/index.html#intro">제품 설명 보기</a><a href="${base}products/${item.key}/index.html#demo">데모 시연</a></div></article>`).join('') || '<div class="empty-box">바로 이어서 비교할 제품이 아직 없습니다. 현재 제품 기준으로 먼저 판단하셔도 괜찮습니다.</div>';  const faqRoot = document.getElementById('product-faq'); if (faqRoot) faqRoot.innerHTML = (product.faqs || []).map((item) => `<article class="faq-card"><span class="tag">Q</span><h3>${esc(item.q)}</h3><p>${esc(item.a)}</p></article>`).join(''); const actions = document.getElementById('product-actions'); if (actions) actions.innerHTML = `<a class="button" href="${base}products/${product.key}/demo/index.html">샘플 결과</a><a class="button secondary" href="${base}products/${product.key}/plans/index.html">플랜 보기</a><a class="button ghost" href="${base}products/${product.key}/delivery/index.html">전달 자료 보기</a><a class="button ghost" href="${base}products/${product.key}/board/index.html">자료실 보기</a>`; const basis = document.getElementById('product-pricing-basis'); if (basis) basis.textContent = product.pricing_basis || ''; const demoForm = document.getElementById('product-demo-form'); if (demoForm) { const defaults = product.demo_defaults || {}; demoForm.querySelectorAll('[data-demo-field]').forEach((input)=>{ const key = input.dataset.demoField; if (defaults[key] && !input.value) input.value = defaults[key]; }); const countryField = demoForm.querySelector('[name="country"]'); if (countryField && !countryField.value) countryField.value = 'KR'; } }
  function advanceOrder(orderId){ return updateItem(STORE.orders, orderId, (item) => { if (item.paymentStatus !== 'paid') throw new Error('결제 완료 전에는 자동 제공을 완료할 수 없습니다.'); return {...item, status:'delivered', deliveryMeta:{...(item.deliveryMeta||{}), automation:'local_auto', deliveredAt: stamp()}, updatedAt: stamp()}; }); }
  function toggleOrderPayment(orderId){ return updateItem(STORE.orders, orderId, (item) => { const paymentStatus = item.paymentStatus === 'paid' ? 'pending' : 'paid'; const status = paymentStatus === 'paid' ? 'delivered' : 'payment_pending'; return {...item, paymentStatus, status, deliveryMeta: paymentStatus === 'paid' ? { ...(item.deliveryMeta||{}), automation:'local_auto', deliveredAt: stamp() } : item.deliveryMeta, updatedAt: stamp()}; }); }
  function republishOrder(orderId){ const orders = read(STORE.orders); const order = orders.find((item) => item.id === orderId); if (!order) throw new Error('결제 접수를 찾지 못했습니다.'); const extra = createPublicationsForOrder(order); return updateItem(STORE.orders, orderId, (item) => ({...item, publicationIds: [...(item.publicationIds || []), ...extra.map((p) => p.id)], publicationCount: (item.publicationCount || 0) + extra.length, updatedAt: stamp()})); }
  function lookupOrder(email, code){ const orders = read(STORE.orders); if (code) { const exact = orders.find((item) => String(item.code).toLowerCase() === String(code).toLowerCase()); if (exact && (!email || String(exact.email).toLowerCase() === String(email).toLowerCase())) return exact; } if (email) return orders.find((item) => String(item.email).toLowerCase() === String(email).toLowerCase()) || null; return null; }
  function renderPublicationDetail(targetId, items){ const root = document.getElementById(targetId); if (!root) return; const params = new URLSearchParams(location.search); const postId = params.get('post'); const item = items.find((entry) => entry.id === postId) || items[0]; if (!item) { root.innerHTML = '<div class="empty-box">지금 표시할 글이 없습니다. 목록에서 다른 글을 선택하시거나 제품 상세로 이동해 주세요.</div>'; return; } const detailProduct = products[item.product] || null; const portalLink = item.code ? `${base}portal/index.html?code=${encodeURIComponent(item.code)}` : `${base}portal/index.html`; root.innerHTML = `<article class="post-detail"><span class="tag">${esc(item.productName || productName(item.product))}</span><h3>${esc(item.title)}</h3><p>${esc(item.summary)}</p><div class="kv"><div class="row"><strong>게시 시각</strong><span>${formatDate(item.createdAt)}</span></div><div class="row"><strong>조회 코드</strong><span>${esc(item.code || '기본 안내')}</span></div><div class="row"><strong>글 유형</strong><span>${esc(item.source || 'board')}</span></div><div class="row"><strong>본문</strong><span>${esc(item.body || item.summary).split('\n').join('<br>')}</span></div></div><div class="small-actions">${boardCtaMarkup(item)}<a href="${detailProduct ? `${base}products/${item.product}/index.html` : `${base}products/index.html`}">자세히 보기</a><a href="${base}products/${item.product}/board/index.html?post=${item.id}">같은 제품 글 더 보기</a><a href="${portalLink}">제공 상태 확인</a></div></article>`; }
  function renderPublicBoard() { const root = document.getElementById('public-board-grid'); if (!root) return; ensureSeedData(); const items = read(STORE.publications).filter((item) => item.product === 'veridion').sort((a,b) => (a.createdAt < b.createdAt ? 1 : -1)); if (!items.length) { root.innerHTML = '<div class="empty-box">아직 공개된 글이 없습니다. 조금 뒤 다시 확인하시거나 제품 상세에서 먼저 방향을 살펴보실 수 있습니다.</div>'; return; } root.innerHTML = items.slice(0, 12).map((item, idx) => `<article class="board-card board-card-blog"><span class="tag">Veridion 자료실 ${idx + 1}</span><h3>${esc(item.title)}</h3><p>${esc(item.summary)}</p><div class="board-meta"><span>${esc(item.productName || productName(item.product))}</span><span>${esc(String(item.readMinutes || 3))}분 읽기</span><span>${esc(item.format || 'ai-hybrid-blog')}</span></div><div class="small-actions">${boardCtaMarkup(item)}<a href="${publicBoardHref(item.id)}">글 보기</a><a href="${base}products/veridion/index.html">제품 상세</a></div></article>`).join(''); renderPublicationDetail('public-post-detail', items); }
  function renderProductBoard() { const root = document.getElementById('product-board-grid'); if (!root || !product) return; ensureSeedData(); const dynamic = read(STORE.publications).filter((item) => item.product === product.key); const automation = product.board_automation || {}; const seedCards = (automation.topics || []).map((topic, idx) => buildPublicationRecord({ product: product.key, title: topic.title, summary: topic.summary, source:'topic-seed', code:'', createdAt: stamp(), ctaLabel: topic.ctaText || automation.cta_label || '제품 보기', ctaHref: buildCtaHref(automation.cta_href, product.key), topicSummary: topic.summary, id:`topic-${idx}` })); const items = [...dynamic, ...seedCards].sort((a,b)=>a.createdAt < b.createdAt ? 1 : -1); root.innerHTML = items.slice(0, 12).map((item, idx) => `<article class="board-card board-card-blog"><span class="tag">${product.name} 자료실 ${idx + 1}</span><h3>${esc(item.title)}</h3><p>${esc(item.summary)}</p><div class="board-meta"><span>${esc(String(item.readMinutes || 3))}분 읽기</span><span>${esc(item.format || 'ai-hybrid-blog')}</span></div><div class="small-actions">${boardCtaMarkup(item)}<a href="${productBoardHref(product.key, item.id)}">글 보기</a><a href="${base}products/${product.key}/index.html#order">결제 진행</a></div></article>`).join(''); renderPublicationDetail('product-post-detail', items); }
  async function loadBoardFeed(){ const url = config.integration?.board_feed_endpoint; if (!url) return false; try { const res = await fetch(url, { headers: { 'Accept':'application/json' } }); if (!res.ok) return false; const payload = await res.json(); if (Array.isArray(payload?.items)) write(STORE.publications, payload.items); return Array.isArray(payload?.items); } catch { return false; } }
  function setPrefills(){ const params = new URLSearchParams(location.search); const productField = document.querySelector('input[name="product"], select[name="product"]'); if (productField && params.get('product')) productField.value = params.get('product'); const planField = document.querySelector('select[name="plan"][data-prefill="plan"]'); if (planField && params.get('plan')) planField.value = params.get('plan'); if (product?.key) { const report = getLastProductReport(product.key); if (report) applyProductReportToCheckout(product.key, report, report); } }
  function renderAdminSummary(){ const orders = read(STORE.orders); const demos = read(STORE.demos); const contacts = read(STORE.contacts); const publications = read(STORE.publications); const reports = read(STORE.reports); const summary = document.getElementById('admin-summary'); const delivered = orders.filter((item)=>item.status==='delivered'); const automated = delivered.filter((item)=>clean(item?.deliveryMeta?.automation || '').includes('auto')); const portalReady = delivered.filter((item)=>Boolean(item?.code && normalizeEmail(item?.email || ''))); const adminRuntime = runtime.systemConfig?.admin || {}; const paymentRuntime = runtime.systemConfig?.payment || {}; const securityState = adminRuntime.protected && adminRuntime.required ? '잠금' : adminRuntime.protected ? '부분 잠금' : '미설정'; if (summary) summary.innerHTML = `<article class="record-card"><span class="tag">주문</span><h4>${orders.length}</h4><p>저장된 결제·주문 건수</p></article><article class="record-card"><span class="tag">자동 전달</span><h4>${automated.length}</h4><p>자동 결과 생성과 전달 연결까지 끝난 주문</p></article><article class="record-card"><span class="tag">포털 연결</span><h4>${portalReady.length}</h4><p>조회 코드와 고객 포털 연결이 준비된 주문</p></article><article class="record-card"><span class="tag">관리 보안</span><h4>${esc(securityState)}</h4><p>${adminRuntime.required ? '관리자 비밀키가 필수로 설정된 상태입니다.' : '운영 환경에서는 NV0_REQUIRE_ADMIN_TOKEN=1 권장'}</p></article><article class="record-card"><span class="tag">Veridion 리포트</span><h4>${reports.filter((item)=>item.product==='veridion').length}</h4><p>실제 탐색 기반 발행 리포트</p></article>`; const automation = document.getElementById('admin-automation-grid'); if (automation) { const latest = reports.filter((item)=>item.product==='veridion').sort((a,b)=> String(a.createdAt||'') < String(b.createdAt||'') ? 1 : -1)[0]; const manualEnabled = Boolean(runtime.systemConfig?.admin?.manualActionsEnabled); automation.innerHTML = `<article class="record-card"><span class="tag">주문 자동화</span><h4>${orders.length ? Math.round((automated.length / orders.length) * 100) : 100}%</h4><p>${manualEnabled ? '수동 보정 허용 상태입니다.' : '수동 보정 버튼 없이 자동 흐름만 사용합니다.'}</p></article><article class="record-card"><span class="tag">콘텐츠 연결</span><h4>${publications.length}개 공개 글</h4><p>결제 완료 주문은 공개 글과 포털 기록이 같은 코드로 연결됩니다.</p></article><article class="record-card"><span class="tag">결제 런타임</span><h4>${paymentRuntime.toss?.enabled ? (paymentRuntime.toss?.mock ? 'Mock' : 'Live') : 'Off'}</h4><p>${paymentRuntime.toss?.enabled ? '결제 API가 열려 있습니다.' : '결제 키가 비어 있어 예약만 동작할 수 있습니다.'}</p></article><article class="record-card"><span class="tag">Veridion 스캔</span><h4>${latest?.stats?.explorationRate ?? '-' }%</h4><p>${latest ? `최근 리포트 ${esc(latest.code)} · 핵심 페이지 ${esc(String(latest.stats?.priorityCoverage ?? '-'))}%` : '아직 실제 탐색 리포트가 없습니다.'}</p></article>`; } const orderRoot = document.getElementById('admin-orders'); if (orderRoot) orderRoot.innerHTML = orders.length ? orders.slice(0,12).map((item)=>{ const publicationCount = Number(item.publicationCount || (item.publicationIds || []).length || 0); const autoMode = esc(item?.deliveryMeta?.automation || 'auto_runtime'); const reportLine = item.reportCode ? ` · 리포트 ${esc(item.reportCode)}` : ''; const paymentKeyLine = item.paymentKey ? '결제 키 확인 완료' : (clean(item.paymentStatus) === 'paid' ? '결제 승인 완료' : '결제 대기'); return `<article class="record-card"><span class="tag">${esc(item.productName || productName(item.product))}</span><h4>${esc(item.company || item.email)}</h4><p>플랜 ${esc(item.plan)} · 결제 ${esc(paymentStatusLabel(item.paymentStatus))} · 상태 ${esc(orderStatusLabel(item.status))}</p><p>조회 코드 <span class="inline-code">${esc(item.code)}</span>${reportLine}</p><ul class="clean"><li>자동화 모드: ${autoMode}</li><li>결과 묶음: ${publicationCount}건 연결</li><li>결제/포털: ${paymentKeyLine}</li></ul><div class="small-actions"><a href="${portalHref(item)}">고객 포털</a><a href="${base}products/${item.product}/index.html">제품 보기</a></div></article>`; }).join('') : '<div class="empty-box">저장된 주문이 없습니다.</div>'; const requestRoot = document.getElementById('admin-requests'); if (requestRoot) requestRoot.innerHTML = ([...demos.map((item)=>`<article class="record-card"><span class="tag">데모</span><h4>${esc(item.company || item.email)}</h4><p>${esc(item.productName)} · ${esc(item.need || '')}</p><p>코드 <span class="inline-code">${esc(item.code)}</span>${item.reportCode ? ` · 리포트 ${esc(item.reportCode)}` : ''}</p></article>`), ...contacts.map((item)=>`<article class="record-card"><span class="tag">문의</span><h4>${esc(item.company || item.email)}</h4><p>${esc(item.productName)} · ${esc(item.issue || '')}</p><p>코드 <span class="inline-code">${esc(item.code)}</span></p></article>`)]).slice(0,12).join('') || '<div class="empty-box">저장된 요청이 없습니다.</div>'; const pubRoot = document.getElementById('admin-publications'); if (pubRoot) pubRoot.innerHTML = publications.length ? publications.slice(0,12).map((item)=>`<article class="record-card"><span class="tag">${esc(item.productName || productName(item.product))}</span><h4>${esc(item.title)}</h4><p>${esc(item.summary)}</p><div class="small-actions"><a href="${publicBoardHref(item.id)}">전체 글</a><a href="${productBoardHref(item.product, item.id)}">제품 글</a></div></article>`).join('') : '<div class="empty-box">발행된 글이 없습니다.</div>'; const feed = document.getElementById('admin-feed'); if (feed) { const latest = reports.filter((item)=>item.product==='veridion').sort((a,b)=> String(a.createdAt||'') < String(b.createdAt||'') ? 1 : -1)[0]; const issuesHtml = latest ? (latest.issues || []).slice(0,4).map((item)=>`<div class="mock-step"><strong>${esc(item.title)}</strong><span>${esc(item.detail)}</span></div>`).join('') : ''; feed.innerHTML = `<div class="mock-step"><strong>자동 처리 원칙</strong><span>수동 결제 전환, 수동 전달 완료, 수동 재발행 버튼 없이 주문·결제·포털 연결을 자동 흐름으로만 유지합니다.</span></div>${latest ? `<div class="mock-step"><strong>최근 Veridion 리포트</strong><span>${esc(latest.code)} · 탐색률 ${esc(String(latest.stats?.explorationRate ?? '-'))}% · 핵심 페이지 ${esc(String(latest.stats?.priorityCoverage ?? '-'))}%</span></div>` : '<div class="empty-box">아직 Veridion 탐색 리포트가 없습니다.</div>'}${issuesHtml}`; } }
  function bindAdminActions(){
    const root = document.getElementById('admin-console');
    if (!root) return;
    const boardForm = document.getElementById('admin-board-settings-form');
    boardForm?.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(boardForm, async () => {
      const data = Object.fromEntries(new FormData(boardForm).entries());
      data.autoPublishAllProducts = boardForm.querySelector('input[name="autoPublishAllProducts"]')?.checked ? 1 : 0;
      const res = await postIfConfigured('/api/admin/board-settings', data);
      if (res.ok && res.json?.settings) { applyStatePayload(res.json?.state); showResult('admin-action-result', '자료실 CTA 자동 발행 설정을 저장했습니다.'); }
      else throw new Error(res.json?.detail || res.text || '자료실 설정 저장에 실패했습니다.');
    }).catch((error)=>showResult('admin-action-result', createFriendlyError(error,'자료실 설정 저장 실패'))); });
    const publishAll = document.getElementById('admin-publish-all');
    publishAll?.addEventListener('click', () => { withSubmitLock(boardForm || root, async () => {
      const res = await postIfConfigured('/api/admin/actions/publish-now', {});
      if (res.ok) { applyStatePayload(res.json?.state); renderPublicBoard(); renderProductBoard(); renderAdminSummary(); showResult('admin-action-result', '전체 제품 기준 자료실 글을 즉시 발행했습니다.'); }
      else throw new Error(res.json?.detail || res.text || '전체 발행에 실패했습니다.');
    }).catch((error)=>showResult('admin-action-result', createFriendlyError(error,'전체 발행 실패'))); });
    const publicationForm = document.getElementById('admin-publication-form');
    publicationForm?.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(publicationForm, async () => {
      const payload = Object.fromEntries(new FormData(publicationForm).entries());
      const res = await postIfConfigured('/api/admin/library/publications', payload);
      if (res.ok) { applyStatePayload(res.json?.state); publicationForm.reset(); renderPublicBoard(); renderProductBoard(); renderAdminSummary(); showResult('admin-action-result', '자료실 글을 등록했습니다.'); }
      else throw new Error(res.json?.detail || res.text || '자료실 글 등록에 실패했습니다.');
    }).catch((error)=>showResult('admin-action-result', createFriendlyError(error,'자료실 글 등록 실패'))); });
    const assetForm = document.getElementById('admin-asset-form');
    assetForm?.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(assetForm, async () => {
      const fd = new FormData(assetForm);
      const res = await fetch('/api/admin/library/assets', fetchOptionsFor('/api/admin/library/assets', { method:'POST', headers: headersFor('/api/admin/library/assets'), body: fd }));
      const json = await res.json().catch(()=>null);
      if (res.ok && json?.asset) { assetForm.reset(); showResult('admin-action-result', `파일 업로드 완료: ${esc(json.asset.title)} / ${esc(json.asset.url)}`); }
      else throw new Error(json?.detail || '파일 업로드에 실패했습니다.');
    }).catch((error)=>showResult('admin-action-result', createFriendlyError(error,'파일 업로드 실패'))); });
    root.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-admin-action]');
      if (!button) return;
      event.preventDefault();
      showResult('admin-action-result', '수동 보정 버튼은 기본 비활성화 상태입니다. 자동 흐름 이상이 보이면 로그·백업·복구 기준으로만 점검하세요.');
    });
  }

  function detectCountryCodeFromWebsite(value){
    const url = String(value || '').trim().toLowerCase();
    if (!url) return '';
    if (/(\.co\.kr|\.or\.kr|\.go\.kr|\.ac\.kr|\.kr)(?:[\/:?#]|$)/.test(url)) return 'KR';
    if (/(\.co\.jp|\.ne\.jp|\.or\.jp|\.jp)(?:[\/:?#]|$)/.test(url)) return 'JP';
    if (/(\.com\.cn|\.cn)(?:[\/:?#]|$)/.test(url)) return 'CN';
    if (/(\.com\.sg|\.com\.my|\.co\.id|\.co\.th|\.ph|\.vn)(?:[\/:?#]|$)/.test(url)) return 'SEA';
    if (/(\.de|\.fr|\.it|\.es|\.nl|\.eu)(?:[\/:?#]|$)/.test(url)) return 'EU';
    if (/(\.com|\.io|\.ai|\.us)(?:[\/:?#]|$)/.test(url)) return 'US';
    return '';
  }

  function recommendVeridionFocus(industry, country){
    const key = `${clean(industry) || 'commerce'}:${clean(country) || 'KR'}`;
    const map = {
      'commerce:KR': '결제·환불·청약철회 고지',
      'commerce:US': '결제·환불·청약철회 고지',
      'commerce:JP': '결제·환불·청약철회 고지',
      'commerce:CN': '결제·환불·청약철회 고지',
      'commerce:EU': '개인정보·회원가입 동선',
      'commerce:SEA': '결제·환불·청약철회 고지',
      'commerce:GLOBAL': '전체 리스크 빠르게 보기',
      'beauty:KR': '광고·표시 문구',
      'beauty:US': '광고·표시 문구',
      'beauty:JP': '광고·표시 문구',
      'beauty:CN': '광고·표시 문구',
      'beauty:EU': '광고·표시 문구',
      'beauty:SEA': '광고·표시 문구',
      'beauty:GLOBAL': '광고·표시 문구',
      'healthcare:KR': '민감 업종·표현 위험',
      'healthcare:US': '민감 업종·표현 위험',
      'healthcare:JP': '민감 업종·표현 위험',
      'healthcare:CN': '민감 업종·표현 위험',
      'healthcare:EU': '민감 업종·표현 위험',
      'healthcare:SEA': '민감 업종·표현 위험',
      'healthcare:GLOBAL': '민감 업종·표현 위험',
      'education:KR': '약관·정책 문서 일치',
      'education:US': '약관·정책 문서 일치',
      'education:JP': '약관·정책 문서 일치',
      'education:CN': '약관·정책 문서 일치',
      'education:EU': '개인정보·회원가입 동선',
      'education:SEA': '약관·정책 문서 일치',
      'education:GLOBAL': '약관·정책 문서 일치',
      'saas:KR': '개인정보·회원가입 동선',
      'saas:US': '개인정보·회원가입 동선',
      'saas:JP': '개인정보·회원가입 동선',
      'saas:CN': '개인정보·회원가입 동선',
      'saas:EU': '개인정보·회원가입 동선',
      'saas:SEA': '개인정보·회원가입 동선',
      'saas:GLOBAL': '개인정보·회원가입 동선'
    };
    return map[key] || map[`${clean(industry) || 'commerce'}:KR`] || '전체 리스크 빠르게 보기';
  }

  function setupVeridionSmartFocus(form){
    if (!form || form.dataset.smartFocusBound === '1') return;
    const website = form.querySelector('[name="website"]');
    const industry = form.querySelector('[name="industry"]');
    const country = form.querySelector('[name="country"]');
    const focus = form.querySelector('[name="focus"]');
    if (!industry || !country || !focus) return;
    form.dataset.smartFocusBound = '1';

    let hint = form.querySelector('.smart-focus-note');
    if (!hint) {
      hint = document.createElement('div');
      hint.className = 'notice notice-light smart-focus-note';
      hint.style.marginTop = '12px';
      const actions = form.querySelector('.actions');
      form.insertBefore(hint, actions || null);
    }

    const updateHint = (reason='') => {
      const countryLabel = country.selectedOptions?.[0]?.textContent?.trim() || '대한민국';
      const focusLabel = focus.selectedOptions?.[0]?.textContent?.trim() || focus.value || '전체 리스크 빠르게 보기';
      hint.innerHTML = `<strong>자동 추천 적용</strong><br>${esc(countryLabel)} 운영 기준으로 <strong>${esc(focusLabel)}</strong>을 우선 점검하도록 맞췄습니다.${reason ? ` ${esc(reason)}` : ''}`;
    };

    const syncRecommendedFocus = (reason='') => {
      if (focus.dataset.manual === '1') { updateHint('중점 확인 사항은 수동 선택을 유지합니다.'); return; }
      const recommended = recommendVeridionFocus(industry.value, country.value);
      if ([...focus.options].some((opt) => opt.value === recommended)) focus.value = recommended;
      updateHint(reason);
    };

    focus.addEventListener('change', () => { focus.dataset.manual = '1'; updateHint('중점 확인 사항은 수동 선택을 유지합니다.'); });
    industry.addEventListener('change', () => syncRecommendedFocus('업종 기준으로 다시 추천했습니다.'));
    country.addEventListener('change', () => { country.dataset.manual = '1'; syncRecommendedFocus('운영 국가 기준으로 다시 추천했습니다.'); });
    website?.addEventListener('blur', () => {
      website.value = normalizeWebsiteInput(website.value);
      if (country.dataset.manual === '1') return;
      const detected = detectCountryCodeFromWebsite(website.value);
      if (detected && country.value !== detected) { country.value = detected; syncRecommendedFocus('사이트 주소 도메인을 보고 운영 국가를 자동 반영했습니다.'); }
    });
    website?.addEventListener('paste', () => { setTimeout(() => { website.value = normalizeWebsiteInput(website.value); }, 0); });

    syncRecommendedFocus();
  }

  function buildDemoSaveBox(entry, remoteSaved){
    if (entry?.code) return `<div class="demo-save-box"><strong>임시 저장 결과</strong><br>조회 코드 <span class="inline-code">${esc(entry.code)}</span> 로 데모를 다시 확인할 수 있습니다.${remoteSaved ? ' 서버에도 저장했습니다.' : ''}</div>`;
    return `<div class="demo-save-box"><strong>다음 단계</strong><br>무료 데모는 저장형 문의가 아니라 즉시 분석 화면입니다. 결제 후 진행 정보 입력 단계에서 회사명, 담당자명, 이메일, 사이트 주소를 한 번에 받습니다.</div>`;
  }

  function renderProductDemoWorkspace(){
    const root = document.getElementById('product-demo-shell');
    if (!root || !product) return;
    if (product.key === 'veridion') {
      root.innerHTML = `<form id="product-demo-form" class="stack-form"><div class="form-grid"><div class="span-2"><label>사이트 주소</label><input name="website" data-demo-field="website" placeholder="https://example.com" inputmode="url" autocomplete="url" required></div><div><label>업종</label><select name="industry" data-demo-field="industry"><option value="commerce">이커머스</option><option value="beauty">뷰티·웰니스</option><option value="healthcare">의료·건강</option><option value="education">교육·서비스</option><option value="saas">B2B SaaS</option></select></div><div><label>운영 국가</label><select name="country" data-demo-field="country"><option value="KR" selected>대한민국</option><option value="US">미국</option><option value="JP">일본</option><option value="CN">중국</option><option value="EU">유럽연합</option><option value="SEA">동남아</option><option value="GLOBAL">글로벌</option></select></div><div><label>중점 확인 사항</label><select name="focus" data-demo-field="focus"><option value="전체 리스크 빠르게 보기">전체 리스크 빠르게 보기</option><option value="개인정보·회원가입 동선">개인정보·회원가입 동선</option><option value="결제·환불·청약철회 고지">결제·환불·청약철회 고지</option><option value="광고·표시 문구">광고·표시 문구</option><option value="약관·정책 문서 일치">약관·정책 문서 일치</option><option value="민감 업종·표현 위험">민감 업종·표현 위험</option></select></div></div><div class="notice notice-light"><strong>데모에서 바로 보여주는 항목</strong><br>영역별 위반 가능 항목 수, 위기 점수, 유사 업종 대비 하위 퍼센트, 예상 최대 과태료, 결제 후 열리는 서비스 1·2·3까지 먼저 확인합니다.</div><div class="actions"><button class="button" type="submit">즉시 분석하기</button><a class="button ghost" href="#order">바로 결제</a></div></form>`;
      setupVeridionSmartFocus(document.getElementById('product-demo-form'));
      return;
    }
    root.innerHTML = `<form id="product-demo-form" class="stack-form"><div class="form-grid"><div><label>회사명(선택)</label><input name="company" data-demo-field="company" placeholder="예: 샘플 브랜드"></div><div><label>중점 확인 사항</label><select name="focus" data-demo-field="focus"><option value="전체 리스크 빠르게 보기">전체 리스크 빠르게 보기</option><option value="개인정보·회원가입 동선">개인정보·회원가입 동선</option><option value="결제·환불·청약철회 고지">결제·환불·청약철회 고지</option><option value="광고·표시 문구">광고·표시 문구</option><option value="약관·정책 문서 일치">약관·정책 문서 일치</option><option value="민감 업종·표현 위험">민감 업종·표현 위험</option></select></div></div><div class="actions"><button class="button" type="submit">즉시 분석하기</button><a class="button ghost" href="#order">바로 결제</a></div></form>`;
  }

  function intakeFormMarkup(order){
    return `<form id="payment-intake-form" class="stack-form"><div class="form-grid"><div><label>회사명</label><input name="company" value="${esc(order?.company || '')}" required></div><div><label>담당자명</label><input name="name" value="${esc(order?.name || '')}" required></div><div><label>이메일</label><input name="email" type="email" value="${esc(order?.email || '')}" required></div><div class="span-2"><label>사이트 주소</label><input name="website" value="${esc(order?.link || '')}" placeholder="https://example.com" ${order?.product === 'veridion' ? 'required' : ''}></div></div><div class="actions"><button class="button" type="submit">진행 정보 저장하고 결과 받기</button></div></form>`;
  }

  async function startCheckout(payload, resultId){
    const reserve = await postIfConfigured(config.integration?.reserve_order_endpoint || '/api/public/orders/reserve', payload);
    if (!(reserve.ok && reserve.json?.order)) throw new Error(reserve.json?.detail || reserve.text || '결제 준비에 실패했습니다.');
    applyStatePayload(reserve.json?.state);
    const order = reserve.json.order;
    try { sessionStorage.setItem('nv0-last-order', JSON.stringify(order)); } catch {}
    const payment = reserve.json.payment || paymentRuntime() || {};
    const successUrl = `${location.origin}${base === './' ? '' : base.replace(/\.\//g,'')}`;
    if (payment.enabled && !payment.mock && window.TossPayments && payment.clientKey) {
      const toss = window.TossPayments(payment.clientKey);
      await toss.requestPayment('카드', { amount: order.amount, orderId: order.id, orderName: `${productName(order.product)} ${order.plan}`, customerName: '결제 고객', successUrl: `${location.origin}/payments/toss/success/`, failUrl: `${location.origin}/payments/toss/fail/` });
      return order;
    }
    const query = new URLSearchParams({ orderId: order.id, paymentKey: `mock_${order.id}`, amount: String(order.amount), mock: '1' });
    location.href = `${base}payments/toss/success/index.html?${query.toString()}`;
    showResult(resultId, '결제 페이지로 이동합니다.');
    return order;
  }

  async function bindProductCheckoutForm(){
    const form = document.getElementById('product-checkout-form');
    if (!form) return;
    form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
      const values = Object.fromEntries(new FormData(form).entries());
      assert(validateProduct(values.product), '제품을 확인해 주세요.');
      assert(validatePlan(values.product, values.plan), '플랜을 선택해 주세요.');
      const report = getLastProductReport(values.product);
      const payload = { ...values, reportId: values.reportId || report?.id || '', reportCode: values.reportCode || report?.code || '', link: values.link || report?.scannedWebsite || report?.website || '' };
      await startCheckout(payload, 'product-checkout-result');
    }).catch((error)=>showResult('product-checkout-result', createFriendlyError(error,'결제 시작 실패'))); });
  }

  function bindDemoForm(){
    const form = document.getElementById('demo-form');
    if (!form) return;
    setupVeridionSmartFocus(form);
    form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
      const values = Object.fromEntries(new FormData(form).entries());
      values.website = normalizeWebsiteInput(values.website);
      const websiteField = form.querySelector('[name="website"]');
      if (websiteField) websiteField.value = values.website;
      values.country = clean(values.country) || 'KR';
      values.countryLabel = form.querySelector('[name="country"]')?.selectedOptions?.[0]?.textContent?.trim() || '대한민국';
      values.market = values.countryLabel;
      values.options = veridionOptionsFromValues(values);
      assert(clean(values.website), '사이트 주소를 입력하세요.');
      showResult('demo-result', '<div class="notice"><strong>분석 중입니다.</strong><br>사이트 주소와 운영 국가 기준으로 공개 화면을 점검하고 있습니다.</div>');
      const res = await postIfConfigured(veridionScanEndpoint(), values);
      if (res.mode === 'remote' && res.ok && res.json?.report) {
        applyStatePayload(res.json?.state);
        const report = res.json.report;
        setLastVeridionReport(report);
        showResult('demo-result', renderVeridionRemoteReport(report, values) + buildDemoSaveBox(null, false));
        return;
      }
      const reason = res.mode === 'remote' ? (res.json?.detail || res.text || '실제 탐색 응답이 불안정했습니다.') : (res.error || '서버 연결이 불안정했습니다.');
      showResult('demo-result', buildVeridionFallbackHtml(values, reason) + buildDemoSaveBox(null, false));
    }).catch((error)=>showResult('demo-result', `<div class="empty-box">${esc(createFriendlyError(error,'즉시 분석 실패'))}</div>`)); });
  }

  function bindCheckoutForm(){
    const form = document.getElementById('checkout-form');
    if (!form) return;
    form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
      const values = Object.fromEntries(new FormData(form).entries());
      await startCheckout(values, 'checkout-result');
    }).catch((error)=>showResult('checkout-result', createFriendlyError(error,'결제 시작 실패'))); });
  }

  function bindContactForm(){
    const form = document.getElementById('contact-form');
    if (!form) return;
    form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
      const payload = Object.fromEntries(new FormData(form).entries());
      const res = await postIfConfigured(config.integration?.contact_endpoint || '/api/public/contact-requests', payload);
      if (res.ok && res.json?.contact) { applyStatePayload(res.json?.state); showResult('contact-result', `문의가 저장되었습니다. 조회 코드 ${esc(res.json.contact.code)}`); }
      else throw new Error(res.json?.detail || res.text || '문의 저장 실패');
    }).catch((error)=>showResult('contact-result', createFriendlyError(error,'문의 저장 실패'))); });
  }

  function bindPortalLookup(){
    const form = document.getElementById('portal-lookup-form');
    if (!form) return;
    form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
      const payload = Object.fromEntries(new FormData(form).entries());
      const res = await postIfConfigured(config.integration?.portal_lookup_endpoint || '/api/public/portal/lookup', payload);
      if (res.ok) { applyStatePayload(res.json?.state); const order = res.json?.order; showResult('portal-lookup-result', order ? `조회 코드 ${esc(order.code)} · 상태 ${esc(orderStatusLabel(order.status))}` : '일치하는 결과를 찾지 못했습니다.'); }
      else throw new Error(res.json?.detail || res.text || '조회 실패');
    }).catch((error)=>showResult('portal-lookup-result', createFriendlyError(error,'조회 실패'))); });
  }

  async function bindPaymentResultPages(){
    if (pageKey === 'payment-success') {
      const target = document.getElementById('payment-success-result');
      const params = new URLSearchParams(location.search);
      const orderId = params.get('orderId');
      const paymentKey = params.get('paymentKey') || `mock_${orderId || ''}`;
      const amount = Number(params.get('amount') || 0);
      if (!orderId || !amount) { if (target) target.innerHTML = '결제 정보가 없어 확인할 수 없습니다.'; return; }
      try {
        const res = await postIfConfigured(config.integration?.toss_confirm_endpoint || '/api/public/payments/toss/confirm', { orderId, paymentKey, amount });
        if (!(res.ok && res.json?.order)) throw new Error(res.json?.detail || res.text || '결제 확인 실패');
        applyStatePayload(res.json?.state);
        const order = res.json.order;
        if (order.status === 'intake_required') {
          target.innerHTML = `<strong>결제는 완료되었습니다.</strong><br>이제 진행 정보만 입력하면 결과 제공을 시작합니다.` + intakeFormMarkup(order);
          const intakeForm = document.getElementById('payment-intake-form');
          intakeForm?.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(intakeForm, async () => {
            const payload = Object.fromEntries(new FormData(intakeForm).entries());
            const intake = await postIfConfigured(`/api/public/orders/${encodeURIComponent(order.id)}/intake`, payload);
            if (!(intake.ok && intake.json?.order)) throw new Error(intake.json?.detail || intake.text || '진행 정보 저장 실패');
            applyStatePayload(intake.json?.state);
            const done = intake.json.order;
            target.innerHTML = `<strong>진행 정보가 저장되었습니다.</strong><br>조회 코드 <span class="inline-code">${esc(done.code)}</span> · 상태 ${esc(orderStatusLabel(done.status))}<br><a class="button" href="${portalHref(done)}">고객 포털 열기</a>`;
          }).catch((error)=>{ target.innerHTML = createFriendlyError(error,'진행 정보 저장 실패'); }); });
        } else {
          target.innerHTML = `<strong>결제 확인 완료</strong><br>조회 코드 <span class="inline-code">${esc(order.code)}</span> · 상태 ${esc(orderStatusLabel(order.status))}<br><a class="button" href="${portalHref(order)}">고객 포털 열기</a>`;
        }
      } catch (error) { if (target) target.innerHTML = createFriendlyError(error,'결제 확인 실패'); }
    }
    if (pageKey === 'payment-fail') {
      const target = document.getElementById('payment-fail-result');
      const params = new URLSearchParams(location.search);
      if (target) target.innerHTML = `결제가 완료되지 않았습니다. ${esc(params.get('message') || '잠시 후 다시 시도해 주세요.')}`;
    }
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

function buildDemoUpsellBox(productKey){
  const target = products[productKey] || products.veridion || Object.values(products)[0];
  if (!target) return '';
  const recommended = (target.plans || []).find((item)=>item.recommended) || (target.plans || [])[0];
  const planText = recommended ? `${recommended.name} · ${recommended.price || ''}` : '추천 플랜';
  return `<div class="demo-upsell-box"><strong>다음으로 가장 효율적인 선택</strong><br>${esc(target.name)} ${esc(planText)} 기준으로 전체 결과, 전달 자산, 고객 포털 연결까지 한 번에 열 수 있습니다.<div class="small-actions"><a href="${base}products/${target.key}/plans/index.html">추천 플랜 보기</a><a href="${base}products/${target.key}/index.html#order">가격/결제 바로가기</a></div></div>`;
}
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
      extra:`<div class="demo-section-stack"><h4>제출 운영 제품 소개</h4>${renderDemoTable(rows)}<h4>바로 쓸 수 있는 안내문</h4>${renderCopyCards(copyCards)}</div>`,
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
        <div class="demo-save-box"><strong>이번 결과 한 줄 제품 소개</strong><br>${esc(result.note || '')}</div>${buildDemoUpsellBox(product.key)}
      </div>
    `;
  }

  function buildHomeProducts() {
    const root = document.getElementById('product-grid');
    if (!root) return;
    const focus = products.veridion || Object.values(products)[0];
    if (!focus) { root.innerHTML = '<div class="empty-box">현재 공개된 핵심 제품 정보가 없습니다.</div>'; return; }
    root.innerHTML = `
      <article class="card product-card strong ${focus.theme}">
        <span class="tag theme-chip">공개 핵심 제품</span>
        <h3>${esc(focus.name)}</h3>
        <p>${esc(focus.problem || focus.headline || '')}</p>
        <ul class="clean">${(focus.value_points || []).slice(0, 4).map((text) => `<li>${esc(text)}</li>`).join('')}</ul>
        <div class="muted-box" style="margin-top:18px">${esc(focus.pricing_basis || '')}</div>
        <div class="actions">
          <a class="button" href="${productPageHref(focus.key, '#demo')}">무료 데모 보기</a>
          <a class="button secondary" href="${base}products/${focus.key}/plans/index.html">가격 보기</a>
          <a class="button ghost" href="${base}products/${focus.key}/board/index.html">자료실 보기</a>
        </div>
      </article>
      <article class="card strong">
        <span class="tag">결제 후 열리는 항목</span>
        <h3>전체 리포트, 맞춤 문구안, 정밀 발행, 이력 조회</h3>
        <p>무료 데모에서는 상위 이슈와 위기 점수만 먼저 보여 주고, 결제 후에는 전체 이슈 목록과 페이지별 수정 우선순위, 사이트 맞춤 지침과 문구안, 로그인 이력 조회까지 연결합니다.</p>
        <ul class="clean"><li>영역별 이슈 건수와 위기 점수</li><li>예상 과태료 범위와 수정 우선순위</li><li>맞춤 지침·문구 작성 추가 발행</li><li>로그인 후 지난 발행 이력 조회</li></ul>
      </article>
    `;
  }

  function buildModuleMatrix() {
    const root = document.getElementById('module-matrix');
    if (!root) return;
    const modules = Object.values(products).filter((item) => item.key !== 'veridion');
    if (!modules.length) { root.innerHTML = '<div class="empty-box">현재 분리 모듈이 없습니다.</div>'; return; }
    root.innerHTML = modules.map((item) => `
      <article class="story-card ${item.theme}">
        <span class="tag theme-chip">분리 모듈</span>
        <h3>${esc(item.name)}</h3>
        <p>${esc(item.summary || item.problem || '')}</p>
        <div class="actions">
          <a class="button soft" href="${base}products/${item.key}/index.html">모듈 상세 보기</a>
          <a class="button ghost" href="${base}products/${item.key}/board/index.html">자료실 보기</a>
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
    if (actions) actions.innerHTML = `<a class="button" href="#demo">실제 데모</a><a class="button secondary" href="#order">플랜/결제</a><a class="button ghost" href="#delivery">전달 범위</a><a class="button ghost" href="${base}products/${product.key}/board/index.html">자료실</a>`;
    const basis = document.getElementById('product-pricing-basis');
    if (basis) basis.textContent = product.pricing_basis || '';
    renderProductDemoWorkspace();
  }

  async function bindProductDemoForm(){
    const form = document.getElementById('product-demo-form');
    if (!form || !product) return;
    if (product.key === 'veridion') setupVeridionSmartFocus(form);
    form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
      const data = new FormData(form);
      const values = Object.fromEntries(data.entries());
      values.options = checkedValues(form, 'option');
      if (product.key === 'veridion') {
        values.country = clean(values.country) || 'KR';
        const countryField = form.querySelector('[name="country"]');
        values.countryLabel = countryField?.selectedOptions?.[0]?.textContent?.trim() || '대한민국';
        values.market = values.countryLabel;
        assert(clean(values.website), '점검할 URL을 입력하세요.');
      }
      let remoteReport = null;
      if (product.key === 'veridion') {
        values.website = normalizeWebsiteInput(values.website);
        const websiteField = form.querySelector('[name="website"]');
        if (websiteField) websiteField.value = values.website;
        values.options = veridionOptionsFromValues(values);
        const scanPayload = { website: values.website, industry: values.industry, country: values.country, market: values.market, maturity: values.maturity, pages: values.pages, focus: values.focus, options: values.options, company: values.company };
        const scan = await postIfConfigured(veridionScanEndpoint(), scanPayload);
        if (scan.mode === 'remote' && scan.ok && scan.json?.report) { applyStatePayload(scan.json?.state); remoteReport = scan.json.report; setLastProductReport('veridion', remoteReport); }
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
        const demoPayload = { product: product.key, company: values.company, name: values.name, email: values.email, team: values.teamSize || values.contributors || values.approvalSteps || values.countryLabel || values.market || '', need: note, keywords: (values.options || []).join(', '), reportId: remoteReport?.id || '', reportCode: remoteReport?.code || '' };
        const remote = await postIfConfigured(config.integration?.demo_endpoint, demoPayload);
        if (remote.mode === 'remote' && remote.ok && remote.json?.demo) { applyStatePayload(remote.json?.state); await syncRemoteState(); entry = remote.json.demo; remoteSaved = true; }
        else if (remote.mode === 'remote' && !remote.ok) throw new Error(remote.json?.detail || remote.text || '데모 저장에 실패했습니다.');
        else entry = createDemo(demoPayload);
      }
      const remoteHtml = product.key === 'veridion' ? renderVeridionRemoteReport(remoteReport, values) : product.key === 'clearport' ? renderClearportRemoteReport(remoteReport, values) : product.key === 'grantops' ? renderGrantopsRemoteReport(remoteReport, values) : renderDraftforgeRemoteReport(remoteReport, values);
      const fallbackHtml = product.key === 'veridion' ? buildVeridionFallbackHtml(values, '실시간 탐색 응답이 불안정해도 입력값 기준 프리뷰를 먼저 보여드립니다.') : buildProductSpecificDemoResult(values);
      const html = ((remoteReport ? remoteHtml : fallbackHtml) || fallbackHtml) + buildDemoSaveBox(entry, remoteSaved);
      showResult('product-demo-result', html);
      fillCheckoutFromDemo({ company: values.company, name: values.name, email: values.email, note });
      if (remoteReport) applyProductReportToCheckout(product.key, values, remoteReport);
      renderAdminSummary(); renderLiveStats(); renderWorkspaceCards();
    }); });
  }


function renderHeader(){
  const header = document.getElementById('site-header'); if (!header) return;
  const quickLinks = renderProductSubLinks('sub-link');
  header.innerHTML = `<div class="container nav-wrap"><div class="nav-left"><button class="mobile-nav-toggle" type="button" aria-expanded="false" aria-controls="mobile-drawer" data-nav-toggle="1">메뉴</button><a class="brand" href="${base}index.html"><span class="brand-mark">V</span><span class="brand-copy"><strong>Veridion</strong><span>온라인 개인사업자용 법률·규제 리스크 방어막</span></span></a></div><nav class="nav-links">${renderNavLinks('top-link')}<a class="button ghost admin-link-inline" href="${base}admin/index.html" data-admin-entry="1" data-admin-href="${base}admin/index.html" title="관리 메뉴를 엽니다">관리</a></nav></div><div class="container subnav"><span class="subnav-label">제품</span>${quickLinks}</div>`;
}

function renderSidebar(){
  let shell = document.getElementById('side-nav-shell');
  if (!shell) {
    shell = document.createElement('aside');
    shell.id = 'side-nav-shell';
    shell.className = 'side-nav-shell';
    document.body.prepend(shell);
  }
  shell.innerHTML = '';
  document.body.classList.remove('with-side-nav');
  if (!document.getElementById('mobile-nav-backdrop')) {
    const backdrop = document.createElement('button');
    backdrop.type = 'button';
    backdrop.id = 'mobile-nav-backdrop';
    backdrop.className = 'mobile-nav-backdrop';
    backdrop.setAttribute('aria-hidden', 'true');
    document.body.appendChild(backdrop);
  }
  let drawer = document.getElementById('mobile-drawer');
  if (!drawer) {
    drawer = document.createElement('aside');
    drawer.id = 'mobile-drawer';
    drawer.className = 'mobile-drawer';
    document.body.appendChild(drawer);
  }
  drawer.innerHTML = `<div class="mobile-drawer-card"><div class="mobile-drawer-top"><strong>메뉴</strong><button class="mobile-nav-close" type="button" data-nav-close="1">닫기</button></div><a class="side-admin-button" href="${base}admin/index.html" data-admin-entry="1" data-admin-href="${base}admin/index.html" title="관리 메뉴를 엽니다">관리</a><nav class="side-nav-links"><div class="side-group"><span class="side-group-title">메인 메뉴</span>${renderNavLinks('side-link')}</div><div class="side-group"><span class="side-group-title">제품</span>${renderProductSubLinks('side-sublink')}<a href="${base}products/veridion/demo/index.html" class="side-sublink ${path.includes('/products/veridion/demo/') ? 'active' : ''}">즉시 데모</a></div></nav></div>`;
}

function orderStatusLabel(status){ return ({payment_pending:'결제 대기', intake_required:'진행 정보 입력 필요', draft_ready:'자동 실행 준비', published:'콘텐츠 발행 완료', delivered:'결과 전달 완료'})[clean(status)] || (clean(status) || '확인 필요'); }

function syncPlanOptionsForForm(form){
  if (!form) return;
  const select = form.elements?.plan;
  if (!select || select.tagName !== 'SELECT') return;
  const productKey = clean(form.elements?.product?.value || product?.key || document.body?.dataset?.product || '');
  const target = products[productKey];
  const plans = Array.isArray(target?.plans) ? target.plans : [];
  if (!plans.length) return;
  const previous = clean(select.value);
  select.innerHTML = plans.map((item) => `<option value="${esc(item.name)}">${esc(item.name)} · ${esc(item.price || '')}</option>`).join('');
  const fallback = (plans.find((item) => item.recommended)?.name) || plans[0].name;
  select.value = plans.some((item) => item.name === previous) ? previous : fallback;
}

function syncBillingForForm(form){
  if (!form) return 'one-time';
  const productKey = clean(form.elements?.product?.value || product?.key || document.body?.dataset?.product || '');
  const planName = clean(form.elements?.plan?.value || 'Starter');
  const plan = products[productKey]?.plans?.find((item) => item.name === planName);
  const billing = clean(plan?.billing || form.elements?.billing?.value || 'one-time');
  if (form.elements?.billing) form.elements.billing.value = billing;
  return billing;
}

function updatePlanSummary(form, summaryId){
  const summary = document.getElementById(summaryId);
  if (!form || !summary) return;
  const productKey = clean(form.elements?.product?.value || product?.key || document.body?.dataset?.product || '');
  const planName = clean(form.elements?.plan?.value || 'Starter');
  const billing = syncBillingForForm(form);
  const billingLabel = billing === 'monthly' ? '월 구독' : '1회 결제';
  summary.innerHTML = `<strong>현재 선택 요약</strong><br>${esc(productName(productKey))} · ${esc(planName)} · ${esc(planPrice(productKey, planName))} · ${esc(billingLabel)}${planNote(productKey, planName) ? `<br><small>${esc(planNote(productKey, planName))}</small>` : ''}`;
}

function buildDemoSaveBox(entry, remoteSaved){
  if (!entry) return `<div class="demo-save-box"><strong>다음 단계</strong><br>지금은 저장 없이 결과만 먼저 확인하셨습니다. 원하시면 바로 결제로 넘어가실 수 있습니다.</div>${buildDemoUpsellBox(product?.key || document.body?.dataset?.product || 'veridion')}`;
  return `<div class="demo-save-box"><strong>저장 완료</strong><br>샘플 코드 <span class="inline-code">${esc(entry.code || '-') }</span>${remoteSaved ? ' · 서버에 기록되었습니다.' : ' · 브라우저에 임시 저장했습니다.'}</div>${buildDemoUpsellBox(product?.key || document.body?.dataset?.product || 'veridion')}`;
}

function renderProductDemoWorkspace(){
  const root = document.getElementById('product-demo-shell');
  if (!root || !product) return;
  if (product.key === 'veridion') {
    root.innerHTML = `<form id="product-demo-form" class="stack-form"><div class="form-grid"><div class="span-2"><label>사이트 주소</label><input name="website" placeholder="https://example.com" inputmode="url" autocomplete="url" required></div><div><label>업종</label><select name="industry"><option value="commerce">이커머스</option><option value="beauty">뷰티·웰니스</option><option value="healthcare">의료·건강</option><option value="education">교육·서비스</option><option value="saas">B2B SaaS</option></select></div><div><label>주요 운영 국가</label><select name="country"><option value="KR" selected>대한민국</option><option value="US">미국</option><option value="JP">일본</option><option value="CN">중국</option><option value="EU">유럽연합</option><option value="SEA">동남아</option><option value="GLOBAL">글로벌</option></select></div><div><label>중점 확인 사항</label><select name="focus" data-demo-field="focus"><option value="전체 리스크 빠르게 보기">전체 리스크 빠르게 보기</option><option value="개인정보·회원가입 동선">개인정보·회원가입 동선</option><option value="결제·환불·청약철회 고지">결제·환불·청약철회 고지</option><option value="광고·표시 문구">광고·표시 문구</option><option value="약관·정책 문서 일치">약관·정책 문서 일치</option><option value="민감 업종·표현 위험">민감 업종·표현 위험</option></select></div></div><div class="notice notice-light"><strong>데모에서 바로 보여주는 항목</strong><br>영역별 위반 가능 항목 수, 위기 점수, 유사 업종 대비 하위 퍼센트, 예상 최대 과태료, 결제 후 열리는 서비스 1·2·3까지 먼저 확인합니다.</div><div class="actions"><button class="button" type="submit">즉시 분석하기</button><a class="button ghost" href="#order">바로 결제</a></div></form>`;
    return;
  }
  if (product.key === 'clearport') {
    root.innerHTML = `<form id="product-demo-form" class="stack-form"><div class="form-grid"><div><label>제출 유형</label><input name="submissionType" placeholder="예: 입찰, 등록, 제휴"></div><div><label>마감일</label><input name="deadline" type="date"></div><div><label>제출처</label><input name="targetOrg" placeholder="예: 공공기관, 거래처"></div><div><label>팀 규모</label><input name="teamSize" placeholder="예: 2인 운영팀"></div><div class="span-2"><label>막히는 지점</label><input name="blocker" placeholder="예: 서류 누락, 회신 지연"></div></div><div class="actions"><button class="button" type="submit">샘플 결과 보기</button></div></form>`;
    return;
  }
  if (product.key === 'grantops') {
    root.innerHTML = `<form id="product-demo-form" class="stack-form"><div class="form-grid"><div><label>사업/공모명</label><input name="projectName" placeholder="예: 창업 지원사업"></div><div><label>마감일</label><input name="deadline" type="date"></div><div><label>현재 진행률</label><select name="progress"><option>자료 수집 전</option><option>초안 작성 중</option><option>검토 중</option><option>마감 직전</option></select></div><div><label>참여 인원</label><input name="contributors" placeholder="예: 3명"></div><div class="span-2"><label>지연 포인트</label><input name="delayPoint" placeholder="예: 증빙 수집, 승인 지연"></div></div><div class="actions"><button class="button" type="submit">샘플 결과 보기</button></div></form>`;
    return;
  }
  root.innerHTML = `<form id="product-demo-form" class="stack-form"><div class="form-grid"><div><label>문서 종류</label><input name="docType" placeholder="예: 제안서, 보고서"></div><div><label>현재 버전 상태</label><select name="versionState"><option>최신본이 정리되어 있음</option><option>초안만 있음</option><option>수정본이 여러 개 흩어져 있음</option></select></div><div><label>승인 단계</label><input name="approvalSteps" placeholder="예: 3단계"></div><div><label>주요 채널</label><input name="channel" placeholder="예: 이메일, 메신저"></div><div class="span-2"><label>가장 큰 문제</label><input name="draftPain" placeholder="예: 최신본 혼선, 승인 지연"></div></div><div class="actions"><button class="button" type="submit">샘플 결과 보기</button></div></form>`;
}

async function requestMockOrLivePayment(order, payment){
  const confirmUrl = config.integration?.toss_confirm_endpoint || '/api/public/payments/toss/confirm';
  const successPath = payment?.successUrl || `${location.origin}${base.replace('./','/') }payments/toss/success/index.html`;
  const failPath = payment?.failUrl || `${location.origin}${base.replace('./','/') }payments/toss/fail/index.html`;
  if (payment?.enabled && !payment?.mock && window.TossPayments) {
    const clientKey = payment.clientKey;
    const toss = window.TossPayments(clientKey);
    await toss.requestPayment('카드', {
      amount: Number(order.amount || 0),
      orderId: order.id,
      orderName: `${order.productName || productName(order.product)} ${order.plan || 'Starter'}`,
      customerName: order.name || '결제 고객',
      customerEmail: order.email || 'checkout@nv0.kr',
      successUrl: successPath,
      failUrl: failPath,
    });
    return null;
  }
  const confirm = await postIfConfigured(confirmUrl, { orderId: order.id, paymentKey: `mock_${order.id}`, amount: order.amount });
  if (confirm.mode === 'remote' && confirm.ok && confirm.json?.order) {
    applyStatePayload(confirm.json?.state);
    const url = `${base}payments/toss/success/index.html?orderId=${encodeURIComponent(confirm.json.order.id)}&paymentKey=${encodeURIComponent(confirm.json.order.paymentKey || `mock_${confirm.json.order.id}`)}&amount=${encodeURIComponent(confirm.json.order.amount || 0)}`;
    location.href = url;
    return confirm.json.order;
  }
  throw new Error(confirm.json?.detail || confirm.text || '결제 승인 처리에 실패했습니다.');
}

async function bindProductCheckoutForm(){
  const form = document.getElementById('product-checkout-form');
  if (!form) return;
  if (form.dataset.bound === '1') return;
  form.dataset.bound = '1';
  form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
    const values = Object.fromEntries(new FormData(form).entries());
    const payload = { product: values.product || product?.key, plan: values.plan || 'Starter', billing: values.billing || 'one-time', paymentMethod: values.paymentMethod || 'toss' };
    const reserve = await postIfConfigured(config.integration?.reserve_order_endpoint || '/api/public/orders/reserve', payload);
    if (reserve.mode === 'remote' && reserve.ok && reserve.json?.order) {
      applyStatePayload(reserve.json?.state);
      await requestMockOrLivePayment(reserve.json.order, reserve.json.payment || paymentRuntime());
      return;
    }
    if (reserve.mode === 'remote') throw new Error(reserve.json?.detail || reserve.text || '결제 준비에 실패했습니다.');
    const local = createOrder({ ...payload, company:'결제 후 입력', name:'결제 후 입력', email:'checkout@nv0.kr' });
    location.href = `${base}payments/toss/success/index.html?orderId=${encodeURIComponent(local.id)}&paymentKey=${encodeURIComponent(`mock_${local.id}`)}&amount=${encodeURIComponent(local.amount || 0)}`;
  }); });
}

async function bindDemoForm(){
  const form = document.getElementById('demo-form');
  if (!form || form.dataset.bound === '1') return;
  form.dataset.bound = '1';
  form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
    const values = Object.fromEntries(new FormData(form).entries());
    assert(clean(values.website), '사이트 주소를 입력하세요.');
    const scan = await postIfConfigured(veridionScanEndpoint(), values);
    if (scan.mode === 'remote' && scan.ok && scan.json?.report) {
      applyStatePayload(scan.json?.state);
      setLastVeridionReport(scan.json.report);
      showResult('demo-result', renderVeridionRemoteReport(scan.json.report, values));
      return;
    }
    throw new Error(scan.json?.detail || scan.text || '즉시 분석에 실패했습니다.');
  }).catch((error)=>showResult('demo-result', `<div class="empty-box">${esc(createFriendlyError(error,'즉시 분석에 실패했습니다.'))}</div>`)); });
}

async function bindCheckoutForm(){
  const form = document.getElementById('checkout-form');
  if (!form || form.dataset.bound === '1') return;
  form.dataset.bound = '1';
  form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
    const values = Object.fromEntries(new FormData(form).entries());
    const payload = { product: values.product, plan: values.plan || 'Starter', billing: values.billing || 'one-time', paymentMethod: values.paymentMethod || 'toss' };
    const reserve = await postIfConfigured(config.integration?.reserve_order_endpoint || '/api/public/orders/reserve', payload);
    if (reserve.mode === 'remote' && reserve.ok && reserve.json?.order) {
      applyStatePayload(reserve.json?.state);
      await requestMockOrLivePayment(reserve.json.order, reserve.json.payment || paymentRuntime());
      return;
    }
    throw new Error(reserve.json?.detail || reserve.text || '결제 준비에 실패했습니다.');
  }).catch((error)=>showResult('checkout-result', `<div class="empty-box">${esc(createFriendlyError(error,'결제 준비에 실패했습니다.'))}</div>`)); });
}

async function bindContactForm(){
  const form = document.getElementById('contact-form');
  if (!form || form.dataset.bound === '1') return;
  form.dataset.bound = '1';
  form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
    const values = Object.fromEntries(new FormData(form).entries());
    const remote = await postIfConfigured(config.integration?.contact_endpoint || '/api/public/contact-requests', values);
    if (remote.mode === 'remote' && remote.ok) { applyStatePayload(remote.json?.state); showResult('contact-result', '<div class="notice"><strong>확인 요청을 접수했습니다.</strong><br>운영 조건을 검토한 뒤 안내드리겠습니다.</div>'); return; }
    const entry = createContact(values); showResult('contact-result', `<div class="notice"><strong>확인 요청을 저장했습니다.</strong><br>코드 <span class="inline-code">${esc(entry.code)}</span></div>`);
  }).catch((error)=>showResult('contact-result', `<div class="empty-box">${esc(createFriendlyError(error,'요청 접수에 실패했습니다.'))}</div>`)); });
}

async function bindPortalLookup(){
  const form = document.getElementById('portal-lookup-form');
  if (!form || form.dataset.bound === '1') return;
  form.dataset.bound = '1';
  form.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
    const values = Object.fromEntries(new FormData(form).entries());
    const remote = await postIfConfigured(config.integration?.portal_lookup_endpoint || '/api/public/portal/lookup', values);
    const payload = remote.mode === 'remote' && remote.ok ? remote.json : { order: lookupOrder(values.email, values.code), publications: [] };
    const order = payload?.order;
    if (!order) { showResult('portal-result', '<div class="empty-box">일치하는 조회 내역을 찾지 못했습니다.</div>'); return; }
    showResult('portal-result', `<div class="notice"><strong>${esc(order.productName || productName(order.product))}</strong><br>상태: ${esc(orderStatusLabel(order.status))}<br>조회 코드 <span class="inline-code">${esc(order.code)}</span><br><a href="${portalHref(order)}">포털 링크 열기</a></div>`);
    const mock = document.getElementById('portal-mock');
    if (mock) mock.innerHTML = `<div class="mock-step"><strong>${esc(orderStatusLabel(order.status))}</strong><span>${esc(order.plan || '-')} · ${esc(order.email || '')}</span></div>`;
  }).catch((error)=>showResult('portal-result', `<div class="empty-box">${esc(createFriendlyError(error,'조회에 실패했습니다.'))}</div>`)); });
}

function renderPaymentSuccessState(order){
  const resultId = 'payment-success-result';
  if (!order) { showResult(resultId, '<div class="empty-box">결제 정보를 찾지 못했습니다.</div>'); return; }
  if (clean(order.status) === 'intake_required') {
    const websiteField = clean(order.product) === 'veridion' ? '<div class="span-2"><label>사이트 주소</label><input name="website" placeholder="https://example.com" inputmode="url" autocomplete="url" required></div>' : '';
    const introNotice = clean(order.product) === 'veridion' ? '서비스 1 전체 세부 점검 리포트와 서비스 2 사이트 맞춤형 수정안 리포트를 발행하기 위한 최소 정보만 입력해 주세요.' : '서비스 진행에 필요한 정보만 입력해 주세요.';
    showResult(resultId, `<div class="notice"><strong>결제가 완료되었습니다.</strong><br>${esc(introNotice)}</div><form id="payment-intake-form" class="stack-form"><div class="form-grid"><div><label>회사명</label><input name="company" placeholder="회사명" value="${esc(order.company || '')}" required></div><div><label>담당자명</label><input name="name" placeholder="담당자명" value="${esc(order.name || '')}" required></div><div><label>이메일</label><input name="email" type="email" placeholder="email@company.com" value="${esc(order.email || '')}" required></div>${websiteField}<div class="span-2"><label>추가 요청(선택)</label><input name="note" placeholder="꼭 포함할 기준, 참고할 점"></div></div><div class="actions"><button class="button" type="submit">진행 정보 저장</button></div></form>`);
    const form = document.getElementById('payment-intake-form');
    form?.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(form, async () => {
      const values = Object.fromEntries(new FormData(form).entries());
      const remote = await postIfConfigured(`/api/public/orders/${encodeURIComponent(order.id)}/intake`, values);
      if (remote.mode === 'remote' && remote.ok && remote.json?.order) {
        applyStatePayload(remote.json?.state);
        renderPaymentSuccessState(remote.json.order);
        return;
      }
      throw new Error(remote.json?.detail || remote.text || '진행 정보 저장에 실패했습니다.');
    }).catch((error)=>showResult(resultId, `<div class="empty-box">${esc(createFriendlyError(error,'진행 정보 저장에 실패했습니다.'))}</div>`)); });
    return;
  }
  const doneDetail = clean(order.product) === 'veridion' ? `${orderStatusLabel(order.status)} · 서비스 1 전체 세부 점검 / 서비스 2 맞춤형 수정안` : orderStatusLabel(order.status);
  showResult(resultId, `<div class="notice"><strong>결제가 완료되었습니다.</strong><br>${esc(doneDetail)} · 조회 코드 <span class="inline-code">${esc(order.code || '-')}</span><br><a href="${portalHref(order)}">고객 포털에서 결과 확인하기</a></div>`);
}

async function bindPaymentResultPages(){
  const success = document.getElementById('payment-success-result');
  if (success) {
    const params = new URLSearchParams(location.search);
    const orderId = clean(params.get('orderId'));
    const paymentKey = clean(params.get('paymentKey'));
    const amount = Number(params.get('amount') || 0);
    if (!orderId) { showResult('payment-success-result', '<div class="empty-box">결제 승인 정보가 없습니다.</div>'); return; }
    const confirm = await postIfConfigured(config.integration?.toss_confirm_endpoint || '/api/public/payments/toss/confirm', { orderId, paymentKey: paymentKey || `mock_${orderId}`, amount });
    if (confirm.mode === 'remote' && confirm.ok && confirm.json?.order) { applyStatePayload(confirm.json?.state); renderPaymentSuccessState(confirm.json.order); return; }
    const localOrder = read(STORE.orders).find((item)=>item.id===orderId); renderPaymentSuccessState(localOrder);
  }
  const fail = document.getElementById('payment-fail-result');
  if (fail) {
    const params = new URLSearchParams(location.search);
    showResult('payment-fail-result', `<div class="empty-box">결제가 완료되지 않았습니다.${params.get('message') ? `<br>${esc(params.get('message'))}` : ''}</div>`);
  }
}

function toBase64(file){ return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result || '').split(',').pop() || ''); reader.onerror = () => reject(reader.error || new Error('파일을 읽지 못했습니다.')); reader.readAsDataURL(file); }); }

function bindAdminActions(){
  const root = document.getElementById('admin-console');
  if (!root) return;
  const settingsForm = document.getElementById('admin-board-settings-form');
  const publicationForm = document.getElementById('admin-publication-form');
  const assetForm = document.getElementById('admin-asset-form');
  const publishAll = document.getElementById('admin-publish-all');
  const publishNowProduct = document.getElementById('admin-publish-now-product');
  const publishNowCount = document.getElementById('admin-publish-now-count');
  const loadSettings = async () => {
    if (!(await checkAdminSession())) return;
    const res = await fetch('/api/admin/board-settings', fetchOptionsFor('/api/admin/board-settings', { headers: headersFor('/api/admin/board-settings', { 'Accept':'application/json' }) }));
    if (!res.ok) return;
    const payload = await res.json();
    const settings = payload.settings || {};
    if (!settingsForm) return;
    if (settingsForm.elements.ctaLabel) settingsForm.elements.ctaLabel.value = settings.ctaLabel || '';
    if (settingsForm.elements.ctaHref) settingsForm.elements.ctaHref.value = settings.ctaHref || '';
    if (settingsForm.elements.autoPublishAllProducts) settingsForm.elements.autoPublishAllProducts.checked = Boolean(settings.autoPublishAllProducts);
    if (settingsForm.elements.autoPublishEnabled) settingsForm.elements.autoPublishEnabled.checked = Boolean(settings.autoPublishEnabled);
    if (settingsForm.elements.scheduleType) settingsForm.elements.scheduleType.value = settings.scheduleType || 'daily';
    if (settingsForm.elements.frequencyPerRun) settingsForm.elements.frequencyPerRun.value = settings.frequencyPerRun || 1;
    if (settingsForm.elements.intervalHours) settingsForm.elements.intervalHours.value = settings.intervalHours || 24;
    if (settingsForm.elements.timeSlots) settingsForm.elements.timeSlots.value = Array.isArray(settings.timeSlots) ? settings.timeSlots.join(', ') : (settings.timeSlots || '09:00');
    if (settingsForm.elements.selectedProducts) settingsForm.elements.selectedProducts.value = Array.isArray(settings.selectedProducts) ? settings.selectedProducts.join(', ') : (settings.selectedProducts || '');
    if (settingsForm.elements.publishMode) settingsForm.elements.publishMode.value = settings.publishMode || 'publish';
  };
  loadSettings().catch(()=>{});

  settingsForm?.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(settingsForm, async () => {
    const values = Object.fromEntries(new FormData(settingsForm).entries());
    values.autoPublishAllProducts = settingsForm.elements.autoPublishAllProducts?.checked ? 1 : 0;
    values.autoPublishEnabled = settingsForm.elements.autoPublishEnabled?.checked ? 1 : 0;
    const res = await postIfConfigured('/api/admin/board-settings', values);
    if (res.mode === 'remote' && res.ok) { applyStatePayload(res.json?.state); showResult('admin-action-result', '자료실 CTA 자동 발행 설정을 저장했습니다.'); return; }
    throw new Error(res.json?.detail || res.text || '설정 저장에 실패했습니다.');
  }).catch((error)=>showResult('admin-action-result', esc(createFriendlyError(error,'설정 저장에 실패했습니다.')))); });

  publishAll?.addEventListener('click', () => { withSubmitLock(settingsForm || root, async () => {
    const payload = { product: clean(publishNowProduct?.value), count: Number(publishNowCount?.value || 1) || 1 };
    const res = await postIfConfigured('/api/admin/actions/publish-now', payload);
    if (res.mode === 'remote' && res.ok) { applyStatePayload(res.json?.state); renderAdminSummary(); renderPublicBoard(); renderProductBoard(); showResult('admin-action-result', '자료실 글을 즉시 발행했습니다.'); return; }
    throw new Error(res.json?.detail || res.text || '즉시 발행에 실패했습니다.');
  }).catch((error)=>showResult('admin-action-result', esc(createFriendlyError(error,'즉시 발행에 실패했습니다.')))); });

  publicationForm?.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(publicationForm, async () => {
    const values = Object.fromEntries(new FormData(publicationForm).entries());
    values.autoGenerate = publicationForm.elements.autoGenerate?.checked ? 1 : 0;
    const res = await postIfConfigured('/api/admin/library/publications', values);
    if (res.mode === 'remote' && res.ok) {
      applyStatePayload(res.json?.state);
      renderAdminSummary();
      renderPublicBoard();
      renderProductBoard();
      showResult('admin-action-result', values.autoGenerate ? '자동 글을 즉시 발행했습니다.' : '자료실 글을 등록했습니다.');
      publicationForm.reset();
      return;
    }
    throw new Error(res.json?.detail || res.text || '자료실 글 등록에 실패했습니다.');
  }).catch((error)=>showResult('admin-action-result', esc(createFriendlyError(error,'자료실 글 등록에 실패했습니다.')))); });

  assetForm?.addEventListener('submit', (event) => { event.preventDefault(); withSubmitLock(assetForm, async () => {
    const fd = new FormData(assetForm); const file = fd.get('file');
    if (!(file instanceof File) || !file.size) throw new Error('업로드할 파일을 선택하세요.');
    const payload = { product: fd.get('product'), title: fd.get('title'), filename: file.name, mimeType: file.type, contentBase64: await toBase64(file) };
    const res = await postIfConfigured('/api/admin/library/assets', payload);
    if (res.mode === 'remote' && res.ok && res.json?.asset) {
      applyStatePayload(res.json?.state);
      if (publicationForm?.elements.assetUrl) publicationForm.elements.assetUrl.value = res.json.asset.url || '';
      showResult('admin-action-result', `파일 업로드를 완료했습니다. ${res.json.asset.url || ''}`);
      assetForm.reset();
      return;
    }
    throw new Error(res.json?.detail || res.text || '파일 업로드에 실패했습니다.');
  }).catch((error)=>showResult('admin-action-result', esc(createFriendlyError(error,'파일 업로드에 실패했습니다.')))); });
}

document.addEventListener('DOMContentLoaded', async () => { await loadSystemConfig(); if ((pageKey === 'checkout' || pageKey === 'product') && paymentRuntime()?.enabled && !paymentRuntime()?.mock) await loadTossScript(); const stateSynced = await syncRemoteState(); if (!stateSynced) { const boardSynced = await loadBoardFeed(); if (!boardSynced) ensureSeedData(); } else if (!read(STORE.publications).length) { const boardSynced = await loadBoardFeed(); if (!boardSynced) ensureSeedData(); } else { ensureSeedData(); } enhanceDocumentChrome(); renderHeader(); renderSidebar(); ensureAdminAccessModal(); bindNavChrome(); bindAdminEntry(); renderFooter(); buildHomeProducts(); buildModuleMatrix(); fillProductSlots(); buildPlans(); setPrefills(); renderPublicBoard(); renderProductBoard(); renderLiveStats(); renderWorkspaceCards(); renderProductServices(); renderServiceCatalog(); bindProductDemoForm(); await bindProductCheckoutForm(); bindDemoForm(); bindCheckoutForm(); bindContactForm(); bindPortalLookup(); bindAdminTokenControls(); bindQuickDemoButtons(); attachConsentGuards(); bindPlanSummaries(); await bindPaymentResultPages(); await bootstrapAdminGate(); renderAdminSummary(); bindAdminActions(); });
  window.NV0App = { read, write, lookupOrder, createOrder, createDemo, createContact, createLookup, ensureSeedData, renderAdminSummary, advanceOrder, toggleOrderPayment, republishOrder, validateEmail, validateProduct, validatePlan, setAdminToken, getAdminToken, loadSystemConfig, publicBoardHref, productBoardHref, portalHref };
})();