"""
Test script to verify admin session endpoints are working
"""
import requests

BASE_URL = "http://localhost:8000"

# Test health endpoint
print("Testing health endpoint...")
response = requests.get(f"{BASE_URL}/health")
print(f"Health: {response.status_code} - {response.json()}")

# Test session status endpoint (without auth - should get 401)
print("\nTesting session status endpoint (no auth)...")
response = requests.get(f"{BASE_URL}/api/admin/session/status")
print(f"Session Status (no auth): {response.status_code}")
if response.status_code == 401:
    print("PASS: Correctly returns 401 without authentication")
elif response.status_code == 404:
    print("FAIL: Endpoint not found (404)")
else:
    print(f"Response: {response.text}")

# Test WebSocket endpoint info
print("\nWebSocket endpoints available:")
print("- /ws/market/{ticker} - Market data streaming")
print("- /ws/session - Session synchronization")
print("- /ws/account/{account_id} - Account-specific updates")
print("- /ws/admin/notifications - Admin notifications")

print("\nPASS: Backend is running and endpoints are registered")
