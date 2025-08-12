#!/usr/bin/env python3
"""
Automatically fix deploy_enhanced.py by removing updated_at references
"""

# Read the original file
try:
    with open('deploy_enhanced.py', 'r') as f:
        content = f.read()
except FileNotFoundError:
    print("❌ deploy_enhanced.py not found!")
    exit(1)

# Remove all occurrences of updated_at
replacements = [
    # Remove from UPDATE clause
    (",\n                updated_at = NOW()", ""),
    (", updated_at = NOW()", ""),
    (",\nupdated_at = NOW()", ""),
    (", updated_at=NOW()", ""),
    
    # Remove standalone updated_at lines
    ("updated_at = NOW()\n", ""),
    ("updated_at = NOW(),\n", ""),
    
    # Fix any double commas that might result
    (",,", ","),
    
    # Fix trailing commas before closing parenthesis
    (",\n            \"\"\")", "\n            \"\"\")")
]

# Apply all replacements
for old, new in replacements:
    content = content.replace(old, new)

# Save the fixed version
with open('deploy_enhanced_fixed.py', 'w') as f:
    f.write(content)

print("✅ Created deploy_enhanced_fixed.py without updated_at references")
print("\nNow run:")
print("  mv deploy_enhanced.py deploy_enhanced_old.py")
print("  mv deploy_enhanced_fixed.py deploy_enhanced.py")
print("  python3 deploy_enhanced.py")
