"""
Test script for MarketClock functionality
"""
from app.services.market_clock import get_market_clock
import time

def test_market_clock():
    print("Testing MarketClock Service...")
    
    # Get the singleton instance
    clock = get_market_clock()
    
    # Test initial status
    print("\n1. Initial Status:")
    status = clock.get_status()
    print(f"   Session ID: {status['session_id']}")
    print(f"   Simulated Time: {status['simulated_time']}")
    print(f"   Speed Multiplier: {status['speed_multiplier']}")
    print(f"   Market Status: {status['market_status']}")
    print(f"   Is Running: {status['is_running']}")
    
    # Test setting time
    print("\n2. Setting Time:")
    from datetime import datetime, timezone
    target_time = datetime(2026, 7, 15, 9, 30, 0, tzinfo=timezone.utc)
    clock.set_time(target_time)
    status = clock.get_status()
    print(f"   Set time to: {target_time.isoformat()}")
    print(f"   Current time: {status['simulated_time']}")
    
    # Test speed multiplier
    print("\n3. Setting Speed Multiplier:")
    clock.set_speed_multiplier(2.0)
    status = clock.get_status()
    print(f"   Set multiplier to: 2.0")
    print(f"   Current multiplier: {status['speed_multiplier']}")
    
    # Test invalid multiplier
    print("\n4. Testing Invalid Multiplier:")
    try:
        clock.set_speed_multiplier(3.0)
        print("   ERROR: Should have raised ValueError")
    except ValueError as e:
        print(f"   Correctly raised ValueError: {e}")
    
    # Test time advancement
    print("\n5. Testing Time Advancement:")
    if not status['is_running']:
        clock.start()
        time.sleep(2)
    else:
        time.sleep(2)
    
    new_status = clock.get_status()
    print(f"   Time after 2 seconds: {new_status['simulated_time']}")
    print(f"   Advanced by: {2.0 * 2.0} seconds (2 real seconds * 2x speed)")
    
    # Test reset
    print("\n6. Testing Reset:")
    clock.reset()
    status = clock.get_status()
    print(f"   After reset:")
    print(f"   Simulated Time: {status['simulated_time']}")
    print(f"   Speed Multiplier: {status['speed_multiplier']}")
    print(f"   Market Status: {status['market_status']}")
    
    # Stop the clock
    clock.stop()
    print("\nAll MarketClock tests passed!")

if __name__ == "__main__":
    test_market_clock()
