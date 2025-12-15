# Auth0 Integration - Code Reference Guide
**Date**: 2025-12-14
**Purpose**: Practical code patterns and integration examples for Auth0 Management API

---

## Quick Reference: API Endpoints

### Token Endpoint
```
POST https://{AUTH0_DOMAIN}/oauth/token
Content-Type: application/json

{
  "client_id": "{CLIENT_ID}",
  "client_secret": "{CLIENT_SECRET}",
  "audience": "https://{AUTH0_DOMAIN}/api/v2/",
  "grant_type": "client_credentials"
}

Response:
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

### Create User Endpoint
```
POST https://{AUTH0_DOMAIN}/api/v2/users
Authorization: Bearer {ACCESS_TOKEN}
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "Secure123!",
  "username": "username",
  "user_metadata": {...},
  "app_metadata": {...},
  "connection": "Username-Password-Authentication",
  "verify_email": true
}

Response: 201 Created
{
  "user_id": "auth0|5f7a1c2b3d4e5f6g7h8i",
  "email": "user@example.com",
  "created_at": "2025-12-14T14:30:00.000Z"
}
```

### Assign Role Endpoint
```
POST https://{AUTH0_DOMAIN}/api/v2/users/{USER_ID}/roles
Authorization: Bearer {ACCESS_TOKEN}
Content-Type: application/json

{
  "roles": ["rol_abc123xyz"]
}

Response: 204 No Content
```

---

## Complete Python Implementation

### Module 1: Token Manager

```python
# backend/integrations/auth0_token_manager.py

import requests
import time
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class Auth0TokenManager:
    """Manage Auth0 access tokens with automatic refresh"""

    def __init__(self, domain: str, client_id: str, client_secret: str):
        """
        Initialize token manager

        Args:
            domain: Auth0 domain (e.g., 'tenant.auth0.com')
            client_id: Machine-to-machine app client ID
            client_secret: Machine-to-machine app client secret
        """
        self.domain = domain
        self.client_id = client_id
        self.client_secret = client_secret
        self.token: Optional[str] = None
        self.token_expires_at: float = 0
        self.token_type: str = "Bearer"

    def get_access_token(self) -> str:
        """
        Get valid access token, refreshing if necessary

        Returns:
            Valid JWT access token

        Raises:
            Exception: If token request fails
        """
        current_time = time.time()

        # If token still valid (with 5 minute buffer), return it
        if self.token and current_time < self.token_expires_at:
            logger.debug("Using cached Auth0 token")
            return self.token

        logger.info("Refreshing Auth0 access token")
        self._refresh_token()

        return self.token

    def _refresh_token(self):
        """Refresh access token from Auth0"""
        try:
            response = requests.post(
                f"https://{self.domain}/oauth/token",
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "audience": f"https://{self.domain}/api/v2/",
                    "grant_type": "client_credentials"
                },
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            if response.status_code != 200:
                error_data = response.json()
                raise Exception(
                    f"Token request failed ({response.status_code}): "
                    f"{error_data.get('error_description', 'Unknown error')}"
                )

            data = response.json()
            self.token = data['access_token']
            self.token_type = data.get('token_type', 'Bearer')

            # Set expiry with 5 minute buffer for safety
            expires_in = data['expires_in']
            self.token_expires_at = time.time() + expires_in - 300

            logger.info(
                f"Auth0 token refreshed. Expires in {expires_in} seconds "
                f"({datetime.fromtimestamp(self.token_expires_at).isoformat()})"
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"Token request failed: {str(e)}")
            raise Exception(f"Failed to get Auth0 token: {str(e)}")

    def get_headers(self) -> dict:
        """Get headers with authorization token"""
        token = self.get_access_token()
        return {
            "Authorization": f"{self.token_type} {token}",
            "Content-Type": "application/json"
        }
```

### Module 2: Auth0 API Client

```python
# backend/integrations/auth0_api_client.py

import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime
from auth0_token_manager import Auth0TokenManager

logger = logging.getLogger(__name__)


class Auth0APIClient:
    """Auth0 Management API client"""

    # Max retries for transient failures
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds

    def __init__(self, domain: str, token_manager: Auth0TokenManager):
        """
        Initialize API client

        Args:
            domain: Auth0 domain
            token_manager: Auth0TokenManager instance
        """
        self.domain = domain
        self.token_manager = token_manager
        self.base_url = f"https://{domain}/api/v2"

    def create_user(
        self,
        email: str,
        username: str,
        user_metadata: Dict,
        app_metadata: Dict,
        verify_email: bool = True,
        password: Optional[str] = None
    ) -> Dict:
        """
        Create new user in Auth0

        Args:
            email: User email address
            username: User login username
            user_metadata: User-facing metadata dict
            app_metadata: Application-facing metadata dict
            verify_email: Send verification email (default: True)
            password: Initial password (None if verify_email=True)

        Returns:
            {
                'success': bool,
                'user_id': str,
                'email': str,
                'message': str,
                'created_at': str
            }
        """
        if not email or not username:
            return {
                'success': False,
                'message': 'email and username are required'
            }

        payload = {
            "email": email,
            "username": username,
            "user_metadata": user_metadata,
            "app_metadata": app_metadata,
            "connection": "Username-Password-Authentication",
            "verify_email": verify_email,
            "email_verified": not verify_email,
            "blocked": False
        }

        # Only include password if verify_email is False
        if password:
            payload['password'] = password

        try:
            response = self._make_request(
                "POST",
                f"{self.base_url}/users",
                json=payload
            )

            if response.status_code == 201:
                user_data = response.json()
                logger.info(f"User created: {user_data['user_id']}")
                return {
                    'success': True,
                    'user_id': user_data['user_id'],
                    'email': user_data['email'],
                    'created_at': user_data['created_at'],
                    'message': 'User created successfully'
                }

            elif response.status_code == 409:
                logger.warning(f"User already exists: {email}")
                return {
                    'success': False,
                    'message': f'User {email} already exists'
                }

            else:
                error_data = response.json()
                message = error_data.get('message', 'Unknown error')
                logger.error(f"User creation failed ({response.status_code}): {message}")
                return {
                    'success': False,
                    'message': message
                }

        except Exception as e:
            logger.error(f"Exception creating user: {str(e)}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }

    def get_user(self, user_id: str) -> Dict:
        """
        Get user details

        Args:
            user_id: Auth0 user ID

        Returns:
            User details dict or empty dict if not found
        """
        try:
            response = self._make_request("GET", f"{self.base_url}/users/{user_id}")

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.warning(f"User not found: {user_id}")
                return {}
            else:
                logger.error(f"Get user failed: {response.status_code}")
                return {}

        except Exception as e:
            logger.error(f"Exception getting user: {str(e)}")
            return {}

    def assign_role(self, user_id: str, role_id: str) -> bool:
        """
        Assign role to user

        Args:
            user_id: Auth0 user ID
            role_id: Auth0 role ID

        Returns:
            True if successful, False otherwise
        """
        try:
            response = self._make_request(
                "POST",
                f"{self.base_url}/users/{user_id}/roles",
                json={"roles": [role_id]}
            )

            if response.status_code == 204:
                logger.info(f"Role {role_id} assigned to user {user_id}")
                return True
            else:
                logger.error(f"Role assignment failed ({response.status_code})")
                return False

        except Exception as e:
            logger.error(f"Exception assigning role: {str(e)}")
            return False

    def get_roles(self, name_filter: Optional[str] = None) -> List[Dict]:
        """
        Get list of roles

        Args:
            name_filter: Optional role name filter

        Returns:
            List of role dicts
        """
        params = {}
        if name_filter:
            params['name_filter'] = name_filter

        try:
            response = self._make_request(
                "GET",
                f"{self.base_url}/roles",
                params=params
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Get roles failed ({response.status_code})")
                return []

        except Exception as e:
            logger.error(f"Exception getting roles: {str(e)}")
            return []

    def update_app_metadata(self, user_id: str, app_metadata: Dict) -> bool:
        """
        Update user app_metadata

        Args:
            user_id: Auth0 user ID
            app_metadata: Metadata dict to update

        Returns:
            True if successful, False otherwise
        """
        try:
            response = self._make_request(
                "PATCH",
                f"{self.base_url}/users/{user_id}",
                json={"app_metadata": app_metadata}
            )

            if response.status_code == 200:
                logger.info(f"Metadata updated for user {user_id}")
                return True
            else:
                logger.error(f"Metadata update failed ({response.status_code})")
                return False

        except Exception as e:
            logger.error(f"Exception updating metadata: {str(e)}")
            return False

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make HTTP request with retry logic

        Args:
            method: HTTP method (GET, POST, PATCH, etc.)
            url: Full URL
            **kwargs: Additional arguments for requests

        Returns:
            Response object
        """
        headers = self.token_manager.get_headers()
        kwargs['headers'] = headers

        for attempt in range(self.MAX_RETRIES):
            try:
                response = requests.request(method, url, timeout=10, **kwargs)

                # Retry on 429 (rate limit) or 5xx errors
                if response.status_code in [429, 500, 502, 503, 504]:
                    if attempt < self.MAX_RETRIES - 1:
                        wait_time = self.RETRY_DELAY * (2 ** attempt)
                        logger.warning(
                            f"Retry {attempt + 1}/{self.MAX_RETRIES} "
                            f"(status {response.status_code}, wait {wait_time}s)"
                        )
                        time.sleep(wait_time)
                        continue

                return response

            except requests.exceptions.Timeout:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"Timeout, retrying ({attempt + 1}/{self.MAX_RETRIES})")
                    time.sleep(self.RETRY_DELAY)
                else:
                    raise

        return response
```

### Module 3: High-Level Manager

```python
# backend/integrations/auth0_manager.py

import logging
from typing import Dict, Optional
from datetime import datetime
from auth0_api_client import Auth0APIClient
from auth0_token_manager import Auth0TokenManager

logger = logging.getLogger(__name__)


class Auth0Manager:
    """High-level manager for Auth0 integration"""

    def __init__(self, domain: str, client_id: str, client_secret: str):
        """
        Initialize manager

        Args:
            domain: Auth0 domain
            client_id: M2M app client ID
            client_secret: M2M app client secret
        """
        self.domain = domain
        self.token_manager = Auth0TokenManager(domain, client_id, client_secret)
        self.api_client = Auth0APIClient(domain, self.token_manager)

    def create_employee_account(self, employee_data: Dict) -> Dict:
        """
        Create Auth0 account for new employee

        Args:
            employee_data: {
                'employee_id': int,
                'name': str,
                'email': str,
                'department': str,
                'connecteam_id': str (optional),
                'phone_number': str (optional)
            }

        Returns:
            {
                'success': bool,
                'user_id': str (if success),
                'email': str (if success),
                'message': str,
                'auth0_email_verified': bool
            }
        """
        logger.info(f"Creating Auth0 account for employee {employee_data.get('employee_id')}")

        # Validate input
        required_fields = ['employee_id', 'name', 'email', 'department']
        for field in required_fields:
            if not employee_data.get(field):
                return {
                    'success': False,
                    'message': f'Missing required field: {field}'
                }

        # Prepare metadata
        user_metadata = {
            "employee_id": employee_data['employee_id'],
            "full_name": employee_data['name'],
            "department": employee_data['department'],
            "timezone": "America/Chicago",
            "created_at_timestamp": datetime.utcnow().isoformat() + "Z"
        }

        if employee_data.get('phone_number'):
            user_metadata['phone_number'] = employee_data['phone_number']

        app_metadata = {
            "employee_id": employee_data['employee_id'],
            "internal_id": employee_data['employee_id'],
            "department": employee_data['department'],
            "role_code": "associate",
            "created_by": "productivity_system",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "sync_status": "active"
        }

        if employee_data.get('connecteam_id'):
            app_metadata['connecteam_id'] = employee_data['connecteam_id']

        # Create user with email verification
        username = employee_data['email'].split('@')[0]

        result = self.api_client.create_user(
            email=employee_data['email'],
            username=username,
            user_metadata=user_metadata,
            app_metadata=app_metadata,
            verify_email=True  # Send verification email
        )

        if not result['success']:
            logger.error(f"User creation failed: {result['message']}")
            return result

        user_id = result['user_id']

        # Assign default role
        role_assigned = self._assign_default_role(user_id)

        result['auth0_email_verified'] = False
        result['role_assigned'] = role_assigned
        result['message'] = 'Account created. Verification email sent.'

        logger.info(
            f"Auth0 account created successfully",
            extra={
                'employee_id': employee_data['employee_id'],
                'auth0_user_id': user_id,
                'email': employee_data['email']
            }
        )

        return result

    def _assign_default_role(self, user_id: str) -> bool:
        """Assign production_associate role to new user"""
        try:
            roles = self.api_client.get_roles(name_filter='production_associate')

            if not roles:
                logger.warning(f"production_associate role not found")
                return False

            role_id = roles[0]['id']
            success = self.api_client.assign_role(user_id, role_id)

            if success:
                logger.info(f"Default role assigned to {user_id}")

            return success

        except Exception as e:
            logger.error(f"Error assigning role: {str(e)}")
            return False

    def get_user_info(self, user_id: str) -> Optional[Dict]:
        """Get user details from Auth0"""
        return self.api_client.get_user(user_id)

    def update_user_metadata(self, user_id: str, metadata: Dict) -> bool:
        """Update user app_metadata"""
        return self.api_client.update_app_metadata(user_id, metadata)
```

---

## Integration with Flask API

### Adding Endpoint to User Management

```python
# backend/api/user_management.py

from flask import Blueprint, request, jsonify
from auth.auth_decorator import require_api_key
from database.db_manager import get_db
from integrations.auth0_manager import Auth0Manager
from config import config
import logging

logger = logging.getLogger(__name__)

# Initialize Auth0 manager
auth0_manager = Auth0Manager(
    domain=config.AUTH0_DOMAIN,
    client_id=config.AUTH0_CLIENT_ID,
    client_secret=config.AUTH0_CLIENT_SECRET
)


@user_management_bp.route('/api/admin/employees/<int:employee_id>/create-auth0', methods=['POST'])
@require_api_key
def create_auth0_account(employee_id):
    """
    Create Auth0 account for existing employee

    Expected JSON body:
    {
        "force": false  # Force recreation if already exists
    }
    """
    try:
        # Get employee from database
        employee = get_db().execute_one(
            """
            SELECT id, name, email, department, phone_number, connecteam_id
            FROM employees
            WHERE id = %s
            """,
            (employee_id,)
        )

        if not employee:
            return jsonify({'success': False, 'message': 'Employee not found'}), 404

        # Check if already has Auth0 account
        if employee.get('auth0_user_id'):
            data = request.json or {}
            if not data.get('force'):
                return jsonify({
                    'success': False,
                    'message': 'Employee already has Auth0 account',
                    'auth0_user_id': employee['auth0_user_id']
                }), 400

        # Create Auth0 account
        result = auth0_manager.create_employee_account({
            'employee_id': employee['id'],
            'name': employee['name'],
            'email': employee['email'],
            'department': employee['department'],
            'phone_number': employee.get('phone_number'),
            'connecteam_id': employee.get('connecteam_id')
        })

        if result['success']:
            # Update employee record with Auth0 user ID
            get_db().execute_query(
                """
                UPDATE employees
                SET auth0_user_id = %s,
                    auth0_account_created_at = NOW(),
                    auth0_sync_status = 'created'
                WHERE id = %s
                """,
                (result['user_id'], employee_id)
            )

            # Log the action
            get_db().execute_query(
                """
                INSERT INTO auth0_sync_logs
                (employee_id, auth0_user_id, action, status, response_data, created_at)
                VALUES (%s, %s, 'create', 'success', %s, NOW())
                """,
                (employee_id, result['user_id'], json.dumps(result))
            )

        else:
            # Log failure
            get_db().execute_query(
                """
                INSERT INTO auth0_sync_logs
                (employee_id, action, status, response_data, created_at)
                VALUES (%s, 'create', 'failed', %s, NOW())
                """,
                (employee_id, json.dumps({'error': result.get('message')}))
            )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error creating Auth0 account: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500
```

---

## Configuration

### Environment Variables Required

```bash
# .env file
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_CLIENT_ID=your_client_id_here
AUTH0_CLIENT_SECRET=your_client_secret_here
```

### Config Class Addition

```python
# backend/config.py

class Config:
    # ... existing config ...

    # Auth0 Configuration
    AUTH0_DOMAIN = os.getenv('AUTH0_DOMAIN')
    AUTH0_CLIENT_ID = os.getenv('AUTH0_CLIENT_ID')
    AUTH0_CLIENT_SECRET = os.getenv('AUTH0_CLIENT_SECRET')

    # Validate Auth0 config if needed
    if not all([AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET]):
        if ENV == 'production':
            raise ValueError("Auth0 credentials required in production")
        # OK to skip in development
```

---

## Testing

### Unit Tests

```python
# tests/test_auth0_integration.py

import pytest
from unittest.mock import Mock, patch, MagicMock
from integrations.auth0_manager import Auth0Manager
from integrations.auth0_api_client import Auth0APIClient
from integrations.auth0_token_manager import Auth0TokenManager


class TestAuth0TokenManager:
    def test_get_access_token(self):
        """Test token acquisition and caching"""
        manager = Auth0TokenManager(
            "test.auth0.com",
            "client_id",
            "client_secret"
        )

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                'access_token': 'test_token',
                'token_type': 'Bearer',
                'expires_in': 86400
            }

            token1 = manager.get_access_token()
            token2 = manager.get_access_token()

            # Should use cache on second call
            assert token1 == token2
            assert mock_post.call_count == 1

    def test_token_refresh_on_expiry(self):
        """Test token refresh when expired"""
        manager = Auth0TokenManager(
            "test.auth0.com",
            "client_id",
            "client_secret"
        )

        # Force token expiry
        manager.token_expires_at = 0

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                'access_token': 'new_token',
                'token_type': 'Bearer',
                'expires_in': 86400
            }

            token = manager.get_access_token()
            assert token == 'new_token'


class TestAuth0APIClient:
    def test_create_user_success(self):
        """Test successful user creation"""
        token_manager = Mock()
        token_manager.get_headers.return_value = {'Authorization': 'Bearer token'}

        client = Auth0APIClient("test.auth0.com", token_manager)

        with patch('requests.request') as mock_request:
            mock_request.return_value.status_code = 201
            mock_request.return_value.json.return_value = {
                'user_id': 'auth0|123',
                'email': 'test@example.com',
                'created_at': '2025-12-14T14:30:00Z'
            }

            result = client.create_user(
                email='test@example.com',
                username='test',
                user_metadata={},
                app_metadata={}
            )

            assert result['success']
            assert result['user_id'] == 'auth0|123'

    def test_create_user_duplicate(self):
        """Test handling duplicate user"""
        token_manager = Mock()
        token_manager.get_headers.return_value = {'Authorization': 'Bearer token'}

        client = Auth0APIClient("test.auth0.com", token_manager)

        with patch('requests.request') as mock_request:
            mock_request.return_value.status_code = 409
            mock_request.return_value.json.return_value = {
                'message': 'The user already exists'
            }

            result = client.create_user(
                email='test@example.com',
                username='test',
                user_metadata={},
                app_metadata={}
            )

            assert not result['success']
            assert 'already exists' in result['message']


class TestAuth0Manager:
    def test_create_employee_account(self):
        """Test high-level employee account creation"""
        with patch('integrations.auth0_manager.Auth0APIClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock user creation response
            mock_client.create_user.return_value = {
                'success': True,
                'user_id': 'auth0|123',
                'email': 'john@example.com',
                'created_at': '2025-12-14T14:30:00Z',
                'message': 'User created successfully'
            }

            # Mock role retrieval and assignment
            mock_client.get_roles.return_value = [{'id': 'rol_123'}]
            mock_client.assign_role.return_value = True

            manager = Auth0Manager("test.auth0.com", "client_id", "client_secret")

            with patch.object(manager.api_client, 'create_user') as mock_create:
                with patch.object(manager, '_assign_default_role') as mock_assign:
                    mock_create.return_value = {
                        'success': True,
                        'user_id': 'auth0|123',
                        'email': 'john@example.com',
                        'created_at': '2025-12-14T14:30:00Z',
                        'message': 'User created successfully'
                    }
                    mock_assign.return_value = True

                    result = manager.create_employee_account({
                        'employee_id': 42,
                        'name': 'John Doe',
                        'email': 'john@example.com',
                        'department': 'Heat Press'
                    })

                    assert result['success']
                    assert result['user_id'] == 'auth0|123'
```

---

## Monitoring & Logging

### Structured Logging Example

```python
# In Auth0Manager.create_employee_account()

logger.info(
    "Auth0 account created",
    extra={
        'action': 'create_user',
        'employee_id': employee_data['employee_id'],
        'auth0_user_id': result['user_id'],
        'email': employee_data['email'],
        'department': employee_data['department'],
        'timestamp': datetime.utcnow().isoformat(),
        'duration_ms': elapsed_time * 1000
    }
)
```

### Metrics to Export

```python
# For Prometheus/monitoring integration

auth0_user_creation_total = Counter(
    'auth0_user_creation_total',
    'Total Auth0 user creation attempts',
    ['status']  # success, failure
)

auth0_user_creation_duration = Histogram(
    'auth0_user_creation_duration_seconds',
    'Auth0 user creation duration'
)

auth0_token_refresh_total = Counter(
    'auth0_token_refresh_total',
    'Auth0 token refresh attempts',
    ['status']
)
```

---

## Error Codes Reference

| Status | Error | Meaning |
|--------|-------|---------|
| 201 | - | User created successfully |
| 204 | - | Role assigned successfully |
| 400 | invalid_body | Malformed JSON payload |
| 400 | invalid_email | Invalid email format |
| 400 | invalid_query_string | Bad query parameters |
| 401 | Unauthorized | Invalid or missing token |
| 403 | Forbidden | No permission for action |
| 404 | Not Found | User/role not found |
| 409 | Conflict | User email already exists |
| 429 | Too Many Requests | Rate limited |
| 500 | Internal Server Error | Auth0 server error |
| 502 | Bad Gateway | Auth0 service unavailable |
| 503 | Service Unavailable | Auth0 maintenance |

---

## Deployment Checklist

- [ ] Auth0 M2M application created
- [ ] Management API scopes granted
- [ ] Credentials stored in environment variables
- [ ] Token manager tested locally
- [ ] API client tested with Auth0 sandbox
- [ ] Flask endpoint integrated
- [ ] Database schema updated with auth0_user_id column
- [ ] Error handling and retry logic tested
- [ ] Logging and monitoring configured
- [ ] Rate limiting verified
- [ ] Security review completed
- [ ] Documentation updated
- [ ] Operations team trained
- [ ] Deployment to production

---

