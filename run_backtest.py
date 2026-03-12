# run_backtest.py
import argparse
from backtest.engine import backtest
from backtest.report import generate_report
from config.assets import ASSETS

def main():
    parser = argparse.ArgumentParser(description='Run backtest for a symbol')
    parser.add_argument('--symbol', type=str, default='BTC/USDT', help='Symbol to backtest')
    parser.add_argument('--start', type=str, default='2023-01-01', help='Start date YYYY-MM-DD')
    parser.add_argument('--end', type=str, default='2024-01-01', help='End date YYYY-MM-DD')
    parser.add_argument('--sl', type=float, default=2.0, help='Stop loss %')
    parser.add_argument('--tp', type=float, default=5.0, help='Take profit %')
    parser.add_argument('--leverage', type=int, default=1, help='Leverage')
    args = parser.parse_args()

    # Cari tipe aset dari ASSETS
    asset_info = None
    for name, info in ASSETS.items():
        if name == args.symbol or info['symbol'] == args.symbol:
            asset_info = info
            break
    if not asset_info:
        print(f"Symbol {args.symbol} tidak ditemukan di ASSETS. Gunakan salah satu: {list(ASSETS.keys())}")
        return

    print(f"Running backtest for {args.symbol}...")
    result = backtest(
        symbol=asset_info['symbol'],
        asset_type=asset_info['type'],
        start_date=args.start,
        end_date=args.end,
        sl_pct=args.sl,
        tp_pct=args.tp,
        leverage=args.leverage
    )
    if result is None:
        print("Backtest gagal: data tidak cukup.")
        return

    generate_report(result, output_file=f"backtest_{args.symbol.replace('/', '_')}.png")

if __name__ == "__main__":
    main()