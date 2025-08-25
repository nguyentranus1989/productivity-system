#!/usr/bin/env python3
"""
Main daily prediction runner
"""

from deploy_enhanced import deploy_enhanced_predictions
from datetime import datetime

print(f"\n{'='*60}")
print(f"🚀 DAILY PREDICTION RUN - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*60}")

try:
    success = deploy_enhanced_predictions()
    if success:
        print("\n✅ Predictions completed successfully!")
    else:
        print("\n❌ Prediction failed")
except Exception as e:
    print(f"\n❌ Error: {e}")
