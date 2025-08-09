#!/usr/bin/env python3

with open('manager.html', 'r') as f:
    lines = f.readlines()

# Find where setDateRange was just added (around line 2638) and add applyDateFilter after it
function_added = False
for i, line in enumerate(lines):
    if 'function setDateRange' in line:
        # Find the end of setDateRange function
        brace_count = 0
        start_found = False
        for j in range(i, min(i+50, len(lines))):
            if '{' in lines[j]:
                brace_count += lines[j].count('{')
                start_found = True
            if '}' in lines[j]:
                brace_count -= lines[j].count('}')
            if start_found and brace_count == 0:
                # Add applyDateFilter after setDateRange
                applyDateFilter_code = '''
        function applyDateFilter() {
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            
            if (!startDate || !endDate) {
                alert('Please select both start and end dates');
                return;
            }
            
            if (startDate > endDate) {
                alert('Start date must be before end date');
                return;
            }
            
            console.log('Applying date filter:', startDate, 'to', endDate);
            
            // Update the dashboard title
            const titleElement = document.querySelector('.dashboard-title p');
            if (startDate === endDate) {
                const dateObj = new Date(startDate + 'T12:00:00');
                titleElement.textContent = `Data for ${dateObj.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}`;
            } else {
                titleElement.textContent = `Data from ${new Date(startDate).toLocaleDateString()} to ${new Date(endDate).toLocaleDateString()}`;
            }
            
            // Store the date range
            dashboardData.startDate = startDate;
            dashboardData.endDate = endDate;
            
            // Reload data with new date range
            loadDashboardData();
            
            // If cost analysis is active, reload it too
            const costSection = document.getElementById('cost-section');
            if (costSection && costSection.classList.contains('active')) {
                if (typeof loadCostAnalysisData === 'function') {
                    loadCostAnalysisData();
                }
            }
        }
'''
                lines[j] = lines[j] + applyDateFilter_code
                function_added = True
                print(f"Added applyDateFilter function after line {j}")
                break
        break

# Write back
with open('manager.html', 'w') as f:
    f.writelines(lines)

if function_added:
    print("Successfully added applyDateFilter function")
else:
    print("Could not add applyDateFilter - you may need to add it manually")
