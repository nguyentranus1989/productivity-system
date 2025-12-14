# Employee User Management Feature - Implementation Plan

**Date:** 2025-12-13
**Status:** Planning
**Priority:** High
**Estimated Effort:** 3-4 days

---

## 1. Executive Summary

Add full CRUD operations for employee management in the Productivity Tracker system. Currently has basic listing and archive functionality; needs create, edit, suspend, delete, and bulk operations.

### Current State Analysis
- **Existing in manager.html:** Employee list tab, archive functionality, add employee form (HTML only, no JS handler)
- **Existing in dashboard.py:** GET /employees, archive, restore, mapping endpoints
- **Missing:** Create employee API, Edit API, Suspend functionality, Delete API, Bulk operations
- **Critical Finding:** `addEmployee` form exists but NO JavaScript function to handle it

---

## 2. Database Schema Changes

### 2.1 Modify `employees` Table

```sql
-- Add new columns for suspend and soft delete tracking
ALTER TABLE employees
ADD COLUMN status ENUM('active', 'suspended', 'archived', 'deleted') DEFAULT 'active',
ADD COLUMN suspended_at DATETIME NULL,
ADD COLUMN suspended_by VARCHAR(100) NULL,
ADD COLUMN suspended_reason VARCHAR(255) NULL,
ADD COLUMN deleted_at DATETIME NULL,
ADD COLUMN deleted_by VARCHAR(100) NULL,
ADD COLUMN department VARCHAR(100) NULL,
ADD COLUMN notes TEXT NULL,
ADD COLUMN updated_by VARCHAR(100) NULL;

-- Add index for status filtering
CREATE INDEX idx_employees_status ON employees(status);

-- Migration: Convert existing is_active and archived_at to new status
UPDATE employees SET status = 'archived' WHERE archived_at IS NOT NULL;
UPDATE employees SET status = 'active' WHERE is_active = 1 AND archived_at IS NULL;
UPDATE employees SET status = 'suspended' WHERE is_active = 0 AND archived_at IS NULL;
```

### 2.2 No New Tables Required
- Existing `role_configs` table handles role assignment via `role_id` FK
- Existing `employee_auth` table handles authentication (PIN, tokens)
- Keep using `is_active` column for backward compatibility; new `status` column for finer control

---

## 3. API Endpoints

### 3.1 New Endpoints (backend/api/dashboard.py)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/dashboard/employees` | Create new employee |
| PUT | `/api/dashboard/employees/<id>` | Update employee details |
| POST | `/api/dashboard/employees/<id>/suspend` | Suspend employee |
| POST | `/api/dashboard/employees/<id>/unsuspend` | Reactivate suspended employee |
| DELETE | `/api/dashboard/employees/<id>` | Permanently delete employee |
| POST | `/api/dashboard/employees/bulk-action` | Bulk suspend/archive/delete |

### 3.2 Endpoint Specifications

#### POST /api/dashboard/employees (Create)
```python
# Request
{
    "name": "John Doe",
    "email": "john@example.com",
    "role_id": 1,                    # Required - FK to role_configs
    "department": "Production",       # Optional
    "hire_date": "2025-01-15",       # Optional, defaults to today
    "connecteam_user_id": "12345",   # Optional
    "podfactory_emails": ["j@pf.com"], # Optional
    "notes": "New hire from agency"  # Optional
}

# Response
{
    "success": true,
    "employee_id": 123,
    "message": "Employee created successfully"
}
```

#### PUT /api/dashboard/employees/<id> (Edit)
```python
# Request - partial updates allowed
{
    "name": "John Smith",
    "email": "john.smith@example.com",
    "role_id": 2,
    "department": "Shipping",
    "notes": "Promoted to senior"
}

# Response
{
    "success": true,
    "message": "Employee updated successfully"
}
```

#### POST /api/dashboard/employees/<id>/suspend
```python
# Request
{
    "reason": "Performance review pending",
    "suspended_by": "manager"
}

# Response
{
    "success": true,
    "message": "Employee suspended successfully"
}
```

#### DELETE /api/dashboard/employees/<id>
```python
# Request - requires confirmation token
{
    "confirm": true,
    "deleted_by": "admin",
    "reason": "Termination - policy violation"
}

# Response
{
    "success": true,
    "message": "Employee permanently deleted"
}
```

#### POST /api/dashboard/employees/bulk-action
```python
# Request
{
    "employee_ids": [1, 2, 3, 5],
    "action": "suspend",  # "suspend", "archive", "delete", "unsuspend", "activate"
    "reason": "Department restructuring",
    "performed_by": "manager"
}

# Response
{
    "success": true,
    "affected_count": 4,
    "message": "4 employees suspended"
}
```

### 3.3 Modify Existing Endpoints

| Endpoint | Change |
|----------|--------|
| GET /api/dashboard/employees | Add `?status=active,suspended,archived` filter param |
| POST /api/dashboard/employees/<id>/archive | Add `reason` and `archived_by` fields |

---

## 4. Frontend Components

### 4.1 Files to Modify
- `frontend/manager.html` - All UI changes

### 4.2 HTML Components

#### 4.2.1 Enhanced Add Employee Form (Line ~744)
```html
<!-- Replace existing form with expanded fields -->
<form id="addEmployeeForm" onsubmit="return addEmployee(event)">
    <div class="form-row">
        <div class="form-group">
            <label>Full Name *</label>
            <input type="text" id="newEmpName" required>
        </div>
        <div class="form-group">
            <label>Email *</label>
            <input type="email" id="newEmpEmail" required>
        </div>
    </div>
    <div class="form-row">
        <div class="form-group">
            <label>Role *</label>
            <select id="newEmpRoleId" required>
                <!-- Populated dynamically from role_configs -->
            </select>
        </div>
        <div class="form-group">
            <label>Department</label>
            <input type="text" id="newEmpDepartment" placeholder="e.g., Production, Shipping">
        </div>
    </div>
    <div class="form-row">
        <div class="form-group">
            <label>Hire Date</label>
            <input type="date" id="newEmpHireDate">
        </div>
        <div class="form-group">
            <label>Connecteam User ID</label>
            <input type="text" id="newEmpConnecteamId">
        </div>
    </div>
    <div class="form-group">
        <label>PodFactory Email(s)</label>
        <input type="text" id="newEmpPodFactoryEmails" placeholder="Comma-separated">
    </div>
    <div class="form-group">
        <label>Notes</label>
        <textarea id="newEmpNotes" rows="2"></textarea>
    </div>
    <button type="submit" class="btn-primary">Add Employee</button>
</form>
```

#### 4.2.2 Edit Employee Modal
```html
<div id="editEmployeeModal" class="modal" style="display:none;">
    <div class="modal-content">
        <h3>Edit Employee</h3>
        <form id="editEmployeeForm">
            <input type="hidden" id="editEmpId">
            <!-- Same fields as add form, pre-populated -->
            <div class="modal-actions">
                <button type="button" onclick="closeEditModal()">Cancel</button>
                <button type="submit" class="btn-primary">Save Changes</button>
            </div>
        </form>
    </div>
</div>
```

#### 4.2.3 Suspend Confirmation Modal
```html
<div id="suspendEmployeeModal" class="modal" style="display:none;">
    <div class="modal-content">
        <h3>Suspend Employee</h3>
        <p id="suspendEmployeeName"></p>
        <div class="form-group">
            <label>Reason for Suspension</label>
            <textarea id="suspendReason" required placeholder="e.g., Performance review pending"></textarea>
        </div>
        <div class="modal-actions">
            <button type="button" onclick="closeSuspendModal()">Cancel</button>
            <button type="button" onclick="confirmSuspend()" class="btn-warning">Suspend Employee</button>
        </div>
    </div>
</div>
```

#### 4.2.4 Delete Confirmation Modal
```html
<div id="deleteEmployeeModal" class="modal" style="display:none;">
    <div class="modal-content modal-danger">
        <h3>Permanently Delete Employee</h3>
        <p class="warning-text">This action cannot be undone. All data associated with this employee will be permanently removed.</p>
        <p>Employee: <strong id="deleteEmployeeName"></strong></p>
        <div class="form-group">
            <label>Type employee name to confirm:</label>
            <input type="text" id="deleteConfirmName" placeholder="Type exact name">
        </div>
        <div class="modal-actions">
            <button type="button" onclick="closeDeleteModal()">Cancel</button>
            <button type="button" onclick="confirmDelete()" class="btn-danger" id="confirmDeleteBtn" disabled>Delete Permanently</button>
        </div>
    </div>
</div>
```

#### 4.2.5 Bulk Action Toolbar
```html
<!-- Add above employee table -->
<div id="bulkActionBar" style="display:none; margin-bottom:15px; background:rgba(102,126,234,0.1); padding:15px; border-radius:8px;">
    <span id="selectedCount">0 selected</span>
    <div class="bulk-actions">
        <button onclick="bulkSuspend()" class="btn-warning btn-sm">Suspend Selected</button>
        <button onclick="bulkArchive()" class="btn-secondary btn-sm">Archive Selected</button>
        <button onclick="bulkDelete()" class="btn-danger btn-sm">Delete Selected</button>
        <button onclick="clearSelection()" class="btn-outline btn-sm">Clear Selection</button>
    </div>
</div>
```

#### 4.2.6 Update Employee Table Header
```html
<!-- Add checkbox column to table header -->
<th style="width:40px;">
    <input type="checkbox" id="selectAllEmployees" onchange="toggleSelectAll()">
</th>
```

### 4.3 JavaScript Functions (~Line 4575+)

```javascript
// ========== ADD EMPLOYEE ==========
window.addEmployee = async function(event) {
    event.preventDefault();

    const data = {
        name: document.getElementById('newEmpName').value,
        email: document.getElementById('newEmpEmail').value,
        role_id: parseInt(document.getElementById('newEmpRoleId').value),
        department: document.getElementById('newEmpDepartment').value || null,
        hire_date: document.getElementById('newEmpHireDate').value || null,
        connecteam_user_id: document.getElementById('newEmpConnecteamId').value || null,
        podfactory_emails: document.getElementById('newEmpPodFactoryEmails').value
            .split(',').map(e => e.trim()).filter(e => e),
        notes: document.getElementById('newEmpNotes').value || null
    };

    try {
        const response = await fetch(`${API_BASE}/api/dashboard/employees`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
            body: JSON.stringify(data)
        });

        const result = await response.json();
        if (result.success) {
            await alertDialog('Success', 'Employee created successfully');
            document.getElementById('addEmployeeForm').reset();
            showEmpTab('list');
            loadEmployeeManagementData();
        } else {
            await alertDialog('Error', result.error || 'Failed to create employee');
        }
    } catch (error) {
        await alertDialog('Error', 'Network error creating employee');
    }

    return false;
};

// ========== EDIT EMPLOYEE ==========
window.editEmployee = async function(id) {
    try {
        // Fetch current employee data
        const response = await fetch(`${API_BASE}/api/dashboard/employees/${id}`, {
            headers: { 'X-API-Key': API_KEY }
        });
        const data = await response.json();

        if (!data.success) {
            await alertDialog('Error', 'Could not load employee data');
            return;
        }

        const emp = data.employee;
        document.getElementById('editEmpId').value = emp.id;
        document.getElementById('editEmpName').value = emp.name;
        document.getElementById('editEmpEmail').value = emp.email || '';
        document.getElementById('editEmpRoleId').value = emp.role_id;
        document.getElementById('editEmpDepartment').value = emp.department || '';
        document.getElementById('editEmpNotes').value = emp.notes || '';

        document.getElementById('editEmployeeModal').style.display = 'flex';
    } catch (error) {
        await alertDialog('Error', 'Failed to load employee');
    }
};

window.saveEmployeeEdit = async function(event) {
    event.preventDefault();
    const id = document.getElementById('editEmpId').value;

    const data = {
        name: document.getElementById('editEmpName').value,
        email: document.getElementById('editEmpEmail').value,
        role_id: parseInt(document.getElementById('editEmpRoleId').value),
        department: document.getElementById('editEmpDepartment').value || null,
        notes: document.getElementById('editEmpNotes').value || null
    };

    try {
        const response = await fetch(`${API_BASE}/api/dashboard/employees/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
            body: JSON.stringify(data)
        });

        const result = await response.json();
        if (result.success) {
            closeEditModal();
            await alertDialog('Success', 'Employee updated successfully');
            loadEmployeeManagementData();
        } else {
            await alertDialog('Error', result.error || 'Failed to update employee');
        }
    } catch (error) {
        await alertDialog('Error', 'Network error updating employee');
    }

    return false;
};

// ========== SUSPEND EMPLOYEE ==========
let suspendingEmployeeId = null;
let suspendingEmployeeName = null;

window.suspendEmployee = function(id, name) {
    suspendingEmployeeId = id;
    suspendingEmployeeName = name;
    document.getElementById('suspendEmployeeName').textContent = `Suspend: ${name}`;
    document.getElementById('suspendReason').value = '';
    document.getElementById('suspendEmployeeModal').style.display = 'flex';
};

window.confirmSuspend = async function() {
    const reason = document.getElementById('suspendReason').value;
    if (!reason.trim()) {
        await alertDialog('Error', 'Please provide a reason for suspension');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/dashboard/employees/${suspendingEmployeeId}/suspend`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
            body: JSON.stringify({ reason, suspended_by: 'manager' })
        });

        const result = await response.json();
        if (result.success) {
            closeSuspendModal();
            await alertDialog('Success', `${suspendingEmployeeName} has been suspended`);
            loadEmployeeManagementData();
        } else {
            await alertDialog('Error', result.error || 'Failed to suspend employee');
        }
    } catch (error) {
        await alertDialog('Error', 'Network error suspending employee');
    }
};

// ========== DELETE EMPLOYEE ==========
let deletingEmployeeId = null;
let deletingEmployeeName = null;

window.deleteEmployee = function(id, name) {
    deletingEmployeeId = id;
    deletingEmployeeName = name;
    document.getElementById('deleteEmployeeName').textContent = name;
    document.getElementById('deleteConfirmName').value = '';
    document.getElementById('confirmDeleteBtn').disabled = true;
    document.getElementById('deleteEmployeeModal').style.display = 'flex';
};

// Enable delete button only when name matches
document.getElementById('deleteConfirmName')?.addEventListener('input', function() {
    const matches = this.value === deletingEmployeeName;
    document.getElementById('confirmDeleteBtn').disabled = !matches;
});

window.confirmDelete = async function() {
    try {
        const response = await fetch(`${API_BASE}/api/dashboard/employees/${deletingEmployeeId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
            body: JSON.stringify({ confirm: true, deleted_by: 'manager' })
        });

        const result = await response.json();
        if (result.success) {
            closeDeleteModal();
            await alertDialog('Success', 'Employee permanently deleted');
            loadEmployeeManagementData();
        } else {
            await alertDialog('Error', result.error || 'Failed to delete employee');
        }
    } catch (error) {
        await alertDialog('Error', 'Network error deleting employee');
    }
};

// ========== BULK OPERATIONS ==========
let selectedEmployees = new Set();

window.toggleEmployeeSelection = function(id) {
    if (selectedEmployees.has(id)) {
        selectedEmployees.delete(id);
    } else {
        selectedEmployees.add(id);
    }
    updateBulkActionBar();
};

window.toggleSelectAll = function() {
    const selectAll = document.getElementById('selectAllEmployees').checked;
    const checkboxes = document.querySelectorAll('.employee-checkbox');

    selectedEmployees.clear();
    checkboxes.forEach(cb => {
        cb.checked = selectAll;
        if (selectAll) selectedEmployees.add(parseInt(cb.dataset.id));
    });
    updateBulkActionBar();
};

function updateBulkActionBar() {
    const bar = document.getElementById('bulkActionBar');
    const count = selectedEmployees.size;

    if (count > 0) {
        bar.style.display = 'flex';
        document.getElementById('selectedCount').textContent = `${count} selected`;
    } else {
        bar.style.display = 'none';
    }
}

window.bulkSuspend = async function() {
    if (selectedEmployees.size === 0) return;

    const confirmed = await confirmDialog('Bulk Suspend',
        `Are you sure you want to suspend ${selectedEmployees.size} employees?`);
    if (!confirmed) return;

    await performBulkAction('suspend');
};

window.bulkArchive = async function() {
    if (selectedEmployees.size === 0) return;

    const confirmed = await confirmDialog('Bulk Archive',
        `Are you sure you want to archive ${selectedEmployees.size} employees?`);
    if (!confirmed) return;

    await performBulkAction('archive');
};

window.bulkDelete = async function() {
    if (selectedEmployees.size === 0) return;

    const confirmed = await confirmDialog('Bulk Delete',
        `WARNING: This will PERMANENTLY DELETE ${selectedEmployees.size} employees. This cannot be undone!`,
        { type: 'danger' });
    if (!confirmed) return;

    await performBulkAction('delete');
};

async function performBulkAction(action) {
    try {
        const response = await fetch(`${API_BASE}/api/dashboard/employees/bulk-action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
            body: JSON.stringify({
                employee_ids: Array.from(selectedEmployees),
                action: action,
                performed_by: 'manager'
            })
        });

        const result = await response.json();
        if (result.success) {
            await alertDialog('Success', result.message);
            clearSelection();
            loadEmployeeManagementData();
        } else {
            await alertDialog('Error', result.error || 'Bulk action failed');
        }
    } catch (error) {
        await alertDialog('Error', 'Network error performing bulk action');
    }
}

window.clearSelection = function() {
    selectedEmployees.clear();
    document.querySelectorAll('.employee-checkbox').forEach(cb => cb.checked = false);
    document.getElementById('selectAllEmployees').checked = false;
    updateBulkActionBar();
};

// ========== MODAL HELPERS ==========
window.closeEditModal = () => document.getElementById('editEmployeeModal').style.display = 'none';
window.closeSuspendModal = () => document.getElementById('suspendEmployeeModal').style.display = 'none';
window.closeDeleteModal = () => document.getElementById('deleteEmployeeModal').style.display = 'none';
```

### 4.4 Update Employee Table Row Template

Modify `displayEmployeeTable` function to include:
- Checkbox column for bulk selection
- Status column with suspend/active/archived indicators
- Updated action dropdown with Edit, Suspend/Unsuspend, Archive, Delete options

---

## 5. Implementation Phases

### Phase 1: Database & Basic CRUD (Day 1)
**Files:** `backend/api/dashboard.py`, database migration script

1. Create migration script for schema changes
2. Implement POST /employees (Create)
3. Implement PUT /employees/<id> (Edit)
4. Add frontend addEmployee() function
5. Test create/edit flow

**Deliverables:**
- [x] Migration script: `backend/scripts/migrate_employee_management.py`
- [x] Create endpoint working
- [x] Edit endpoint working
- [x] Frontend forms connected

### Phase 2: Suspend & Status Management (Day 2)
**Files:** `backend/api/dashboard.py`, `frontend/manager.html`

1. Implement suspend/unsuspend endpoints
2. Add status filter to GET /employees
3. Add suspend modal to frontend
4. Update employee table with status column
5. Test suspend/unsuspend flow

**Deliverables:**
- [x] Suspend endpoint working
- [x] Status filtering working
- [x] Frontend suspend UI complete

### Phase 3: Delete & Safety (Day 2-3)
**Files:** `backend/api/dashboard.py`, `frontend/manager.html`

1. Implement DELETE endpoint with safeguards
2. Add delete confirmation modal (name-match required)
3. Implement cascading cleanup (auth, mappings)
4. Test delete flow with validation

**Deliverables:**
- [x] Delete endpoint with safeguards
- [x] Confirmation modal working
- [x] Data cleanup verified

### Phase 4: Bulk Operations (Day 3)
**Files:** `backend/api/dashboard.py`, `frontend/manager.html`

1. Implement bulk action endpoint
2. Add checkbox selection to table
3. Add bulk action toolbar
4. Test bulk suspend/archive/delete

**Deliverables:**
- [x] Bulk endpoint working
- [x] Selection UI working
- [x] All bulk actions tested

### Phase 5: Polish & Integration (Day 4)
**Files:** All modified files

1. Add role dropdown to forms (fetch from role_configs)
2. Add loading states
3. Error handling improvements
4. UI polish (status badges, tooltips)
5. Integration testing with existing features

**Deliverables:**
- [x] Role selection working
- [x] Loading states implemented
- [x] Full integration verified

---

## 6. File Ownership

| File | Owner | Changes |
|------|-------|---------|
| `backend/api/dashboard.py` | Backend | +6 endpoints (~200 lines) |
| `backend/scripts/migrate_employee_management.py` | Backend | New file (~50 lines) |
| `frontend/manager.html` | Frontend | +3 modals, +1 toolbar, ~300 lines JS |

---

## 7. Dependencies & Risks

### Dependencies
1. **Role configs table** - Must have role_configs populated for role dropdown
2. **API key auth** - All new endpoints use existing @require_api_key decorator
3. **Existing archive logic** - New status field must coexist with legacy is_active/archived_at

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Large manager.html file (~220KB) | High | Medium | Keep changes modular, add at specific line ranges |
| Breaking existing archive flow | Medium | High | Test archive/restore thoroughly after migration |
| Cascade delete issues | Low | High | Soft delete first, hard delete requires confirmation |
| Performance with bulk ops | Low | Medium | Limit bulk selection to 100 employees |

### Backward Compatibility
- Keep `is_active` column for legacy code
- New `status` enum takes precedence for new code
- Existing GET /employees continues working

---

## 8. Testing Checklist

### Unit Tests
- [ ] Create employee with valid data
- [ ] Create employee with duplicate email (should fail)
- [ ] Edit employee name
- [ ] Edit employee role
- [ ] Suspend active employee
- [ ] Unsuspend suspended employee
- [ ] Archive suspended employee
- [ ] Delete archived employee
- [ ] Delete active employee (should require confirmation)
- [ ] Bulk suspend 5 employees
- [ ] Bulk delete 3 employees

### Integration Tests
- [ ] Create employee -> appears in list
- [ ] Suspend employee -> removed from productivity calculations
- [ ] Delete employee -> auth tokens invalidated
- [ ] Archive employee -> restored successfully

### Edge Cases
- [ ] Suspend currently clocked-in employee (should warn)
- [ ] Delete employee with pending activity data
- [ ] Bulk action on mixed status employees

---

## 9. Unresolved Questions

1. **Audit logging:** Should we log all employee changes to a separate audit table?
   - Recommendation: Not for v1, add if compliance requires

2. **Cascade delete scope:** When deleting, should we delete:
   - Activity logs? (Recommend: No, anonymize instead)
   - Daily scores? (Recommend: No, keep for historical reports)
   - Auth records? (Recommend: Yes, delete)
   - PodFactory mappings? (Recommend: Yes, delete)

3. **Permission levels:** Should managers vs admins have different capabilities?
   - Recommendation: For v1, all managers can perform all actions. Add RBAC later if needed.

4. **Bulk operation limit:** What's the max employees for bulk actions?
   - Recommendation: 100 employees per operation

---

## 10. Success Criteria

1. Manager can create new employee with all fields
2. Manager can edit any employee field
3. Manager can suspend/unsuspend employees (different from archive)
4. Manager can permanently delete employee with confirmation
5. Manager can select multiple employees for bulk actions
6. All operations update UI immediately without page refresh
7. Existing archive/restore functionality unaffected
