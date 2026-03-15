with open("bot.py","r",encoding="utf-8") as f: c=f.read()

# 1. Import
c = c.replace(
    "from core.momentum_filter import get_momentum_signal",
    "from core.momentum_filter import get_momentum_signal\nfrom core.dxy_filter import get_dxy_signal",
1)

# 2. Sisipkan DXY block sebelum momentum filter
old = "        # === MOMENTUM PRE-FILTER (Strategy E) ==="
new = (
    "        # === DXY MACRO FILTER ===\n"
    "        if info.get('type') == 'crypto':\n"
    "            dxy_sig, dxy_det = get_dxy_signal()\n"
    "            print(f'  [DXY] {dxy_sig} | DXY={dxy_det.get(\"dxy\")} trend={dxy_det.get(\"trend\")}')\n"
    "            dxy_penalty = 0.15 if dxy_sig == 'BEARISH' else 0.0\n"
    "        else:\n"
    "            dxy_penalty = 0.0\n"
    "\n"
    "        # === MOMENTUM PRE-FILTER (Strategy E) ==="
)
c = c.replace(old, new, 1)

# 3. Terapkan penalty di kondisi BUY
c = c.replace(
    "if signal == 'BUY' and conf >= 0.6 and not pos and alloc > 10:",
    "if signal == 'BUY' and (conf - dxy_penalty) >= 0.6 and not pos and alloc > 10:",
1)

with open("bot.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
