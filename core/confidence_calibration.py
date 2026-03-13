"""
core/confidence_calibration.py
Confidence calibration untuk LLM ensemble signals.
Teknik: Platt Scaling + Brier Score monitoring.
"""

import json
import math
import os
import logging
from datetime import datetime, timezone
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

CALIBRATION_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "calibration.json")

DEFAULT_PARAMS = {
    "claude":   {"A": -1.0, "B": 0.0},
    "gemini":   {"A": -1.0, "B": 0.0},
    "gpt":      {"A": -1.0, "B": 0.0},
    "grok":     {"A": -1.0, "B": 0.0},
    "deepseek": {"A": -1.0, "B": 0.0},
    "qwen":     {"A": -1.0, "B": 0.0},
}

MIN_SAMPLES_FOR_CALIBRATION = 30


def _load_calibration():
    try:
        with open(CALIBRATION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_calibration(data):
    os.makedirs(os.path.dirname(CALIBRATION_FILE), exist_ok=True)
    tmp = CALIBRATION_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp, CALIBRATION_FILE)


def _load_predictions():
    pred_file = os.path.join(os.path.dirname(__file__), "..", "logs", "predictions.json")
    try:
        with open(pred_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def brier_score(predictions):
    scored = [p for p in predictions if "outcome" in p and "confidence" in p]
    if not scored:
        return float("nan")
    return sum((p["confidence"] - p["outcome"]) ** 2 for p in scored) / len(scored)


def brier_score_per_llm(predictions):
    grouped = defaultdict(list)
    for p in predictions:
        if "outcome" in p and "confidence" in p and "llm" in p:
            grouped[p["llm"]].append(p)
    return {llm: brier_score(preds) for llm, preds in grouped.items()}


def calibration_bins(predictions, n_bins=10):
    scored = [p for p in predictions if "outcome" in p and "confidence" in p]
    bins = [[] for _ in range(n_bins)]
    for p in scored:
        idx = min(int(p["confidence"] * n_bins), n_bins - 1)
        bins[idx].append(p)
    result = []
    for i, bucket in enumerate(bins):
        if not bucket:
            continue
        mean_conf = sum(p["confidence"] for p in bucket) / len(bucket)
        accuracy  = sum(p["outcome"] for p in bucket) / len(bucket)
        result.append({"bin_mid": (i+0.5)/n_bins, "mean_conf": round(mean_conf,4),
                        "accuracy": round(accuracy,4), "count": len(bucket)})
    return result


def _sigmoid(x):
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def platt_scaling(confidence, llm, calib_data=None):
    if calib_data is None:
        calib_data = _load_calibration()
    params = calib_data.get("platt_params", {}).get(llm, DEFAULT_PARAMS.get(llm, {"A": -1.0, "B": 0.0}))
    A, B = params["A"], params["B"]
    eps = 1e-6
    f_clamp = max(eps, min(1.0 - eps, confidence))
    logit_f = math.log(f_clamp / (1.0 - f_clamp))
    return round(_sigmoid(A * logit_f + B), 4)


def _fit_platt_params(predictions):
    scored = [p for p in predictions if "outcome" in p and "confidence" in p]
    if len(scored) < MIN_SAMPLES_FOR_CALIBRATION:
        return -1.0, 0.0
    eps = 1e-6
    A, B = -1.0, 0.0
    lr = 0.01
    for _ in range(500):
        dA = dB = 0.0
        for p in scored:
            f_clamp = max(eps, min(1.0 - eps, p["confidence"]))
            logit_f = math.log(f_clamp / (1.0 - f_clamp))
            pred_prob = _sigmoid(A * logit_f + B)
            err = pred_prob - p["outcome"]
            dA += err * logit_f
            dB += err
        n = len(scored)
        A -= lr * dA / n
        B -= lr * dB / n
    return round(A, 4), round(B, 4)


def get_calibrated_confidence(llm, raw_conf, asset, calib_data=None):
    if calib_data is None:
        calib_data = _load_calibration()
    sample_counts = calib_data.get("sample_counts", {})
    n_samples = sample_counts.get(f"{llm}:{asset}", 0)
    if n_samples < MIN_SAMPLES_FOR_CALIBRATION:
        return round(raw_conf, 4)
    return platt_scaling(raw_conf, llm, calib_data)


def update_calibration_from_outcomes():
    all_preds = _load_predictions()
    calib_data = _load_calibration()
    by_llm = defaultdict(list)
    for p in all_preds:
        if "outcome" in p and "confidence" in p and "llm" in p:
            by_llm[p["llm"]].append(p)
    sample_counts = defaultdict(int)
    for p in all_preds:
        if "outcome" in p and "llm" in p and "asset" in p:
            sample_counts[f"{p['llm']}:{p['asset']}"] += 1
    platt_params = {}
    brier_scores = {}
    fit_summary = []
    for llm, preds in by_llm.items():
        n = len(preds)
        bs = brier_score(preds)
        brier_scores[llm] = round(bs, 4) if not math.isnan(bs) else None
        if n >= MIN_SAMPLES_FOR_CALIBRATION:
            A, B = _fit_platt_params(preds)
            platt_params[llm] = {"A": A, "B": B, "n_samples": n}
            fit_summary.append(f"{llm}: A={A}, B={B} (n={n}, BS={bs:.3f})")
        else:
            platt_params[llm] = {**DEFAULT_PARAMS.get(llm, {"A":-1.0,"B":0.0}), "n_samples": n}
            fit_summary.append(f"{llm}: default (n={n} < {MIN_SAMPLES_FOR_CALIBRATION})")
    calib_data.update({
        "platt_params": platt_params, "brier_scores": brier_scores,
        "sample_counts": dict(sample_counts),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_outcomes": len([p for p in all_preds if "outcome" in p]),
    })
    _save_calibration(calib_data)
    logger.info("Calibration updated: %s", "; ".join(fit_summary))
    return {"platt_params": platt_params, "brier_scores": brier_scores, "fit_summary": fit_summary}


def calibration_summary():
    calib_data = _load_calibration()
    platt_params = calib_data.get("platt_params", {})
    brier_scores = calib_data.get("brier_scores", {})
    sample_counts_raw = calib_data.get("sample_counts", {})
    last_updated = calib_data.get("last_updated", "N/A")
    llm_totals = defaultdict(int)
    for key, n in sample_counts_raw.items():
        llm_totals[key.split(":")[0]] += n
    all_llms = sorted(set(list(DEFAULT_PARAMS.keys()) + list(platt_params.keys())))
    lines = ["*LLM Calibration Summary*"]
    for llm in all_llms:
        bs = brier_scores.get(llm)
        n = llm_totals.get(llm, 0)
        params = platt_params.get(llm, DEFAULT_PARAMS.get(llm, {}))
        A = params.get("A", -1.0)
        B = params.get("B", 0.0)
        bs_str = f"BS={bs:.3f}" if bs is not None else "BS=N/A"
        prefix = "OK" if (bs is not None and bs <= 0.22 and n >= MIN_SAMPLES_FOR_CALIBRATION) else "WARN"
        lines.append(f"[{prefix}] {llm}: {bs_str} | n={n} | A={A:+.2f} B={B:+.2f}")
    lines.append(f"Update terakhir: {last_updated[:19].replace('T',' ')} UTC")
    return "\n".join(lines)


def log_prediction(llm, asset, signal, confidence, price_at_signal):
    pred_file = os.path.join(os.path.dirname(__file__), "..", "logs", "predictions.json")
    try:
        with open(pred_file, "r", encoding="utf-8") as f:
            preds = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        preds = []
    preds.append({
        "id": f"{llm}_{asset}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}",
        "llm": llm, "asset": asset, "signal": signal,
        "confidence": round(confidence, 4), "price_at_signal": price_at_signal,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(preds) > 10_000:
        preds = preds[-10_000:]
    os.makedirs(os.path.dirname(pred_file), exist_ok=True)
    with open(pred_file, "w", encoding="utf-8") as f:
        json.dump(preds, f, indent=2, default=str)


def fill_outcome(prediction_id, outcome):
    pred_file = os.path.join(os.path.dirname(__file__), "..", "logs", "predictions.json")
    try:
        with open(pred_file, "r", encoding="utf-8") as f:
            preds = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    found = False
    for p in preds:
        if p.get("id") == prediction_id and "outcome" not in p:
            p["outcome"] = outcome
            p["outcome_time"] = datetime.now(timezone.utc).isoformat()
            found = True
            break
    if found:
        with open(pred_file, "w", encoding="utf-8") as f:
            json.dump(preds, f, indent=2, default=str)
    return found


if __name__ == "__main__":
    import sys
    if "--update" in sys.argv:
        result = update_calibration_from_outcomes()
        for line in result["fit_summary"]:
            print(" ", line)
    elif "--summary" in sys.argv:
        print(calibration_summary())
    elif "--brier" in sys.argv:
        scores = brier_score_per_llm(_load_predictions())
        for llm, bs in sorted(scores.items(), key=lambda x: x[1]):
            print(f"  {llm:<12}: {bs:.4f}")
