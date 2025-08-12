#!/usr/bin/env python3
from predictor_core import WarehousePredictor
from datetime import datetime, timedelta

print("🧪 Testing Warehouse Predictor Model")
print("=" * 50)

try:
    # Initialize and train
    predictor = WarehousePredictor()
    predictor.train()
    
    print("\n📅 Test Predictions for Next 7 Days:")
    print("-" * 50)
    
    # Generate test predictions
    total = 0
    for i in range(7):
        date = datetime.now().date() + timedelta(days=i)
        result = predictor.predict(date)
        
        print(f"{result['date']} ({result['day_name']:9}) : "
              f"{result['predicted_orders']:4} items (×{result['multiplier']:.2f})")
        total += result['predicted_orders']
    
    print("-" * 50)
    print(f"Weekly Total: {total:,} items")
    print(f"Daily Average: {total/7:.0f} items")
    
    predictor.close()
    print("\n✅ Model test complete!")
    
except Exception as e:
    print(f"❌ Error: {e}")
