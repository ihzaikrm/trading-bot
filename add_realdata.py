import re

html = open('dashboard/index.html', encoding='utf-8').read()

fetch_script = '''
<script>
// ── REAL DATA LOADER ──
const RAW_URL = "https://raw.githubusercontent.com/ihzaikrm/trading-bot/main/logs/paper_trades.json";

async function loadRealData() {
  try {
    const r = await fetch(RAW_URL + "?t=" + Date.now());
    if (!r.ok) return;
    const d = await r.json();

    const trades   = d.trades || [];
    const balance  = d.balance || 1000;
    const pos      = d.positions || {};
    const shorts   = d.shorts || {};
    const initial  = 1000.0;

    // Equity = balance + unrealized (approx balance for paper)
    const equity   = balance;
    const totalPnl = trades.reduce((s,t) => s + (t.pnl||0), 0);
    const allTimePct = ((equity - initial) / initial * 100).toFixed(2);
    const wins     = trades.filter(t => (t.pnl||0) > 0).length;
    const winrate  = trades.length ? (wins/trades.length*100).toFixed(1) : "0.0";
    const dd       = equity < initial ? ((initial-equity)/initial*100).toFixed(1) : "0.0";

    // Update portfolio value
    const pvEl = document.querySelector('.stat-value.large');
    if (pvEl) pvEl.textContent = "$" + equity.toFixed(2);

    // Update all-time PnL
    const subEls = document.querySelectorAll('.stat-sub');
    if (subEls[0]) {
      const sign = totalPnl >= 0 ? "+" : "";
      subEls[0].textContent = sign + "$" + totalPnl.toFixed(2) + "  ·  " + sign + allTimePct + "% all-time";
      subEls[0].className = "stat-sub " + (totalPnl >= 0 ? "up" : "dn");
    }

    // Update winrate
    const statVals = document.querySelectorAll('.stat-value');
    if (statVals[3]) statVals[3].textContent = winrate + "%";

    // Update drawdown
    if (statVals[2]) {
      statVals[2].textContent = dd + "%";
      statVals[2].style.color = parseFloat(dd) > 2 ? "var(--accent-red)" : "var(--accent-gold)";
    }

    // Update trade count in winrate card
    const neutralEls = document.querySelectorAll('.stat-sub.neutral');
    if (neutralEls[0]) neutralEls[0].textContent = "from " + trades.length + " trades";

    // Update holdings table — positions
    const tbody = document.querySelector('.holdings-table tbody');
    if (tbody && Object.keys(pos).length > 0) {
      // Mark open positions
      Object.entries(pos).forEach(([name, p]) => {
        const rows = tbody.querySelectorAll('tr');
        rows.forEach(row => {
          if (row.textContent.includes(name.replace('/USDT','').replace('^',''))) {
            const cells = row.querySelectorAll('td');
            if (cells[1]) cells[1].innerHTML = '<span style="color:var(--accent-green)">LONG</span>';
            if (cells[2]) cells[2].textContent = "$" + (p.entry_price||0).toLocaleString();
          }
        });
      });
    }

    // Update recent trades list
    const tradeList = document.querySelector('.trade-list');
    if (tradeList && trades.length > 0) {
      const recent = [...trades].reverse().slice(0,5);
      tradeList.innerHTML = recent.map(t => {
        const pnl   = (t.pnl||0).toFixed(2);
        const sign  = t.pnl >= 0 ? "+" : "";
        const color = t.pnl >= 0 ? "var(--accent-green)" : "var(--accent-red)";
        const type  = t.exit_reason || (t.pnl >= 0 ? "TP ✓" : "SL ✗");
        const date  = (t.exit_time||t.entry_time||"").slice(0,10);
        const asset = (t.asset||"").replace('/USDT','').replace('^','').slice(0,3);
        return \<div class="trade-item">
          <div class="trade-dot" style="background:\"></div>
          <div class="trade-asset">\</div>
          <div class="trade-type" style="color:\">\</div>
          <div class="trade-date">\</div>
          <div class="trade-pnl" style="color:\">\$\</div>
        </div>\;
      }).join('');
    }

    // Update total PnL box
    const pnlBoxes = document.querySelectorAll('.alloc-center-val, [style*="accent-green"]');
    const totalBox = document.querySelector('[style*="rgba(0,230,118,0.05)"] .\\\\:font-bold');

    console.log("[Dashboard] Real data loaded: balance=" + balance + " trades=" + trades.length);
  } catch(e) {
    console.log("[Dashboard] Using demo data:", e.message);
  }
}

loadRealData();
setInterval(loadRealData, 60000); // refresh setiap 1 menit
</script>'''

# Sisipkan sebelum </body>
if '</body>' in html and 'loadRealData' not in html:
    html = html.replace('</body>', fetch_script + '\n</body>')
    open('dashboard/index.html', 'w', encoding='utf-8').write(html)
    print('OK: real data loader ditambahkan')
else:
    print('SKIP: sudah ada atau </body> tidak ditemukan')
