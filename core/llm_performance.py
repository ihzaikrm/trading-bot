# core/llm_performance.py
import json
import os
from datetime import datetime

PERF_FILE = "logs/llm_performance.json"
PRED_FILE = "logs/predictions.json"

def load_performance():
    """Load performance data dari file JSON"""
    if os.path.exists(PERF_FILE):
        with open(PERF_FILE) as f:
            return json.load(f)
    # Default: semua LLM dengan data kosong
    return {
        "claude": {"correct": 0, "total": 0, "accuracy": 0.5},
        "gemini": {"correct": 0, "total": 0, "accuracy": 0.5},
        "gpt": {"correct": 0, "total": 0, "accuracy": 0.5},
        "grok": {"correct": 0, "total": 0, "accuracy": 0.5},
        "deepseek": {"correct": 0, "total": 0, "accuracy": 0.5},
        "qwen": {"correct": 0, "total": 0, "accuracy": 0.5},
    }

def save_performance(perf):
    """Simpan performance data ke file JSON"""
    os.makedirs("logs", exist_ok=True)
    with open(PERF_FILE, "w") as f:
        json.dump(perf, f, indent=2)

def update_accuracy(perf):
    """Update akurasi berdasarkan correct/total"""
    for llm in perf:
        total = perf[llm]["total"]
        if total > 0:
            perf[llm]["accuracy"] = perf[llm]["correct"] / total
        else:
            perf[llm]["accuracy"] = 0.5

def get_weights(perf):
    """Menghitung bobot berdasarkan akurasi (normalisasi)"""
    accuracies = {llm: perf[llm]["accuracy"] for llm in perf}
    total_acc = sum(accuracies.values())
    if total_acc == 0:
        # fallback ke bobot sama
        return {llm: 1/len(perf) for llm in perf}
    return {llm: acc / total_acc for llm, acc in accuracies.items()}

def load_predictions():
    if os.path.exists(PRED_FILE):
        with open(PRED_FILE) as f:
            return json.load(f)
    return []

def save_predictions(preds):
    os.makedirs("logs", exist_ok=True)
    with open(PRED_FILE, "w") as f:
        json.dump(preds, f, indent=2)

def add_prediction(asset, timestamp, price, llm, signal, confidence):
    preds = load_predictions()
    preds.append({
        "asset": asset,
        "timestamp": timestamp,
        "price": price,
        "llm": llm,
        "signal": signal,
        "confidence": confidence,
        "evaluated": False
    })
    save_predictions(preds)

def evaluate_predictions(current_prices):
    """Evaluasi prediksi yang belum dievaluasi dengan harga terbaru"""
    preds = load_predictions()
    perf = load_performance()
    new_preds = []
    for p in preds:
        if p.get("evaluated", False):
            new_preds.append(p)
            continue
        asset = p["asset"]
        if asset in current_prices:
            current_price = current_prices[asset]
            entry_price = p["price"]
            change = (current_price - entry_price) / entry_price * 100
            signal = p["signal"]
            correct = False
            if signal == "BUY" and change > 0.5:
                correct = True
            elif signal == "SHORT" and change < -0.5:
                correct = True
            # Jika benar, update performa
            if correct:
                perf[p["llm"]]["correct"] += 1
                perf[p["llm"]]["total"] += 1
            elif signal in ["BUY","SHORT"]:
                # Hanya update total jika sinyal entry (agar tidak dihitung untuk sinyal exit)
                perf[p["llm"]]["total"] += 1
            p["evaluated"] = True
            p["outcome"] = "correct" if correct else "wrong"
            p["actual_change"] = round(change, 2)
        new_preds.append(p)
    save_predictions(new_preds)
    update_accuracy(perf)
    save_performance(perf)
    return perf