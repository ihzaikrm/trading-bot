import json, os, math
from datetime import datetime, timedelta
from typing import Optional

PREDICTIONS_FILE = os.path.join("logs", "predictions.json")
CALIBRATION_FILE = os.path.join("logs", "calibration.json")
N_BINS = 5

def load_predictions(llm=None, days=90):
    if not os.path.exists(PREDICTIONS_FILE): return []
    try:
        with open(PREDICTIONS_FILE) as f: preds = json.load(f)
        cutoff = datetime.utcnow() - timedelta(days=days)
        return [p for p in preds if p.get("outcome") is not None
                and (not llm or p.get("llm") == llm)
                and datetime.fromisoformat(p.get("timestamp","1970-01-01")) >= cutoff]
    except: return []

def brier_score(predictions):
    if not predictions: return 0.25
    return round(sum((p.get("confidence",0.5) - (1.0 if p.get("outcome")=="win" else 0.0))**2
                     for p in predictions) / len(predictions), 4)

def calibration_bins(predictions):
    bins = [{"low":i/N_BINS,"high":(i+1)/N_BINS,"preds":[],"wins":0,"count":0}
            for i in range(N_BINS)]
    for p in predictions:
        conf = p.get("confidence", 0.5)
        idx = min(int(conf * N_BINS), N_BINS - 1)
        bins[idx]["count"] += 1
        bins[idx]["wins"] += 1 if p.get("outcome") == "win" else 0
        bins[idx]["preds"].append(conf)
    return [{"bin": f"{b['low']:.0%}-{b['high']:.0%}",
             "predicted": round(sum(b["preds"])/len(b["preds"]),3),
             "actual_wr": round(b["wins"]/b["count"],3),
             "count": b["count"],
             "error": round(abs(sum(b["preds"])/len(b["preds"]) - b["wins"]/b["count"]),3)}
            for b in bins if b["count"] > 0]

def _load_calibration():
    if not os.path.exists(CALIBRATION_FILE): return {}
    try:
        with open(CALIBRATION_FILE) as f: return json.load(f)
    except: return {}

def _save_calibration(cal):
    os.makedirs("logs", exist_ok=True)
    with open(CALIBRATION_FILE, "w") as f: json.dump(cal, f, indent=2)

def update_calibration_from_outcomes():
    cal = _load_calibration()
    llms = set(p.get("llm") for p in load_predictions() if p.get("llm"))
    for llm in llms:
        preds = load_predictions(llm=llm, days=90)
        if len(preds) < 10: continue
        bins = calibration_bins(preds)
        # Platt scaling: fit a,b dari bin data
        # Simplified: linear regression predicted→actual
        xs = [b["predicted"] for b in bins]
        ys = [b["actual_wr"] for b in bins]
        if len(xs) < 2:
            a, b_coef = 1.0, 0.0
        else:
            n = len(xs)
            mx, my = sum(xs)/n, sum(ys)/n
            denom = sum((x-mx)**2 for x in xs)
            a = sum((xs[i]-mx)*(ys[i]-my) for i in range(n)) / denom if denom else 1.0
            b_coef = my - a * mx
        cal[llm] = {
            "a": round(a, 4), "b": round(b_coef, 4),
            "brier": brier_score(preds),
            "n": len(preds),
            "updated": datetime.utcnow().isoformat()
        }
    _save_calibration(cal)
    return cal

def get_calibrated_confidence(llm, raw_conf, asset=None):
    cal = _load_calibration()
    if llm not in cal: return raw_conf
    a = cal[llm].get("a", 1.0)
    b = cal[llm].get("b", 0.0)
    calibrated = a * raw_conf + b
    return round(max(0.05, min(0.95, calibrated)), 3)

def calibration_summary():
    cal = _load_calibration()
    if not cal: return "Belum ada data kalibrasi (min 10 prediksi per LLM)"
    lines = ["📐 KALIBRASI LLM (90 hari)\n"]
    for llm, data in cal.items():
        brier = data.get("brier", 0.25)
        quality = "🟢 Baik" if brier < 0.15 else "🟡 Sedang" if brier < 0.20 else "🔴 Buruk"
        lines.append(f"{quality} {llm}: Brier={brier:.3f} | n={data.get('n',0)} | "
                     f"slope={data.get('a',1):.2f}")
    return "\n".join(lines)
