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
    def send_welcome_email(employee_name, pin, to_email, employee_id=None):
        """
        Send welcome email with PIN to employee via SendGrid

        Args:
            employee_name: Employee's name
            pin: Their login PIN
            to_email: Employee's personal email
            employee_id: Employee's user ID

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
            id_line = f"Your User ID: {employee_id}\n" if employee_id else ""
            text_content = f"""
Hi {employee_name},

Welcome! Your employee portal account has been set up.

{id_line}Your PIN: {pin}

Access the portal at: {EmailService.PORTAL_URL}

Keep this PIN secure and do not share it with others.
Contact your manager if you need any help.

- {EmailService.COMPANY_NAME} Team
            """.strip()

            # HTML version - Stacked Cards Design
            id_card = f"""
            <div style="background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border: 2px solid #22c55e; border-radius: 12px; padding: 20px; margin: 15px 0; display: flex; align-items: center;">
                <div style="width: 50px; height: 50px; border-radius: 50%; background: #22c55e; color: white; display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: bold; margin-right: 15px;">ID</div>
                <div>
                    <div style="font-size: 13px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Your User ID</div>
                    <div style="font-size: 32px; font-weight: bold; font-family: 'Courier New', monospace; letter-spacing: 4px; color: #15803d;">{employee_id}</div>
                </div>
            </div>
            """ if employee_id else ""

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
    </style>
</head>
<body>
    <div style="max-width: 500px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; padding: 25px; text-align: center; border-radius: 12px 12px 0 0;">
            <h1 style="margin: 0; font-size: 28px;">Welcome!</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">Your account is ready</p>
        </div>
        <div style="background: #ffffff; padding: 30px; border-radius: 0 0 12px 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <p>Hi <strong>{employee_name}</strong>,</p>
            <p>Your employee portal credentials:</p>

            {id_card}

            <div style="background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%); border: 2px solid #6366f1; border-radius: 12px; padding: 20px; margin: 15px 0; display: flex; align-items: center;">
                <div style="width: 50px; height: 50px; border-radius: 50%; background: #6366f1; color: white; display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: bold; margin-right: 15px;">#</div>
                <div>
                    <div style="font-size: 13px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Your PIN Code</div>
                    <div style="font-size: 32px; font-weight: bold; font-family: 'Courier New', monospace; letter-spacing: 4px; color: #4f46e5;">{pin}</div>
                </div>
            </div>

            <p style="text-align: center;">
                <a href="{EmailService.PORTAL_URL}" style="display: inline-block; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; padding: 14px 35px; text-decoration: none; border-radius: 8px; margin-top: 20px; font-weight: 600;">Access Employee Portal</a>
            </p>

            <p style="color: #666; font-size: 14px; margin-top: 25px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                Keep these credentials secure and do not share them.<br>
                Contact your manager if you need any help.
            </p>
        </div>
        <div style="text-align: center; color: #666; font-size: 12px; margin-top: 20px;">
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
