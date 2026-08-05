"""
Global MarketClock Service - Single source of truth for all time-based operations.

This service maintains the simulated timestamp and session state, and provides
the canonical time source for all trading logic, feed simulation, portfolio calculations,
and WebSocket updates. No component should use system clock for trading logic.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import threading
import time
import uuid
from app.core.config import settings


class MarketClock:
    """
    Global MarketClock service that maintains simulated time and session state.
    
    This is the single source of truth for all time-based operations in the platform.
    All components should use MarketClock.now() instead of system time.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Session state
        self._session_id = str(uuid.uuid4())
        self._start_timestamp = self._get_feed_start_timestamp()
        self._current_timestamp = self._start_timestamp
        self._speed_multiplier = 1.0
        self._market_status = "open"  # pre-market, open, closed
        self._last_real_time = time.time()
        self._is_running = False
        
        # Thread for time advancement
        self._clock_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def _get_feed_start_timestamp(self) -> datetime:
        """
        Get the start timestamp from the feed dataset.
        This is the first minute-bar timestamp in the dataset (Jun 30 2026 09:30 UTC).
        """
        # Default start time - this should be the first timestamp in the minute data
        return datetime(2026, 6, 30, 9, 30, 0, tzinfo=timezone.utc)
    
    def now(self) -> datetime:
        """
        Get the current simulated timestamp.
        This is the canonical time source for all trading logic.
        """
        with self._lock:
            return self._current_timestamp
    
    def set_time(self, target_time: datetime) -> None:
        """
        Set the simulated time to a specific datetime.
        Admin-only operation.
        
        Args:
            target_time: The datetime to set (must be timezone-aware)
        """
        with self._lock:
            if target_time.tzinfo is None:
                target_time = target_time.replace(tzinfo=timezone.utc)
            self._current_timestamp = target_time
            self._last_real_time = time.time()
    
    def set_speed_multiplier(self, multiplier: float) -> None:
        """
        Set the speed multiplier for time advancement.
        Admin-only operation.
        
        Args:
            multiplier: Speed multiplier (1, 2, 5, 12, or 30)
        """
        valid_multipliers = [1.0, 2.0, 5.0, 12.0, 30.0]
        if multiplier not in valid_multipliers:
            raise ValueError(f"Invalid speed multiplier. Must be one of: {valid_multipliers}")
        
        with self._lock:
            self._speed_multiplier = multiplier
    
    def reset(self) -> None:
        """
        Reset the session to the start of the dataset.
        Admin-only operation.
        """
        with self._lock:
            self._current_timestamp = self._start_timestamp
            self._speed_multiplier = 1.0
            self._market_status = "open"
            self._last_real_time = time.time()
            self._session_id = str(uuid.uuid4())
    
    def get_status(self) -> Dict:
        """
        Get the current session status.
        
        Returns:
            Dict with session information
        """
        with self._lock:
            return {
                "session_id": self._session_id,
                "simulated_time": self._current_timestamp.isoformat(),
                "speed_multiplier": self._speed_multiplier,
                "market_status": self._market_status,
                "start_timestamp": self._start_timestamp.isoformat(),
                "is_running": self._is_running
            }
    
    def start(self) -> None:
        """
        Start the MarketClock time advancement thread.
        """
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._stop_event.clear()
        
        def clock_loop():
            while not self._stop_event.is_set():
                with self._lock:
                    if not self._is_running:
                        break
                    
                    # Calculate time elapsed in real time
                    current_real_time = time.time()
                    real_elapsed = current_real_time - self._last_real_time
                    self._last_real_time = current_real_time
                    
                    # Advance simulated time by speed multiplier
                    sim_elapsed = real_elapsed * self._speed_multiplier
                    self._current_timestamp = self._current_timestamp + timedelta(seconds=sim_elapsed)
                
                # Update market status based on time of day
                self._update_market_status()
                
                # Sleep for a short interval to prevent tight loop
                time.sleep(0.1)
        
        self._clock_thread = threading.Thread(target=clock_loop, daemon=True)
        self._clock_thread.start()
    
    def stop(self) -> None:
        """
        Stop the MarketClock time advancement thread.
        """
        with self._lock:
            self._is_running = False
            self._stop_event.set()
        
        if self._clock_thread:
            self._clock_thread.join(timeout=1.0)
    
    def _update_market_status(self) -> None:
        """
        Update market status based on current simulated time.
        Simple implementation: 9:30-16:00 is open, otherwise closed.
        """
        hour = self._current_timestamp.hour
        minute = self._current_timestamp.minute
        
        # Simple market hours: 9:30 AM to 4:00 PM UTC
        if 9 < hour < 16 or (hour == 9 and minute >= 30) or (hour == 16 and minute == 0):
            self._market_status = "open"
        else:
            self._market_status = "closed"


# Global instance
_market_clock: Optional[MarketClock] = None


def get_market_clock() -> MarketClock:
    """
    Get the global MarketClock instance.
    Creates it if it doesn't exist.
    """
    global _market_clock
    if _market_clock is None:
        _market_clock = MarketClock()
    return _market_clock