import requests, json, time, os
import yfinance as yf
from datetime import datetime

# ============================================================
# MANIPULATION FIREWALL
# ============================================================
def manipulation_score(symbol, atype, data):
    """
    Return score 0-100. Semakin tinggi = semakin suspect manipulasi.
    Score > 60 = REJECT
    """
    score = 0
    flags = []

    # ETF whitelist - skip manipulation check
    ETF_WHITELIST = ["QQQ","SPY","GLD","SLV","USO","IWM","DIA","XLF","XLE","XLK","VTI","EEM"]
    if symbol in ETF_WHITELIST:
        return 0, ["ETF whitelisted"]

    if atype == "crypto":
        price_change_24h = abs(data.get("price_change_percentage_24h", 0))
        price_change_7d  = abs(data.get("price_change_percentage_7d", 0))
        vol_mcap_ratio   = data.get("total_volume", 0) / max(data.get("market_cap", 1), 1)
        age_days         = 999  # default aman

        # Volume/mcap ratio terlalu tinggi = suspect pump
        if vol_mcap_ratio > 0.5:
            score += 30
            flags.append(f"vol/mcap={vol_mcap_ratio:.2f} (>0.5 suspect)")

        # Harga naik terlalu cepat
        if price_change_24h > 25:
            score += 25
            flags.append(f"24h change={price_change_24h:.1f}% (>25% suspect)")
        if price_change_7d > 50:
            score += 20
            flags.append(f"7d change={price_change_7d:.1f}% (>50% suspect)")

        # Market cap terlalu kecil = micro cap risk
        mcap = data.get("market_cap", 0)
        if mcap < 20_000_000:
            score += 20
            flags.append(f"mcap=${mcap/1e6:.1f}M (<$20M micro cap)")

        # Volume terlalu rendah = illiquid
        if data.get("total_volume", 0) < 300_000:
            score += 25
            flags.append("volume<$300K illiquid")

    elif atype == "stock":
        hist   = data.get("hist")
        if hist is None or len(hist) < 5:
            return 100, ["no data"]

        prices = hist["Close"].tolist()
        vols   = hist["Volume"].tolist()

        # Volume spike tiba-tiba
        avg_vol = sum(vols[:-1]) / max(len(vols)-1, 1)
        if avg_vol > 0 and vols[-1] > avg_vol * 4:
            score += 30
            flags.append(f"vol spike {vols[-1]/avg_vol:.1f}x avg")

        # Price spike
        if len(prices) >= 3:
            chg3d = (prices[-1] - prices[-4]) / prices[-4] * 100 if prices[-4] > 0 else 0
            if abs(chg3d) > 30:
                score += 25
                flags.append(f"3d change={chg3d:.1f}%")

        # Market cap check
        mcap = data.get("mcap", 0)
        if mcap < 50_000_000:
            score += 20
            flags.append(f"mcap=${mcap/1e6:.0f}M (<$50M micro cap)")

    return score, flags


# ============================================================
# MACRO ALIGNMENT
# ============================================================
NARRATIVE_ASSETS = {
    "AI_TECH":        ["NVDA","AAPL","QQQ","IONQ","SOUN"],
    "CRYPTO_BULL":    ["BTC","ETH","SOL","BNB","STX"],
    "DEFI_SEASON":    ["ETH","BNB","SEI","STX"],
    "INFLATION_HEDGE":["GLD","SLV","BTC","USO"],
    "SEMIS_SUPPLY":   ["NVDA","TSLA","RKLB","IONQ"],
    "RISK_OFF":       ["GLD","SPY","RXRX"],
    "EMERGING_TECH":  ["TSLA","RKLB","ASTS","ACHR","JOBY"],
}

def get_allowed_assets(active_narratives):
    allowed = set()
    for narr in active_narratives:
        allowed.update(NARRATIVE_ASSETS.get(narr, []))
    return allowed


# ============================================================
# POSITION SIZING (Kelly + Confidence)
# ============================================================
def calc_position_size(balance, confidence, kelly_mult, atype, mcap=0):
    """
    Dinamis berdasarkan Kelly × confidence
    Cap berdasarkan ukuran aset:
    - Large cap  (>$2B)  : max 15%
    - Mid cap    ($200M-$2B): max 8%
    - Small cap  ($20M-$200M): max 5%
    - Micro cap  (<$20M) : max 2%
    """
    base = balance * kelly_mult * confidence * 0.3

    if mcap >= 2_000_000_000:
        cap_pct = 0.15
    elif mcap >= 200_000_000:
        cap_pct = 0.08
    elif mcap >= 20_000_000:
        cap_pct = 0.05
    else:
        cap_pct = 0.02

    max_alloc = balance * cap_pct
    return round(min(base, max_alloc), 2)


# ============================================================
# MAIN SCREENER
# ============================================================
def run_screener(active_narratives=None, balance=1000, kelly_mult=0.5):
    if active_narratives is None:
        active_narratives = ["INFLATION_HEDGE", "RISK_OFF"]

    allowed = get_allowed_assets(active_narratives)
    print(f"Active narratives: {active_narratives}")
    print(f"Allowed assets: {allowed}\n")

    candidates = []

    # --- CRYPTO SCAN ---
    print("Scanning crypto...")
    try:
        # Cek cache dulu (max 6 jam)
        cache_file = "logs/coingecko_cache.json"
        coins = []
        use_cache = False
        if os.path.exists(cache_file):
            with open(cache_file) as f:
                cache = json.load(f)
            age_hours = (datetime.now().timestamp() - cache.get("ts", 0)) / 3600
            if age_hours < 6:
                coins = cache.get("coins", [])
                use_cache = True
                print(f"  Using cache ({age_hours:.1f}h old, {len(coins)} coins)")

        if not use_cache:
            pages = [1, 2, 3, 4, 5]
            for pg in pages:
                url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=50&page={pg}&sparkline=false&price_change_percentage=7d"
                r = requests.get(url, timeout=10)
                if r.status_code == 429:
                    print(f"  Rate limited page {pg}, skip")
                    time.sleep(2)
                    continue
                data = r.json()
                if isinstance(data, list):
                    coins.extend(data)
                time.sleep(1.5)  # delay antar page
            # Simpan cache
            with open(cache_file, "w") as f:
                json.dump({"ts": datetime.now().timestamp(), "coins": coins}, f)
            print(f"  Fetched {len(coins)} coins, cached")

        for c in coins:
            sym = c["symbol"].upper()
            if sym not in allowed:
                continue

            score, flags = manipulation_score(sym, "crypto", c)
            status = "REJECT" if score > 60 else "PASS"
            mcap = c.get("market_cap", 0)
            alloc = calc_position_size(balance, 0.7, kelly_mult, "crypto", mcap) if status == "PASS" else 0
            # mcap sudah dari CoinGecko

            candidates.append({
                "symbol": sym, "type": "crypto",
                "price": c["current_price"],
                "mcap": mcap,
                "vol": c.get("total_volume", 0),
                "manip_score": score,
                "flags": flags,
                "status": status,
                "alloc": alloc
            })
    except Exception as e:
        print(f"  Crypto scan error: {e}")

    # --- STOCK SCAN ---
    print("Scanning stocks...")
    stock_universe = [
        "NVDA","AAPL","TSLA","QQQ","SPY","GLD","SLV","USO",
        "IONQ","RXRX","SOUN","ACHR","JOBY","RKLB","LUNR","ASTS","MARA"
    ]

    for sym in stock_universe:
        if sym not in allowed:
            continue
        try:
            tk = yf.Ticker(sym)
            hist = tk.history(period="10d")
            if hist.empty:
                continue
            # Ambil mcap real dari yfinance
            try:
                mcap = tk.fast_info.market_cap or 0
            except:
                mcap = 0
            # ETF tidak punya mcap - set ke large cap dummy
            ETF_LIST = ["QQQ","SPY","GLD","SLV","USO","IWM","DIA","XLF","XLE","XLK","VTI","EEM"]
            if sym in ETF_LIST and mcap == 0:
                mcap = 50_000_000_000  # $50B dummy = large cap tier

            score, flags = manipulation_score(sym, "stock", {"hist": hist, "mcap": mcap})
            status = "REJECT" if score > 60 else "PASS"
            price = round(float(hist["Close"].iloc[-1]), 2)
            alloc = calc_position_size(balance, 0.7, kelly_mult, "stock", mcap) if status == "PASS" else 0

            candidates.append({
                "symbol": sym, "type": "stock",
                "price": price,
                "mcap": mcap,
                "manip_score": score,
                "flags": flags,
                "status": status,
                "alloc": alloc
            })
        except Exception as e:
            print(f"  {sym} error: {e}")

    # --- HASIL ---
    passed  = [c for c in candidates if c["status"] == "PASS"]
    rejected = [c for c in candidates if c["status"] == "REJECT"]

    print(f"\n{'='*60}")
    print(f"  SCREENING RESULTS")
    print(f"{'='*60}")
    print(f"  Scanned : {len(candidates)} aset")
    print(f"  PASSED  : {len(passed)}")
    print(f"  REJECTED: {len(rejected)}")
    print(f"\n  PASSED candidates:")
    print(f"  {'Symbol':<8} {'Type':<8} {'Price':>10} {'MScore':>8} {'Alloc$':>8}")
    print(f"  {'-'*50}")
    for c in sorted(passed, key=lambda x: x["manip_score"]):
        print(f"  {c['symbol']:<8} {c['type']:<8} ${c['price']:>9,.2f} {c['manip_score']:>7} ${c['alloc']:>7.2f}")

    if rejected:
        print(f"\n  REJECTED (manipulation suspect):")
        for c in rejected:
            print(f"  {c['symbol']:<8} score={c['manip_score']} flags={c['flags']}")

    result = {
        "timestamp": datetime.now().isoformat(),
        "narratives": active_narratives,
        "passed": passed,
        "rejected": rejected
    }
    with open("logs/screener_results.json", "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved to logs/screener_results.json")
    return passed

if __name__ == "__main__":
    run_screener(
        active_narratives=["INFLATION_HEDGE", "RISK_OFF", "AI_TECH"],
        balance=1000,
        kelly_mult=0.5
    )
