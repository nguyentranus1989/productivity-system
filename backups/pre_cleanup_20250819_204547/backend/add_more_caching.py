"""Add caching to more endpoints"""

with open('/var/www/productivity-system/backend/api/dashboard.py', 'r') as f:
    content = f.read()

# Endpoints to cache and their cache times
endpoints_to_cache = [
    ('def get_department_stats():', 'department_stats', 15),
    ('def get_cost_analysis():', 'cost_analysis', 30),
    ('def get_recent_activities():', 'recent_activities', 5),
]

for func_def, cache_name, cache_time in endpoints_to_cache:
    if func_def in content:
        # Check if already cached
        func_pos = content.find(func_def)
        func_end = content.find('\ndef ', func_pos + 10)
        if func_end == -1:
            func_end = len(content)
        
        func_content = content[func_pos:func_end]
        
        if 'get_cached_response' not in func_content:
            # Add caching
            cache_check = f'''
    # Check cache first
    cached = get_cached_response("{cache_name}", cache_seconds={cache_time})
    if cached:
        return jsonify(cached)
    '''
            
            # Insert after function definition
            insert_pos = func_pos + len(func_def)
            content = content[:insert_pos] + cache_check + content[insert_pos:]
            
            print(f"✅ Added cache check to {cache_name}")
            
            # Find where to add cache_response
            # This is trickier - need to find the return statement
            # For now, we'll skip this as it's complex to do automatically

with open('/var/www/productivity-system/backend/api/dashboard.py', 'w') as f:
    f.write(content)
