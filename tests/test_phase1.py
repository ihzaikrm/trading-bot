import asyncio, sys, os, time, re, json
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import LLM_CONFIGS, TRADING
from core.llm_clients import call_llm, call_all_llms

G="\033[92m"; R="\033[91m"; Y="\033[93m"; C="\033[96m"; B="\033[1m"; D="\033[2m"; X="\033[0m"

def header():
    print(f"\n{B}{C}{'='*55}{X}")
    print(f"{B}{C}   AI TRADING BOT - PHASE 1 TEST{X}")
    print(f"{B}{C}{'='*55}{X}")
    print(f"   Mode    : {Y}{TRADING.mode.upper()}{X}")
    print(f"   Max Loss: {Y}{TRADING.max_daily_loss_pct}%/hari{X}\n")

def check_keys():
    print(f"{B}[1/3] CEK API KEYS{X}\n{'─'*55}")
    for name, cfg in LLM_CONFIGS.items():
        ok = cfg.is_available
        st = f"{G}✓ SIAP{X}" if ok else f"{Y}✗ Kosong{X}"
        print(f"  {C}{name:<12}{X} {st}  {D}[{cfg.role}]{X}")
    print()

async def test_one(name, cfg):
    if not cfg.is_available:
        return {"name":name,"ok":False,"resp":"API key kosong","lat":0,"skip":True}
    sys_p = f"Kamu adalah {cfg.role} dalam sistem trading."
    usr_p = 'Balas HANYA JSON: {"status":"OK","role":"<peranmu>","confidence":0.9}'
    t = time.time()
    ok, resp = await call_llm(name, sys_p, usr_p, use_cache=False)
    return {"name":name,"display":cfg.name,"ok":ok,"resp":resp,"lat":round(time.time()-t,2),"skip":False}

async def test_all():
    print(f"{B}[2/3] TEST KONEKSI INDIVIDUAL{X}\n{'─'*55}")
    results = []
    for name, cfg in LLM_CONFIGS.items():
        print(f"  Testing {C}{cfg.name}{X}...", end=" ", flush=True)
        r = await test_one(name, cfg)
        results.append(r)
        if r["skip"]: print(f"{Y}SKIP{X}")
        elif r["ok"]:
            print(f"{G}OK{X} ({r['lat']}s)")
            print(f"    {D}→ {r['resp'][:70]}{X}")
        else:
            print(f"{R}GAGAL{X}")
            print(f"    {R}→ {r['resp'][:80]}{X}")
    print()
    return results

async def test_parallel():
    print(f"{B}[3/3] TEST PARALLEL ENSEMBLE{X}\n{'─'*55}")
    avail = [n for n,c in LLM_CONFIGS.items() if c.is_available]
    if not avail:
        print(f"  {Y}Tidak ada LLM aktif.{X}\n"); return
    print(f"  Memanggil {len(avail)} LLM paralel: {C}{', '.join(avail)}{X}\n")
    sys_p = "Kamu adalah analis trading profesional."
    usr_p = 'Data BTC/USDT: Harga $67420, RSI=62, MACD bullish, Volume +15%\nBalas HANYA JSON: {"signal":"BUY/SELL/HOLD","confidence":0.0,"reason":"singkat"}'
    t = time.time()
    results = await call_all_llms(sys_p, usr_p, names=avail)
    total = round(time.time()-t, 2)
    signals = []
    print(f"  {'LLM':<12} {'Status':<8} {'Signal':<8} {'Conf':<6} Alasan")
    print(f"  {'─'*52}")
    for name, (ok, resp) in results.items():
        if ok:
            try:
                m = re.search(r'\{[^}]+\}', resp, re.DOTALL)
                d = json.loads(m.group()) if m else {}
                sig = d.get("signal","?"); conf = d.get("confidence","?"); reason = str(d.get("reason",""))[:30]
                signals.append(sig)
                sc = G if sig=="BUY" else (R if sig=="SELL" else Y)
                print(f"  {C}{name:<12}{X} {G}OK{X}      {sc}{sig:<8}{X} {str(conf):<6} {D}{reason}{X}")
            except:
                print(f"  {C}{name:<12}{X} {G}OK{X}      {D}{resp[:45]}{X}")
        else:
            print(f"  {C}{name:<12}{X} {R}GAGAL{X}   {D}{resp[:45]}{X}")
    if signals:
        top = Counter(signals).most_common(1)[0]
        sc = G if top[0]=="BUY" else (R if top[0]=="SELL" else Y)
        print(f"\n  {B}Konsensus: {sc}{top[0]}{X} ({top[1]}/{len(signals)} LLM setuju)")
    print(f"  {D}Waktu paralel: {total}s{X}\n")

def summary(results):
    ok = sum(1 for r in results if r["ok"])
    skip = sum(1 for r in results if r["skip"])
    fail = len(results) - ok - skip
    print(f"{B}{'='*55}\n  HASIL PHASE 1{X}\n{'─'*55}")
    print(f"  {G}Berhasil : {ok}{X}  |  {Y}Dilewati : {skip}{X}  |  {R}Gagal : {fail}{X}\n")
    if ok == len(results): print(f"  {G}{B}✓ PHASE 1 SELESAI! Lanjut ke Phase 2{X}")
    elif ok > 0: print(f"  {Y}⚡ Sebagian OK ({ok}/{len(results)}). Isi API key yang kosong.{X}")
    else: print(f"  {R}✗ Isi file .env dengan API keys Anda dulu!{X}")
    print(f"\n  {D}Panduan daftar API keys gratis:{X}")
    print(f"  {D}• Gemini (GRATIS) : https://aistudio.google.com{X}")
    print(f"  {D}• DeepSeek        : https://platform.deepseek.com{X}")
    print(f"  {D}• Claude          : https://console.anthropic.com{X}")
    print(f"{'='*55}\n")

async def main():
    header(); check_keys()
    results = await test_all()
    await test_parallel()
    summary(results)

if __name__ == "__main__":
    asyncio.run(main())
