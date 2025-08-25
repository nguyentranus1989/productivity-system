#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}AUTO-FIXING CLOCKED HOURS ISSUE${NC}"
echo -e "${GREEN}========================================${NC}"

# Step 1: Backup the dashboard.py file
echo -e "${YELLOW}Step 1: Creating backup...${NC}"
cp /var/www/productivity-system/backend/api/dashboard.py \
   /var/www/productivity-system/backend/api/dashboard.py.backup_$(date +%Y%m%d_%H%M%S)
echo -e "${GREEN}✓ Backup created${NC}"

# Step 2: Fix the dashboard.py file
echo -e "${YELLOW}Step 2: Fixing dashboard.py...${NC}"

# Create Python script to fix the file
cat > /tmp/fix_dashboard.py << 'PYTHON'
import re

# Read the dashboard.py file
with open('/var/www/productivity-system/backend/api/dashboard.py', 'r') as f:
    content = f.read()

# Store original for comparison
original_content = content

# Fix 1: Replace the main clocked_hours calculation
old_pattern1 = r'\(SELECT SUM\(clocked_minutes\) / 60\.0 FROM daily_scores WHERE employee_id = e\.id AND score_date BETWEEN %s AND %s\) as clocked_hours'
new_replacement1 = """(SELECT COALESCE(SUM(
                    TIMESTAMPDIFF(MINUTE, ct.clock_in, COALESCE(ct.clock_out, NOW()))
                ) / 60.0, 0)
                FROM clock_times ct
                WHERE ct.employee_id = e.id 
                AND DATE(ct.clock_in) BETWEEN %s AND %s) as clocked_hours"""

content = re.sub(old_pattern1, new_replacement1, content)

# Fix 2: Replace idle hours calculation (if it exists)
old_pattern2 = r'\(SELECT SUM\(clocked_minutes - active_minutes\) / 60\.0'
new_replacement2 = """(SELECT COALESCE(
                    (SELECT SUM(TIMESTAMPDIFF(MINUTE, ct.clock_in, COALESCE(ct.clock_out, NOW()))) 
                     FROM clock_times ct 
                     WHERE ct.employee_id = e.id AND DATE(ct.clock_in) BETWEEN %s AND %s) -
                    (SELECT SUM(active_minutes) 
                     FROM daily_scores 
                     WHERE employee_id = e.id AND score_date BETWEEN %s AND %s)
                ) / 60.0, 0)"""

if 'clocked_minutes - active_minutes' in content:
    content = re.sub(old_pattern2, new_replacement2, content, count=1)

# Check if changes were made
if content != original_content:
    # Write the fixed content back
    with open('/var/www/productivity-system/backend/api/dashboard.py', 'w') as f:
        f.write(content)
    print("✓ Fixed dashboard.py successfully")
    print("  - Replaced clocked_hours calculation to use clock_times instead of daily_scores")
else:
    print("⚠ No changes needed - file might already be fixed")
PYTHON

python3 /tmp/fix_dashboard.py

# Step 3: Test the fix with Man Nguyen
echo -e "${YELLOW}Step 3: Testing the fix...${NC}"

mysql -h db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com \
      -P 25060 -u doadmin -p'AVNS_OWqdUdZ2Nw_YCkGI5Eu' \
      productivity_tracker \
      -e "SELECT 
            e.name,
            (SELECT COALESCE(SUM(
                TIMESTAMPDIFF(MINUTE, ct.clock_in, COALESCE(ct.clock_out, NOW()))
            ) / 60.0, 0)
             FROM clock_times ct
             WHERE ct.employee_id = e.id 
             AND DATE(ct.clock_in) = CURDATE()) as clocked_hours_fixed,
            (SELECT COALESCE(SUM(clocked_minutes) / 60.0, 0) 
             FROM daily_scores 
             WHERE employee_id = e.id 
             AND score_date = CURDATE()) as clocked_hours_old
          FROM employees e
          WHERE e.name = 'Man Nguyen';"

# Step 4: Restart PM2
echo -e "${YELLOW}Step 4: Restarting backend...${NC}"
pm2 restart productivity-backend
sleep 3

# Step 5: Verify PM2 is running
pm2_status=$(pm2 list | grep productivity-backend | grep online)
if [ -n "$pm2_status" ]; then
    echo -e "${GREEN}✓ Backend restarted successfully${NC}"
else
    echo -e "${RED}✗ Backend restart failed - check PM2 logs${NC}"
    pm2 logs productivity-backend --lines 20
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}FIX COMPLETED!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Check the Cost Analysis dashboard - Man Nguyen should show 6.4 hours"
echo "2. Monitor PM2 logs: pm2 logs productivity-backend"
echo "3. If issues, restore backup: cp /var/www/productivity-system/backend/api/dashboard.py.backup_* /var/www/productivity-system/backend/api/dashboard.py"
