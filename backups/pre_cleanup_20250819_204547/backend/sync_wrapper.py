#!/usr/bin/env python3
"""
Wrapper for PodFactory sync to run in automated mode
"""
import sys
from datetime import datetime
from podfactory_sync import PodFactorySync

def main():
    sync = PodFactorySync()
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
        if mode == "continuous":
            print("Starting continuous sync (5-minute intervals)...")
            sync.run_continuous_sync(interval_minutes=3)
            
        elif mode == "today":
            print(f"Syncing today's activities...")
            today = datetime.now().date()
            sync.sync_date_range(today, today)
            print("✨ Today's sync complete!")
            
        elif mode == "recent":
            print(f"Syncing recent activities...")
            sync.sync_activities(use_last_sync=True)
            print("✨ Recent sync complete!")
            
        else:
            print(f"Unknown mode: {mode}")
            print("Usage: python sync_wrapper.py [continuous|today|recent]")
            sys.exit(1)
    else:
        # Default: sync today
        print("Syncing today's activities (default mode)...")
        today = datetime.now().date()
        sync.sync_date_range(today, today)
        print("✨ Sync complete!")

if __name__ == "__main__":
    main()
