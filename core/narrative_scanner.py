"""

Sprint A: Narrative Scanner + Asset Universe

LLM scan narasi dominan setiap 2 jam

"""

import json, os, sys, re, asyncio

from datetime import datetime



sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv

load_dotenv()

from core.llm_clients import call_all_llms



NARRATIVE_FILE = "logs/narrative_state.json"



# Universe aset per narasi

NARRATIVES = {

    "AI_TECH": {

        "description": "AI & semiconductor boom",

        "keywords": ["nvidia","ai","artificial intelligence","semiconductor","gpu","llm","openai","chatgpt"],

        "assets": {

            "stocks": ["NVDA","AMD","MSFT","GOOGL","META","TSMC","ASML"],

            "crypto": ["FET/USDT","RNDR/USDT","WLD/USDT"],

        },

        "risk": "moderate",

        "tp_pct": 40,

        "sl_pct": 15,

    },

    "CRYPTO_BULL": {

        "description": "Crypto bull market / halving cycle",

        "keywords": ["bitcoin","btc","crypto","halving","bull run","altseason","blockchain"],

        "assets": {

            "crypto": ["BTC/USDT","ETH/USDT","SOL/USDT","BNB/USDT","AVAX/USDT"],

            "stocks": ["COIN","MSTR"],

        },

        "risk": "aggressive",

        "tp_pct": 50,

        "sl_pct": 20,

    },

    "DEFI_SEASON": {

        "description": "DeFi & Web3 narrative",

        "keywords": ["defi","decentralized finance","yield","liquidity","dex","uniswap","aave"],

        "assets": {

            "crypto": ["UNI/USDT","AAVE/USDT","MKR/USDT","CRV/USDT","LDO/USDT"],

        },

        "risk": "aggressive",

        "tp_pct": 60,

        "sl_pct": 25,

    },

    "INFLATION_HEDGE": {

        "description": "Inflation hedge & macro uncertainty",

        "keywords": ["inflation","cpi","fed","interest rate","gold","commodity","oil","recession"],

        "assets": {

            "commodities": ["GC=F","CL=F","SI=F"],

            "crypto": ["BTC/USDT"],

            "stocks": ["GLD","SLV","USO"],

        },

        "risk": "conservative",

        "tp_pct": 25,

        "sl_pct": 10,

    },

    "SEMIS_SUPPLY": {

        "description": "Semiconductor supply chain",

        "keywords": ["semiconductor","chip","wafer","tsmc","asml","supply chain","foundry"],

        "assets": {

            "stocks": ["ASML","TSM","AMAT","KLAC","LRCX","MU"],

        },

        "risk": "moderate",

        "tp_pct": 35,

        "sl_pct": 12,

    },

    "RISK_OFF": {

        "description": "Bear market / high uncertainty — hold cash",

        "keywords": ["crash","recession","crisis","war","panic","fear","selloff","bear market"],

        "assets": {

            "commodities": ["GC=F"],

            "cash_pct": 80,

        },

        "risk": "conservative",

        "tp_pct": 15,

        "sl_pct": 8,

    },

    "EMERGING_TECH": {

        "description": "Emerging tech: biotech, space, energy",

        "keywords": ["biotech","space","clean energy","ev","electric vehicle","solar","nuclear"],

        "assets": {

            "stocks": ["TSLA","ENPH","NEE","LMT","ARKG"],

        },

        "risk": "moderate",

        "tp_pct": 35,

        "sl_pct": 15,

    },

}



def load_narrative_state():

    if os.path.exists(NARRATIVE_FILE):

        with open(NARRATIVE_FILE) as f:

            return json.load(f)

    return {

        "active_narratives": [],

        "last_scan": None,

        "history": []

    }



def save_narrative_state(state):

    os.makedirs("logs", exist_ok=True)

    with open(NARRATIVE_FILE, "w") as f:

        json.dump(state, f, indent=2)



def score_narrative_from_news(news_text, narrative_name, narrative_info):

    """Hitung skor narasi berdasarkan kemunculan keyword di berita"""

    score = 0

    text_lower = news_text.lower()

    for kw in narrative_info["keywords"]:

        count = text_lower.count(kw)

        score += count

    return score



async def scan_narratives_llm(news_text, market_context):

    """6 LLM voting narasi dominan saat ini"""

    narrative_list = "\n".join([

        f"- {name}: {info['description']}"

        for name, info in NARRATIVES.items()

    ])



    prompt = ("Analisa kondisi market saat ini berdasarkan berita dan data berikut:\n\n"

             "BERITA TERKINI:\n" + news_text[:500] + "\n\n"

             "MARKET DATA:\n" + (str(market_context) if not isinstance(market_context,str) else market_context) + "\n\n"

             "PILIHAN NARASI:\n" + narrative_list + "\n\n"

             "Pilih TOP 3 narasi. "

             "Tentukan juga profil risk: conservative/moderate/aggressive.\n"

             'Balas HANYA JSON:\n'

             '{"narratives":["NARASI1","NARASI2","NARASI3"],'

             '"risk_profile":"moderate",'

             '"reasoning":"max 20 kata",'

             '"rotation_urgency":"low/medium/high"}')



    try:
        results = await asyncio.wait_for(call_all_llms("Analis macro & narrative trading. Balas JSON saja.", prompt), timeout=25)
    except asyncio.TimeoutError:
        print("  Narrative LLM timeout - skip")
        return [], "moderate", "low", {}



    narrative_votes = {n: 0 for n in NARRATIVES}

    risk_votes = []

    urgency_votes = []

    llm_results = {}



    for llm, (ok, resp) in results.items():

        if ok:

            try:

                r = json.loads(re.search(r"\{.*\}", resp, re.DOTALL).group())

                narratives = r.get("narratives", [])

                for i, narr in enumerate(narratives[:3]):

                    if narr in narrative_votes:

                        # Narasi #1 dapat 3 poin, #2 dapat 2 poin, #3 dapat 1 poin

                        narrative_votes[narr] += (3 - i)

                risk_votes.append(r.get("risk_profile", "moderate"))

                urgency_votes.append(r.get("rotation_urgency", "low"))

                llm_results[llm] = r

            except:

                pass



    # Top 3 narasi berdasarkan vote

    top_narratives = sorted(narrative_votes.items(), key=lambda x: x[1], reverse=True)

    top3 = [(n, v) for n, v in top_narratives if v > 0][:3]



    # Risk profile mayoritas

    from collections import Counter

    risk_profile = Counter(risk_votes).most_common(1)[0][0] if risk_votes else "moderate"

    rotation_urgency = Counter(urgency_votes).most_common(1)[0][0] if urgency_votes else "low"



    return top3, risk_profile, rotation_urgency, llm_results



def get_assets_for_narratives(top_narratives, risk_profile, max_positions=5):

    """Pilih aset terbaik dari narasi aktif"""

    selected = []

    used_symbols = set()



    # Alokasi berdasarkan risk profile

    alloc_map = {

        "conservative": {"crypto": 20, "stocks": 30, "commodities": 30, "cash": 20},

        "moderate":     {"crypto": 35, "stocks": 35, "commodities": 15, "cash": 15},

        "aggressive":   {"crypto": 50, "stocks": 35, "commodities": 5,  "cash": 10},

    }

    allocation = alloc_map.get(risk_profile, alloc_map["moderate"])



    for narr_name, score in top_narratives:

        if narr_name not in NARRATIVES:

            continue

        narr = NARRATIVES[narr_name]

        assets = narr["assets"]



        # Ambil top asset per kategori

        for category, symbols in assets.items():

            if category == "cash_pct":

                continue

            if isinstance(symbols, list):

                for sym in symbols[:2]:  # Max 2 per narasi

                    if sym not in used_symbols and len(selected) < max_positions:

                        selected.append({

                            "symbol": sym,

                            "narrative": narr_name,

                            "category": category,

                            "tp_pct": narr["tp_pct"],

                            "sl_pct": narr["sl_pct"],

                            "score": score

                        })

                        used_symbols.add(sym)



    return selected, allocation



async def run_narrative_scan(news_text="", market_context=""):

    """Main: scan narasi + pilih aset"""

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"\n[NARRATIVE SCAN] {now}")



    # Score dari keyword berita

    keyword_scores = {}

    for name, info in NARRATIVES.items():

        keyword_scores[name] = score_narrative_from_news(news_text, name, info)



    top_keyword = sorted(keyword_scores.items(), key=lambda x: x[1], reverse=True)[:3]

    print("  Keyword scores: " + ", ".join([f"{n}:{s}" for n,s in top_keyword]))



    # LLM voting

    print("  LLM voting narasi...")

    top_narratives, risk_profile, urgency, llm_results = await scan_narratives_llm(

        news_text, market_context)



    print(f"  Top narratives: {[(n,v) for n,v in top_narratives]}")

    print(f"  Risk profile: {risk_profile} | Urgency: {urgency}")



    # Pilih aset

    selected_assets, allocation = get_assets_for_narratives(

        top_narratives, risk_profile)



    print(f"\n  Selected {len(selected_assets)} aset:")

    for a in selected_assets:

        print(f"    {a['symbol']} [{a['narrative']}] TP:{a['tp_pct']}% SL:{a['sl_pct']}%")



    print(f"\n  Alokasi: {allocation}")



    # Simpan state

    state = load_narrative_state()

    prev_narratives = [n for n,_ in state.get("active_narratives", [])]

    curr_narratives = [n for n,_ in top_narratives]



    # Deteksi rotasi

    rotation_needed = urgency == "high" or set(prev_narratives) != set(curr_narratives)

    if rotation_needed and prev_narratives:

        print(f"\n  ⚡ ROTASI DETECTED: {prev_narratives} → {curr_narratives}")



    state["active_narratives"] = top_narratives

    state["risk_profile"] = risk_profile

    state["rotation_urgency"] = urgency

    state["selected_assets"] = selected_assets

    state["allocation"] = allocation

    state["last_scan"] = now

    state["rotation_needed"] = rotation_needed

    state["history"].append({

        "time": now,

        "narratives": curr_narratives,

        "risk": risk_profile

    })

    # Simpan max 100 history

    state["history"] = state["history"][-100:]

    save_narrative_state(state)



    return state



if __name__ == "__main__":

    print("=== NARRATIVE SCANNER TEST ===")

    # Test dengan berita sample

    sample_news = """

    Bitcoin surges past $70,000 as institutional demand grows.

    NVIDIA reports record earnings driven by AI chip demand.

    Federal Reserve signals potential rate cuts amid cooling inflation.

    Gold hits all-time high as geopolitical tensions rise.

    Ethereum ETF approval drives crypto market rally.

    """

    sample_market = "BTC: $70,868 +3% | GOLD: $2,340 +0.5% | SPX: 5,200 -0.3%"

    asyncio.run(run_narrative_scan(sample_news, sample_market))


