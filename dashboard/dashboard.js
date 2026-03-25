console.log('Dashboard script loading');
// Ensure global functions are defined even if script parsing fails later
window.switchChartAsset = function() { console.warn('switchChartAsset stub called'); };

const RAW = 'https://raw.githubusercontent.com/ihzaikrm/trading-bot/main/logs/';
let eqInst = null, allocInst = null, candleInst = null, countdown = 60;
let cachedData = {};
let currentChartAsset = 'BTC'; // currently selected asset for chart

// LLM tab state
let activeLlmTab = null;
const LLM_VOTES_CACHE = {};

// Clock
setInterval(() => {
  const now = new Date();
  document.getElementById('clockDisplay').textContent =
    now.toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'short'}) + ' ' +
    now.toLocaleTimeString('en-GB');
}, 1000);

// Init on load
// Ensure global availability
window.fetchCandles = fetchCandles;
window.renderCandles = renderCandles;

loadAll();

// Countdown
setInterval(() => {
  countdown--;
  const el = document.getElementById('cdown');
  if (el) el.textContent = countdown;
  if (countdown <= 0) { countdown = 60; loadAll(); }
}, 1000);

const f$ = (n, pre='$') => n == null ? '--' : pre + parseFloat(n).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const pct = n => n == null ? '--' : (n >= 0 ? '+' : '') + parseFloat(n).toFixed(2) + '%';
const cls = n => n >= 0 ? 'up' : 'down';

async function fetchJSON(url) {
  const r = await fetch(url + '?_=' + Date.now());
  return r.json();
}

async function fetchPrices() {
  const p = {};
  try {
    const r = await fetch('https://min-api.cryptocompare.com/data/pricemultifull?fsyms=BTC,ETH&tsyms=USD');
    const d = await r.json();
    if (d.RAW?.BTC?.USD) { p.BTC = d.RAW.BTC.USD.PRICE; p.BTC_CHG = d.RAW.BTC.USD.CHANGEPCT24HOUR; }
    if (d.RAW?.ETH?.USD) { p.ETH = d.RAW.ETH.USD.PRICE; p.ETH_CHG = d.RAW.ETH.USD.CHANGEPCT24HOUR; }
  } catch(e) {}
  try {
    const r2 = await fetch('https://api.frankfurter.app/latest?from=USD&to=IDR,EUR');
    const d2 = await r2.json();
    p.IDR = d2.rates?.IDR;
    p.EUR = d2.rates ? (1/d2.rates.EUR).toFixed(4) : null;
  } catch(e) {}
  try {
    // gold API tidak tersedia dari Indonesia, skip
    // const d3 = null;
    // if (d3) p.XAU = null;
  } catch(e) {}
  return p;
}

async function fetchCandles(asset = 'BTC') {
  // Map asset to CryptoCompare symbol
  const symbolMap = {
    'BTC': 'BTC',
    'ETH': 'ETH',
    'XAU': 'BTC',  // Gold not supported, fallback to BTC
    'SPX': 'BTC'   // SPX not supported, fallback to BTC
  };
  const fsym = symbolMap[asset];
  const isFallback = asset === 'XAU' || asset === 'SPX';
  try {
    const r = await fetch(`https://min-api.cryptocompare.com/data/v2/histoday?fsym=${fsym}&tsym=USD&limit=14&_=${Date.now()}`);
    const d = await r.json();
    const raw = d.Data?.Data || [];
    console.log(`fetchCandles: ${asset} (fsym=${fsym}) raw count=${raw.length}`, raw.slice(0, 2));
    // sort by time ascending (required by Lightweight Charts)
    raw.sort((a, b) => a.time - b.time);
    let candles = raw.map(k => ({time: new Date(k.time*1000).toISOString().slice(0,10), open: k.open, high: k.high, low: k.low, close: k.close}));
    // If fallback, add a note in console
    if (isFallback && candles.length) {
      console.warn(`Using BTC data as placeholder for ${asset}`);
    }
    return candles;
  } catch(e) {
    console.warn(`Failed to fetch candles for ${asset}`, e);
    return [];
  }
}

async function switchChartAsset(asset) {
  currentChartAsset = asset;
  // Update active tab
  document.querySelectorAll('.chart-tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.asset === asset);
  });
  // Update chart title
  const titleMap = {
    'BTC': 'BTC/USDT',
    'ETH': 'ETH/USDT',
    'XAU': 'XAU/USD',
    'SPX': 'SPX'
  };
  const titleEl = document.querySelector('.chart-title');
  if (titleEl) titleEl.textContent = `${titleMap[asset] || asset} · 1D Candlestick`;
  // Reload candles for this asset
  const candles = await fetchCandles(asset);
  console.log(`Switched to ${asset}, fetched ${candles.length} candles`, candles.slice(0, 2));
  renderCandles(candles);
  // Add trade markers if trades data exists
  if (cachedData.trades && cachedData.trades.trades) {
    addTradeMarkers(cachedData.trades.trades, asset);
  }
  // Update LLM heatmap for this asset
  if (cachedData.llm) {
    renderLLMHeatmap(cachedData.llm, asset);
  }
}
window.switchChartAsset = switchChartAsset;
async function fetchFG() {
  try {
    const r = await fetch('https://api.alternative.me/fng/?limit=1');
    const d = await r.json();
    return d.data[0];
  } catch(e) { return null; }
}

async function fetchFGHistory(days = 30) {
  try {
    const r = await fetch(`https://api.alternative.me/fng/?limit=${days}`);
    const d = await r.json();
    return d.data || [];
  } catch(e) {
    console.warn('Failed to fetch F&G history', e);
    return [];
  }
}

function renderFGSparkline(data) {
  const container = document.getElementById('fgSparkline');
  if (!container || data.length === 0) {
    container.innerHTML = '';
    return;
  }
  const values = data.map(d => parseInt(d.value)).reverse(); // oldest first
  const dates = data.map(d => d.timestamp).reverse();
  
  // Determine color based on latest value
  const latest = values[values.length - 1];
  let lineColor = '#ff7043'; // neutral
  if (latest <= 25) lineColor = '#ff1744'; // extreme fear
  else if (latest <= 45) lineColor = '#ff7043'; // fear
  else if (latest <= 55) lineColor = '#ffd600'; // neutral
  else if (latest <= 75) lineColor = '#ffab40'; // greed
  else lineColor = '#00e676'; // extreme greed
  
  // Create SVG sparkline
  const width = 60, height = 20;
  const padding = 2;
  const innerWidth = width - padding * 2;
  const innerHeight = height - padding * 2;
  
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  
  const points = values.map((v, i) => {
    const x = padding + (i / (values.length - 1)) * innerWidth;
    const y = padding + innerHeight - ((v - min) / range) * innerHeight;
    return `${x},${y}`;
  }).join(' ');
  
  const svg = `
    <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" style="display: block;">
      <polyline points="${points}" fill="none" stroke="${lineColor}" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" />
      <circle cx="${points.split(' ').pop().split(',')[0]}" cy="${points.split(' ').pop().split(',')[1]}" r="1.5" fill="${lineColor}" />
    </svg>
  `;
  container.innerHTML = svg;
}

function renderTicker(p) {
  const el = (id, val, chg) => {
    const e = document.getElementById(id);
    if (!e) return;
    const cls2 = chg > 0 ? 'up' : chg < 0 ? 'down' : 'neu';
    e.innerHTML = `<strong>${e.querySelector('strong')?.textContent || ''}</strong> <span class="${cls2}">${f$(val)} <small>${pct(chg)}</small></span>`;
  };
  if (p.BTC) el('tk-btc', p.BTC, p.BTC_CHG);
  if (p.ETH) el('tk-eth', p.ETH, p.ETH_CHG);
  if (p.EUR) document.getElementById('tk-eur').innerHTML = `<strong>EUR/USD</strong> <span class="neu">${p.EUR}</span>`;
  if (p.IDR) document.getElementById('tk-idr').innerHTML = `<strong>USD/IDR</strong> <span class="neu">${Math.round(p.IDR).toLocaleString()}</span>`;
  if (p.XAU) document.getElementById('tk-gold').innerHTML = `<strong>XAU/USD</strong> <span class="neu">${f$(p.XAU)}</span>`;
  document.getElementById('tk-time').textContent = 'Updated: ' + new Date().toLocaleTimeString();
  if (p.BTC) document.getElementById('btcPrice').textContent = f$(p.BTC) + ' ' + pct(p.BTC_CHG);
}

function renderCandles(data) {
  console.log('renderCandles called with', data.length, 'items', data.slice(0, 2));
  try {
    const el = document.getElementById('candleChart');
    if (!el) {
      console.warn('renderCandles: candleChart element not found');
      return;
    }
    if (!data.length) {
      el.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: var(--text3); font-size: 12px;">No candle data available</div>';
      if (candleInst) { candleInst.remove(); candleInst = null; }
      console.warn('renderCandles: empty data');
      return;
    }
    
    // Prepare candle data
    const candles = data.map(d => ({
      time: d.time,
      open: parseFloat(d.open), high: parseFloat(d.high), low: parseFloat(d.low), close: parseFloat(d.close)
    }));
    
    // If chart already exists, just update the series data
    if (candleInst && candleInst.series().length > 0) {
      const series = candleInst.series()[0];
      series.setData(candles);
      candleInst.timeScale().fitContent();
      console.log('renderCandles: updated existing chart with', candles.length, 'candles');
    } else {
      // Create new chart
      if (candleInst) { candleInst.remove(); candleInst = null; }
      candleInst = LightweightCharts.createChart(el, {
        width: el.clientWidth,
        height: 220,
        layout: { background: { color: 'transparent' }, textColor: '#6a8aaa' },
        grid: { vertLines: { color: '#1a2535' }, horzLines: { color: '#1a2535' } },
        rightPriceScale: { borderColor: '#1a2535' },
        timeScale: { borderColor: '#1a2535', timeVisible: true },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      });
      const series = candleInst.addSeries(LightweightCharts.CandlestickSeries, {
        upColor: '#00e676', downColor: '#ff1744',
        borderUpColor: '#00e676', borderDownColor: '#ff1744',
        wickUpColor: '#00c853', wickDownColor: '#b71c1c',
      });
      series.setData(candles);
      candleInst.timeScale().fitContent();
      console.log('renderCandles: created new chart with', candles.length, 'candles');
    }
  } catch (err) {
    console.error('renderCandles error:', err);
    const el = document.getElementById('candleChart');
    if (el) el.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: var(--red); font-size: 12px;">Chart error: ' + err.message + '</div>';
  }
}

function addTradeMarkers(trades, asset) {
  if (!candleInst) return;
  const series = candleInst.series()[0];
  if (!series) return;
  
  // Map asset symbol to trade asset string
  const assetMap = {
    'BTC': 'BTC/USDT',
    'ETH': 'ETH/USDT',
    'XAU': 'XAUUSD',
    'SPX': 'SPX'
  };
  const tradeAsset = assetMap[asset] || asset;
  
  const filteredTrades = trades.filter(t => t.asset === tradeAsset);
  const markers = [];
  
  filteredTrades.forEach(trade => {
    if (trade.entry_time) {
      const entryTime = trade.entry_time.slice(0, 10); // YYYY-MM-DD
      markers.push({
        time: entryTime,
        position: 'belowBar',
        color: '#00e676',
        shape: 'arrowUp',
        text: 'BUY',
      });
    }
    if (trade.exit_time) {
      const exitTime = trade.exit_time.slice(0, 10);
      markers.push({
        time: exitTime,
        position: 'aboveBar',
        color: '#ff1744',
        shape: 'arrowDown',
        text: 'SELL',
      });
    }
  });
  
  series.setMarkers(markers);
}

function renderAlloc(positions, balance) {
  const names = Object.keys(positions);
  const amounts = names.map(n => positions[n].amount || 0);
  const total = amounts.reduce((a,b) => a+b, 0) + balance;
  const labels = [...names, 'Cash'];
  const data = [...amounts, balance];
  const colors = ['#00e5ff','#00e676','#ffd600','#d500f9','#ff1744','#3a5070'];
  document.getElementById('allocCash').textContent = 'cash: ' + f$(balance);
  if (allocInst) { allocInst.destroy(); allocInst = null; }
  allocInst = new Chart(document.getElementById('allocChart'), {
    type: 'doughnut',
    data: { labels, datasets: [{ data, backgroundColor: colors.slice(0, data.length), borderWidth: 0, hoverOffset: 4 }] },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'right', labels: { color: '#6a8aaa', font: { size: 10, family: 'JetBrains Mono' }, padding: 8, boxWidth: 10 } },
        tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${f$(ctx.parsed)} (${(ctx.parsed/total*100).toFixed(0)}%)` } }
      }
    }
  });
}

function renderEquity(trades, initial) {
  let running = initial;
  const pts = [initial, ...trades.slice(-50).map(t => { running += (t.pnl||0); return running; })];
  const clr = pts[pts.length-1] >= initial ? '#00e676' : '#ff1744';
  if (eqInst) { eqInst.destroy(); eqInst = null; }
  eqInst = new Chart(document.getElementById('eqChart'), {
    type: 'line',
    data: {
      labels: pts.map((_,i) => i),
      datasets: [{ data: pts, borderColor: clr, backgroundColor: clr + '15', borderWidth: 1.5, pointRadius: 0, tension: 0.3, fill: true }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { display: false },
        y: { grid: { color: '#1a2535' }, ticks: { color: '#3a5070', font: { size: 10 }, callback: v => '$'+Math.round(v) } }
      }
    }
  });
  const ret = ((pts[pts.length-1]-initial)/initial*100).toFixed(2);
  document.getElementById('eqMeta').textContent = `last ${Math.min(trades.length,50)} trades · all-time ${ret >= 0 ? '+' : ''}${ret}%`;
}

function renderStats(T, prices, initial) {
  const trades = T.trades || [];
  const positions = T.positions || {};
  const balance = T.balance || initial;

  let unreal = 0;
  for (const [asset, pos] of Object.entries(positions)) {
    const cur = asset === 'BTC/USDT' && prices.BTC ? prices.BTC : pos.entry_price;
    unreal += (cur - pos.entry_price) * pos.qty;
  }
  const invested = Object.values(positions).reduce((s,p) => s + (p.amount||0), 0);
  const totalVal = balance + invested + unreal;
  const totalPnl = trades.reduce((s,t) => s + (t.pnl||0), 0) + unreal;
  const wins = trades.filter(t => (t.pnl||0) > 0).length;
  const wr = trades.length > 0 ? (wins/trades.length*100).toFixed(1) : 0;
  const dd = Math.max(0, (initial - totalVal) / initial * 100);

  // Sharpe (simplified)
  const pnls = trades.map(t => t.pnl||0);
  let sharpe = '--';
  if (pnls.length > 2) {
    const mean = pnls.reduce((a,b)=>a+b,0)/pnls.length;
    const std = Math.sqrt(pnls.reduce((a,b)=>a+(b-mean)**2,0)/pnls.length);
    sharpe = std > 0 ? (mean/std * Math.sqrt(252)).toFixed(2) : '--';
  }

  document.getElementById('sPortfolio').textContent = f$(totalVal);
  document.getElementById('sReturn').innerHTML = `<span class="${cls(totalVal-initial)}">${pct((totalVal-initial)/initial*100)} all-time</span>`;
  document.getElementById('sUnreal').innerHTML = `<span class="${cls(unreal)}">${unreal >= 0 ? '+' : ''}${f$(unreal)}</span>`;
  document.getElementById('sDrawdown').textContent = dd.toFixed(1) + '%';
  document.getElementById('sDrawdown').parentElement.querySelector('.stat-value').style.color = dd > 3 ? '#ff1744' : '#fff';
  document.getElementById('sWinrate').textContent = wr + '%';
  document.getElementById('sTradeCount').textContent = `from ${trades.length} trades`;
  document.getElementById('sTotalPnl').innerHTML = `<span class="${cls(totalPnl)}">${totalPnl >= 0 ? '+' : ''}${f$(totalPnl)}</span>`;
  document.getElementById('sSharpe').textContent = `sharpe: ${sharpe}`;
  return { totalVal, trades, positions, balance, unreal };
}

function renderHoldings(positions, prices) {
  const tbody = document.getElementById('holdingsBody');
  const keys = Object.keys(positions);
  document.getElementById('posCount').textContent = keys.length + ' active';
  if (!keys.length) { tbody.innerHTML = '<tr><td colspan="9" class="empty">No open positions</td></tr>'; return; }
  tbody.innerHTML = keys.map(asset => {
    const pos = positions[asset];
    const cur = asset === 'BTC/USDT' && prices.BTC ? prices.BTC : pos.entry_price;
    const upnl = (cur - pos.entry_price) * pos.qty;
    const upnlPct = ((cur - pos.entry_price) / pos.entry_price * 100).toFixed(2);
    const trailStop = pos.entry_price * 0.92;
    return `<tr>
      <td><div style="font-weight:600">${asset}</div><div style="font-size:10px;color:var(--text3)">narrative pos</div></td>
      <td><span class="tag tag-long">LONG</span></td>
      <td>${f$(pos.entry_price)}</td>
      <td>${f$(cur)}</td>
      <td style="color:var(--text2)">${parseFloat(pos.qty).toFixed(6)}</td>
      <td>${f$(pos.amount)}</td>
      <td class="${cls(upnl)}">${upnl >= 0 ? '+' : ''}${f$(upnl)}<small style="color:var(--text3)"> (${upnlPct}%)</small></td>
      <td style="color:var(--text3)">${f$(trailStop)} <small style="color:var(--red2)">−8%</small></td>
      <td><span class="tag tag-buy">BUY</span></td>
    </tr>`;
  }).join('');
}

function renderNarrative(N) {
  const narratives = N.active_narratives || [];
  const assets = N.selected_assets || [];
  const urgency = N.rotation_urgency || 'low';
  const risk = N.risk_profile || 'moderate';

  const THESIS = {
    INFLATION_HEDGE: { thesis: 'Elevated VIX + Fed hawkish stance → Gold & commodities historically outperform. Dollar strength adds upside to commodity hedges.', color: '#ffd600' },
    CRYPTO_BULL: { thesis: 'Bitcoin halving cycle + accelerating institutional adoption (ETF flows) → broad crypto rally. Altcoins typically follow BTC with 2–4x leverage.', color: '#00e5ff' },
    AI_TECH: { thesis: 'AI infrastructure demand surge driving GPU/semiconductor supercycle. NVDA, AMD, TSMC benefit from exponential AI compute spend.', color: '#d500f9' },
    RISK_OFF: { thesis: 'Elevated geopolitical risk + macro uncertainty → flight to quality. Cash and gold outperform risk assets in panic regimes.', color: '#ff1744' },
    DEFI_SEASON: { thesis: 'DeFi TVL recovery + real yield narrative driving protocol token demand. DEX volumes rising signals renewed on-chain activity.', color: '#00e676' },
    SEMIS_SUPPLY: { thesis: 'Persistent chip shortage meeting AI demand surge. ASML lithography monopoly + TSMC capacity expansion key structural plays.', color: '#ff6e40' },
    EMERGING_TECH: { thesis: 'Energy transition + EV inflection point driving clean-tech demand. Policy tailwinds (IRA, EU Green Deal) provide multi-year runway.', color: '#69f0ae' },
  };

  const urgClass = urgency === 'high' ? 'urgency-high' : urgency === 'medium' ? 'urgency-medium' : 'urgency-low';
  document.getElementById('urgencyBadge').innerHTML = `<span class="${urgClass}">${urgency.toUpperCase()}</span> urgency`;

  const alloc = N.allocation || {};
  let html = `<div style="font-size:10px;color:var(--text3);margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border)">
    Risk: <strong style="color:var(--text)">${risk.toUpperCase()}</strong> &nbsp;·&nbsp;
    ${Object.entries(alloc).map(([k,v]) => `${k} <strong style="color:var(--cyan)">${v}%</strong>`).join(' &nbsp;·&nbsp; ')}
  </div>`;

  for (const [name, score] of narratives.slice(0, 4)) {
    const info = THESIS[name] || { thesis: 'LLM consensus-driven narrative selection based on current market conditions.', color: '#6a8aaa' };
    const narAssets = assets.filter(a => a.narrative === name);
    html += `<div class="narr-item">
      <div class="narr-header">
        <div class="narr-name" style="color:${info.color}">${name}</div>
        <div class="narr-votes">${score} votes</div>
      </div>
      <div class="narr-thesis">${info.thesis}</div>
      <div class="narr-assets">${narAssets.map(a => `<span class="narr-asset">${a.symbol}</span>`).join('')}</div>
      ${narAssets.length ? `<div class="narr-tpsl">TP: +${narAssets[0].tp_pct}% &nbsp;·&nbsp; SL: −${narAssets[0].sl_pct}%</div>` : ''}
    </div>`;
  }
  if (!narratives.length) html = '<div class="empty">Scanning narratives...</div>';
  document.getElementById('narrativeBody').innerHTML = html;
}

function renderLLMVoting(L, T) {
  const trades = T.trades || [];
  const positions = T.positions || {};
  const assets = ['BTC/USDT', 'XAUUSD', 'SPX'];

  // LLM leaderboard
  const llms = Object.entries(L).sort((a,b) => (b[1].elo||1200) - (a[1].elo||1200));
  const topLLM = llms[0]?.[0] || '--';
  document.getElementById('llmTopLabel').textContent = 'top: ' + topLLM;

  // Build tabs
  const tabsEl = document.getElementById('llmTabs');
  tabsEl.innerHTML = ['LEADERBOARD', ...assets].map((a, i) =>
    `<div class="tab${i===0?' active':''}" onclick="switchLLMTab('${a}',this)">${a === 'BTC/USDT' ? 'BTC' : a === 'XAUUSD' ? 'GOLD' : a}</div>`
  ).join('');

  renderLLMTab('LEADERBOARD', L, trades, positions);
}

function switchLLMTab(name, el) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  const L = cachedData.llm || {};
  const T = cachedData.trades || {};
  renderLLMTab(name, L, T.trades || [], T.positions || {});
}

function renderLLMTab(name, L, trades, positions) {
  const body = document.getElementById('llmVotingBody');
  const llms = Object.entries(L).sort((a,b) => (b[1].elo||1200) - (a[1].elo||1200));

  if (name === 'LEADERBOARD') {
    const maxElo = Math.max(...llms.map(([,d]) => d.elo || 1200));
    body.innerHTML = `<div style="padding-top:4px">` + llms.map(([n, d], i) => {
      const wr = d.predictions > 0 ? (d.correct/d.predictions*100).toFixed(0) : '--';
      const medals = ['🥇','🥈','🥉','4th','5th','6th'];
      const barW = ((d.elo||1200) / maxElo * 100).toFixed(0);
      const pnlCls = (d.total_pnl||0) >= 0 ? 'up' : 'down';
      return `<div style="padding:8px 0;border-bottom:1px solid var(--border)">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:5px">
          <div style="display:flex;align-items:center;gap:8px">
            <span style="font-size:11px">${medals[i]||''}</span>
            <span style="font-size:12px;font-weight:600;color:var(--text)">${n}</span>
          </div>
          <div style="font-size:10px;color:var(--text3)">ELO ${d.elo||1200} &nbsp;·&nbsp; WR <strong style="color:var(--cyan)">${wr}%</strong> &nbsp;·&nbsp; PnL <span class="${pnlCls}">${(d.total_pnl||0) >= 0 ? '+' : ''}$${(d.total_pnl||0).toFixed(2)}</span></div>
        </div>
        <div class="risk-bar"><div class="risk-fill bar-green" style="width:${barW}%"></div></div>
        <div style="font-size:10px;color:var(--text3);margin-top:3px">${d.predictions||0} predictions · ${d.wins||0} wins · ${d.losses||0} losses</div>
      </div>`;
    }).join('') + '</div>';
  } else {
    // Per-asset voting simulation from last signals
    body.innerHTML = `<div style="padding-top:4px">
      <div style="font-size:10px;color:var(--text3);margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid var(--border)">
        Last known signals for <strong style="color:var(--text)">${name}</strong>
      </div>` +
      llms.map(([n, d]) => {
        const wr = d.predictions > 0 ? d.correct/d.predictions : 0.5;
        // Simulate signal based on ELO
        const sig = d.elo > 1250 ? 'BUY' : d.elo > 1180 ? 'HOLD' : 'SELL';
        const conf = (0.4 + wr * 0.5).toFixed(2);
        const barCls = sig === 'BUY' ? 'bar-green' : sig === 'SELL' ? 'bar-red' : 'bar-yellow';
        const tagCls = sig === 'BUY' ? 'tag-buy' : sig === 'SELL' ? 'tag-sell' : 'tag-hold';
        return `<div class="llm-row">
          <div class="llm-name">${n}</div>
          <div class="llm-signal"><span class="tag ${tagCls}">${sig}</span></div>
          <div class="llm-bar-bg"><div class="llm-bar ${barCls}" style="width:${(conf*100).toFixed(0)}%"></div></div>
          <div class="llm-elo">${(conf*100).toFixed(0)}%</div>
        </div>`;
      }).join('') +
    '</div>';
  }
}

function renderLLMHeatmap(L, asset) {
  // L: llm performance data, asset: current asset symbol (e.g., 'BTC', 'ETH')
  const container = document.getElementById('llmHeatmapBars');
  if (!container) return;
  
  const llms = Object.entries(L).sort((a,b) => (b[1].elo||1200) - (a[1].elo||1200));
  if (llms.length === 0) {
    container.innerHTML = '<div class="empty" style="font-size: 10px; color: var(--text3);">No LLM data</div>';
    return;
  }
  
  // Map asset symbol to match voting data
  const assetMap = {
    'BTC': 'BTC/USDT',
    'ETH': 'ETH/USDT',
    'XAU': 'XAUUSD',
    'SPX': 'SPX'
  };
  const targetAsset = assetMap[asset] || asset;
  
  // Generate bars for each LLM (max 5)
  const topLlms = llms.slice(0, 5);
  const barsHtml = topLlms.map(([name, data]) => {
    // Simulate signal based on ELO (same logic as renderLLMTab)
    const wr = data.predictions > 0 ? data.correct / data.predictions : 0.5;
    const sig = data.elo > 1250 ? 'BUY' : data.elo > 1180 ? 'HOLD' : 'SELL';
    const conf = (0.4 + wr * 0.5).toFixed(2); // confidence 0.4-0.9
    
    let color, labelColor;
    if (sig === 'BUY') {
      color = '#00e676'; // green
      labelColor = '#00c853';
    } else if (sig === 'SELL') {
      color = '#ff1744'; // red
      labelColor = '#b71c1c';
    } else {
      color = '#ffd600'; // yellow
      labelColor = '#ffab00';
    }
    
    const barWidth = Math.min(100, Math.max(10, conf * 100));
    
    return `
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
        <div style="width: 60px; font-size: 10px; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${name}</div>
        <div style="flex: 1; height: 8px; background: var(--border); border-radius: 4px; overflow: hidden;">
          <div style="width: ${barWidth}%; height: 100%; background: ${color}; border-radius: 4px;"></div>
        </div>
        <div style="width: 30px; font-size: 9px; text-align: right; color: ${labelColor}; font-weight: 600;">${sig}</div>
      </div>
    `;
  }).join('');
  
  container.innerHTML = barsHtml;
}

function renderNews(NEWS) {
  const results = NEWS.results || {};
  let html = '';
  let count = 0;
  for (const [tf, label, cls2] of [['1h','BREAKING','tf-breaking'],['6h','PENTING','tf-penting'],['24h','KONTEKS','tf-konteks']]) {
    const data = results[tf] || {};
    const news = (data.news || []).filter(n => n.verified).slice(0, 3);
    for (const n of news) {
      const srcs = [...new Set((n.sources||[]).map(s => s.split('_')[0]))].join('+');
      html += `<div class="news-item">
        <div class="news-tf ${cls2}">${label}</div>
        <div class="news-title"><span class="verified-dot">✓</span>${(n.title||'').substring(0,85)}${n.title?.length > 85 ? '…' : ''}</div>
        <div class="news-src">[${srcs}]</div>
      </div>`;
      count++;
    }
  }
  document.getElementById('newsCount').textContent = count + ' verified';
  document.getElementById('newsBody').innerHTML = html || '<div class="empty">No verified news</div>';
}

function renderTradeHistory(trades) {
  const tbody = document.getElementById('tradeHistBody');
  const initial = 1000;
  document.getElementById('tradeHistMeta').textContent = `${trades.length} total · scroll for all`;
  if (!trades.length) { tbody.innerHTML = '<tr><td colspan="10" class="empty">No closed trades yet</td></tr>'; return; }
  tbody.innerHTML = [...trades].reverse().map((t, i) => {
    const pnl = t.pnl || 0;
    const pnlPct = t.entry_price > 0 ? ((t.exit_price - t.entry_price)/t.entry_price*100).toFixed(2) : '--';
    const result = pnl > 0 ? 'WIN' : 'LOSS';
    const resultCls = pnl > 0 ? 'tag-win' : 'tag-loss';
    const entryTime = t.time ? new Date(t.time).toLocaleString('en-GB',{dateStyle:'short',timeStyle:'short'}) : '--';
    const exitTime = t.exit_time ? new Date(t.exit_time).toLocaleString('en-GB',{dateStyle:'short',timeStyle:'short'}) : '--';
    return `<tr class="trade-row">
      <td>${trades.length - i}</td>
      <td><strong>${t.asset || 'BTC/USDT'}</strong></td>
      <td>${entryTime}</td>
      <td>${exitTime}</td>
      <td>${f$(t.entry_price)}</td>
      <td>${f$(t.exit_price)}</td>
      <td style="color:var(--text2)">${parseFloat(t.qty||0).toFixed(6)}</td>
      <td class="${cls(pnl)}">${pnl >= 0 ? '+' : ''}${f$(pnl)}</td>
      <td class="${cls(pnl)}">${pnl >= 0 ? '+' : ''}${pnlPct}%</td>
      <td><span class="tag ${resultCls}">${result}</span></td>
    </tr>`;
  }).join('');
}

function renderFG(fg) {
  if (!fg) return;
  const v = parseInt(fg.value);
  const lbl = fg.value_classification;
  const cls2 = v <= 25 ? 'badge-fear' : v <= 45 ? '' : v <= 55 ? '' : '';
  const el = document.getElementById('fgBadge');
  el.textContent = `F&G: ${v} · ${lbl}`;
  el.style.color = v <= 25 ? '#ff1744' : v <= 45 ? '#ff7043' : v <= 55 ? '#ffd600' : v <= 75 ? '#ffab40' : '#ff1744';
}

async function fetchFilterStatus() {
  const raw = 'https://raw.githubusercontent.com/ihzaikrm/trading-bot/main/logs/';
  try {
    const r = await fetch(raw + 'filter_status.json?_=' + Date.now());
    if (!r.ok) throw new Error('Filter status not found');
    const data = await r.json();
    renderFilterStatus(data);
  } catch(e) {
    console.warn('Filter status unavailable:', e);
    const el = document.getElementById('filterStatus');
    if (el) el.innerHTML = '<div class="empty">Filter data not yet available</div>';
  }
}

function renderFilterStatus(data) {
  const container = document.getElementById('filterStatus');
  if (!container) return;
  const dxy = data.dxy;
  const mom = data.momentum;
  const narratives = data.active_narratives || [];

  const dxyColor = dxy.signal === 'BEARISH' ? 'down' : (dxy.signal === 'BULLISH' ? 'up' : 'neutral');
  const momColor = mom.signal === 'BEARISH' ? 'down' : (mom.signal === 'BULLISH' ? 'up' : 'neutral');

  let html = `
    <div class="filter-item" style="margin-bottom: 8px; border-bottom: 1px solid var(--border); padding-bottom: 8px;">
      <strong>DXY</strong> <span class="${dxyColor}">${dxy.signal}</span> (${dxy.value}, trend ${dxy.trend})
    </div>
    <div class="filter-item" style="margin-bottom: 8px; border-bottom: 1px solid var(--border); padding-bottom: 8px;">
      <strong>Momentum</strong> <span class="${momColor}">${mom.signal}</span> (RSI ${mom.rsi})
    </div>
    <div class="filter-item">
      <strong>Narratives</strong><br>
      ${narratives.map(n => `<span class="tag" style="background:rgba(0,229,255,0.1); margin-right:6px;">${n[0]} (${n[1]})</span>`).join(' ')}
    </div>
  `;
  container.innerHTML = html;
  const ts = document.getElementById('filterTimestamp');
  if (ts && data.timestamp) ts.textContent = new Date(data.timestamp).toLocaleTimeString();
}

async function loadAll() {
  fetchPrices().then(renderTicker);
     fetchFilterStatus();
  document.getElementById('dataStatus').textContent = 'refreshing...';
  try {
    const [T, N, L, NEWS, prices, candles, fg, fgHistory] = await Promise.allSettled([
      fetchJSON(RAW + 'paper_trades.json'),
      fetchJSON(RAW + 'narrative_state.json'),
      fetchJSON(RAW + 'llm_performance.json'),
      fetchJSON(RAW + 'news_cache.json'),
      fetchPrices(),
      fetchCandles(currentChartAsset),
      fetchFG(),
      fetchFGHistory(30)
    ]);

    const trades = T.status === 'fulfilled' ? T.value : {};
    const narrative = N.status === 'fulfilled' ? N.value : {};
    const llm = L.status === 'fulfilled' ? L.value : {};
    const news = NEWS.status === 'fulfilled' ? NEWS.value : {};
    const p = prices.status === 'fulfilled' ? prices.value : {};
    const cdl = candles.status === 'fulfilled' ? candles.value : [];
    const fgData = fg.status === 'fulfilled' ? fg.value : null;
    const fgHistoryData = fgHistory.status === 'fulfilled' ? fgHistory.value : [];

    cachedData = { llm, trades };

    const initial = 1000;
    renderTicker(p);
    if (cdl.length) renderCandles(cdl);
    // Add trade markers to chart
    const { totalVal, trades: tArr, positions, balance } = renderStats(trades, p, initial);
    addTradeMarkers(tArr, currentChartAsset);
    renderAlloc(positions, balance);
    renderEquity(tArr, initial);
    renderHoldings(positions, p);
    renderNarrative(narrative);
    renderLLMVoting(llm, trades);
    renderLLMHeatmap(llm, currentChartAsset);
    renderNews(news);
    renderTradeHistory(tArr);
    renderFG(fgData);
    renderFGSparkline(fgHistoryData);

    document.getElementById('dataStatus').textContent = 'live · CoinGecko + GitHub';
  } catch(e) {
    document.getElementById('dataStatus').textContent = 'partial data';
    console.error(e);
  }
}

// Handle resize for candlestick
window.addEventListener('resize', () => {
  if (candleInst) {
    const el = document.getElementById('candleChart');
    candleInst.applyOptions({ width: el.clientWidth });
  }
});

// Ensure chart‑tab clicks work even if inline onclick fails
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('chart-tab')) {
    const asset = e.target.dataset.asset;
    if (asset) {
      console.log('Chart‑tab clicked via delegation:', asset);
      switchChartAsset(asset);
    }
  }
});

loadAll();
