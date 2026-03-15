import requests, json, os, time
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OFFSET_FILE = "logs/tg_offset.txt"
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

def load_offset():
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE) as f:
            return int(f.read().strip())
    return 0

def save_offset(offset):
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))

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
    open_pos = ", ".join(positions.keys()) if positions else "Tidak ada"
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (f"📊 *STATUS BOT* — {now}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Balance: ${balance:,.2f}\n"
            f"📈 Total PnL: ${total_pnl:+.2f}\n"
            f"🎯 Winrate: {winrate} ({len(trades)} trades)\n"
            f"📉 Posisi: {open_pos}\n"
            f"🔥 Narasi: {top_narr}\n"
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
            msg += (f"\n🟢 *{asset}*\n"
                   f"   Entry: ${pos.get('entry_price',0):,.2f}\n"
                   f"   Qty: {pos.get('qty',0):.6f}\n"
                   f"   Amount: ${pos.get('amount',0):.2f}\n")
    else:
        msg += "\nTidak ada posisi terbuka\n"
    msg += (f"\n━━━━━━━━━━━━━━━━━━\n"
           f"💵 Cash: ${balance:,.2f}\n"
           f"📊 Realized PnL: ${total_pnl:+.2f}")
    return msg

def cmd_narrative():
    N = load_json("narrative_state.json")
    narratives = N.get("active_narratives", [])
    assets = N.get("selected_assets", [])
    urgency = N.get("rotation_urgency", "low")
    risk = N.get("risk_profile", "moderate")
    THESIS = {
        "INFLATION_HEDGE": "VIX tinggi + Fed hawkish → Gold & commodities outperform",
        "CRYPTO_BULL": "Bitcoin halving + institutional demand → crypto rally",
        "AI_TECH": "AI adoption + GPU demand → NVDA, semis outperform",
        "RISK_OFF": "Market fear → cash & gold safe haven",
        "DEFI_SEASON": "DeFi TVL naik → altcoin season",
        "SEMIS_SUPPLY": "Chip shortage + AI → semiconductor chain",
        "EMERGING_TECH": "Clean energy + EV → green tech rally",
    }
    urgency_emoji = "🔴" if urgency=="high" else "🟡" if urgency=="medium" else "🟢"
    msg = f"🎯 *NARRATIVE PORTFOLIO*\n━━━━━━━━━━━━━━━━━━\n"
    msg += f"Risk: *{risk.upper()}* | Urgency: {urgency_emoji} *{urgency.upper()}*\n\n"
    for name, score in narratives[:3]:
        thesis = THESIS.get(name, "Analisa market saat ini")
        narr_assets = [a["symbol"] for a in assets if a.get("narrative") == name]
        msg += (f"📌 *{name}* ({score} votes)\n"
               f"   💡 {thesis}\n"
               f"   📦 {', '.join(narr_assets) or 'scanning...'}\n\n")
    return msg

def cmd_llm():
    L = load_json("llm_performance.json")
    msg = "🤖 *LLM LEADERBOARD*\n━━━━━━━━━━━━━━━━━━\n"
    if not L:
        return msg + "Belum ada data"
    llms = sorted(L.items(), key=lambda x: x[1].get("elo",1200), reverse=True)
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣"]
    for i, (name, data) in enumerate(llms):
        elo = data.get("elo",1200)
        preds = data.get("predictions",0)
        correct = data.get("correct",0)
        pnl = data.get("total_pnl",0)
        wr = f"{correct/preds*100:.0f}%" if preds > 0 else "N/A"
        msg += f"{medals[i] if i<6 else '•'} *{name}*: ELO {elo} | WR {wr} | ${pnl:+.2f}\n"
    return msg

def cmd_news():
    NEWS = load_json("news_cache.json")
    results = NEWS.get("results", {})
    msg = "📰 *BERITA TERVERIFIKASI*\n━━━━━━━━━━━━━━━━━━\n"
    count = 0
    for tf, label in [("1h","🔴 BREAKING"),("6h","🟡 PENTING"),("24h","⚪ KONTEKS")]:
        data = results.get(tf, {})
        verified = [n for n in data.get("news",[]) if n.get("verified")][:2]
        if verified:
            msg += f"\n*{label}*\n"
            for n in verified:
                msg += f"✅ {n.get('title','')[:60]}...\n"
            count += len(verified)
    return msg if count > 0 else msg + "Belum ada berita verified"

def cmd_help():
    return ("🤖 *TRADING BOT COMMANDS*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "/status — Ringkasan portfolio\n"
            "/portfolio — Detail holdings\n"
            "/narrative — Narasi aktif + thesis\n"
            "/llm — Leaderboard LLM\n"
            "/news — Berita terverifikasi\n"
            "/help — Daftar perintah\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Dashboard: ihzaikrm.github.io/trading-bot/")

COMMANDS = {
    "/status": cmd_status,
    "/portfolio": cmd_portfolio,
    "/narrative": cmd_narrative,
    "/llm": cmd_llm,
    "/news": cmd_news,
    "/help": cmd_help,
}

def main():
    print("Telegram Listener starting...")
    offset = load_offset()
    deadline = time.time() + 230  # 3.8 menit (Actions timeout 4 menit)
    while time.time() < deadline:
        try:
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                           params={"offset": offset, "timeout": 10}, timeout=15)
            updates = r.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                save_offset(offset)
                msg = update.get("message", {})
                text = msg.get("text","").strip()
                chat_id = msg.get("chat",{}).get("id")
                print(f"Received: {text} from {chat_id}")
                if text in COMMANDS:
                    tg(COMMANDS[text](), chat_id)
                elif text.startswith("/"):
                    tg("Perintah tidak dikenal. Ketik /help", chat_id)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
        time.sleep(2)
    print("Listener selesai")

if __name__ == "__main__":
    main()
