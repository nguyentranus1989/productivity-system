#!/usr/bin/env python3
"""
Show folder structure and all files for cleanup analysis
"""
import os
from datetime import datetime
import fnmatch

def get_file_size(file_path):
    """Get file size in human readable format"""
    try:
        size = os.path.getsize(file_path)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}TB"
    except:
        return "N/A"

def get_file_modified_date(file_path):
    """Get file modification date"""
    try:
        timestamp = os.path.getmtime(file_path)
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
    except:
        return "N/A"

def scan_directory(root_dir='.'):
    """Scan directory and organize files by type"""
    
    # Categories of files
    categories = {
        'Python Scripts': [],
        'Test Scripts': [],
        'Backup Files': [],
        'Log Files': [],
        'Config Files': [],
        'Database Files': [],
        'Documentation': [],
        'Frontend Files': [],
        'Cache Files': [],
        'Temporary Files': [],
        'Other Files': []
    }
    
    # Patterns for categorization
    patterns = {
        'Test Scripts': ['test_*.py', '*_test.py', 'check_*.py', 'diagnose_*.py', 'fix_*.py'],
        'Backup Files': ['*.backup*', '*.bak', '*.old', '*_backup*'],
        'Log Files': ['*.log', '*.txt'],
        'Config Files': ['*.json', '*.yaml', '*.yml', '*.ini', '*.conf'],
        'Database Files': ['*.db', '*.sql', '*.sqlite'],
        'Documentation': ['*.md', '*.rst', '*.doc*', '*.pdf'],
        'Frontend Files': ['*.html', '*.css', '*.js'],
        'Cache Files': ['__pycache__', '*.pyc', '*.pyo', '.cache'],
        'Temporary Files': ['*.tmp', '*.temp', '~*', '.~*']
    }
    
    # Walk through directory
    for root, dirs, files in os.walk(root_dir):
        # Skip venv and .git directories
        dirs[:] = [d for d in dirs if d not in ['venv', '.git', '__pycache__', '.idea', 'node_modules']]
        
        level = root.replace(root_dir, '').count(os.sep)
        indent = ' ' * 2 * level
        folder_name = os.path.basename(root)
        
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, root_dir)
            size = get_file_size(file_path)
            modified = get_file_modified_date(file_path)
            
            # Categorize file
            categorized = False
            for category, file_patterns in patterns.items():
                for pattern in file_patterns:
                    if fnmatch.fnmatch(file.lower(), pattern.lower()):
                        categories[category].append({
                            'path': rel_path,
                            'size': size,
                            'modified': modified,
                            'name': file
                        })
                        categorized = True
                        break
                if categorized:
                    break
            
            # If not categorized, check if it's a Python file or other
            if not categorized:
                if file.endswith('.py'):
                    categories['Python Scripts'].append({
                        'path': rel_path,
                        'size': size,
                        'modified': modified,
                        'name': file
                    })
                else:
                    categories['Other Files'].append({
                        'path': rel_path,
                        'size': size,
                        'modified': modified,
                        'name': file
                    })
    
    return categories

def print_structure():
    """Print directory structure and categorized files"""
    print("=" * 80)
    print("PRODUCTIVITY SYSTEM - FILE STRUCTURE ANALYSIS")
    print("=" * 80)
    print(f"Directory: {os.path.abspath('.')}")
    print(f"Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # First show directory tree
    print("\nDIRECTORY STRUCTURE:")
    print("-" * 40)
    
    for root, dirs, files in os.walk('.'):
        # Skip venv and other large directories
        dirs[:] = [d for d in dirs if d not in ['venv', '.git', '__pycache__', '.idea', 'node_modules']]
        
        level = root.replace('.', '').count(os.sep)
        indent = '│   ' * level
        print(f"{indent}├── {os.path.basename(root)}/")
        
        # Don't show files in tree, we'll categorize them below
    
    # Now categorize files
    print("\n" + "=" * 80)
    print("FILES BY CATEGORY:")
    print("=" * 80)
    
    categories = scan_directory()
    
    # Define what's likely safe to delete
    safe_to_delete = ['Test Scripts', 'Backup Files', 'Cache Files', 'Temporary Files']
    maybe_delete = ['Log Files']
    
    # Print categories
    for category, files in categories.items():
        if files:  # Only show categories with files
            print(f"\n{category.upper()} ({len(files)} files)")
            print("-" * 40)
            
            if category in safe_to_delete:
                print("🗑️  LIKELY SAFE TO DELETE")
            elif category in maybe_delete:
                print("⚠️  REVIEW BEFORE DELETING")
            else:
                print("📁 KEEP THESE FILES")
            
            print("-" * 40)
            
            # Sort files by modified date
            files.sort(key=lambda x: x['modified'], reverse=True)
            
            for file in files[:20]:  # Show max 20 files per category
                print(f"  {file['name']:<40} {file['size']:>8} {file['modified']}")
                if len(file['path']) > 50:
                    print(f"    Path: {file['path']}")
            
            if len(files) > 20:
                print(f"  ... and {len(files) - 20} more files")
    
    # Summary
    print("\n" + "=" * 80)
    print("CLEANUP RECOMMENDATIONS:")
    print("=" * 80)
    
    total_test_files = len(categories['Test Scripts'])
    total_backup_files = len(categories['Backup Files'])
    total_cache_files = len(categories['Cache Files'])
    total_temp_files = len(categories['Temporary Files'])
    
    print(f"\n🗑️  SAFE TO DELETE:")
    print(f"  - {total_test_files} test/diagnostic scripts (test_*.py, fix_*.py, check_*.py)")
    print(f"  - {total_backup_files} backup files (*.backup*, *.bak)")
    print(f"  - {total_cache_files} cache files (__pycache__, *.pyc)")
    print(f"  - {total_temp_files} temporary files")
    
    print(f"\n⚠️  REVIEW FIRST:")
    print(f"  - {len(categories['Log Files'])} log files (might want to keep recent ones)")
    
    print(f"\n📁 KEEP:")
    print(f"  - All files in 'api/', 'calculations/', 'database/', 'integrations/' folders")
    print(f"  - Main scripts: app.py, config.py, start_productivity_system.bat")
    print(f"  - sync_connecteam.py, podfactory_sync.py (your sync scripts)")

if __name__ == "__main__":
    print_structure()