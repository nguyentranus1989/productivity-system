# Authentication System Security Review

**Date:** 2025-12-13
**System:** Productivity Tracker System
**Scope:** Backend (Python Flask) + Frontend (Vanilla JS)

---

## Executive Summary

Current system implements TWO separate authentication mechanisms:
1. **Admin Auth** - Username/password with session tokens (database-backed)
2. **Employee Auth** - Employee ID/PIN with session tokens (database-backed)

**Critical Finding:** Password hashing uses SHA256, NOT bcrypt (despite bcrypt being in requirements.txt).

---

## 1. Current Authentication Architecture

### 1.1 Admin Authentication

**File:** `backend/api/admin_auth.py`

| Component | Implementation | Line # |
|-----------|---------------|--------|
| Password Hashing | SHA256 (WEAK) | 30-31 |
| Token Generation | `secrets.token_hex(32)` (Good) | 34-35 |
| Token Storage | Database `session_token` column | 79-87 |
| Token Expiry | 24 hours | 77 |
| Account Lockout | 5 failed attempts = 30 min lock | 67-73 |
| Audit Logging | `admin_audit_log` table | 90-93 |

**Password Hash Function (Line 30-31):**
```python
def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()
```

**Database Schema Required:**
- `admin_users` table with columns: `id`, `username`, `password_hash`, `full_name`, `is_active`, `session_token`, `token_expires`, `last_login`, `failed_attempts`, `locked_until`
- `admin_audit_log` table with columns: `admin_id`, `action`, `details`, `ip_address`

### 1.2 Employee Authentication

**File:** `backend/api/employee_auth.py`

| Component | Implementation | Line # |
|-----------|---------------|--------|
| Credential | Employee ID + PIN | 16-17 |
| PIN Storage | Plain text comparison (CRITICAL) | 30 |
| Token Generation | `secrets.token_urlsafe(32)` (Good) | 34 |
| Token Storage | Database `login_token` column | 38-42 |
| Token Expiry | 24 hours | 35 |

**Critical Issue (Line 30):**
```python
if not result or result['pin'] != pin:
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
```
PIN is compared directly - stored in PLAIN TEXT.

**Database Schema Required:**
- `employee_auth` table with columns: `employee_id`, `pin`, `login_token`, `token_expires`, `last_login`

### 1.3 Shop Floor Authentication

**File:** `frontend/login.html` (Line 317, 496)

| Component | Implementation |
|-----------|---------------|
| PIN | Hardcoded in JavaScript: `'1234'` |
| Token | Client-generated: `'shopfloor_' + Date.now()` |
| Validation | Client-side only, no backend call |

**Critical Issue (Line 317):**
```javascript
const SHOP_FLOOR_PIN = '1234';  // Change this to your desired PIN
```

---

## 2. API Key Authentication

**File:** `backend/api/auth.py`

| Component | Implementation | Line # |
|-----------|---------------|--------|
| Key Validation | `X-API-Key` header or `api_key` query param | 19-26 |
| Key Comparison | Direct string comparison | 32 |
| Rate Limiting | Redis-based, 60 req/min | 84-141 |
| Signature Auth | HMAC-SHA256 for sensitive endpoints | 44-80 |

**API Key Source (Line 32):**
```python
if api_key != Config.API_KEY:
```

**Config Default (config.py Line 16):**
```python
API_KEY = os.getenv('API_KEY', 'dev-api-key-123')
```

### Hardcoded API Key Vulnerability

**File:** `backend/auth/auth_decorator.py` (Line 8)
```python
if api_key != 'dev-api-key-123':
```
This decorator has a hardcoded key, bypassing environment variable configuration.

---

## 3. Frontend Token Management

**File:** `frontend/js/auth-check.js`

| Component | Implementation | Line # |
|-----------|---------------|--------|
| Token Storage | localStorage/sessionStorage | 37-54 |
| Dev Bypass | Auth disabled on localhost | 7-17 |
| Role-Based Access | Client-side only | 26-33, 67-74 |
| Token Verification | Optional backend call (commented out) | 218-225 |

**Development Bypass (Lines 7-17):**
```javascript
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    console.log('Auth disabled for local development');
    sessionStorage.setItem('adminToken', 'local-dev-token');
    sessionStorage.setItem('userRole', 'admin');
    window.currentUserRole = 'admin';
    // ... bypasses all auth checks
}
```

---

## 4. Security Vulnerabilities Assessment

### Critical (Severity: HIGH)

| ID | Issue | Location | Risk |
|----|-------|----------|------|
| C1 | SHA256 password hashing | admin_auth.py:30 | Vulnerable to rainbow tables |
| C2 | Plain text PIN storage | employee_auth.py:30 | Database breach = all PINs exposed |
| C3 | Hardcoded shop floor PIN | login.html:317 | Anyone can view source to get PIN |
| C4 | Hardcoded API key | auth_decorator.py:8 | Bypasses env configuration |
| C5 | DB credentials in code | admin_auth.py:19-24 | Source code exposure = DB access |

### High (Severity: MEDIUM-HIGH)

| ID | Issue | Location | Risk |
|----|-------|----------|------|
| H1 | No password complexity | admin_auth.py | Weak passwords allowed |
| H2 | Long token expiry (24h) | admin_auth.py:77 | Extended attack window |
| H3 | Client-side role checking | auth-check.js:67-74 | Easily bypassed |
| H4 | Dev auth bypass in production | auth-check.js:7-17 | Could be exploited |
| H5 | No HTTPS enforcement | - | Credentials in transit |

### Medium (Severity: MEDIUM)

| ID | Issue | Location | Risk |
|----|-------|----------|------|
| M1 | No password reset flow | - | Users can't recover accounts |
| M2 | No session invalidation on password change | admin_auth.py | Old sessions remain valid |
| M3 | Token in localStorage | auth-check.js:37-45 | XSS exposure |
| M4 | No MFA/2FA | - | Single factor auth only |
| M5 | No login notifications | - | Undetected account compromise |

---

## 5. Database Schema Analysis

### Required Tables (Based on Code)

**admin_users:**
```sql
CREATE TABLE admin_users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,   -- Currently SHA256 hex
    full_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    session_token VARCHAR(64),             -- Random hex token
    token_expires DATETIME,
    last_login DATETIME,
    failed_attempts INT DEFAULT 0,
    locked_until DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**employee_auth:**
```sql
CREATE TABLE employee_auth (
    id INT PRIMARY KEY AUTO_INCREMENT,
    employee_id INT NOT NULL,
    pin VARCHAR(10),                        -- Plain text PIN!
    login_token VARCHAR(64),
    token_expires DATETIME,
    last_login DATETIME,
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);
```

**admin_audit_log:**
```sql
CREATE TABLE admin_audit_log (
    id INT PRIMARY KEY AUTO_INCREMENT,
    admin_id INT NOT NULL,
    action VARCHAR(50),
    details TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 6. Missing Features for Professional Auth

| Feature | Current State | Required |
|---------|--------------|----------|
| Admin creates employee accounts | Not implemented | YES |
| Password complexity enforcement | None | YES |
| bcrypt password hashing | Unused | YES |
| PIN hashing | None | YES |
| Password reset flow | None | YES |
| Email verification | None | OPTIONAL |
| MFA/2FA | None | RECOMMENDED |
| JWT tokens | Session tokens | OPTIONAL |
| Role management (admin levels) | None | RECOMMENDED |
| Password expiry | None | RECOMMENDED |
| Session management UI | None | RECOMMENDED |

---

## 7. Recommended Implementation Plan

### Phase 1: Critical Security Fixes (Priority: IMMEDIATE)

1. **Replace SHA256 with bcrypt for admin passwords**
   - File: `backend/api/admin_auth.py`
   - bcrypt is already in requirements.txt

2. **Hash employee PINs with bcrypt**
   - File: `backend/api/employee_auth.py`
   - Migrate existing PINs

3. **Move shop floor PIN to database/config**
   - File: `frontend/login.html`
   - Add backend validation endpoint

4. **Remove hardcoded credentials**
   - File: `backend/api/admin_auth.py` (DB creds)
   - File: `backend/auth/auth_decorator.py` (API key)

5. **Remove dev auth bypass in production**
   - File: `frontend/js/auth-check.js`
   - Add environment check

### Phase 2: Admin User Management

1. **Admin CRUD endpoints:**
   - `POST /api/admin/users` - Create user
   - `GET /api/admin/users` - List users
   - `PUT /api/admin/users/:id` - Update user
   - `DELETE /api/admin/users/:id` - Deactivate user

2. **Employee credential management:**
   - `POST /api/admin/employees/:id/set-pin` - Set/reset PIN
   - `GET /api/admin/employees/:id/auth-status` - View auth status

3. **Password policies:**
   - Minimum 8 characters
   - Require uppercase, lowercase, number
   - Block common passwords

### Phase 3: Enhanced Security

1. **Shorter token expiry** (4-8 hours)
2. **Password reset via email**
3. **Session invalidation on password change**
4. **Login notifications**
5. **Consider JWT for stateless auth**

---

## 8. Files Requiring Changes

| File | Changes Needed |
|------|----------------|
| `backend/api/admin_auth.py` | bcrypt, remove hardcoded creds |
| `backend/api/employee_auth.py` | PIN hashing |
| `backend/auth/auth_decorator.py` | Remove hardcoded API key |
| `frontend/login.html` | Backend shop floor validation |
| `frontend/js/auth-check.js` | Remove dev bypass, add env check |
| `backend/config.py` | Add new auth settings |
| **NEW** `backend/api/user_management.py` | Admin CRUD endpoints |

---

## 9. Code Examples for Fixes

### Fix C1: bcrypt for Admin Passwords

```python
# backend/api/admin_auth.py
import bcrypt

def hash_password(password):
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password, hashed):
    """Verify password against bcrypt hash"""
    return bcrypt.checkpw(password.encode(), hashed.encode())
```

### Fix C2: bcrypt for Employee PINs

```python
# backend/api/employee_auth.py
import bcrypt

def hash_pin(pin):
    """Hash PIN using bcrypt"""
    salt = bcrypt.gensalt(rounds=10)
    return bcrypt.hashpw(pin.encode(), salt).decode()

def verify_pin(pin, hashed):
    """Verify PIN against bcrypt hash"""
    return bcrypt.checkpw(pin.encode(), hashed.encode())
```

### Fix C3: Backend Shop Floor Validation

```python
# backend/api/shop_floor_auth.py
from flask import Blueprint, request, jsonify
from database.db_manager import get_db
import bcrypt

shop_floor_bp = Blueprint('shop_floor', __name__)

@shop_floor_bp.route('/api/shopfloor/login', methods=['POST'])
def shop_floor_login():
    data = request.json
    pin = data.get('pin')

    result = get_db().execute_one("""
        SELECT pin_hash FROM shop_floor_settings WHERE id = 1
    """)

    if result and bcrypt.checkpw(pin.encode(), result['pin_hash'].encode()):
        return jsonify({'success': True})

    return jsonify({'success': False, 'message': 'Invalid PIN'}), 401
```

---

## 10. Summary

### Current State
- Two auth systems (admin, employee) with basic implementation
- Critical security flaws: SHA256 hashing, plain text PINs, hardcoded secrets
- No admin user management UI
- Client-side auth bypass on localhost

### Required Actions
1. **Immediate:** Fix password/PIN hashing, remove hardcoded credentials
2. **Short-term:** Implement admin user management endpoints
3. **Medium-term:** Add password policies, reset flow, session management

### Risk Level
**HIGH** - Current implementation has multiple exploitable vulnerabilities that could lead to:
- Mass credential exposure on database breach
- Unauthorized admin access via source code inspection
- Session hijacking via XSS

---

## Appendix: File Locations

| File | Path |
|------|------|
| Admin Auth | `C:\Users\12104\Projects\Productivity_system\backend\api\admin_auth.py` |
| Employee Auth | `C:\Users\12104\Projects\Productivity_system\backend\api\employee_auth.py` |
| API Auth | `C:\Users\12104\Projects\Productivity_system\backend\api\auth.py` |
| Auth Decorator | `C:\Users\12104\Projects\Productivity_system\backend\auth\auth_decorator.py` |
| Config | `C:\Users\12104\Projects\Productivity_system\backend\config.py` |
| Frontend Auth Check | `C:\Users\12104\Projects\Productivity_system\frontend\js\auth-check.js` |
| Admin Auth Functions | `C:\Users\12104\Projects\Productivity_system\frontend\admin_auth_functions.js` |
| Admin Auth Script | `C:\Users\12104\Projects\Productivity_system\frontend\admin_auth_script.js` |
| Login Page | `C:\Users\12104\Projects\Productivity_system\frontend\login.html` |

---

## Unresolved Questions

1. **Database schema verification:** Are `admin_users`, `employee_auth`, and `admin_audit_log` tables already created? Need to verify actual schema.

2. **bcrypt migration strategy:** How to migrate existing SHA256 hashes and plain text PINs to bcrypt without forcing all users to reset?

3. **Production environment:** Is the dev auth bypass (localhost check) actually hitting production, or is there a build process that removes it?

4. **Admin initial setup:** How was the first admin user created? Is there a setup script or manual SQL insert?

5. **Shop floor PIN:** Is there a UI anywhere to change the shop floor PIN, or is it always `1234`?
