import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.momentum_filter import get_momentum_signal
from modules.dxy_filter import get_dxy_signal

def test_momentum_filter_returns_tuple():
    """Test that momentum filter returns (signal, details)."""
    sig, det = get_momentum_signal("BTC")
    assert sig in ["BULLISH", "BEARISH", "NEUTRAL"]
    assert isinstance(det, dict)

def test_dxy_filter_returns_tuple():
    """Test that DXY filter returns (signal, details)."""
    sig, det = get_dxy_signal()
    assert sig in ["BULLISH", "BEARISH", "NEUTRAL"]
    assert isinstance(det, dict)

if __name__ == "__main__":
    pytest.main([__file__])
