with open("bot.py","r",encoding="utf-8") as f: c=f.read()

old = "        signal, conf, wvotes, details, llm_signals = await get_signal_weighted("
new = (
    "        # === SMC + DELTA CONTEXT untuk LLM ===\n"
    "        if info.get('type') == 'crypto':\n"
    "            sym = info['symbol'].split('/')[0]\n"
    "            smc_text = get_smc_context(sym)\n"
    "            from core.momentum_filter import get_momentum_signal\n"
    "            _, mom_det = get_momentum_signal(sym)\n"
    "            delta_bull = mom_det.get('delta_bullish', None)\n"
    "            delta_text = 'DELTA: Buying pressure' if delta_bull == True else ('DELTA: Selling pressure' if delta_bull == False else 'DELTA: N/A')\n"
    "        else:\n"
    "            smc_text = ''\n"
    "            delta_text = ''\n"
    "\n"
    "        signal, conf, wvotes, details, llm_signals = await get_signal_weighted("
)
c = c.replace(old, new, 1)

with open("bot.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
