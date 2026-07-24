/* ================================================================
   aistocks.tech — single-page app  v3
   Router + page renderers + data fetching + chatbot
   ================================================================ */

const STATE = { funds: null, news: null, signals: null, reports: null,
                meta: { paypalEmail: 'lvl13cs@gmail.com' } };
const CHARTS = {};
let SIGNALS_FILTER = 'ALL';
let SECTOR_FILTER = 'ALL';
let PICKED_TICKERS = [];

const fmt$  = n => { const v = n||0; return (v<0?'-$':'$') + Math.abs(v).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}); };
const fmt$0 = n => { const v = Math.round(n||0); return (v<0?'-$':'$') + Math.abs(v).toLocaleString(); };
const fmtPct = n => (n>=0?'+':'') + (n||0).toFixed(2) + '%';
const cls   = n => n>=0 ? 'pos' : 'neg';
const $     = id => document.getElementById(id);

const FUND_META = {
  // (2026-07-09 restyle) bot13's series color is the BRAND GREEN — never pink (BOT13_DESIGN_SPEC).
  bot13:     { name:'BOT13',     icon:'13', color:'#57ffb0', kind:'DAILY',
               tagline:"Daily intraday bot. Buys at open, sells before close. Skips the day if no edge." },
  oracle:    { name:'ORACLE',    icon:'OR', color:'#a855f7', kind:'WEEKLY',
               tagline:"Weekly bot. Trades every Monday. All-in on the week's best bets." },
  wizard:    { name:'WIZARD',    icon:'WZ', color:'#10b981', kind:'MONTHLY',
               tagline:"Monthly hold bot. Buys the 1st trading day, sells the last. Slow and patient." },
  equalizer: { name:'EQUALIZER', icon:'EQ', color:'#00d4ff', kind:'BASELINE',
               tagline:"Equal weight. No favorites. $1,000 in every stock." },
  titan:     { name:'TITAN',     icon:'TT', color:'#ff8c00', kind:'BASELINE',
               tagline:"Half on the heavyweights. Half on the rest. Concentration meets coverage." },
};
const FUND_ORDER = ['bot13','oracle','wizard','equalizer','titan'];

// ============ DATA LOADING ============
const TRACKER_API = 'https://wallstbots-backend-868128114349.us-east1.run.app/public/tracker';
const API_BASE    = 'https://wallstbots-backend-868128114349.us-east1.run.app';
const REPORT_PLATFORM = 'aistocks';   // this site's platform (per-site branding value)
const REPORT_BRAND    = 'AI Stocks';

// ============ AUTH HELPERS ============
const JWT_KEY = 'aistocks_jwt';
function getJWT()       { try { return localStorage.getItem(JWT_KEY); } catch(e) { return null; } }
function setJWT(token)  { try { localStorage.setItem(JWT_KEY, token); } catch(e) {} }
function clearJWT()     { try { localStorage.removeItem(JWT_KEY); } catch(e) {} }
function isLoggedIn()   { return !!getJWT(); }
function authHeaders()  { return { 'Authorization': 'Bearer ' + getJWT(), 'Content-Type': 'application/json' }; }

async function apiFetch(path, opts) {
  const r = await fetch(API_BASE + path, opts || {});
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || j.message || ('HTTP ' + r.status));
  return j;
}

function fetchWithTimeout(url, opts = {}, ms = 8000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  return fetch(url, { ...opts, signal: ctrl.signal }).finally(() => clearTimeout(t));
}

async function loadAll() {
  if (location.protocol === 'file:') { showFileProtocolWarning(); return; }
  try {
    const r = await Promise.allSettled([
      fetchWithTimeout(`${TRACKER_API}/state?platform=aistocks`,   { cache: 'no-store' }).then(r => r.json()).then(r => r.data),
      fetchWithTimeout(`${TRACKER_API}/news?platform=aistocks`,    { cache: 'no-store' }).then(r => r.json()).then(r => r.data),
      fetchWithTimeout(`${TRACKER_API}/signals?platform=aistocks`, { cache: 'no-store' }).then(r => r.json()).then(r => r.data),
      fetchWithTimeout(`${TRACKER_API}/reports?platform=aistocks`, { cache: 'no-store' }).then(r => r.json()).then(r => r.data),
    ]);
    STATE.funds   = r[0].status === 'fulfilled' ? r[0].value : null;
    STATE.news    = r[1].status === 'fulfilled' ? r[1].value : { items: [] };
    STATE.signals = r[2].status === 'fulfilled' ? r[2].value : { recommendations: [], summary:{} };
    STATE.reports = r[3].status === 'fulfilled' ? r[3].value : { reports: [] };
    if (!r.some(x => x.status === 'fulfilled')) { showDataLoadError('All four data files failed to load.'); return; }
  } catch (e) { console.error(e); showDataLoadError(e && e.message); return; }
  try { route(); } catch (e) {
    console.error('Render error', e);
    const a = $('app');
    if (a) a.innerHTML = '<div class="hero" style="border-color:var(--red)"><h1 style="color:var(--red)">Render error</h1><p>'+escapeHtml(e.message)+'</p></div>';
  }
}

function showFileProtocolWarning() {
  $('app').innerHTML = '<div class="hero" style="border-color:var(--orange)"><h1 style="color:var(--orange)">Open this site over HTTP, not file://</h1><p>Double-click <code>PREVIEW_SITE.bat</code> in the project folder.</p></div>';
}
function showDataLoadError(detail) {
  $('app').innerHTML = '<div class="hero" style="border-color:var(--red)"><h1 style="color:var(--red)">Couldn\'t load site data</h1>'+(detail?'<p style="color:var(--muted);font-family:monospace">'+escapeHtml(detail)+'</p>':'')+'<p>Try a hard refresh (Ctrl+F5).</p></div>';
}

// ============ ROUTING ============
function route() {
  // Strip any ?query from the hash BEFORE matching routes: invite/referral links
  // are shaped #/get-yours?ref=CODE, and matching the full string sent every
  // invitee to the homepage instead (2026-07-05 fix). renderGetYours reads the
  // ref from the hash query itself.
  const path = (location.hash.replace(/^#/, '').split('?')[0] || '/');
  // Tracker-proof invite links arrive as /?ref=CODE with NO #fragment (email
  // click-tracking redirects strip fragments). Route them to Get Yours --
  // renderGetYours reads the ref straight from location.search (2026-07-06 fix).
  if ((path === '/' || path === '') && new URLSearchParams(location.search).get('ref')) {
    setActiveNav(path); closeMenu();
    window.scrollTo({ top: 0, behavior: 'instant' });
    return renderGetYours();
  }
  setActiveNav(path); closeMenu();
  window.scrollTo({ top: 0, behavior: 'instant' });
  try { renderPageHero(path); } catch (e) { console.error('hero render', e); }
  // Auth route fall-throughs — mirror bitbot13/wallstbots
  if (path === '/login')  { window.location.href = '/login.html'; return; }
  if (path === '/signup') { window.location.href = '/login.html#signup'; return; }
  if (path === '/dashboard') { window.location.href = '/dashboard.html'; return; }
  if (path === '/' || path === '')           return renderHome();
  if (path === '/how')                       return renderHowItWorks();
  if (path === '/race')                      return renderRace();
  if (path.startsWith('/fund/'))             return renderFund(path.split('/')[2]);
  if (path === '/signals')                   return renderSignals();
  if (path === '/news-all' || path === '/news') return renderNewsAll();
  if (path === '/reports')                   return renderReports();
  if (path.startsWith('/report/'))           return renderReport(path.split('/')[2]);
  if (path === '/get-yours')                 return renderGetYours();
  if (path === '/customize')                 return renderCustomize();
  if (path === '/thanks')                    return renderThanks();
  if (path === '/thanks-admin')              return renderThanksAdmin();
  if (path === '/setup')                     return renderSetup();
  if (path === '/my-tracker')                return renderMyTracker();
  if (path === '/my-picks')                  return renderMyPicks();
  renderHome();
}
function setActiveNav(path) {
  document.querySelectorAll('.site-nav a').forEach(a => {
    const r = a.getAttribute('data-route');
    a.classList.toggle('active', r === path || (r === '/' && path === '/'));
  });
}
function toggleMenu() { const n=$('siteNav'); if(n) n.classList.toggle('open'); }
function closeMenu()  { const n=$('siteNav'); if(n) n.classList.remove('open'); }

// ============ HELPERS ============
function escapeHtml(s) {
  return String(s||'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function relTime(iso) {
  if (!iso) return '';
  // Backend timestamps (e.g. "2026-06-15T20:32:15") are UTC but often lack a
  // timezone marker. JS would otherwise parse them as LOCAL time, which makes
  // them look hours in the future (showing "-226m ago"). If there's no timezone
  // suffix (Z or +/-hh:mm), treat the value as UTC by appending "Z".
  let s = String(iso).trim();
  if (/\d{2}:\d{2}/.test(s) && !/(Z|[+-]\d{2}:?\d{2})$/.test(s)) s = s.replace(' ', 'T') + 'Z';
  const t = new Date(s); if (isNaN(t)) return iso;
  let m = Math.round((Date.now() - t) / 60000);
  if (m < 0) m = 0;                       // guard tiny clock skew → never negative
  if (m < 60)      return m + 'm ago';
  if (m < 1440)    return Math.round(m/60) + 'h ago';
  if (m < 10080)   return Math.round(m/1440) + 'd ago';
  return t.toLocaleDateString();
}
function sectorClass(s) {
  if (!s) return 'other';
  const v = s.toLowerCase();
  if (v.includes('ai') || v.includes('quantum')) return 'aiq';
  if (v.includes('bio') || v.includes('health')) return 'bio';
  if (v.includes('energy') || v.includes('oil')) return 'energy';
  if (v.includes('defense') || v.includes('military')) return 'defense';
  if (v.includes('finance') || v.includes('bank')) return 'finance';
  if (v.includes('tech')) return 'tech';
  return 'other';
}
function isAIQ(item) {
  const s = (item.sector || '').toLowerCase();
  return s.includes('ai') || s.includes('quantum');
}
function getYoursHint(msg) {
  // (2026-07-09 restyle) JOIN STRIP per BOT13_DESIGN_SPEC §7: every public page, above the footer.
  msg = msg || '3-day free trial — see every live trade before you pay a dime.';
  return '<div class="join-strip"><p>' + msg
    + ' <a class="btn btn-primary" href="#/get-yours">Join Now</a></p></div>';
}

/* ============ PAGE HERO + TICKER (BOT13 design language, 2026-07-09) ============
   Renders into the #pageHero slot ABOVE #app. Homepage + bot13 page get the VIDEO
   hero; every other page gets the static banner. Artwork's robot occupies the LEFT
   half of every banner — text sits on the RIGHT ONLY (owner rule). The ticker under
   the hero scrolls LEFT -> RIGHT and shows the 5 bots' day %, best -> worst, from
   the state the page already loaded (display-only — no extra data fetches). */
function heroCopy(path) {
  if (path === '/' || path === '') return {
    title: 'FIVE BOTS. ONE RACE.',
    sub: '<strong>BOT13</strong> only trades when it sees a real edge — no edge, no trade, no risk.',
    cta: '<a class="btn btn-primary btn-lg" href="#/get-yours">Join Now</a> <a class="btn btn-secondary" href="#/race">See The Race</a>'
  };
  if (path.startsWith('/fund/bot13')) return {
    title: 'BOT13 — THE ONE TO WATCH',
    sub: 'Daily bot. Buys the edge at the open, banks it before close.',
    cta: '<a class="btn btn-primary" href="#/get-yours">Run It On Your Stocks</a>'
  };
  // Every other page: the PAGE NAME on the RIGHT side of the banner (owner rule —
  // the artwork's robot owns the left; text only ever sits right).
  const names = {
    '/news-all': 'NEWS', '/news': 'NEWS', '/how': 'HOW IT WORKS', '/race': 'THE RACE',
    '/signals': 'SIGNALS', '/reports': 'REPORTS', '/get-yours': 'GET YOURS',
    '/referral': 'REFER & EARN', '/thanks': 'WELCOME ABOARD', '/thanks-admin': 'WELCOME ABOARD'
  };
  let title = names[path];
  if (!title && path.startsWith('/fund/'))   title = (FUND_META[path.split('/')[2]] || {}).name || 'THE RACE';
  if (!title && path.startsWith('/report/')) title = 'MONTHLY REPORT';
  if (!title) title = '';
  return { title: title, sub: '', cta: '' };
}
function tickerRail() {
  const f = (STATE.funds && STATE.funds.funds) || {};
  const rows = FUND_ORDER
    .map(fid => ({ fid, meta: FUND_META[fid], v: (f[fid] && f[fid].value) || null }))
    .filter(r => r.v && r.v.day_pct != null)
    .sort((a, b) => (b.v.day_pct || 0) - (a.v.day_pct || 0));
  if (!rows.length) return '';
  const cells = rows.map(r =>
    '<span class="tick-item"><span class="sym">' + r.meta.name + '</span>'
    + '<span class="cat">' + r.meta.kind + '</span>'
    + '<span class="' + ((r.v.day_pct || 0) >= 0 ? 'pos' : 'neg') + '">' + fmtPct(r.v.day_pct) + '</span></span>'
  ).join('');
  // rail doubled so translateX(0) -> -50% loops seamlessly — classic ticker: text
  // enters from the RIGHT edge and continuously shifts LEFT (owner spec).
  return '<div class="ticker-wrap"><div class="ticker">' + cells + cells + '</div></div>';
}
function renderPageHero(path) {
  const slot = $('pageHero');
  if (!slot) return;
  const isVideo = (path === '/' || path === '' || path.startsWith('/fund/bot13'));
  const copy = heroCopy(path);
  // Platform tagline on EVERY hero banner (owner rule — matches bot13.tech's hero-sub)
  const tag = '<p class="hero13-tag">The Wall St. Bots Platform</p>';
  const overlay = (copy && copy.title)
    ? '<div class="hero13-overlay"><h1 class="hero13-title">' + copy.title + '</h1>'
      + (copy.sub ? '<p class="hero13-sub">' + copy.sub + '</p>' : '')
      + tag /* tagline sits ABOVE any buttons (owner rule 2026-07-09) */
      + (copy.cta ? '<div class="hero13-ctas">' + copy.cta + '</div>' : '')
      + '</div>'
    : '<div class="hero13-overlay">' + tag + '</div>';
  const media = isVideo
    ? '<video autoplay muted loop playsinline poster="assets/herobanner.png"><source src="assets/herobanner_vid.mp4" type="video/mp4"></video>'
    : '<img class="hero13-img" src="assets/herobanner.png" alt="">';
  slot.innerHTML = '<div class="hero13">' + media + overlay + '</div>' + tickerRail();
}
function fundCard(fid, data) {
  const meta = FUND_META[fid];
  const v = data && data.value ? data.value : { total: 50000, pnl: 0, pnl_pct: 0, day_pnl: 0, day_pct: 0 };
  return '<a class="card clickable fund-card" href="#/fund/'+fid+'">'
    + '<div class="fund-head"><span class="fund-icon '+fid+'">'+meta.icon+'</span>'
    + '<div style="min-width:0"><div class="fund-name">'+meta.name+'</div><div class="fund-kind" style="color:'+meta.color+'">'+meta.kind+'</div></div></div>'
    + '<div class="fund-tag">'+meta.tagline+'</div>'
    + '<div class="fund-value">'+fmt$0(v.total)+'</div>'
    + '<div class="fund-pnl '+cls(Math.round(v.pnl))+'">'+fmt$0(v.pnl)+' ('+fmtPct(v.pnl_pct)+') since inception</div>'
    + '<div class="stat-row"><span class="stat-label">Today</span>'
    + '<span class="stat-val '+cls(Math.round(v.day_pnl))+'">'+fmtPct(v.day_pct)+'</span></div></a>';
}

function newsCard(it) {
  const cat = sectorClass(it.sector);
  const url = it.url && it.url !== '#' ? it.url : null;
  const open = url ? ' target="_blank" rel="noopener noreferrer"' : '';
  const href = url || 'javascript:void(0)';
  return '<a class="news-card cat-'+cat+'" href="'+escapeHtml(href)+'"'+open+'>'
    + '<div class="news-title">'+escapeHtml(it.title||'')+'</div>'
    + '<div class="news-meta">'+escapeHtml(it.source||it.sector||'Source')+'</div></a>';
}

// ============ PAGE: HOMEPAGE ============
// ============ BOT13 TRACK RECORD (self-updating from snapshots) ============
// Computes BOT13's up/down/cash-day record + worst day straight from the daily
// snapshot history already in STATE. No backend call -- updates itself daily.
function bot13Record() {
  const snaps = (STATE.funds && STATE.funds.snapshots) || [];
  let prev = null, up = 0, down = 0, cash = 0, worst = 0, best = 0, days = 0;
  for (const sn of snaps) {
    const v = (sn && typeof sn.bot13 === 'number') ? sn.bot13 : null;
    if (v === null) continue;
    if (prev !== null && prev > 0) {
      const ch = (v / prev - 1) * 100;
      days++;
      if (ch > 0.05) up++;
      else if (ch < -0.05) down++;
      else cash++;
      if (ch < worst) worst = ch;
      if (ch > best) best = ch;
    }
    prev = v;
  }
  return { up, down, cash, worst, best, days };
}

function bot13RecordTile() {
  const r = bot13Record();
  if (!r.days) {
    // Fewer than 2 days of history (e.g. right after a reset): show a clean
    // "tracking just started" state instead of hiding the whole section.
    return '<div class="panel" style="border-color:var(--pink);background:linear-gradient(135deg,rgba(236,72,153,0.08),rgba(236,72,153,0.01))">'
      + '<div class="section-head" style="margin:0 0 14px">'
      + '<h3 style="color:var(--pink)"><span class="fund-icon bot13" style="width:20px;height:20px;font-size:9px;display:inline-flex;align-items:center;justify-content:center;border-radius:5px;vertical-align:-3px;margin-right:7px;color:var(--bg);font-weight:700">13</span>BOT13 Track Record</h3>'
      + '<span class="more" style="cursor:default;color:var(--muted)">Fresh start</span>'
      + '</div>'
      + '<p style="color:var(--muted);font-size:13px;line-height:1.6;margin:0">'
      + 'BOT13’s track record is building fresh \u2014 up, down, and cash days will appear here as each market day completes. '
      + 'The method never changes: it only trades when it sees a real edge, and holds cash otherwise. No edge, no trade, no risk. '
      + '<a class="more" href="#/get-yours">Run BOT13 on your stocks →</a></p>'
      + '</div>';
  }
  const cell = (num, label, cls) =>
    '<div style="flex:1;min-width:74px;text-align:center;padding:14px 6px;background:var(--panel2);border:1px solid var(--border);border-radius:var(--radius)">'
    + '<div class="stat-val ' + cls + '" style="font-size:28px;line-height:1">' + num + '</div>'
    + '<div class="stat-label" style="margin-top:7px">' + label + '</div>'
    + '</div>';
  const downCls = r.down === 0 ? 'pos' : 'neg';
  const worstCls = r.worst < 0 ? 'neg' : 'pos';
  return '<div class="panel" style="border-color:var(--pink);background:linear-gradient(135deg,rgba(236,72,153,0.08),rgba(236,72,153,0.01))">'
    + '<div class="section-head" style="margin:0 0 14px">'
    + '<h3 style="color:var(--pink)"><span class="fund-icon bot13" style="width:20px;height:20px;font-size:9px;display:inline-flex;align-items:center;justify-content:center;border-radius:5px;vertical-align:-3px;margin-right:7px;color:var(--bg);font-weight:700">13</span>BOT13 Track Record</h3>'
    + '<span class="more" style="cursor:default;color:var(--muted)">Updates every market day</span>'
    + '</div>'
    + '<div style="display:flex;gap:10px;flex-wrap:wrap">'
    + cell(r.up,   'Up days',   'pos')
    + cell(r.down, 'Down days', downCls)
    + cell(r.cash, 'Cash days', '')
    + cell('+' + r.best.toFixed(2) + '%', 'Best day', 'pos')
    + cell(r.worst.toFixed(2) + '%', 'Worst day', worstCls)
    + '</div>'
    + '<p style="color:var(--muted);font-size:13px;line-height:1.6;margin:14px 0 0">'
    + 'BOT13 only trades when it sees a real edge — otherwise it holds cash and risks nothing. '
    + 'No edge, no trade: the downside of a quiet day is a quiet day, not a loss. '
    + 'The record above updates itself every market day. '
    + '<a class="more" href="#/get-yours">Run BOT13 on your stocks →</a></p>'
    + '</div>';
}

function renderHome() {
  // Live leaderboard strip — 5 funds
  const strip = FUND_ORDER.map(fid => {
    const data = STATE.funds && STATE.funds.funds ? STATE.funds.funds[fid] : null;
    const v = data && data.value ? data.value : { day_pct: 0, day_pnl: 0 };
    const m = FUND_META[fid];
    return '<a class="card clickable" href="#/fund/'+fid+'">'
      + '<span class="fund-icon '+fid+'">'+m.icon+'</span>'
      + '<div class="lb-name"><strong>'+m.name+'</strong><small>'+m.kind+'</small></div>'
      + '<div class="lb-pct '+cls(Math.round(v.day_pnl))+'">'+fmtPct(v.day_pct)+'</div></a>';
  }).join('');

  // SIGNALS — TODAY: top picks per category
  const signals = (STATE.signals && STATE.signals.recommendations) || [];
  const summary = (STATE.signals && STATE.signals.summary) || {};
  const topByAction = (action, n) => signals.filter(r => r.action === action).slice(0, n);
  const sigCol = (label, action, color, n) => {
    const items = topByAction(action, n);
    const rows = items.length ? items.map(r =>
      '<div class="row"><strong>'+r.symbol+'</strong>'
      + '<span class="'+(r.upside_pct>=0?'pos':'neg')+'">'+(r.upside_pct!=null?fmtPct(r.upside_pct):'')+'</span></div>'
    ).join('') : '<div class="row" style="color:var(--muted);font-size:11px">None today</div>';
    return '<div class="card">'
      + '<div class="signals-today-head"><span class="signal signal-'+action.toLowerCase().replace(/ /g,'-')+'">'+label+'</span>'
      + '<span style="color:var(--muted);font-size:10px">'+(summary[action]||0)+' total</span></div>'
      + '<div class="signals-today-list">'+rows+'</div></div>';
  };

  // NEWS — TODAY: 5 AI/Quantum stories only
  const news = STATE.news || { items: [] };
  const aiqItems = (news.items || []).filter(isAIQ).slice(0, 5);
  const newsCards = aiqItems.length ? aiqItems.map(newsCard).join('')
    : '<p class="sub">No AI &amp; Quantum headlines yet — the fetcher runs nightly.</p>';

  // RACE — 5 fund cards
  const raceCards = FUND_ORDER.map(fid =>
    fundCard(fid, STATE.funds && STATE.funds.funds ? STATE.funds.funds[fid] : null)).join('');

  // (2026-07-09 restyle) The page hero is now the full-bleed video banner rendered
  // into #pageHero by route() — the old in-app hero section is gone. The page body
  // starts with the intro line + BOT13 record tile.
  $('app').innerHTML =
    '<p class="sub" style="margin-top:6px">Three bots — daily, weekly, monthly — trade head-to-head against two passive benchmarks on 50 hand-picked AI &amp; Quantum stocks. Same money. Same market. Every trade public. <strong style="color:var(--green)">BOT13 only buys when it sees a real edge</strong> and holds cash when it doesn’t. Daily Buy/Sell/Hold signals on every name. Monthly statements you can download.</p>'
    + bot13RecordTile()

    + '<div class="section-head"><h3>Live Leaderboard — Today</h3>'
    + '<a class="more" href="#/race">View all →</a></div>'
    + '<div class="lb-strip">'+strip+'</div>'

    + '<div class="section-head"><h3>Signals — Today</h3>'
    + '<a class="more" href="#/signals">View all signals →</a></div>'
    + '<div class="signals-today">'
    + sigCol('TOP BUYS', 'STRONG BUY', 'green', 4)
    + sigCol('HOLDS',    'HOLD',       'muted', 4)
    + sigCol('TOP SELLS','STRONG SELL','red',   4)
    + '</div>'

    + '<div class="section-head"><h3>News — Today</h3>'
    + '<a class="more" href="#/news-all">More news →</a></div>'
    + '<div class="news-grid">'+newsCards+'</div>'

    + '<div class="section-head"><h3>The Race</h3>'
    + '<a class="more" href="#/race">Full race →</a></div>'
    + '<div class="grid grid-5">'+raceCards+'</div>'

    + '<div class="panel" style="margin-top:18px"><h3>Performance Trajectory — All 5 Strategies</h3>'
    + '<div class="chart-wrap"><canvas id="chartRace"></canvas></div></div>'

+ '<div class="section-head" style="margin-top:36px"><h3>Also from Wall St. Bots</h3></div>'
    + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:18px">'

    + '<div class="card" style="display:flex;flex-direction:column">'
    + '<div style="font-size:10px;font-weight:700;letter-spacing:1px;color:var(--blue);margin-bottom:12px;text-transform:uppercase">Our<br>Wall Street<br>Bots</div>'
    + '<a href="https://wallstbots.tech" target="_blank" rel="noopener">'
    + '<img src="assets/logo-wallstbots.png" alt="Wall St. Bots" style="width:100%;max-width:320px;height:auto;display:block;margin:0 auto 14px;border-radius:8px"></a>'
    + '<p style="color:var(--muted);font-size:13px;line-height:1.6;margin:0 0 14px;flex:1">Five AI bots tracking top stocks across every sector — plus the hottest new IPOs. Daily signals, live leaderboards, and downloadable monthly statements.</p>'
    + '<a class="btn btn-secondary" href="https://wallstbots.tech" target="_blank" rel="noopener" style="font-size:12px;margin-top:auto">Visit wallstbots.tech →</a>'
    + '</div>'

    + '<div class="card" style="display:flex;flex-direction:column">'
    + '<div style="font-size:10px;font-weight:700;letter-spacing:1px;color:var(--blue);margin-bottom:12px;text-transform:uppercase">Our<br>Cryptocurrency<br>Bots</div>'
    + '<a href="https://bitbot13.tech" target="_blank" rel="noopener">'
    + '<img src="assets/logo-bitbot13.png" alt="BitBot13" style="width:100%;max-width:320px;height:auto;display:block;margin:0 auto 14px;border-radius:8px"></a>'
    + '<p style="color:var(--muted);font-size:13px;line-height:1.6;margin:0 0 14px;flex:1">The same AI intelligence applied to Bitcoin and crypto markets. BitBot13 tracks the top 50 coins with daily Buy/Sell/Hold signals and strategy competition.</p>'
    + '<a class="btn btn-secondary" href="https://bitbot13.tech" target="_blank" rel="noopener" style="font-size:12px;margin-top:auto">Visit bitbot13.tech →</a>'
    + '</div>'

    + '</div>'
    + '<p style="text-align:center;color:var(--muted);font-size:13px;margin:0 0 36px;line-height:1.6">One login for stocks or cryptocurrencies. Your trading market research platform — Level 13.</p>'

    + getYoursHint('Join and let BOT13 — the bot that only trades when it sees an edge — trade your own stock picks.');
  drawTrajectory();
}

// ============ PAGE: NEWS-ALL (standalone) ============
function renderNewsAll() {
  const news = STATE.news || { items: [] };
  const sectors = news.sectors || ['AI & QUANTUM','BIOTECH','ENERGY','DEFENSE','FINANCE'];
  const items = (news.items || []).filter(i =>
    SECTOR_FILTER === 'ALL' || (i.sector || '').toUpperCase() === SECTOR_FILTER);
  const chips = ['ALL', ...sectors].map(s =>
    '<button class="sector-chip '+(SECTOR_FILTER===s?'active':'')+'" onclick="SECTOR_FILTER=\''+s+'\'; renderNewsAll()">'+s+'</button>'
  ).join('');
  const cards = items.length ? items.map(newsCard).join('')
    : '<p class="sub">No headlines for this sector yet.</p>';

  $('app').innerHTML = '<h1>News</h1>'
    + '<p class="sub">Filtered headlines from the sectors that matter. Updated nightly. Click any card to read at the source.</p>'
    + '<div class="sector-bar"><span class="sector-bar-label">Filter:</span>'+chips+'</div>'
    + '<div class="news-grid">'+cards+'</div>'

    // Sales push at the bottom of /news-all
    + '<div class="sales-strip" style="margin-top:36px">'
    + '<div><h3>Want news for YOUR sectors?</h3>'
    + '<p>Pick the sectors you care about. We curate, dedupe, deliver — straight to your private dashboard.</p></div>'
    + '<a href="#/get-yours" class="btn btn-primary" style="margin-left:auto">Get Yours →</a></div>'

    + '<div class="grid grid-3" style="margin-top:18px">'
    + [['Custom news feed','Pick AI, Quantum, Biotech, Defense, Energy — any combination.'],
       ['Daily refresh','Headlines pulled fresh every night.'],
       ['Source-direct','Every card links straight to the original article.']].map(p =>
         '<div class="card"><h3 style="color:var(--blue)">✓ '+p[0]+'</h3>'
         + '<p style="color:var(--muted);font-size:13px;margin:0">'+p[1]+'</p></div>').join('')
    + '</div>'
    + getYoursHint('Join and get this news feed filtered to your own sectors.');
}

// ============ PAGE: HOW IT WORKS ============
function renderHowItWorks() {
  const bots = [
    { id:'bot13',     l1:'Buys at open, sells before close.', l2:'Skips the day if no edge.' },
    { id:'oracle',    l1:'Trades every Monday morning.',      l2:'Holds for the week.' },
    { id:'wizard',    l1:'Buys 1st trading day of month.',    l2:'Liquidates the last day.' },
    { id:'equalizer', l1:'$1,000 in every stock.',            l2:'Equal weight, no favorites.' },
    { id:'titan',     l1:'Half on top-10 mega-caps.',         l2:'Half across the rest.' },
  ];
  const stripCards = bots.map(b => {
    const m = FUND_META[b.id];
    return '<div class="bot-strip-card '+b.id+'"><div class="fund-head">'
      + '<span class="fund-icon '+b.id+'">'+m.icon+'</span><div class="fund-name">'+m.name+'</div></div>'
      + '<div class="kind">'+m.kind+'</div><div class="l1">'+b.l1+'</div><div class="l2">'+b.l2+'</div></div>';
  }).join('');
  const features = [
    ['Daily Buy / Sell / Hold','Composite analysis on every stock — every day. Score combines momentum, RSI, MACD, volume, volatility into a Strong Buy → Strong Sell call with target price.'],
    ['Monthly Statements You Can Download','A bank-statement PDF for every month — BOT13’s daily trades, every bot’s monthly P&L, and the weekly &amp; monthly picks.'],
    ['AI &amp; Quantum News, Filtered','Headlines pulled from the sectors that matter. AI, Quantum, Biotech, Defense — pick what you follow.'],
  ];
  const featureCards = features.map(f =>
    '<div class="card"><h3 style="color:var(--blue)">✓ '+f[0]+'</h3>'
    + '<p style="color:var(--muted);font-size:13px;margin:0">'+f[1]+'</p></div>').join('');
  $('app').innerHTML = '<h1>How It Works</h1>'
    + '<p class="sub">Five strategies. One universe. The same starting capital. Then we let them prove it — in public.</p>'
    + '<div class="panel" style="margin-bottom:20px">'
    + '<p style="font-size:15px;line-height:1.7;margin:0 0 10px">Most trading advice is noise — screenshots, hot takes, and “trust me.” We built something you can actually watch instead: five strategies, each handed the same money and the same stocks, trading head-to-head every single market day. Three are active bots — daily, weekly, monthly. Two are passive benchmarks that show what plain buy-and-hold would have done.</p>'
    + '<p style="font-size:15px;line-height:1.7;margin:0;color:var(--muted)">Nothing is hidden. Every trade is timestamped, every result is live, and every month is downloadable. This isn’t a pitch — it’s a scoreboard.</p>'
    + '</div>'
    + '<div class="panel" style="border-color:var(--pink);background:linear-gradient(135deg,rgba(236,72,153,0.08),rgba(236,72,153,0.01));margin-bottom:20px">'
    + '<div class="section-head" style="margin:0 0 12px"><h3 style="color:var(--pink)">Meet BOT13 — the one to watch</h3></div>'
    + '<p style="font-size:15px;line-height:1.7;margin:0 0 12px">BOT13 is the daily bot, and it lives by one rule: <strong style="color:var(--pink)">no edge, no trade.</strong> Each morning it scores the entire universe. See a real edge? It buys — and sells before the close. No edge? It does the hardest thing in trading: nothing. It holds cash and risks zero. That is the discipline most traders wish they had, running automatically, on the record.</p>'
    + '<div style="display:flex;gap:10px;flex-wrap:wrap">'
    + '<div style="flex:1;min-width:150px;text-align:center;padding:12px;background:var(--panel2);border:1px solid var(--border);border-radius:8px"><div class="stat-val pos" style="font-size:19px">No edge, no trade</div><div class="stat-label" style="margin-top:5px">A quiet day costs you nothing</div></div>'
    + '<div style="flex:1;min-width:150px;text-align:center;padding:12px;background:var(--panel2);border:1px solid var(--border);border-radius:8px"><div class="stat-val" style="font-size:19px;color:var(--pink)">Flat by every close</div><div class="stat-label" style="margin-top:5px">No overnight surprises</div></div>'
    + '<div style="flex:1;min-width:150px;text-align:center;padding:12px;background:var(--panel2);border:1px solid var(--border);border-radius:8px"><div class="stat-val" style="font-size:19px">Every trade public</div><div class="stat-label" style="margin-top:5px">Timestamped, on the record</div></div>'
    + '</div>'
    + '<p style="font-size:13px;color:var(--muted);margin:12px 0 0">The results speak for themselves — watch them live on the leaderboard, or download the monthly statement and read every trade BOT13 made.</p>'
    + '</div>'
    + '<h3>The 5 Strategies</h3><div class="bot-strip">'+stripCards+'</div>'
    + '<div class="sales-strip" style="margin-top:20px"><div><h3>How the edge is scored.</h3>'
    + '<p>Every stock, every day, gets one composite score — momentum, RSI, MACD, volume, and volatility rolled into a single Strong Buy → Strong Sell call with a target price. The bots don’t guess and they don’t get emotional. They act on the score, log the trade, and move on. You see exactly why every move was made.</p></div></div>'
    + '<h3 style="margin-top:24px">What You Get</h3><div class="grid grid-3">'+featureCards+'</div>'
    + '<div class="panel" style="margin-top:20px;border-color:var(--blue)">'
    + '<div class="section-head" style="margin:0 0 10px"><h3 style="color:var(--blue)">Now run it on YOUR stocks</h3></div>'
    + '<p style="font-size:15px;line-height:1.7;margin:0 0 12px">The homepage race runs on our universe. As a member, you point the exact same five bots at <strong>your</strong> picks — up to 50 AI &amp; Quantum stocks. BOT13 trades them by the same no-edge-no-trade rule, and you get daily Buy/Sell/Hold signals, news filtered to your names, and a monthly statement you can keep.</p>'
    + '<ul style="margin:0;padding-left:18px;font-size:14px;line-height:1.9;color:var(--muted)"><li>Your portfolio, your tickers — the bots supply the discipline.</li><li>Daily signals and alerts, straight to your inbox.</li><li>Downloadable monthly statements for every bot.</li><li>Stocks, AI &amp; Quantum, and crypto — one login on the Syndicate plan.</li></ul>'
    + '</div>'
    + '<div class="sales-strip" style="margin-top:20px"><div><h3>Why most traders lose.</h3>'
    + '<p>It’s rarely the strategy — it’s the human running it. We hold losers too long, dump winners too early, and trade out of boredom on the days we should sit still. The bots don’t. They follow the same rule every single day — no ego, no fear, no FOMO. That discipline is the whole edge.</p></div></div>'
    + '<div class="panel" style="margin-top:20px">'
    + '<div class="section-head" style="margin:0 0 10px"><h3>Nothing to hide</h3></div>'
    + '<p style="font-size:15px;line-height:1.7;margin:0 0 10px">Anyone can post a green screenshot. We post everything — every trade, every day, win or lose, timestamped and public. The leaderboard updates as the market moves; the monthly statement is a PDF you can download and check line by line. No black box. No cherry-picking. No “DM me for results.”</p>'
    + '<p style="font-size:13px;color:var(--muted);margin:0">If a strategy works, it should prove it in the open — every day. Ours does.</p>'
    + '</div>'
    + '<h3 style="margin-top:24px">Why this beats a typical alerts group</h3>'
    + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">'
    + '<div class="card"><h3 style="color:var(--muted);margin-bottom:10px">A typical alerts group</h3><ul style="margin:0;padding-left:16px;font-size:13px;line-height:1.9;color:var(--muted)"><li>Vague picks buried in a chat, easy to miss</li><li>Winners screenshotted, losers quietly forgotten</li><li>No track record you can actually audit</li><li>Runs on their picks — never yours</li><li>Loud when it wins, silent when it doesn’t</li></ul></div>'
    + '<div class="card" style="border-color:var(--pink)"><h3 style="color:var(--pink);margin-bottom:10px">'+"'+REPORT_BRAND+'"+'</h3><ul style="margin:0;padding-left:16px;font-size:13px;line-height:1.9;color:var(--fg)"><li>A clear Buy / Sell / Hold on every name, every day</li><li>Every trade logged — wins and losses both</li><li>Public leaderboard + downloadable monthly statements</li><li>Runs on <strong>your</strong> picks, the same disciplined way</li><li>No edge, no trade — it holds cash instead of forcing it</li></ul></div>'
    + '</div>'
    + '<div class="sales-strip" style="margin-top:20px"><div><h3>The Challenge.</h3>'
    + '<p>Three active bots. Two passive benchmarks. The same money, the same market. The best strategy wins in the open — every trading day.</p></div></div>'
    + getYoursHint('Point these five bots at your own stocks — start free.');
}

// ============ PAGE: THE RACE ============
function renderRace() {
  const cards = FUND_ORDER.map(fid =>
    fundCard(fid, STATE.funds && STATE.funds.funds ? STATE.funds.funds[fid] : null)).join('');
  $('app').innerHTML = '<h1>The Race</h1>'
    + '<p class="sub">Five strategies. '+fmt$0((STATE.funds&&STATE.funds.starting_capital)||50000)+' each. Same 50-stock universe. Refreshed live.</p>'
    + '<div class="grid grid-5">'+cards+'</div>'
    + '<div class="panel" style="margin-top:24px"><h3>Performance Trajectory — All 5 Strategies</h3>'
    + '<div class="chart-wrap"><canvas id="chartRace"></canvas></div></div>'
    + getYoursHint('This race is yours to design. Pick stocks, sectors, strategy.');
  drawTrajectory();
}

function drawTrajectory() {
  const ctx = $('chartRace');
  if (!ctx || !window.Chart) return;
  if (CHARTS.race) CHARTS.race.destroy();
  const snaps = (STATE.funds && STATE.funds.snapshots) || [];
  const labels = snaps.map(s => s.date);
  const datasets = FUND_ORDER.map(fid => ({
    label: FUND_META[fid].name,
    data: snaps.map(s => s[fid] || null),
    borderColor: FUND_META[fid].color,
    backgroundColor: FUND_META[fid].color + '22',
    tension: 0.3, borderWidth: 2,
  }));
  CHARTS.race = new Chart(ctx, {
    type: 'line', data: { labels, datasets },
    options: { responsive:true, maintainAspectRatio:false,
      plugins: { legend: { labels: { color:'#e6edf3', font:{size:12} } } },
      scales: {
        x: { ticks:{color:'#7d8590'}, grid:{color:'#1e2633'} },
        y: { ticks:{color:'#7d8590', callback: v => '$'+v.toLocaleString()}, grid:{color:'#1e2633'} }
      }
    }
  });
}

// ── Oracle cash-window helper ─────────────────────────────────────────────────
// Returns true only during the weekend gap: Sat 3:01 AM → Mon market open ET.
function oracleInCashWindow() {
  const etDate = new Date(new Date().toLocaleString("en-US", {timeZone: "America/New_York"}));
  const day = etDate.getDay();
  const minuteOfDay = etDate.getHours() * 60 + etDate.getMinutes();
  const CUTOFF = 3 * 60 + 1;   // 3:01 AM
  const OPEN   = 9 * 60 + 30;  // 9:30 AM
  if (day === 0) return true;                  // Sunday: always cash
  if (day === 6) return minuteOfDay >= CUTOFF; // Sat: cash after 3:01 AM
  if (day === 1) return minuteOfDay < OPEN;    // Mon: cash before market open
  return false;                                // Tue–Fri: show positions
}

// ── Bot13 cash-window helper ──────────────────────────────────────────────────
// Returns true when bot13 holdings should be hidden and "Holding cash" shown.
// Active display window: trade time → 3:00 AM ET (Mon–Sat morning)
// Cash window: 3:01 AM ET → next trade (and all weekend)
function bot13InCashWindow() {
  const etDate = new Date(new Date().toLocaleString("en-US", {timeZone: "America/New_York"}));
  const day = etDate.getDay();                          // 0=Sun 1=Mon … 6=Sat
  const minuteOfDay = etDate.getHours() * 60 + etDate.getMinutes();
  const OPEN  = 9 * 60 + 30;                           // 9:30 AM = 570 min
  const CLOSE = 16 * 60;                               // 4:00 PM = 960 min
  if (day === 0 || day === 6) return true;              // Weekend: always cash
  return minuteOfDay < OPEN || minuteOfDay >= CLOSE;   // Weekday: cash before open or after close
}


// ---- Trade ledger formatting (transparency feature) ----
function fmtTradeTime(iso){
  if(!iso) return '';
  var s=String(iso).replace('Z','').trim();
  var d=new Date(s.indexOf('T')>=0?s:s.replace(' ','T'));
  if(isNaN(d.getTime())) return String(iso);
  var h=d.getHours(), m=d.getMinutes(); var ap=h>=12?'PM':'AM'; var h12=h%12; if(h12===0) h12=12;
  return h12+':'+(m<10?'0':'')+m+' '+ap+' ET';
}
// Sort a COPY of the immutable trade_log for display only (never mutate source).
//  - During the session (windowOpen): strict chronological, oldest -> newest.
//  - After hours (!windowOpen): each symbol shown as a BUY->SELL pair, and the
//    PAIRS ordered by the symbol's earliest BUY time. Reads as a clean round-trip
//    log: 9:35 BUY SPCX / 2:00 SELL SPCX, then 9:35 BUY XYZ / 2:00 SELL XYZ, ...
//    Close-out sells therefore sit with their buys, and the day reads in order.
// DISPLAY SPEC v1 (2026-07-10, all platforms): asset-aware precision, same RULES everywhere.
// Stocks: $ + 2dp, sub-$1 stocks 4dp. Crypto: fmtCrypto dynamic (8/4/2). Quantities:
// Trade History 4dp (the receipt), Holdings 2dp, whole units + commas once qty >= 1,000.
function fmtPxS(v){ if(v==null||isNaN(v)) return '-'; v=Number(v);
  var dp = v<1?4:2;
  return '$'+v.toLocaleString(undefined,{minimumFractionDigits:dp,maximumFractionDigits:dp}); }
function fmtShares(v,dp){ if(v==null||isNaN(v)) return '-'; v=Number(v);
  if(v>=1000) return v.toLocaleString(undefined,{maximumFractionDigits:0});
  return v.toFixed(dp); }

function sortTradeLog(tl, windowOpen){
  var arr = (tl||[]).slice();
  if (windowOpen) {
    // During the session: chronological by time. Within the SAME timestamp, a SELL
    // comes before a BUY -- on a strategy rotation the bot closes its prior positions
    // first (freeing capital), then opens the new ones, so closes must list first.
    var _rk = function(act){ return act==='SELL'?0:act==='BUY'?1:2; };
    arr.sort(function(a,b){
      var ta=String(a&&a.ts||''), tb=String(b&&b.ts||'');
      if (ta!==tb) return ta<tb?-1:1;
      return _rk(String(a&&a.action))-_rk(String(b&&b.action));
    });
  } else {
    // first BUY timestamp per symbol = the pair's sort key
    var firstBuy = {};
    arr.forEach(function(e){
      var s=String(e&&e.symbol||''), t=String(e&&e.ts||'');
      if (String(e&&e.action)==='BUY' && (!(s in firstBuy) || t<firstBuy[s])) firstBuy[s]=t;
    });
    var keyOf = function(e){
      var s=String(e&&e.symbol||'');
      return (s in firstBuy) ? firstBuy[s] : String(e&&e.ts||'');  // fallback: own ts
    };
    var rank = function(act){ return act==='BUY'?0:act==='SELL'?2:1; };
    arr.sort(function(a,b){
      var ka=keyOf(a), kb=keyOf(b);
      if (ka!==kb) return ka<kb?-1:1;   // pairs ordered by earliest BUY time
      var sa=String(a&&a.symbol||''), sb=String(b&&b.symbol||'');
      if (sa!==sb) return sa<sb?-1:1;   // tie-break: keep same symbol together
      var ra=rank(a&&a.action), rb=rank(b&&b.action);
      if (ra!==rb) return ra-rb;        // BUY before SELL within the symbol
      var ta=String(a&&a.ts||''), tb=String(b&&b.ts||'');
      return ta<tb?-1:ta>tb?1:0;        // then by time
    });
  }
  return arr;
}
// Box F - Trade History. BOT13 ONLY. Never hidden for bot13: shows "No trades today"
// on a pure cash day instead of disappearing.
function renderTradeLog(tl, fid, windowOpen){
  if (fid !== 'bot13') return '';            // Box F is BOT13-only
  var open = windowOpen !== false;
  var sub  = open ? 'Every buy and sell is timestamped, in the order it happened.'
                  : 'Today\u2019s trades, grouped by symbol \u2014 buy then sell.';
  var _thDate = new Date().toLocaleDateString('en-US', {timeZone:'America/New_York', month:'short', day:'numeric', year:'numeric'});
  // Show ONLY today's (ET) trades -- the header says "Today", so stale trades from a prior
  // session (e.g. over a weekend/holiday when nothing traded) must not appear under today's date.
  var _todayISO = new Date().toLocaleDateString('en-CA', {timeZone:'America/New_York'});  // YYYY-MM-DD
  tl = (tl || []).filter(function(t){ return String((t && t.ts) || '').slice(0,10) === _todayISO; });
  var head = '<div class="panel"><h3>Trade History - '+_thDate+'</h3>'
    + '<div style="color:var(--muted);font-size:12px;margin:-4px 0 10px">'+sub+'</div>'
    + '<div class="tbl-wrap"><table>'
    + '<thead><tr><th>Time</th><th>Action</th><th>Symbol</th><th class="num">Shares</th><th class="num">Price</th><th class="num">Realized P&amp;L</th><th>Note</th></tr></thead>'
    + '<tbody>';
  if (!tl || !tl.length) {
    return head + '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:18px">No trades today</td></tr>'
      + '</tbody></table></div></div>';
  }
  var rows = sortTradeLog(tl, open).map(function(t){
    var act=t.action||''; var c=act==='BUY'?'var(--blue)':act==='SELL'?((t.realized!=null&&Number(t.realized)<0)?'var(--red)':'var(--green)'):'var(--muted)';
    var realized = (t.realized!=null && act==='SELL')
      ? '<td class="num '+cls(t.realized)+'">'+fmt$0(t.realized)+'</td>' : '<td class="num">-</td>';
    return '<tr><td style="white-space:nowrap;color:var(--muted);font-size:12px">'+escapeHtml(fmtTradeTime(t.ts))+'</td>'
      + '<td><strong style="color:'+c+'">'+escapeHtml(act)+'</strong></td>'
      + '<td><strong>'+escapeHtml(t.symbol||'')+'</strong></td>'
      + '<td class="num">'+fmtShares(t.shares,4)+'</td>'
      + '<td class="num">$'+(t.price!=null?Number(t.price).toFixed(2):'-')+'</td>'
      + realized
      + '<td style="color:var(--muted);font-size:12px">'+escapeHtml(t.reason||'')+'</td></tr>';
  }).join('');
  return head + rows + '</tbody></table></div></div>';
}

// ============ PAGE: INDIVIDUAL FUND ============
function renderFund(fid) {
  const data = STATE.funds && STATE.funds.funds ? STATE.funds.funds[fid] : null;
  const meta = FUND_META[fid];
  if (!meta) { $('app').innerHTML = '<p>Unknown fund</p>'; return; }
  const cap = (STATE.funds && STATE.funds.starting_capital) || 50000;
  const v = data && data.value ? data.value : { total:cap, pnl:0, pnl_pct:0, day_pnl:0, day_pct:0, positions:[] };
  const startCap = (data && data.starting_capital) || cap;
  let strategyHTML = '';
  if (['bot13','oracle','wizard'].includes(fid) && data && data.current_strategy) {
    strategyHTML = renderStrategyPanel(fid, data.current_strategy);
  }

  const holdingCash = v.holding_cash === true;
  const windowOpen = v.window_open !== false;
  const tradedToday = v.traded_today === true;
  // Current Holdings = strictly CURRENT.
  //  - During the session: show held positions; if flat -> "Holding cash - no edge".
  //  - After the session ends: NO assets. Trade History is the day's record. Show
  //    "End of trading session - holding cash" if it traded today, else
  //    "Holding cash - no edge".
  function _cashRow(txt){
    return '<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:18px">'+txt+'</td></tr>';
  }
  const noEdgeRow = _cashRow('Holding cash - no edge');
  let positionRows;
  if (!windowOpen) {
    positionRows = tradedToday ? _cashRow('End of trading session - holding cash') : noEdgeRow;
  } else if ((v.positions || []).length && !holdingCash) {
    positionRows = v.positions.map(p => {
        const entry  = p.entry_price || p.entry || 0;
        const price  = p.price || entry;
        const shares = p.shares || 0;
        const value  = p.value || (shares * price);
        const pnl    = p.pnl != null ? p.pnl : (value - (p.cost_basis || (shares * entry)));
        const pnlPct = p.pnl_pct != null ? p.pnl_pct
                     : (entry > 0 ? ((price/entry - 1)*100) : 0);
        const dayPnl = p.day_pnl != null ? p.day_pnl : 0;
        const dayPct = p.day_pct != null ? p.day_pct : 0;
        return '<tr><td><strong>'+p.symbol+'</strong></td>'
          + '<td class="num">'+fmtShares(shares,2)+'</td>'
          + '<td class="num">'+fmtPxS(entry)+'</td>'
          + '<td class="num">'+fmtPxS(price)+'</td>'
          + '<td class="num">'+fmt$0(value)+'</td>'
          + '<td class="num '+cls(dayPnl)+'">'+fmtPct(dayPct)+'</td>'
          + '<td class="num '+cls(pnl)+'">'+fmt$0(pnl)+'</td>'
          + '<td class="num '+cls(pnlPct)+'">'+fmtPct(pnlPct)+'</td></tr>';
      }).join('');
  } else {
    positionRows = noEdgeRow;
  }

  $('app').innerHTML =
    '<div class="fund-head" style="margin-bottom:14px">'
    + '<span class="fund-icon '+fid+'" style="width:48px;height:48px;font-size:16px">'+meta.icon+'</span>'
    + '<div><h1 style="margin:0">'+meta.name+'</h1>'
    + '<div class="fund-tag">'+meta.tagline+'</div></div></div>'
    + '<div class="grid grid-3" style="margin-bottom:18px">'
    + '<div class="card"><h3>Current Value</h3>'
    + '<div class="fund-value">'+fmt$0(v.total)+'</div>'
    + '<div style="color:var(--muted);font-size:11px;margin-top:6px">Started at '+fmt$0(startCap)+'</div></div>'
    + '<div class="card"><h3>Total P&amp;L</h3>'
    + '<div class="fund-value '+cls(Math.round(v.pnl))+'">'+fmt$0(v.pnl)+'</div>'
    + '<div class="fund-pnl '+cls(v.pnl_pct)+'">'+fmtPct(v.pnl_pct)+' all-time</div></div>'
    + '<div class="card"><h3>Today\'s Change</h3>'
    + '<div class="fund-value '+cls(Math.round(v.day_pnl))+'">'+fmt$0(v.day_pnl)+'</div>'
    + '<div class="fund-pnl '+cls(v.day_pct)+'">'+fmtPct(v.day_pct)+' since yesterday</div></div></div>'
    + strategyHTML
    + '<div class="panel"><h3>Current Holdings</h3>'
    + '<div class="tbl-wrap"><table>'
    + '<thead><tr><th>Symbol</th><th class="num">Shares</th><th class="num">Entry</th>'
    + '<th class="num">Price</th><th class="num">Value</th><th class="num">Today</th>'
    + '<th class="num">Total P&amp;L</th><th class="num">%</th></tr></thead>'
    + '<tbody>'+positionRows+'</tbody></table></div></div>'
    + renderTradeLog((v.trade_log||[]), fid, windowOpen)
    + (fid === 'bot13' ? bot13RecordTile() : '')
    // COPY-TRADE DISCLOSURE (2026-07-10, Rule 0): honest expectations for copiers
    + '<p style="color:var(--muted);font-size:11px;text-align:center;max-width:760px;margin:14px auto 0">All results are simulated fills at real market feed prices recorded at decision time. Feed prices can lag live markets by a few minutes, and results exclude broker spreads, commissions, and fees \u2014 copying trades in real time should produce closely similar, not identical, results.</p>'
    + getYoursHint('Want a '+meta.name.toLowerCase()+'-style bot picking from YOUR stock list?');
}

function renderStrategyPanel(fid, strat) {
  const period = fid==='bot13' ? 'Day of '+strat.day
               : fid==='oracle' ? 'Week of '+strat.week
               : 'Month of '+strat.month;
  const label  = fid==='bot13' ? "CURRENT SESSION'S STRATEGY"
               : fid==='oracle' ? "THIS WEEK'S STRATEGY"
               : "THIS MONTH'S STRATEGY";
  const projLabel = fid==='bot13' ? 'Projected Return'
                  : fid==='oracle' ? 'Projected Week Return'
                  : 'Projected Month Return';
  const projRet = strat.projected_return;
  // Projected Return only shows for BOT13 — it is the pre-trade edge score,
  // never the actual return. Oracle and Wizard do not show this.
  const projHtml = (fid === 'bot13' && projRet != null)
    ? '<div style="margin:6px 0 10px;font-size:13px">'
      + '<span style="color:var(--muted)">Projected Edge Score: </span>'
      + '<span style="font-weight:700;color:'+(projRet > 0 ? 'var(--green)' : projRet < 0 ? 'var(--red)' : 'var(--muted)')+'">'
      + (projRet > 0 ? '+' : '')+projRet.toFixed(2)+'%</span>'
      + '<span style="color:var(--muted);font-size:11px;margin-left:6px">(must exceed 1.74% to trade)</span></div>'
    : '';
  // After a day BOT13 traded, the engine flips decision to HOLD for accounting at
  // close-out. For DISPLAY (Box D), keep showing the day's picks and a "closed for
  // the day" note instead of the 100% CASH card -- HOLD card only on true no-trade days.
  var _tradedToday = strat.traded_today === true;
  let picks = '';
  if ((strat.decision === 'CASH' || strat.decision === 'HOLD') && !_tradedToday) {
    picks = '<div class="pick-card"><div class="pick-head"><div class="pick-sym">100% CASH</div><div class="pick-meta">No positions — holding cash</div></div>'
      + '<div class="pick-rationale" style="color:var(--muted)">'+escapeHtml(strat.rationale||'')+'</div></div>';
  } else {
    picks = '<div class="pick-grid">' + (strat.picks||[]).map(p => {
      const ind = p.indicators || {};
      const parts = [];
      if (ind.mom_1d   != null) parts.push('1d: '+fmtPct(ind.mom_1d));
      if (ind.mom_5d   != null) parts.push('5d: '+fmtPct(ind.mom_5d));
      if (ind.mom_20d  != null) parts.push('20d: '+fmtPct(ind.mom_20d));
      if (ind.mom_60d  != null) parts.push('60d: '+fmtPct(ind.mom_60d));
      if (ind.rsi_14   != null) parts.push('RSI: '+ind.rsi_14);
      if (ind.macd_pct != null) parts.push('MACD: '+fmtPct(ind.macd_pct));
      return '<div class="pick-card"><div class="pick-head">'
        + '<div class="pick-sym">'+p.symbol+'</div>'
        + '<div class="pick-meta">Wt '+(p.weight*100).toFixed(0)+'% · '+(p.score>=0?'+':'')+p.score+'</div></div>'
        + '<div class="pick-rationale">'+escapeHtml(p.rationale||'')+'</div>'
        + '<div class="pick-indicators">'+parts.join(' · ')+'</div></div>';
    }).join('') + '</div>';
  }
  const cleanRationale = (strat.rationale||'').replace(/^Projected\s+\w*\s*return:[^.]*\.\s*/i, '');
  return '<div class="strategy-panel '+fid+'"><h3>'+label+'</h3>'
    + '<div class="strategy-meta">'+escapeHtml(period)+' · '+escapeHtml(_tradedToday && (strat.decision==='HOLD'||strat.decision==='CASH') ? 'TRADED — closed for the day' : (strat.decision||''))+'</div>'
    + projHtml
    + '<p class="strategy-rationale">'+escapeHtml(cleanRationale)+'</p>'+picks+'</div>';
}

// ============ PAGE: SIGNALS ============
function renderSignals() {
  const data = STATE.signals || { recommendations: [], summary: {} };
  const sum = data.summary || {};
  const summary = '<div class="grid grid-5" style="margin-bottom:18px">'
    + [['STRONG BUY','pos'],['BUY','pos'],['HOLD',''],['SELL','neg'],['STRONG SELL','neg']].map(([k,c]) =>
        '<div class="card" style="text-align:center"><div class="fund-value '+c+'" style="font-size:26px">'+(sum[k]||0)+'</div><h3 style="margin:0;font-size:10px">'+k+'</h3></div>'
      ).join('') + '</div>';
  const filters = ['ALL','STRONG BUY','BUY','HOLD','SELL','STRONG SELL'];
  const filterHTML = '<div class="sector-bar">' + filters.map(f =>
    '<button class="sector-chip '+(SIGNALS_FILTER===f?'active':'')+'" onclick="SIGNALS_FILTER=\''+f+'\'; renderSignals()">'+f+'</button>'
  ).join('') + '</div>';
  const ACTION_ORDER = {'STRONG BUY':0,'BUY':1,'HOLD':2,'SELL':3,'STRONG SELL':4};
  const recs = (data.recommendations||[]).filter(r =>
    SIGNALS_FILTER==='ALL' || r.action===SIGNALS_FILTER)
    .sort((a,b) => (ACTION_ORDER[a.action]??99) - (ACTION_ORDER[b.action]??99));
  const rows = recs.length ? recs.map(r => {
    const ind = r.indicators || {};
    const slug = (r.action || 'NA').toLowerCase().replace(/ /g,'-');
    return '<tr><td><strong>'+r.symbol+'</strong></td>'
      + '<td><span class="signal signal-'+slug+'">'+r.action+'</span></td>'
      + '<td class="num">'+(r.price ? '$'+r.price.toFixed(2) : '—')+'</td>'
      + '<td class="num">'+(r.target ? '$'+r.target.toFixed(2) : '—')+'</td>'
      + '<td class="num '+(r.upside_pct>=0?'pos':'neg')+'">'+(r.upside_pct!=null?fmtPct(r.upside_pct):'—')+'</td>'
      + '<td class="num">'+(r.score!=null?(r.score>=0?'+':'')+r.score.toFixed(1):'—')+'</td>'
      + '<td>'+(r.confidence||'—')+'</td><td>'+(r.risk||'—')+'</td>'
      + '<td class="num">'+(ind.rsi_14!=null?ind.rsi_14:'—')+'</td>'
      + '<td class="num '+(ind.mom_5d>=0?'pos':'neg')+'">'+(ind.mom_5d!=null?fmtPct(ind.mom_5d):'—')+'</td>'
      + '<td class="num '+(ind.mom_20d>=0?'pos':'neg')+'">'+(ind.mom_20d!=null?fmtPct(ind.mom_20d):'—')+'</td></tr>';
  }).join('') : '<tr><td colspan="11" style="text-align:center;padding:18px;color:var(--muted)">No signals match this filter.</td></tr>';

  $('app').innerHTML = '<h1>Signals — Buy / Sell / Hold</h1>'
    + '<p class="sub">Composite analysis on every stock in the universe. Updated daily'+(data.generated_at?' — last run '+relTime(data.generated_at):'')+'.</p>'
    + summary + filterHTML
    + '<div class="panel"><div class="tbl-wrap"><table><thead><tr>'
    + '<th>Sym</th><th>Action</th><th class="num">Price</th><th class="num">Target</th>'
    + '<th class="num">Upside</th><th class="num">Score</th><th>Conf</th><th>Risk</th>'
    + '<th class="num">RSI</th><th class="num">5d</th><th class="num">20d</th>'
    + '</tr></thead><tbody>'+rows+'</tbody></table></div></div>'
    + '<div class="panel" style="font-size:12px;color:var(--muted);line-height:1.7">'
    + '<strong style="color:var(--text)">How signals are computed.</strong> '
    + 'Composite score blends 5d &amp; 20d momentum, MACD bias, RSI(14), volume confirmation, and a volatility penalty. '
    + 'Strong Buy ≥ +12. Buy ≥ +4. Sell ≤ −4 or extreme overbought + bearish MACD. Strong Sell ≤ −12.</div>'
    + getYoursHint('Get this signal table on YOUR 50 stocks.');
}

// ============ PAGE: REPORTS ============
function monthLabel(ym){
  const M=['January','February','March','April','May','June','July','August','September','October','November','December'];
  const p=String(ym||'').split('-'); if(p.length<2) return ym;
  return M[(parseInt(p[1],10)||1)-1]+' '+p[0];
}

// Reports page: list every month with a bank-statement PDF download.
function renderReports(){
  $('app').innerHTML='<h1>Monthly Reports</h1>'
    +'<p class="sub">Bank-statement-style performance reports. Download any month as a PDF \u2014 BOT13\u2019s daily trades, every bot\u2019s monthly P&amp;L, and the weekly &amp; monthly picks.</p>'
    +'<div class="panel" id="repList"><p style="color:var(--muted);text-align:center;padding:20px">Loading reports\u2026</p></div>'
    +getYoursHint();
  fetch(API_BASE+'/public/reports/available?platform='+REPORT_PLATFORM,{cache:'no-store'})
    .then(r=>r.json()).then(d=>{
      const el=$('repList'); if(!el) return;
      const months=(d&&d.months)||[]; const cur=d&&d.current_month;
      const rows=[];
      if(cur) rows.push(reportCard(cur,true));
      months.filter(m=>m!==cur).forEach(m=>rows.push(reportCard(m,false)));
      el.innerHTML = rows.length
        ? '<div class="grid grid-3">'+rows.join('')+'</div>'
        : '<p style="color:var(--muted);text-align:center;padding:20px">No reports yet \u2014 statements begin accumulating this month.</p>';
    }).catch(()=>{ const el=$('repList'); if(el) el.innerHTML='<p style="color:var(--muted);text-align:center;padding:20px">Couldn\u2019t load reports right now.</p>'; });
}

function reportCard(ym,isCurrent){
  return '<div class="card">'
    +'<h3 style="margin-bottom:2px">'+monthLabel(ym)+'</h3>'
    +'<div style="font-size:12px;color:var(--muted);margin-bottom:14px">'+(isCurrent?'This month so far':'Full month')+'</div>'
    +'<div class="hero-ctas" style="gap:8px;flex-wrap:wrap">'
    +'<button class="btn btn-primary" onclick="downloadStatementPDF(\''+ym+'\',this)">Download PDF</button>'
    +'<a class="btn btn-secondary" href="#/report/'+ym+'">View</a>'
    +'</div></div>';
}

// On-page preview of a single month (also offers the PDF).
function renderReport(ym){
  $('app').innerHTML='<h1>'+monthLabel(ym)+' Statement</h1>'
    +'<p class="sub">'+REPORT_BRAND+' \u2014 simulated performance</p>'
    +'<div style="margin-bottom:14px"><button class="btn btn-primary" onclick="downloadStatementPDF(\''+ym+'\',this)">Download PDF</button> '
    +'<a class="btn btn-secondary" href="#/reports">All reports</a></div>'
    +'<div class="panel" id="repView"><p style="color:var(--muted);text-align:center;padding:20px">Loading\u2026</p></div>';
  fetch(API_BASE+'/public/reports/monthly?platform='+REPORT_PLATFORM+'&month='+ym,{cache:'no-store'})
    .then(r=>r.json()).then(d=>{ const el=$('repView'); if(el) el.innerHTML=reportPreviewHTML(d); })
    .catch(()=>{ const el=$('repView'); if(el) el.innerHTML='<p style="color:var(--muted);text-align:center;padding:20px">Couldn\u2019t load this statement.</p>'; });
}

function reportPreviewHTML(d){
  if(!d||!d.success) return '<p style="color:var(--muted);text-align:center;padding:20px">No data for this month yet.</p>';
  const funds=(d.funds||[]).map(f=>
    '<div class="stat-row"><span class="stat-label">'+escapeHtml(f.name)+(f.is_baseline?' <span style="color:var(--muted);font-size:11px">(baseline)</span>':'')+'</span>'
    +'<span class="'+cls(f.month_pnl)+'" style="font-weight:600">'+fmt$(f.month_pnl)+' ('+fmtPct(f.month_pct)+')</span></div>').join('');
  const b=d.bot13||{}; const days=(b.daily||[]).filter(x=>(x.trades||[]).length);
  const bDaily = days.length ? days.map(day=>
    '<div style="margin:8px 0"><div style="font-size:12px;color:var(--muted);margin-bottom:2px">'+day.date+'  \u2014  day P&amp;L '+fmt$(day.day_pnl)+'</div>'
    +(day.trades||[]).map(t=>
      '<div class="stat-row" style="padding:2px 0"><span class="stat-label"><span class="'+((String(t.action).toUpperCase()==='BUY')?'pos':'neg')+'">'+escapeHtml(t.action)+'</span> '+escapeHtml(t.symbol||'')+'</span>'
      +'<span style="font-size:12px">'+((t.price!=null)?('@ '+fmt$(t.price)):'')+((t.realized!=null&&String(t.action).toUpperCase()==='SELL')?('  \u2014  '+fmt$(t.realized)):'')+'</span></div>').join('')
    +'</div>').join('') : '<p style="color:var(--muted);font-size:13px">No BOT13 trades recorded this month yet.</p>';
  const picks=(d.picks||{}); 
  const pickBlock=(title,arr)=> (arr&&arr.length)? '<div style="margin-top:8px"><div style="font-weight:600">'+title+'</div>'
      +arr.map(p=>'<div style="font-size:13px;color:var(--muted)">'+p.start_date+': '+escapeHtml((p.symbols||[]).join(', '))+'</div>').join('')+'</div>' : '';
  return '<h3 style="margin-bottom:8px">Monthly P&amp;L by bot</h3>'+funds
    +'<h3 style="margin:16px 0 8px">BOT13 \u2014 daily trades</h3>'+bDaily
    +((picks.oracle&&picks.oracle.length)||(picks.wizard&&picks.wizard.length)?'<h3 style="margin:16px 0 8px">Strategy picks</h3>'+pickBlock('Oracle (weekly)',picks.oracle)+pickBlock('Wizard (monthly)',picks.wizard):'');
}

// Lazy-load jsPDF (only when a download is requested).
function ensureJsPDF(){
  return new Promise((resolve,reject)=>{
    if(window.jspdf&&window.jspdf.jsPDF) return resolve();
    const s=document.createElement('script');
    s.src='https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
    s.onload=()=>resolve(); s.onerror=()=>reject(new Error('PDF library failed to load'));
    document.head.appendChild(s);
  });
}

async function downloadStatementPDF(ym,btn){
  const label=btn?btn.textContent:''; 
  try{
    if(btn){ btn.disabled=true; btn.textContent='Preparing\u2026'; }
    await ensureJsPDF();
    const d=await fetch(API_BASE+'/public/reports/monthly?platform='+REPORT_PLATFORM+'&month='+ym,{cache:'no-store'}).then(r=>r.json());
    if(!d||!d.success) throw new Error('no data');
    buildStatementPDF(d);
  }catch(e){ alert('Sorry \u2014 could not generate the PDF right now.'); }
  finally{ if(btn){ btn.disabled=false; btn.textContent=label||'Download PDF'; } }
}

// Render the bank-statement PDF from backend-computed numbers (frontend draws only).
function buildStatementPDF(d){
  const { jsPDF }=window.jspdf;
  const doc=new jsPDF({unit:'pt',format:'letter'});
  const W=doc.internal.pageSize.getWidth(), H=doc.internal.pageSize.getHeight(), M=48;
  let y=54;
  const money=n=>{ n=Number(n)||0; return (n<0?'-$':'$')+Math.abs(n).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}); };
  const pcts=n=>{ n=Number(n)||0; return (n>=0?'+':'')+n.toFixed(2)+'%'; };
  const need=h=>{ if(y+h>H-54){ doc.addPage(); y=54; } };
  const line=()=>{ doc.setDrawColor(210); doc.line(M,y,W-M,y); y+=12; };

  // Header
  doc.setFont('helvetica','bold'); doc.setFontSize(18); doc.setTextColor(20);
  doc.text(REPORT_BRAND, M, y);
  doc.setFont('helvetica','normal'); doc.setFontSize(10); doc.setTextColor(120);
  doc.text('Monthly Performance Statement', W-M, y, {align:'right'}); y+=20;
  doc.setFontSize(13); doc.setTextColor(20); doc.setFont('helvetica','bold');
  doc.text(d.month_label||d.month||'', M, y);
  doc.setFont('helvetica','normal'); doc.setFontSize(9); doc.setTextColor(140);
  doc.text('Generated '+String(d.generated_at||'').replace('T',' '), W-M, y, {align:'right'}); y+=8;
  line();

  // Summary table: monthly P&L by bot
  doc.setFont('helvetica','bold'); doc.setFontSize(11); doc.setTextColor(20);
  doc.text('Monthly P&L by bot', M, y); y+=16;
  doc.setFontSize(9); doc.setTextColor(120);
  doc.text('BOT', M, y); doc.text('START', M+230, y,{align:'right'}); doc.text('END', M+330, y,{align:'right'});
  doc.text('MONTH P&L', M+450, y,{align:'right'}); doc.text('%', W-M, y,{align:'right'}); y+=6; line();
  doc.setFontSize(10);
  (d.funds||[]).forEach(f=>{
    need(18);
    doc.setTextColor(20); doc.setFont('helvetica','bold');
    doc.text(String(f.name)+(f.is_baseline?'  (baseline)':''), M, y);
    doc.setFont('helvetica','normal'); doc.setTextColor(60);
    doc.text(money(f.start_value), M+230, y,{align:'right'});
    doc.text(money(f.end_value),   M+330, y,{align:'right'});
    doc.setTextColor((Number(f.month_pnl)||0)<0?190:20); if((Number(f.month_pnl)||0)>=0) doc.setTextColor(20);
    doc.setTextColor((Number(f.month_pnl)||0)<0?183:22,(Number(f.month_pnl)||0)<0?28:22,(Number(f.month_pnl)||0)<0?28:22);
    doc.text(money(f.month_pnl), M+450, y,{align:'right'});
    doc.text(pcts(f.month_pct), W-M, y,{align:'right'});
    y+=17;
  });
  y+=6; line();

  // BOT13 daily trades
  need(24); doc.setFont('helvetica','bold'); doc.setFontSize(11); doc.setTextColor(20);
  const b=d.bot13||{};
  doc.text('BOT13 \u2014 daily trades  ('+money(b.month_pnl)+' this month, '+pcts(b.month_pct)+')', M, y); y+=16;
  const days=(b.daily||[]).filter(x=>(x.trades||[]).length);
  if(!days.length){ doc.setFont('helvetica','normal'); doc.setFontSize(10); doc.setTextColor(120);
    doc.text('No BOT13 trades recorded this month yet.', M, y); y+=18; }
  days.forEach(day=>{
    need(20); doc.setFont('helvetica','bold'); doc.setFontSize(9.5); doc.setTextColor(90);
    doc.text(day.date+'   \u2014   day P&L '+money(day.day_pnl), M, y); y+=14;
    doc.setFont('helvetica','normal'); doc.setFontSize(9.5);
    (day.trades||[]).forEach(t=>{
      need(14);
      const isBuy=String(t.action).toUpperCase()==='BUY';
      doc.setTextColor(isBuy?20:150,isBuy?120:30,isBuy?60:30);
      doc.text((isBuy?'BUY  ':'SELL ')+(t.symbol||''), M+14, y);
      doc.setTextColor(80);
      let rt=[]; if(t.shares!=null) rt.push(Number(t.shares).toLocaleString()+' u'); if(t.price!=null) rt.push('@ '+money(t.price));
      if(!isBuy&&t.realized!=null) rt.push('realized '+money(t.realized));
      doc.text(rt.join('   '), M+120, y); y+=13;
    });
    y+=4;
  });
  y+=6; need(30); line();

  // Strategy picks
  const picks=d.picks||{};
  const drawPicks=(title,arr)=>{
    if(!arr||!arr.length) return;
    need(20); doc.setFont('helvetica','bold'); doc.setFontSize(10.5); doc.setTextColor(20);
    doc.text(title, M, y); y+=14; doc.setFont('helvetica','normal'); doc.setFontSize(9.5); doc.setTextColor(80);
    arr.forEach(p=>{ need(13); doc.text(p.start_date+':  '+((p.symbols||[]).join(', ')), M+14, y); y+=13; });
    y+=4;
  };
  if((picks.oracle&&picks.oracle.length)||(picks.wizard&&picks.wizard.length)){
    need(22); doc.setFont('helvetica','bold'); doc.setFontSize(11); doc.setTextColor(20);
    doc.text('Strategy picks', M, y); y+=16;
    drawPicks('Oracle \u2014 weekly', picks.oracle);
    drawPicks('Wizard \u2014 monthly', picks.wizard);
  }

  // Footer on every page
  const pages=doc.internal.getNumberOfPages();
  for(let i=1;i<=pages;i++){ doc.setPage(i); doc.setFont('helvetica','normal'); doc.setFontSize(8); doc.setTextColor(150);
    doc.text('Simulated performance for education only \u2014 not financial advice. '+REPORT_BRAND, M, H-30);
    doc.text(i+' / '+pages, W-M, H-30, {align:'right'});
  }
  doc.save(REPORT_PLATFORM+'_statement_'+(d.month||'')+'.pdf');
}

// ============ PAGE: GET YOURS ============
const PRICING = {
  member:    { monthly: 49.99, annual: 499.00 },
  insider:   { monthly: 69.99, annual: 699.00 },
  syndicate: { monthly: 99.99, annual: 899.00 },
};
const TIER_META = {
  member:    { label:'MEMBER',    color:'#00d4ff', popular:false,
               features:['Run all 5 bots on your own picks','5 portfolios','Daily Buy/Sell/Hold signals + alerts','Monthly statements to download'] },
  insider:   { label:'INSIDER',   color:'#a855f7', popular:false,
               features:['Everything in Member','10 portfolios','Stocks and crypto together','Priority signals + analytics'] },
  syndicate: { label:'SYNDICATE', color:'#ff8c00', popular:true,
               features:['Everything in Insider','Up to 25 portfolios','All 3 markets: stocks, AI &amp; crypto','First access to new features'] },
};
let GY_CYCLE      = 'monthly';
let GY_TIER       = 'member';
let GY_REF        = '';
let GY_VALID      = false;
let GY_ADMIN_CODE = '';   // set when an admin lifetime code is applied
let GY_ADMIN_TIER = 'insider'; // tier granted by the admin code ('insider' or 'syndicate')

function renderGetYours() {
  // Load Cloudflare Turnstile script once (captcha on the free signup form).
  if (!document.getElementById('cf-turnstile-script')) {
    var _ts = document.createElement('script');
    _ts.id = 'cf-turnstile-script';
    _ts.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js';
    _ts.async = true; _ts.defer = true;
    document.head.appendChild(_ts);
  }
  const urlRef = new URLSearchParams(location.search).get('ref')
              || new URLSearchParams(location.hash.split('?')[1] || '').get('ref') || '';

  $('app').innerHTML =
    '<section class="hero" style="margin-bottom:24px"><img src="assets/logo.svg" alt="" class="hero-robot">'
    + '<div class="hero-content"><span class="hero-eyebrow">Master the Market — Without the Risk</span>'
    + '<h1>You\'ve seen what it does. Now make it yours.</h1>'
    + '<p>You’ve seen the race. <strong style="color:var(--pink)">BOT13’s edge is simple: it only trades when it sees one.</strong> No edge, no trade — it holds cash and risks nothing. Add your own AI &amp; Quantum stocks and it works them the exact same way: daily Buy/Sell/Hold signals, news filtered to your picks, and a monthly statement you can download. The results are public — see them live on the leaderboard.</p></div></section>'

    // ── Billing toggle ──
    + '<div style="display:flex;justify-content:center;margin-bottom:28px">'
    + '<div style="display:flex;background:var(--surface2);border-radius:8px;padding:3px">'
    + '<button id="cycleMonthly" onclick="setGyCycle(\'monthly\')" style="border:none;cursor:pointer;padding:8px 22px;border-radius:6px;font-weight:600;font-size:13px;transition:all 0.15s">Monthly</button>'
    + '<button id="cycleAnnual"  onclick="setGyCycle(\'annual\')"  style="border:none;cursor:pointer;padding:8px 22px;border-radius:6px;font-weight:600;font-size:13px;transition:all 0.15s">Annual <span style="font-size:11px;color:#10b981">SAVE UP TO 25%</span></button>'
    + '</div></div>'

    + '<div class="panel" style="margin-bottom:16px;border-color:var(--pink);background:linear-gradient(135deg,rgba(236,72,153,0.07),rgba(236,72,153,0.01))"><div style="display:flex;gap:10px;flex-wrap:wrap;align-items:stretch">'
    + '<div style="flex:1;min-width:130px;text-align:center"><div class="stat-val pos" style="font-size:22px">No edge, no trade</div><div class="stat-label" style="margin-top:5px">Holds cash, risks nothing</div></div>'
    + '<div style="flex:1;min-width:130px;text-align:center"><div class="stat-val" style="font-size:22px;color:var(--pink)">Flat by every close</div><div class="stat-label" style="margin-top:5px">No overnight risk</div></div>'
    + '<div style="flex:1;min-width:130px;text-align:center"><div class="stat-val" style="font-size:22px">Every trade public</div><div class="stat-label" style="margin-top:5px">See it live, download the statement</div></div>'
    + '</div><p style="color:var(--muted);font-size:11px;margin:10px 0 0;text-align:center">Simulated/paper-trading results, shown live on the leaderboard.</p></div>'
    // ── Paid tier cards ──
    + '<div class="grid grid-3" style="gap:16px;margin-bottom:24px">'
    + Object.entries(TIER_META).map(([tier, meta]) =>
        '<div id="tierCard_'+tier+'" onclick="setGyTier(\''+tier+'\')" '
        + 'style="border:2px solid '+(meta.popular ? meta.color : 'var(--border)')+';border-radius:12px;padding:20px;cursor:pointer;transition:all 0.15s;position:relative;background:var(--surface)">'
        + (meta.popular ? '<div style="position:absolute;top:-1px;right:16px;background:'+meta.color+';color:#000;font-size:10px;font-weight:800;letter-spacing:1px;padding:2px 10px;border-radius:0 0 6px 6px;text-transform:uppercase">POPULAR</div>' : '')
        + '<div style="font-size:11px;font-weight:700;letter-spacing:1.5px;color:'+meta.color+';margin-bottom:10px;text-transform:uppercase">'+meta.label+'</div>'
        + '<div id="tierPrice_'+tier+'" style="font-size:26px;font-weight:800;color:var(--fg);margin-bottom:4px"></div>'
        + '<div id="tierSub_'+tier+'" style="font-size:12px;color:var(--muted);margin-bottom:14px"></div>'
        + '<ul style="margin:0;padding-left:16px;font-size:13px;color:var(--muted);line-height:1.8">'
        + meta.features.map(f => '<li>'+f+'</li>').join('')
        + '</ul>'
        + '<div id="tierSelect_'+tier+'" style="margin-top:14px;padding:7px 0;border-radius:6px;font-size:13px;font-weight:700;text-align:center;border:2px solid '+meta.color+';color:'+meta.color+'">Select Plan</div>'
        + '</div>'
      ).join('')
    + '</div>'

    // ── FREE lane, visible next to the paid tiers (owner order 2026-07-23:
    // the free option was buried at the very bottom of the page) ──
    + '<div class="panel" style="margin-bottom:24px;display:flex;gap:14px;flex-wrap:wrap;align-items:center;justify-content:space-between;border:1px solid rgba(16,185,129,0.4)">'
    + '<div style="flex:1;min-width:220px"><span style="font-weight:800;color:#10b981">FREE — $0</span> '
    + '<span style="color:var(--muted);font-size:13px">· 1 portfolio · daily Buy/Sell/Hold signals to your inbox · no card required</span></div>'
    + '<button onclick="var el=document.getElementById(\'freeEmail\');if(el){el.scrollIntoView({behavior:\'smooth\',block:\'center\'});setTimeout(function(){el.focus()},600);}" '
    + 'style="background:rgba(16,185,129,0.15);color:#10b981;border:1px solid #10b981;border-radius:8px;padding:10px 18px;font-weight:700;cursor:pointer">Create free account ↓</button>'
    + '</div>'

    // ── Referral code ──
    + '<div class="panel" style="margin-bottom:24px">'
    + '<h3 style="margin-bottom:12px">Have a Referral Code?</h3>'
    + '<div style="display:flex;gap:10px;flex-wrap:wrap">'
    + '<input id="refInput" type="text" placeholder="AIS-XXXXXXXX" maxlength="20" '
    + 'style="flex:1;min-width:160px;background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:10px 14px;color:var(--fg);font-size:14px;font-family:monospace;text-transform:uppercase" '
    + 'value="'+escapeHtml(urlRef)+'" oninput="this.value=this.value.toUpperCase()">'
    + '<button onclick="applyRefCode()" style="background:var(--blue);color:#fff;border:none;border-radius:8px;padding:10px 20px;font-weight:700;cursor:pointer;white-space:nowrap">Apply Code</button>'
    + '</div>'
    + '<div id="refMsg" style="margin-top:10px;font-size:13px"></div>'
    + '</div>'

    // ── Subscribe box ──
    + '<div class="sales-hero"><div class="sales-hero-left">'
    + '<h2 style="font-size:28px;letter-spacing:-0.5px">YOUR PORTFOLIO. YOUR STOCKS.</h2>'
    + '<p style="color:var(--muted);font-size:15px">Pick up to 50 AI &amp; Quantum stocks. Daily, weekly, and monthly bots. Custom news feed. Monthly statements you can download.</p>'
    + '<div id="activePriceLabel" style="color:var(--blue);font-weight:700;font-size:15px"></div>'
    + '</div><div class="sales-hero-right">'
    + '<h3>Subscribe with Stripe</h3>'
    + '<div id="paypalFormWrap"></div>'
    + '<div class="powered">SECURED BY STRIPE</div>'
    + '</div></div>'

    // ── Feature grid ──
    + '<div class="sales-strip"><div><h3>Any Sector. Any Stocks. Any News.</h3>'
    + '<p>Tech, biotech, energy, finance, defense, REITs — pick the sectors that matter; we pull the news.</p></div>'
    + '<span class="signal signal-buy" style="font-size:11px;padding:6px 14px">15+ SECTORS</span></div>'
    + '<h3>What\'s Included</h3><div class="grid grid-3">'
    + [['Up to 50 stocks','Any sector, any exchange. NYSE, NASDAQ, plus custom tickers.'],
       ['BOT13 + 4 more','The daily bot that only trades on a real edge — and holds cash otherwise — runs on your picks, plus weekly, monthly, and two benchmarks for context.'],
       ['Daily Buy/Sell/Hold','Composite signals on every stock you picked.'],
       ['Custom news feed','Pick the sectors. We curate, dedupe, deliver.'],
       ['Downloadable monthly statements','A bank-statement PDF: your bots’ daily trades and monthly P&L.'],
       ['One login, all sites','Syndicate plan includes all 3 platforms.']].map(p =>
         '<div class="card"><h3 style="color:var(--blue);margin-bottom:8px">✓ '+p[0]+'</h3>'
         + '<p style="color:var(--muted);font-size:13px;margin:0">'+p[1]+'</p></div>').join('')
    + '</div>'
    + '<div class="panel" style="margin-top:24px">'
    + '<p style="color:var(--muted);font-size:13px;margin:0 0 8px 0">Built by an operator who runs the same system on his own portfolio. Cancel anytime — managed through your Stripe billing portal. Questions? <a href="#" onclick="chatbotOpen();return false;" style="color:var(--blue)">Open a support ticket ↓</a></p>'
    + '<p style="font-size:13px;margin:0">Refer a friend → they get <strong style="color:var(--blue)">50% off their first month</strong> or <strong style="color:var(--blue)">$100 off annual</strong> and you earn a <strong style="color:var(--blue)">$35 bill credit</strong>.</p>'
    + '</div>'

    // ── Start free (entry option, at the bottom) ──
    + '<div class="section-head" style="margin-top:30px"><h3>Prefer to start free?</h3></div>'
    // ── FREE tier ──
    + '<div class="panel" style="margin-bottom:16px;border:1px solid var(--border)">'
    + '<div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:16px">'
    + '<div style="flex:1 1 240px">'
    + '<div style="font-size:11px;font-weight:700;letter-spacing:1.5px;color:var(--muted);margin-bottom:6px;text-transform:uppercase">FREE</div>'
    + '<div style="font-size:26px;font-weight:800;color:var(--fg)">$0</div>'
    + '<div style="display:inline-flex;align-items:center;gap:6px;background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.35);border-radius:6px;padding:4px 10px;margin:8px 0 6px 0">'
    + '<span style="color:#10b981;font-weight:700;font-size:13px">✓ 1 Portfolio Included</span></div>'
    + '<div style="font-size:13px;color:var(--muted);margin-top:4px">Start free with your own portfolio tracker. Get daily Buy/Hold/Sell signals straight to your inbox and see exactly how Bot13 trades every market day.</div>'
    + '</div>'
    + '<div style="flex:1 1 240px;min-width:0">'
    + '<input id="freeEmail" type="email" placeholder="Enter your email" '
    + 'style="width:100%;box-sizing:border-box;background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:10px 14px;color:var(--fg);font-size:14px;margin-bottom:8px">'
    + '<input id="freePassword" type="password" placeholder="Create a password (8+ characters)" minlength="8" '
    + 'style="width:100%;box-sizing:border-box;background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:10px 14px;color:var(--fg);font-size:14px;margin-bottom:8px">'
    + '<div class="cf-turnstile" data-sitekey="0x4AAAAAADs-8zs2xr2GKeWV" data-theme="dark" style="margin-bottom:8px"></div>'
    + '<button onclick="gyFreeSignup()" style="width:100%;background:var(--surface2);color:var(--fg);border:1px solid var(--border);border-radius:8px;padding:10px 0;font-weight:700;cursor:pointer;font-size:14px">Create Free Account →</button>'
    + '<div id="freeMsg" style="font-size:12px;margin-top:6px;min-height:16px"></div>'
    + '</div></div></div>'

    ;

  GY_CYCLE      = 'monthly';
  GY_TIER       = 'member';
  GY_REF        = '';
  GY_VALID      = false;
  GY_ADMIN_CODE = '';
  GY_ADMIN_TIER = 'insider';
  updateGyPricing();
  if (urlRef) { const inp = $('refInput'); if (inp) inp.value = urlRef.toUpperCase(); applyRefCode(); }
  // Resume a checkout that was interrupted by account creation (2026-07-23).
  gyResumeCheckout();
}

async function gyFreeSignup() {
  const inp = $('freeEmail');
  const pwInp = $('freePassword');
  const msg = $('freeMsg');
  if (!inp || !msg) return;
  const email = inp.value.trim();
  const password = pwInp ? pwInp.value : '';
  if (!email || !email.includes('@')) {
    msg.innerHTML = '<span style="color:var(--red)">Please enter a valid email.</span>';
    return;
  }
  if (!password || password.length < 8) {
    msg.innerHTML = '<span style="color:var(--red)">Choose a password (at least 8 characters).</span>';
    return;
  }
  msg.innerHTML = '<span style="color:var(--muted)">Creating your free account…</span>';
  try {
    const r = await fetch('https://wallstbots-backend-868128114349.us-east1.run.app/auth/signup-free', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, platform: 'aistocks', turnstile_token: (window.turnstile ? turnstile.getResponse() : '') })
    });
    const data = await r.json().catch(() => ({}));
    if (r.ok && data.success) {
      if (data.access_token) {
        // Real account created + logged in — drop them into their dashboard.
        setJWT(data.access_token);
        if (typeof updateNavAuth === 'function') updateNavAuth();
        msg.innerHTML = '<span style="color:#10b981;font-weight:700">✓ Account created! Taking you to your dashboard…</span>';
        location.hash = '#/my-picks';
      } else {
        // Account made but email confirmation required before login.
        msg.innerHTML = '<span style="color:#10b981;font-weight:700">✓ Account created! Check your inbox to confirm your email, then log in.</span>';
      }
      inp.value = ''; if (pwInp) pwInp.value = '';
    } else {
      const detail = data.detail || 'Something went wrong';
      msg.innerHTML = '<span style="color:var(--muted)">' + escapeHtml(detail) + ' — try again or <a href="#" onclick="chatbotOpen();return false;" style="color:var(--blue)">open a support ticket</a></span>';
    }
  } catch (_) {
    msg.innerHTML = '<span style="color:var(--muted)">Could not connect — check your connection.</span>';
  }
}

function setGyTier(tier) { GY_TIER = tier; updateGyPricing(); }
function setGyCycle(cycle) { GY_CYCLE = cycle; updateGyPricing(); }

function updateGyPricing() {
  const annual = GY_CYCLE === 'annual';
  const hasRef = GY_VALID;
  const suffix = annual ? '/yr' : '/mo';

  ['cycleMonthly','cycleAnnual'].forEach(id => {
    const el = $(id); if (!el) return;
    const active = (id === 'cycleAnnual') === annual;
    el.style.background = active ? 'var(--blue)' : 'transparent';
    el.style.color = active ? '#fff' : 'var(--muted)';
  });

  Object.entries(PRICING).forEach(([tier, prices]) => {
    const price    = annual ? prices.annual  : prices.monthly;
    const refPrice = annual ? (price - 100).toFixed(2) : (price * 0.5).toFixed(2);
    const isSelected = tier === GY_TIER;
    const meta = TIER_META[tier];
    const card  = $('tierCard_'+tier);
    const prEl  = $('tierPrice_'+tier);
    const subEl = $('tierSub_'+tier);
    const selEl = $('tierSelect_'+tier);
    if (!card) return;
    card.style.borderColor = isSelected ? meta.color : (meta.popular ? meta.color : 'var(--border)');
    card.style.background  = isSelected ? 'rgba(0,0,0,0.15)' : 'var(--surface)';
    if (prEl) {
      if (hasRef) {
        prEl.innerHTML = '<span style="text-decoration:line-through;color:var(--muted);font-size:18px">$'+price.toFixed(2)+'</span> $'+refPrice;
        prEl.style.color = '#10b981';
      } else { prEl.textContent = '$'+price.toFixed(2); prEl.style.color = ''; }
    }
    if (subEl) subEl.textContent = hasRef
      ? (annual ? '$100 off — then $'+price.toFixed(2)+suffix : '50% off first month — then $'+price.toFixed(2)+suffix)
      : suffix + ' · cancel anytime';
    if (selEl) {
      selEl.textContent      = isSelected ? '✓ Selected' : 'Select Plan';
      selEl.style.background = isSelected ? meta.color : 'transparent';
      selEl.style.color      = isSelected ? '#000'     : meta.color;
    }
  });

  const tierPrices = PRICING[GY_TIER];
  const price  = annual ? tierPrices.annual  : tierPrices.monthly;
  const refPrice = annual ? (price - 100).toFixed(2) : (price * 0.5).toFixed(2);
  const lbl = $('activePriceLabel');
  if (lbl) lbl.textContent = hasRef
    ? '$' + refPrice + suffix + ' today — ' + TIER_META[GY_TIER].label + ' plan (referral applied!)'
    : '$' + price.toFixed(2) + suffix + ' — ' + TIER_META[GY_TIER].label + ' plan · cancel anytime';
  renderPaypalForm();
}

async function applyRefCode() {
  const inp = $('refInput'), msg = $('refMsg');
  if (!inp || !msg) return;
  const code = inp.value.trim().toUpperCase();
  if (!code) { msg.innerHTML = ''; return; }
  msg.innerHTML = '<span style="color:var(--muted)">Validating…</span>';
  try {
    const r = await fetch('https://wallstbots-backend-868128114349.us-east1.run.app/subscriptions/validate-referral?code='+encodeURIComponent(code));
    const d = await r.json();
    if (d.valid && d.type === 'admin_lifetime') {
      GY_ADMIN_CODE = code;
      GY_ADMIN_TIER = d.tier || 'insider';
      GY_REF = ''; GY_VALID = false;
      msg.innerHTML = '<span style="color:#ff8c00;font-weight:700">Admin code verified — free lifetime ' + GY_ADMIN_TIER.toUpperCase() + ' access. Enter your details below to claim.</span>';
      renderPaypalForm();
    } else if (d.valid) {
      GY_ADMIN_CODE = '';
      GY_REF = d.code; GY_VALID = true;
      msg.innerHTML = '<span style="color:#10b981;font-weight:700">✓ Referral code applied! '
        + (GY_CYCLE === 'annual' ? '$100 off your annual plan.' : '50% off your first month.')
        + '</span>';
    } else {
      GY_ADMIN_CODE = '';
      GY_REF = ''; GY_VALID = false;
      msg.innerHTML = '<span style="color:var(--red)">✗ '+(d.message||'Invalid code.')+'</span>';
    }
  } catch (_) {
    GY_ADMIN_CODE = '';
    GY_REF = ''; GY_VALID = false;
    msg.innerHTML = '<span style="color:var(--muted)">Could not validate — check your connection.</span>';
  }
  updateGyPricing();
}

function renderPaypalForm() {
  // Renamed internally but kept as renderPaypalForm() so all callers still work.
  // Now renders a Stripe Checkout button instead of a PayPal form.
  const wrap = $('paypalFormWrap'); if (!wrap) return;

  if (GY_ADMIN_CODE) {
    wrap.innerHTML =
      '<div style="background:var(--surface2);border-radius:12px;padding:24px;max-width:360px">'
      + '<p style="color:#ff8c00;font-weight:700;margin-bottom:16px">Free Lifetime ' + GY_ADMIN_TIER.toUpperCase() + ' Access</p>'
      + '<div style="margin-bottom:12px"><label style="color:var(--muted);font-size:12px;display:block;margin-bottom:4px">EMAIL</label>'
      + '<input type="email" id="admin-email" placeholder="you@example.com" style="width:100%;background:var(--surface);border:1px solid var(--border);color:var(--fg);border-radius:8px;padding:10px 14px;font-size:14px;box-sizing:border-box"></div>'
      + '<div style="margin-bottom:16px"><label style="color:var(--muted);font-size:12px;display:block;margin-bottom:4px">PASSWORD</label>'
      + '<input type="password" id="admin-password" placeholder="At least 8 characters" style="width:100%;background:var(--surface);border:1px solid var(--border);color:var(--fg);border-radius:8px;padding:10px 14px;font-size:14px;box-sizing:border-box"></div>'
      + '<button onclick="claimAdminAccess()" style="width:100%;background:var(--blue);color:#fff;border:none;border-radius:8px;padding:12px;font-size:15px;font-weight:700;cursor:pointer">Claim Free ' + GY_ADMIN_TIER.toUpperCase() + ' Access</button>'
      + '<p id="admin-claim-msg" style="margin-top:10px;font-size:13px;color:var(--muted)"></p>'
      + '</div>';
    return;
  }

  const annual     = GY_CYCLE === 'annual';
  const ref        = GY_VALID ? GY_REF : '';
  const tierPrices = PRICING[GY_TIER];
  const price      = annual ? tierPrices.annual : tierPrices.monthly;
  const base       = price.toFixed(2);
  const refPrice   = annual ? (price - 100).toFixed(2) : (price * 0.5).toFixed(2);
  const btnTxt     = ref
    ? 'Subscribe — $' + refPrice + ' today, then $' + base + (annual ? '/yr' : '/mo')
    : 'Subscribe — $' + base + (annual ? '/yr' : '/mo');

  // NEW-VISITOR LANE (owner order 2026-07-23): a logged-out visitor used to hit
  // "Your session expired. Please log in again" — a fake error to someone who
  // never had a session — then had to find the signup tab, confirm email, log
  // in, come BACK here and re-pick the plan. Now: one honest button that saves
  // the chosen plan, sends them to the signup form, and checkout RESUMES
  // automatically the moment their account is live (see gyResumeCheckout).
  if (!getJWT()) {
    wrap.innerHTML =
      '<button onclick="gyGoSignup()" '
      + 'style="width:100%;background:var(--blue);color:#fff;border:none;border-radius:8px;padding:14px;font-size:15px;font-weight:700;cursor:pointer">'
      + 'Create account & subscribe — ' + (ref ? '$' + refPrice : '$' + base) + (annual ? '/yr' : '/mo') + '</button>'
      + '<div style="font-size:12px;margin-top:8px;color:var(--muted);text-align:center">Takes ~30 seconds. Your '
      + TIER_META[GY_TIER].label + ' plan is remembered — checkout continues automatically after signup.</div>'
      + '<div style="font-size:12px;margin-top:6px;color:var(--muted);text-align:center">Already a member? '
      + '<a href="/login.html" style="color:var(--blue)">Log in</a></div>';
    return;
  }

  wrap.innerHTML =
    '<button id="stripeCheckoutBtn" onclick="startStripeCheckout()" '
    + 'style="width:100%;background:var(--blue);color:#fff;border:none;border-radius:8px;padding:14px;font-size:15px;font-weight:700;cursor:pointer;transition:opacity 0.15s">'
    + btnTxt + '</button>'
    + '<div style="font-size:12px;margin-top:8px;color:var(--muted);text-align:center">'
    + (ref ? 'Referral discount applied. Renews at $'+base+(annual?'/yr':'/mo')+' afterwards.' : 'Renews every '+(annual?'year':'month')+' · cancel anytime')
    + '</div>';
    // NOTE: "SECURED BY STRIPE" is rendered once in the panel header (class
    // "powered"); do NOT add a second copy here (caused a doubled label).
}

// Returns true if a usable JWT is in place (refreshing it first if expired),
// false if the user needs to log in again. Prevents the "Token expired"
// checkout dead-end: if the access token is stale but a refresh token exists,
// we silently mint a new access token via /auth/refresh.
async function ensureFreshJWT() {
  let jwt = getJWT();
  // Decode the JWT exp claim; treat as expired if within 30s of expiry.
  function isExpired(tok) {
    try {
      const payload = JSON.parse(atob(tok.split('.')[1]));
      return !payload.exp || (payload.exp * 1000) < (Date.now() + 30000);
    } catch (e) { return true; }
  }
  if (jwt && !isExpired(jwt)) return true;

  const refresh = (function(){ try {
    return localStorage.getItem('aistocks_refresh_token')
        || localStorage.getItem('aistocks_refresh')
        || localStorage.getItem('wallstbots_refresh');
  } catch(e){ return null; } })();
  if (!refresh) return false;

  try {
    const rr = await fetch(API_BASE + '/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!rr.ok) return false;
    const rd = await rr.json();
    if (rd.access_token) {
      setJWT(rd.access_token);
      if (rd.refresh_token) { try { localStorage.setItem('aistocks_refresh_token', rd.refresh_token); } catch(e) {} }
      return true;
    }
    return false;
  } catch (e) { return false; }
}

// Save the chosen plan and hand off to the signup form (which owns the captcha).
function gyGoSignup() {
  try {
    localStorage.setItem('gy_pending', JSON.stringify(
      { t: GY_TIER, c: GY_CYCLE, r: GY_VALID ? GY_REF : '' }));
  } catch (e) {}
  window.location.href = '/login.html#signup';
}

// Called on get-yours load: a pending plan + a live login = resume checkout
// automatically (after signup->email confirm->auto-login, or a normal login).
function gyResumeCheckout() {
  let pending = null;
  try { pending = JSON.parse(localStorage.getItem('gy_pending') || 'null'); } catch (e) {}
  if (!pending || !getJWT()) return false;
  try { localStorage.removeItem('gy_pending'); } catch (e) {}
  if (pending.t && PRICING[pending.t]) GY_TIER = pending.t;
  if (pending.c === 'annual' || pending.c === 'monthly') GY_CYCLE = pending.c;
  if (pending.r) { GY_REF = pending.r; GY_VALID = true; }
  updateGyPricing();
  const wrap = $('paypalFormWrap');
  if (wrap) wrap.innerHTML =
    '<div style="text-align:center;color:var(--muted);font-size:14px;padding:14px 0">'
    + '✓ Account ready — resuming your ' + (TIER_META[GY_TIER] || {}).label
    + ' checkout…</div>';
  setTimeout(startStripeCheckout, 400);
  return true;
}

async function startStripeCheckout() {
  const btn = $('stripeCheckoutBtn');
  if (btn) { btn.disabled = true; btn.textContent = 'Redirecting to checkout…'; }

  // Make sure we have a non-expired token before calling checkout.
  const ok = await ensureFreshJWT();
  if (!ok) {
    alert('Your session expired. Please log in again, then return here to subscribe.');
    if (btn) { btn.disabled = false; btn.textContent = 'Subscribe'; }
    window.location.href = '/login.html';
    return;
  }
  const jwt = getJWT();

  try {
    const r = await fetch(API_BASE + '/stripe/create-checkout', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + jwt, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tier:     GY_TIER,
        cycle:    GY_CYCLE,
        platform: 'aistocks',
        ref_code: GY_VALID ? GY_REF : '',
      }),
    });
    const d = await r.json();
    if (d.url) {
      window.location.href = d.url;
    } else if (r.status === 401 || /token|expired|auth/i.test(d.detail || '')) {
      // Token was rejected — send to login rather than a dead-end error.
      alert('Your session expired. Please log in again, then return here to subscribe.');
      if (btn) { btn.disabled = false; btn.textContent = 'Subscribe'; }
      window.location.href = '/login.html';
    } else {
      throw new Error(d.detail || 'Could not create checkout session');
    }
  } catch(e) {
    alert('Checkout error: ' + (e.message || 'Please try again.'));
    if (btn) { btn.disabled = false; btn.textContent = 'Subscribe'; }
  }
}


// ================================================================
// SETUP — post-payment account activation (arrives via email link)
// ================================================================
function renderSetup() {
  const params = new URLSearchParams(location.hash.split('?')[1] || '');
  const token  = params.get('token') || '';
  const app    = document.getElementById('app');

  // If already logged in, send to dashboard
  if (isLoggedIn()) {
    app.innerHTML = '<div class="panel" style="text-align:center;padding:48px 24px">'
      + '<p style="color:var(--muted);font-size:15px">You are already set up.</p>'
      + '<a href="#/my-tracker" class="btn btn-primary" style="margin-top:16px">Go to My Tracker</a></div>';
    return;
  }

  if (!token) {
    app.innerHTML = '<div class="panel" style="text-align:center;padding:48px 24px">'
      + '<h2 style="color:var(--red)">Invalid Setup Link</h2>'
      + '<p style="color:var(--muted)">This link is missing the setup token. Check your email for the original setup link, or open a support ticket in the chat below.</p></div>';
    return;
  }

  app.innerHTML = '<div class="panel" style="max-width:480px;margin:48px auto">'
    + '<h2 style="margin-bottom:4px">Set Up Your Account</h2>'
    + '<p style="color:var(--muted);font-size:13px;margin-bottom:24px">Choose a password to access your private tracker dashboard.</p>'
    + '<form id="setupForm">'
    + '<div style="margin-bottom:16px"><label style="color:var(--muted);font-size:12px;display:block;margin-bottom:6px">PASSWORD</label>'
    + '<input type="password" id="setupPw" placeholder="At least 8 characters" required minlength="8" style="width:100%;background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:10px 14px;font-size:14px;box-sizing:border-box">'
    + '</div>'
    + '<div style="margin-bottom:24px"><label style="color:var(--muted);font-size:12px;display:block;margin-bottom:6px">CONFIRM PASSWORD</label>'
    + '<input type="password" id="setupPw2" placeholder="Repeat password" required minlength="8" style="width:100%;background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:10px 14px;font-size:14px;box-sizing:border-box">'
    + '</div>'
    + '<div id="setupErr" style="color:var(--red);font-size:13px;margin-bottom:12px;display:none"></div>'
    + '<button type="submit" class="btn btn-primary" style="width:100%">Activate My Account</button>'
    + '</form></div>';

  const form = document.getElementById('setupForm');
  if (!form) return;
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const pw  = document.getElementById('setupPw').value;
    const pw2 = document.getElementById('setupPw2').value;
    const err = document.getElementById('setupErr');
    err.style.display = 'none';
    if (pw !== pw2) { err.textContent = 'Passwords do not match.'; err.style.display = 'block'; return; }
    const btn = form.querySelector('button[type="submit"]');
    btn.textContent = 'Activating...'; btn.disabled = true;
    try {
      const result = await apiFetch('/auth/setup-account', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password: pw, platform: 'aistocks' }),
      });
      setJWT(result.access_token);
      updateNavAuth();
      location.hash = '#/my-picks';
    } catch (ex) {
      err.textContent = ex.message || 'Setup failed — try again or open a support ticket in the chat below.';
      err.style.display = 'block';
      btn.textContent = 'Activate My Account'; btn.disabled = false;
    }
  });
}


// ================================================================
// MY TRACKER — private per-user dashboard
// ================================================================
async function renderMyTracker() {
  const app = document.getElementById('app');
  if (!isLoggedIn()) {
    app.innerHTML = '<div class="panel" style="text-align:center;padding:48px 24px">'
      + '<p style="color:var(--muted)">You need to be logged in to view your tracker.</p>'
      + '<a href="#/get-yours" class="btn btn-primary" style="margin-top:16px">Get Your Tracker</a></div>';
    return;
  }

  app.innerHTML = '<div class="loading">Loading your tracker...</div>';
  try {
    const result = await apiFetch('/user/tracker/state?platform=aistocks', { headers: authHeaders() });
    const data   = result.data;

    if (!data) {
      app.innerHTML = '<div class="panel" style="text-align:center;padding:48px 24px">'
        + '<h3>Your tracker is being set up</h3>'
        + '<p style="color:var(--muted);font-size:13px;margin-top:8px">Your custom data will appear after tonight\'s nightly run (usually by 6 AM ET). Check back soon!</p>'
        + '<a href="#/my-picks" class="btn btn-primary" style="margin-top:20px">Review My Picks</a></div>';
      return;
    }

    // Render using the same fund + race UI as the public tracker
    STATE.userFunds = data.funds || {};
    const funds = data.funds || {};
    const snaps = data.snapshots || [];
    const lb    = data.leaderboards || {};
    const sc    = data.starting_capital || 50000;

    let html = '<section class="section"><h2 class="section-title">My Tracker</h2>'
      + '<p style="color:var(--muted);font-size:13px;margin-bottom:20px">Last updated: '
      + (data.last_refresh ? data.last_refresh.replace('T', ' ').slice(0, 16) + ' UTC' : 'N/A')
      + ' &nbsp;|&nbsp; <a href="#/my-picks" style="color:var(--blue)">Manage My Picks</a>'
      + ' &nbsp;|&nbsp; <button onclick="doLogout()" style="background:none;border:none;color:var(--muted);cursor:pointer;font-size:13px;text-decoration:underline">Log Out</button></p>';

    // Fund cards
    html += '<div class="grid grid-3" style="margin-bottom:28px">';
    FUND_ORDER.forEach(fid => {
      const f = funds[fid]; if (!f) return;
      const v = f.value;
      const sign = v.pnl >= 0 ? '+' : '';
      html += '<div class="card">'
        + '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">'
        + '<span style="background:' + f.color + ';color:#000;font-weight:700;font-size:11px;padding:3px 8px;border-radius:5px">' + f.name + '</span>'
        + '<span style="color:var(--muted);font-size:11px">' + f.current_strategy + '</span></div>'
        + '<div style="font-size:22px;font-weight:700;margin-bottom:2px">' + fmt$0(v.total) + '</div>'
        + '<div style="font-size:13px;color:' + (v.pnl >= 0 ? 'var(--green)' : 'var(--red)') + '">'
        + fmt$0(v.pnl) + ' (' + fmtPct(v.pnl_pct) + ')</div>'
        + '<div style="font-size:12px;color:var(--muted);margin-top:4px">Today: '
        + fmtPct(v.day_pct) + '</div></div>';
    });
    html += '</div>';

    // Leaderboard
    if (lb.all && lb.all.length) {
      html += '<div class="panel" style="margin-bottom:24px"><h3 style="margin-bottom:14px">All-Time Leaderboard</h3>';
      lb.all.forEach((row, i) => {
        const f = funds[row.fund]; if (!f) return;
        const sign = row.all_pnl >= 0 ? '+' : '';
        html += '<div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--border)">'
          + '<span style="color:var(--muted);font-size:12px;width:20px">#' + (i+1) + '</span>'
          + '<span style="background:' + f.color + ';color:#000;font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px">' + f.name + '</span>'
          + '<span style="flex:1;color:var(--muted);font-size:12px">' + f.current_strategy + '</span>'
          + '<span style="font-weight:700;color:' + (row.all_pnl >= 0 ? 'var(--green)' : 'var(--red)') + '">'
          + sign + row.all_pct.toFixed(1) + '%</span>'
          + '<span class="signal signal-' + (row.overall_grade.startsWith('A') ? 'buy' : row.overall_grade === 'F' ? 'sell' : 'hold') + '" style="font-size:10px;padding:2px 7px">'
          + row.overall_grade + '</span></div>';
      });
      html += '</div>';
    }

    // Top holdings from EQUALIZER (equal weight = cleanest view)
    const eq = funds['equalizer'];
    if (eq && eq.value && eq.value.positions && eq.value.positions.length) {
      const positions = eq.value.positions.slice(0, 20);
      html += '<div class="panel"><h3 style="margin-bottom:14px">My Holdings (Top 20)</h3>'
        + '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px">';
      positions.forEach(p => {
        const sign = p.day_pnl >= 0 ? '+' : '';
        html += '<div class="card" style="padding:10px 12px">'
          + '<div style="font-weight:700;font-size:14px;color:var(--blue)">' + p.symbol + '</div>'
          + '<div style="font-size:13px;margin:4px 0">$' + p.price.toFixed(2) + '</div>'
          + '<div style="font-size:12px;color:' + (p.day_pnl >= 0 ? 'var(--green)' : 'var(--red)') + '">'
          + sign + p.day_pct.toFixed(1) + '% today</div></div>';
      });
      html += '</div></div>';
    }

    html += '</section>';
    app.innerHTML = html;

  } catch (ex) {
    if (ex.message && ex.message.includes('401')) {
      clearJWT(); updateNavAuth();
      app.innerHTML = '<div class="panel" style="text-align:center;padding:48px 24px">'
        + '<p style="color:var(--muted)">Your session expired. Please log in again.</p>'
        + '<a href="#/get-yours" class="btn btn-primary" style="margin-top:16px">Get Yours</a></div>';
    } else {
      app.innerHTML = '<div class="panel" style="text-align:center;padding:48px 24px">'
        + '<p style="color:var(--red)">Could not load your tracker: ' + (ex.message || 'unknown error') + '</p>'
        + '<button class="btn btn-primary" onclick="renderMyTracker()" style="margin-top:16px">Retry</button></div>';
    }
  }
}

window.doLogout = function() {
  clearJWT();
  updateNavAuth();
  location.hash = '#/';
};


// ================================================================
// MY PICKS — pick / manage user's stock universe
// ================================================================
async function renderMyPicks() {
  const app = document.getElementById('app');
  if (!isLoggedIn()) {
    app.innerHTML = '<div class="panel" style="text-align:center;padding:48px 24px">'
      + '<p style="color:var(--muted)">You need to be logged in to manage picks.</p>'
      + '<a href="#/get-yours" class="btn btn-primary" style="margin-top:16px">Get Your Tracker</a></div>';
    return;
  }

  app.innerHTML = '<div class="loading">Loading your picks...</div>';
  try {
    const result = await apiFetch('/user/stocks', { headers: authHeaders() });
    const picks  = result.picks || [];

    let html = '<section class="section"><h2 class="section-title">My Stock Picks</h2>'
      + '<p style="color:var(--muted);font-size:13px;margin-bottom:20px">'
      + picks.length + ' of 50 stocks selected. The nightly bot run uses exactly these tickers.'
      + ' &nbsp;|&nbsp; <a href="#/my-tracker" style="color:var(--blue)">View My Tracker</a></p>';

    // Search box
    html += '<div class="panel" style="margin-bottom:20px">'
      + '<h3 style="margin-bottom:12px">Add a Stock</h3>'
      + '<div style="display:flex;gap:10px">'
      + '<input type="text" id="picksSearch" placeholder="Search by ticker or name..." style="flex:1;background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:10px 14px;font-size:14px">'
      + '<button id="picksSearchBtn" class="btn btn-primary">Search</button></div>'
      + '<div id="picksResults" style="margin-top:12px"></div></div>';

    // Current picks
    if (picks.length) {
      html += '<div class="panel"><h3 style="margin-bottom:14px">Current Picks</h3>'
        + '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px">';
      picks.forEach(p => {
        html += '<div class="card" style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px">'
          + '<div><div style="font-weight:700;color:var(--blue)">' + p.ticker + '</div>'
          + '<div style="font-size:11px;color:var(--muted)">' + (p.company_name || '') + '</div></div>'
          + '<button onclick="removePick(\'' + p.ticker + '\')" style="background:none;border:none;color:var(--muted);cursor:pointer;font-size:18px;line-height:1" title="Remove">&times;</button></div>';
      });
      html += '</div></div>';
    } else {
      html += '<div class="panel" style="text-align:center;padding:24px"><p style="color:var(--muted)">No stocks picked yet. Search above to add up to 50 tickers.</p></div>';
    }

    html += '</section>';
    app.innerHTML = html;

    // Wire search
    const searchInput = document.getElementById('picksSearch');
    const searchBtn   = document.getElementById('picksSearchBtn');
    const resultsDiv  = document.getElementById('picksResults');

    async function doSearch() {
      const q = searchInput ? searchInput.value.trim() : '';
      if (!q || !resultsDiv) return;
      resultsDiv.innerHTML = '<span style="color:var(--muted);font-size:13px">Searching...</span>';
      try {
        const r = await apiFetch('/stocks/search?q=' + encodeURIComponent(q) + '&limit=8', { headers: authHeaders() });
        const results = r.results || [];
        if (!results.length) { resultsDiv.innerHTML = '<span style="color:var(--muted);font-size:13px">No results found.</span>'; return; }
        resultsDiv.innerHTML = results.map(s =>
          '<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border)">'
          + '<div><span style="font-weight:700;color:var(--blue)">' + s.ticker + '</span>'
          + ' <span style="color:var(--muted);font-size:12px">' + (s.name || '') + '</span></div>'
          + '<button onclick="addPick(\'' + s.ticker + '\',\'' + (s.name||'').replace(/'/g,"\\'") + '\')" class="btn btn-primary" style="padding:4px 14px;font-size:12px">+ Add</button></div>'
        ).join('');
      } catch(ex) {
        resultsDiv.innerHTML = '<span style="color:var(--red);font-size:13px">Search failed: ' + ex.message + '</span>';
      }
    }

    if (searchBtn) searchBtn.addEventListener('click', doSearch);
    if (searchInput) searchInput.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

  } catch(ex) {
    app.innerHTML = '<div class="panel" style="text-align:center;padding:48px 24px">'
      + '<p style="color:var(--red)">Could not load picks: ' + (ex.message || '') + '</p>'
      + '<button class="btn btn-primary" onclick="renderMyPicks()" style="margin-top:16px">Retry</button></div>';
  }
}

window.addPick = async function(ticker, name) {
  try {
    await apiFetch('/user/stocks', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ tickers: [{ ticker, company_name: name }] }),
    });
    renderMyPicks();
  } catch(ex) {
    alert('Could not add ' + ticker + ': ' + ex.message);
  }
};

window.removePick = async function(ticker) {
  if (!confirm('Remove ' + ticker + ' from your tracker?')) return;
  try {
    await apiFetch('/user/stocks/' + ticker, { method: 'DELETE', headers: authHeaders() });
    renderMyPicks();
  } catch(ex) {
    alert('Could not remove ' + ticker + ': ' + ex.message);
  }
};


async function claimAdminAccess() {
  const email    = (document.getElementById('admin-email')    || {}).value || '';
  const password = (document.getElementById('admin-password') || {}).value || '';
  const msgEl    = document.getElementById('admin-claim-msg');
  if (!email || !password) { if (msgEl) msgEl.textContent = 'Please fill in both fields.'; return; }
  if (password.length < 8)  { if (msgEl) msgEl.textContent = 'Password must be at least 8 characters.'; return; }
  if (msgEl) msgEl.textContent = 'Claiming…';
  try {
    const r = await fetch('https://wallstbots-backend-868128114349.us-east1.run.app/auth/signup-with-admin-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: GY_ADMIN_CODE, email, password, platform: 'aistocks' })
    });
    const d = await r.json();
    if (!r.ok) { if (msgEl) msgEl.textContent = d.detail || 'Error — try again.'; return; }
    if (d.access_token) localStorage.setItem('access_token', d.access_token);
    location.hash = '#/thanks-admin';
  } catch(e) {
    if (msgEl) msgEl.textContent = 'Network error — please try again.';
  }
}

function renderThanksAdmin() {
  const tierLabel = GY_ADMIN_TIER.toUpperCase();
  const upsell = GY_ADMIN_TIER === 'syndicate' ? '' :
    '<div class="panel" style="margin-top:24px;border:2px solid var(--blue)">'
    + '<h3 style="color:var(--blue);margin-bottom:8px">Want even more?</h3>'
    + '<p style="color:var(--muted);margin-bottom:16px">Upgrade to <strong style="color:var(--fg)">SYNDICATE</strong> for just <strong style="color:var(--fg)">$30/mo more</strong> and unlock our full signal suite, priority alerts, and exclusive syndicate reports.</p>'
    + '<a class="btn btn-primary" href="#/get-yours">Upgrade to SYNDICATE — $30/mo</a>'
    + '</div>';
  $('app').innerHTML =
    '<section class="hero"><div class="hero-content">'
    + '<h1>You\'re in.</h1>'
    + '<p style="font-size:1.15rem;margin-bottom:8px"><strong style="color:var(--blue)">' + tierLabel + ' FREE · LIFETIME</strong></p>'
    + '<p>Your free lifetime ' + tierLabel + ' access has been activated. Log in now to get started.</p>'
    + '<div class="hero-ctas">'
    + '<a class="btn btn-primary" href="https://aistocks.tech/login.html">Log In →</a>'
    + '</div></div></section>'
    + upsell;
}

// ============ PAGE: THANKS ============
function renderThanks() {
  $('app').innerHTML = '<section class="hero"><div class="hero-content">'
    + '<h1>You\'re in.</h1>'
    + '<p>Your aistocks.tech tracker will be live within 24 hours. Check your email for your setup link.</p>'
    + '<div class="hero-ctas"><a class="btn btn-primary" href="#/">Back to Home</a></div>'
    + '</div></section>'
    + '<div class="panel" style="margin-top:24px;border:2px solid var(--blue)">'
    + '<h3 style="color:var(--blue);margin-bottom:8px">Want a tracker on crypto or sector stocks too?</h3>'
    + '<p style="color:var(--muted);margin-bottom:16px">Your login works on every Level 13 site — add a second tracker for $29.99/mo or $299/yr.</p>'
    + '<a class="btn btn-primary" href="https://bitbot13.tech" target="_blank" rel="noopener" style="margin-right:8px">Visit BitBot13 →</a>'
    + '<a class="btn btn-secondary" href="https://wallstbots.tech" target="_blank" rel="noopener">Visit Wall St. Bots →</a>'
    + '</div>';
}

// ================================================================
// CHATBOT — FAQ engine
// ================================================================
const FAQS = [
  { q: ['price','cost','how much','pricing','member','insider','syndicate'], a: "MEMBER: $49.99/mo or $499/yr (5 portfolios). INSIDER: $69.99/mo or $699/yr (10 portfolios). SYNDICATE: $99.99/mo or $899/yr (up to 25 portfolios, all 3 platforms). FREE tier: 1 portfolio included + daily signals by email at no cost." },
  { q: ['referral','refer','code','discount'], a: "Share your referral code and earn $35 credit per friend who subscribes — automatically applied to your next bill. Your friend gets 50% off their first month or $100 off an annual plan. No cap on referrals." },
  { q: ['cancel','refund','stop'], a: "Cancel anytime through the Stripe billing portal — use the link in your subscription confirmation email, or go to Dashboard → Manage Billing. No further charges after cancellation." },
  { q: ['stocks','tickers','how many','add','holding','what can i add'], a: "Add any Nasdaq/NYSE-listed stock — with a focus on AI, quantum computing, semiconductors, and emerging tech. You can also add any other U.S.-listed ticker. Up to 50 holdings per portfolio. Each gets a $1,000 paper allocation." },
  { q: ['ai','quantum','semiconductor','tech stocks','what can i track'], a: "AI Stocks is built for AI and quantum — NVDA, AMD, INTC, IONQ, QCOM, MSFT, GOOGL, and any emerging tech play. Track the stocks shaping the next wave of computing." },
  { q: ['portfolio','tracker','bot-detail','my portfolio','dashboard'], a: "Your portfolio page shows: your holdings with live P&L, pie chart breakdown, bot signals on each stock, curated AI/quantum news for your picks, and a live leaderboard of all 5 bots competing on your exact stock list." },
  { q: ['news','articles','sources'], a: "We pull from 80+ sources via NewsAPI, dedupe, and filter to the sectors your stocks are in. AI and tech news updated every night." },
  { q: ['bot','bots','strategy','strategies'], a: "5 strategies race on YOUR stock list — and BOT13, the daily bot, keeps winning by refusing to chase a bad trade. It only trades when it sees an edge and sits in cash otherwise — no edge, no trade, no risk — while still beating every other strategy and both market benchmarks. The others (ORACLE weekly, WIZARD monthly, plus EQUALIZER & TITAN benchmarks) are there for context. When you join, BOT13 trades your exact stock list the same way." },
  { q: ['best bot','which bot','top bot','does it work','proof','track record','winning','why bot13','losing'], a: "BOT13 — the daily strategy — is the standout, and here’s WHY it wins: it only trades when it sees a real edge, and sits in cash otherwise. No edge, no trade, no risk — the downside of a quiet day is a quiet day, not a loss. It still beats the other bots and the market (paper-trading results, shown live on the leaderboard, including its day-by-day win/cash record). Join, add your stocks, and copy the bot that won’t bet against you." },
  { q: ['signals','buy','sell','hold'], a: "Every trading day we score every stock on your list — momentum, RSI, MACD, volume, volatility — and label it Strong Buy / Buy / Hold / Sell / Strong Sell." },
  { q: ['report','reports','sunday','weekly'], a: "Every Sunday you get an auto-generated report: each bot's grade, what they bought/sold, why, and what's coming next." },
  { q: ['real money','live trade','execute','broker'], a: "No — these are paper portfolios for research and signals only. We never touch a brokerage account. You see what the bots would do, then decide for yourself." },
  { q: ['mobile','phone','app','iphone','android'], a: "Fully mobile-optimized. Open it in your phone's browser — no app download needed. Your dashboard, portfolio, and all bot data work on any screen size." },
  { q: ['data','privacy','share','sell my'], a: "Your data stays yours. We don't share or sell it. Your tracker runs on a private endpoint — only you see it." },
  { q: ['custom bot','custom strategy','build your own','bespoke','custom plan','custom setup'], a: "Interested in a custom bot or strategy? Fill out a support ticket below and we'll reach out to discuss your setup." },
  { q: ['contact','support','help','email','reach'], a: "Use this chat to open a support ticket anytime — just type 'support ticket' or click the Support button above." },
  { q: ['how long','setup','time','when'], a: "Your tracker is live within 24 hours of checkout. You'll get an email with your private dashboard link." },
];
function botAnswer(input) {
  const q = (input || '').toLowerCase().trim();
  if (!q) return null;
  for (const item of FAQS) {
    if (item.q.some(k => q.includes(k))) return item.a;
  }
  return "I don't have an answer for that one yet — type 'support ticket' to reach the team directly. We'll get back to you within 24 hours.";
}
function chatbotAddMsg(text, who) {
  const body = $('chatbotBody'); if (!body) return;
  const div = document.createElement('div');
  div.className = 'chatbot-msg ' + (who || 'bot');
  div.textContent = text;
  body.appendChild(div);
  body.scrollTop = body.scrollHeight;
}

// ── Support ticket chatbot flow ───────────────────────────────────────────────
let _ticketState = null; // null | 'awaiting_issue' | 'awaiting_email'
let _ticketIssue = '';
function _ticketEmail() {
  const tok = localStorage.getItem('auth_token') || localStorage.getItem('aistocks_jwt');
  if (!tok) return null;
  try { return JSON.parse(atob(tok.split('.')[1])).email || null; } catch { return null; }
}
function _ticketName() {
  const tok = localStorage.getItem('auth_token') || localStorage.getItem('aistocks_jwt');
  if (!tok) return null;
  try {
    const p = JSON.parse(atob(tok.split('.')[1]));
    return (p.user_metadata && (p.user_metadata.full_name || p.user_metadata.name)) || null;
  } catch { return null; }
}
async function _ticketSubmit(email, name, issue) {
  chatbotAddMsg('Opening your ticket…', 'bot');
  try {
    const r = await fetch('https://wallstbots-backend-868128114349.us-east1.run.app/support/ticket', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.trim(), name: name || null, issue, platform: PLATFORM })
    });
    const d = await r.json();
    if (r.ok && d.ticket_number) {
      chatbotAddMsg('✓ Ticket ' + d.ticket_number + ' opened. A confirmation is on its way to your email — our team will reach out within 24 hours.', 'bot');
    } else {
      chatbotAddMsg('Could not create the ticket right now — please try again in a moment.', 'bot');
    }
  } catch {
    chatbotAddMsg('Connection error — please try again in a moment.', 'bot');
  }
  _ticketState = null;
  _ticketIssue = '';
}
const TICKET_TRIGGERS = ['support ticket','open ticket','submit ticket','create ticket','file a ticket','contact support','tech support','speak to someone','talk to someone','real person','human support','support'];
function chatHandleInput(q) {
  const ql = q.toLowerCase().trim();
  if (_ticketState === 'awaiting_issue') {
    _ticketIssue = q;
    const email = _ticketEmail();
    if (email) { _ticketSubmit(email, _ticketName(), q); }
    else { _ticketState = 'awaiting_email'; chatbotAddMsg('Got it. What email address can our team reach you at?', 'bot'); }
    return;
  }
  if (_ticketState === 'awaiting_email') { _ticketSubmit(q, null, _ticketIssue); return; }
  if (TICKET_TRIGGERS.some(t => ql.includes(t))) {
    _ticketState = 'awaiting_issue';
    chatbotAddMsg('I’ll open a support ticket right now. Briefly describe the issue you’re experiencing:', 'bot');
    return;
  }
  chatbotAddMsg(botAnswer(q), 'bot');
}

function chatbotRenderQuick() {
  const wrap = $('chatbotQuick'); if (!wrap) return;
  const quick = ['Pricing', 'Why BOT13?', 'Stocks', 'Cancel', 'Support'];
  wrap.innerHTML = quick.map(q => '<button data-q="'+q+'">'+q+'</button>').join('');
  wrap.querySelectorAll('button').forEach(btn => {
    btn.addEventListener('click', () => {
      const q = btn.getAttribute('data-q');
      chatbotAddMsg(q, 'user');
      setTimeout(() => chatHandleInput(q), 250);
    });
  });
}
function chatbotOpen()  { const p=$('chatbotPanel'); if(p) p.classList.add('open'); const t=$('chatbotToggle'); if(t) t.setAttribute('aria-expanded','true'); }
function chatbotClose() { const p=$('chatbotPanel'); if(p) p.classList.remove('open'); const t=$('chatbotToggle'); if(t) t.setAttribute('aria-expanded','false'); }

// ================================================================
// BOOTSTRAP — wires up everything once the DOM is ready
// ================================================================
function wireUI() {
  const mt = $('menuToggle');
  if (mt) mt.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleMenu();
    const open = $('siteNav') && $('siteNav').classList.contains('open');
    mt.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  document.querySelectorAll('.site-nav a').forEach(a => {
    a.addEventListener('click', () => closeMenu());
  });

  document.addEventListener('click', (e) => {
    const nav = $('siteNav');
    const tog = $('menuToggle');
    if (!nav || !tog) return;
    if (nav.classList.contains('open') && !nav.contains(e.target) && !tog.contains(e.target)) {
      closeMenu();
    }
  });

  const ct = $('chatbotToggle');
  if (ct) ct.addEventListener('click', chatbotOpen);
  const cc = $('chatbotClose');
  if (cc) cc.addEventListener('click', chatbotClose);

  const cf = $('chatbotForm');
  if (cf) cf.addEventListener('submit', (e) => {
    e.preventDefault();
    const inp = $('chatbotInput');
    const q = inp ? inp.value.trim() : '';
    if (!q) return;
    chatbotAddMsg(q, 'user');
    if (inp) inp.value = '';
    setTimeout(() => chatHandleInput(q), 250);
  });

  chatbotRenderQuick();

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { closeMenu(); chatbotClose(); }
  });

  window.addEventListener('hashchange', () => {
    try { route(); } catch (e) { console.error('Route error', e); }
  });
}

function updateNavAuth() {
  // Remove any stale "My Tracker" link — Dashboard is the members entry point
  const nav = document.getElementById('siteNav');
  if (!nav) return;
  const existing = nav.querySelector('[data-route="/my-tracker"]');
  if (existing) existing.remove();
}

// Mirror bitbot13/wallstbots nav toggle for the static Log In / Dashboard buttons in index.html
function updateNavAuthState() {
  const loginBtn   = document.getElementById('navLoginBtn');
  const dashBtn    = document.getElementById('navDashBtn');
  const signOutBtn = document.getElementById('navSignOutBtn');
  if (!loginBtn || !dashBtn) return;
  const loggedIn = !!(localStorage.getItem('aistocks_jwt') || localStorage.getItem('auth_token'));
  loginBtn.style.display   = loggedIn ? 'none' : '';
  dashBtn.style.display    = loggedIn ? ''     : 'none';
  if (signOutBtn) signOutBtn.style.display = loggedIn ? '' : 'none';
}

function navSignOut() {
  ['aistocks_jwt','auth_token','wallstbots_jwt','bitbot13_jwt','wallstbots_refresh'].forEach(k => localStorage.removeItem(k));
  window.location.hash = '#/';
  updateNavAuthState();
}

document.addEventListener('DOMContentLoaded', () => {
  wireUI();
  updateNavAuthState();
  loadAll();
});

// When the user returns via browser-back from Stripe (bfcache restore), the
// checkout button can be stuck disabled on "Redirecting to checkout…". Reset
// the Get Yours pricing panel so the Subscribe button is usable again.
window.addEventListener('pageshow', (e) => {
  if (e.persisted && location.hash.indexOf('get-yours') !== -1) {
    try { if (typeof updateGyPricing === 'function') updateGyPricing(); } catch (err) {}
  }
});
