# backtest/report.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # non-interactive backend

def calculate_metrics(results):
    """
    Hitung metrik performa dari hasil backtest
    """
    trades = results['trades']
    if not trades:
        return {
            'total_return': 0,
            'annual_return': 0,
            'winrate': 0,
            'total_trades': 0,
            'max_drawdown': 0,
            'sharpe': 0,
            'best_trade': 0,
            'worst_trade': 0
        }

    pnls = [t['pnl'] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    total_return = results['total_return']
    # Annual return (asumsi data harian, 252 trading days per tahun)
    days = (pd.to_datetime(results['end']) - pd.to_datetime(results['start'])).days
    years = days / 365.25
    annual_return = (1 + total_return/100) ** (1/years) - 1 if years > 0 else 0
    annual_return *= 100

    winrate = len(wins) / len(pnls) * 100 if pnls else 0

    # Max drawdown dari equity curve
    equity = results.get('equity_curve', [])
    if equity:
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak * 100
        max_drawdown = np.max(drawdown)
    else:
        max_drawdown = 0

    # Sharpe ratio (asumsi risk-free rate 0)
    returns = np.diff(equity) / equity[:-1] if len(equity) > 1 else [0]
    sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) != 0 else 0

    best_trade = max(pnls) if pnls else 0
    worst_trade = min(pnls) if pnls else 0

    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'winrate': winrate,
        'total_trades': len(trades),
        'max_drawdown': max_drawdown,
        'sharpe': sharpe,
        'best_trade': best_trade,
        'worst_trade': worst_trade
    }

def generate_report(results, output_file='backtest_result.png'):
    """
    Cetak laporan dan simpan grafik equity curve
    """
    metrics = calculate_metrics(results)
    trades = results['trades']

    print("\n" + "="*50)
    print(f"BACKTEST REPORT: {results['symbol']}")
    print(f"Periode: {results['start']} s/d {results['end']}")
    print("="*50)
    print(f"Initial Balance: ${results['initial_balance']:.2f}")
    print(f"Final Balance:   ${results['final_balance']:.2f}")
    print(f"Total Return:    {metrics['total_return']:.2f}%")
    print(f"Annual Return:   {metrics['annual_return']:.2f}%")
    print(f"Winrate:         {metrics['winrate']:.2f}%")
    print(f"Total Trades:    {metrics['total_trades']}")
    print(f"Max Drawdown:    {metrics['max_drawdown']:.2f}%")
    print(f"Sharpe Ratio:    {metrics['sharpe']:.2f}")
    print(f"Best Trade:      ${metrics['best_trade']:.2f}")
    print(f"Worst Trade:     ${metrics['worst_trade']:.2f}")
    print("="*50)

    # Plot equity curve
    if results.get('equity_curve'):
        plt.figure(figsize=(10, 5))
        plt.plot(results['equity_curve'], label='Equity Curve')
        plt.axhline(y=results['initial_balance'], color='r', linestyle='--', label='Initial Balance')
        plt.title(f"Equity Curve - {results['symbol']}")
        plt.xlabel("Time (bars)")
        plt.ylabel("Balance ($)")
        plt.legend()
        plt.grid(True)
        plt.savefig(output_file)
        print(f"Equity curve saved to {output_file}")
        plt.close()