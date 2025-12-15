# Phase 01: Backend Setup

## Context
- **Parent Plan**: [plan.md](plan.md)
- **Dependencies**: None
- **Docs**: [Auth0 Research](../reports/researcher-251214-auth0-summary.md)

---

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-14 |
| Description | Set up Auth0 config, token manager, API client |
| Priority | High |
| Implementation Status | ⬜ Not Started |
| Review Status | ⬜ Not Reviewed |

---

## Key Insights

1. Auth0 M2M app already configured with full scopes
2. Token expires in 24 hours - need caching + auto-refresh
3. Follow existing pattern from `connecteam_sync.py`

---

## Requirements

1. Add Auth0 credentials to `config.py`
2. Create token manager (cache token, refresh before expiry)
3. Create API client (HTTP calls with retry logic)
4. Add credentials to `.env` and `.env.production`

---

## Related Code Files

| File | Purpose |
|------|---------|
| `backend/config.py` | Add Auth0 config vars |
| `backend/integrations/connecteam_sync.py` | Reference pattern |
| `backend/.env` | Local credentials |

---

## Implementation Steps

### Step 1: Update config.py
```python
# Add to Config class
AUTH0_DOMAIN = os.getenv('AUTH0_DOMAIN')
AUTH0_CLIENT_ID = os.getenv('AUTH0_CLIENT_ID')
AUTH0_CLIENT_SECRET = os.getenv('AUTH0_CLIENT_SECRET')
AUTH0_AUDIENCE = os.getenv('AUTH0_AUDIENCE')  # Management API URL
```

### Step 2: Create auth0_token_manager.py
```python
# backend/integrations/auth0_token_manager.py
"""
Auth0 Token Manager - Handles token acquisition and caching
"""
import time
import requests
from config import Config

class Auth0TokenManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.token = None
            cls._instance.token_expires_at = 0
        return cls._instance

    def get_access_token(self):
        """Get valid access token, refresh if expired"""
        # Refresh 5 minutes before expiry
        if time.time() < self.token_expires_at - 300:
            return self.token

        return self._refresh_token()

    def _refresh_token(self):
        """Request new token from Auth0"""
        response = requests.post(
            f"https://{Config.AUTH0_DOMAIN}/oauth/token",
            json={
                "client_id": Config.AUTH0_CLIENT_ID,
                "client_secret": Config.AUTH0_CLIENT_SECRET,
                "audience": f"https://{Config.AUTH0_DOMAIN}/api/v2/",
                "grant_type": "client_credentials"
            },
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code != 200:
            raise Exception(f"Token request failed: {response.text}")

        data = response.json()
        self.token = data['access_token']
        self.token_expires_at = time.time() + data['expires_in']

        return self.token

# Singleton instance
token_manager = Auth0TokenManager()
```

### Step 3: Create auth0_manager.py
```python
# backend/integrations/auth0_manager.py
"""
Auth0 Manager - High-level API for user management
"""
import requests
from datetime import datetime
from config import Config
from integrations.auth0_token_manager import token_manager

class Auth0Manager:
    BASE_URL = f"https://{Config.AUTH0_DOMAIN}/api/v2"

    @staticmethod
    def create_employee_account(employee_data):
        """
        Create Auth0 account for employee

        Args:
            employee_data: {
                'employee_id': int,
                'name': str,
                'email': str,
                'department': str (optional)
            }

        Returns:
            {'success': bool, 'user_id': str, 'message': str}
        """
        try:
            token = token_manager.get_access_token()

            payload = {
                "email": employee_data['email'],
                "name": employee_data['name'],
                "user_metadata": {
                    "employee_id": employee_data['employee_id'],
                    "full_name": employee_data['name'],
                    "department": employee_data.get('department', ''),
                    "timezone": "America/Chicago"
                },
                "app_metadata": {
                    "employee_id": employee_data['employee_id'],
                    "created_by": "productivity_system",
                    "created_at": datetime.utcnow().isoformat() + "Z"
                },
                "connection": "Username-Password-Authentication",
                "verify_email": True,
                "email_verified": False
            }

            response = requests.post(
                f"{Auth0Manager.BASE_URL}/users",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=15
            )

            if response.status_code == 201:
                user_data = response.json()
                return {
                    'success': True,
                    'user_id': user_data['user_id'],
                    'email': user_data['email'],
                    'message': 'Auth0 account created'
                }
            elif response.status_code == 409:
                return {
                    'success': False,
                    'message': 'User already exists in Auth0'
                }
            else:
                return {
                    'success': False,
                    'message': f"Auth0 error: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return {
                'success': False,
                'message': f"Auth0 creation failed: {str(e)}"
            }

    @staticmethod
    def is_configured():
        """Check if Auth0 is properly configured"""
        return all([
            Config.AUTH0_DOMAIN,
            Config.AUTH0_CLIENT_ID,
            Config.AUTH0_CLIENT_SECRET
        ])
```

### Step 4: Update .env files
```bash
# Add to backend/.env and backend/.env.production
AUTH0_DOMAIN=dev-3e23sfjnt6u107d8.us.auth0.com
AUTH0_CLIENT_ID=wMZcd5CTLkh4v0k63hJyNb4WWtcEylUk
AUTH0_CLIENT_SECRET=3tXKEkucjODsPMqwOj4Mfp5nF17C9eLSUqq-h1_fng0gM9vx4_iQmKIUkOuvqkob
```

---

## Todo List

- [ ] Add Auth0 config to `config.py`
- [ ] Create `auth0_token_manager.py`
- [ ] Create `auth0_manager.py`
- [ ] Add credentials to `.env`
- [ ] Test token acquisition locally

---

## Success Criteria

- [ ] `Auth0Manager.is_configured()` returns True
- [ ] Token acquisition works (manual test)
- [ ] Token caching works (same token on second call)

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Invalid credentials | Test before proceeding |
| Network timeout | 10-15 second timeout configured |

---

## Security Considerations

- CLIENT_SECRET in env vars only (never in code)
- Token cached in memory (not persisted)
- HTTPS enforced for all Auth0 calls

---

## Next Steps

After completing this phase → Proceed to [Phase 02: API Endpoints](phase-02-api-endpoints.md)
