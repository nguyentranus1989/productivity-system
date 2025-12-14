# Employee User Management - API Endpoints Reference

## Summary

| Method | Endpoint | Status | Purpose |
|--------|----------|--------|---------|
| POST | /api/dashboard/employees | NEW | Create employee |
| PUT | /api/dashboard/employees/:id | NEW | Update employee |
| POST | /api/dashboard/employees/:id/suspend | NEW | Suspend employee |
| POST | /api/dashboard/employees/:id/unsuspend | NEW | Unsuspend employee |
| DELETE | /api/dashboard/employees/:id | NEW | Permanently delete |
| POST | /api/dashboard/employees/bulk-action | NEW | Bulk operations |
| GET | /api/dashboard/employees | MODIFY | Add status filter |

---

## Detailed Specifications

### POST /api/dashboard/employees

**Purpose:** Create a new employee

**Auth:** `X-API-Key` header required

**Request Body:**
```json
{
    "name": "John Doe",           // Required - string, max 100 chars
    "email": "john@example.com",  // Required - valid email, unique
    "role_id": 1,                 // Required - FK to role_configs.id
    "department": "Production",   // Optional - string
    "hire_date": "2025-01-15",   // Optional - ISO date, defaults to today
    "connecteam_user_id": "12345", // Optional - for time tracking
    "podfactory_emails": ["john@pf.com"], // Optional - array of emails
    "notes": "Notes here"         // Optional - text
}
```

**Response (Success - 201):**
```json
{
    "success": true,
    "employee_id": 123,
    "message": "Employee created successfully"
}
```

**Response (Error - 400):**
```json
{
    "success": false,
    "error": "Email already exists"
}
```

**Validation:**
- Name: required, 1-100 characters
- Email: required, valid format, unique in database
- Role ID: required, must exist in role_configs table

---

### PUT /api/dashboard/employees/:id

**Purpose:** Update employee details

**Auth:** `X-API-Key` header required

**URL Params:**
- `id` - Employee ID (integer)

**Request Body (partial updates allowed):**
```json
{
    "name": "John Smith",
    "email": "john.smith@example.com",
    "role_id": 2,
    "department": "Shipping",
    "notes": "Promoted to senior"
}
```

**Response (Success - 200):**
```json
{
    "success": true,
    "message": "Employee updated successfully"
}
```

**Response (Error - 404):**
```json
{
    "success": false,
    "error": "Employee not found"
}
```

**Notes:**
- Only provided fields are updated
- Cannot update email to an existing email
- Cannot update deleted employees

---

### POST /api/dashboard/employees/:id/suspend

**Purpose:** Suspend an employee (different from archive)

**Auth:** `X-API-Key` header required

**URL Params:**
- `id` - Employee ID (integer)

**Request Body:**
```json
{
    "reason": "Performance review pending",  // Required
    "suspended_by": "manager"                // Optional, defaults to "system"
}
```

**Response (Success - 200):**
```json
{
    "success": true,
    "message": "Employee suspended successfully"
}
```

**Side Effects:**
- Sets `status = 'suspended'`
- Sets `is_active = 0`
- Records `suspended_at`, `suspended_by`, `suspended_reason`
- Invalidates any active login tokens in `employee_auth`

---

### POST /api/dashboard/employees/:id/unsuspend

**Purpose:** Reactivate a suspended employee

**Auth:** `X-API-Key` header required

**URL Params:**
- `id` - Employee ID (integer)

**Request Body:**
```json
{
    "unsuspended_by": "manager"  // Optional
}
```

**Response (Success - 200):**
```json
{
    "success": true,
    "message": "Employee reactivated successfully"
}
```

**Side Effects:**
- Sets `status = 'active'`
- Sets `is_active = 1`
- Clears `suspended_at`, `suspended_by`, `suspended_reason`

---

### DELETE /api/dashboard/employees/:id

**Purpose:** Permanently delete an employee

**Auth:** `X-API-Key` header required

**URL Params:**
- `id` - Employee ID (integer)

**Request Body:**
```json
{
    "confirm": true,              // Required - safety check
    "deleted_by": "admin",        // Optional
    "reason": "Termination"       // Optional
}
```

**Response (Success - 200):**
```json
{
    "success": true,
    "message": "Employee permanently deleted"
}
```

**Response (Error - 400):**
```json
{
    "success": false,
    "error": "Confirmation required"
}
```

**Side Effects:**
- For soft delete: Sets `status = 'deleted'`, `deleted_at`, `deleted_by`
- Deletes from `employee_auth` (login credentials)
- Deletes from `employee_podfactory_mapping_v2` (PodFactory mappings)
- Does NOT delete `activity_logs` or `daily_scores` (keeps for historical data)

**Safety:**
- Requires `confirm: true` in body
- Cannot delete currently clocked-in employees (returns 400)

---

### POST /api/dashboard/employees/bulk-action

**Purpose:** Perform action on multiple employees

**Auth:** `X-API-Key` header required

**Request Body:**
```json
{
    "employee_ids": [1, 2, 3, 5],
    "action": "suspend",          // "suspend", "unsuspend", "archive", "delete", "activate"
    "reason": "Department restructuring",  // Optional
    "performed_by": "manager"              // Optional
}
```

**Response (Success - 200):**
```json
{
    "success": true,
    "affected_count": 4,
    "skipped_count": 0,
    "message": "4 employees suspended"
}
```

**Response (Partial Success - 200):**
```json
{
    "success": true,
    "affected_count": 3,
    "skipped_count": 1,
    "skipped_ids": [5],
    "message": "3 employees suspended, 1 skipped (currently clocked in)"
}
```

**Limits:**
- Max 100 employees per request
- Clocked-in employees are skipped for suspend/archive/delete actions

---

### GET /api/dashboard/employees (Modified)

**Purpose:** Get employee list with optional status filter

**Auth:** `X-API-Key` header required

**Query Params (all optional):**
- `status` - Comma-separated list: `active,suspended,archived`
- `department` - Filter by department
- `search` - Search by name or email

**Examples:**
```
GET /api/dashboard/employees?status=active
GET /api/dashboard/employees?status=active,suspended
GET /api/dashboard/employees?department=Production
GET /api/dashboard/employees?search=john
```

**Response (Success - 200):**
```json
{
    "success": true,
    "employees": [
        {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com",
            "role_id": 1,
            "role_name": "Production Worker",
            "department": "Production",
            "status": "active",
            "is_active": 1,
            "connecteam_user_id": "12345",
            "podfactory_emails": ["john@pf.com"],
            "hire_date": "2025-01-15",
            "created_at": "2025-01-15T09:00:00",
            "notes": null
        }
    ],
    "total_count": 85
}
```

**Default Behavior:**
- Without status filter: returns only `active` employees (backward compatible)
- With `status=all`: returns all statuses except `deleted`

---

## Error Codes

| HTTP Code | Meaning |
|-----------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad request (validation failed, missing confirm, etc.) |
| 401 | Unauthorized (missing/invalid API key) |
| 404 | Employee not found |
| 409 | Conflict (e.g., duplicate email) |
| 500 | Server error |
