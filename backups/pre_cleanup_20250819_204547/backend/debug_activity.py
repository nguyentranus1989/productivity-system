from podfactory_sync import PodFactorySync
from datetime import datetime, timedelta

sync = PodFactorySync()
last_sync = sync.get_last_sync_time()
activities = sync.fetch_new_activities(last_sync)

if activities:
    print(f"Found {len(activities)} activities")
    print("\nFirst activity structure:")
    for key, value in activities[0].items():
        print(f"  {key}: {value}")
else:
    print("No activities found")
