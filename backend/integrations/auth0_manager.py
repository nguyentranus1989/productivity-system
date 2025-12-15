"""
Auth0 Manager - Handles user creation, deletion, and role management
Uses Management API with client credentials grant
"""

import time
import string
import secrets
import requests
from config import Config


class Auth0TokenManager:
    """Singleton token manager with auto-refresh"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.token = None
            cls._instance.token_expires_at = 0
        return cls._instance

    def get_access_token(self):
        """Get valid access token, refresh if expired or expiring soon"""
        # Refresh 5 minutes before expiry
        if self.token and time.time() < self.token_expires_at - 300:
            return self.token
        return self._refresh_token()

    def _refresh_token(self):
        """Request new token from Auth0"""
        if not Auth0Manager.is_configured():
            raise Exception("Auth0 not configured")

        response = requests.post(
            f"https://{Config.AUTH0_DOMAIN}/oauth/token",
            json={
                "client_id": Config.AUTH0_CLIENT_ID,
                "client_secret": Config.AUTH0_CLIENT_SECRET,
                "audience": f"https://{Config.AUTH0_DOMAIN}/api/v2/",
                "grant_type": "client_credentials"
            },
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code != 200:
            raise Exception(f"Auth0 token request failed: {response.text}")

        data = response.json()
        self.token = data['access_token']
        self.token_expires_at = time.time() + data['expires_in']
        return self.token


# Singleton instance
_token_manager = Auth0TokenManager()


class Auth0Manager:
    """High-level Auth0 user management"""

    # Workspace options
    WORKSPACES = {
        'MS': 'Mississippi',
        'TX': 'Texas'
    }

    @staticmethod
    def is_configured():
        """Check if Auth0 is properly configured"""
        return all([
            Config.AUTH0_DOMAIN,
            Config.AUTH0_CLIENT_ID,
            Config.AUTH0_CLIENT_SECRET
        ])

    @staticmethod
    def _get_headers():
        """Get authorization headers"""
        token = _token_manager.get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    @staticmethod
    def _base_url():
        return f"https://{Config.AUTH0_DOMAIN}/api/v2"

    @staticmethod
    def generate_password(length=10):
        """Generate secure random password"""
        # Ensure at least one of each: upper, lower, digit, special
        chars = string.ascii_letters + string.digits + "!@#$%"
        password = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice("!@#$%")
        ]
        # Fill rest with random chars
        password += [secrets.choice(chars) for _ in range(length - 4)]
        # Shuffle
        secrets.SystemRandom().shuffle(password)
        return ''.join(password)

    @staticmethod
    def get_roles():
        """Get all roles from Auth0"""
        if not Auth0Manager.is_configured():
            return {'success': False, 'message': 'Auth0 not configured', 'roles': []}

        try:
            response = requests.get(
                f"{Auth0Manager._base_url()}/roles",
                headers=Auth0Manager._get_headers(),
                timeout=10
            )

            if response.status_code == 200:
                roles = response.json()
                return {
                    'success': True,
                    'roles': [{'id': r['id'], 'name': r['name'], 'description': r.get('description', '')}
                              for r in roles]
                }
            else:
                return {'success': False, 'message': f"Failed to fetch roles: {response.text}", 'roles': []}

        except Exception as e:
            return {'success': False, 'message': str(e), 'roles': []}

    @staticmethod
    def create_user(employee_data):
        """
        Create Auth0 user account

        Args:
            employee_data: {
                'employee_id': int,
                'name': str,
                'email': str,
                'role_id': str (Auth0 role ID),
                'workspace': str ('TX' or 'MS'),
                'password': str (optional - custom password, generates random if not provided)
            }

        Returns:
            {'success': bool, 'user_id': str, 'password': str, 'message': str}
        """
        if not Auth0Manager.is_configured():
            return {'success': False, 'message': 'Auth0 not configured'}

        try:
            # Use custom password or generate random
            password = employee_data.get('password') or Auth0Manager.generate_password()

            # Create user payload
            payload = {
                "email": employee_data['email'],
                "name": employee_data['name'],
                "password": password,
                "email_verified": True,  # No verification email
                "connection": "Username-Password-Authentication",
                "app_metadata": {
                    "employee_id": employee_data.get('employee_id'),
                    "workspace": employee_data.get('workspace', 'MS'),
                    "created_by": "productivity_system"
                }
            }

            # Create user
            response = requests.post(
                f"{Auth0Manager._base_url()}/users",
                headers=Auth0Manager._get_headers(),
                json=payload,
                timeout=15
            )

            if response.status_code == 201:
                user_data = response.json()
                user_id = user_data['user_id']

                # Assign role if provided
                role_id = employee_data.get('role_id')
                if role_id:
                    Auth0Manager._assign_role(user_id, role_id)

                return {
                    'success': True,
                    'user_id': user_id,
                    'password': password,
                    'message': 'Auth0 account created'
                }
            elif response.status_code == 409:
                return {'success': False, 'message': 'User already exists in Auth0'}
            else:
                return {'success': False, 'message': f"Auth0 error: {response.status_code} - {response.text}"}

        except Exception as e:
            return {'success': False, 'message': f"Auth0 creation failed: {str(e)}"}

    @staticmethod
    def _assign_role(user_id, role_id):
        """Assign role to user"""
        try:
            requests.post(
                f"{Auth0Manager._base_url()}/users/{user_id}/roles",
                headers=Auth0Manager._get_headers(),
                json={"roles": [role_id]},
                timeout=10
            )
        except Exception as e:
            print(f"[Auth0] Failed to assign role: {e}")

    @staticmethod
    def delete_user(auth0_user_id):
        """
        Delete Auth0 user account

        Args:
            auth0_user_id: Auth0 user ID (e.g., 'auth0|xxx')

        Returns:
            {'success': bool, 'message': str}
        """
        if not Auth0Manager.is_configured():
            return {'success': False, 'message': 'Auth0 not configured'}

        if not auth0_user_id:
            return {'success': False, 'message': 'No Auth0 user ID provided'}

        try:
            response = requests.delete(
                f"{Auth0Manager._base_url()}/users/{auth0_user_id}",
                headers=Auth0Manager._get_headers(),
                timeout=10
            )

            if response.status_code == 204:
                return {'success': True, 'message': 'Auth0 account deleted'}
            elif response.status_code == 404:
                return {'success': True, 'message': 'Auth0 account not found (already deleted)'}
            else:
                return {'success': False, 'message': f"Auth0 delete error: {response.status_code}"}

        except Exception as e:
            return {'success': False, 'message': f"Auth0 deletion failed: {str(e)}"}

    @staticmethod
    def reset_password(auth0_user_id, custom_password=None):
        """
        Reset Auth0 user password

        Args:
            auth0_user_id: Auth0 user ID (e.g., 'auth0|xxx')
            custom_password: Optional custom password (generates random if not provided)

        Returns:
            {'success': bool, 'password': str, 'message': str}
        """
        if not Auth0Manager.is_configured():
            return {'success': False, 'message': 'Auth0 not configured'}

        if not auth0_user_id:
            return {'success': False, 'message': 'No Auth0 user ID provided'}

        try:
            # Use custom password or generate random
            new_password = custom_password or Auth0Manager.generate_password()

            # Update password via Management API
            response = requests.patch(
                f"{Auth0Manager._base_url()}/users/{auth0_user_id}",
                headers=Auth0Manager._get_headers(),
                json={"password": new_password},
                timeout=15
            )

            if response.status_code == 200:
                return {
                    'success': True,
                    'password': new_password,
                    'message': 'Password reset successfully'
                }
            elif response.status_code == 404:
                return {'success': False, 'message': 'Auth0 user not found'}
            else:
                return {'success': False, 'message': f"Auth0 password reset error: {response.status_code} - {response.text}"}

        except Exception as e:
            return {'success': False, 'message': f"Auth0 password reset failed: {str(e)}"}

    @staticmethod
    def get_workspaces():
        """Get available workspaces"""
        return [
            {'code': code, 'name': name}
            for code, name in Auth0Manager.WORKSPACES.items()
        ]
