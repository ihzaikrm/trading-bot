import asyncio, json, os, sys, re, requests



from datetime import datetime



from collections import Counter



import ccxt



import pandas as pd







sys.path.insert(0, os.getcwd())



from dotenv import load_dotenv



load_dotenv()



from core.llm_clients import call_all_llms
from core.momentum_filter import get_momentum_signal



from core.dynamic_weights import get_current_weights, record_prediction, print_leaderboard, get_leaderboard



from core.news_pipeline import get_multi_timeframe_news
from core.performance_boost import (get_fear_greed, apply_fg_to_signal,
    update_trailing_stop, clear_trailing_stop, is_too_correlated)
from core.cot_weekly import (build_cot_prompt, generate_weekly_report,
    should_send_weekly_report, tg as tg_report)

from core.performance_boost import (get_fear_greed, apply_fg_to_signal,

    update_trailing_stop, clear_trailing_stop, is_too_correlated)

from core.cot_weekly import (build_cot_prompt, generate_weekly_report,

    should_send_weekly_report, tg as tg_report)







BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")



CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")



PAPER_FILE = "logs/paper_trades.json"







ASSETS = {



    "BTC/USDT": {"type": "crypto", "symbol": "BTC/USDT", "name": "Bitcoin"},



    "XAUUSD":   {"type": "stock",  "symbol": "GC=F",     "name": "Gold"},



    "SPX":      {"type": "stock",  "symbol": "^GSPC",    "name": "S&P 500"},



}







def tg(msg):



    try:



        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",



            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)



    except Exception as e:



        print(f"[TG] Gagal: {e}")







def load_trades():



    if os.path.exists(PAPER_FILE):



        with open(PAPER_FILE) as f:



            return json.load(f)



    return {"balance": 1000.0, "trades": [], "positions": {}}







def save_trades(data):



    os.makedirs("logs", exist_ok=True)



    with open(PAPER_FILE, "w") as f:



        json.dump(data, f, indent=2)







def calc_indicators(closes):



    s = pd.Series(closes)



    delta = s.diff()



    gain = delta.clip(lower=0).rolling(14).mean()



    loss = -delta.clip(upper=0).rolling(14).mean()



    rs = gain / loss.replace(0, 1)



    rsi = round(float((100 - 100/(1+rs)).iloc[-1]), 2)



    ema12 = s.ewm(span=12).mean()



    ema26 = s.ewm(span=26).mean()



    macd = ema12 - ema26



    signal = macd.ewm(span=9).mean()



    macd_hist = round(float((macd - signal).iloc[-1]), 4)



    macd_cross = "BULLISH" if macd.iloc[-1] > signal.iloc[-1] else "BEARISH"



    return rsi, macd_hist, macd_cross







def get_crypto_data(symbol):



    ex = ccxt.gate()



    t = ex.fetch_ticker(symbol)



    price = float(t.get("last") or t.get("close") or 0)



    change = float(t.get("percentage") or 0)



    ohlcv = ex.fetch_ohlcv(symbol, "1d", limit=50)



    closes = [c[4] for c in ohlcv]



    rsi, macd_hist, macd_cross = calc_indicators(closes)



    return round(price,2), round(change,2), rsi, macd_hist, macd_cross







def get_stock_data(symbol):



    import yfinance as yf



    hist = yf.Ticker(symbol).history(period="60d")



    if hist.empty:



        return None



    price = round(float(hist["Close"].iloc[-1]), 2)



    change = round((price - float(hist["Close"].iloc[-2])) / float(hist["Close"].iloc[-2]) * 100, 2)



    rsi, macd_hist, macd_cross = calc_indicators(hist["Close"].tolist())



    return price, change, rsi, macd_hist, macd_cross







def get_asset_data(name, info):



    try:



        if info["type"] == "crypto":



            return get_crypto_data(info["symbol"])



        else:



            return get_stock_data(info["symbol"])



    except Exception as e:



        print(f"  Error {name}: {e}")



        return None







def filter_news_for_asset(news_results, asset_name):



    """Filter berita yang relevan untuk aset tertentu"""



    asset_keywords = {



        "Bitcoin":  ["bitcoin", "btc", "crypto", "cryptocurrency", "satoshi"],



        "Gold":     ["gold", "xau", "precious metal", "commodity", "silver"],



        "S&P 500":  ["s&p", "sp500", "nasdaq", "dow", "stock market", "equities", "fed", "inflation"]



    }



    keywords = asset_keywords.get(asset_name, [])



    relevant = []



    for tf, data in news_results.items():



        for n in data["news"]:



            title_lower = n["title"].lower()



            if any(kw in title_lower for kw in keywords):



                weight = data["weight"]



                if n["verified"]:



                    weight *= 1.5



                relevant.append({**n, "timeframe": tf, "weight": weight})



    relevant.sort(key=lambda x: x["weight"], reverse=True)



    return relevant[:5]







async def get_signal_weighted(name, price, change, rsi, macd_hist, macd_cross, news_text):



    """Voting dengan dynamic weighting + news context"""



    weights = get_current_weights()



    prompt = (name+" | Harga: "+str(price)+" | 24h: "+str(change)+"%\n"



             "RSI: "+str(rsi)+" | MACD: "+str(macd_hist)+" ("+macd_cross+")\n\n"



             +news_text+"\n\n"



             "Pertimbangkan data teknikal DAN berita di atas.\n"



             'Balas JSON: {"signal":"BUY/SELL/HOLD","confidence":0.0-1.0,"reason":"max 10 kata"}')



    results = await call_all_llms("Analis trading profesional. Balas JSON saja.", prompt)







    weighted_votes = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}



    details = []



    llm_signals = {}







    for llm, (ok, resp) in results.items():



        if ok:



            try:



                r = json.loads(re.search(r"\{.*\}", resp, re.DOTALL).group())



                sig = r.get("signal", "HOLD")



                if sig not in weighted_votes:



                    sig = "HOLD"



                conf = float(r.get("confidence", 0.5))



                w = weights.get(llm, 1/6)



                weighted_votes[sig] += conf * w



                llm_signals[llm] = sig



                details.append(llm+"("+str(round(w*100))+"%) → "+sig+" ("+str(round(conf*100))+"%)")



            except: pass







    final_signal = max(weighted_votes, key=weighted_votes.get)



    total_weight = sum(weighted_votes.values())



    confidence = round(weighted_votes[final_signal] / total_weight, 2) if total_weight > 0 else 0.5



    return final_signal, confidence, weighted_votes, details, llm_signals







async def main():



    now = datetime.now().strftime("%Y-%m-%d %H:%M")



    print("=== TRADING BOT | "+now+" ===")



    data = load_trades()



    positions = data.get("positions", {})







    # Ambil berita multi-timeframe



    print("\n[1] Scan berita...")



    try:



        news_results, news_summary = get_multi_timeframe_news()



        verified_total = sum(v["verified_count"] for v in news_results.values())



        print(f"  Total verified: {verified_total}")



    except Exception as e:



        print(f"  News error: {e}")



        news_results = {}



        news_summary = "Berita tidak tersedia."







    # Circuit breaker



    initial = 1000.0



    current = data["balance"]



    for name, pos in positions.items():



        result = get_asset_data(name, ASSETS.get(name, {"type":"stock","symbol":name}))



        if result:



            price = result[0]



            current += pos["amount"] + (price - pos["entry_price"]) * pos["qty"]



    drawdown = max(0, (initial - current) / initial * 100)







    if drawdown > 5:



        msg = "CIRCUIT BREAKER: Drawdown "+str(round(drawdown,1))+"% > 5%!"



        print(msg); tg(msg)



        return







    # ── VIX Regime Detection ──────────────────────────────



    try:



        import yfinance as yf



        vix_hist = yf.Ticker("^VIX").history(period="2d")



        vix = round(float(vix_hist["Close"].iloc[-1]), 2) if not vix_hist.empty else 20.0



    except:



        vix = 20.0







    if vix < 15:



        regime = "BULL"



        kelly_mult = 1.0



    elif vix < 25:



        regime = "NORMAL"



        kelly_mult = 0.8



    elif vix < 35:



        regime = "FEAR"



        kelly_mult = 0.5



    else:



        regime = "PANIC"



        kelly_mult = 0.0







    print(f"  VIX: {vix} | Regime: {regime} | Kelly mult: {kelly_mult}")



    if kelly_mult == 0.0:



        msg = f"⚠️ PANIC REGIME (VIX {vix}) — skip semua entry"



        print(msg); tg(msg)







    alloc = data["balance"] / len(ASSETS) * kelly_mult



    summary = []







    # Build current_prices dict untuk narrative module



    current_prices = {}



    print("\n[2] Analisa aset...")



    for name, info in ASSETS.items():



        result = get_asset_data(name, info)



        if not result:



            continue



        price, change, rsi, macd_hist, macd_cross = result



        current_prices[name] = price



        print(f"  {name}: ${price} | RSI:{rsi} | MACD:{macd_cross}")







        # Filter berita untuk aset ini



        asset_news = filter_news_for_asset(news_results, info["name"])



        if asset_news:



            news_text = "BERITA RELEVAN:\n"



            for n in asset_news:



                status = "✅" if n["verified"] else "⚠️"



                news_text += status+" ["+n["timeframe"]+"] "+n["title"][:70]+"\n"



        else:



            news_text = "Tidak ada berita spesifik untuk aset ini."







        # === MOMENTUM PRE-FILTER (Strategy E) ===
        if info.get('type') == 'crypto':
            mom_sig, mom_det = get_momentum_signal(info['symbol'].split('/')[0])
            print(f'  [MomentumFilter] {mom_sig} | {mom_det}')
            if mom_sig == 'BEARISH':
                print(f'  -> SKIP LLM (Momentum BEARISH)')
                summary.append(name+': HOLD (momentum filter)')
                continue
        else:
            mom_sig = 'NEUTRAL'

        signal, conf, wvotes, details, llm_signals = await get_signal_weighted(



            info["name"], price, change, rsi, macd_hist, macd_cross, news_text)



        print(f"  -> {signal} conf:{conf}")



        summary.append(name+": "+signal+" ("+str(conf)+")")







        pos = positions.get(name)







        if signal == "BUY" and conf >= 0.6 and not pos and alloc > 10:



            qty = alloc / price



            positions[name] = {



                "entry_price": price, "qty": qty,



                "amount": alloc, "time": now,



                "pending_llm_signals": llm_signals



            }



            data["balance"] -= alloc



            msg = ("BUY "+info["name"]+"\n"



                  "Harga: $"+str(price)+"\n"



                  "Qty: "+str(round(qty,6))+"\n"



                  "Amount: $"+str(round(alloc,2))+"\n"



                  "RSI: "+str(rsi)+" | MACD: "+macd_cross+"\n"



                  "Conf: "+str(conf)+"\n\n"



                  "Voting:\n"+"\n".join(details)+"\n\n"



                  "News:\n"+news_text[:200])



            tg(msg)







        elif signal == "SELL" and pos:



            pnl = (price - pos["entry_price"]) * pos["qty"]



            data["balance"] += pos["amount"] + pnl



            if "pending_llm_signals" in pos:



                for llm, sig in pos["pending_llm_signals"].items():



                    if sig == "BUY":



                        outcome = "correct" if pnl > 0 else "wrong"



                        record_prediction(llm, sig, outcome, pnl/6)



            data["trades"].append({



                **{k:v for k,v in pos.items() if k!="pending_llm_signals"},



                "asset": name, "exit_price": price,



                "pnl": round(pnl,2), "exit_time": now



            })



            del positions[name]



            emoji = "✅" if pnl > 0 else "🔴"



            msg = (emoji+" SELL "+info["name"]+"\nPnL: $"+str(round(pnl,2))+



                   "\nBalance: $"+str(round(data["balance"],2)))



            tg(msg)







    data["positions"] = positions







    # ── Sprint 4: Narrative Rotation ──



    try:



        from core.narrative_scanner import run_narrative_scan, load_narrative_state



        from core.portfolio_manager import (



            alloc_per_asset, check_partial_tp,



            check_rotation_needed, get_portfolio_summary



        )



        print("\n[3] Narrative scan...")



        market_ctx = "BTC: "+str(current_prices.get("BTC/USDT","?"))+" | XAUUSD: "+str(current_prices.get("XAUUSD","?"))+" | SPX: "+str(current_prices.get("SPX","?"))



        # Ambil news dari cache file



        import json as _json, os as _os



        _cache = _os.path.join("logs","news_cache.json")



        try:



            _news = _json.load(open(_cache, encoding="utf-8")) if _os.path.exists(_cache) else {}



            _results = _news.get("results",{}); _1h = _results.get("1h",{}).get("news",[]); _6h = _results.get("6h",{}).get("news",[]); _titles = [n.get("title","") for n in _1h[:3]] + [n.get("title","") for n in _6h[:3]]



            news_text_for_narr = " ".join(_titles)



        except:



            news_text_for_narr = ""



        narrative_state = await run_narrative_scan(news_text_for_narr, market_ctx)



        top_narr = [(n,v) for n,v in narrative_state.get("active_narratives",[])]



        print("  Top narratives:", top_narr[:3])







        # Cek rotasi posisi existing



        to_close = check_rotation_needed(narrative_state, positions)



        for sym, reason in to_close:



            if sym in positions:



                pos = positions[sym]



                price = current_prices.get(sym, pos["entry_price"])



                pnl = (price - pos["entry_price"]) * pos["qty"]



                data["balance"] += pos["amount"] + pnl



                data["trades"].append({**{k:v for k,v in pos.items() if k!="pending_llm_signals"},



                    "asset":sym,"exit_price":price,"pnl":round(pnl,2),"exit_time":now,"exit_reason":"ROTATION"})



                del positions[sym]



                tg("🔄 ROTASI: Close "+sym+"\nAlasan: "+reason+"\nPnL: $"+str(round(pnl,2)))



                print("  Rotation close:", sym, reason)







        # Cek partial TP posisi existing



        for sym, pos in list(positions.items()):



            price = current_prices.get(sym, 0)



            if price <= 0: continue



            tp_pct = pos.get("tp_pct", 30)



            action, qty_sell, reason = check_partial_tp(sym, pos["entry_price"], price, pos["qty"], tp_pct)



            if action in ["PARTIAL_TP_1","PARTIAL_TP_2"]:



                partial_pnl = (price - pos["entry_price"]) * qty_sell



                data["balance"] += (pos["amount"] * qty_sell/pos["qty"]) + partial_pnl



                positions[sym]["qty"] -= qty_sell



                positions[sym]["amount"] -= pos["amount"] * qty_sell/pos["qty"]



                tg("💰 "+action+" "+sym+"\n"+reason+"\nPnL: $"+str(round(partial_pnl,2)))



                print("  Partial TP:", sym, action, reason)







        # Buka posisi baru dari narasi



        narrative_alloc = alloc_per_asset(narrative_state, data["balance"], max_positions=5)



        open_count = len(positions)



        for sym, info in narrative_alloc.items():



            if open_count >= 5: break



            if sym in positions: continue



            if info["amount"] < 10: continue



            # Skip aset yang butuh data berbeda (yfinance/stock)



            if "/" not in sym and sym not in ["GC=F","^GSPC"]: continue



            price = current_prices.get(sym, 0)



            if price <= 0: continue



            qty = info["amount"] / price



            positions[sym] = {



                "entry_price": price, "qty": qty,



                "amount": info["amount"], "time": now,



                "narrative": info["narrative"],



                "tp_pct": info["tp_pct"], "sl_pct": info["sl_pct"]



            }



            data["balance"] -= info["amount"]



            open_count += 1



            tg("🚀 NARRATIVE BUY "+sym+"\nNarasi: "+info["narrative"]+"\nHarga: $"+str(price)+"\nAmount: $"+str(info["amount"])+"\nTP: "+str(info["tp_pct"])+"% SL: "+str(info["sl_pct"])+"%")







        # Summary narrative portfolio



        narr_summary = get_portfolio_summary(



            {k:v for k,v in positions.items() if v.get("narrative")},



            current_prices)



        tg(narr_summary)







    except Exception as e:



        print("  [Narrative] Error:", e)







    data["positions"] = positions



    save_trades(data)







    # Leaderboard top 3



    board = get_leaderboard()



    lb_text = "TOP LLM:\n"



    for b in board[:3]:



        lb_text += b["llm"]+" W:"+str(round(b["weight"]*100))+"% ELO:"+str(b["elo"])+"\n"







    trades = data["trades"]



    wins = sum(1 for t in trades if t.get("pnl",0) > 0)



    winrate = str(round(wins/len(trades)*100))+"%" if trades else "N/A"



    total_pnl = sum(t.get("pnl",0) for t in trades)



    open_pos = ", ".join(positions.keys()) if positions else "Tidak ada"







    status = ("STATUS "+now+"\n"



             "Balance: $"+str(round(data["balance"],2))+"\n"



             "Drawdown: "+str(round(drawdown,1))+"%\n"



             "Posisi: "+open_pos+"\n\n"



             +"\n".join(summary)+"\n\n"



             +lb_text+"\n"



             "Trade: "+str(len(trades))+" | Winrate: "+winrate+"\n"



             "PnL: $"+str(round(total_pnl,2)))



    print("\n"+status)



    tg(status)



    print_leaderboard()



    print("=== SELESAI ===")







asyncio.run(main())



