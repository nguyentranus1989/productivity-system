import requests
base_url = "http://localhost:5000"
headers = {"X-API-Key": "dev-api-key-123"}

# Test different bulk endpoints
endpoints = [
    "/api/dashboard/activities/bulk",
    "/api/activities/bulk",
    "/api/bulk_activities"
]

for endpoint in endpoints:
    r = requests.post(f"{base_url}{endpoint}", json={"activities": []}, headers=headers)
    print(f"{endpoint}: {r.status_code}")