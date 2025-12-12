"""
API endpoints for enhanced idle detection
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
# LAZY IMPORT: EnhancedIdleDetector moved inside get_detector() for fast startup
from api.auth import require_api_key
from database.db_manager import DatabaseManager
from functools import wraps
import json

idle_bp = Blueprint('idle', __name__)

# Lazy-loaded detector
_detector = None

def get_detector():
    """Get detector instance (lazy initialization)"""
    global _detector
    if _detector is None:
        # Import here to avoid slow startup (sklearn imports take ~3s)
        from calculations.enhanced_idle_detector import EnhancedIdleDetector
        _detector = EnhancedIdleDetector()
    return _detector

# Simple cache wrapper since cache_wrapper doesn't exist
def cache_response(expiration=300):
    """Simple response caching decorator"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # For now, just pass through - caching can be added later
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@idle_bp.route('/threshold/<int:employee_id>', methods=['GET'])
@require_api_key
def get_idle_threshold(employee_id):
    """Get contextual idle threshold for an employee"""
    try:
        db_manager = DatabaseManager()
        with db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT role FROM employees WHERE id = %s
            """, (employee_id,))
            
            result = cursor.fetchone()
            if not result:
                return jsonify({'error': 'Employee not found'}), 404
            
            role = result['role']
        
        threshold = get_detector().get_contextual_threshold(
            employee_id, 
            role, 
            datetime.now()
        )
        
        return jsonify({
            'employee_id': employee_id,
            'role': role,
            'base_threshold': get_detector().role_thresholds.get(role, 20),
            'contextual_threshold': threshold,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@idle_bp.route('/probability/<int:employee_id>', methods=['GET'])
@require_api_key
def get_idle_probability(employee_id):
    """Get ML-predicted idle probability"""
    try:
        probability = get_detector().predict_idle_probability(
            employee_id,
            datetime.now()
        )
        
        features = get_detector().get_employee_features(
            employee_id,
            datetime.now()
        )[0]
        
        return jsonify({
            'employee_id': employee_id,
            'idle_probability': round(probability, 3),
            'risk_level': 'high' if probability > 0.7 else 'medium' if probability > 0.4 else 'low',
            'features': {
                'minutes_since_activity': float(features[0]),
                'recent_activity_count': float(features[1]),
                'time_of_day': float(features[2]),
                'recent_points': float(features[4]),
                'efficiency': float(features[6])
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@idle_bp.route('/patterns/<int:employee_id>', methods=['GET'])
@require_api_key
@cache_response(expiration=300)
def get_idle_patterns(employee_id):
    """Get idle patterns analysis for an employee"""
    try:
        patterns = get_detector().detect_idle_patterns(employee_id)
        
        return jsonify({
            'employee_id': employee_id,
            'patterns': patterns,
            'analysis_period': '30 days',
            'generated_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@idle_bp.route('/train-model', methods=['POST'])
@require_api_key
def train_idle_model():
    """Retrain the idle detection model"""
    try:
        data = request.get_json()
        days_back = data.get('days_back', 30) if data else 30
        
        get_detector().train_model(days_back)
        
        return jsonify({
            'status': 'success',
            'message': f'Model trained on last {days_back} days of data',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
