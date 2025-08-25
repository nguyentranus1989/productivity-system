#!/usr/bin/env python3
"""
Simple test to check if sync is working
"""
import requests
import time

print("Testing Connecteam sync...")
print("=" * 40)

# Test employee sync
print("\n1. Testing employee sync...")
response = requests.post(
    'http://localhost:5000/api/connecteam/sync/employees',
    headers={'X-API-Key': 'dev-api-key-123'},
    timeout=30
)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print(f"   Result: {response.json()}")

# Wait a bit
time.sleep(2)

# Test shift sync
print("\n2. Testing shift sync...")
response = requests.post(
    'http://localhost:5000/api/connecteam/sync/shifts/today',
    headers={'X-API-Key': 'dev-api-key-123'},
    timeout=30
)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print("   SUCCESS! Shift sync is working!")
    print(f"   Result: {response.json()}")
else:
    print("   Still failing")
    print("   Check Flask console for errors")

print("\n" + "=" * 40)