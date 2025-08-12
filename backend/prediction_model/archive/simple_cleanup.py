#!/usr/bin/env python3
"""
Simple cleanup script for prediction_model directory
"""

import os
import shutil

print("🧹 CLEANING UP PREDICTION MODEL PROJECT")
print("=" * 60)

# Create archive directories
os.makedirs('archive/test_files', exist_ok=True)
os.makedirs('archive/fix_scripts', exist_ok=True)
os.makedirs('archive/old_versions', exist_ok=True)
print("✓ Created archive directories")

# Move test files
test_files = ['test_advanced.py', 'test_connection.py', 'test_enhanced.py', 'test_model.py']
for f in test_files:
    if os.path.exists(f):
        shutil.move(f, f'archive/test_files/{f}')
        print(f"  Archived: {f}")

# Move fix scripts
fix_files = ['fix_column.py', 'fix_decimal_issues.py', 'fix_deploy.py', 'fix_deploy_enhanced.py']
for f in fix_files:
    if os.path.exists(f):
        shutil.move(f, f'archive/fix_scripts/{f}')
        print(f"  Archived: {f}")

# Move old versions
old_files = [
    'deploy_enhanced_backup.py', 'deploy_enhanced_fixed.py', 
    'deploy_enhanced_old.py', 'deploy_clear.py',
    'enhanced_predictor_backup.py', 'predictor_core.py',
    'advanced_predictor.py', 'warehouse_predictor.py'
]
for f in old_files:
    if os.path.exists(f):
        shutil.move(f, f'archive/old_versions/{f}')
        print(f"  Archived: {f}")

# Move cleanup script itself
if os.path.exists('cleanup_project.py'):
    shutil.move('cleanup_project.py', 'archive/cleanup_project.py')

# Rename clear version to main if exists
if os.path.exists('deploy_enhanced_clear.py'):
    if os.path.exists('deploy_enhanced.py'):
        shutil.move('deploy_enhanced.py', 'archive/old_versions/deploy_enhanced_original.py')
    shutil.move('deploy_enhanced_clear.py', 'deploy_enhanced.py')
    print("✓ Updated deploy_enhanced.py to clear version")

print("\n" + "=" * 60)
print("✅ CLEANUP COMPLETE!")
print("=" * 60)

# Show what's left
print("\n📁 Remaining Python files:")
for f in os.listdir('.'):
    if f.endswith('.py'):
        size = os.path.getsize(f) / 1024
        print(f"  ✓ {f:<30} ({size:.1f} KB)")

print("\n🎯 Essential files kept:")
print("  • db_config.py - Database configuration")
print("  • enhanced_predictor.py - Main prediction model")
print("  • deploy_enhanced.py - Deployment script")
print("\n📂 All other files moved to archive/")
print("\nTo remove archive: rm -rf archive/")
