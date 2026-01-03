#!/usr/bin/env python3
"""Sync only missing dates from Connecteam"""
import sys
import os
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import get_db
from config import Config
from integrations.connecteam_sync import ConnecteamSync

def main():
    print("SYNC MISSING DATES")
    print("=" * 50)

    db = get_db()
    config = Config()
    sync = ConnecteamSync(config.CONNECTEAM_API_KEY, config.CONNECTEAM_CLOCK_ID)

    # Get existing dates
    ct_dates = db.fetch_all('SELECT DISTINCT DATE(clock_in) as d FROM clock_times WHERE YEAR(clock_in)=2025')
    ct_set = set(r['d'] for r in ct_dates)

    # Find missing dates (exclude Sundays)
    missing = []
    d = date(2025, 1, 1)
    while d <= date(2025, 12, 31):
        if d not in ct_set and d.weekday() != 6:
            missing.append(d)
        d += timedelta(days=1)

    print(f"Found {len(missing)} missing non-Sunday dates")
    print()

    synced = 0
    for i, d in enumerate(missing):
        print(f"[{i+1}/{len(missing)}] {d} ... ", end="")
        sys.stdout.flush()
        try:
            stats = sync.sync_shifts_for_date_v2(d)
            if stats.get('total_shifts', 0) > 0:
                print(f"OK {stats['total_shifts']} shifts")
                synced += 1
            else:
                print("no shifts")
            time.sleep(0.3)
        except Exception as e:
            print(f"ERROR: {e}")

    print()
    print(f"Done. Synced {synced} new days with data.")

if __name__ == "__main__":
    main()
