#!/usr/bin/env python3
"""
Sync all of today's activities from PodFactory
"""

from datetime import datetime
from podfactory_sync import PodFactorySync

def sync_today():
    print("="*60)
    print(f"SYNCING ALL ACTIVITIES FOR TODAY: {datetime.now().date()}")
    print("="*60)
    
    # Initialize sync
    sync = PodFactorySync()
    
    # Get today's date
    today = datetime.now().date()
    
    # Sync today's activities
    print(f"\nSyncing all activities for {today}...")
    sync.sync_date_range(today, today)
    
    print("\n✅ Sync complete!")
    print("\nNow run force_calculate.py to update all scores.")

if __name__ == "__main__":
    sync_today()