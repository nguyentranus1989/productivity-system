# Add debug logging to write_direct_to_db
with open('/var/www/productivity-system/backend/podfactory_sync.py', 'r') as f:
    lines = f.readlines()

# Find the write_direct_to_db method and add debug
for i in range(len(lines)):
    if 'def write_direct_to_db(self, activities_batch):' in lines[i]:
        # Add debug after the try:
        for j in range(i, i+20):
            if 'try:' in lines[j]:
                lines.insert(j+1, '            # Debug first activity\n')
                lines.insert(j+2, '            if activities_batch:\n')
                lines.insert(j+3, '                logger.info(f"First activity keys: {list(activities_batch[0].keys())}")\n')
                lines.insert(j+4, '                if "metadata" in activities_batch[0]:\n')
                lines.insert(j+5, '                    logger.info(f"Metadata keys: {list(activities_batch[0][\'metadata\'].keys())}")\n')
                break
        break

with open('/var/www/productivity-system/backend/podfactory_sync.py', 'w') as f:
    f.writelines(lines)

print("Added debug logging")
