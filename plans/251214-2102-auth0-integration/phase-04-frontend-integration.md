# Phase 04: Frontend Integration

## Context
- **Parent Plan**: [plan.md](plan.md)
- **Dependencies**: [Phase 02](phase-02-api-endpoints.md), [Phase 03](phase-03-database-schema.md)
- **Docs**: [manager.html](../../frontend/manager.html)

---

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-14 |
| Description | Add Employee form with Auth0 checkbox in manager.html |
| Priority | High |
| Implementation Status | ⬜ Not Started |
| Review Status | ⬜ Not Reviewed |

---

## Key Insights

1. Employee Management tab exists in manager.html
2. No "Add Employee" form currently - only PIN management
3. Need modal form with Auth0 checkbox option

---

## Requirements

1. Add "Add Employee" button to Employee Management tab
2. Create modal with form fields (name, email, department)
3. Add "Create Auth0 Account" checkbox
4. Show Auth0 status in employee table
5. Add "Create Auth0" action button for existing employees

---

## Related Code Files

| File | Purpose |
|------|---------|
| `frontend/manager.html` | Add form and table updates |

---

## Implementation Steps

### Step 1: Add "Add Employee" button

```html
<!-- Add to Employee Management tab header -->
<button class="btn btn-primary" onclick="showAddEmployeeModal()">
    <svg>...</svg> Add Employee
</button>
```

### Step 2: Create Add Employee modal

```html
<!-- Add Employee Modal -->
<div class="modal" id="addEmployeeModal">
    <div class="modal-content">
        <h3>Add New Employee</h3>

        <div class="form-group">
            <label>Full Name *</label>
            <input type="text" id="newEmployeeName" required>
        </div>

        <div class="form-group">
            <label>Work Email *</label>
            <input type="email" id="newEmployeeEmail" required>
        </div>

        <div class="form-group">
            <label>Personal Email (for PIN notification)</label>
            <input type="email" id="newEmployeePersonalEmail">
        </div>

        <div class="form-group">
            <label>Phone Number</label>
            <input type="tel" id="newEmployeePhone">
        </div>

        <div class="form-group">
            <label class="checkbox-label">
                <input type="checkbox" id="createAuth0Account" checked>
                Create Auth0 account (for PodFactory access)
            </label>
            <small>Employee will receive email verification link</small>
        </div>

        <div class="modal-actions">
            <button onclick="closeAddEmployeeModal()">Cancel</button>
            <button class="btn-primary" onclick="addEmployee()">Add Employee</button>
        </div>
    </div>
</div>
```

### Step 3: Add JavaScript functions

```javascript
function showAddEmployeeModal() {
    document.getElementById('addEmployeeModal').style.display = 'flex';
    document.getElementById('newEmployeeName').focus();
}

function closeAddEmployeeModal() {
    document.getElementById('addEmployeeModal').style.display = 'none';
    // Clear form
    document.getElementById('newEmployeeName').value = '';
    document.getElementById('newEmployeeEmail').value = '';
    document.getElementById('newEmployeePersonalEmail').value = '';
    document.getElementById('newEmployeePhone').value = '';
}

async function addEmployee() {
    const name = document.getElementById('newEmployeeName').value.trim();
    const email = document.getElementById('newEmployeeEmail').value.trim();
    const personalEmail = document.getElementById('newEmployeePersonalEmail').value.trim();
    const phone = document.getElementById('newEmployeePhone').value.trim();
    const createAuth0 = document.getElementById('createAuth0Account').checked;

    if (!name || !email) {
        showToast('Name and email are required', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/admin/employees/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            },
            body: JSON.stringify({
                name,
                email,
                personal_email: personalEmail || null,
                phone_number: phone || null,
                create_auth0: createAuth0
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast(`Employee ${name} created successfully`, 'success');
            if (data.auth0?.success) {
                showToast('Auth0 account created - verification email sent', 'info');
            }
            closeAddEmployeeModal();
            loadEmployees(); // Refresh table
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('Failed to create employee', 'error');
        console.error(error);
    }
}
```

### Step 4: Update employee table to show Auth0 status

```javascript
// In employee table rendering
const auth0Status = emp.auth0_user_id
    ? '<span class="badge badge-success">Auth0 ✓</span>'
    : '<span class="badge badge-warning">No Auth0</span>';

// Add to Actions dropdown
const auth0Action = !emp.auth0_user_id
    ? `<button onclick="createAuth0Account(${emp.id})">Create Auth0</button>`
    : '';
```

### Step 5: Add createAuth0Account function

```javascript
async function createAuth0Account(employeeId) {
    if (!confirm('Create Auth0 account for this employee?')) return;

    try {
        const response = await fetch(`${API_BASE}/api/admin/employees/${employeeId}/create-auth0`, {
            method: 'POST',
            headers: { 'X-API-Key': API_KEY }
        });

        const data = await response.json();

        if (data.success) {
            showToast('Auth0 account created', 'success');
            loadEmployees();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('Failed to create Auth0 account', 'error');
    }
}
```

---

## Todo List

- [ ] Add "Add Employee" button
- [ ] Create Add Employee modal
- [ ] Add JavaScript form handling
- [ ] Update employee table with Auth0 status
- [ ] Add "Create Auth0" action for existing employees
- [ ] Style modal to match Industrial theme

---

## Success Criteria

- [ ] "Add Employee" button visible in Employee Management tab
- [ ] Modal opens with form fields
- [ ] Form submission creates employee
- [ ] Auth0 checkbox triggers account creation
- [ ] Table shows Auth0 status for each employee

---

## Next Steps

After completing this phase → Proceed to [Phase 05: Testing & Deploy](phase-05-testing-deploy.md)
