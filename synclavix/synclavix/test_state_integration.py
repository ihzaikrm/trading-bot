import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

from state.state_manager import StateManager
from modules.momentum_filter import get_momentum_signal
from modules.dxy_filter import get_dxy_signal
from utils.logger import setup_logger

logger = setup_logger("test_state_integration")

async def test_momentum_state():
    """Simulate running momentum filter and saving state."""
    sm = StateManager(data_dir="data")
    state = sm.load_state()
    logger.info(f"Current state: {state['current_state']}")

    # Simulate data
    symbol = "BTC"
    mom_sig, mom_det = get_momentum_signal(symbol)
    dxy_sig, dxy_det = get_dxy_signal()

    logger.info(f"Momentum: {mom_sig} | DXY: {dxy_sig}")
    # Save checkpoint
    checkpoint_data = {
        "momentum": {"signal": mom_sig, "details": mom_det},
        "dxy": {"signal": dxy_sig, "details": dxy_det}
    }
    sm.save_checkpoint("ANALYZE", checkpoint_data)
    logger.info("Checkpoint saved")

if __name__ == "__main__":
    asyncio.run(test_momentum_state())
