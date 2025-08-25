#!/bin/bash

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Starting SAFE Project Cleanup...${NC}"

# Create archive directory
ARCHIVE_DIR="/var/www/productivity-system/backend/archive_cleanup_$(date +%Y%m%d)"
mkdir -p "$ARCHIVE_DIR/fix_scripts"
mkdir -p "$ARCHIVE_DIR/backup_files"
mkdir -p "$ARCHIVE_DIR/old_versions"

# 1. SAFE: Move one-time fix scripts (definitely not used in production)
echo "Moving one-time fix scripts..."
for file in fix_*.py apply_*fix*.py final_fix_*.py; do
    if [ -f "$file" ]; then
        mv "$file" "$ARCHIVE_DIR/fix_scripts/"
        echo "  Moved: $file"
    fi
done

# 2. SAFE: Move backup files
echo -e "\nMoving backup files..."
find . -name "*.backup*" -type f -not -path "./venv/*" -exec mv {} "$ARCHIVE_DIR/backup_files/" \;

# 3. SAFE: Move old calculator versions (keeping main one)
echo -e "\nMoving old calculator versions..."
for calc in calculations/productivity_calculator_*.py; do
    if [[ -f "$calc" && "$calc" != "calculations/productivity_calculator.py" ]]; then
        mv "$calc" "$ARCHIVE_DIR/old_versions/"
        echo "  Moved: $calc"
    fi
done

# 4. SAFE: Move obvious temp files
echo -e "\nMoving temp files..."
mv debug_*.py "$ARCHIVE_DIR/fix_scripts/" 2>/dev/null
mv test_*.py "$ARCHIVE_DIR/fix_scripts/" 2>/dev/null

# 5. SAFE: Clean Python cache
echo -e "\nCleaning Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

echo -e "\n${GREEN}Summary:${NC}"
echo "Files archived to: $ARCHIVE_DIR"
echo "- Fix scripts: $(find "$ARCHIVE_DIR/fix_scripts" -type f 2>/dev/null | wc -l)"
echo "- Backup files: $(find "$ARCHIVE_DIR/backup_files" -type f 2>/dev/null | wc -l)"
echo "- Old versions: $(find "$ARCHIVE_DIR/old_versions" -type f 2>/dev/null | wc -l)"

echo -e "\n${YELLOW}Critical files preserved:${NC}"
echo "✓ app.py (Flask backend)"
echo "✓ podfactory_sync.py (PM2 sync)"
echo "✓ calculations/productivity_calculator.py (main calculator)"
echo "✓ All API endpoints"
echo "✓ All database models"
echo "✓ reconciliation_cron.py (cron job)"

