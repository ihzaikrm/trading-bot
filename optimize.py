# optimize.py
import subprocess
import json
import os
from itertools import product

SYMBOLS = ["SPX", "XAUUSD", "BTC/USDT"]
START = "2015-01-01"
END = "2024-01-01"
SL_VALUES = [1.0, 2.0, 3.0, 4.0, 5.0]
TP_VALUES = [3.0, 5.0, 8.0, 10.0]
LEVERAGE = 3

results = []

for symbol in SYMBOLS:
    best_return = -999
    best_params = None
    for sl, tp in product(SL_VALUES, TP_VALUES):
        print(f"Testing {symbol} SL={sl} TP={tp}...")
        cmd = [
            "py", "run_backtest.py",
            "--symbol", symbol,
            "--start", START,
            "--end", END,
            "--sl", str(sl),
            "--tp", str(tp),
            "--leverage", str(LEVERAGE)
        ]
        try:
            output = subprocess.check_output(cmd, text=True)
            # Parse total return dari output
            for line in output.splitlines():
                if "Total Return:" in line:
                    total_return = float(line.split("%")[0].split()[-1])
                    if total_return > best_return:
                        best_return = total_return
                        best_params = (sl, tp)
                    break
        except Exception as e:
            print(f"Error: {e}")
            continue
    results.append({
        "symbol": symbol,
        "best_sl": best_params[0] if best_params else None,
        "best_tp": best_params[1] if best_params else None,
        "best_return": best_return
    })
    print(f"Best for {symbol}: SL={best_params[0]} TP={best_params[1]} Return={best_return}%")

# Simpan hasil
with open("optimization_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Optimization complete. Results saved to optimization_results.json")