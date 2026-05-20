/* ================================================================
   wallstbots.tech — single-page app  v1
   Identical engine to lvl13.tech — sector stocks universe
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

const TRACKER_API = 'https://wallstbots-backend-868128114349.us-east1.run.app/public/tracker';

function fetchWithTimeout(url, opts = {}, ms = 8000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  return fetch(url, { ...opts, signal: ctrl.signal }).finally(() => clearTimeout(t));
}

// ============ DATA LOADING — backend API ============
async function loadAll() {
  if (location.protocol === 'file:') { showFileProtocolWarning(); return; }
  try {
    const r = await Promise.allSettled([
      fetch('data/state.json',   { cache: 'no-store' }).then(r => r.json()).then(r => r.data),
      fetchWithTimeout(`${TRACKER_API}/news?platform=wallstbots`, { cache: 'no-store' }).then(r => r.json()).then(r => r.data),
      fetch('data/signals.json', { cache: 'no-store' }).then(r => r.json()).then(r => r.data),
      fetch('data/reports.json', { cache: 'no-store' }).then(r => r.json()).then(r => r.data),
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
  $('app').innerHTML = '<div class="hero" style="border-color:var(--orange)"><h1 style="color:var(--orange)">Open this site over HTTP, not file://</h1><p>Serve via a local web server or deploy to Cloudflare Pages.</p></div>';
}
function showDataLoadError(detail) {
  $('app').innerHTML = '<div class="hero" style="border-color:var(--red)"><h1 style="color:var(--red)">Couldn\'t load site data</h1>'+(detail?'<p style="color:var(--muted);font-family:monospace">'+escapeHtml(detail)+'</p>':'')+'<p>Try a hard refresh (Ctrl+F5).</p></div>';
}

// ============ ROUTING ============
function route() {
  const path = (location.hash.replace(/^#/, '') || '/');
  setActiveNav(path); closeMenu();
  window.scrollTo({ top: 0, behavior: 'instant' });
  if (path === '/' || path === '')           return renderHome();
  if (path === '/how')                       return renderHowItWorks();
  if (path === '/race')                      return renderRace();
  if (path.startsWith('/fund/'))             return renderFund(path.split('/')[2]);
  if (path === '/signals')                   return renderSignals();
  if (path === '/news-all' || path === '/news') return renderNewsAll();
  if (path === '/reports')                   return renderReports();
  if (path.startsWith('/report/'))           return renderReport(path.split('/')[2]);
  if (path === '/get-yours')                 return renderGetYours();
  if (path === '/thanks')                    return renderThanks();
  if (path === '/referral')                  return renderReferral();
  if (path === '/login')  { window.location.href = '/login.html'; return; }
  if (path === '/signup') { window.location.href = '/login.html#signup'; return; }
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
  if (v.includes('energy'))                          return 'energy';
  if (v.includes('material'))                        return 'other';
  if (v.includes('industrial'))                      return 'tech';
  if (v.includes('consumer disc'))                   return 'other';
  if (v.includes('consumer stap'))                   return 'other';
  if (v.includes('health') || v.includes('bio'))     return 'bio';
  if (v.includes('financ') || v.includes('bank'))    return 'finance';
  if (v.includes('tech') || v.includes(' it'))       return 'tech';
  if (v.includes('communic'))                        return 'tech';
  if (v.includes('util'))                            return 'energy';
  if (v.includes('real estate'))                     return 'finance';
  return 'other';
}
function getYoursHint(msg) {
  msg = msg || 'Want this tracker running on YOUR stocks?';
  return '<a class="get-yours-hint" href="#/get-yours" style="text-decoration:none"><span class="arrow">→</span><span class="msg">'+msg+'</span><span class="pill">GET YOURS</span></a>';
}
function fundCard(fid, data) {
  const meta = FUND_META[fid];
  const cap = (STATE.funds && STATE.funds.starting_capital) || 55000;
  const v = data && data.value ? data.value : { total: cap, pnl: 0, pnl_pct: 0, day_pnl: 0, day_pct: 0 };
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
  const strip = FUND_ORDER.map(fid => {
    const data = STATE.funds && STATE.funds.funds ? STATE.funds.funds[fid] : null;
    const v = data && data.value ? data.value : { day_pct: 0, day_pnl: 0 };
    const m = FUND_META[fid];
    return '<a class="card clickable" href="#/fund/'+fid+'">'
      + '<span class="fund-icon '+fid+'">'+m.icon+'</span>'
      + '<div class="lb-name"><strong>'+m.name+'</strong><small>'+m.kind+'</small></div>'
      + '<div class="lb-pct '+cls(v.day_pnl)+'">'+fmtPct(v.day_pct)+'</div></a>';
  }).join('');

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

  const news = STATE.news || { items: [] };
  const newsItems = (news.items || []).slice(0, 5);
  const newsCards = newsItems.length ? newsItems.map(newsCard).join('')
    : '<p class="sub">No headlines yet — the fetcher runs nightly.</p>';

  const raceCards = FUND_ORDER.map(fid =>
    fundCard(fid, STATE.funds && STATE.funds.funds ? STATE.funds.funds[fid] : null)).join('');

  const cap = (STATE.funds && STATE.funds.starting_capital) || 55000;
  const stockCount = (() => {
    const eq = STATE.funds && STATE.funds.funds && STATE.funds.funds.equalizer;
    return eq && eq.value && eq.value.positions ? eq.value.positions.length : 55;
  })();

  $('app').innerHTML =
    '<section class="hero"><img src="assets/robot.svg" alt="" class="hero-robot">'
    + '<div class="hero-content"><span class="hero-eyebrow">Sector Stock Tracker</span>'
    + '<h1>5 strategies. '+stockCount+' stocks. Watch them race.</h1>'
    + '<p>Three bots — daily, weekly, monthly — trading head-to-head against two passive strategies on the top 3 stocks per S&amp;P 500 sector plus the hottest IPOs since 2024. '+fmt$0(cap)+' starting capital. Daily Buy/Sell/Hold signals on every name. Sector news, filtered to what matters. <strong>Welcome to Wall St. Bots.</strong></p>'
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

    + '<div class="section-head" style="margin-top:36px"><h3>Also from Level 13</h3></div>'
    + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:18px">'

    + '<div class="card" style="display:flex;flex-direction:column">'
    + '<div style="font-size:10px;font-weight:700;letter-spacing:1px;color:var(--blue);margin-bottom:12px;text-transform:uppercase">Our<br>AI &amp; Quantum<br>Bots</div>'
    + '<a href="https://lvl13.tech" target="_blank" rel="noopener">'
    + '<img src="assets/logo-lvl13.png" alt="lvl13.tech" style="width:100%;max-width:200px;height:auto;display:block;margin-bottom:14px;border-radius:8px"></a>'
    + '<p style="color:var(--muted);font-size:13px;line-height:1.6;margin:0 0 14px;flex:1">The same 5 bots racing on 43 hand-picked AI &amp; Quantum stocks. Daily signals, live leaderboards, and weekly performance reports.</p>'
    + '<a class="btn btn-secondary" href="https://lvl13.tech" target="_blank" rel="noopener" style="font-size:12px;margin-top:auto">Visit lvl13.tech →</a>'
    + '</div>'

    + '<div class="card" style="display:flex;flex-direction:column">'
    + '<div style="font-size:10px;font-weight:700;letter-spacing:1px;color:var(--blue);margin-bottom:12px;text-transform:uppercase">Our Cryptocurrency Bots</div>'
    + '<a href="https://bitbot13.tech" target="_blank" rel="noopener">'
    + '<img src="assets/logo-bitbot13.png" alt="BitBot13" style="width:100%;max-width:200px;height:auto;display:block;margin-bottom:14px;border-radius:8px"></a>'
    + '<p style="color:var(--muted);font-size:13px;line-height:1.6;margin:0 0 14px;flex:1">The same AI intelligence applied to Bitcoin and crypto markets. BitBot13 tracks the top 50 coins with daily Buy/Sell/Hold signals and strategy competition.</p>'
    + '<a class="btn btn-secondary" href="https://bitbot13.tech" target="_blank" rel="noopener" style="font-size:12px;margin-top:auto">Visit bitbot13.tech →</a>'
    + '</div>'

    + '</div>'
    + '<p style="text-align:center;color:var(--muted);font-size:13px;margin:0 0 36px;line-height:1.6">One login for stocks or cryptocurrencies. Your trading market research platform — Level 13.</p>'

    + getYoursHint('Run this exact dashboard on YOUR stocks. Custom bots, custom news.');
  drawTrajectory();
}

// ============ PAGE: NEWS-ALL ============
function renderNewsAll() {
  const news = STATE.news || { items: [] };
  const sectors = news.sectors || ['ENERGY','MATERIALS','INDUSTRIALS','CONSUMER DISCRETIONARY','CONSUMER STAPLES','HEALTH CARE','FINANCIALS','IT','COMMUNICATION SERVICES','UTILITIES','REAL ESTATE'];
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
    + '<div class="sales-strip" style="margin-top:36px">'
    + '<div><h3>Want news for YOUR sectors?</h3>'
    + '<p>Pick the sectors you care about. We curate, dedupe, deliver — straight to your private dashboard.</p></div>'
    + '<a href="#/get-yours" class="btn btn-primary" style="margin-left:auto">Get Yours →</a></div>'
    + '<div class="grid grid-3" style="margin-top:18px">'
    + [['Custom news feed','Pick Energy, Tech, Health Care, Financials — any combination.'],
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
    ['Sector News, Filtered','Headlines pulled from all 11 GICS sectors. Energy, Tech, Health Care, Financials — pick what you follow.'],
  ];
  const featureCards = features.map(f =>
    '<div class="card"><h3 style="color:var(--blue)">✓ '+f[0]+'</h3>'
    + '<p style="color:var(--muted);font-size:13px;margin:0">'+f[1]+'</p></div>').join('');
  $('app').innerHTML = '<h1>How It Works</h1>'
    + '<p class="sub">Five strategies. One universe. The same starting capital. Then we watch.</p>'
    + '<h3>The 5 Strategies</h3><div class="bot-strip">'+stripCards+'</div>'
    + '<h3>What You Get</h3><div class="grid grid-3">'+featureCards+'</div>'
    + '<div class="sales-strip" style="margin-top:24px"><div><h3>The Challenge.</h3>'
    + '<p>Can three bots beat two passive strategies on the same 55-stock universe with the same money?</p></div></div>'
    + getYoursHint('Want this on YOUR stocks, with YOUR sectors?');
}

// ============ PAGE: THE RACE ============
function renderRace() {
  const cap = (STATE.funds && STATE.funds.starting_capital) || 55000;
  const stockCount = (() => {
    const eq = STATE.funds && STATE.funds.funds && STATE.funds.funds.equalizer;
    return eq && eq.value && eq.value.positions ? eq.value.positions.length : 55;
  })();
  const cards = FUND_ORDER.map(fid =>
    fundCard(fid, STATE.funds && STATE.funds.funds ? STATE.funds.funds[fid] : null)).join('');
  $('app').innerHTML = '<h1>The Race</h1>'
    + '<p class="sub">Five strategies. '+fmt$0(cap)+' each. Same '+stockCount+'-stock universe. Refreshed daily.</p>'
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
  const cap = (STATE.funds && STATE.funds.starting_capital) || 55000;
  const v = data && data.value ? data.value : { total:cap, pnl:0, pnl_pct:0, day_pnl:0, day_pct:0, positions:[] };
  const startCap = (data && data.starting_capital) || cap;
  let strategyHTML = '';
  if (['bot13','oracle','wizard'].includes(fid) && data && data.current_strategy) {
    strategyHTML = renderStrategyPanel(fid, data.current_strategy);
  }

  const positionRows = (v.positions || []).length
    ? v.positions.map(p => {
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
    + getYoursHint('Want a '+meta.name.toLowerCase()+'-style bot on YOUR stock list?');
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
// Shared state for the pricing/referral widget
const PRICING = {
  firstMonthly: 79.99, firstAnnual: 799.00,
  addMonthly: 29.99,   addAnnual: 299.00,
  refMonthly: 39.99,   refAnnual: 639.20,
};
let GY_CYCLE = 'annual';   // 'monthly' | 'annual'
let GY_REF   = '';         // validated referral code
let GY_VALID = false;      // true once code validated

function renderGetYours() {
  // Auto-detect referral code from URL  (?ref=L13-XXXXXXXX)
  const urlRef = new URLSearchParams(location.search).get('ref')
              || new URLSearchParams(location.hash.split('?')[1] || '').get('ref') || '';

  const paypal = STATE.meta.paypalEmail;
  $('app').innerHTML =
    '<section class="hero" style="margin-bottom:24px"><img src="assets/robot.svg" alt="" class="hero-robot">'
    + '<div class="hero-content"><span class="hero-eyebrow">Master the Market — Without the Risk</span>'
    + '<h1>You\'ve seen what it does. Now make it yours.</h1>'
    + '<p>Up to 50 stocks. 5 AI-powered strategies. Daily signals, custom news feed, Sunday auto-reports. <strong style="color:var(--blue)">Wall St. Bots</strong> runs the research so you can make the call.</p></div></section>'

    // ── Pricing toggle ──
    + '<div class="panel" style="margin-bottom:24px">'
    + '<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:16px">'
    + '<h3 style="margin:0">Choose Your Plan</h3>'
    + '<div style="display:flex;background:var(--surface2);border-radius:8px;padding:3px">'
    + '<button id="cycleMonthly" onclick="setGyCycle(\'monthly\')" style="border:none;cursor:pointer;padding:6px 18px;border-radius:6px;font-weight:600;font-size:13px;transition:all 0.15s">Monthly</button>'
    + '<button id="cycleAnnual"  onclick="setGyCycle(\'annual\')"  style="border:none;cursor:pointer;padding:6px 18px;border-radius:6px;font-weight:600;font-size:13px;transition:all 0.15s">Annual <span style="color:#10b981;font-size:11px">SAVE 17%</span></button>'
    + '</div></div>'

    // Pricing cards
    + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px">'
    + '<div class="card" style="border:2px solid var(--blue)">'
    + '<div style="font-size:11px;font-weight:700;letter-spacing:1px;color:var(--blue);margin-bottom:8px;text-transform:uppercase">1st Portfolio</div>'
    + '<div id="price1" style="font-size:28px;font-weight:800;color:var(--fg)"></div>'
    + '<div id="price1sub" style="font-size:12px;color:var(--muted);margin-top:4px"></div>'
    + '</div>'
    + '<div class="card">'
    + '<div style="font-size:11px;font-weight:700;letter-spacing:1px;color:var(--muted);margin-bottom:8px;text-transform:uppercase">Each Additional</div>'
    + '<div id="price2" style="font-size:28px;font-weight:800;color:var(--fg)"></div>'
    + '<div id="price2sub" style="font-size:12px;color:var(--muted);margin-top:4px"></div>'
    + '</div></div>'
    + '<p style="font-size:12px;color:var(--muted);margin:0">Additional portfolios can be on any Level 13 site — stocks, crypto, or AI &amp; Quantum.</p>'
    + '</div>'

    // ── Referral code ──
    + '<div class="panel" style="margin-bottom:24px">'
    + '<h3 style="margin-bottom:12px">Have a Referral Code?</h3>'
    + '<div style="display:flex;gap:10px;flex-wrap:wrap">'
    + '<input id="refInput" type="text" placeholder="L13-XXXXXXXX" maxlength="20" '
    + 'style="flex:1;min-width:160px;background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:10px 14px;color:var(--fg);font-size:14px;font-family:monospace;text-transform:uppercase" '
    + 'value="'+escapeHtml(urlRef)+'" oninput="this.value=this.value.toUpperCase()">'
    + '<button onclick="applyRefCode()" style="background:var(--blue);color:#fff;border:none;border-radius:8px;padding:10px 20px;font-weight:700;cursor:pointer;white-space:nowrap">Apply Code</button>'
    + '</div>'
    + '<div id="refMsg" style="margin-top:10px;font-size:13px"></div>'
    + '</div>'

    // ── Subscribe box ──
    + '<div class="sales-hero"><div class="sales-hero-left">'
    + '<h2 style="font-size:28px;letter-spacing:-0.5px">BUILD YOUR OWN</h2>'
    + '<p style="color:var(--muted);font-size:15px">Pick up to 50 stocks from ANY sector. Daily, weekly, and monthly AI bots. Custom news feed. Sunday auto-reports.</p>'
    + '<div id="activePriceLabel" style="color:var(--blue);font-weight:700;font-size:15px"></div>'
    + '</div><div class="sales-hero-right">'
    + '<h3>Subscribe with PayPal</h3>'
    + '<div id="paypalFormWrap"></div>'
    + '<div class="powered">POWERED BY PAYPAL BUSINESS</div>'
    + '</div></div>'

    // ── Feature grid ──
    + '<div class="sales-strip"><div><h3>Any Sector. Any Stocks. Any News.</h3>'
    + '<p>Tech, biotech, energy, finance, defense, REITs — pick the sectors that matter; we pull the news.</p></div>'
    + '<span class="signal signal-buy" style="font-size:11px;padding:6px 14px">11 GICS SECTORS</span></div>'
    + '<h3>What\'s Included</h3><div class="grid grid-3">'
    + [['Up to 50 stocks','Any sector, any exchange. NYSE, NASDAQ, plus custom tickers.'],
       ['5 AI bots','Daily, weekly, monthly — plus two market-cap benchmarks.'],
       ['Daily Buy/Sell/Hold','Composite signals on every stock you picked.'],
       ['Custom news feed','Pick the sectors. We curate, dedupe, deliver.'],
       ['Sunday auto-reports','Weekly grades, pros/cons, trade-by-trade review.'],
       ['One login, all sites','Add crypto or AI &amp; Quantum for $29.99/mo each.']].map(p =>
         '<div class="card"><h3 style="color:var(--blue);margin-bottom:8px">✓ '+p[0]+'</h3>'
         + '<p style="color:var(--muted);font-size:13px;margin:0">'+p[1]+'</p></div>').join('')
    + '</div>'
    + '<div class="panel" style="margin-top:24px">'
    + '<p style="color:var(--muted);font-size:13px;margin:0 0 8px 0">Built by an operator who runs the same system on his own portfolio. Cancel anytime from your PayPal account. Questions? <a href="mailto:info@wallstbots.tech" style="color:var(--blue)">info@wallstbots.tech</a></p>'
    + '<p style="font-size:13px;margin:0">Refer a friend → they get <strong style="color:var(--blue)">50% off their first month</strong> and you earn a <strong style="color:var(--blue)">$35 bill credit</strong>. <a href="#/referral" style="color:var(--blue)">Learn more →</a></p>'
    + '</div>';

  // Initialize UI
  GY_CYCLE = 'annual';
  GY_REF   = '';
  GY_VALID = false;
  updateGyPricing();

  // Auto-apply ref from URL
  if (urlRef) {
    const inp = $('refInput');
    if (inp) inp.value = urlRef.toUpperCase();
    applyRefCode();
  }
}

function setGyCycle(cycle) {
  GY_CYCLE = cycle;
  updateGyPricing();
}

function updateGyPricing() {
  const annual   = GY_CYCLE === 'annual';
  const hasRef   = GY_VALID;
  const first    = annual ? PRICING.firstAnnual   : PRICING.firstMonthly;
  const add      = annual ? PRICING.addAnnual     : PRICING.addMonthly;
  const firstRef = annual ? PRICING.refAnnual     : PRICING.refMonthly;
  const suffix   = annual ? '/yr' : '/mo';
  const period   = annual ? '365 days' : '30 days';

  // Cycle buttons
  ['cycleMonthly','cycleAnnual'].forEach(id => {
    const el = $(id);
    if (!el) return;
    const active = (id === 'cycleAnnual') === annual;
    el.style.background = active ? 'var(--blue)' : 'transparent';
    el.style.color       = active ? '#fff'        : 'var(--muted)';
  });

  // Price cards
  const p1 = $('price1'), p1s = $('price1sub');
  const p2 = $('price2'), p2s = $('price2sub');
  if (p1) {
    if (hasRef) {
      p1.innerHTML = '<span style="text-decoration:line-through;color:var(--muted);font-size:18px">$'+first.toFixed(2)+'</span> $'+firstRef.toFixed(2);
      p1.style.color = '#10b981';
    } else {
      p1.textContent = '$' + first.toFixed(2);
      p1.style.color = '';
    }
  }
  if (p1s) p1s.textContent = hasRef
    ? (annual ? '20% off — then $799/yr' : '50% off 1st month — then $79.99/mo')
    : suffix + ' · auto-renews · cancel anytime';
  if (p2) p2.textContent = '$' + add.toFixed(2);
  if (p2s) p2s.textContent = suffix + ' per extra portfolio (any Level 13 site)';

  // Active price label
  const lbl = $('activePriceLabel');
  if (lbl) {
    lbl.textContent = hasRef
      ? '$' + firstRef.toFixed(2) + suffix + ' today (referral discount applied!)'
      : '$' + first.toFixed(2) + suffix + ' · auto-renews · cancel anytime';
  }

  // Rebuild PayPal form
  renderPaypalForm();
}

async function applyRefCode() {
  const inp = $('refInput');
  const msg = $('refMsg');
  if (!inp || !msg) return;
  const code = inp.value.trim().toUpperCase();
  if (!code) { msg.innerHTML = ''; return; }

  msg.innerHTML = '<span style="color:var(--muted)">Validating…</span>';
  try {
    const r = await fetch('https://api.lvl13.tech/subscriptions/validate-referral?code=' + encodeURIComponent(code));
    const d = await r.json();
    if (d.valid) {
      GY_REF   = d.code;
      GY_VALID = true;
      msg.innerHTML = '<span style="color:#10b981;font-weight:700">✓ Referral code applied! '
        + (GY_CYCLE === 'annual'
          ? 'Save $' + d.annual_savings.toFixed(2) + ' on your annual plan.'
          : 'First month just $' + d.monthly_first_payment.toFixed(2) + ' (50% off).')
        + '</span>';
    } else {
      GY_REF   = '';
      GY_VALID = false;
      msg.innerHTML = '<span style="color:var(--red)">✗ ' + (d.message || 'Invalid code.') + '</span>';
    }
  } catch (_) {
    GY_REF   = '';
    GY_VALID = false;
    msg.innerHTML = '<span style="color:var(--muted)">Could not validate — check your connection.</span>';
  }
  updateGyPricing();
}

function renderPaypalForm() {
  const wrap = $('paypalFormWrap');
  if (!wrap) return;
  const paypal = STATE.meta.paypalEmail;
  const annual = GY_CYCLE === 'annual';
  const ref    = GY_VALID ? GY_REF : '';
  const base   = annual ? '799.00' : '79.99';
  const unit   = annual ? 'Y'      : 'M';
  const label  = annual ? 'Annual' : 'Monthly';
  const btnTxt = annual ? 'Subscribe — $799/yr' : 'Subscribe — $79.99/mo';

  // With referral: use trial pricing (a1/p1/t1 for first discounted payment)
  const firstAmt = annual ? '639.20' : '39.99';
  const refFields = ref
    ? '<input type="hidden" name="a1" value="'+firstAmt+'">'
    + '<input type="hidden" name="p1" value="1">'
    + '<input type="hidden" name="t1" value="'+unit+'">'
    + '<input type="hidden" name="custom" value="'+escapeHtml(ref)+'">'
    : '';
  const refBtnTxt = ref
    ? (annual ? 'Subscribe — $639.20 today, then $799/yr' : 'Subscribe — $39.99 today, then $79.99/mo')
    : btnTxt;

  wrap.innerHTML =
    '<form action="https://www.paypal.com/cgi-bin/webscr" method="post" target="_top" style="margin:0">'
    + '<input type="hidden" name="cmd" value="_xclick-subscriptions">'
    + '<input type="hidden" name="business" value="'+paypal+'">'
    + '<input type="hidden" name="lc" value="US">'
    + '<input type="hidden" name="item_name" value="wallstbots.tech Custom Tracker - '+label+'">'
    + '<input type="hidden" name="no_note" value="1"><input type="hidden" name="no_shipping" value="1">'
    + '<input type="hidden" name="src" value="1">'
    + refFields
    + '<input type="hidden" name="a3" value="'+base+'">'
    + '<input type="hidden" name="p3" value="1"><input type="hidden" name="t3" value="'+unit+'">'
    + '<input type="hidden" name="currency_code" value="USD">'
    + '<input type="hidden" name="return" value="https://wallstbots.tech/#/thanks">'
    + '<input type="hidden" name="cancel_return" value="https://wallstbots.tech/#/get-yours">'
    + '<button type="submit" class="paypal-btn">'+refBtnTxt+'</button>'
    + '</form>'
    + '<div style="font-size:12px;margin-top:6px;opacity:0.85">'
    + (ref
      ? 'Referral discount applied to first payment. Renews at $'+base+'/'+unit.toLowerCase()+' afterwards.'
      : '$'+base+' today, $'+base+' every '+(annual?'365 days':'30 days'))
    + '</div>';
}

function renderThanks() {
  // Extract referral code from localStorage (set during signup) or just show generic
  const refCode = localStorage.getItem('myReferralCode') || '';
  const siteBase = 'https://wallstbots.tech/#/get-yours';
  const refLink  = refCode ? siteBase + '?ref=' + refCode : '';

  $('app').innerHTML = '<section class="hero"><div class="hero-content">'
    + '<h1>You\'re in. 🎉</h1>'
    + '<p>Your Wall St. Bots tracker will be live within 24 hours. Check your email for your setup link.</p>'
    + '<div class="hero-ctas"><a class="btn btn-primary" href="#/">Back to Dashboard</a></div>'
    + '</div></section>'
    + '<div class="panel" style="margin-top:24px;border:2px solid var(--blue)">'
    + '<h3 style="color:var(--blue);margin-bottom:8px">Earn $35 per referral</h3>'
    + '<p style="color:var(--muted);margin-bottom:16px">Share your referral link. Your friend gets <strong style="color:var(--fg)">50% off their first month</strong> (or 20% off annual). You earn <strong style="color:var(--fg)">$35 credit</strong> applied to your next bill — automatically.</p>'
    + (refCode
      ? '<div style="background:var(--surface2);border-radius:8px;padding:12px 16px;font-family:monospace;font-size:14px;color:var(--blue);word-break:break-all;margin-bottom:12px">'
        + escapeHtml(refLink) + '</div>'
        + '<button onclick="navigator.clipboard.writeText(\''+escapeHtml(refLink)+'\').then(()=>{this.textContent=\'Copied!\';setTimeout(()=>this.textContent=\'Copy Link\',2000)})" '
        + 'style="background:var(--blue);color:#fff;border:none;border-radius:8px;padding:10px 20px;font-weight:700;cursor:pointer">Copy Link</button>'
      : '<p style="color:var(--muted);font-size:13px">Your referral code will be in your welcome email. <a href="#/referral" style="color:var(--blue)">Learn more about the referral program →</a></p>')
    + '</div>';
}

// ============ PAGE: REFERRAL PROGRAM ============
function renderReferral() {
  $('app').innerHTML =
    '<section class="hero" style="margin-bottom:24px"><div class="hero-content">'
    + '<span class="hero-eyebrow">Referral Program</span>'
    + '<h1>Share the edge. Get paid.</h1>'
    + '<p>Every time a friend subscribes using your referral link, you earn <strong style="color:var(--blue)">$35 credit</strong> applied to your next bill automatically. They get <strong style="color:var(--blue)">50% off their first month</strong> — or <strong style="color:var(--blue)">20% off an annual plan</strong>. Everyone wins.</p>'
    + '</div></section>'

    // How it works
    + '<h3>How It Works</h3>'
    + '<div class="grid grid-3" style="margin-bottom:32px">'
    + [['1. Share Your Link','Copy your personal referral link and send it to anyone who trades or invests. Works across all three Level 13 sites.'],
       ['2. They Subscribe','Your friend clicks your link, sees their discount pre-applied, and subscribes with PayPal. No extra steps.'],
       ['3. You Both Win','They save on day one. You automatically get $35 credited to your account — reduces your next auto-bill.']].map(p =>
         '<div class="card"><h3 style="color:var(--blue);margin-bottom:8px">'+p[0]+'</h3>'
         + '<p style="color:var(--muted);font-size:13px;margin:0">'+p[1]+'</p></div>').join('')
    + '</div>'

    // Discount details
    + '<div class="panel" style="margin-bottom:24px">'
    + '<h3 style="margin-bottom:16px">Referral Discounts</h3>'
    + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">'
    + '<div style="background:var(--surface2);border-radius:10px;padding:16px">'
    + '<div style="font-size:11px;font-weight:700;letter-spacing:1px;color:var(--blue);margin-bottom:8px;text-transform:uppercase">Monthly Plan</div>'
    + '<div style="font-size:22px;font-weight:800;margin-bottom:4px"><span style="text-decoration:line-through;color:var(--muted);font-size:16px">$79.99</span> $39.99</div>'
    + '<div style="font-size:13px;color:var(--muted)">First month only — then $79.99/mo</div>'
    + '</div>'
    + '<div style="background:var(--surface2);border-radius:10px;padding:16px">'
    + '<div style="font-size:11px;font-weight:700;letter-spacing:1px;color:var(--blue);margin-bottom:8px;text-transform:uppercase">Annual Plan</div>'
    + '<div style="font-size:22px;font-weight:800;margin-bottom:4px"><span style="text-decoration:line-through;color:var(--muted);font-size:16px">$799.00</span> $639.20</div>'
    + '<div style="font-size:13px;color:var(--muted)">20% off — then $799/yr at renewal</div>'
    + '</div></div>'
    + '<p style="margin:16px 0 0 0;font-size:13px;color:var(--muted)">Discounts apply to the first portfolio only. Additional portfolios are $29.99/mo or $299/yr regardless.</p>'
    + '</div>'

    // Referrer credit info
    + '<div class="panel" style="margin-bottom:24px;border:1px solid var(--blue)">'
    + '<h3 style="margin-bottom:8px;color:var(--blue)">Your $35 Credit</h3>'
    + '<p style="color:var(--muted);margin:0">Each time someone redeems your referral code, $35 is added to your account credit balance. On your next billing date, your autobill is automatically reduced by your full credit balance. No action required — it happens on its own.</p>'
    + '<p style="font-size:13px;color:var(--muted);margin-top:8px">There\'s no cap on referrals. Refer 10 people → $350 credit. Refer enough and your tracker pays for itself.</p>'
    + '</div>'

    // My dashboard (requires login)
    + '<div class="panel" id="referralDashboard"><p style="color:var(--muted);text-align:center">Loading your referral stats…</p></div>'

    + '<div class="panel" style="margin-top:24px;text-align:center">'
    + '<a class="btn btn-primary" href="#/get-yours">Get Your Tracker →</a>'
    + '</div>';

  // Attempt to load referral stats from backend
  loadReferralDashboard();
}

async function loadReferralDashboard() {
  const token = localStorage.getItem('auth_token');
  const dash  = $('referralDashboard');
  if (!dash) return;

  if (!token) {
    dash.innerHTML = '<p style="text-align:center;color:var(--muted)">Already a subscriber? '
      + '<a href="/login.html" style="color:var(--blue)">Log in</a> to see your referral code and earnings.</p>';
    return;
  }

  try {
    const r = await fetch('https://api.lvl13.tech/account/referral', {
      headers: { 'Authorization': 'Bearer ' + token }
    });
    if (!r.ok) throw new Error('not_authed');
    const d = await r.json();

    const link = d.share_links.wallstbots;
    const txRows = (d.transactions || []).map(t =>
      '<tr><td style="color:'+(t.amount>0?'#10b981':'var(--red)')+'">'+
      (t.amount>0?'+':'')+t.amount.toFixed(2)+'</td>'
      + '<td>'+t.description+'</td>'
      + '<td style="color:var(--muted)">'+t.date+'</td></tr>'
    ).join('');

    dash.innerHTML =
      '<h3 style="margin-bottom:16px">Your Referral Dashboard</h3>'
      // Stats row
      + '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px">'
      + '<div style="background:var(--surface2);border-radius:10px;padding:14px;text-align:center">'
      + '<div style="font-size:24px;font-weight:800;color:var(--blue)">'+d.total_redemptions+'</div>'
      + '<div style="font-size:12px;color:var(--muted)">Referrals Redeemed</div></div>'
      + '<div style="background:var(--surface2);border-radius:10px;padding:14px;text-align:center">'
      + '<div style="font-size:24px;font-weight:800;color:#10b981">$'+d.credit_balance.toFixed(2)+'</div>'
      + '<div style="font-size:12px;color:var(--muted)">Current Credit Balance</div></div>'
      + '<div style="background:var(--surface2);border-radius:10px;padding:14px;text-align:center">'
      + '<div style="font-size:24px;font-weight:800;color:var(--fg)">$'+d.total_credits_earned.toFixed(2)+'</div>'
      + '<div style="font-size:12px;color:var(--muted)">Total Credits Earned</div></div>'
      + '</div>'
      // Referral code
      + '<div style="margin-bottom:16px">'
      + '<div style="font-size:11px;font-weight:700;letter-spacing:1px;color:var(--muted);margin-bottom:6px;text-transform:uppercase">Your Referral Code</div>'
      + '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
      + '<div style="background:var(--surface2);border-radius:8px;padding:10px 16px;font-family:monospace;font-size:18px;font-weight:700;color:var(--blue);letter-spacing:2px">'+d.referral_code+'</div>'
      + '<button onclick="navigator.clipboard.writeText(\''+escapeHtml(d.referral_code)+'\').then(()=>{this.textContent=\'Copied!\';setTimeout(()=>this.textContent=\'Copy Code\',2000)})" '
      + 'style="background:var(--surface2);color:var(--blue);border:1px solid var(--blue);border-radius:8px;padding:10px 16px;font-weight:700;cursor:pointer">Copy Code</button>'
      + '</div></div>'
      // Share link
      + '<div style="margin-bottom:20px">'
      + '<div style="font-size:11px;font-weight:700;letter-spacing:1px;color:var(--muted);margin-bottom:6px;text-transform:uppercase">Your Referral Link</div>'
      + '<div style="background:var(--surface2);border-radius:8px;padding:10px 14px;font-size:13px;color:var(--fg);word-break:break-all;margin-bottom:8px">'+escapeHtml(link)+'</div>'
      + '<button onclick="navigator.clipboard.writeText(\''+escapeHtml(link)+'\').then(()=>{this.textContent=\'Copied!\';setTimeout(()=>this.textContent=\'Copy Link\',2000)})" '
      + 'style="background:var(--blue);color:#fff;border:none;border-radius:8px;padding:10px 20px;font-weight:700;cursor:pointer">Copy Link</button>'
      + '</div>'
      // Transaction history
      + (txRows
        ? '<h3 style="margin-bottom:10px">Credit History</h3>'
          + '<div class="tbl-wrap"><table><thead><tr>'
          + '<th>Amount</th><th>Description</th><th>Date</th>'
          + '</tr></thead><tbody>'+txRows+'</tbody></table></div>'
        : '<p style="color:var(--muted);font-size:13px">No referral activity yet. Share your link to start earning!</p>');

  } catch (_) {
    dash.innerHTML = '<p style="text-align:center;color:var(--muted)">Could not load referral stats. '
      + '<a href="/login.html" style="color:var(--blue)">Log in</a> if you haven\'t already.</p>';
  }
}

// ================================================================
// CHATBOT — FAQ engine
// ================================================================
const FAQS = [
  { q: ['price','cost','how much','pricing','799','79'], a: "First portfolio: $79.99/mo or $799/yr. Each additional (stocks, crypto, or AI & Quantum): $29.99/mo or $299/yr. Have a referral code? Get 50% off your first month or 20% off annual." },
  { q: ['referral','refer','code','discount'], a: "Share your referral code and earn $35 credit per friend who subscribes — automatically deducted from your next bill. Your friend gets 50% off their first month (or 20% off annual). No cap on referrals." },
  { q: ['cancel','refund','stop'], a: "Cancel anytime from your PayPal account → Settings → Automatic Payments. No further charges after cancellation." },
  { q: ['stocks','tickers','how many'], a: "Up to 50 stocks from any sector (NYSE, NASDAQ, plus most listed tickers). You pick them after checkout." },
  { q: ['sector','sectors','industries'], a: "Any of the 11 GICS sectors — tech, biotech, energy, financials, industrials, real estate, you name it. We fetch news for the sectors you choose." },
  { q: ['news','articles','sources'], a: "We pull from 80+ sources via NewsAPI, dedupe, and filter to the sectors you picked. Updated every night." },
  { q: ['bot','bots','strategy','strategies'], a: "5 strategies race on the SAME stock list: BOT13 (daily intraday), ORACLE (weekly Monday rebalance), WIZARD (monthly hold), EQUALIZER (equal-weight baseline), TITAN (cap-weighted baseline)." },
  { q: ['signals','buy','sell','hold'], a: "Every trading day we score every stock on your list — momentum, RSI, MACD, volume, volatility — and label it Strong Buy / Buy / Hold / Sell / Strong Sell." },
  { q: ['report','reports','sunday','weekly'], a: "Every Sunday you get an auto-generated report: each fund's grade, what they bought/sold, why, and what's coming up." },
  { q: ['real money','live trade','execute','broker'], a: "Nope — these are paper portfolios for research and signals. We don't touch a brokerage account. You see what the bots WOULD do, then decide for yourself." },
  { q: ['data','privacy','share','sell my'], a: "Your data stays yours. We don't share or sell. Your tracker runs on a private endpoint — only you see it." },
  { q: ['contact','support','help','email'], a: "Email info@wallstbots.tech anytime. Built and supported directly by the operator." },
  { q: ['how long','setup','time','when'], a: "Tracker is live within 24 hours of checkout. You'll get an email with your private dashboard link." },
];
function botAnswer(input) {
  const q = (input || '').toLowerCase().trim();
  if (!q) return null;
  for (const item of FAQS) {
    if (item.q.some(k => q.includes(k))) return item.a;
  }
  return "I don't have an answer for that yet — but the operator does. Email info@wallstbots.tech and you'll get a real reply, fast.";
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
// AUTH-AWARE NAV — show Dashboard if logged in, Log In if not
// ================================================================
function updateNavAuthState() {
  const loginBtn = document.getElementById('navLoginBtn');
  const dashBtn  = document.getElementById('navDashBtn');
  if (!loginBtn || !dashBtn) return;
  const loggedIn = !!localStorage.getItem('auth_token');
  loginBtn.style.display = loggedIn ? 'none' : '';
  dashBtn.style.display  = loggedIn ? ''     : 'none';
}

// ================================================================
// BOOTSTRAP
// ================================================================
function wireUI() {
  const mt = document.getElementById('menuToggle');
  if (mt) mt.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleMenu();
    const open = document.getElementById('siteNav') && document.getElementById('siteNav').classList.contains('open');
    mt.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
  document.querySelectorAll('.site-nav a').forEach(a => {
    a.addEventListener('click', () => closeMenu());
  });
  document.addEventListener('click', (e) => {
    const nav = document.getElementById('siteNav');
    const toggle = document.getElementById('menuToggle');
    if (nav && toggle && !nav.contains(e.target) && !toggle.contains(e.target)) closeMenu();
  });
  // chatbot
  const ct = document.getElementById('chatbotToggle');
  if (ct) ct.addEventListener('click', chatbotOpen);
  const cc = document.getElementById('chatbotClose');
  if (cc) cc.addEventListener('click', chatbotClose);
  const cf = document.getElementById('chatbotForm');
  if (cf) cf.addEventListener('submit', (e) => {
    e.preventDefault();
    const inp = document.getElementById('chatbotInput');
    if (!inp || !inp.value.trim()) return;
    const q = inp.value.trim();
    chatbotAddMsg(q, 'user');
    inp.value = '';
    chatbotAddMsg(botAnswer(q) || "Email info@wallstbots.tech for help!", 'bot');
  });
  chatbotRenderQuick();
}

window.addEventListener('hashchange', route);
document.addEventListener('DOMContentLoaded', () => {
  wireUI();
  updateNavAuthState();
  loadAll();
});
