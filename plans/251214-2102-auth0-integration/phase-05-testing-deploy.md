# Phase 05: Testing & Deployment

## Context
- **Parent Plan**: [plan.md](plan.md)
- **Dependencies**: All previous phases complete
- **Docs**: [Deployment Guide](../../docs/deployment-guide.md)

---

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-14 |
| Description | Test Auth0 integration, deploy to production, verify PodFactory |
| Priority | High |
| Implementation Status | ⬜ Not Started |
| Review Status | ⬜ Not Reviewed |

---

## Key Insights

1. Test locally first with real Auth0 credentials
2. Deploy to production server (134.199.194.237)
3. Verify PodFactory can see new users in Auth0

---

## Testing Checklist

### Local Testing

- [ ] Token acquisition works
- [ ] Create employee without Auth0 ✓
- [ ] Create employee with Auth0 ✓
- [ ] Duplicate email handling (409 error)
- [ ] Auth0 failure doesn't block employee creation
- [ ] Employee table shows Auth0 status
- [ ] "Create Auth0" button works for existing employees

### API Testing (curl)

```bash
# Test create employee without Auth0
curl -X POST 'http://localhost:5000/api/admin/employees/create' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-api-key-123' \
  -d '{
    "name": "Test User",
    "email": "test@colorecommerce.us",
    "create_auth0": false
  }'

# Test create employee with Auth0
curl -X POST 'http://localhost:5000/api/admin/employees/create' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-api-key-123' \
  -d '{
    "name": "Auth0 Test User",
    "email": "auth0test@colorecommerce.us",
    "create_auth0": true
  }'

# Test create Auth0 for existing employee
curl -X POST 'http://localhost:5000/api/admin/employees/99/create-auth0' \
  -H 'X-API-Key: dev-api-key-123'
```

---

## Deployment Steps

### Step 1: Push code to repository
```bash
git add .
git commit -m "feat: Auth0 integration for employee account automation"
git push origin main
```

### Step 2: Deploy to production
```bash
ssh root@134.199.194.237 "cd /var/www/productivity-system && git pull origin main"
```

### Step 3: Update production .env
```bash
ssh root@134.199.194.237 "cat >> /var/www/productivity-system/backend/.env << 'EOF'

# Auth0 Integration
AUTH0_DOMAIN=dev-3e23sfjnt6u107d8.us.auth0.com
AUTH0_CLIENT_ID=wMZcd5CTLkh4v0k63hJyNb4WWtcEylUk
AUTH0_CLIENT_SECRET=3tXKEkucjODsPMqwOj4Mfp5nF17C9eLSUqq-h1_fng0gM9vx4_iQmKIUkOuvqkob
EOF"
```

### Step 4: Run database migration
```bash
ssh root@134.199.194.237 "mysql -h db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com -P 25060 -u doadmin -p'AVNS_OWqdUdZ2Nw_YCkGI5Eu' productivity_tracker -e \"
ALTER TABLE employees
ADD COLUMN auth0_user_id VARCHAR(255) UNIQUE NULL,
ADD COLUMN auth0_sync_status ENUM('pending', 'created', 'verified', 'failed') NULL;
\""
```

### Step 5: Restart Flask
```bash
ssh root@134.199.194.237 "pm2 restart flask-backend"
```

### Step 6: Purge Cloudflare cache
```bash
curl -X POST "https://api.cloudflare.com/client/v4/zones/f64496e04490331d9b0912ad3b829599/purge_cache" \
  -H "Authorization: Bearer zT6cSLU5SZoNbQmVW1LxkWCP8Mqme3iDPOaDglo6" \
  -H "Content-Type: application/json" \
  --data '{"purge_everything":true}'
```

---

## Production Verification

### Step 1: Test API endpoint
```bash
curl -X POST 'https://reports.podgasus.com/api/admin/employees/create' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-api-key-123' \
  -d '{
    "name": "Production Test",
    "email": "prodtest@colorecommerce.us",
    "create_auth0": true
  }'
```

### Step 2: Verify in Auth0 Dashboard
1. Go to Auth0 → User Management → Users
2. Search for newly created user
3. Verify metadata is correct

### Step 3: Verify PodFactory can see user
1. Wait for PodFactory sync cycle
2. Check if new user appears in PodFactory

---

## Rollback Plan

If issues occur:

```bash
# Revert code
ssh root@134.199.194.237 "cd /var/www/productivity-system && git revert HEAD"

# Remove .env additions (manual)
ssh root@134.199.194.237 "nano /var/www/productivity-system/backend/.env"

# Restart
ssh root@134.199.194.237 "pm2 restart flask-backend"
```

Note: Database columns can remain (nullable, won't break existing code)

---

## Success Criteria

- [ ] Production API returns success
- [ ] Auth0 account created in Auth0 dashboard
- [ ] Employee receives verification email
- [ ] PodFactory can fetch new user
- [ ] No errors in Flask logs

---

## Documentation Updates

After successful deployment:
- [ ] Update `docs/system-architecture.md` with Auth0 integration
- [ ] Update `docs/codebase-summary.md` with new files
- [ ] Add Auth0 credentials to `keys/credentials-backup.txt` ✅ (already done)

---

## Next Steps

After successful deployment → Feature complete. Consider:
1. Bulk import existing employees to Auth0
2. Webhook for Auth0 email verification events
3. Role assignment during user creation
