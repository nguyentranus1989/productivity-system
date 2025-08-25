# Backend File Structure Documentation

## 📁 Main Application Files
- `app.py` - Main Flask application (PM2: flask-backend)
- `config.py` - Configuration settings
- `__init__.py` - Package initializer

## 📁 Sync & Processing Scripts
- `podfactory_sync.py` - Main PodFactory sync logic
- `sync_wrapper.py` - PM2 wrapper for continuous sync (PM2: podfactory-sync)  
- `connecteam_sync.py` - Connecteam time clock sync
- `reconciliation_cron.py` - Daily reconciliation cron job
- `force_calculate.py` - Manual score calculation trigger

## 📁 Utilities & Helpers
- `auto_reconciliation.py` - Automatic reconciliation logic
- `connecteam_reconciliation.py` - Connecteam-specific reconciliation
- `daily_reconciliation.py` - Daily reconciliation tasks
- `employee_auto_creator.py` - Auto-create employees from activities
- `health_check.py` - System health monitoring
- `import_payrates.py` - Import employee pay rates
- `show_folder_structure.py` - Display folder structure

## 📁 Data Import Scripts (One-time use, consider archiving)
- `import_historical_data.py`
- `complete_sync.py`
- `full_sync_today.py`
- `sync_today.py`

## 📁 Cache & Performance Scripts (Review needed)
- `endpoint_cache.py`
- `simple_cache.py`
- `add_cache.py`
- `add_*_cache.py` files

## 📁 Directories
- `/api` - API endpoints
- `/calculations` - Core calculation logic (ProductivityCalculator)
- `/database` - Database models and managers
- `/integrations` - External service integrations
- `/models` - Data models
- `/utils` - Utility functions
- `/tests` - Test files
- `/logs` - Log files
- `/data` - Data files

## 📁 Archive Directory
- `/archive_cleanup_20250819` - Contains all archived fix scripts and backups
