"""
Chain-of-thought LLM + Weekly Report
"""
import json, os, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def tg(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

# ============================================================
# CHAIN-OF-THOUGHT PROMPT BUILDER
# ============================================================
def build_cot_prompt(asset_name, price, change, rsi, macd_hist, macd_cross,
                     fg_value, fg_label, vix, news_text=""):
    """
    Build prompt yang memaksa LLM berpikir step-by-step
    sebelum memberikan sinyal final
    """
    fg_interpretation = (
        "Extreme Fear - pasar sangat oversold, potensi reversal bullish" if fg_value <= 25 else
        "Fear - sentimen negatif, tapi bisa jadi buying opportunity" if fg_value <= 45 else
        "Neutral - tidak ada bias kuat" if fg_value <= 55 else
        "Greed - pasar mulai overbought, hati-hati" if fg_value <= 75 else
        "Extreme Greed - pasar sangat overbought, risiko koreksi tinggi"
    )
    prompt = f"""Kamu adalah analis trading profesional. Analisa {asset_name} secara sistematis:

DATA MARKET:
- Harga: ${price:,.2f} | 24h: {change:+.2f}%
- RSI(14): {rsi} | MACD: {macd_hist} ({macd_cross})
- Fear & Greed: {fg_value}/100 ({fg_label}) ? {fg_interpretation}
- VIX: {vix} (market volatility index)

BERITA RELEVAN:
{news_text[:300] if news_text else "Tidak ada berita spesifik"}

INSTRUKSI - Analisa step by step:
1. TREND: Apakah trend saat ini bullish/bearish/sideways?
2. MOMENTUM: RSI dan MACD menunjukkan apa?
3. SENTIMEN: Fear & Greed dan berita mendukung arah mana?
4. RISIKO: Apa risiko utama saat ini?
5. KEPUTUSAN FINAL: BUY/SELL/HOLD?

Balas dengan format JSON:
{{"thinking":"ringkasan analisa 1-2 kalimat","signal":"BUY/SELL/HOLD","confidence":0.0-1.0,"reason":"alasan utama max 10 kata","risk":"risiko utama max 8 kata"}}"""
    return prompt

# ============================================================
# WEEKLY PERFORMANCE REPORT
# ============================================================
def generate_weekly_report():
    """Generate laporan performa mingguan"""
    try:
        with open("logs/paper_trades.json", encoding="utf-8") as f:
            T = json.load(f)
    except:
        return "Tidak ada data trading"

    trades = T.get("trades", [])
    balance = T.get("balance", 1000)
    positions = T.get("positions", {})
    initial = 1000.0

    # Filter trades 7 hari terakhir
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    week_trades = []
    for t in trades:
        try:
            exit_time = datetime.fromisoformat(t.get("exit_time",""))
            if exit_time >= week_ago:
                week_trades.append(t)
        except: pass

    # Statistik minggu ini
    week_pnl = sum(t.get("pnl",0) for t in week_trades)
    week_wins = sum(1 for t in week_trades if t.get("pnl",0) > 0)
    week_wr = f"{week_wins/len(week_trades)*100:.0f}%" if week_trades else "N/A"

    # Statistik all-time
    all_pnl = sum(t.get("pnl",0) for t in trades)
    all_wins = sum(1 for t in trades if t.get("pnl",0) > 0)
    all_wr = f"{all_wins/len(trades)*100:.0f}%" if trades else "N/A"

    # Portfolio value
    total_invested = sum(p.get("amount",0) for p in positions.values())
    total_value = balance + total_invested
    total_return = ((total_value - initial) / initial * 100)

    # Best & worst trade minggu ini
    best = max(week_trades, key=lambda t: t.get("pnl",0)) if week_trades else None
    worst = min(week_trades, key=lambda t: t.get("pnl",0)) if week_trades else None

    # LLM leaderboard
    try:
        with open("logs/llm_performance.json", encoding="utf-8") as f:
            llm_data = json.load(f)
        top_llm = sorted(llm_data.items(), key=lambda x: x[1].get("elo",1200), reverse=True)
        llm_summary = " | ".join([f"{n}({d.get('elo',1200)})" for n,d in top_llm[:3]])
    except:
        llm_summary = "N/A"

    now_str = now.strftime("%Y-%m-%d")
    week_start = week_ago.strftime("%Y-%m-%d")

    report = (f"?? *WEEKLY REPORT*\n"
             f"??????????????????\n"
             f"Periode: {week_start} ? {now_str}\n\n"
             f"?? *PERFORMA MINGGU INI*\n"
             f"Trade: {len(week_trades)} | WR: {week_wr}\n"
             f"PnL: ${week_pnl:+.2f}\n")

    if best:
        report += f"?? Best: {best.get('asset','?')} +${best.get('pnl',0):.2f}\n"
    if worst:
        report += f"?? Worst: {worst.get('asset','?')} ${worst.get('pnl',0):.2f}\n"

    report += (f"\n?? *PORTFOLIO STATUS*\n"
              f"Balance: ${balance:,.2f}\n"
              f"Total Value: ${total_value:,.2f}\n"
              f"All-time Return: {total_return:+.2f}%\n"
              f"All-time WR: {all_wr} ({len(trades)} trades)\n"
              f"All-time PnL: ${all_pnl:+.2f}\n\n"
              f"?? *TOP LLM*\n{llm_summary}\n\n"
              f"??????????????????\n"
              f"Dashboard: ihzaikrm.github.io/trading-bot/")

    return report

def should_send_weekly_report():
    """Cek apakah sudah waktunya kirim weekly report (setiap Minggu jam 09.00)"""
    now = datetime.now()
    REPORT_FILE = "logs/last_weekly_report.txt"
    # Cek apakah hari ini Minggu
    if now.weekday() != 6:  # 6 = Sunday
        return False
    # Cek apakah sudah kirim hari ini
    if os.path.exists(REPORT_FILE):
        with open(REPORT_FILE) as f:
            last = f.read().strip()
        if last == now.strftime("%Y-%m-%d"):
            return False
    # Simpan tanggal kirim
    os.makedirs("logs", exist_ok=True)
    with open(REPORT_FILE, "w") as f:
        f.write(now.strftime("%Y-%m-%d"))
    return True

if __name__ == "__main__":
    print("=== CHAIN-OF-THOUGHT + WEEKLY REPORT TEST ===\n")

    # Test CoT prompt
    print("[1] Chain-of-Thought Prompt:")
    prompt = build_cot_prompt(
        "Bitcoin", 70652, 2.3, 58.73, 0.0012, "BULLISH",
        15, "Extreme Fear", 27.19,
        "Iran war disrupts global trade. Fed holds rates."
    )
    print(prompt[:300] + "...\n")

    # Test Weekly Report
    print("[2] Weekly Report:")
    report = generate_weekly_report()
    print(report)

    # Test kirim ke Telegram
    print("\n[3] Kirim ke Telegram...")
    tg(report)
    print("Terkirim!")
