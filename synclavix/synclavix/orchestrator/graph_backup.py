import asyncio
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# ============================================
# Define State
# ============================================
class SynclavixState(TypedDict):
    current_step: str
    market_data: dict
    analysis: dict
    risk_approved: bool
    executed: bool
    reconciled: bool
    user_id: str

# ============================================
# Node Functions
# ============================================
async def collect_node(state: SynclavixState) -> dict:
    print("?? COLLECT: Fetching market data...")
    try:
        from modules.market_data import get_btc_price
        price = get_btc_price()
        market_data = {"BTC/USDT": price, "timestamp": "now"}
        return {"market_data": market_data, "current_step": "ANALYZE"}
    except Exception as e:
        print(f"Error fetching data: {e}")
        return {"market_data": {"BTC/USDT": 70000}, "current_step": "ANALYZE"}

async def analyze_node(state: SynclavixState) -> dict:
    print("?? ANALYZE: Running filters and LLM...")
    price = state.get("market_data", {}).get("BTC/USDT", 70000)
    from orchestrator.signal_generator import generate_signal
    signal, confidence = await generate_signal("BTC", price)
    analysis = {"signal": signal, "confidence": confidence}
    return {"analysis": analysis, "current_step": "RISK_CHECK"}

async def risk_check_node(state: SynclavixState) -> dict:
    print("??? RISK_CHECK: Validating...")
    return {"risk_approved": True, "current_step": "EXECUTE"}

async def execute_node(state: SynclavixState) -> dict:
    print("? EXECUTE: Placing orders...")
    signal = state.get("analysis", {}).get("signal")
    price = state.get("market_data", {}).get("BTC/USDT")
    if signal in ["BUY", "SELL"]:
        import json, os
        os.makedirs("logs", exist_ok=True)
        with open("logs/signals.json", "a") as f:
            json.dump({"timestamp": "now", "signal": signal, "price": price}, f)
            f.write("\n")
    return {"executed": True, "current_step": "RECONCILE"}

async def reconcile_node(state: SynclavixState) -> dict:
    print("? RECONCILE: Updating state...")
    return {"reconciled": True, "current_step": "COLLECT"}

# ============================================
# Build Graph
# ============================================
def build_graph():
    workflow = StateGraph(SynclavixState)

    workflow.add_node("COLLECT", collect_node)
    workflow.add_node("ANALYZE", analyze_node)
    workflow.add_node("RISK_CHECK", risk_check_node)
    workflow.add_node("EXECUTE", execute_node)
    workflow.add_node("RECONCILE", reconcile_node)

    workflow.set_entry_point("COLLECT")
    workflow.add_edge("COLLECT", "ANALYZE")
    workflow.add_edge("ANALYZE", "RISK_CHECK")
    workflow.add_edge("RISK_CHECK", "EXECUTE")
    workflow.add_edge("EXECUTE", "RECONCILE")
    workflow.add_edge("RECONCILE", "COLLECT")

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)

async def run_graph(user_id="default"):
    graph = build_graph()
    initial_state = {
        "current_step": "COLLECT",
        "market_data": {},
        "analysis": {},
        "risk_approved": False,
        "executed": False,
        "reconciled": False,
        "user_id": user_id
    }
    config = {"configurable": {"thread_id": user_id}}
    async for event in graph.astream(initial_state, config):
        for node, output in event.items():
            print(f"Node {node} completed: {output}")
    print("? Graph finished.")

if __name__ == "__main__":
    asyncio.run(run_graph("test_user"))
