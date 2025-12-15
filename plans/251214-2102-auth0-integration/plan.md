# Auth0 Integration for Employee Account Automation

## Overview
Automate Auth0 account creation when admin adds new employee in Productivity System. PodFactory pulls user data from Auth0 automatically.

**Created**: 2025-12-14
**Status**: Planning
**Priority**: High

---

## Requirements Summary

| Feature | Implementation |
|---------|---------------|
| **Verification Email** | ❌ None - `email_verified: true` |
| **Role** | Dropdown from Auth0 (15 roles) |
| **Workspace** | Dropdown: TX (Texas), MS (Mississippi) |
| **Password** | Auto-generate + show once (like PIN) |

---

## Credentials (Configured)

| Setting | Value |
|---------|-------|
| Domain | `dev-3e23sfjnt6u107d8.us.auth0.com` |
| Client ID | `wMZcd5CTLkh4vOk63hJyNb4WWtcEylUk` |
| M2M App | POD Backend Audience MM |
| Scopes | All Management API scopes ✅ |

---

## Implementation Phases

| # | Phase | Status | Description |
|---|-------|--------|-------------|
| 1 | [Backend Setup](phase-01-backend-setup.md) | ⬜ Pending | Config, token manager, API client |
| 2 | [API Endpoints](phase-02-api-endpoints.md) | ⬜ Pending | Flask endpoints for user creation |
| 3 | [Database Schema](phase-03-database-schema.md) | ⬜ Pending | Add auth0 columns to employees |
| 4 | [Frontend Integration](phase-04-frontend-integration.md) | ⬜ Pending | Add Employee form + Auth0 trigger |
| 5 | [Testing & Deploy](phase-05-testing-deploy.md) | ⬜ Pending | Test, deploy, verify PodFactory |

---

## Architecture

```
Admin creates employee (manager.html)
        ↓
POST /api/admin/employees/create
        ↓
Backend creates employee record
        ↓
Backend calls Auth0 Management API
        ↓
Auth0 creates user + sends verification email
        ↓
PodFactory queries Auth0 → Gets new user
```

---

## Files to Create/Modify

### Create
- `backend/integrations/auth0_manager.py` - Auth0 API wrapper
- `backend/integrations/auth0_token_manager.py` - Token caching

### Modify
- `backend/config.py` - Add Auth0 config
- `backend/api/user_management.py` - Add create endpoint
- `frontend/manager.html` - Add Employee form
- `backend/.env` - Add Auth0 credentials

---

## Success Criteria

- [ ] New employees get Auth0 account automatically
- [ ] Auth0 verification email sent to employee
- [ ] PodFactory can fetch created users
- [ ] No manual Auth0 dashboard steps needed
- [ ] Rollback on Auth0 failure (no orphan records)

---

## Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| Auth0 API downtime | Low | Queue + retry mechanism |
| Token expiry | Low | Auto-refresh before expiry |
| PodFactory break | Low | No changes to PodFactory |

---

## Related Documents

- [Auth0 Research Report](../reports/researcher-251214-auth0-summary.md)
- [System Architecture](../../docs/system-architecture.md)
