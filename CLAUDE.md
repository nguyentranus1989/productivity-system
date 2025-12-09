# CLAUDE.md - Productivity Tracker System

## Project Context
Employee productivity tracking system for manufacturing. Python Flask backend + vanilla HTML/JS frontend.

## Quick Commands

```bash
# Start backend
cd backend && python app.py

# Serve frontend
cd frontend && python -m http.server 8080
```

## Key Files

### Backend Entry Points
- `backend/app.py` - Flask application
- `backend/config.py` - Configuration

### Core Logic
- `backend/calculations/productivity_calculator.py` - Score calculation
- `backend/calculations/idle_detector.py` - Idle detection
- `backend/integrations/connecteam_sync.py` - Time clock sync

### Frontend Pages
- `frontend/manager.html` - Main dashboard (219KB)
- `frontend/employee.html` - Employee view
- `frontend/intelligent-schedule.html` - Scheduling

## API Patterns
- All API routes prefixed with `/api/`
- Auth via API key header: `X-API-Key`
- CORS enabled for all origins

## Database
- MySQL with tables: `employees`, `activity_logs`, `connecteam_shifts`, `daily_scores`
- Redis for caching

## Code Style
- Python: Flask blueprints, snake_case
- JS: Vanilla JS, inline in HTML files
- No TypeScript, no React

## Common Tasks

### Add new API endpoint
1. Create/edit file in `backend/api/`
2. Register blueprint in `backend/app.py`

### Modify productivity calculation
Edit `backend/calculations/productivity_calculator.py`

### Update dashboard
Edit `frontend/manager.html` (large file, search for function names)

## Known Issues
- Large HTML files (manager.html 219KB) - hard to navigate
- Timezone: Central Time (America/Chicago)
- Production IP: 134.199.194.237
