"""Add manual caching to leaderboard endpoint"""

# Read dashboard.py
with open('/var/www/productivity-system/backend/api/dashboard.py', 'r') as f:
    lines = f.readlines()

# Add import at the top if not present
import_added = False
for i in range(30):
    if 'from flask import' in lines[i]:
        # Add import after this line
        if 'endpoint_cache' not in ''.join(lines):
            lines.insert(i+1, 'from endpoint_cache import get_cached_response, cache_response\n')
            import_added = True
            break

# Find the get_leaderboard function
for i in range(len(lines)):
    if 'def get_leaderboard():' in lines[i]:
        # Find the start of the function body
        func_start = i + 1
        
        # Check if caching is already added
        if 'get_cached_response' not in ''.join(lines[func_start:func_start+10]):
            # Add caching check at the beginning
            indent = '    '
            cache_code = [
                f'{indent}# Check cache first\n',
                f'{indent}cached = get_cached_response("leaderboard", cache_seconds=10)\n',
                f'{indent}if cached:\n',
                f'{indent}    return jsonify(cached)\n',
                f'{indent}\n'
            ]
            
            # Insert cache check
            for j, code_line in enumerate(cache_code):
                lines.insert(func_start + j, code_line)
            
            # Now find where the function returns data
            # Look for return jsonify
            for j in range(func_start + len(cache_code), len(lines)):
                if 'return jsonify(leaderboard)' in lines[j]:
                    # Add caching before return
                    lines.insert(j, f'{indent}cache_response("leaderboard", leaderboard, cache_seconds=10)\n')
                    break
            
            print("✅ Added caching to get_leaderboard")
            break

# Save the modified file
with open('/var/www/productivity-system/backend/api/dashboard.py', 'w') as f:
    f.writelines(lines)
