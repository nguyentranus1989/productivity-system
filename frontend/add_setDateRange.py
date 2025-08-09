#!/usr/bin/env python3

with open('manager.html', 'r') as f:
    lines = f.readlines()

# Find where to add the function (look for applyDateFilter)
function_added = False
for i, line in enumerate(lines):
    if 'function applyDateFilter()' in line:
        # Add setDateRange before applyDateFilter
        indent = '        '
        setDateRange_code = '''        function setDateRange(range) {
            const today = api.getCentralDate();
            const startInput = document.getElementById('startDate');
            const endInput = document.getElementById('endDate');
            
            console.log('Setting date range:', range, 'Today:', today);
            
            if (range === 'today') {
                startInput.value = today;
                endInput.value = today;
            } else if (range === 'week') {
                const endDate = new Date(today + 'T12:00:00');
                const startDate = new Date(endDate);
                startDate.setDate(startDate.getDate() - 7);
                startInput.value = startDate.toISOString().split('T')[0];
                endInput.value = today;
            } else if (range === 'month') {
                const endDate = new Date(today + 'T12:00:00');
                const startDate = new Date(endDate);
                startDate.setMonth(startDate.getMonth() - 1);
                startInput.value = startDate.toISOString().split('T')[0];
                endInput.value = today;
            }
        }
        
'''
        lines[i] = setDateRange_code + lines[i]
        function_added = True
        print(f"Added setDateRange function at line {i}")
        break

if not function_added:
    print("Could not find applyDateFilter function, adding at end of script")
    # Find the last </script> tag
    for i in range(len(lines)-1, -1, -1):
        if '</script>' in lines[i]:
            lines[i] = '''        function setDateRange(range) {
            const today = api.getCentralDate();
            const startInput = document.getElementById('startDate');
            const endInput = document.getElementById('endDate');
            
            if (range === 'today') {
                startInput.value = today;
                endInput.value = today;
            } else if (range === 'week') {
                const endDate = new Date(today + 'T12:00:00');
                const startDate = new Date(endDate);
                startDate.setDate(startDate.getDate() - 7);
                startInput.value = startDate.toISOString().split('T')[0];
                endInput.value = today;
            } else if (range === 'month') {
                const endDate = new Date(today + 'T12:00:00');
                const startDate = new Date(endDate);
                startDate.setMonth(startDate.getMonth() - 1);
                startInput.value = startDate.toISOString().split('T')[0];
                endInput.value = today;
            }
        }
        
''' + lines[i]
            function_added = True
            print(f"Added setDateRange function before line {i}")
            break

# Write back
with open('manager.html', 'w') as f:
    f.writelines(lines)

if function_added:
    print("Successfully added setDateRange function")
else:
    print("Failed to add setDateRange function")
