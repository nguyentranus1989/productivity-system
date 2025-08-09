#!/usr/bin/env python3

print("Fixing loadDashboardData to use stored dates...")

with open('manager.html', 'r') as f:
    lines = f.readlines()

# Find and fix loadDashboardData function
fixed = False
for i, line in enumerate(lines):
    if 'async function loadDashboardData()' in line:
        print(f"Found loadDashboardData at line {i+1}")
        
        # Look for the line that sets currentDate
        for j in range(i, min(i+10, len(lines))):
            if 'const currentDate = api.getCentralDate()' in lines[j]:
                # Replace with dashboardData.startDate or today
                lines[j] = lines[j].replace(
                    'const currentDate = api.getCentralDate()',
                    'const currentDate = dashboardData.startDate || api.getCentralDate()'
                )
                print(f"Fixed line {j+1}: Now uses dashboardData.startDate")
                fixed = True
                break
        
        if fixed:
            break

# Also fix any other direct calls to api.getLeaderboard, etc.
for i, line in enumerate(lines):
    # Fix getLeaderboard calls
    if 'api.getLeaderboard(' in lines[i]:
        if 'currentDate' not in lines[i] and 'dashboardData' not in lines[i]:
            lines[i] = lines[i].replace(
                'api.getLeaderboard()',
                'api.getLeaderboard(dashboardData.startDate || api.getCentralDate())'
            )
            print(f"Fixed getLeaderboard call at line {i+1}")
    
    # Fix getDepartmentStats calls
    if 'api.getDepartmentStats(' in lines[i]:
        if 'currentDate' not in lines[i] and 'dashboardData' not in lines[i]:
            lines[i] = lines[i].replace(
                'api.getDepartmentStats()',
                'api.getDepartmentStats(dashboardData.startDate || api.getCentralDate())'
            )
            print(f"Fixed getDepartmentStats call at line {i+1}")

# Write back
with open('manager.html', 'w') as f:
    f.writelines(lines)

print("Fixed date usage in manager.html")
