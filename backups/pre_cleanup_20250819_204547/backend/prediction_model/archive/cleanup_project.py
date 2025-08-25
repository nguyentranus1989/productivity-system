#!/usr/bin/env python3
"""
Clean up and organize the prediction_model directory
Keep only essential files, archive the rest
"""

import os
import shutil
from datetime import datetime

print("🧹 CLEANING UP PREDICTION MODEL PROJECT")
print("=" * 60)

# Create organized directories
dirs_to_create = {
    'archive': 'Old and backup files',
    'archive/test_files': 'Test scripts',
    'archive/fix_scripts': 'One-time fix scripts',
    'archive/old_versions': 'Backup versions'
}

for dir_name, description in dirs_to_create.items():
    os.makedirs(dir_name, exist_ok=True)
    print(f"✓ Created {dir_name}/ - {description}")

print("\n" + "=" * 60)
print("📦 ORGANIZING FILES...")
print("=" * 60)

# Define what to keep and what to archive
files_to_archive = {
    # Test files - we don't need these in production
    'test_advanced.py': 'archive/test_files/',
    'test_connection.py': 'archive/test_files/',
    'test_enhanced.py': 'archive/test_files/',
    'test_model.py': 'archive/test_files/',
    
    # Fix scripts - one-time use only
    'fix_column.py': 'archive/fix_scripts/',
    'fix_decimal_issues.py': 'archive/fix_scripts/',
    'fix_deploy.py': 'archive/fix_scripts/',
    'fix_deploy_enhanced.py': 'archive/fix_scripts/',
    
    # Old/backup versions
    'deploy_enhanced_backup.py': 'archive/old_versions/',
    'deploy_enhanced_fixed.py': 'archive/old_versions/',
    'deploy_enhanced_old.py': 'archive/old_versions/',
    'deploy_clear.py': 'archive/old_versions/',
    'enhanced_predictor_backup.py': 'archive/old_versions/',
    'predictor_core.py': 'archive/old_versions/',  # Using enhanced_predictor instead
    'advanced_predictor.py': 'archive/old_versions/',  # Using enhanced_predictor instead
    'warehouse_predictor.py': 'archive/old_versions/',  # Early version
}

# Files to keep (the essential ones)
files_to_keep = {
    'db_config.py': 'Database configuration',
    'enhanced_predictor.py': 'Main prediction model',
    'deploy_enhanced.py': 'Production deployment script',
    'deploy_enhanced_clear.py': 'Clear deployment (showing real demand)'
}

# Move files to archive
archived_count = 0
for filename, destination in files_to_archive.items():
    if os.path.exists(filename):
        try:
            shutil.move(filename, destination + filename)
            print(f"  📁 Archived: {filename} → {destination}")
            archived_count += 1
        except Exception as e:
            print(f"  ⚠️  Could not move {filename}: {e}")

print(f"\n✅ Archived {archived_count} files")

# Rename the clear deployment to be the main one
if os.path.exists('deploy_enhanced_clear.py') and os.path.exists('deploy_enhanced.py'):
    shutil.move('deploy_enhanced.py', 'archive/old_versions/deploy_enhanced_original.py')
    shutil.move('deploy_enhanced_clear.py', 'deploy_enhanced.py')
    print("✅ Updated deploy_enhanced.py to show clear demand numbers")

print("\n" + "=" * 60)
print("📋 FILES REMAINING:")
print("=" * 60)

# List remaining files
remaining_files = [f for f in os.listdir('.') if f.endswith('.py')]
for file in remaining_files:
    size = os.path.getsize(file) / 1024  # Size in KB
    print(f"  ✓ {file:<30} ({size:.1f} KB)")

# Create the main runner script
print("\n📝 Creating main runner script...")

main_runner = '''#!/usr/bin/env python3
"""
Main Daily Prediction Runner
This is the primary script to run predictions
"""

from enhanced_predictor import EnhancedWarehousePredictor
from deploy_enhanced import deploy_enhanced_predictions
from datetime import datetime

def run_daily_predictions():
    """Run the daily prediction process"""
    print(f"\\n{'='*60}")
    print(f"🚀 DAILY PREDICTION RUN - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    
    try:
        # Run the deployment
        success = deploy_enhanced_predictions()
        
        if success:
            print("\\n✅ Daily predictions completed successfully!")
            print("\\n📊 To view results:")
            print("  • Check database: SELECT * FROM order_predictions WHERE prediction_date >= CURDATE()")
            print("  • View demand analysis: python3 show_demand_analysis.py")
            return True
        else:
            print("\\n❌ Prediction failed - check logs")
            return False
            
    except Exception as e:
        print(f"\\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    run_daily_predictions()
'''

with open('run_daily_predictions.py', 'w') as f:
    f.write(main_runner)
os.chmod('run_daily_predictions.py', 0o755)  # Make executable

# Create demand analysis script
demand_script = '''#!/usr/bin/env python3
"""
Show Real Demand vs QC Capacity Analysis
"""

from enhanced_predictor import EnhancedWarehousePredictor
from db_config import DB_CONFIG
import mysql.connector
from datetime import datetime, timedelta

def show_demand_analysis():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    
    print(f"\\n{'='*80}")
    print("📊 DEMAND vs CAPACITY ANALYSIS - NEXT 7 DAYS")
    print(f"{'='*80}\\n")
    
    cursor.execute("""
        SELECT 
            prediction_date,
            DAYNAME(prediction_date) as day,
            predicted_orders,
            confidence_score
        FROM order_predictions
        WHERE prediction_date >= CURDATE()
        ORDER BY prediction_date
        LIMIT 7
    """)
    
    results = cursor.fetchall()
    
    predictor = EnhancedWarehousePredictor()
    predictor.train_enhanced()
    
    total_overflow = 0
    
    for row in results:
        day_name = row['day']
        qc_limited = row['predicted_orders']
        
        # Get real demand
        if day_name in predictor.patterns['day_of_week']:
            real_demand = int(predictor.patterns['day_of_week'][day_name]['average'])
        else:
            real_demand = int(predictor.base_average)
        
        overflow = max(0, real_demand - qc_limited)
        total_overflow += overflow
        
        status = "⚠️ OVERFLOW" if overflow > 0 else "✅ OK"
        
        print(f"{row['prediction_date']} ({day_name:9}): Demand={real_demand:4} → QC={qc_limited:4} [{status}]")
        
        if overflow > 0:
            print(f"{'':23} Need {overflow/150:.1f} overtime hours")
    
    if total_overflow > 0:
        print(f"\\n💡 WEEKLY OVERTIME NEEDED: {total_overflow/150:.0f} hours total")
        print(f"   Estimated cost: ${total_overflow/150*25:.2f}")
    
    cursor.close()
    conn.close()
    predictor.close()

if __name__ == "__main__":
    show_demand_analysis()
'''

with open('show_demand_analysis.py', 'w') as f:
    f.write(demand_script)

# Create PM2 ecosystem config
pm2_config = '''module.exports = {
  apps: [
    {
      name: 'predictions-daily',
      script: 'run_daily_predictions.py',
      interpreter: '/var/www/productivity-system/backend/venv/bin/python3',
      cwd: '/var/www/productivity-system/backend/prediction_model',
      cron_restart: '0 6 * * *',
      autorestart: false,
      watch: false
    }
  ]
}'''

with open('ecosystem.config.js', 'w') as f:
    f.write(pm2_config)

# Create README
# Create README
readme = """# Prediction Model System (CLEANED)

## Essential Files Only

### Core Files (3)
- db_config.py - Database configuration
- enhanced_predictor.py - The prediction model
- deploy_enhanced.py - Deployment script with clear demand visibility

### Runner Scripts (2)
- run_daily_predictions.py - Main daily runner (use this!)
- show_demand_analysis.py - View demand vs capacity

### Configuration (1)
- ecosystem.config.js - PM2 configuration for automation

## Daily Usage

```bash
# Run predictions manually
python3 run_daily_predictions.py

# View demand analysis
python3 show_demand_analysis.py

# Schedule with PM2 (runs at 6 AM daily)
pm2 start ecosystem.config.js
