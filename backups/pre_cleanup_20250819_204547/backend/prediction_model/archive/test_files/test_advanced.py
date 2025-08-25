#!/usr/bin/env python3
"""
Test the advanced prediction model
"""

from advanced_predictor import AdvancedWarehousePredictor
from datetime import datetime, timedelta

print("🚀 Testing Advanced Warehouse Predictor")
print("=" * 60)

try:
    # Initialize and train
    predictor = AdvancedWarehousePredictor()
    predictor.train_comprehensive()
    
    # Backtest for accuracy
    accuracy = predictor.backtest(test_start='2025-06-01', test_end='2025-06-30')
    
    print("\n" + "=" * 60)
    print("📅 PREDICTIONS FOR NEXT 14 DAYS:")
    print("=" * 60)
    
    total = 0
    for i in range(14):
        date = datetime.now().date() + timedelta(days=i)
        result = predictor.predict_with_bounds(date)
        
        print(f"\n{result['date']} ({result['day_name']})")
        print(f"  Prediction: {result['predicted_orders']} items")
        print(f"  Likely Range: {result['likely_range']} items")
        print(f"  Confidence: {result['confidence']}%")
        print(f"  Factors: {', '.join(result['adjustments'])}")
        
        total += result['predicted_orders']
        
        # Extra detail for next 7 days
        if i < 7:
            if result['lower_bound'] < result['predicted_orders'] < result['upper_bound']:
                print(f"  📊 95% chance between {result['lower_bound']}-{result['upper_bound']} items")
    
    print("\n" + "=" * 60)
    print(f"14-Day Total: {total:,} items")
    print(f"Daily Average: {total/14:.0f} items")
    print(f"Model Accuracy: {accuracy:.1f}%")
    
    predictor.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
