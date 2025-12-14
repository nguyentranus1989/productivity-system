# Production Deployment State Report

*Generated: 2025-12-14*

## Executive Summary

Production server at `134.199.194.237` runs a Flask+NGINX stack managed by PM2. **Existing deployment workflow uses git-pull strategy** via SSH with minimal downtime. WebFetch returned SSL certificate error, indicating HTTPS is configured but cert may have issues.

---

## Current Production Architecture

```
Internet → NGINX (80/443) → Flask (:5000)
                         → Static HTML files
                         ↓
            PM2 Process Manager
            ├── flask-backend (app.py)
            └── podfactory-sync (sync_wrapper.py)
                         ↓
            MySQL + Redis + External APIs
```

### Server Details
| Item | Value |
|------|-------|
| IP | 134.199.194.237 |
| Path | /var/www/productivity-system |
| Process Manager | PM2 |
| Web Server | NGINX |
| Python | 3.10+ (venv) |

### Running Processes (via PM2)
1. `flask-backend` - Main Flask API
2. `podfactory-sync` - Continuous sync wrapper

---

## Existing Deployment Workflow

**File**: `deploy.sh`

```bash
# Current process:
1. git add . && git commit -m "$MESSAGE"
2. git push
3. SSH to production:
   - cd /var/www/productivity-system
   - git pull
   - cd backend && source venv/bin/activate
   - pm2 restart flask-backend
   - pm2 restart podfactory-sync
```

### Pros
- Simple, battle-tested
- Git history preserved on server
- ~5-10 second downtime during PM2 restart

### Cons
- Brief downtime during restart
- No rollback mechanism
- Manual dependency updates

---

## Deployment Options Analysis

### Option 1: Enhanced Current (Recommended)

**Zero-downtime upgrade to existing workflow:**

```bash
# On production server:
pm2 reload flask-backend  # graceful reload vs restart
```

**Changes needed:**
- Use `pm2 reload` instead of `pm2 restart`
- Add `pip install -r requirements.txt` if deps changed
- Add health check before/after

**Downtime**: Near-zero (graceful reload)
**Effort**: Low
**Risk**: Low

### Option 2: Blue-Green with PM2

**Two instances, switch traffic:**

```bash
pm2 start app.py --name flask-blue -i 1
pm2 start app.py --name flask-green -i 1
# NGINX routes to active instance
# Deploy to inactive, then switch
```

**Downtime**: Zero
**Effort**: Medium
**Risk**: Medium (config complexity)

### Option 3: Docker Containers

**Containerize app for consistent deploys:**

```dockerfile
FROM python:3.10-slim
COPY backend/ /app
RUN pip install -r requirements.txt
CMD ["python", "app.py"]
```

**Downtime**: Zero (with docker-compose rolling update)
**Effort**: High (initial setup)
**Risk**: Medium (new infrastructure)

---

## Recommended Deployment Approach

### Immediate (Today)

Use existing `deploy.sh` with one modification:

```bash
# Change line:
pm2 restart flask-backend
# To:
pm2 reload flask-backend --update-env
```

### Short-term Improvements

1. **Add pre-deploy checks**:
   ```bash
   ssh root@134.199.194.237 "pm2 status flask-backend"
   ```

2. **Auto-install deps**:
   ```bash
   pip install -r requirements.txt --quiet
   ```

3. **Post-deploy health check**:
   ```bash
   curl -sf http://134.199.194.237/health || pm2 restart flask-backend
   ```

### Updated deploy.sh (Proposed)

```bash
#!/bin/bash
MESSAGE=${1:-"Update from local development"}

echo "Deploying: $MESSAGE"

git add .
git commit -m "$MESSAGE"
git push

echo "Updating production server..."
ssh root@134.199.194.237 << 'ENDSSH'
cd /var/www/productivity-system
git pull

cd backend
source venv/bin/activate
pip install -r requirements.txt --quiet

pm2 reload flask-backend --update-env
pm2 reload podfactory-sync --update-env

# Health check
sleep 3
curl -sf http://localhost:5000/health && echo "Health check passed" || echo "WARNING: Health check failed"
ENDSSH

echo "Deployment complete!"
echo "Check: http://134.199.194.237"
```

---

## URL/IP Access Considerations

### Current State
- Direct IP access: `http://134.199.194.237`
- HTTPS attempted (cert error suggests Let's Encrypt or self-signed)

### Recommendations
1. **Keep same IP** - No DNS changes needed
2. **Fix SSL cert** - Renew Let's Encrypt or check NGINX config
3. **Consider domain** - Easier cert management, professional appearance

---

## Pre-Deployment Checklist

- [ ] Ensure SSH access: `ssh root@134.199.194.237`
- [ ] Verify PM2 status: `pm2 status`
- [ ] Check disk space: `df -h`
- [ ] Backup database (if schema changes)
- [ ] Test locally first

---

## SSL Certificate Issue

WebFetch returned: `unable to verify the first certificate`

**Likely causes:**
1. Self-signed cert
2. Expired Let's Encrypt cert
3. Incomplete cert chain

**To diagnose (run on server):**
```bash
sudo certbot certificates
# or
openssl s_client -connect 134.199.194.237:443 -servername 134.199.194.237
```

---

## Summary

| Aspect | Current | Recommended |
|--------|---------|-------------|
| Method | git pull + pm2 restart | git pull + pm2 reload |
| Downtime | ~5-10 sec | <1 sec |
| Rollback | git revert + redeploy | same |
| Same URL | Yes | Yes |

**Bottom line**: Current workflow is solid. Minor tweak (`reload` vs `restart`) achieves near-zero downtime. No infrastructure changes needed.
