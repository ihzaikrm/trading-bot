c = open('bot.py', encoding='utf-8').read()

old = '''    data["positions"] = positions
    save_trades(data)'''

new = '''    data["positions"] = positions

    # ── Sprint 4: Narrative Rotation ──
    try:
        from core.narrative_scanner import run_narrative_scan, load_narrative_state
        from core.portfolio_manager import (
            alloc_per_asset, check_partial_tp,
            check_rotation_needed, get_portfolio_summary
        )
        print("\\n[3] Narrative scan...")
        market_ctx = "BTC: "+str(current_prices.get("BTC/USDT","?"))+" | XAUUSD: "+str(current_prices.get("XAUUSD","?"))+" | SPX: "+str(current_prices.get("SPX","?"))
        narrative_state = await run_narrative_scan(news_summary if "news_summary" in dir() else "", market_ctx)
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
                tg("🔄 ROTASI: Close "+sym+"\\nAlasan: "+reason+"\\nPnL: $"+str(round(pnl,2)))
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
                tg("💰 "+action+" "+sym+"\\n"+reason+"\\nPnL: $"+str(round(partial_pnl,2)))
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
            tg("🚀 NARRATIVE BUY "+sym+"\\nNarasi: "+info["narrative"]+"\\nHarga: $"+str(price)+"\\nAmount: $"+str(info["amount"])+"\\nTP: "+str(info["tp_pct"])+"% SL: "+str(info["sl_pct"])+"%")

        # Summary narrative portfolio
        narr_summary = get_portfolio_summary(
            {k:v for k,v in positions.items() if v.get("narrative")},
            current_prices)
        tg(narr_summary)

    except Exception as e:
        print("  [Narrative] Error:", e)

    data["positions"] = positions
    save_trades(data)'''

if old in c:
    c = c.replace(old, new)
    open('bot.py', 'w', encoding='utf-8').write(c)
    print('OK: narrative integration ditambahkan')
else:
    print('SKIP: pattern tidak ditemukan')
    print(repr(c[c.find('data["positions"]'):c.find('data["positions"]')+60]))
