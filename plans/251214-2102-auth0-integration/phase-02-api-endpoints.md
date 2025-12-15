# Phase 02: API Endpoints

## Context
- **Parent Plan**: [plan.md](plan.md)
- **Dependencies**: [Phase 01](phase-01-backend-setup.md) must be complete
- **Docs**: [user_management.py](../../backend/api/user_management.py)

---

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-14 |
| Description | Add Flask endpoints for employee creation with Auth0 |
| Priority | High |
| Implementation Status | ⬜ Not Started |
| Review Status | ⬜ Not Reviewed |

---

## Key Insights

1. Existing `user_management.py` handles PIN management
2. No "Add Employee" endpoint exists - need to create
3. Transaction pattern: Create local → Create Auth0 → Rollback on failure

---

## Requirements

1. Create employee endpoint with Auth0 integration
2. Optional checkbox to create Auth0 account
3. Handle Auth0 failures gracefully (rollback)
4. Return both employee_id and auth0_user_id

---

## Related Code Files

| File | Purpose |
|------|---------|
| `backend/api/user_management.py` | Add new endpoint |
| `backend/integrations/auth0_manager.py` | Call Auth0 API |

---

## Implementation Steps

### Step 1: Add create_employee endpoint

```python
# Add to backend/api/user_management.py

from integrations.auth0_manager import Auth0Manager

@user_management_bp.route('/api/admin/employees/create', methods=['POST'])
@require_api_key
def create_employee():
    """Create new employee with optional Auth0 account"""
    try:
        data = request.json or {}

        # Required fields
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()

        if not name:
            return jsonify({'success': False, 'message': 'Name is required'}), 400
        if not email:
            return jsonify({'success': False, 'message': 'Email is required'}), 400

        # Optional fields
        department = data.get('department', '').strip() or None
        personal_email = data.get('personal_email', '').strip() or None
        phone_number = data.get('phone_number', '').strip() or None
        create_auth0 = data.get('create_auth0', False)

        # Check if employee with email already exists
        existing = get_db().execute_one("""
            SELECT id FROM employees WHERE email = %s
        """, (email,))

        if existing:
            return jsonify({'success': False, 'message': 'Employee with this email already exists'}), 409

        # Create employee record
        result = get_db().execute_query("""
            INSERT INTO employees (name, email, personal_email, phone_number, is_active)
            VALUES (%s, %s, %s, %s, 1)
        """, (name, email, personal_email, phone_number))

        employee_id = get_db().execute_one("SELECT LAST_INSERT_ID() as id")['id']

        # Create Auth0 account if requested
        auth0_result = None
        if create_auth0 and Auth0Manager.is_configured():
            auth0_result = Auth0Manager.create_employee_account({
                'employee_id': employee_id,
                'name': name,
                'email': email,
                'department': department
            })

            if auth0_result['success']:
                # Store Auth0 user ID
                get_db().execute_query("""
                    UPDATE employees
                    SET auth0_user_id = %s, auth0_sync_status = 'created'
                    WHERE id = %s
                """, (auth0_result['user_id'], employee_id))
            else:
                # Log failure but don't rollback employee creation
                print(f"[Auth0] Failed to create account: {auth0_result['message']}")

        return jsonify({
            'success': True,
            'employee_id': employee_id,
            'name': name,
            'email': email,
            'message': 'Employee created successfully',
            'auth0': auth0_result
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
```

### Step 2: Add create_auth0_for_existing endpoint

```python
@user_management_bp.route('/api/admin/employees/<int:employee_id>/create-auth0', methods=['POST'])
@require_api_key
def create_auth0_for_employee(employee_id):
    """Create Auth0 account for existing employee"""
    try:
        # Get employee
        employee = get_db().execute_one("""
            SELECT id, name, email, auth0_user_id
            FROM employees WHERE id = %s
        """, (employee_id,))

        if not employee:
            return jsonify({'success': False, 'message': 'Employee not found'}), 404

        if employee.get('auth0_user_id'):
            return jsonify({'success': False, 'message': 'Employee already has Auth0 account'}), 409

        if not employee.get('email'):
            return jsonify({'success': False, 'message': 'Employee has no email address'}), 400

        # Create Auth0 account
        result = Auth0Manager.create_employee_account({
            'employee_id': employee_id,
            'name': employee['name'],
            'email': employee['email']
        })

        if result['success']:
            get_db().execute_query("""
                UPDATE employees
                SET auth0_user_id = %s, auth0_sync_status = 'created'
                WHERE id = %s
            """, (result['user_id'], employee_id))

        return jsonify({
            'success': result['success'],
            'employee_id': employee_id,
            'auth0_user_id': result.get('user_id'),
            'message': result['message']
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
```

### Step 3: Update list_employees to include Auth0 status

```python
# Modify existing list_employees_with_auth query
employees = get_db().execute_query("""
    SELECT
        e.id,
        e.name,
        e.email,
        e.personal_email,
        e.phone_number,
        rc.role_name as role,
        e.is_active,
        e.auth0_user_id,
        e.auth0_sync_status,
        CASE WHEN ea.pin IS NOT NULL THEN 1 ELSE 0 END as has_pin,
        ea.pin_plain,
        ea.last_login,
        ea.pin_set_at,
        e.welcome_sent_at
    FROM employees e
    LEFT JOIN role_configs rc ON e.role_id = rc.id
    LEFT JOIN employee_auth ea ON e.id = ea.employee_id
    ORDER BY e.name
""")
```

---

## Todo List

- [ ] Add `create_employee` endpoint
- [ ] Add `create_auth0_for_employee` endpoint
- [ ] Update `list_employees` to include Auth0 fields
- [ ] Test endpoints locally with curl

---

## Success Criteria

- [ ] POST `/api/admin/employees/create` creates employee
- [ ] POST `/api/admin/employees/create` with `create_auth0: true` creates Auth0 account
- [ ] POST `/api/admin/employees/{id}/create-auth0` works for existing employees
- [ ] Auth0 failures logged but don't block employee creation

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Duplicate Auth0 accounts | Check auth0_user_id before creation |
| Auth0 timeout | 15 second timeout, graceful failure |

---

## Security Considerations

- Require API key for all endpoints
- Validate email format before Auth0 call
- Don't expose Auth0 errors to frontend (log only)

---

## Next Steps

After completing this phase → Proceed to [Phase 03: Database Schema](phase-03-database-schema.md)
