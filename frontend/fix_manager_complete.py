
#!/usr/bin/env python3

print("Fixing manager.html date initialization...")

# Read the file
with open('manager.html', 'r') as f:
    lines = f.readlines()

# Find the DOMContentLoaded section
for i, line in enumerate(lines):
    if "document.addEventListener('DOMContentLoaded'" in line:
        # Find where we initialize the chart (around line 1638)
        for j in range(i, min(i+50, len(lines))):
            if "// Initialize chart" in lines[j]:
                # Add date initialization BEFORE chart initialization
                indent = '            '
                date_init_code = f'''{indent}// Initialize date inputs with today's date
{indent}const today = api.getCentralDate();
{indent}console.log('Setting initial date to:', today);
{indent}document.getElementById('startDate').value = today;
{indent}document.getElementById('endDate').value = today;
{indent}
{indent}// Store in dashboardData
{indent}dashboardData.startDate = today;
{indent}dashboardData.endDate = today;
{indent}
{indent}// Update the title to show today's date
{indent}const titleElement = document.querySelector('.dashboard-title p');
{indent}if (titleElement) {{
{indent}    const dateObj = new Date(today + 'T12:00:00');  // Add time to avoid timezone issues
{indent}    titleElement.textContent = `Data for ${{dateObj.toLocaleDateString('en-US', {{ weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }})}}`; 
{indent}}}
{indent}
'''
                # Insert before the chart initialization
                lines[j] = date_init_code + lines[j]
                print(f"Added date initialization at line {j}")
                break
        break

# Also find and fix the loadCostAnalysisData function to use the stored dates
for i, line in enumerate(lines):
    if "function loadCostAnalysisData()" in line:
        # Look for where it gets the dates (around line 2175-2176)
        for j in range(i, min(i+20, len(lines))):
            if "document.getElementById('startDate').value || api.getCentralDate()" in lines[j]:
                # Change to use dashboardData if available
                lines[j] = lines[j].replace(
                    "document.getElementById('startDate').value || api.getCentralDate()",
                    "dashboardData.startDate || document.getElementById('startDate').value || api.getCentralDate()"
                )
                lines[j+1] = lines[j+1].replace(
                    "document.getElementById('endDate').value || api.getCentralDate()",
                    "dashboardData.endDate || document.getElementById('endDate').value || api.getCentralDate()"
                )
                print(f"Fixed loadCostAnalysisData date handling at line {j}")
                break
        break

# Write back
with open('manager.html', 'w') as f:
    f.writelines(lines)

print("Done! Date initialization added to manager.html")
