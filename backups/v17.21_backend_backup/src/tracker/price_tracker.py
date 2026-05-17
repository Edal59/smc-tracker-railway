"""
SMC Performance Tracker — Price Tracker
Background price monitoring for active signals.
Calculates MFE/MAE and detects TP/SL hits.
"""
import time
import logging
import threading
import requests
from datetime import datetime, timezone

from src.config import config
from src.database import (
    get_active_signals, update_signal, insert_price_tick,
    insert_event, get_pip_size, cleanup_price_ticks
)

logger = logging.getLogger(__name__)


class PriceProvider:
    """Base class for price data providers."""
    def get_price(self, pair: str) -> float:
        raise NotImplementedError


class MockPriceProvider(PriceProvider):
    """Mock provider for testing — returns entry price (no movement)."""
    def __init__(self):
        self._prices = {}

    def set_price(self, pair: str, price: float):
        self._prices[pair] = price

    def get_price(self, pair: str) -> float:
        return self._prices.get(pair, 0.0)


class TwelveDataProvider(PriceProvider):
    """Twelve Data API price provider."""
    BASE_URL = "https://api.twelvedata.com/price"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._cache = {}  # pair -> (price, timestamp)
        self._cache_ttl = 10  # seconds

    def get_price(self, pair: str) -> float:
        # Check cache
        cached = self._cache.get(pair)
        if cached:
            price, ts = cached
            if time.time() - ts < self._cache_ttl:
                return price

        try:
            # Convert pair format: EURUSD -> EUR/USD
            symbol = f"{pair[:3]}/{pair[3:]}"
            resp = requests.get(self.BASE_URL, params={
                'symbol': symbol, 'apikey': self.api_key
            }, timeout=5)
            data = resp.json()
            price = float(data.get('price', 0))
            if price > 0:
                self._cache[pair] = (price, time.time())
                return price
        except Exception as e:
            logger.error(f"TwelveData API error for {pair}: {e}")

        # Return cached if available
        if cached:
            return cached[0]
        return 0.0


class AlphaVantageProvider(PriceProvider):
    """Alpha Vantage API price provider."""
    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._cache = {}
        self._cache_ttl = 15

    def get_price(self, pair: str) -> float:
        cached = self._cache.get(pair)
        if cached and time.time() - cached[1] < self._cache_ttl:
            return cached[0]
        try:
            from_cur = pair[:3]
            to_cur = pair[3:]
            resp = requests.get(self.BASE_URL, params={
                'function': 'CURRENCY_EXCHANGE_RATE',
                'from_currency': from_cur,
                'to_currency': to_cur,
                'apikey': self.api_key,
            }, timeout=5)
            data = resp.json()
            rate_data = data.get('Realtime Currency Exchange Rate', {})
            price = float(rate_data.get('5. Exchange Rate', 0))
            if price > 0:
                self._cache[pair] = (price, time.time())
                return price
        except Exception as e:
            logger.error(f"AlphaVantage API error for {pair}: {e}")
        if cached:
            return cached[0]
        return 0.0


def create_price_provider() -> PriceProvider:
    """Create price provider based on configuration."""
    provider_name = config.get('price_tracker', 'provider', default='mock')
    api_key = config.get('price_tracker', 'api_key', default='')

    if provider_name == 'twelve_data' and api_key:
        logger.info("Using TwelveData price provider")
        return TwelveDataProvider(api_key)
    elif provider_name == 'alpha_vantage' and api_key:
        logger.info("Using AlphaVantage price provider")
        return AlphaVantageProvider(api_key)
    else:
        logger.info("Using Mock price provider")
        return MockPriceProvider()


class PriceTracker:
    """Background price tracker for active signals."""

    def __init__(self, provider: PriceProvider = None):
        self.provider = provider or create_price_provider()
        self.poll_interval = config.price_poll_interval
        self.timeout_minutes = config.timeout_minutes
        self._running = False
        self._thread = None

    def start(self):
        """Start background tracking thread."""
        if not config.price_tracker_enabled:
            logger.info("Price tracker disabled in config")
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="PriceTracker")
        self._thread.start()
        logger.info(f"Price tracker started (interval={self.poll_interval}s)")

    def stop(self):
        """Stop the tracking thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Price tracker stopped")

    def _run_loop(self):
        """Main tracking loop."""
        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.error(f"Price tracker error: {e}", exc_info=True)
            time.sleep(self.poll_interval)

    def _tick(self):
        """Single tracking cycle — check all active signals."""
        active = get_active_signals()
        if not active:
            return

        # Collect unique pairs to minimize API calls
        pairs = set(s['pair'] for s in active)
        prices = {}
        for pair in pairs:
            price = self.provider.get_price(pair)
            if price > 0:
                prices[pair] = price

        for signal in active:
            pair = signal['pair']
            current_price = prices.get(pair)
            if not current_price:
                continue
            self._process_signal_tick(signal, current_price)

    def _process_signal_tick(self, signal: dict, current_price: float):
        """Process a price tick for a single signal."""
        signal_id = signal['signal_id']
        pair = signal['pair']
        direction = signal['direction']
        entry_price = signal['entry_price']
        stop_loss = signal['stop_loss']
        take_profit = signal['take_profit']
        pip_size = get_pip_size(pair)

        updates = {}
        is_mfe = False
        is_mae = False

        # Calculate current pips from entry
        if direction == 'LONG':
            current_pips = (current_price - entry_price) / pip_size
        else:
            current_pips = (entry_price - current_price) / pip_size

        sl_dist_pips = abs(entry_price - stop_loss) / pip_size
        current_rr = current_pips / sl_dist_pips if sl_dist_pips > 0 else 0

        # MFE check
        favorable_pips = max(current_pips, 0)
        current_mfe = signal.get('mfe_pips') or 0
        if favorable_pips > current_mfe:
            updates['mfe_pips'] = round(favorable_pips, 1)
            updates['mfe_price'] = current_price
            updates['mfe_rr'] = round(favorable_pips / sl_dist_pips, 2) if sl_dist_pips > 0 else 0
            is_mfe = True

        # MAE check
        adverse_pips = max(-current_pips, 0)
        current_mae = signal.get('mae_pips') or 0
        if adverse_pips > current_mae:
            updates['mae_pips'] = round(adverse_pips, 1)
            updates['mae_price'] = current_price
            updates['mae_rr'] = round(adverse_pips / sl_dist_pips, 2) if sl_dist_pips > 0 else 0
            is_mae = True

        # TP hit check
        tp_hit = False
        if direction == 'LONG' and current_price >= take_profit:
            tp_hit = True
        elif direction == 'SHORT' and current_price <= take_profit:
            tp_hit = True

        # SL hit check
        sl_hit = False
        if direction == 'LONG' and current_price <= stop_loss:
            sl_hit = True
        elif direction == 'SHORT' and current_price >= stop_loss:
            sl_hit = True

        # Timeout check
        timed_out = False
        if signal.get('signal_timestamp'):
            try:
                sig_time = datetime.fromisoformat(signal['signal_timestamp'].replace('Z', '+00:00'))
                elapsed = (datetime.now(timezone.utc) - sig_time).total_seconds() / 60
                if elapsed >= self.timeout_minutes:
                    timed_out = True
            except Exception:
                pass

        # Resolve outcome
        now_ts = datetime.now(timezone.utc).isoformat()
        if tp_hit:
            tp_pips = signal.get('tp_distance_pips') or abs(take_profit - entry_price) / pip_size
            updates.update({
                'status': 'WON',
                'outcome_timestamp': now_ts,
                'outcome_price': current_price,
                'pips_gained': round(tp_pips, 1),
                'actual_rr': round(signal.get('target_rr', 3.0), 2),
            })
            self._resolve_signal(signal_id, updates, 'TP_HIT', current_price)
            return
        elif sl_hit:
            updates.update({
                'status': 'LOST',
                'outcome_timestamp': now_ts,
                'outcome_price': current_price,
                'pips_gained': round(-sl_dist_pips, 1),
                'actual_rr': -1.0,
            })
            self._resolve_signal(signal_id, updates, 'SL_HIT', current_price)
            return
        elif timed_out:
            updates.update({
                'status': 'TIMEOUT',
                'outcome_timestamp': now_ts,
                'outcome_price': current_price,
                'pips_gained': round(current_pips, 1),
                'actual_rr': round(current_rr, 2),
            })
            self._resolve_signal(signal_id, updates, 'TIMEOUT', current_price)
            return

        # Just update MFE/MAE if changed
        if updates:
            update_signal(signal_id, updates)

        # Store price tick
        insert_price_tick(signal_id, pair, current_price, is_mfe=is_mfe, is_mae=is_mae)

    def _resolve_signal(self, signal_id: str, updates: dict, event_type: str, price: float):
        """Resolve a signal and clean up."""
        update_signal(signal_id, updates)
        insert_event(signal_id, event_type,
                     event_data={'outcome': updates.get('status'), 'price': price},
                     price_at_event=price)
        cleanup_price_ticks(signal_id)
        logger.info(f"Signal {signal_id} resolved: {event_type} @ {price}")
