/* ================================================================
   bitbot13.tech — single-page app  v1
   Identical engine to lvl13.tech — top 50 crypto universe
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
               tagline:"Daily intraday bot. Buys at open, sells before close. Skips the session if no edge." },
  oracle:    { name:'ORACLE',    icon:'OR', color:'#a855f7', kind:'WEEKLY',
               tagline:"Weekly bot. Trades every Monday. All-in on the week's best bets." },
  wizard:    { name:'WIZARD',    icon:'WZ', color:'#10b981', kind:'MONTHLY',
               tagline:"Monthly hold bot. Buys the 1st of the month, sells the last. Slow and patient." },
  equalizer: { name:'EQUALIZER', icon:'EQ', color:'#00d4ff', kind:'BASELINE',
               tagline:"Equal weight. No favorites. $1,000 in every coin." },
  titan:     { name:'TITAN',     icon:'TT', color:'#ff8c00', kind:'BASELINE',
               tagline:"Half on the heavyweights. Half on the rest. Concentration meets coverage." },
};
const FUND_ORDER = ['bot13','oracle','wizard','equalizer','titan'];

// ============ DATA LOADING — local files ============
async function loadAll() {
  if (location.protocol === 'file:') { showFileProtocolWarning(); return; }
  try {
    const r = await Promise.allSettled([
      fetch('data/state.json',   { cache: 'no-store' }).then(r => r.json()).then(r => r.data),
      fetch('data/news.json',    { cache: 'no-store' }).then(r => r.json()).then(r => r.data),
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
  if (v.includes('layer 1') || v.includes('l1'))              return 'tech';
  if (v.includes('defi') || v.includes('decentralized fin'))  return 'finance';
  if (v.includes('exchange') || v.includes('dex'))            return 'finance';
  if (v.includes('smart contract') || v.includes('platform')) return 'tech';
  if (v.includes('gaming') || v.includes('metaverse'))        return 'other';
  if (v.includes('payment') || v.includes('transfer'))        return 'finance';
  if (v.includes('meme') || v.includes('community'))          return 'other';
  if (v.includes('storage') || v.includes('compute'))         return 'tech';
  if (v.includes('privacy') || v.includes('anonymous'))       return 'other';
  if (v.includes('oracle') || v.includes('data'))             return 'tech';
  return 'other';
}
function getYoursHint(msg) {
  msg = msg || 'Want this tracker running on YOUR coins?';
  return '<a class="get-yours-hint" href="#/get-yours" style="text-decoration:none"><span class="arrow">→</span><span class="msg">'+msg+'</span><span class="pill">GET YOURS</span></a>';
}
function fundCard(fid, data) {
  const meta = FUND_META[fid];
  const cap = (STATE.funds && STATE.funds.starting_capital) || 50000;
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

  const cap = (STATE.funds && STATE.funds.starting_capital) || 50000;
  const coinCount = (() => {
    const eq = STATE.funds && STATE.funds.funds && STATE.funds.funds.equalizer;
    return eq && eq.value && eq.value.positions ? eq.value.positions.length : 50;
  })();

  $('app').innerHTML =
    '<section class="hero"><img src="assets/robot.svg" alt="" class="hero-robot">'
    + '<div class="hero-content"><span class="hero-eyebrow">Crypto Trading Bot Tracker</span>'
    + '<h1>5 strategies. '+coinCount+' coins. Watch them race.</h1>'
    + '<p>Three bots — daily, weekly, monthly — trading head-to-head against two passive strategies on the top 50 crypto by market cap. No stablecoins. 24/7 markets. '+fmt$0(cap)+' starting capital. Daily Buy/Sell/Hold signals on every coin. Crypto news, filtered to what matters. <strong>Welcome to BitBot13.</strong></p>'
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

    + getYoursHint('Run this exact dashboard on YOUR coins. Custom bots, custom news.');
  drawTrajectory();
}

// ============ PAGE: NEWS-ALL ============
function renderNewsAll() {
  const news = STATE.news || { items: [] };
  const sectors = news.sectors || ['LAYER 1','DEFI','EXCHANGE','SMART CONTRACT','GAMING','PAYMENT','MEME','STORAGE','PRIVACY','ORACLE'];
  const items = (news.items || []).filter(i =>
    SECTOR_FILTER === 'ALL' || (i.sector || '').toUpperCase() === SECTOR_FILTER);
  const chips = ['ALL', ...sectors].map(s =>
    '<button class="sector-chip '+(SECTOR_FILTER===s?'active':'')+'" onclick="SECTOR_FILTER=\''+s+'\'; renderNewsAll()">'+s+'</button>'
  ).join('');
  const cards = items.length ? items.map(newsCard).join('')
    : '<p class="sub">No headlines for this category yet.</p>';

  $('app').innerHTML = '<h1>News</h1>'
    + '<p class="sub">Filtered crypto headlines from across the market. Updated nightly. Click any card to read at the source.</p>'
    + '<div class="sector-bar"><span class="sector-bar-label">Filter:</span>'+chips+'</div>'
    + '<div class="news-grid">'+cards+'</div>'
    + '<div class="sales-strip" style="margin-top:36px">'
    + '<div><h3>Want news for YOUR crypto picks?</h3>'
    + '<p>Pick the coins you care about. We curate, dedupe, deliver — straight to your private dashboard.</p></div>'
    + '<a href="#/get-yours" class="btn btn-primary" style="margin-left:auto">Get Yours →</a></div>'
    + '<div class="grid grid-3" style="margin-top:18px">'
    + [['Custom news feed','Pick your chains and projects — Layer 1, DeFi, gaming, meme, and more.'],
       ['Daily refresh','Headlines pulled fresh every night.'],
       ['Source-direct','Every card links straight to the original article.']].map(p =>
         '<div class="card"><h3 style="color:var(--blue)">✓ '+p[0]+'</h3>'
         + '<p style="color:var(--muted);font-size:13px;margin:0">'+p[1]+'</p></div>').join('')
    + '</div>'
    + getYoursHint('Build the same news feed on YOUR coins.');
}

// ============ PAGE: HOW IT WORKS ============
function renderHowItWorks() {
  const bots = [
    { id:'bot13',     l1:'Buys at session open, sells before close.', l2:'Skips the session if no edge. Runs 24/7.' },
    { id:'oracle',    l1:'Trades every Monday morning.',              l2:'Holds for the week.' },
    { id:'wizard',    l1:'Buys 1st day of month.',                   l2:'Liquidates the last day.' },
    { id:'equalizer', l1:'$1,000 in every coin.',                    l2:'Equal weight, no favorites.' },
    { id:'titan',     l1:'Half on top-10 mega-caps.',                l2:'Half across the rest.' },
  ];
  const stripCards = bots.map(b => {
    const m = FUND_META[b.id];
    return '<div class="bot-strip-card '+b.id+'"><div class="fund-head">'
      + '<span class="fund-icon '+b.id+'">'+m.icon+'</span><div class="fund-name">'+m.name+'</div></div>'
      + '<div class="kind">'+m.kind+'</div><div class="l1">'+b.l1+'</div><div class="l2">'+b.l2+'</div></div>';
  }).join('');
  const features = [
    ['Daily Buy / Sell / Hold','Composite analysis on every coin — every day. Score combines momentum, RSI, MACD, volume, volatility into a Strong Buy → Strong Sell call with target price.'],
    ['Auto Reports, Every Sunday','Weekly grades A–F per strategy. Pros, cons, narrative for what worked. Trade-by-trade review for every bot.'],
    ['Crypto News, Filtered','Headlines pulled from across the crypto market. Layer 1, DeFi, gaming tokens, meme coins — pick what you follow.'],
  ];
  const featureCards = features.map(f =>
    '<div class="card"><h3 style="color:var(--blue)">✓ '+f[0]+'</h3>'
    + '<p style="color:var(--muted);font-size:13px;margin:0">'+f[1]+'</p></div>').join('');
  $('app').innerHTML = '<h1>How It Works</h1>'
    + '<p class="sub">Five strategies. One universe. The same starting capital. Then we watch.</p>'
    + '<h3>The 5 Strategies</h3><div class="bot-strip">'+stripCards+'</div>'
    + '<h3>What You Get</h3><div class="grid grid-3">'+featureCards+'</div>'
    + '<div class="sales-strip" style="margin-top:24px"><div><h3>The Challenge.</h3>'
    + '<p>Can three bots beat two passive strategies on the same 50-coin universe with the same money? Crypto never sleeps — neither do the bots.</p></div></div>'
    + getYoursHint('Want this on YOUR coins, with YOUR picks?');
}

// ============ PAGE: THE RACE ============
function renderRace() {
  const cap = (STATE.funds && STATE.funds.starting_capital) || 50000;
  const coinCount = (() => {
    const eq = STATE.funds && STATE.funds.funds && STATE.funds.funds.equalizer;
    return eq && eq.value && eq.value.positions ? eq.value.positions.length : 50;
  })();
  const cards = FUND_ORDER.map(fid =>
    fundCard(fid, STATE.funds && STATE.funds.funds ? STATE.funds.funds[fid] : null)).join('');
  $('app').innerHTML = '<h1>The Race</h1>'
    + '<p class="sub">Five strategies. '+fmt$0(cap)+' each. Same '+coinCount+'-coin universe. Refreshed daily.</p>'
    + '<div class="grid grid-5">'+cards+'</div>'
    + '<div class="panel" style="margin-top:24px"><h3>Performance Trajectory — All 5 Strategies</h3>'
    + '<div class="chart-wrap"><canvas id="chartRace"></canvas></div></div>'
    + getYoursHint('This race is yours to design. Pick coins, tokens, strategy.');
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
  const cap = (STATE.funds && STATE.funds.starting_capital) || 50000;
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
          + '<td class="num">'+shares.toFixed(4)+'</td>'
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
    + '<thead><tr><th>Symbol</th><th class="num">Units</th><th class="num">Entry</th>'
    + '<th class="num">Price</th><th class="num">Value</th><th class="num">Today</th>'
    + '<th class="num">P&amp;L</th><th class="num">%</th></tr></thead>'
    + '<tbody>'+positionRows+'</tbody></table></div></div>'
    + getYoursHint('Want a '+meta.name.toLowerCase()+'-style bot on YOUR coin list?');
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
    + '<p class="sub">Composite analysis on every coin in the universe. Updated daily'+(data.generated_at?' — last run '+relTime(data.generated_at):'')+'.</p>'
    + summary + filterHTML
    + '<div class="panel"><div class="tbl-wrap"><table><thead><tr>'
    + '<th>Symbol</th><th>Action</th><th class="num">Price</th><th class="num">Target</th>'
    + '<th class="num">Upside</th><th class="num">Score</th><th>Conf</th><th>Risk</th>'
    + '<th class="num">RSI</th><th class="num">5d</th><th class="num">20d</th>'
    + '</tr></thead><tbody>'+rows+'</tbody></table></div></div>'
    + '<div class="panel" style="font-size:12px;color:var(--muted);line-height:1.7">'
    + '<strong style="color:var(--text)">How signals are computed.</strong> '
    + 'Composite score blends 5d &amp; 20d momentum, MACD bias, RSI(14), volume confirmation, and a volatility penalty. '
    + 'Strong Buy ≥ +12. Buy ≥ +4. Sell ≤ −4 or extreme overbought + bearish MACD. Strong Sell ≤ −12.</div>'
    + getYoursHint('Get this signal table on YOUR 50 coins.');
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
    + '<div class="hero-content"><span class="hero-eyebrow">Master Crypto — Without the Risk</span>'
    + '<h1>You\'ve seen what it does. Now make it yours.</h1>'
    + '<p>Build, test, and refine your crypto portfolio with a market research tool built for the modern trader. Track up to 50 coins simultaneously with daily technical analysis — Buy/Sell/Hold signals analyzed by AI. Plus, never miss a beat with personalized crypto news delivered straight to your dashboard. <strong style="color:var(--blue)">BitBot13</strong> lets you master the market without the risk.</p></div></section>'
    + '<div class="sales-hero"><div class="sales-hero-left">'
    + '<h2 style="font-size:28px;letter-spacing:-0.5px">BUILD YOUR OWN</h2>'
    + '<p style="color:var(--muted);font-size:15px">Pick up to 50 coins from any chain or category. Three custom AI bots. Custom news feed. Sunday auto-reports.</p>'
    + '<p style="color:var(--blue);font-weight:700;font-size:15px">$799/year &nbsp;·&nbsp; auto-renews &nbsp;·&nbsp; cancel anytime</p>'
    + '</div><div class="sales-hero-right"><h3>Subscribe with PayPal</h3>'
    + '<form action="https://www.paypal.com/cgi-bin/webscr" method="post" target="_top" style="margin:0">'
    + '<input type="hidden" name="cmd" value="_xclick-subscriptions">'
    + '<input type="hidden" name="business" value="'+paypal+'">'
    + '<input type="hidden" name="lc" value="US">'
    + '<input type="hidden" name="item_name" value="bitbot13.tech Custom Tracker - Annual">'
    + '<input type="hidden" name="no_note" value="1"><input type="hidden" name="no_shipping" value="1">'
    + '<input type="hidden" name="src" value="1"><input type="hidden" name="a3" value="799.00">'
    + '<input type="hidden" name="p3" value="1"><input type="hidden" name="t3" value="Y">'
    + '<input type="hidden" name="currency_code" value="USD">'
    + '<input type="hidden" name="return" value="https://bitbot13.tech/#/thanks">'
    + '<input type="hidden" name="cancel_return" value="https://bitbot13.tech/#/get-yours">'
    + '<button type="submit" class="paypal-btn">Subscribe — $799/yr</button></form>'
    + '<div style="font-size:12px;margin-top:6px;opacity:0.85">$799 today, $799 every 365 days</div>'
    + '<div class="powered">POWERED BY PAYPAL BUSINESS</div></div></div>'
    + '<div class="sales-strip"><div><h3>Any Chain. Any Coins. Any News.</h3>'
    + '<p>BTC maxis, ETH degens, altcoin hunters, DeFi explorers — pick the coins that matter; we pull the news.</p></div>'
    + '<span class="signal signal-buy" style="font-size:11px;padding:6px 14px">TOP 50 CRYPTO</span></div>'
    + '<h3>What\'s Included</h3><div class="grid grid-3">'
    + [['Up to 50 coins','Any chain, any category. BTC, ETH, altcoins, DeFi, gaming tokens.'],
       ['3 AI bots','Daily, weekly, monthly — all yours.'],
       ['2 baselines','Equal-weight + market-cap weighted benchmarks.'],
       ['Daily Buy/Sell/Hold','Composite signals on every coin you picked.'],
       ['Custom news feed','Pick your chains and projects. We curate, dedupe, deliver.'],
       ['Sunday auto-reports','Weekly grades, pros/cons, trade-by-trade review.']].map(p =>
         '<div class="card"><h3 style="color:var(--blue);margin-bottom:8px">✓ '+p[0]+'</h3>'
         + '<p style="color:var(--muted);font-size:13px;margin:0">'+p[1]+'</p></div>').join('')
    + '</div>'
    + '<div class="panel" style="margin-top:24px;text-align:center">'
    + '<p style="color:var(--muted);font-size:13px;font-style:italic;margin:0">Built by an operator who runs the same system on his own portfolio. Cancel anytime from your PayPal account. Questions? <a href="mailto:info@bitbot13.tech" style="color:var(--blue)">info@bitbot13.tech</a></p></div>';
}

function renderThanks() {
  $('app').innerHTML = '<section class="hero"><div class="hero-content">'
    + '<h1>You\'re in. 🎉</h1>'
    + '<p>Your BitBot13 tracker will be live within 24 hours. Check your email for your private dashboard link.</p>'
    + '<div class="hero-ctas"><a class="btn btn-primary" href="#/">Back to Dashboard</a></div>'
    + '</div></section>';
}

// ================================================================
// CHATBOT — FAQ engine
// ================================================================
const FAQS = [
  { q: ['price','cost','how much','pricing','799'], a: "Custom Tracker is $799/year (auto-renews, cancel anytime from your PayPal account). One flat price, all 5 strategies, your coins, your news." },
  { q: ['cancel','refund','stop'], a: "Cancel anytime from your PayPal account → Settings → Automatic Payments. No refund for the partial year, but no further charges." },
  { q: ['coin','coins','tickers','how many'], a: "Up to 50 coins from any chain or category — BTC, ETH, altcoins, DeFi, gaming, meme. You pick them after checkout." },
  { q: ['chain','chains','layer','defi','category'], a: "Any chain, any category — Layer 1, DeFi, exchanges, gaming, meme coins, and more. We fetch crypto news for the coins and projects you choose." },
  { q: ['news','articles','sources'], a: "We pull from 80+ sources via NewsAPI, dedupe, and filter to the crypto topics you picked. Updated every night." },
  { q: ['bot','bots','strategy','strategies'], a: "5 strategies race on the SAME coin list: BOT13 (daily intraday), ORACLE (weekly Monday rebalance), WIZARD (monthly hold), EQUALIZER (equal-weight baseline), TITAN (cap-weighted baseline)." },
  { q: ['signals','buy','sell','hold'], a: "Every trading day we score every coin on your list — momentum, RSI, MACD, volume, volatility — and label it Strong Buy / Buy / Hold / Sell / Strong Sell." },
  { q: ['report','reports','sunday','weekly'], a: "Every Sunday you get an auto-generated report: each fund's grade, what they bought/sold, why, and what's coming up." },
  { q: ['real money','live trade','execute','broker','exchange'], a: "Nope — these are paper portfolios for research and signals. We don't touch an exchange account. You see what the bots WOULD do, then decide for yourself." },
  { q: ['data','privacy','share','sell my'], a: "Your data stays yours. We don't share or sell. Your tracker runs on a private endpoint — only you see it." },
  { q: ['contact','support','help','email'], a: "Email info@bitbot13.tech anytime. Built and supported directly by the operator." },
  { q: ['how long','setup','time','when'], a: "Tracker is live within 24 hours of checkout. You'll get an email with your private dashboard link." },
  { q: ['24/7','always on','market hours','crypto market'], a: "Crypto never sleeps — and neither do the bots. BOT13 evaluates intraday signals around the clock, not just during stock market hours." },
];
function botAnswer(input) {
  const q = (input || '').toLowerCase().trim();
  if (!q) return null;
  for (const item of FAQS) {
    if (item.q.some(k => q.includes(k))) return item.a;
  }
  return "I don't have an answer for that yet — but the operator does. Email info@bitbot13.tech and you'll get a real reply, fast.";
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
  const quick = ['Pricing', 'Coins', 'Bots', 'Cancel', 'Contact'];
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
// BOOTSTRAP
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

function boot() { wireUI(); loadAll(); }

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
