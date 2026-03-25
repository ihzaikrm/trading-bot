import ccxt
import asyncio
import time
from typing import Dict, List, Tuple, Optional

class OrderFlowAnalyzer:
    """
    Real-time order flow analyzer using CCXT exchange API.
    Provides order book imbalance, liquidity levels, and cumulative delta metrics.
    """
    
    def __init__(self, symbol: str = "BTC/USDT", depth: int = 10, exchange_id: str = "gate"):
        self.symbol = symbol
        self.depth = depth
        self.exchange_id = exchange_id
        self.bids: Dict[float, float] = {}
        self.asks: Dict[float, float] = {}
        self.imbalance = 0.0
        self.bid_volume = 0.0
        self.ask_volume = 0.0
        self.last_update = 0
        self.cache_ttl = 5  # seconds
        self._exchange = None
        
    def _get_exchange(self):
        """Lazy initialization of CCXT exchange."""
        if self._exchange is None:
            exchange_class = getattr(ccxt, self.exchange_id)
            self._exchange = exchange_class({
                'enableRateLimit': True,
                'timeout': 10000,
            })
        return self._exchange
    
    async def fetch_orderbook(self, force_refresh: bool = False) -> float:
        """
        Fetch real order book from exchange and compute imbalance.
        Returns imbalance ratio (-1 to 1) where positive indicates buying pressure.
        """
        current_time = time.time()
        
        # Use cached data if still valid
        if not force_refresh and current_time - self.last_update < self.cache_ttl:
            return self.imbalance
        
        try:
            exchange = self._get_exchange()
            loop = asyncio.get_event_loop()
            
            # Fetch order book with specified depth
            orderbook = await loop.run_in_executor(
                None, 
                lambda: exchange.fetch_order_book(self.symbol, self.depth)
            )
            
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])
            
            # Convert to dict for easy access
            self.bids = {price: amount for price, amount in bids}
            self.asks = {price: amount for price, amount in asks}
            
            # Calculate volume-weighted imbalance
            self.bid_volume = sum(price * amount for price, amount in bids[:self.depth])
            self.ask_volume = sum(price * amount for price, amount in asks[:self.depth])
            total_volume = self.bid_volume + self.ask_volume
            
            if total_volume > 0:
                self.imbalance = (self.bid_volume - self.ask_volume) / total_volume
            else:
                self.imbalance = 0.0
            
            self.last_update = current_time
            return self.imbalance
            
        except Exception as e:
            print(f"OrderFlowAnalyzer error fetching order book for {self.symbol}: {e}")
            # Return cached imbalance if available, else 0
            return self.imbalance if self.last_update > 0 else 0.0
    
    async def get_liquidity_levels(self, threshold: float = 1000.0) -> List[Tuple[str, float, float]]:
        """
        Identify significant liquidity levels in the order book.
        Returns list of (side, price, amount) where amount * price > threshold.
        """
        try:
            await self.fetch_orderbook()
            levels = []
            
            # Check bids
            for price, amount in self.bids.items():
                if price * amount > threshold:
                    levels.append(('bid', price, amount))
            
            # Check asks
            for price, amount in self.asks.items():
                if price * amount > threshold:
                    levels.append(('ask', price, amount))
            
            # Sort by amount (largest first)
            return sorted(levels, key=lambda x: x[2], reverse=True)[:10]
            
        except Exception as e:
            print(f"OrderFlowAnalyzer error getting liquidity levels: {e}")
            return []
    
    async def get_cumulative_delta(self, lookback_trades: int = 100) -> Dict[str, float]:
        """
        Calculate cumulative delta (buy volume - sell volume) from recent trades.
        Returns dict with delta metrics.
        """
        try:
            exchange = self._get_exchange()
            loop = asyncio.get_event_loop()
            
            # Fetch recent trades
            trades = await loop.run_in_executor(
                None,
                lambda: exchange.fetch_trades(self.symbol, limit=lookback_trades)
            )
            
            buy_volume = 0.0
            sell_volume = 0.0
            trade_count = len(trades)
            
            for trade in trades:
                price = trade['price']
                amount = trade['amount']
                side = trade['side'] if 'side' in trade else None
                
                # If side not available, infer from tick direction (some exchanges)
                if side == 'buy':
                    buy_volume += price * amount
                elif side == 'sell':
                    sell_volume += price * amount
                else:
                    # Assume unknown side - skip or infer from price movement
                    pass
            
            total_volume = buy_volume + sell_volume
            delta = buy_volume - sell_volume
            
            return {
                'buy_volume': buy_volume,
                'sell_volume': sell_volume,
                'total_volume': total_volume,
                'delta': delta,
                'delta_ratio': delta / total_volume if total_volume > 0 else 0.0,
                'trade_count': trade_count,
                'buy_ratio': buy_volume / total_volume if total_volume > 0 else 0.0,
            }
            
        except Exception as e:
            print(f"OrderFlowAnalyzer error getting cumulative delta: {e}")
            return {
                'buy_volume': 0.0,
                'sell_volume': 0.0,
                'total_volume': 0.0,
                'delta': 0.0,
                'delta_ratio': 0.0,
                'trade_count': 0,
                'buy_ratio': 0.0,
            }
    
    async def get_orderflow_summary(self) -> Dict:
        """
        Generate comprehensive order flow summary including all metrics.
        """
        imbalance = await self.fetch_orderbook()
        liquidity_levels = await self.get_liquidity_levels()
        delta_metrics = await self.get_cumulative_delta()
        
        return {
            'symbol': self.symbol,
            'imbalance': imbalance,
            'bid_volume': self.bid_volume,
            'ask_volume': self.ask_volume,
            'bid_ask_ratio': self.bid_volume / self.ask_volume if self.ask_volume > 0 else float('inf'),
            'liquidity_levels': liquidity_levels,
            'cumulative_delta': delta_metrics,
            'timestamp': self.last_update,
        }
    
    async def get_confidence_modifier(self, summary: Optional[Dict] = None) -> float:
        """
        Calculate a confidence multiplier based on order flow metrics.
        Returns a value between 0.7 and 1.3 where:
        - >1.0 increases confidence (strong buying pressure)
        - <1.0 decreases confidence (strong selling pressure)
        """
        if summary is None:
            summary = await self.get_orderflow_summary()
        
        imbalance = summary['imbalance']
        delta_ratio = summary['cumulative_delta']['delta_ratio']
        
        # Combine signals with weights
        modifier = 1.0 + (imbalance * 0.3) + (delta_ratio * 0.2)
        
        # Clamp between 0.7 and 1.3
        return max(0.7, min(1.3, modifier))
    
    def get_orderflow_text(self, summary: Optional[Dict] = None) -> str:
        """
        Format order flow summary as text for LLM prompt.
        """
        if summary is None:
            # Generate a placeholder text if no data
            return "ORDER FLOW: data tidak tersedia"
        
        lines = [
            "ORDER FLOW ANALISIS:",
            f"  Imbalance: {summary['imbalance']:.3f} (positif = tekanan beli)",
            f"  Volume Bid: ${summary['bid_volume']:.2f}",
            f"  Volume Ask: ${summary['ask_volume']:.2f}",
            f"  Ratio Bid/Ask: {summary['bid_ask_ratio']:.2f}",
        ]
        
        # Add cumulative delta info
        delta = summary['cumulative_delta']
        lines.extend([
            "  CUMULATIVE DELTA (100 trades terakhir):",
            f"    Delta: ${delta['delta']:.2f} (ratio: {delta['delta_ratio']:.3f})",
            f"    Buy volume: ${delta['buy_volume']:.2f}",
            f"    Sell volume: ${delta['sell_volume']:.2f}",
            f"    Buy ratio: {delta['buy_ratio']:.3f}",
        ])
        
        # Add top liquidity levels
        liquidity = summary['liquidity_levels'][:3]
        if liquidity:
            lines.append("  LIQUIDITY LEVELS SIGNIFIKAN:")
            for side, price, amount in liquidity:
                lines.append(f"    {side.upper()} @ ${price:.2f}: {amount:.4f} (${price * amount:.2f})")
        
        return "\n".join(lines)