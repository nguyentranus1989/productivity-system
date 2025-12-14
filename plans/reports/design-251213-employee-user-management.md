# Employee User Management - UI/UX Design Specification

**Date:** 2025-12-13
**Author:** UI/UX Designer
**Status:** Design Ready
**Priority:** High

---

## 1. Executive Summary

This document specifies UI/UX designs for Employee User Management features in the PodFactory Command Center. Designs maintain consistency with the existing dark cyberpunk theme while introducing intuitive patterns for CRUD operations, status management, bulk actions, and filtering.

---

## 2. Design Components

### 2.1 Create Employee Modal

#### Wireframe Description

```
+----------------------------------------------------------+
| [X]                  ADD NEW EMPLOYEE                     |
+----------------------------------------------------------+
|                                                          |
|  PERSONAL INFORMATION                                    |
|  +----------------------------------------------------+  |
|  | Full Name *                                        |  |
|  | [____________________________________]             |  |
|  +----------------------------------------------------+  |
|                                                          |
|  +----------------------------------------------------+  |
|  | Email Address *                                    |  |
|  | [____________________________________]             |  |
|  +----------------------------------------------------+  |
|                                                          |
|  ROLE & DEPARTMENT                                       |
|  +------------------------+  +------------------------+  |
|  | Department            |  | Role                   |  |
|  | [Production      v]   |  | [Operator         v]  |  |
|  +------------------------+  +------------------------+  |
|                                                          |
|  SYSTEM INTEGRATIONS                                     |
|  +----------------------------------------------------+  |
|  | Connecteam User ID (optional)                      |  |
|  | [____________________________________]             |  |
|  | (i) Auto-link from Connecteam sync if left blank   |  |
|  +----------------------------------------------------+  |
|                                                          |
|  +----------------------------------------------------+  |
|  | PodFactory Email(s) (optional)                     |  |
|  | [____________________________________]             |  |
|  | (i) Comma-separated for multiple accounts          |  |
|  +----------------------------------------------------+  |
|                                                          |
|  PAY CONFIGURATION                                       |
|  +------------------------+  +------------------------+  |
|  | Pay Type              |  | Rate                   |  |
|  | [Hourly          v]   |  | [$________ /hr]        |  |
|  +------------------------+  +------------------------+  |
|                                                          |
+----------------------------------------------------------+
|            [Cancel]                    [+ Add Employee]  |
+----------------------------------------------------------+
```

#### CSS Styling

```css
/* Modal Container */
.employee-modal-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0, 0, 0, 0.85);
    backdrop-filter: blur(4px);
    z-index: 10001;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
}

.employee-modal {
    background: linear-gradient(180deg, rgba(20, 20, 35, 0.98) 0%, rgba(10, 10, 20, 0.98) 100%);
    border: 1px solid rgba(0, 245, 255, 0.2);
    border-radius: 12px;
    max-width: 600px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow:
        0 0 50px rgba(0, 245, 255, 0.1),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
    animation: modalSlideIn 0.3s ease;
}

@keyframes modalSlideIn {
    from {
        opacity: 0;
        transform: translateY(-20px) scale(0.98);
    }
    to {
        opacity: 1;
        transform: translateY(0) scale(1);
    }
}

/* Modal Header */
.modal-header {
    padding: 20px 24px;
    border-bottom: 1px solid rgba(0, 245, 255, 0.1);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.modal-header h2 {
    font-family: 'Orbitron', sans-serif;
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 2px;
    color: #00f5ff;
    text-transform: uppercase;
    margin: 0;
    text-shadow: 0 0 20px rgba(0, 245, 255, 0.5);
}

.modal-close {
    background: none;
    border: none;
    color: #606080;
    font-size: 24px;
    cursor: pointer;
    padding: 5px;
    line-height: 1;
    transition: all 0.2s ease;
}

.modal-close:hover {
    color: #ff0044;
    text-shadow: 0 0 10px rgba(255, 0, 68, 0.5);
}

/* Form Sections */
.form-section {
    padding: 20px 24px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.form-section:last-of-type {
    border-bottom: none;
}

.form-section-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 2px;
    color: #606080;
    text-transform: uppercase;
    margin-bottom: 16px;
}

/* Form Groups */
.form-group {
    margin-bottom: 16px;
}

.form-group:last-child {
    margin-bottom: 0;
}

.form-label {
    display: block;
    font-family: 'Rajdhani', sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: #e0e0e0;
    margin-bottom: 8px;
}

.form-label .required {
    color: #ff0044;
    margin-left: 2px;
}

.form-input {
    width: 100%;
    padding: 12px 14px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    color: #e0e0e0;
    font-family: 'Rajdhani', sans-serif;
    font-size: 14px;
    transition: all 0.3s ease;
}

.form-input::placeholder {
    color: #404060;
}

.form-input:focus {
    outline: none;
    border-color: #00f5ff;
    box-shadow:
        0 0 0 3px rgba(0, 245, 255, 0.1),
        0 0 20px rgba(0, 245, 255, 0.15);
}

.form-input:invalid:not(:placeholder-shown) {
    border-color: #ff0044;
    box-shadow: 0 0 0 3px rgba(255, 0, 68, 0.1);
}

.form-hint {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 6px;
    font-size: 12px;
    color: #606080;
}

.form-hint i {
    color: #00f5ff;
    font-size: 10px;
}

/* Two-Column Layout */
.form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}

@media (max-width: 500px) {
    .form-row {
        grid-template-columns: 1fr;
    }
}

/* Select Dropdown */
.form-select {
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2300f5ff' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 12px center;
    padding-right: 36px;
}

/* Modal Footer */
.modal-footer {
    padding: 16px 24px;
    border-top: 1px solid rgba(0, 245, 255, 0.1);
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    background: rgba(0, 0, 0, 0.2);
}
```

#### Interaction Notes
1. Modal opens with slide-in animation (0.3s)
2. Click outside or press ESC to close
3. Required fields marked with red asterisk
4. Real-time validation on blur
5. Submit button disabled until required fields valid
6. Loading state shows spinner on submit button
7. Success: Close modal + show toast notification
8. Error: Show inline error messages

---

### 2.2 Edit Employee Modal

#### Wireframe Description

```
+----------------------------------------------------------+
| [X]                  EDIT EMPLOYEE                        |
+----------------------------------------------------------+
|                                                          |
|  +------------------+                                    |
|  |   [Avatar]       |  John Smith                        |
|  |    (initials)    |  Employee ID: EMP-001              |
|  +------------------+  Status: [Active v]                |
|                                                          |
+----------------------------------------------------------+
|  [Personal] [Integrations] [Pay & Role] [History]        |
+----------------------------------------------------------+
|                                                          |
|  (Tab content same as Create form sections)              |
|                                                          |
+----------------------------------------------------------+
|     [Delete Employee]         [Cancel]    [Save Changes] |
+----------------------------------------------------------+
```

#### Key Differences from Create
- Shows employee avatar/initials at top
- Displays Employee ID (read-only)
- Inline status dropdown for quick changes
- Tabbed interface for organization
- Delete button (left-aligned, destructive style)
- "History" tab shows audit log of changes

#### Additional CSS

```css
/* Employee Header in Edit Modal */
.employee-edit-header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px 24px;
    background: rgba(0, 245, 255, 0.03);
    border-bottom: 1px solid rgba(0, 245, 255, 0.1);
}

.employee-avatar {
    width: 60px;
    height: 60px;
    border-radius: 8px;
    background: linear-gradient(135deg, #00f5ff 0%, #ff00ff 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Orbitron', sans-serif;
    font-size: 20px;
    font-weight: 700;
    color: #0a0a0f;
}

.employee-header-info h3 {
    font-family: 'Rajdhani', sans-serif;
    font-size: 18px;
    font-weight: 600;
    color: #e0e0e0;
    margin: 0 0 4px 0;
}

.employee-header-meta {
    font-family: 'Orbitron', sans-serif;
    font-size: 10px;
    color: #606080;
    letter-spacing: 1px;
}

/* Modal Tabs */
.modal-tabs {
    display: flex;
    border-bottom: 1px solid rgba(0, 245, 255, 0.1);
    background: rgba(0, 0, 0, 0.2);
    overflow-x: auto;
}

.modal-tab {
    padding: 12px 20px;
    background: none;
    border: none;
    color: #606080;
    font-family: 'Orbitron', sans-serif;
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
    cursor: pointer;
    position: relative;
    white-space: nowrap;
    transition: all 0.2s ease;
}

.modal-tab:hover {
    color: #e0e0e0;
}

.modal-tab.active {
    color: #00f5ff;
}

.modal-tab.active::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 0;
    right: 0;
    height: 2px;
    background: #00f5ff;
    box-shadow: 0 0 10px rgba(0, 245, 255, 0.5);
}

/* Delete Button */
.btn-delete {
    background: transparent;
    border: 1px solid rgba(255, 0, 68, 0.3);
    color: #ff0044;
    padding: 10px 16px;
    font-family: 'Orbitron', sans-serif;
    font-size: 11px;
    letter-spacing: 1px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    margin-right: auto;
}

.btn-delete:hover {
    background: rgba(255, 0, 68, 0.1);
    border-color: #ff0044;
    box-shadow: 0 0 20px rgba(255, 0, 68, 0.2);
}
```

---

### 2.3 Employee Status Management

#### Status Types & Visual Design

| Status | Color | Background | Icon | Description |
|--------|-------|------------|------|-------------|
| Active | `#22c55e` | `rgba(34, 197, 94, 0.15)` | `fa-check-circle` | Normal working status |
| Suspended | `#fbbf24` | `rgba(251, 191, 36, 0.15)` | `fa-pause-circle` | Temporarily disabled |
| Archived | `#a855f7` | `rgba(168, 85, 247, 0.15)` | `fa-archive` | Soft-deleted, hidden by default |

#### Status Badge CSS

```css
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 20px;
    font-family: 'Orbitron', sans-serif;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.status-badge i {
    font-size: 9px;
}

.status-badge--active {
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
    border: 1px solid rgba(34, 197, 94, 0.3);
}

.status-badge--suspended {
    background: rgba(251, 191, 36, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(251, 191, 36, 0.3);
}

.status-badge--archived {
    background: rgba(168, 85, 247, 0.15);
    color: #a855f7;
    border: 1px solid rgba(168, 85, 247, 0.3);
}

/* Animated pulse for active status */
.status-badge--active::before {
    content: '';
    width: 6px;
    height: 6px;
    background: #22c55e;
    border-radius: 50%;
    animation: statusPulse 2s ease-in-out infinite;
}

@keyframes statusPulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); }
    50% { opacity: 0.8; box-shadow: 0 0 0 4px rgba(34, 197, 94, 0); }
}
```

#### Inline Status Dropdown (Table)

```css
.status-select {
    appearance: none;
    background: transparent;
    border: 1px solid transparent;
    padding: 4px 24px 4px 8px;
    border-radius: 20px;
    font-family: 'Orbitron', sans-serif;
    font-size: 10px;
    letter-spacing: 1px;
    cursor: pointer;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 8px center;
    transition: all 0.2s ease;
}

.status-select:hover {
    border-color: rgba(255, 255, 255, 0.2);
}

.status-select--active {
    color: #22c55e;
}

.status-select--suspended {
    color: #fbbf24;
}

.status-select--archived {
    color: #a855f7;
}

.status-select option {
    background: #1a1a2e;
    color: #e0e0e0;
}
```

---

### 2.4 Bulk Selection UI

#### Wireframe Description

```
+----------------------------------------------------------+
|  Search: [____________________] [Status v] [Dept v]      |
+----------------------------------------------------------+
|  [ ] Select All (Page)                                   |
+----------------------------------------------------------+
| [ ] | ID    | Name        | Email         | Status |     |
| [x] | E-001 | John Smith  | john@...      | Active |     |
| [x] | E-002 | Jane Doe    | jane@...      | Active |     |
| [ ] | E-003 | Bob Wilson  | bob@...       | Susp.  |     |
+----------------------------------------------------------+

+----------------------------------------------------------+
| BULK ACTION BAR (appears when items selected)            |
| 2 employees selected                                     |
| [Set Active] [Suspend] [Archive] [Export] | [Clear]      |
+----------------------------------------------------------+
```

#### CSS Styling

```css
/* Checkbox Styling */
.emp-checkbox {
    appearance: none;
    width: 18px;
    height: 18px;
    border: 2px solid rgba(0, 245, 255, 0.3);
    border-radius: 4px;
    background: transparent;
    cursor: pointer;
    position: relative;
    transition: all 0.2s ease;
}

.emp-checkbox:hover {
    border-color: #00f5ff;
    box-shadow: 0 0 10px rgba(0, 245, 255, 0.2);
}

.emp-checkbox:checked {
    background: #00f5ff;
    border-color: #00f5ff;
}

.emp-checkbox:checked::after {
    content: '';
    position: absolute;
    top: 2px;
    left: 5px;
    width: 5px;
    height: 9px;
    border: solid #0a0a0f;
    border-width: 0 2px 2px 0;
    transform: rotate(45deg);
}

/* Indeterminate state for "Select All" */
.emp-checkbox:indeterminate {
    background: rgba(0, 245, 255, 0.5);
    border-color: #00f5ff;
}

.emp-checkbox:indeterminate::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 3px;
    right: 3px;
    height: 2px;
    background: #0a0a0f;
    transform: translateY(-50%);
}

/* Table Row Selection State */
tr.selected {
    background: rgba(0, 245, 255, 0.08) !important;
}

tr.selected td:first-child {
    box-shadow: inset 3px 0 0 #00f5ff;
}

/* Bulk Action Bar */
.bulk-action-bar {
    position: fixed;
    bottom: 0;
    left: 260px; /* Sidebar width */
    right: 0;
    background: linear-gradient(180deg, rgba(10, 10, 20, 0.98) 0%, rgba(5, 5, 15, 0.99) 100%);
    border-top: 1px solid rgba(0, 245, 255, 0.2);
    padding: 16px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    z-index: 100;
    transform: translateY(100%);
    transition: transform 0.3s ease;
    box-shadow: 0 -10px 40px rgba(0, 0, 0, 0.5);
}

.bulk-action-bar.visible {
    transform: translateY(0);
}

.bulk-action-bar__count {
    font-family: 'Orbitron', sans-serif;
    font-size: 12px;
    color: #00f5ff;
    letter-spacing: 1px;
}

.bulk-action-bar__count strong {
    font-size: 16px;
    margin-right: 4px;
}

.bulk-action-bar__actions {
    display: flex;
    gap: 8px;
    align-items: center;
}

.bulk-action-bar__divider {
    width: 1px;
    height: 24px;
    background: rgba(255, 255, 255, 0.1);
    margin: 0 8px;
}

/* Bulk Action Buttons */
.bulk-btn {
    padding: 8px 14px;
    border-radius: 6px;
    font-family: 'Orbitron', sans-serif;
    font-size: 10px;
    letter-spacing: 1px;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 6px;
}

.bulk-btn--primary {
    background: rgba(0, 245, 255, 0.15);
    border: 1px solid rgba(0, 245, 255, 0.3);
    color: #00f5ff;
}

.bulk-btn--primary:hover {
    background: rgba(0, 245, 255, 0.25);
    box-shadow: 0 0 15px rgba(0, 245, 255, 0.2);
}

.bulk-btn--success {
    background: rgba(34, 197, 94, 0.15);
    border: 1px solid rgba(34, 197, 94, 0.3);
    color: #22c55e;
}

.bulk-btn--warning {
    background: rgba(251, 191, 36, 0.15);
    border: 1px solid rgba(251, 191, 36, 0.3);
    color: #fbbf24;
}

.bulk-btn--danger {
    background: rgba(255, 0, 68, 0.15);
    border: 1px solid rgba(255, 0, 68, 0.3);
    color: #ff0044;
}

.bulk-btn--ghost {
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #808080;
}

/* Mobile Responsive */
@media (max-width: 768px) {
    .bulk-action-bar {
        left: 0;
        flex-direction: column;
        gap: 12px;
        padding: 12px 16px;
    }

    .bulk-action-bar__actions {
        width: 100%;
        flex-wrap: wrap;
        justify-content: center;
    }
}
```

---

### 2.5 Confirmation Dialogs

#### Destructive Action Confirmation

```
+--------------------------------------------------+
|                                                  |
|    [!]  SUSPEND EMPLOYEE                         |
|                                                  |
|    Are you sure you want to suspend             |
|    John Smith?                                   |
|                                                  |
|    This will:                                    |
|    - Remove from active schedules               |
|    - Hide from productivity reports             |
|    - Preserve all historical data               |
|                                                  |
|    [ ] I understand this action                 |
|                                                  |
|    [Cancel]              [Suspend Employee]     |
|                                                  |
+--------------------------------------------------+
```

#### CSS Styling

```css
.confirm-dialog {
    max-width: 420px;
    text-align: center;
}

.confirm-dialog__icon {
    width: 64px;
    height: 64px;
    margin: 0 auto 20px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 28px;
}

.confirm-dialog__icon--warning {
    background: rgba(251, 191, 36, 0.15);
    color: #fbbf24;
    border: 2px solid rgba(251, 191, 36, 0.3);
}

.confirm-dialog__icon--danger {
    background: rgba(255, 0, 68, 0.15);
    color: #ff0044;
    border: 2px solid rgba(255, 0, 68, 0.3);
    animation: dangerPulse 2s ease-in-out infinite;
}

@keyframes dangerPulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(255, 0, 68, 0.3); }
    50% { box-shadow: 0 0 0 10px rgba(255, 0, 68, 0); }
}

.confirm-dialog__title {
    font-family: 'Orbitron', sans-serif;
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 2px;
    color: #e0e0e0;
    margin-bottom: 12px;
    text-transform: uppercase;
}

.confirm-dialog__message {
    font-family: 'Rajdhani', sans-serif;
    font-size: 15px;
    color: #b0b0b0;
    margin-bottom: 20px;
    line-height: 1.5;
}

.confirm-dialog__consequences {
    background: rgba(0, 0, 0, 0.3);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 20px;
    text-align: left;
}

.confirm-dialog__consequences h4 {
    font-family: 'Orbitron', sans-serif;
    font-size: 10px;
    letter-spacing: 1px;
    color: #606080;
    margin-bottom: 10px;
    text-transform: uppercase;
}

.confirm-dialog__consequences ul {
    list-style: none;
    padding: 0;
    margin: 0;
}

.confirm-dialog__consequences li {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 0;
    font-size: 13px;
    color: #a0a0a0;
}

.confirm-dialog__consequences li i {
    color: #fbbf24;
    font-size: 10px;
}

/* Checkbox Confirmation */
.confirm-checkbox-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    margin-bottom: 24px;
    padding: 12px;
    background: rgba(255, 0, 68, 0.05);
    border: 1px solid rgba(255, 0, 68, 0.1);
    border-radius: 8px;
}

.confirm-checkbox-wrapper label {
    font-size: 13px;
    color: #b0b0b0;
    cursor: pointer;
}

/* Footer Buttons */
.confirm-dialog__footer {
    display: flex;
    gap: 12px;
    justify-content: center;
}

.confirm-dialog__footer .btn-cancel {
    flex: 1;
    max-width: 150px;
}

.confirm-dialog__footer .btn-confirm {
    flex: 1;
    max-width: 180px;
}

.btn-confirm:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}
```

---

### 2.6 Search/Filter Enhancement

#### Filter Bar Wireframe

```
+------------------------------------------------------------------+
| Search: [________________________] [x]                            |
|                                                                  |
| Filters:                                                         |
| [Status: All v] [Department: All v] [Role: All v] [Pay Type v]  |
|                                                                  |
| Active Filters: [Status: Active x] [Dept: Production x] [Clear] |
+------------------------------------------------------------------+
```

#### CSS Styling

```css
/* Filter Container */
.filter-bar {
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(0, 245, 255, 0.1);
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 20px;
}

/* Search Input with Icon */
.search-wrapper {
    position: relative;
    margin-bottom: 16px;
}

.search-wrapper i {
    position: absolute;
    left: 14px;
    top: 50%;
    transform: translateY(-50%);
    color: #606080;
    font-size: 14px;
    pointer-events: none;
}

.search-input {
    width: 100%;
    padding: 12px 40px 12px 42px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    color: #e0e0e0;
    font-size: 14px;
    transition: all 0.3s ease;
}

.search-input:focus {
    border-color: #00f5ff;
    box-shadow: 0 0 0 3px rgba(0, 245, 255, 0.1);
}

.search-clear {
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    color: #606080;
    cursor: pointer;
    padding: 4px;
    opacity: 0;
    transition: opacity 0.2s ease;
}

.search-input:not(:placeholder-shown) + .search-clear {
    opacity: 1;
}

.search-clear:hover {
    color: #ff0044;
}

/* Filter Dropdowns Row */
.filter-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 12px;
}

.filter-row label {
    font-family: 'Orbitron', sans-serif;
    font-size: 10px;
    letter-spacing: 1px;
    color: #606080;
    margin-bottom: 4px;
    display: block;
}

.filter-select {
    min-width: 140px;
    padding: 8px 32px 8px 12px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    color: #e0e0e0;
    font-family: 'Rajdhani', sans-serif;
    font-size: 13px;
    cursor: pointer;
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23606080' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 10px center;
    transition: all 0.2s ease;
}

.filter-select:hover {
    border-color: rgba(0, 245, 255, 0.3);
}

.filter-select:focus {
    outline: none;
    border-color: #00f5ff;
}

/* Active Filters Tags */
.active-filters {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.active-filters__label {
    font-family: 'Orbitron', sans-serif;
    font-size: 10px;
    letter-spacing: 1px;
    color: #606080;
}

.filter-tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px 4px 10px;
    background: rgba(0, 245, 255, 0.1);
    border: 1px solid rgba(0, 245, 255, 0.2);
    border-radius: 4px;
    font-family: 'Rajdhani', sans-serif;
    font-size: 12px;
    color: #00f5ff;
}

.filter-tag__remove {
    background: none;
    border: none;
    color: #00f5ff;
    cursor: pointer;
    padding: 0;
    font-size: 14px;
    line-height: 1;
    opacity: 0.7;
    transition: opacity 0.2s ease;
}

.filter-tag__remove:hover {
    opacity: 1;
}

.clear-all-filters {
    background: none;
    border: none;
    color: #808080;
    font-size: 12px;
    cursor: pointer;
    padding: 4px 8px;
    margin-left: auto;
    transition: color 0.2s ease;
}

.clear-all-filters:hover {
    color: #ff0044;
}
```

---

## 3. User Interaction Flows

### 3.1 Create Employee Flow
1. User clicks "Add Employee" tab or button
2. Modal opens with empty form
3. User fills required fields (name, email)
4. Optional: fills department, role, integrations
5. Clicks "Add Employee" button
6. Loading spinner on button
7. Success: Modal closes, toast shows, table refreshes
8. Error: Inline error message, focus on problem field

### 3.2 Edit Employee Flow
1. User clicks edit icon on table row
2. Modal opens with pre-filled data
3. Tabs allow section navigation
4. Changes tracked (dirty state)
5. "Save Changes" only enabled if changes made
6. Confirm dialog for status changes
7. Success/error handling same as create

### 3.3 Delete/Archive Flow
1. User clicks delete button
2. Confirmation dialog opens
3. Shows consequences list
4. Requires checkbox confirmation
5. Button enabled after checkbox
6. Clicking confirm shows loading
7. Success: Dialog closes, row removed/updated
8. Can undo within 5 seconds (toast with undo button)

### 3.4 Bulk Action Flow
1. User checks one or more rows
2. Bulk action bar slides up from bottom
3. Shows count of selected items
4. Available actions based on selection
5. Clicking action shows confirmation
6. Batch operation executes
7. Progress indicator for large batches
8. Summary toast on completion

---

## 4. Accessibility Considerations

### Keyboard Navigation
- Tab order: Search > Filters > Table headers > Table rows
- Enter/Space to toggle checkboxes
- Arrow keys to navigate table rows
- Escape to close modals/dialogs
- Focus trap within modals

### ARIA Attributes
```html
<div role="dialog" aria-modal="true" aria-labelledby="modal-title">
<button aria-label="Close modal">
<input aria-describedby="email-hint" aria-invalid="true">
<table role="grid" aria-label="Employee list">
<div role="status" aria-live="polite">2 employees selected</div>
```

### Screen Reader Announcements
- Selection changes: "2 employees selected"
- Filter changes: "Showing 15 of 50 employees"
- Status changes: "Employee status changed to suspended"
- Form errors: "Error: Email address is required"

### Color Contrast
- All text meets WCAG 2.1 AA (4.5:1 for normal, 3:1 for large)
- Status indicators use icons alongside colors
- Focus states clearly visible (cyan outline)

### Reduced Motion
```css
@media (prefers-reduced-motion: reduce) {
    .bulk-action-bar,
    .employee-modal,
    .status-badge--active::before {
        animation: none;
        transition-duration: 0.01ms;
    }
}
```

---

## 5. Mobile Responsiveness

### Breakpoints
| Breakpoint | Changes |
|------------|---------|
| < 768px | Single column forms, stacked filters, full-width bulk bar |
| < 500px | Simplified table (hide some columns), card view option |

### Mobile Table Adjustments
```css
@media (max-width: 768px) {
    /* Hide less important columns */
    .emp-table th:nth-child(4),
    .emp-table td:nth-child(4),
    .emp-table th:nth-child(5),
    .emp-table td:nth-child(5) {
        display: none;
    }

    /* Reduce padding */
    .emp-table th,
    .emp-table td {
        padding: 10px 8px;
        font-size: 12px;
    }

    /* Touch-friendly action buttons */
    .action-btn {
        min-width: 44px;
        min-height: 44px;
    }
}

@media (max-width: 500px) {
    /* Switch to card view */
    .emp-table {
        display: none;
    }

    .emp-cards {
        display: block;
    }

    .emp-card {
        background: var(--cyber-panel);
        border: 1px solid var(--cyber-border);
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
}
```

### Mobile Modal
```css
@media (max-width: 600px) {
    .employee-modal {
        margin: 0;
        border-radius: 12px 12px 0 0;
        max-height: 85vh;
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        animation: modalSlideUp 0.3s ease;
    }

    @keyframes modalSlideUp {
        from {
            transform: translateY(100%);
        }
        to {
            transform: translateY(0);
        }
    }
}
```

---

## 6. Implementation Notes

### HTML Structure Example (Create Modal)

```html
<div class="employee-modal-overlay" id="createEmployeeModal" style="display: none;" onclick="if(event.target === this) closeCreateModal()">
    <div class="employee-modal" role="dialog" aria-modal="true" aria-labelledby="createModalTitle">
        <div class="modal-header">
            <h2 id="createModalTitle">Add New Employee</h2>
            <button class="modal-close" onclick="closeCreateModal()" aria-label="Close modal">&times;</button>
        </div>

        <form id="createEmployeeForm" onsubmit="return handleCreateEmployee(event)">
            <div class="form-section">
                <div class="form-section-title">Personal Information</div>

                <div class="form-group">
                    <label class="form-label" for="empName">
                        Full Name <span class="required">*</span>
                    </label>
                    <input type="text" id="empName" name="name" class="form-input" required
                           placeholder="Enter employee name">
                </div>

                <div class="form-group">
                    <label class="form-label" for="empEmail">
                        Email Address <span class="required">*</span>
                    </label>
                    <input type="email" id="empEmail" name="email" class="form-input" required
                           placeholder="employee@company.com" aria-describedby="emailHint">
                    <div class="form-hint" id="emailHint">
                        <i class="fas fa-info-circle"></i>
                        Used for system notifications
                    </div>
                </div>
            </div>

            <div class="form-section">
                <div class="form-section-title">Role & Department</div>

                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label" for="empDept">Department</label>
                        <select id="empDept" name="department" class="form-input form-select">
                            <option value="">Select...</option>
                            <option value="production">Production</option>
                            <option value="shipping">Shipping</option>
                            <option value="quality">Quality</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label class="form-label" for="empRole">Role</label>
                        <select id="empRole" name="role" class="form-input form-select">
                            <option value="">Select...</option>
                            <option value="operator">Operator</option>
                            <option value="lead">Team Lead</option>
                            <option value="supervisor">Supervisor</option>
                        </select>
                    </div>
                </div>
            </div>

            <!-- Additional sections... -->

            <div class="modal-footer">
                <button type="button" class="btn-action btn-secondary" onclick="closeCreateModal()">Cancel</button>
                <button type="submit" class="btn-action btn-primary" id="createSubmitBtn">
                    <i class="fas fa-plus"></i> Add Employee
                </button>
            </div>
        </form>
    </div>
</div>
```

### JavaScript Patterns

```javascript
// Modal open/close
function openCreateModal() {
    document.getElementById('createEmployeeModal').style.display = 'flex';
    document.getElementById('empName').focus();
    document.body.style.overflow = 'hidden';
}

function closeCreateModal() {
    document.getElementById('createEmployeeModal').style.display = 'none';
    document.getElementById('createEmployeeForm').reset();
    document.body.style.overflow = '';
}

// ESC key handler
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeCreateModal();
        closeEditModal();
    }
});

// Bulk selection
let selectedEmployees = new Set();

function toggleEmployeeSelection(id) {
    if (selectedEmployees.has(id)) {
        selectedEmployees.delete(id);
    } else {
        selectedEmployees.add(id);
    }
    updateBulkActionBar();
}

function updateBulkActionBar() {
    const bar = document.querySelector('.bulk-action-bar');
    const count = selectedEmployees.size;

    if (count > 0) {
        bar.classList.add('visible');
        bar.querySelector('.bulk-action-bar__count strong').textContent = count;
    } else {
        bar.classList.remove('visible');
    }
}
```

---

## 7. Unresolved Questions

1. **Audit History**: How much edit history should be shown in the History tab? Last 10 changes? All changes?

2. **Bulk Limits**: Should there be a limit on bulk operations (e.g., max 50 at once)?

3. **Undo Duration**: 5 seconds for undo toast - is this sufficient?

4. **Department List**: Are departments dynamic (from API) or static/hardcoded?

5. **Role Permissions**: Does the current user role affect which status changes are allowed?

---

*Report generated: 2025-12-13*
