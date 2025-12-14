"""
Email Service for sending notifications to employees
Uses SendGrid API (HTTP-based, works on DigitalOcean)
"""

import requests
from config import Config


class EmailService:
    """SendGrid email sender"""

    PORTAL_URL = "https://reports.podgasus.com/employee.html"
    COMPANY_NAME = "Productivity Tracker"
    SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"

    @staticmethod
    def is_configured():
        """Check if email is properly configured"""
        return bool(getattr(Config, 'SENDGRID_API_KEY', None))

    @staticmethod
    def send_welcome_email(employee_name, pin, to_email):
        """
        Send welcome email with PIN to employee via SendGrid

        Args:
            employee_name: Employee's name
            pin: Their login PIN
            to_email: Employee's personal email

        Returns:
            dict: {success: bool, message: str}
        """
        if not EmailService.is_configured():
            return {
                'success': False,
                'message': 'Email not configured. Set SENDGRID_API_KEY in .env'
            }

        if not to_email:
            return {
                'success': False,
                'message': 'No email address provided'
            }

        try:
            # Plain text version
            text_content = f"""
Hi {employee_name},

Welcome! Your employee portal PIN has been set up.

Your PIN: {pin}

Access the portal at: {EmailService.PORTAL_URL}

Keep this PIN secure and do not share it with others.
Contact your manager if you need any help.

- {EmailService.COMPANY_NAME} Team
            """.strip()

            # HTML version
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 500px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #6366f1; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 8px 8px; }}
        .pin-box {{ background: white; border: 2px solid #6366f1; padding: 20px; text-align: center; margin: 20px 0; border-radius: 8px; }}
        .pin {{ font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #6366f1; font-family: monospace; }}
        .btn {{ display: inline-block; background: #6366f1; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; margin-top: 15px; }}
        .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">Welcome!</h1>
        </div>
        <div class="content">
            <p>Hi <strong>{employee_name}</strong>,</p>
            <p>Your employee portal PIN has been set up:</p>

            <div class="pin-box">
                <div class="pin">{pin}</div>
            </div>

            <p style="text-align: center;">
                <a href="{EmailService.PORTAL_URL}" class="btn">Access Employee Portal</a>
            </p>

            <p style="color: #666; font-size: 14px;">
                Keep this PIN secure and do not share it with others.<br>
                Contact your manager if you need any help.
            </p>
        </div>
        <div class="footer">
            <p>{EmailService.COMPANY_NAME}</p>
        </div>
    </div>
</body>
</html>
            """.strip()

            # SendGrid API payload
            from_email = getattr(Config, 'SENDGRID_FROM_EMAIL', 'noreply@podgasus.com')
            payload = {
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": from_email, "name": EmailService.COMPANY_NAME},
                "subject": f"Welcome to {EmailService.COMPANY_NAME} - Your Login PIN",
                "content": [
                    {"type": "text/plain", "value": text_content},
                    {"type": "text/html", "value": html_content}
                ]
            }

            # Send via SendGrid API
            response = requests.post(
                EmailService.SENDGRID_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {Config.SENDGRID_API_KEY}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )

            if response.status_code in (200, 201, 202):
                return {
                    'success': True,
                    'message': f'Welcome email sent to {to_email}'
                }
            else:
                return {
                    'success': False,
                    'message': f'SendGrid error: {response.status_code} - {response.text}'
                }

        except requests.exceptions.Timeout:
            return {
                'success': False,
                'message': 'Email request timed out'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Failed to send email: {str(e)}'
            }
