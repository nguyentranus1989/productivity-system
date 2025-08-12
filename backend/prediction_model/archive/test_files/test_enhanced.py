#!/usr/bin/env python3
"""
Test the enhanced prediction model with all improvements
"""

from enhanced_predictor import EnhancedWarehousePredictor
from datetime import datetime, timedelta

print("🚀 Testing Enhanced Warehouse Predictor v3")
print("=" * 70)

try:
    # Initialize and train
    predictor = EnhancedWarehousePredictor()
    predictor.train_enhanced()
    
    # Test holiday detection
    print("\n🎄 HOLIDAY DETECTION TEST:")
    print("-" * 40)
    
    test_dates = [
        datetime(2025, 12, 24).date(),  # Christmas Eve
        datetime(2025, 12, 26).date(),  # Day after Christmas
        datetime(2025, 11, 28).date(),  # Black Friday
        datetime(2025, 8, 11).date(),   # Regular Monday
    ]
    
    for date in test_dates:
        holiday_info = predictor.detect_holidays(date)
        if holiday_info['multiplier'] != 1.0:
            print(f"{date}: {holiday_info['name']} (×{holiday_info['multiplier']:.2f})")
        else:
            print(f"{date}: Regular day")
    
    # Simulate next week with constraints
    print("\n📅 NEXT WEEK PREDICTIONS WITH QC CONSTRAINTS:")
    predictor.simulate_week_with_constraints()
    
    # Test a high-volume scenario
    print("\n🔥 HIGH VOLUME SCENARIO TEST:")
    print("-" * 40)
    
    # Simulate Black Friday week
    black_friday = datetime(2025, 11, 28).date()
    week_start = black_friday - timedelta(days=4)  # Start on Monday
    
    print("Simulating Thanksgiving/Black Friday week:")
    predictor.simulate_week_with_constraints(week_start)
    
    predictor.close()
    
    print("\n✅ Enhanced model test complete!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
