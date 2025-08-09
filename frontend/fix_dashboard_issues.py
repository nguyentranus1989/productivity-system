
#!/usr/bin/env python3

print("Fixing manager.html issues...")

with open('manager.html', 'r') as f:
    content = f.read()

# Count how many times dashboardData is declared
import re
declarations = re.findall(r'(let|var|const)\s+dashboardData\s*=', content)
print(f"Found {len(declarations)} dashboardData declarations")

# Remove duplicate declarations, keep only the first one
if len(declarations) > 1:
    # Keep the first, remove others
    first_found = False
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        if re.search(r'(let|var|const)\s+dashboardData\s*=', line):
            if not first_found:
                first_found = True
                new_lines.append(line)
                print(f"Keeping dashboardData declaration: {line.strip()}")
            else:
                print(f"Removing duplicate: {line.strip()}")
                # Skip this line
                continue
        else:
            new_lines.append(line)
    content = '\n'.join(new_lines)

# Now add the showSection function if it doesn't exist
if 'function showSection' not in content:
    print("Adding showSection function...")
    
    # Find a good place to add it (after other functions)
    insert_pos = content.find('function applyDateFilter')
    if insert_pos == -1:
        insert_pos = content.find('function setDateRange')
    
    if insert_pos > 0:
        # Add before the found function
        showSection_code = '''
        function showSection(sectionName) {
            console.log('Showing section:', sectionName);
            
            // Hide all sections
            const sections = ['dashboard-section', 'cost-section', 'bottleneck-section'];
            sections.forEach(id => {
                const section = document.getElementById(id);
                if (section) {
                    section.style.display = 'none';
                    section.classList.remove('active');
                }
            });
            
            // Show the selected section
            const selectedSection = document.getElementById(sectionName + '-section');
            if (selectedSection) {
                selectedSection.style.display = 'block';
                selectedSection.classList.add('active');
                
                // Load data for the section
                if (sectionName === 'dashboard') {
                    loadDashboardData();
                } else if (sectionName === 'cost') {
                    if (typeof loadCostAnalysisData === 'function') {
                        loadCostAnalysisData();
                    }
                } else if (sectionName === 'bottleneck') {
                    if (typeof loadBottleneckData === 'function') {
                        loadBottleneckData();
                    }
                }
            }
            
            // Update active nav item
            document.querySelectorAll('.nav-item').forEach(item => {
                item.classList.remove('active');
            });
            const activeNav = document.querySelector(`[onclick*="${sectionName}"]`);
            if (activeNav && activeNav.parentElement) {
                activeNav.parentElement.classList.add('active');
            }
        }
        
'''
        content = content[:insert_pos] + showSection_code + content[insert_pos:]
        print("Added showSection function")

# Write the fixed content
with open('manager.html', 'w') as f:
    f.write(content)

print("Fixed manager.html issues")
