/* ================================================================
   lvl13.tech — single-page app  v3
   Router + page renderers + data fetching + chatbot
   ================================================================ */

const STATE = { funds: null, news: null, signals: null, reports: null,
                meta: { paypalEmail: 'lvl13cs@gmail.com' } };
const CHARTS = {};
let SIGNALS_FILTER = 'ALL';
let SECTOR_FILTER = 'ALL';
let PICKED_TICKERS = [];

const fmt$  = n => '$' + (n||0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
const fmt$0 = n => '$' + Math.round(n||0).toLocaleString();
const fmtPct = n => (n>=0?'+':'') + (n||0).toFixed(2) + '%';
const cls   = n => n>=0 ? 'pos' : 'neg';
const $     = id => document.getElementById(id);

const FUND_META = {
  bot13:     { name:'BOT13',     icon:'13', color:'#ec4899', kind:'DAILY',
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

// ============ AUTH HELPERS ============
const JWT_KEY = 'lvl13_jwt';
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

async function loadAll() {
  if (location.protocol === 'file:') { showFileProtocolWarning(); return; }
  try {
    const r = await Promise.allSettled([
      fetch(`${TRACKER_API}/state`,   { cache: 'no-store' }).then(r => r.json()).then(r => r.data),
      fetch(`${TRACKER_API}/news`,    { cache: 'no-store' }).then(r => r.json()).then(r => r.data),
      fetch(`${TRACKER_API}/signals`, { cache: 'no-store' }).then(r => r.json()).then(r => r.data),
      fetch(`${TRACKER_API}/reports`, { cache: 'no-store' }).then(r => r.json()).then(r => r.data),
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
  const path = (location.hash.replace(/^#/, '') || '/');
  setActiveNav(path); closeMenu();
  window.scrollTo({ top: 0, behavior: 'instant' });
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
  const t = new Date(iso); if (isNaN(t)) return iso;
  const m = Math.round((Date.now() - t) / 60000);
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
  msg = msg || 'Like what you see? Build this on YOUR stocks.';
  return '<a class="get-yours-hint" href="#/get-yours" style="text-decoration:none"><span class="arrow">→</span><span class="msg">'+msg+'</span><span class="pill">GET YOURS</span></a>';
}
function fundCard(fid, data) {
  const meta = FUND_META[fid];
  const v = data && data.value ? data.value : { total: 43000, pnl: 0, pnl_pct: 0, day_pnl: 0, day_pct: 0 };
  return '<a class="card clickable fund-card" href="#/fund/'+fid+'">'
    + '<div class="fund-head"><span class="fund-icon '+fid+'">'+meta.icon+'</span>'
    + '<div style="min-width:0"><div class="fund-name">'+meta.name+'</div><div class="fund-kind" style="color:'+meta.color+'">'+meta.kind+'</div></div></div>'
    + '<div class="fund-tag">'+meta.tagline+'</div>'
    + '<div class="fund-value '+cls(v.pnl)+'">'+fmt$0(v.total)+'</div>'
    + '<div class="fund-pnl '+cls(v.pnl)+'">'+fmt$0(v.pnl)+' ('+fmtPct(v.pnl_pct)+') since inception</div>'
    + '<div class="stat-row"><span class="stat-label">Today</span>'
    + '<span class="stat-val '+cls(v.day_pnl)+'">'+fmtPct(v.day_pct)+'</span></div></a>';
}

function newsCard(it) {
  const cat = sectorClass(it.sector);
  const url = it.url && it.url !== '#' ? it.url : null;
  const open = url ? ' target="_blank" rel="noopener noreferrer"' : '';
  const href = url || 'javascript:void(0)';
  return '<a class="news-card cat-'+cat+'" href="'+escapeHtml(href)+'"'+open+'>'
    + '<div class="news-title">'+escapeHtml(it.title||'')+'</div>'
    + '<div class="news-meta">'+escapeHtml(it.source||it.sector||'Source')+' · '+relTime(it.published_at)+'</div></a>';
}

// ============ PAGE: HOMEPAGE ============
function renderHome() {
  // Live leaderboard strip — 5 funds
  const strip = FUND_ORDER.map(fid => {
    const data = STATE.funds && STATE.funds.funds ? STATE.funds.funds[fid] : null;
    const v = data && data.value ? data.value : { day_pct: 0, day_pnl: 0 };
    const m = FUND_META[fid];
    return '<a class="card clickable" href="#/fund/'+fid+'">'
      + '<span class="fund-icon '+fid+'">'+m.icon+'</span>'
      + '<div class="lb-name"><strong>'+m.name+'</strong><small>'+m.kind+'</small></div>'
      + '<div class="lb-pct '+cls(v.day_pnl)+'">'+fmtPct(v.day_pct)+'</div></a>';
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

  $('app').innerHTML =
    '<section class="hero"><img src="assets/robot.svg" alt="" class="hero-robot">'
    + '<div class="hero-content"><span class="hero-eyebrow">AI &amp; Quantum Stock Tracker</span>'
    + '<h1>5 AI strategies. One universe. Watch them race.</h1>'
    + '<p>Three Claude-built bots — daily, weekly, monthly — trading head-to-head against two passive strategies on the same 43 AI/Quantum stocks. Daily Buy/Sell/Hold signals on every name. AI &amp; Quantum news, filtered to what matters. <strong>Welcome to Level 13.</strong></p>'
    + '<div class="hero-ctas"><a class="btn btn-primary" href="#/race">See The Race</a>'
    + '<a class="btn btn-secondary" href="#/how">How It Works</a></div></div></section>'

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

    + '<div class="panel" style="margin-top:28px">'
    + '<div style="color:var(--muted);font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:14px">Also From Level XIII Tech</div>'
    + '<div class="grid grid-2">'
    + '<a href="https://wallstbots.tech" class="card clickable" target="_blank" rel="noopener noreferrer" style="text-decoration:none">'
    + '<div style="color:var(--blue);font-weight:700;font-size:15px;margin-bottom:4px">wallstbots.tech</div>'
    + '<div style="color:var(--muted);font-size:13px;line-height:1.5">Sector Stock Tracker. Top 3 stocks per S&amp;P 500 sector + hottest IPOs since 2024. Same 5 strategies.</div>'
    + '</a>'
    + '<a href="https://bitbot13.tech" class="card clickable" target="_blank" rel="noopener noreferrer" style="text-decoration:none">'
    + '<div style="color:var(--blue);font-weight:700;font-size:15px;margin-bottom:4px">bitbot13.tech</div>'
    + '<div style="color:var(--muted);font-size:13px;line-height:1.5">Crypto Trading Bot Tracker. Top 50 coins by market cap. 24/7 markets. Same 5 strategies.</div>'
    + '</a>'
    + '</div></div>'

    + getYoursHint('Run this exact dashboard on YOUR stocks. Custom bots, custom news.');
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
    + getYoursHint('Build the same news feed on YOUR sectors.');
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
    ['Auto Reports, Every Sunday','Weekly grades A–F per strategy. Pros, cons, narrative for what worked. Trade-by-trade review for every bot.'],
    ['AI &amp; Quantum News, Filtered','Headlines pulled from the sectors that matter. AI, Quantum, Biotech, Defense — pick what you follow.'],
  ];
  const featureCards = features.map(f =>
    '<div class="card"><h3 style="color:var(--blue)">✓ '+f[0]+'</h3>'
    + '<p style="color:var(--muted);font-size:13px;margin:0">'+f[1]+'</p></div>').join('');
  $('app').innerHTML = '<h1>How It Works</h1>'
    + '<p class="sub">Five strategies. One universe. The same starting capital. Then we watch.</p>'
    + '<h3>The 5 Strategies</h3><div class="bot-strip">'+stripCards+'</div>'
    + '<h3>What You Get</h3><div class="grid grid-3">'+featureCards+'</div>'
    + '<div class="sales-strip" style="margin-top:24px"><div><h3>The Challenge.</h3>'
    + '<p>Can three Claude-built bots beat two passive strategies on the same universe with the same money?</p></div></div>'
    + getYoursHint('Want this on YOUR stocks, with YOUR sectors?');
}

// ============ PAGE: THE RACE ============
function renderRace() {
  const cards = FUND_ORDER.map(fid =>
    fundCard(fid, STATE.funds && STATE.funds.funds ? STATE.funds.funds[fid] : null)).join('');
  $('app').innerHTML = '<h1>The Race</h1>'
    + '<p class="sub">Five strategies. '+fmt$0((STATE.funds&&STATE.funds.starting_capital)||43000)+' each. Same 43-stock universe. Refreshed live.</p>'
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

// ============ PAGE: INDIVIDUAL FUND ============
function renderFund(fid) {
  const data = STATE.funds && STATE.funds.funds ? STATE.funds.funds[fid] : null;
  const meta = FUND_META[fid];
  if (!meta) { $('app').innerHTML = '<p>Unknown fund</p>'; return; }
  const v = data && data.value ? data.value : { total:43000, pnl:0, pnl_pct:0, day_pnl:0, day_pct:0, positions:[] };
  const startCap = (data && data.starting_capital) || 43000;
  let strategyHTML = '';
  if (['bot13','oracle','wizard'].includes(fid) && data && data.current_strategy) {
    strategyHTML = renderStrategyPanel(fid, data.current_strategy);
  }

  // Holdings table — graceful fallback for missing price/value
  const positionRows = (v.positions || []).length
    ? v.positions.map(p => {
        const entry  = p.entry_price || p.entry || 0;
        const price  = p.price || entry;  // fall back to entry if live price missing
        const shares = p.shares || 0;
        const value  = p.value || (shares * price);
        const pnl    = p.pnl != null ? p.pnl : (value - (p.cost_basis || (shares * entry)));
        const pnlPct = p.pnl_pct != null ? p.pnl_pct
                     : (entry > 0 ? ((price/entry - 1)*100) : 0);
        const dayPnl = p.day_pnl != null ? p.day_pnl : 0;
        const dayPct = p.day_pct != null ? p.day_pct : 0;
        return '<tr><td><strong>'+p.symbol+'</strong></td>'
          + '<td class="num">'+shares.toFixed(2)+'</td>'
          + '<td class="num">$'+entry.toFixed(2)+'</td>'
          + '<td class="num">$'+price.toFixed(2)+'</td>'
          + '<td class="num">'+fmt$0(value)+'</td>'
          + '<td class="num '+cls(dayPnl)+'">'+fmtPct(dayPct)+'</td>'
          + '<td class="num '+cls(pnl)+'">'+fmt$0(pnl)+'</td>'
          + '<td class="num '+cls(pnlPct)+'">'+fmtPct(pnlPct)+'</td></tr>';
      }).join('')
    : '<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:18px">Holding cash</td></tr>';

  $('app').innerHTML =
    '<div class="fund-head" style="margin-bottom:14px">'
    + '<span class="fund-icon '+fid+'" style="width:48px;height:48px;font-size:16px">'+meta.icon+'</span>'
    + '<div><h1 style="margin:0">'+meta.name+'</h1>'
    + '<div class="fund-tag">'+meta.tagline+'</div></div></div>'
    + '<div class="grid grid-3" style="margin-bottom:18px">'
    + '<div class="card"><h3>Current Value</h3>'
    + '<div class="fund-value '+cls(v.pnl)+'">'+fmt$0(v.total)+'</div>'
    + '<div style="color:var(--muted);font-size:11px;margin-top:6px">Started at '+fmt$0(startCap)+'</div></div>'
    + '<div class="card"><h3>Total P&amp;L</h3>'
    + '<div class="fund-value '+cls(v.pnl)+'">'+fmt$0(v.pnl)+'</div>'
    + '<div class="fund-pnl '+cls(v.pnl_pct)+'">'+fmtPct(v.pnl_pct)+' all-time</div></div>'
    + '<div class="card"><h3>Today\'s Change</h3>'
    + '<div class="fund-value '+cls(v.day_pnl)+'">'+fmt$0(v.day_pnl)+'</div>'
    + '<div class="fund-pnl '+cls(v.day_pct)+'">'+fmtPct(v.day_pct)+' since yesterday</div></div></div>'
    + strategyHTML
    + '<div class="panel"><h3>Holdings</h3>'
    + '<div class="tbl-wrap"><table>'
    + '<thead><tr><th>Symbol</th><th class="num">Shares</th><th class="num">Entry</th>'
    + '<th class="num">Price</th><th class="num">Value</th><th class="num">Today</th>'
    + '<th class="num">P&amp;L</th><th class="num">%</th></tr></thead>'
    + '<tbody>'+positionRows+'</tbody></table></div></div>'
    + getYoursHint('Want a '+meta.name.toLowerCase()+'-style bot picking from YOUR stock list?');
}

function renderStrategyPanel(fid, strat) {
  const period = fid==='bot13' ? 'Day of '+strat.day
               : fid==='oracle' ? 'Week of '+strat.week
               : 'Month of '+strat.month;
  const label  = fid==='bot13' ? "TODAY'S STRATEGY"
               : fid==='oracle' ? "THIS WEEK'S STRATEGY"
               : "THIS MONTH'S STRATEGY";
  let picks = '';
  if (strat.decision === 'CASH') {
    picks = '<div class="pick-card"><div class="pick-head"><div class="pick-sym">100% CASH</div><div class="pick-meta">No trade</div></div>'
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
  return '<div class="strategy-panel '+fid+'"><h3>'+label+'</h3>'
    + '<div class="strategy-meta">'+escapeHtml(period)+' · '+escapeHtml(strat.decision||'')+'</div>'
    + '<p class="strategy-rationale">'+escapeHtml(strat.rationale||'')+'</p>'+picks+'</div>';
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
  const recs = (data.recommendations||[]).filter(r =>
    SIGNALS_FILTER==='ALL' || r.action===SIGNALS_FILTER);
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
function renderReports() {
  const reports = (STATE.reports && STATE.reports.reports) || [];
  if (!reports.length) {
    $('app').innerHTML = '<h1>Sunday Reports</h1>'
      + '<p class="sub">Auto-generated every Sunday. Past-week analysis, fund grades, trade-by-trade review.</p>'
      + '<div class="panel"><p style="color:var(--muted);text-align:center;padding:20px">No reports yet — first one runs this Sunday.</p></div>'
      + getYoursHint();
    return;
  }
  const cards = reports.map(r =>
    '<a class="card clickable" href="#/report/'+r.week_end+'">'
    + '<h3 style="margin-bottom:4px">Week ending</h3>'
    + '<div style="font-size:18px;font-weight:700;margin-bottom:14px">'+r.week_end+'</div>'
    + Object.entries(r.fund_results||{}).map(([id, res]) =>
        '<div class="stat-row"><span class="stat-label">'+(res.name||id).toUpperCase()+'</span>'
        + '<span><span class="grade grade-'+(res.week_grade||'C')[0]+'">'+res.week_grade+'</span>'
        + '<span class="'+cls(res.week_pct)+'" style="margin-left:8px;font-weight:600">'+fmtPct(res.week_pct)+'</span></span></div>'
      ).join('') + '</a>').join('');
  $('app').innerHTML = '<h1>Sunday Reports</h1>'
    + '<p class="sub">Auto-generated every Sunday at market close.</p>'
    + '<div class="grid grid-3">'+cards+'</div>' + getYoursHint();
}

function renderReport(weekEnd) {
  const reports = (STATE.reports && STATE.reports.reports) || [];
  const report = reports.find(r => r.week_end === weekEnd);
  if (!report) { $('app').innerHTML = '<p>Report not found.</p>'; return; }
  const fundCards = Object.entries(report.fund_results||{}).map(([fid, res]) =>
    '<div class="card"><div class="fund-head">'
    + '<div><div class="fund-name">'+(res.name||fid)+'</div><div class="fund-tag">'+escapeHtml(res.narrative||'')+'</div></div>'
    + '<div style="margin-left:auto"><span class="grade grade-'+(res.week_grade||'C')[0]+'">'+res.week_grade+'</span></div></div>'
    + '<div class="stat-row"><span class="stat-label">Week P&amp;L</span><span class="stat-val '+cls(res.week_pnl)+'">'+fmt$(res.week_pnl)+' ('+fmtPct(res.week_pct)+')</span></div></div>'
  ).join('');
  $('app').innerHTML = '<h1>Weekly Report — '+report.week_start+' to '+report.week_end+'</h1>'
    + '<p class="sub">Generated '+report.report_date+'</p>'
    + '<div class="grid grid-3">'+fundCards+'</div>' + getYoursHint();
}

// ============ PAGE: GET YOURS ============
function renderGetYours() {
  const paypal = STATE.meta.paypalEmail;
  $('app').innerHTML =
    '<section class="hero" style="margin-bottom:24px"><img src="assets/robot.svg" alt="" class="hero-robot">'
    + '<div class="hero-content"><span class="hero-eyebrow">Master the Market — Without the Risk</span>'
    + '<h1>You\'ve seen what it does. Now make it yours.</h1>'
    + '<p>Build, test, and refine your portfolio with a market research tool built for the modern trader. Whether you\'re leveraging AI trading bots or manual strategies, you can track 50 stocks simultaneously with daily technical analysis that includes Buy/Sell/Hold signals analyzed by AI. Plus, never miss a beat with personalized news updates delivered straight to your dashboard. Our <strong style="color:var(--blue)">Level XIII</strong> platform is a game changer that lets you master the market without the risk.</p></div></section>'
    + '<div class="sales-hero"><div class="sales-hero-left">'
    + '<h2 style="font-size:28px;letter-spacing:-0.5px">BUILD YOUR OWN</h2>'
    + '<p style="color:var(--muted);font-size:15px">Pick up to 50 stocks from ANY sector. Three custom AI bots. Custom news feed. Sunday auto-reports.</p>'
    + '<p style="color:var(--blue);font-weight:700;font-size:15px">$799/year &nbsp;·&nbsp; auto-renews &nbsp;·&nbsp; cancel anytime</p>'
    + '</div><div class="sales-hero-right"><h3>Subscribe with PayPal</h3>'
    + '<form action="https://www.paypal.com/cgi-bin/webscr" method="post" target="_top" style="margin:0">'
    + '<input type="hidden" name="cmd" value="_xclick-subscriptions">'
    + '<input type="hidden" name="business" value="'+paypal+'">'
    + '<input type="hidden" name="lc" value="US">'
    + '<input type="hidden" name="item_name" value="lvl13.tech Custom Tracker - Annual">'
    + '<input type="hidden" name="no_note" value="1"><input type="hidden" name="no_shipping" value="1">'
    + '<input type="hidden" name="custom" value="lvl13">'
    + '<input type="hidden" name="src" value="1"><input type="hidden" name="a3" value="799.00">'
    + '<input type="hidden" name="p3" value="1"><input type="hidden" name="t3" value="Y">'
    + '<input type="hidden" name="currency_code" value="USD">'
    + '<input type="hidden" name="return" value="https://lvl13.tech/#/thanks">'
    + '<input type="hidden" name="cancel_return" value="https://lvl13.tech/#/get-yours">'
    + '<button type="submit" class="paypal-btn">Subscribe — $799/yr</button></form>'
    + '<div style="font-size:12px;margin-top:6px;opacity:0.85">$799 today, $799 every 365 days</div>'
    + '<div class="powered">POWERED BY PAYPAL BUSINESS</div></div></div>'
    + '<div class="sales-strip"><div><h3>Any Sector. Any Stocks. Any News.</h3>'
    + '<p>Tech, biotech, energy, finance, defense, REITs — pick the sectors that matter; we pull the news.</p></div>'
    + '<span class="signal signal-buy" style="font-size:11px;padding:6px 14px">15+ SECTORS</span></div>'
    + '<h3>What\'s Included</h3><div class="grid grid-3">'
    + [['Up to 50 stocks','Any sector, any exchange. NYSE, NASDAQ, plus custom tickers.'],
       ['3 AI bots','Daily, weekly, monthly — all yours.'],
       ['2 baselines','Equal-weight + market-cap weighted benchmarks.'],
       ['Daily Buy/Sell/Hold','Composite signals on every stock you picked.'],
       ['Custom news feed','Pick the sectors. We curate, dedupe, deliver.'],
       ['Sunday auto-reports','Weekly grades, pros/cons, trade-by-trade review.']].map(p =>
         '<div class="card"><h3 style="color:var(--blue);margin-bottom:8px">✓ '+p[0]+'</h3>'
         + '<p style="color:var(--muted);font-size:13px;margin:0">'+p[1]+'</p></div>').join('')
    + '</div>'
    + '<div class="panel" style="margin-top:24px;text-align:center">'
    + '<p style="color:var(--muted);font-size:13px;font-style:italic;margin:0">Built by an operator who runs the same system on his own portfolio. Cancel anytime from your PayPal account. Questions? <a href="mailto:info@lvl13.tech" style="color:var(--blue)">info@lvl13.tech</a></p></div>';
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
      + '<p style="color:var(--muted)">This link is missing the setup token. Check your email for the original link from info@lvl13.tech.</p></div>';
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
        body: JSON.stringify({ token, password: pw, platform: 'lvl13' }),
      });
      setJWT(result.access_token);
      updateNavAuth();
      location.hash = '#/my-picks';
    } catch (ex) {
      err.textContent = ex.message || 'Setup failed. Try again or email info@lvl13.tech.';
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
    const result = await apiFetch('/user/tracker/state?platform=lvl13', { headers: authHeaders() });
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
    const sc    = data.starting_capital || 43000;

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
        + '<div style="font-size:22px;font-weight:700;margin-bottom:2px">$' + v.total.toLocaleString() + '</div>'
        + '<div style="font-size:13px;color:' + (v.pnl >= 0 ? 'var(--green)' : 'var(--red)') + '">'
        + sign + '$' + Math.abs(v.pnl).toLocaleString() + ' (' + sign + v.pnl_pct.toFixed(1) + '%)</div>'
        + '<div style="font-size:12px;color:var(--muted);margin-top:4px">Today: '
        + (v.day_pnl >= 0 ? '+' : '') + '$' + Math.abs(v.day_pnl).toFixed(0) + '</div></div>';
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


// ============ PAGE: THANKS ============
function renderThanks() {
  $('app').innerHTML = '<section class="hero"><div class="hero-content">'
    + '<h1>You\'re in. 🎉</h1>'
    + '<p>Your lvl13.tech tracker will be live within 24 hours. Check your email for your setup link.</p>'
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
  { q: ['price','cost','how much','pricing','799'], a: "Custom Tracker is $799/year (auto-renews, cancel anytime from your PayPal account). One flat price, all 5 strategies, your stocks, your news." },
  { q: ['cancel','refund','stop'], a: "Cancel anytime from your PayPal account → Settings → Automatic Payments. No refund for the partial year, but no further charges." },
  { q: ['stocks','tickers','how many'], a: "Up to 50 stocks from any sector (NYSE, NASDAQ, plus most listed tickers). You pick them after checkout." },
  { q: ['sector','sectors','industries'], a: "Any sector — tech, biotech, energy, finance, defense, REITs, you name it. We fetch news for the sectors you choose." },
  { q: ['news','articles','sources'], a: "We pull from 80+ sources via NewsAPI, dedupe, and filter to the sectors you picked. Updated every 30 min during market hours." },
  { q: ['bot','bots','strategy','strategies'], a: "5 strategies race on the SAME stock list: BOT13 (daily intraday), ORACLE (weekly Monday rebalance), WIZARD (monthly hold), EQUALIZER (equal-weight baseline), TITAN (cap-weighted baseline)." },
  { q: ['signals','buy','sell','hold'], a: "Every trading day we score every stock on your list — momentum, RSI, MACD, volume, volatility — and label it Strong Buy / Buy / Hold / Sell / Strong Sell." },
  { q: ['report','reports','sunday','weekly'], a: "Every Sunday you get an auto-generated report: each fund's grade, what they bought/sold, why, and what's coming up." },
  { q: ['real money','live trade','execute','broker'], a: "Nope — these are paper portfolios for research and signals. We don't touch a brokerage account. You see what the bots WOULD do, then decide for yourself." },
  { q: ['data','privacy','share','sell my'], a: "Your data stays yours. We don't share or sell. Your tracker runs on a private endpoint — only you and the people you share the link with see it." },
  { q: ['contact','support','help','email'], a: "Email info@lvl13.tech anytime. Built and supported directly by the operator." },
  { q: ['how long','setup','time','when'], a: "Tracker is live within 24 hours of checkout. You'll get an email with your private dashboard link." },
];
function botAnswer(input) {
  const q = (input || '').toLowerCase().trim();
  if (!q) return null;
  for (const item of FAQS) {
    if (item.q.some(k => q.includes(k))) return item.a;
  }
  return "I don't have an answer for that yet — but the operator does. Email info@lvl13.tech and you'll get a real reply, fast.";
}
function chatbotAddMsg(text, who) {
  const body = $('chatbotBody'); if (!body) return;
  const div = document.createElement('div');
  div.className = 'chatbot-msg ' + (who || 'bot');
  div.textContent = text;
  body.appendChild(div);
  body.scrollTop = body.scrollHeight;
}
function chatbotRenderQuick() {
  const wrap = $('chatbotQuick'); if (!wrap) return;
  const quick = ['Pricing', 'Stocks', 'Bots', 'Cancel', 'Contact'];
  wrap.innerHTML = quick.map(q => '<button data-q="'+q+'">'+q+'</button>').join('');
  wrap.querySelectorAll('button').forEach(btn => {
    btn.addEventListener('click', () => {
      const q = btn.getAttribute('data-q');
      chatbotAddMsg(q, 'user');
      chatbotAddMsg(botAnswer(q), 'bot');
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
    const q = inp ? inp.value : '';
    if (!q.trim()) return;
    chatbotAddMsg(q, 'user');
    setTimeout(() => chatbotAddMsg(botAnswer(q), 'bot'), 250);
    if (inp) inp.value = '';
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
  // Insert "My Tracker" link in nav if logged in, remove if not
  const nav = document.getElementById('siteNav');
  if (!nav) return;
  const existing = nav.querySelector('[data-route="/my-tracker"]');
  if (isLoggedIn()) {
    if (!existing) {
      const a = document.createElement('a');
      a.href = '#/my-tracker';
      a.setAttribute('data-route', '/my-tracker');
      a.textContent = 'My Tracker';
      a.style.color = 'var(--blue)';
      // Insert before the "Get Yours" CTA
      const cta = nav.querySelector('.cta');
      nav.insertBefore(a, cta || null);
      a.addEventListener('click', () => closeMenu());
    }
  } else {
    if (existing) existing.remove();
  }
}

// Mirror bitbot13/wallstbots nav toggle for the static Log In / Dashboard buttons in index.html
function updateNavAuthState() {
  const loginBtn = document.getElementById('navLoginBtn');
  const dashBtn  = document.getElementById('navDashBtn');
  if (!loginBtn || !dashBtn) return;
  const loggedIn = !!(localStorage.getItem('lvl13_jwt') || localStorage.getItem('auth_token'));
  loginBtn.style.display = loggedIn ? 'none' : '';
  dashBtn.style.display  = loggedIn ? ''     : 'none';
}

function boot() {
  wireUI();
  updateNavAuth();
  updateNavAuthState();
  loadAll();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
