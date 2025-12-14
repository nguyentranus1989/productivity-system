"""
Email Service for sending notifications to employees
Uses Gmail SMTP with App Password
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config
from datetime import datetime


class EmailService:
    """Gmail SMTP email sender"""

    PORTAL_URL = "https://productivity.colorecommerce.us/employee.html"
    COMPANY_NAME = "Productivity Tracker"

    @staticmethod
    def is_configured():
        """Check if email is properly configured"""
        return all([
            Config.SMTP_HOST,
            Config.SMTP_USER,
            Config.SMTP_PASSWORD
        ])

    @staticmethod
    def send_welcome_email(employee_name, pin, to_email):
        """
        Send welcome email with PIN to employee

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
                'message': 'Email not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in .env'
            }

        if not to_email:
            return {
                'success': False,
                'message': 'No email address provided'
            }

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Welcome to {EmailService.COMPANY_NAME} - Your Login PIN"
            msg['From'] = Config.SMTP_USER
            msg['To'] = to_email

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

            # Attach both versions
            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))

            # Connect and send
            with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
                server.starttls()
                server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
                server.send_message(msg)

            return {
                'success': True,
                'message': f'Welcome email sent to {to_email}'
            }

        except smtplib.SMTPAuthenticationError:
            return {
                'success': False,
                'message': 'SMTP authentication failed. Check Gmail App Password.'
            }
        except smtplib.SMTPException as e:
            return {
                'success': False,
                'message': f'SMTP error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Failed to send email: {str(e)}'
            }
