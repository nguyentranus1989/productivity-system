import requests
import json
from collections import defaultdict

API_KEY = "dev-api-key-123"
BASE_URL = "http://127.0.0.1:5000"

headers = {"X-API-Key": API_KEY}

# Get raw clock times
raw_resp = requests.get(f"{BASE_URL}/api/dashboard/clock-times/today", headers=headers)
raw = raw_resp.json()

# Get cost analysis
cost_resp = requests.get(f"{BASE_URL}/api/dashboard/cost-analysis?start_date=2025-12-10&end_date=2025-12-10", headers=headers)
cost = cost_resp.json()

# Aggregate raw data
raw_emp = defaultdict(lambda: {'total_mins': 0, 'shifts': 0, 'is_in': False})
for row in raw:
    name = row['employee_name']
    raw_emp[name]['total_mins'] += row['total_minutes']
    raw_emp[name]['shifts'] += 1
    if row['is_clocked_in']:
        raw_emp[name]['is_in'] = True

# Build cost analysis lookup
cost_emp = {e['name']: float(e['clocked_hours']) for e in cost['employee_costs']}

# Get all names
all_names = set(raw_emp.keys()) | set(cost_emp.keys())

print('COMPARISON: Raw clock_times vs Cost Analysis')
print('='*100)
header = 'Name                      Raw Hrs   Cost Hrs       Diff     Status   Shifts          Issue'
print(header)
print('-'*100)

discrepancies = []
for name in sorted(all_names):
    raw_hrs = raw_emp[name]['total_mins'] / 60 if name in raw_emp else 0
    cost_hrs = cost_emp.get(name, 0)
    diff = raw_hrs - cost_hrs
    shifts = raw_emp[name]['shifts'] if name in raw_emp else 0
    is_in = raw_emp[name]['is_in'] if name in raw_emp else False
    status = 'IN' if is_in else 'OUT'

    issue = ''
    if name not in raw_emp:
        issue = 'NOT IN RAW'
    elif name not in cost_emp:
        issue = 'NOT IN COST'
    elif abs(diff) > 1.0:
        issue = 'BIG DIFF!'
    elif abs(diff) > 0.5:
        issue = 'MEDIUM DIFF'

    if issue:
        discrepancies.append((name, raw_hrs, cost_hrs, diff, issue))

    line = '%s %10.2f %10.2f %+10.2f %10s %8d %15s' % (name.ljust(25)[:25], raw_hrs, cost_hrs, diff, status, shifts, issue)
    print(line)

print('='*100)
print('Total in Raw: %d | Total in Cost Analysis: %d' % (len(raw_emp), len(cost_emp)))
print()

if discrepancies:
    print('DISCREPANCIES FOUND:')
    print('-'*60)
    for name, raw_hrs, cost_hrs, diff, issue in discrepancies:
        print('  %s: raw=%.2fh, cost=%.2fh, diff=%+.2fh - %s' % (name, raw_hrs, cost_hrs, diff, issue))
