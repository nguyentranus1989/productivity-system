#!/usr/bin/env python3
"""
Fix deploy_enhanced.py to show BOTH real demand and QC-limited numbers clearly
"""

# Read the current deploy_enhanced.py
with open('deploy_enhanced.py', 'r') as f:
    content = f.read()

# Find the section where it prints the predictions and replace it
new_print_section = '''
            # Get REAL unconstrained demand
            real_demand = predictor.base_average
            if result['day_name'] in predictor.patterns['day_of_week']:
                real_demand = predictor.patterns['day_of_week'][result['day_name']]['average']
            
            # Print progress for first week with BOTH numbers
            if i < 7:
                status = ""
                if result.get('qc_constraint'):
                    status = f" [REAL: {int(real_demand)} → LIMITED: {result['predicted_orders']}]"
                    if result.get('overflow', 0) > 0:
                        status += f" OVERFLOW: {result['overflow']}"
                elif holiday_info.get('name'):
                    status = f" [{holiday_info['name']}] DEMAND: {int(real_demand)}"
                else:
                    status = f" [DEMAND: {int(real_demand)}]"
                
                print(f"  ✓ {date} ({result['day_name']}): {result['predicted_orders']} items{status}")
'''

# Replace the print section
import re

# Find and replace the print section
pattern = r"(\s+# Print progress for first week\s+if i < 7:.*?print\(f.*?\))"
replacement = new_print_section

# Use regex with DOTALL flag to match across multiple lines
content = re.sub(pattern, new_print_section, content, flags=re.DOTALL)

# If regex didn't work, do a simpler replacement
if "REAL:" not in content:
    # Find the specific line and replace
    old_line = 'print(f"  ✓ {date} ({result[\'day_name\']}): {result[\'predicted_orders\']} items{status}")'
    new_lines = '''
                # Get REAL demand
                real_demand = predictor.base_average
                if result['day_name'] in predictor.patterns['day_of_week']:
                    real_demand = predictor.patterns['day_of_week'][result['day_name']]['average']
                
                # Show BOTH numbers clearly
                if result.get('qc_constraint'):
                    print(f"  ✓ {date} ({result['day_name']}): DEMAND={int(real_demand)} → QC_LIMITED={result['predicted_orders']} [OVERFLOW: {result.get('overflow', 0)}]")
                else:
                    print(f"  ✓ {date} ({result['day_name']}): {result['predicted_orders']} items [Demand: {int(real_demand)}]")'''
    
    content = content.replace(old_line, new_lines)

# Save the fixed version
with open('deploy_enhanced_fixed.py', 'w') as f:
    f.write(content)

print("✅ Created deploy_enhanced_fixed.py with clear demand visibility")
print("\nNow run:")
print("  cp deploy_enhanced.py deploy_enhanced_backup.py")
print("  cp deploy_enhanced_fixed.py deploy_enhanced.py")
print("  python3 deploy_enhanced.py")
