# Authentication System Review Report

**Date**: 2025-12-13
**Project**: Productivity Tracker System
**Environment**: Python Flask Backend, Vanilla JS Frontend

---

## Executive Summary

Current auth system has **separate flows for 3 user types**: Admin, Employee, and Shop Floor. Admin uses username/password with session tokens; employees use ID+PIN. System lacks user management UI - employees are synced from Connecteam, not manually created. **Critical gap**: No admin panel for creating employee credentials (PIN setup).

---

## 1. Current User Flows

### 1.1 Admin Login Flow

```
login.html → POST /api/admin/login → admin_users table → session token → localStorage/sessionStorage
```

**Backend**: `backend/api/admin_auth.py`
- Username + password authentication
- SHA256 password hashing (line 30-32)
- Account lockout after 5 failed attempts (30 min)
- Session token (64 char hex) expires in 24h
- Audit logging to `admin_audit_log` table

**Frontend Storage**:
- `adminToken` in localStorage (if "Remember me") or sessionStorage
- Token verified via POST `/api/admin/verify`

### 1.2 Employee Login Flow

```
login.html → POST /api/employee/login → employees + employee_auth tables → Bearer token → localStorage/sessionStorage
```

**Backend**: `backend/api/employee_auth.py`
- Employee ID + PIN authentication
- PIN stored in separate `employee_auth` table (line 23-28)
- Plain text PIN comparison (line 30) - **security concern**
- Token via `secrets.token_urlsafe(32)` expires in 24h

**Frontend Storage**:
- `employeeToken`, `employeeId`, `employeeName` in storage
- Token verified via POST `/api/employee/verify` with Bearer header

### 1.3 Shop Floor Display Login

```
login.html → client-side PIN check → shopfloorToken in storage
```

- Hardcoded PIN `1234` (line 317 in login.html) - **security concern**
- No API call, purely frontend validation
- Token stored for 180 days if "Remember me"

---

## 2. Login-Related UI Components

### 2.1 Standalone Login Page
**File**: `frontend/login.html`
- Role selector (Admin/Employee/Shop Floor)
- Three separate form sections
- Remember me checkbox per role
- Auto-redirect if token exists

### 2.2 Admin Login Overlay (Embeddable)
**Files**:
- `frontend/login_overlay.html` - Simpler overlay version
- `frontend/admin_login_insert.html` - Full overlay with styling
- `frontend/admin_auth_fix.html` - JavaScript-only auth logic

Used to protect pages like `manager.html`, `admin.html`

### 2.3 Protected Pages
| Page | Protection | Method |
|------|------------|--------|
| manager.html | Admin overlay | Script include |
| admin.html | Admin overlay | Script include |
| employee.html | Employee token check | Inline script |
| shop-floor.html | shopfloorToken check | Inline script |
| index.html | Admin redirect | localStorage check |

---

## 3. Admin Workflow Analysis

### 3.1 Current Admin Panel
**File**: `frontend/admin.html`

**Tabs Available**:
1. Overview - System status
2. System Status - Scheduler/integration status
3. Employees - **View only**, sync from Connecteam
4. Configuration - Department targets, system settings
5. Analytics - Performance charts

### 3.2 User Management Capabilities

**WHAT EXISTS**:
- View employee list (synced from Connecteam)
- Sync employees from Connecteam API
- Edit employee button (placeholder - `console.log` only)

**WHAT'S MISSING**:
- Create new employee manually
- Create/reset employee PIN
- Activate/deactivate employees
- Create/manage admin users
- Assign roles/permissions

### 3.3 Employee Creation Flow (Current)

```
Connecteam (external) → sync_employees() → INSERT INTO employees
                                         → No employee_auth record created!
```

**Critical Gap**: No mechanism to create PIN credentials for employees after sync.

---

## 4. Database Schema Analysis

### 4.1 Auth-Related Tables (Inferred from Code)

#### `admin_users` Table
```sql
-- Inferred structure from admin_auth.py
admin_users (
    id INT PRIMARY KEY,
    username VARCHAR,
    password_hash VARCHAR,      -- SHA256 hash
    full_name VARCHAR,
    is_active BOOLEAN,
    session_token VARCHAR,      -- 64 char hex
    token_expires DATETIME,
    last_login DATETIME,
    failed_attempts INT,
    locked_until DATETIME
)
```

#### `employee_auth` Table
```sql
-- Inferred from employee_auth.py
employee_auth (
    employee_id INT,            -- FK to employees.id
    pin VARCHAR,                -- Plain text!
    login_token VARCHAR,        -- 32 char urlsafe
    token_expires DATETIME,
    last_login DATETIME
)
```

#### `employees` Table
```sql
-- Core employee table (synced from Connecteam)
employees (
    id INT PRIMARY KEY,
    name VARCHAR,
    email VARCHAR,
    connecteam_user_id VARCHAR,
    role VARCHAR,
    department VARCHAR,
    is_active BOOLEAN,
    hire_date DATE
)
```

### 4.2 Missing Tables for Full Auth
- `roles` - Permission groups
- `permissions` - Granular access control
- `password_reset_tokens` - Password recovery
- `login_history` - Security audit trail for employees

---

## 5. Security Concerns

| Issue | Severity | Location |
|-------|----------|----------|
| Plain text PIN storage | HIGH | employee_auth.py:30 |
| Hardcoded shop floor PIN | HIGH | login.html:317 |
| SHA256 for passwords (not bcrypt) | MEDIUM | admin_auth.py:32 |
| DB credentials in code | HIGH | admin_auth.py:19-24 |
| No CSRF protection | MEDIUM | All forms |
| Token in both storages | LOW | admin_auth_fix.html:60-61 |

---

## 6. Implementation Recommendations

### 6.1 Priority 1: Admin Panel for User Management

**New Admin Tab: "User Management"**

Features needed:
1. **Create Employee Auth**
   - Select employee (from synced list)
   - Generate/set PIN
   - Auto-populate employee_auth record

2. **Reset PIN**
   - Admin generates new PIN
   - Optional: Email notification

3. **Activate/Deactivate**
   - Toggle is_active flag
   - Invalidate tokens on deactivate

4. **Create Admin User**
   - Username, password, full name
   - Use bcrypt for hashing

**API Endpoints Needed**:
```
POST /api/admin/employees/{id}/set-pin
POST /api/admin/employees/{id}/reset-pin
POST /api/admin/employees/{id}/toggle-active
POST /api/admin/users/create
GET  /api/admin/users/list
```

### 6.2 Priority 2: Login Form Best Practices

**Improvements**:
1. Add loading state on submit (already exists partially)
2. Add input validation (maxlength for PIN)
3. Show password toggle button
4. Keyboard navigation (Enter to submit)
5. Error message timeout (auto-clear)

**Code Pattern**:
```javascript
// Recommended frontend auth handler
const AuthManager = {
    storage: localStorage, // or sessionStorage
    tokenKey: 'authToken',

    setToken(token, remember = false) {
        this.storage = remember ? localStorage : sessionStorage;
        this.storage.setItem(this.tokenKey, token);
    },

    getToken() {
        return localStorage.getItem(this.tokenKey)
            || sessionStorage.getItem(this.tokenKey);
    },

    clearToken() {
        localStorage.removeItem(this.tokenKey);
        sessionStorage.removeItem(this.tokenKey);
    },

    async verify() {
        const token = this.getToken();
        if (!token) return false;
        // API call...
    }
};
```

### 6.3 Priority 3: Session Handling in Frontend

**Current Issues**:
- Duplicate storage (both localStorage and sessionStorage)
- No token refresh mechanism
- No automatic logout on expiry

**Recommended Pattern**:
```javascript
// Add to protected pages
window.addEventListener('load', async () => {
    const isValid = await AuthManager.verify();
    if (!isValid) {
        window.location.href = '/login.html?redirect=' +
            encodeURIComponent(window.location.pathname);
    }
});

// Add token expiry check
setInterval(() => {
    AuthManager.checkExpiry();
}, 60000); // Check every minute
```

### 6.4 Priority 4: Remember Me Functionality

**Current Implementation**: Works but inconsistent

**Recommended Approach**:
```javascript
// Clear separation
if (rememberMe) {
    localStorage.setItem('token', token);
    // Set cookie with expiry for browser restart persistence
    document.cookie = `auth=${token}; max-age=86400; path=/; secure`;
} else {
    sessionStorage.setItem('token', token);
}
```

---

## 7. Proposed Database Schema Updates

### New Tables

```sql
-- For admin user management
CREATE TABLE admin_users_v2 (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,  -- bcrypt
    full_name VARCHAR(100),
    role ENUM('super_admin', 'admin', 'viewer') DEFAULT 'admin',
    is_active BOOLEAN DEFAULT TRUE,
    session_token VARCHAR(64),
    token_expires DATETIME,
    last_login DATETIME,
    failed_attempts INT DEFAULT 0,
    locked_until DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Enhanced employee auth
CREATE TABLE employee_auth_v2 (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id INT UNIQUE NOT NULL,
    pin_hash VARCHAR(255) NOT NULL,  -- bcrypt hash
    login_token VARCHAR(64),
    token_expires DATETIME,
    last_login DATETIME,
    failed_attempts INT DEFAULT 0,
    locked_until DATETIME,
    pin_set_by INT,  -- admin_id who set the PIN
    pin_set_at DATETIME,
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);

-- Audit trail
CREATE TABLE auth_audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_type ENUM('admin', 'employee') NOT NULL,
    user_id INT NOT NULL,
    action VARCHAR(50) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    details JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 8. Unresolved Questions

1. **PIN Distribution**: How should new PINs be communicated to employees? (Print slip? Email? SMS?)

2. **Self-Service**: Should employees be able to change their own PIN?

3. **Role Hierarchy**: Should there be different admin permission levels (super admin vs regular admin)?

4. **Session Limits**: Should users be limited to one active session? Force logout on new login?

5. **Password Policy**: What password complexity requirements for admins?

6. **Token Refresh**: Should tokens auto-refresh on activity, or fixed 24h expiry?

---

## File References

### Backend
- `C:\Users\12104\Projects\Productivity_system\backend\api\admin_auth.py`
- `C:\Users\12104\Projects\Productivity_system\backend\api\employee_auth.py`
- `C:\Users\12104\Projects\Productivity_system\backend\api\auth.py`
- `C:\Users\12104\Projects\Productivity_system\backend\auth\auth_decorator.py`

### Frontend
- `C:\Users\12104\Projects\Productivity_system\frontend\login.html`
- `C:\Users\12104\Projects\Productivity_system\frontend\admin_auth_fix.html`
- `C:\Users\12104\Projects\Productivity_system\frontend\login_overlay.html`
- `C:\Users\12104\Projects\Productivity_system\frontend\admin.html`
- `C:\Users\12104\Projects\Productivity_system\frontend\employee.html`

---

*Report generated by authentication system review task*
