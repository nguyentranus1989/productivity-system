# Phase 03: Database Schema

## Context
- **Parent Plan**: [plan.md](plan.md)
- **Dependencies**: None (can run in parallel with Phase 01)
- **Docs**: [System Architecture](../../docs/system-architecture.md)

---

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-14 |
| Description | Add Auth0 columns to employees table |
| Priority | High |
| Implementation Status | ⬜ Not Started |
| Review Status | ⬜ Not Reviewed |

---

## Key Insights

1. `employees` table already exists with basic fields
2. Need to track Auth0 user ID and sync status
3. No new tables needed - just columns

---

## Requirements

1. Add `auth0_user_id` column (unique, nullable)
2. Add `auth0_sync_status` column (enum: pending, created, verified, failed)
3. Optional: Add audit log table for Auth0 operations

---

## Implementation Steps

### Step 1: Add Auth0 columns to employees

```sql
-- Run on production database
ALTER TABLE employees
ADD COLUMN auth0_user_id VARCHAR(255) UNIQUE NULL,
ADD COLUMN auth0_sync_status ENUM('pending', 'created', 'verified', 'failed') NULL;

-- Add index for faster lookups
CREATE INDEX idx_employees_auth0_user_id ON employees(auth0_user_id);
```

### Step 2: Optional - Create audit log table

```sql
-- Only if detailed logging needed
CREATE TABLE auth0_sync_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    employee_id INT NOT NULL,
    auth0_user_id VARCHAR(255),
    action VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);
```

---

## Todo List

- [ ] Run ALTER TABLE on production database
- [ ] Verify columns added successfully
- [ ] Test that existing queries still work

---

## Success Criteria

- [ ] `auth0_user_id` column exists
- [ ] `auth0_sync_status` column exists
- [ ] Existing employee queries work unchanged

---

## Execution Commands

```bash
# Connect to production database
ssh root@134.199.194.237 "mysql -h db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com -P 25060 -u doadmin -p'AVNS_OWqdUdZ2Nw_YCkGI5Eu' productivity_tracker"

# Run migration
ALTER TABLE employees
ADD COLUMN auth0_user_id VARCHAR(255) UNIQUE NULL,
ADD COLUMN auth0_sync_status ENUM('pending', 'created', 'verified', 'failed') NULL;

# Verify
DESCRIBE employees;
```

---

## Next Steps

After completing this phase → Proceed to [Phase 04: Frontend Integration](phase-04-frontend-integration.md)
