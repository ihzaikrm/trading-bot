from backtest.walk_forward import run_quarterly_wfo, wfo_summary
# core/strategy_manager.py
# Quarterly Strategy Evaluation + Research Intelligence Report
#
# Jadwal:
# - Hari ke-1 tiap bulan     → Monthly monitoring (drawdown check, circuit breaker)
# - Hari ke-1 Jan/Apr/Jul/Okt → Quarterly full report (performance + AI research + papers)
#
# Fitur quarterly report:
# 1. Performance evaluation per aset (winrate, PnL, profit factor)
# 2. Circuit breaker otomatis jika underperform
# 3. AI/ML trading research terbaru (via LLM)
# 4. Hedge fund & institutional research digest (via LLM)
# 5. Rekomendasi aksi konkret
# 6. Semua dikirim via Telegram

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
QUARTERLY_MONTHS       = [1, 4, 7, 10]   # Jan, Apr, Jul, Okt
MONTHLY_DD_THRESHOLD   = -20.0            # circuit breaker: monthly DD > 20%
QUARTERLY_WR_THRESHOLD = 0.25             # critical: winrate < 25%
WR_WARNING_DROP        = 0.08             # warning: WR turun >8% dari baseline
WR_UNDERPERFORM_DROP   = 0.15             # underperform: WR turun >15%

BASELINE_WR = {
    "BTC/USDT": 0.41,
    "XAUUSD":   0.37,
    "SPX":      0.47,
}

# ── 1. Data Loading ──────────────────────────────────────────────────────────

def load_trades(asset_name: Optional[str] = None, days: int = 90) -> list:
    """Load closed trades dari paper_trades.json, filter by asset & periode."""
    path = os.path.join("logs", "paper_trades.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            data = json.load(f)
        history = data.get("history", [])
        cutoff  = datetime.utcnow() - timedelta(days=days)
        result  = []
        for t in history:
            if t.get("status") != "closed":
                continue
            if asset_name and t.get("asset") != asset_name:
                continue
            try:
                exit_time = datetime.fromisoformat(t.get("exit_time", ""))
                if exit_time >= cutoff:
                    result.append(t)
            except:
                pass
        return result
    except Exception as e:
        logger.error(f"[StratMgr] load_trades error: {e}")
        return []


# ── 2. Performance Evaluation ────────────────────────────────────────────────

def evaluate_asset(asset_name: str, days: int = 90) -> dict:
    """Evaluasi performa satu aset dalam periode tertentu."""
    trades = load_trades(asset_name, days)
    if not trades:
        return {"asset": asset_name, "trades": 0, "status": "NO_DATA"}

    wins    = [t for t in trades if t.get("pnl", 0) > 0]
    losses  = [t for t in trades if t.get("pnl", 0) <= 0]
    winrate = len(wins) / len(trades)

    total_pnl     = sum(t.get("pnl", 0) for t in trades)
    avg_win       = sum(t["pnl"] for t in wins)   / len(wins)   if wins   else 0
    avg_loss      = sum(t["pnl"] for t in losses) / len(losses) if losses else 0
    gross_profit  = avg_win  * len(wins)
    gross_loss    = abs(avg_loss * len(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999

    baseline = BASELINE_WR.get(asset_name, 0.40)
    wr_drop  = baseline - winrate

    if winrate < QUARTERLY_WR_THRESHOLD:
        status = "CRITICAL"
    elif wr_drop > WR_UNDERPERFORM_DROP:
        status = "UNDERPERFORM"
    elif wr_drop > WR_WARNING_DROP:
        status = "WARNING"
    else:
        status = "OK"

    return {
        "asset":         asset_name,
        "period_days":   days,
        "trades":        len(trades),
        "winrate":       round(winrate, 3),
        "baseline_wr":   baseline,
        "wr_drop":       round(wr_drop, 3),
        "total_pnl":     round(total_pnl, 2),
        "avg_win":       round(avg_win, 2),
        "avg_loss":      round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2),
        "status":        status,
    }


def monthly_circuit_check() -> list:
    """Cek bulanan: apakah ada aset yang perlu circuit breaker?"""
    from config.assets import ASSETS
    alerts = []
    for name in ASSETS:
        trades = load_trades(name, days=30)
        if len(trades) < 3:
            continue
        cumulative_pnl = sum(t.get("pnl", 0) for t in trades)
        if cumulative_pnl < 0:
            # Approximate DD% dari initial $1000
            dd_pct = cumulative_pnl / 1000 * 100
            if dd_pct < MONTHLY_DD_THRESHOLD:
                alerts.append({
                    "asset":  name,
                    "dd_pct": round(dd_pct, 1),
                    "action": "PAUSE",
                    "reason": (f"Monthly DD {dd_pct:.1f}% "
                                f"melebihi threshold {MONTHLY_DD_THRESHOLD}%")
                })
    return alerts


# ── 3. Research Intelligence (via LLM) ──────────────────────────────────────

async def fetch_ai_trading_research() -> str:
    """
    Minta LLM mencari & merangkum perkembangan AI/ML terbaru
    yang relevan untuk trading bot.
    """
    from core.llm_clients import call_single_llm

    quarter = f"Q{(datetime.utcnow().month - 1) // 3 + 1} {datetime.utcnow().year}"

    prompt = f"""Kamu adalah AI research analyst untuk trading bot algoritmik.

Tugas: Cari dan rangkum perkembangan AI/ML terbaru ({quarter}) yang RELEVAN dan ACTIONABLE untuk bot trading (BTC, Gold, SPX).

Fokus area:
1. Model prediksi harga terbaru (transformer, RL, ensemble methods)
2. Feature engineering baru yang terbukti efektif
3. Risk management & position sizing advances (Kelly variants, CVaR)
4. Sentiment analysis & NLP tools terbaru untuk trading
5. Alternative data sources yang proven (on-chain, options flow, dll)

Format output yang WAJIB diikuti:
🤖 AI/ML RESEARCH UPDATE {quarter}

📌 TEMUAN UTAMA:
[2-3 kalimat summary perkembangan terpenting]

🔬 DETAIL TEMUAN:
• [Temuan 1]: [deskripsi + relevansi untuk bot]
• [Temuan 2]: [deskripsi + relevansi untuk bot]
• [Temuan 3]: [deskripsi + relevansi untuk bot]

💡 REKOMENDASI IMPLEMENTASI:
🔴 Prioritas Tinggi: [item yang bisa langsung diimplementasikan]
🟡 Prioritas Menengah: [item untuk sprint berikutnya]
🟢 Jangka Panjang: [item riset lebih lanjut]

⚠️ CATATAN RISIKO:
[risiko atau limitasi yang perlu diperhatikan sebelum implementasi]

Hanya sertakan hal yang EVIDENCE-BASED dan PROVEN. Hindari hype."""

    ok, response = await call_single_llm("deepseek", "AI research analyst", prompt)
    return response if ok else "❌ Gagal fetch AI research — periksa koneksi API"


async def fetch_institutional_research() -> str:
    """
    Minta LLM merangkum research paper terbaru dari hedge fund
    dan institusi akademik yang relevan untuk strategi bot.
    """
    from core.llm_clients import call_single_llm

    quarter = f"Q{(datetime.utcnow().month - 1) // 3 + 1} {datetime.utcnow().year}"

    prompt = f"""Kamu adalah quant researcher yang menganalisis paper akademik dan institutional research.

Tugas: Cari dan rangkum research paper terbaru ({quarter}) yang RELEVAN untuk strategi trading bot ini:
- BTC: Vol-Weighted TSMOM (momentum + volume)
- Gold: Passive trend following + bear protection
- SPX: Seasonal + trend following

Sumber yang dicari:
- SSRN quantitative finance section
- arXiv q-fin
- AQR Capital, Two Sigma, Man Group, Citadel research
- Journal of Finance, Journal of Portfolio Management
- Fed/ECB/BIS working papers tentang crypto/equity/commodities

Format output yang WAJIB diikuti:
📚 INSTITUTIONAL RESEARCH DIGEST {quarter}

🏆 TOP PAPERS:
1. [Judul Paper]
   Penulis/Institusi: [nama]
   Temuan utama: [1-2 kalimat]
   Relevansi: [High/Medium/Low] — [alasan singkat]
   Yang bisa diimplementasikan: [konkret]

2. [Judul Paper]
   [sama seperti di atas]

3. [Judul Paper]
   [sama seperti di atas]

⚡ QUICK WINS (bisa diimplementasikan dalam 1 sprint):
• [item konkret 1]
• [item konkret 2]

🔮 STRATEGIC INSIGHTS:
• [insight jangka panjang 1]
• [insight jangka panjang 2]

🚫 APA YANG SUDAH TIDAK EFEKTIF:
• [strategi/pendekatan yang sudah outdated berdasarkan research terbaru]

Prioritaskan paper yang memiliki out-of-sample validation."""

    ok, response = await call_single_llm("deepseek", "Quant research analyst", prompt)
    return response if ok else "❌ Gagal fetch institutional research — periksa koneksi API"


# ── 4. Report Generation ─────────────────────────────────────────────────────

async def generate_quarterly_report() -> str:
    """
    Generate laporan kuartalan lengkap:
    1. Performance evaluation semua aset
    2. Rekomendasi aksi
    3. AI/ML research terbaru
    4. Institutional research digest
    """
    from config.assets import ASSETS

    now     = datetime.utcnow()
    quarter = f"Q{(now.month - 1) // 3 + 1} {now.year}"
    lines   = []

    # ── Header ──
    lines.append(f"╔══════════════════════════════════╗")
    lines.append(f"║  📊 QUARTERLY REPORT — {quarter}  ║")
    lines.append(f"╚══════════════════════════════════╝")
    lines.append(f"_{now.strftime('%d %b %Y %H:%M')} UTC_\n")

    # ── Bagian 1: Performance ──
    lines.append("📈 *EVALUASI PERFORMA (90 hari)*\n")
    recommendations = []

    for name in ASSETS:
        ev = evaluate_asset(name, days=90)
        emoji = {"OK":"✅","WARNING":"⚠️","UNDERPERFORM":"🔴",
                 "CRITICAL":"🚨","NO_DATA":"❓"}.get(ev["status"], "❓")

        lines.append(f"{emoji} *{name}* — {ev['status']}")
        if ev["trades"] == 0:
            lines.append("   Belum ada closed trade dalam 90 hari\n")
            continue

        lines.append(
            f"   Trades: {ev['trades']} | "
            f"WR: {ev['winrate']:.0%} (baseline {ev['baseline_wr']:.0%})"
        )
        lines.append(
            f"   PnL: ${ev['total_pnl']:+.2f} | "
            f"Profit Factor: {ev['profit_factor']:.2f}\n"
        )

        if ev["status"] == "CRITICAL":
            recommendations.append(
                f"🚨 *{name}*: WR {ev['winrate']:.0%} sangat rendah — "
                f"PAUSE & review manual segera"
            )
        elif ev["status"] == "UNDERPERFORM":
            recommendations.append(
                f"⚠️ *{name}*: WR turun {ev['wr_drop']:.0%} dari baseline — "
                f"jalankan `py -3.11 run_backtest.py` untuk re-validate"
            )
        elif ev["status"] == "WARNING":
            recommendations.append(
                f"⚡ *{name}*: WR mulai turun ({ev['wr_drop']:.0%}) — monitor ketat"
            )

    # ── Bagian 2: Rekomendasi ──
    lines.append("─" * 35)
    if recommendations:
        lines.append("\n🎯 *REKOMENDASI AKSI*\n")
        for r in recommendations:
            lines.append(f"• {r}")
        lines.append("")
    else:
        lines.append("\n✅ *Semua strategi performa normal — tidak ada aksi diperlukan*\n")

    lines.append("─" * 35)

    # ── Bagian 3: AI Research ──
    lines.append("\n🤖 *AI/ML RESEARCH UPDATE*\n")
    ai_research = await fetch_ai_trading_research()
    lines.append(ai_research)

    lines.append("\n" + "─" * 35)

    # ── Bagian 4: Institutional Research ──
    lines.append("\n📚 *INSTITUTIONAL RESEARCH DIGEST*\n")
    inst_research = await fetch_institutional_research()
    lines.append(inst_research)

    lines.append("\n" + "─" * 35)
    lines.append(f"\n🗓 _Next quarterly review: {_next_quarter_date()}_")
    lines.append("⚠️ _Review temuan di atas secara manual sebelum implementasi_")
    lines.append("_Jangan auto-deploy strategi baru tanpa backtest + OOS validation_")

    # ── Bagian 5: WFO Update ──
    lines.append("\n🔄 *5. WALK-FORWARD OPTIMIZATION UPDATE*\n")
    try:
        wfo_text = wfo_summary()
        lines.append(wfo_text if wfo_text else "_WFO: belum cukup data historis_")
    except Exception as e:
        lines.append(f"_WFO error: {e}_")
    lines.append("\n" + "─" * 35)

    return "\n".join(lines)


async def generate_monthly_report() -> str:
    """
    Laporan bulanan ringkas: monitoring + circuit breaker check.
    Tidak ada perubahan strategi — hanya alert jika ada masalah.
    """
    from config.assets import ASSETS

    now   = datetime.utcnow()
    lines = []
    lines.append(f"📅 *MONITORING BULANAN — {now.strftime('%B %Y')}*")
    lines.append(f"_{now.strftime('%d %b %Y %H:%M')} UTC_\n")

    # Circuit breaker
    alerts = monthly_circuit_check()
    if alerts:
        lines.append("🚨 *CIRCUIT BREAKER ALERT*")
        for a in alerts:
            lines.append(f"• {a['asset']}: {a['reason']}")
        lines.append("→ Pertimbangkan /pause untuk aset tersebut\n")

    # Summary 30 hari
    lines.append("*Summary 30 hari:*")
    for name in ASSETS:
        ev = evaluate_asset(name, days=30)
        if ev["trades"] == 0:
            lines.append(f"❓ {name}: Belum ada trade bulan ini")
            continue
        emoji = {"OK":"✅","WARNING":"⚠️","UNDERPERFORM":"🔴",
                 "CRITICAL":"🚨"}.get(ev["status"], "❓")
        lines.append(
            f"{emoji} {name}: {ev['trades']} trades | "
            f"WR {ev['winrate']:.0%} | PnL ${ev['total_pnl']:+.2f}"
        )

    lines.append(f"\n_Evaluasi strategi penuh: {_next_quarter_date()}_")
    lines.append("_Monthly = monitoring only, bukan perubahan strategi_")
    return "\n".join(lines)


# ── 5. Scheduling Helpers ────────────────────────────────────────────────────

def _next_quarter_date() -> str:
    now = datetime.utcnow()
    for qm in QUARTERLY_MONTHS:
        if qm > now.month:
            return f"1 {datetime(now.year, qm, 1).strftime('%B %Y')}"
    return f"1 Januari {now.year + 1}"


def should_run_quarterly() -> bool:
    now = datetime.utcnow()
    return now.month in QUARTERLY_MONTHS and now.day == 1 and now.hour < 2


def should_run_monthly() -> bool:
    now = datetime.utcnow()
    return now.day == 1 and now.hour < 2 and now.month not in QUARTERLY_MONTHS


# ── 6. Entry point dari bot.py ───────────────────────────────────────────────

async def run_scheduled_reports(notifier=None) -> None:
    """
    Dipanggil setiap run dari bot.py.
    Otomatis kirim laporan sesuai jadwal.
    """
    if should_run_quarterly():
        logger.info("[StratMgr] 📊 Menjalankan quarterly report...")
        report = await generate_quarterly_report()
        if notifier:
            # Split jika > 4096 char (limit Telegram)
            for chunk in [report[i:i+4000] for i in range(0, len(report), 4000)]:
                await notifier.send(chunk, parse_mode="Markdown")
        logger.info("[StratMgr] ✅ Quarterly report terkirim")

    elif should_run_monthly():
        logger.info("[StratMgr] 📅 Menjalankan monthly monitoring...")
        report = await generate_monthly_report()
        if notifier:
            await notifier.send(report, parse_mode="Markdown")
        logger.info("[StratMgr] ✅ Monthly report terkirim")
