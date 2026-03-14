"""
Dynamic LLM Weighting System
Kombinasi: Winrate + Profit Weight + ELO Rating
Update: setiap siklus real-time
"""
import json, os, math
from datetime import datetime

WEIGHT_FILE = "logs/llm_performance.json"

DEFAULT_PERFORMANCE = {
    "claude":   {"elo": 1200, "wins": 0, "losses": 0, "total_pnl": 0.0, "predictions": 0, "correct": 0},
    "gemini":   {"elo": 1200, "wins": 0, "losses": 0, "total_pnl": 0.0, "predictions": 0, "correct": 0},
    "gpt":      {"elo": 1200, "wins": 0, "losses": 0, "total_pnl": 0.0, "predictions": 0, "correct": 0},
    "grok":     {"elo": 1200, "wins": 0, "losses": 0, "total_pnl": 0.0, "predictions": 0, "correct": 0},
    "deepseek": {"elo": 1200, "wins": 0, "losses": 0, "total_pnl": 0.0, "predictions": 0, "correct": 0},
    "qwen":     {"elo": 1200, "wins": 0, "losses": 0, "total_pnl": 0.0, "predictions": 0, "correct": 0},
}

def load_performance():
    if os.path.exists(WEIGHT_FILE):
        with open(WEIGHT_FILE) as f:
            data = json.load(f)
        # Pastikan semua LLM ada
        for llm in DEFAULT_PERFORMANCE:
            if llm not in data:
                data[llm] = DEFAULT_PERFORMANCE[llm].copy()
        return data
    return {k: v.copy() for k, v in DEFAULT_PERFORMANCE.items()}

def save_performance(data):
    os.makedirs("logs", exist_ok=True)
    with open(WEIGHT_FILE, "w") as f:
        json.dump(data, f, indent=2)

def calc_weights(perf):
    """Hitung bobot dinamis: 40% winrate + 40% profit + 20% ELO"""
    weights = {}
    
    # 1. Winrate score (0-1)
    winrate_scores = {}
    for llm, p in perf.items():
        if p["predictions"] >= 5:  # Min 5 prediksi sebelum dinilai
            winrate_scores[llm] = p["correct"] / p["predictions"]
        else:
            winrate_scores[llm] = 0.5  # Default 50% kalau belum cukup data

    # 2. Profit score (normalized)
    pnls = [p["total_pnl"] for p in perf.values()]
    min_pnl, max_pnl = min(pnls), max(pnls)
    pnl_range = max_pnl - min_pnl if max_pnl != min_pnl else 1
    profit_scores = {}
    for llm, p in perf.items():
        profit_scores[llm] = (p["total_pnl"] - min_pnl) / pnl_range

    # 3. ELO score (normalized 800-1600 range)
    elos = [p["elo"] for p in perf.values()]
    min_elo, max_elo = min(elos), max(elos)
    elo_range = max_elo - min_elo if max_elo != min_elo else 1
    elo_scores = {}
    for llm, p in perf.items():
        elo_scores[llm] = (p["elo"] - min_elo) / elo_range

    # Kombinasi: 40% winrate + 40% profit + 20% ELO
    raw_weights = {}
    for llm in perf:
        raw_weights[llm] = (
            0.40 * winrate_scores[llm] +
            0.40 * profit_scores[llm] +
            0.20 * elo_scores[llm]
        )

    # Normalize ke range 0.05-0.40 (min 5%, max 40%)
    total = sum(raw_weights.values())
    if total == 0:
        # Semua sama rata kalau belum ada data
        for llm in perf:
            weights[llm] = round(1.0 / len(perf), 3)
    else:
        # Scale ke 0.05-0.40
        for llm in perf:
            normalized = raw_weights[llm] / total
            weights[llm] = round(max(0.05, min(0.40, normalized)), 3)
        # Pastikan total = 1.0
        total_w = sum(weights.values())
        for llm in weights:
            weights[llm] = round(weights[llm] / total_w, 3)

    return weights

def update_elo(winner_elo, loser_elo, k=32):
    """Update ELO setelah satu pertandingan"""
    expected_winner = 1 / (1 + 10**((loser_elo - winner_elo) / 400))
    expected_loser = 1 - expected_winner
    new_winner = winner_elo + k * (1 - expected_winner)
    new_loser = loser_elo + k * (0 - expected_loser)
    return round(new_winner), round(new_loser)

def record_prediction(llm_name, signal, actual_outcome, pnl=0.0):
    """
    Record hasil prediksi LLM
    actual_outcome: 'correct' atau 'wrong'
    pnl: profit/loss dari trade ini
    """
    perf = load_performance()
    if llm_name not in perf:
        perf[llm_name] = DEFAULT_PERFORMANCE[llm_name].copy()

    p = perf[llm_name]
    p["predictions"] += 1
    p["total_pnl"] += pnl

    if actual_outcome == "correct":
        p["correct"] += 1
        p["wins"] += 1
        # ELO: menang melawan semua yang salah
        for other_llm, other_p in perf.items():
            if other_llm != llm_name:
                new_w, new_l = update_elo(p["elo"], other_p["elo"])
                p["elo"] = new_w
                other_p["elo"] = new_l
    else:
        p["losses"] += 1
        # ELO: kalah melawan semua yang benar
        for other_llm, other_p in perf.items():
            if other_llm != llm_name:
                new_w, new_l = update_elo(other_p["elo"], p["elo"])
                other_p["elo"] = new_w
                p["elo"] = new_l

    save_performance(perf)
    return calc_weights(perf)

def get_current_weights():
    """Ambil bobot saat ini"""
    perf = load_performance()
    weights = calc_weights(perf)
    return weights

def get_leaderboard():
    """Tampilkan leaderboard LLM"""
    perf = load_performance()
    weights = calc_weights(perf)
    
    board = []
    for llm, p in perf.items():
        winrate = round(p["correct"]/p["predictions"]*100, 1) if p["predictions"] > 0 else 0
        board.append({
            "llm": llm,
            "elo": p["elo"],
            "winrate": winrate,
            "predictions": p["predictions"],
            "total_pnl": round(p["total_pnl"], 2),
            "weight": weights[llm]
        })
    
    # Sort by weight
    board.sort(key=lambda x: x["weight"], reverse=True)
    return board

def print_leaderboard():
    board = get_leaderboard()
    print("\n=== LLM LEADERBOARD ===")
    print(f"{'LLM':<12} {'ELO':>6} {'WR%':>6} {'Pred':>5} {'PnL':>8} {'Weight':>8}")
    print("-" * 52)
    for b in board:
        print(f"{b['llm']:<12} {b['elo']:>6} {b['winrate']:>5}% {b['predictions']:>5} ${b['total_pnl']:>7.2f} {b['weight']:>7.1%}")
    print("=" * 52)

if __name__ == "__main__":
    print("Test Dynamic Weighting System...")
    
    # Simulasi beberapa prediksi
    print("\nSimulasi prediksi...")
    record_prediction("claude", "BUY", "correct", pnl=15.0)
    record_prediction("gpt", "BUY", "correct", pnl=15.0)
    record_prediction("deepseek", "BUY", "correct", pnl=15.0)
    record_prediction("gemini", "HOLD", "wrong", pnl=0.0)
    record_prediction("grok", "SELL", "wrong", pnl=0.0)
    record_prediction("qwen", "BUY", "correct", pnl=15.0)
    
    record_prediction("claude", "SELL", "correct", pnl=8.0)
    record_prediction("gpt", "HOLD", "wrong", pnl=0.0)
    record_prediction("deepseek", "SELL", "correct", pnl=8.0)
    record_prediction("gemini", "BUY", "wrong", pnl=-5.0)
    record_prediction("grok", "BUY", "wrong", pnl=-5.0)
    record_prediction("qwen", "SELL", "correct", pnl=8.0)
    
    print_leaderboard()
    
    weights = get_current_weights()
    print("\nBobot saat ini:")
    for llm, w in sorted(weights.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(w * 50)
        print(f"  {llm:<12} {w:.1%} {bar}")
