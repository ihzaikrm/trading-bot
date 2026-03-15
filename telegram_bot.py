"""
Telegram Interactive Bot Handler
Commands: /status, /portfolio, /narrative, /llm, /news, /help
Jalankan sebagai background service atau via GitHub Actions
"""
import requests, json, os, time
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
LOGS_DIR = "logs"

def tg(msg, chat_id=None):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id or CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"TG error: {e}")

def load_json(filename):
    path = os.path.join(LOGS_DIR, filename)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}

def cmd_status():
    T = load_json("paper_trades.json")
    N = load_json("narrative_state.json")
    balance = T.get("balance", 1000)
    trades = T.get("trades", [])
    positions = T.get("positions", {})
    wins = sum(1 for t in trades if t.get("pnl",0) > 0)
    winrate = f"{wins/len(trades)*100:.0f}%" if trades else "N/A"
    total_pnl = sum(t.get("pnl",0) for t in trades)
    narratives = N.get("active_narratives", [])
    top_narr = narratives[0][0] if narratives else "N/A"
    urgency = N.get("rotation_urgency", "low")
    open_pos = ", ".join(positions.keys()) if positions else "Tidak ada"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (f"📊 *STATUS BOT* — {now}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Balance: ${balance:,.2f}\n"
            f"📈 Total PnL: ${total_pnl:+.2f}\n"
            f"🎯 Winrate: {winrate} ({len(trades)} trades)\n"
            f"📉 Posisi: {open_pos}\n"
            f"🔥 Narasi: {top_narr} (urgency: {urgency})\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Dashboard: ihzaikrm.github.io/trading-bot/")

def cmd_portfolio():
    T = load_json("paper_trades.json")
    balance = T.get("balance", 1000)
    positions = T.get("positions", {})
    trades = T.get("trades", [])
    total_pnl = sum(t.get("pnl",0) for t in trades)
    msg = "💼 *PORTFOLIO DETAIL*\n━━━━━━━━━━━━━━━━━━\n"
    if positions:
        for asset, pos in positions.items():
            entry = pos.get("entry_price", 0)
            qty = pos.get("qty", 0)
            amount = pos.get("amount", 0)
            msg += (f"\n🟢 *{asset}*\n"
                   f"   Entry: ${entry:,.2f}\n"
                   f"   Qty: {qty:.6f}\n"
                   f"   Amount: ${amount:.2f}\n")
    else:
        msg += "\nTidak ada posisi terbuka\n"
    msg += (f"\n━━━━━━━━━━━━━━━━━━\n"
           f"💵 Cash: ${balance:,.2f}\n"
           f"📊 Realized PnL: ${total_pnl:+.2f}\n"
           f"🏦 Total Capital: ${balance + sum(p.get('amount',0) for p in positions.values()):,.2f}")
    return msg

def cmd_narrative():
    N = load_json("narrative_state.json")
    narratives = N.get("active_narratives", [])
    assets = N.get("selected_assets", [])
    urgency = N.get("rotation_urgency", "low")
    risk = N.get("risk_profile", "moderate")
    alloc = N.get("allocation", {})
    THESIS = {
        "INFLATION_HEDGE": "VIX tinggi + Fed hawkish → Gold & commodities outperform",
        "CRYPTO_BULL": "Bitcoin halving cycle + institutional demand → crypto rally",
        "AI_TECH": "AI adoption + GPU demand → NVDA, AMD, semis outperform",
        "RISK_OFF": "Market fear → cash & gold sebagai safe haven",
        "DEFI_SEASON": "DeFi TVL naik → altcoin & yield farming season",
        "SEMIS_SUPPLY": "Chip shortage + AI demand → semiconductor chain",
        "EMERGING_TECH": "Clean energy + EV transition → green tech rally",
    }
    urgency_emoji = "🔴" if urgency=="high" else "🟡" if urgency=="medium" else "🟢"
    msg = f"🎯 *NARRATIVE PORTFOLIO*\n━━━━━━━━━━━━━━━━━━\n"
    msg += f"Risk Profile: *{risk.upper()}*\n"
    msg += f"Rotation Urgency: {urgency_emoji} *{urgency.upper()}*\n\n"
    for name, score in narratives[:3]:
        thesis = THESIS.get(name, "Analisa market saat ini")
        narr_assets = [a["symbol"] for a in assets if a.get("narrative") == name]
        msg += (f"📌 *{name}* ({score} votes)\n"
               f"   💡 {thesis}\n"
               f"   📦 Assets: {', '.join(narr_assets) or 'scanning...'}\n\n")
    if alloc:
        msg += "━━━━━━━━━━━━━━━━━━\n📊 *Alokasi Target:*\n"
        for k, v in alloc.items():
            msg += f"   {k}: {v}%\n"
    return msg

def cmd_llm():
    L = load_json("llm_performance.json")
    msg = "🤖 *LLM LEADERBOARD*\n━━━━━━━━━━━━━━━━━━\n"
    if not L:
        return msg + "Belum ada data performa LLM"
    llms = sorted(L.items(), key=lambda x: x[1].get("elo", 1200), reverse=True)
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣"]
    for i, (name, data) in enumerate(llms):
        elo = data.get("elo", 1200)
        preds = data.get("predictions", 0)
        correct = data.get("correct", 0)
        pnl = data.get("total_pnl", 0)
        wr = f"{correct/preds*100:.0f}%" if preds > 0 else "N/A"
        medal = medals[i] if i < len(medals) else "•"
        msg += f"{medal} *{name}*: ELO {elo} | WR {wr} | PnL ${pnl:+.2f}\n"
    return msg

def cmd_news():
    NEWS = load_json("news_cache.json")
    results = NEWS.get("results", {})
    msg = "📰 *BERITA TERVERIFIKASI*\n━━━━━━━━━━━━━━━━━━\n"
    count = 0
    for tf, label in [("1h","🔴 BREAKING"), ("6h","🟡 PENTING"), ("24h","⚪ KONTEKS")]:
        data = results.get(tf, {})
        news_list = data.get("news", [])
        verified = [n for n in news_list if n.get("verified")][:2]
        if verified:
            msg += f"\n*{label}*\n"
            for n in verified:
                title = n.get("title","")[:70]
                sources = "+".join(set(s.split("_")[0] for s in n.get("sources",[])))
                msg += f"✅ {title}...\n   [{sources}]\n"
            count += len(verified)
    if count == 0:
        msg += "Belum ada berita verified"
    return msg

def cmd_help():
    return ("🤖 *TRADING BOT COMMANDS*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "/status — Ringkasan portfolio & bot\n"
            "/portfolio — Detail holdings & PnL\n"
            "/narrative — Narasi aktif & thesis\n"
            "/llm — Leaderboard performa LLM\n"
            "/news — Berita terverifikasi terbaru\n"
            "/help — Daftar semua perintah\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Dashboard: ihzaikrm.github.io/trading-bot/\n"
            "Update: setiap 2 jam otomatis")

COMMANDS = {
    "/status": cmd_status,
    "/portfolio": cmd_portfolio,
    "/narrative": cmd_narrative,
    "/llm": cmd_llm,
    "/news": cmd_news,
    "/help": cmd_help,
}

def get_updates(offset=None):
    params = {"timeout": 30}
    if offset: params["offset"] = offset
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                        params=params, timeout=35)
        return r.json().get("result", [])
    except:
        return []

def run_bot():
    print("Telegram Bot listening...")
    tg("🤖 *Bot Online!*\nKetik /help untuk daftar perintah.")
    offset = None
    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            msg = update.get("message", {})
            text = msg.get("text", "").strip()
            chat_id = msg.get("chat", {}).get("id")
            if text in COMMANDS:
                print(f"Command: {text} from {chat_id}")
                tg(COMMANDS[text](), chat_id)
            elif text:
                tg("Perintah tidak dikenal. Ketik /help", chat_id)
        time.sleep(1)

if __name__ == "__main__":
    # Test semua commands
    print("=== TEST TELEGRAM COMMANDS ===")
    for cmd, func in COMMANDS.items():
        print(f"\n{cmd}:")
        print(func()[:100] + "...")
    print("\nKirim /help ke bot kamu di Telegram!")
    tg(cmd_help())
