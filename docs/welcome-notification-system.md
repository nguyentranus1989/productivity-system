# Welcome Notification System

## Overview
Email notification system that sends welcome messages with login credentials (User ID + PIN) to employees when their PIN is set or reset.

## Implementation Date
2025-12-14

## Features
- Send welcome email on PIN set/reset (checkbox option)
- Manual "Send Welcome" button in Actions dropdown
- Industrial theme email template
- Async email sending (non-blocking API)

---

## Email Provider: SendGrid

### Why SendGrid?
DigitalOcean blocks SMTP ports (587, 465) by default to prevent spam. SendGrid uses HTTPS API calls which bypasses this restriction.

### Configuration
```env
# backend/.env
SENDGRID_API_KEY=<your-sendgrid-api-key>
SENDGRID_FROM_EMAIL=colorecommercellc@gmail.com
```

**Note**: Actual API key stored in `keys/credentials-backup.txt` (gitignored)

### Sender Verification
SendGrid requires verified sender identity. We verified `colorecommercellc@gmail.com` as Single Sender.

To verify new sender:
1. Go to SendGrid → Settings → Sender Authentication
2. Click "Verify a Single Sender"
3. Add email and complete verification

### Free Tier Limits
- 100 emails/day on free plan
- Sufficient for employee onboarding use case

---

## Database Schema

Added columns to `employees` table:
```sql
ALTER TABLE employees
ADD COLUMN personal_email VARCHAR(255) NULL,
ADD COLUMN phone_number VARCHAR(20) NULL,
ADD COLUMN welcome_sent_at DATETIME NULL;
```

---

## Backend Files

### backend/services/email_service.py
SendGrid API email sender with Industrial theme template.

Key methods:
- `is_configured()` - Check if SENDGRID_API_KEY is set
- `send_welcome_email(employee_name, pin, to_email, employee_id)` - Send welcome email

### backend/api/user_management.py
Employee management API endpoints.

Key functions:
- `send_email_async()` - Background thread email sender (prevents API timeout)

Endpoints:
- `POST /api/admin/employees/<id>/set-pin` - Set PIN with optional notification
- `POST /api/admin/employees/<id>/reset-pin` - Reset PIN with optional notification
- `POST /api/admin/employees/<id>/send-welcome` - Manual resend welcome email
- `POST /api/admin/employees/<id>/update-contact` - Update personal email/phone

### backend/config.py
Added config variables:
```python
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
SENDGRID_FROM_EMAIL = os.getenv('SENDGRID_FROM_EMAIL', 'noreply@podgasus.com')
```

---

## Frontend Changes

### manager.html - Employee Management Tab

#### Table Columns
- ID, Name, Email (personal), Status, PIN, Actions

#### PIN Modal
- PIN input field (4-6 digits)
- "Send welcome email" checkbox (enabled only if personal email exists)
- Set PIN button
- Reset to Random PIN button

#### Actions Dropdown
- Edit Email - Update personal email
- PIN - Open PIN modal
- Send Welcome - Manual resend (visible when PIN + email exist)
- Map - Map to Connecteam
- Archive - Deactivate employee

---

## Email Template

### Design: Industrial Theme
- Dark background (#0f1419)
- Amber header gradient (#f59e0b → #fbbf24)
- Green User ID card with icon
- Amber PIN card with icon
- Matching CTA button

### Content
```
Subject: Welcome to Productivity Tracker - Your Login PIN

- Welcome header
- User ID (green card)
- PIN Code (amber card)
- "Access Employee Portal" button
- Security reminder
```

---

## API Request Examples

### Set PIN with notification
```bash
curl -X POST 'https://reports.podgasus.com/api/admin/employees/35/set-pin' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-api-key-123' \
  -d '{"pin": "1234", "send_notification": true}'
```

Response:
```json
{
  "success": true,
  "employee_id": 35,
  "employee_name": "Nguyen Tran",
  "pin": "1234",
  "message": "PIN set successfully",
  "notification": {"queued": true}
}
```

### Manual send welcome
```bash
curl -X POST 'https://reports.podgasus.com/api/admin/employees/35/send-welcome' \
  -H 'X-API-Key: dev-api-key-123'
```

---

## Known Issues & Solutions

### Issue: API timeout when sending email
**Cause**: SMTP/API calls take 5-15 seconds
**Solution**: Email sent in background thread (`send_email_async`), API returns immediately with `notification.queued: true`

### Issue: Flask startup takes 30-60 seconds
**Cause**: Database connection pool initialization, scheduler startup
**Solution**: Wait for port 5000 to be available before making requests

### Issue: bcrypt PIN hashing takes 6 seconds
**Cause**: bcrypt with 10 rounds is intentionally slow for security
**Note**: This is acceptable, not a bug

---

## Credentials Reference

Stored in `keys/credentials-backup.txt` (gitignored):
- SendGrid API Key
- SendGrid From Email
- Gmail SMTP (legacy, disabled)

---

## Testing Checklist

1. Add personal email to employee
2. Open PIN modal → checkbox should be enabled
3. Set PIN with "Send welcome email" checked
4. Verify email received with correct User ID and PIN
5. Test "Send Welcome" button in Actions dropdown
6. Test "Reset to Random PIN" with notification

---

## Production Deployment

Server: 134.199.194.237

```bash
# Deploy
ssh root@134.199.194.237
cd /var/www/productivity-system
git pull origin main
pm2 restart flask-backend

# Wait ~40 seconds for Flask to start
sleep 40

# Verify
curl -s http://127.0.0.1:5000/api/system/health -H 'X-API-Key: dev-api-key-123'
```

---

## Files Modified/Created

### Created
- `backend/services/email_service.py` - SendGrid email service
- `docs/welcome-notification-system.md` - This documentation

### Modified
- `backend/config.py` - Added SendGrid config
- `backend/api/user_management.py` - Added async email, updated endpoints
- `backend/.env` - Added SendGrid credentials
- `frontend/manager.html` - PIN modal with notification checkbox, email column
- `keys/credentials-backup.txt` - Added SendGrid credentials

### Demo files (can be deleted)
- `frontend/email-demo-1.html`
- `frontend/email-demo-2.html`
