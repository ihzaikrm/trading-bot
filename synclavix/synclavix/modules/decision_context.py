import json
import os
from datetime import datetime

CONTEXT_FILE = "logs/decision_context.json"

def load_context():
    if os.path.exists(CONTEXT_FILE):
        with open(CONTEXT_FILE, 'r') as f:
            return json.load(f)
    return {"trades": []}

def save_context(context):
    with open(CONTEXT_FILE, 'w') as f:
        json.dump(context, f, indent=2)

def record_entry(asset, price, qty, amount, context_data):
    ctx = load_context()
    ctx["trades"].append({
        "type": "entry",
        "asset": asset,
        "price": price,
        "qty": qty,
        "amount": amount,
        "timestamp": datetime.now().isoformat(),
        "context": context_data
    })
    save_context(ctx)

def record_exit(asset, entry_price, exit_price, pnl, context_data=None):
    ctx = load_context()
    ctx["trades"].append({
        "type": "exit",
        "asset": asset,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "pnl": pnl,
        "timestamp": datetime.now().isoformat(),
        "context": context_data or {}
    })
    save_context(ctx)
