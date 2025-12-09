# Productivity Tracker System

Employee productivity tracking system for manufacturing/production environments. Integrates with Connecteam (time clock) and PodFactory (production data).

## Quick Start

### Prerequisites
- Python 3.10+
- MySQL 8.0+
- Redis 6.0+
- Node.js (optional, for serving frontend)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp ../.env.local .env

# Edit .env with your database credentials
# DB_HOST=localhost
# DB_PORT=3306
# DB_NAME=productivity_tracker
# DB_USER=root
# DB_PASSWORD=your_password

# Run the server
python app.py
```

### Frontend
The frontend is static HTML/JS. Serve with any web server:

```bash
# Using Python
cd frontend
python -m http.server 8080

# Or using Node.js
npx serve frontend -p 8080
```

### Access
- Backend API: http://localhost:5000
- Frontend: http://localhost:8080
- Manager Dashboard: http://localhost:8080/manager.html
- Employee View: http://localhost:8080/employee.html
- Admin Panel: http://localhost:8080/admin.html

## Project Structure

```
productivity-system/
├── backend/           # Python Flask API
│   ├── api/          # REST endpoints
│   ├── calculations/ # Business logic
│   ├── database/     # DB layer
│   └── integrations/ # External APIs
├── frontend/         # HTML/JS UI
│   ├── js/          # Shared scripts
│   └── *.html       # Pages
├── docs/            # Documentation
└── plans/           # Implementation plans
```

## Documentation
- [Project Overview](docs/project-overview-pdr.md)
- [Codebase Summary](docs/codebase-summary.md)
- [System Architecture](docs/system-architecture.md)

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| GET /health | Health check |
| GET /api/activities | Activity data |
| GET /api/dashboard | Dashboard metrics |
| GET /api/connecteam/sync | Trigger Connecteam sync |
| GET /api/gamification/leaderboard | Employee rankings |

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| DB_HOST | MySQL host | Yes |
| DB_PORT | MySQL port | Yes |
| DB_NAME | Database name | Yes |
| DB_USER | Database user | Yes |
| DB_PASSWORD | Database password | Yes |
| REDIS_HOST | Redis host | No |
| CONNECTEAM_API_KEY | Connecteam API key | No |
| ENABLE_AUTO_SYNC | Enable auto sync | No |

## Tech Stack
- **Backend**: Python 3, Flask, APScheduler
- **Database**: MySQL, Redis
- **Frontend**: Vanilla HTML/CSS/JS
- **Integrations**: Connecteam, PodFactory
