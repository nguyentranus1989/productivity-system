# Deployment Guide - Productivity System

**Last Updated:** 2025-12-14

## Server Details

| Item | Value |
|------|-------|
| Server IP | 134.199.194.237 |
| Domain | https://reports.podgasus.com |
| SSH Access | `ssh root@134.199.194.237` |
| App Path | `/var/www/productivity-system` |

## Architecture

```
Internet → Cloudflare (Proxy) → Server:443 (nginx) → localhost:5000 (Flask)
```

## Services (PM2)

| Service | Description | Command |
|---------|-------------|---------|
| flask-backend | Main Flask app | `pm2 restart flask-backend` |
| podfactory-sync | PodFactory data sync | `pm2 restart podfactory-sync` |
| cloudflare-tunnel | Quick tunnel (backup) | `pm2 restart cloudflare-tunnel` |

Check status: `pm2 status`

## Nginx Configuration

**Config files:**
- `/etc/nginx/sites-available/productivity` - Default server
- `/etc/nginx/sites-available/reports-podgasus` - HTTPS for reports.podgasus.com

**Key points:**
- Root: `/var/www/productivity-system/frontend`
- Default index: `login.html` (NOT index.html - was deleted)
- API proxy: `/api` → `http://localhost:5000/api`

**Reload nginx:** `nginx -t && systemctl reload nginx`

## SSL Certificates

- Location: `/etc/nginx/ssl/`
- Files: `podgasus.crt`, `podgasus.key`
- Type: Cloudflare Origin Certificate
- Expires: 2036

Local backup: `keys/podgasus.crt`, `keys/podgasus.key`

## Database

- Type: MySQL (DigitalOcean Managed)
- Host: `db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com`
- Port: 25060
- Config: `/var/www/productivity-system/backend/.env`

## Deployment Steps

### 1. Push code to GitHub
```bash
# From local machine
git push server main   # Note: 'server' remote, not 'origin'
```

### 2. Pull on server
```bash
ssh root@134.199.194.237
cd /var/www/productivity-system
git pull origin main
```

### 3. Install dependencies (if changed)
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Run migrations (if needed)
```bash
python scripts/add_clock_times_unique_constraint.py
python scripts/add_performance_indexes.py
```

### 5. Restart services
```bash
pm2 restart flask-backend --update-env
pm2 status
```

### 6. Verify
```bash
curl -s http://127.0.0.1:5000/api/connecteam/status
```

## Troubleshooting

### Site shows 403 Forbidden
- Check if `login.html` exists in frontend folder
- Nginx config should use `index login.html` not `index index.html`
- Reload nginx: `systemctl reload nginx`

### Flask not starting
- Check logs: `pm2 logs flask-backend --lines 50`
- Common issue: "Too many connections" - kill stale MySQL connections
- Check .env file exists and has correct DB credentials

### Too many MySQL connections
```bash
cd /var/www/productivity-system/backend
source venv/bin/activate
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
import mysql.connector
conn = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    port=int(os.getenv('DB_PORT', 25060)),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME')
)
cursor = conn.cursor()
cursor.execute('SHOW PROCESSLIST')
for r in cursor.fetchall():
    if r[4] == 'Sleep' and r[3] == 'productivity_tracker':
        cursor.execute(f'KILL {r[0]}')
        print(f'Killed connection {r[0]}')
conn.close()
"
```

### Port 5000 not listening
- Flask might be initializing - wait 10-15 seconds
- Check for errors: `pm2 logs flask-backend --err --lines 20`
- Restart: `pm2 restart flask-backend`

## Git Remotes (Local)

```bash
origin  https://github.com/nguyentranus1989/productivity-hub.git    # Personal backup
server  https://github.com/nguyentranus1989/productivity-system.git # Production
```

**Always push to `server` for production deployment.**

## Key Files Modified (2025-12-14)

| File | Change |
|------|--------|
| `backend/integrations/connecteam_sync.py` | Removed hardcoded API keys, fixed bugs |
| `backend/integrations/connecteam_client.py` | Fixed timezone bug, removed hardcoded keys |
| `backend/api/auth.py` | Rate limiter now fails closed |
| `backend/database/db_manager.py` | Unique pool name per process |
| `backend/scripts/add_clock_times_unique_constraint.py` | New migration script |

## Cloudflare

- Domain managed by external team
- Origin certificates provided in `keys/` folder
- DNS proxied through Cloudflare (orange cloud)
- No direct Cloudflare dashboard access

## Quick Tunnel (Backup Access)

If main domain fails, use quick tunnel:
```bash
pm2 restart cloudflare-tunnel
pm2 logs cloudflare-tunnel --lines 5  # Find URL like: https://xxx.trycloudflare.com
```
