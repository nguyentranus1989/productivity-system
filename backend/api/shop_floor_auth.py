"""
Shop Floor Authentication API
Validates shop floor PIN against database instead of hardcoded value
"""

from flask import Blueprint, request, jsonify
import bcrypt
import secrets
from datetime import datetime
from database.db_manager import get_db
from api.auth import require_api_key

shop_floor_auth_bp = Blueprint('shop_floor_auth', __name__)

def hash_pin(pin):
    """Hash PIN using bcrypt"""
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt(10)).decode()

def verify_pin(pin, hashed):
    """Verify PIN against bcrypt hash"""
    try:
        if hashed and hashed.startswith('$2'):
            return bcrypt.checkpw(pin.encode(), hashed.encode())
        else:
            # Legacy plain text support
            return pin == hashed
    except Exception:
        return False

@shop_floor_auth_bp.route('/api/shopfloor/login', methods=['POST'])
def shop_floor_login():
    """Validate shop floor PIN"""
    try:
        data = request.json
        pin = data.get('pin')

        if not pin:
            return jsonify({'success': False, 'message': 'PIN required'}), 400

        # Get shop floor PIN from database
        result = get_db().execute_one("""
            SELECT pin_hash FROM shop_floor_settings WHERE id = 1
        """)

        if not result:
            # No PIN set - use default for backwards compatibility
            # This allows initial setup before admin sets a PIN
            if pin == '1234':
                return jsonify({
                    'success': True,
                    'token': f'shopfloor_{secrets.token_urlsafe(16)}',
                    'message': 'Using default PIN - please set a new PIN in admin panel'
                })
            return jsonify({'success': False, 'message': 'Invalid PIN'}), 401

        if not verify_pin(pin, result['pin_hash']):
            return jsonify({'success': False, 'message': 'Invalid PIN'}), 401

        return jsonify({
            'success': True,
            'token': f'shopfloor_{secrets.token_urlsafe(16)}'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@shop_floor_auth_bp.route('/api/admin/shop-floor/set-pin', methods=['POST'])
@require_api_key
def set_shop_floor_pin():
    """Set or update shop floor PIN (admin only)"""
    try:
        data = request.json
        new_pin = data.get('pin')

        if not new_pin:
            return jsonify({'success': False, 'message': 'PIN required'}), 400

        # Validate PIN format (4-6 digits)
        if not new_pin.isdigit() or len(new_pin) < 4 or len(new_pin) > 6:
            return jsonify({'success': False, 'message': 'PIN must be 4-6 digits'}), 400

        pin_hash = hash_pin(new_pin)

        # Check if record exists
        existing = get_db().execute_one("""
            SELECT id FROM shop_floor_settings WHERE id = 1
        """)

        if existing:
            get_db().execute_query("""
                UPDATE shop_floor_settings
                SET pin_hash = %s, updated_at = NOW()
                WHERE id = 1
            """, (pin_hash,))
        else:
            get_db().execute_query("""
                INSERT INTO shop_floor_settings (id, pin_hash, updated_at)
                VALUES (1, %s, NOW())
            """, (pin_hash,))

        return jsonify({
            'success': True,
            'message': 'Shop floor PIN updated successfully'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@shop_floor_auth_bp.route('/api/admin/shop-floor/status', methods=['GET'])
@require_api_key
def get_shop_floor_status():
    """Check if shop floor PIN has been set"""
    try:
        result = get_db().execute_one("""
            SELECT
                CASE WHEN pin_hash IS NOT NULL THEN 1 ELSE 0 END as has_pin,
                updated_at
            FROM shop_floor_settings
            WHERE id = 1
        """)

        if not result:
            return jsonify({
                'success': True,
                'has_custom_pin': False,
                'message': 'Using default PIN (1234)'
            })

        return jsonify({
            'success': True,
            'has_custom_pin': bool(result['has_pin']),
            'last_updated': result['updated_at'].isoformat() if result['updated_at'] else None
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
