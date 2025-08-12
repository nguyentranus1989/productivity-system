#!/usr/bin/env python3
"""
Fix all Decimal type issues in enhanced_predictor.py
"""

import re

# Read the file
with open('enhanced_predictor.py', 'r') as f:
    content = f.read()

# Fix patterns
fixes = [
    # Fix calculate_qc_capacity function
    (
        r"max_capacity = np\.mean\(\[d\['daily_qc'\] for d in top_days\]\)",
        "max_capacity = np.mean([float(d['daily_qc']) for d in top_days if d['daily_qc'] is not None])"
    ),
    (
        r"practical_capacity = max_capacity \* 0\.95",
        "practical_capacity = float(max_capacity * 0.95)"
    ),
    (
        r"practical_capacity = 2000",
        "practical_capacity = 2000.0"
    ),
    
    # Fix baseline calculations
    (
        r"self\.base_average = float\(baseline\['avg'\]\)",
        "self.base_average = float(baseline['avg']) if baseline['avg'] else 0"
    ),
    (
        r"self\.std_deviation = float\(baseline\['std_dev'\]\)",
        "self.std_deviation = float(baseline['std_dev']) if baseline['std_dev'] else 0"
    ),
    
    # Fix day patterns loop
    (
        r"'multiplier': float\(row\['avg_orders'\]\) / self\.base_average,",
        "'multiplier': float(row['avg_orders']) / self.base_average if self.base_average else 1,"
    ),
    (
        r"'average': float\(row\['avg_orders'\]\),",
        "'average': float(row['avg_orders']) if row['avg_orders'] else 0,"
    ),
    (
        r"'std_dev': float\(row\['std_dev'\]\)",
        "'std_dev': float(row['std_dev']) if row['std_dev'] else 0"
    ),
    
    # Fix detect_customer_patterns
    (
        r"multiplier = float\(result\['avg_orders'\]\) / self\.base_average",
        "multiplier = float(result['avg_orders']) / self.base_average if self.base_average else 1"
    ),
    
    # Fix analyze_recent_performance
    (
        r"errors = \[\(float\(d\['actual_orders'\]\) / d\['predicted_orders'\]\)",
        "errors = [(float(d['actual_orders']) / float(d['predicted_orders']))"
    ),
]

# Apply all fixes
for pattern, replacement in fixes:
    content = re.sub(pattern, replacement, content)

# Additional fix: Add float conversion wrapper function at the top
wrapper_function = '''
def safe_float(value, default=0):
    """Safely convert Decimal or other types to float"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

'''

# Insert after imports
import_end = content.find('class EnhancedWarehousePredictor:')
if import_end > 0:
    content = content[:import_end] + wrapper_function + content[import_end:]

# Replace all remaining Decimal-prone operations
content = re.sub(r"float\(([^)]+)\['([^']+)'\]\)", r"safe_float(\1['\2'])", content)

# Save the fixed file
with open('enhanced_predictor_fixed.py', 'w') as f:
    f.write(content)

print("✅ Created enhanced_predictor_fixed.py with all Decimal issues fixed!")
print("\nNow run:")
print("  mv enhanced_predictor.py enhanced_predictor_backup.py")
print("  mv enhanced_predictor_fixed.py enhanced_predictor.py")
print("  python3 test_enhanced.py")
