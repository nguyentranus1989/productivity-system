"""Trends and analytics API endpoints"""
from flask import Blueprint, request, jsonify
from datetime import datetime, date, timedelta
import logging

from calculations.trend_analyzer import TrendAnalyzer
from api.auth import require_api_key, rate_limit
from database.cache_manager import get_cache_manager
from utils.timezone_helpers import TimezoneHelper

cache = get_cache_manager()
tz_helper = TimezoneHelper()

logger = logging.getLogger(__name__)

# Create blueprint
trends_bp = Blueprint('trends', __name__)

@trends_bp.route('/employee/<int:employee_id>', methods=['GET'])
@require_api_key
@rate_limit(requests_per_minute=60)
def get_employee_trend(employee_id):
    """Get productivity trend for an employee"""
    try:
        # Get days parameter (default 30)
        days = request.args.get('days', 30, type=int)
        days = min(days, 90)  # Cap at 90 days
        
        # Try cache first
        cache_key = f"trend:employee:{employee_id}:days:{days}"
        cached_data = cache.redis_client.get(cache_key)
        
        if cached_data:
            import json
            return jsonify({
                'source': 'cache',
                'data': json.loads(cached_data)
            })
        
        # Calculate trend
        analyzer = TrendAnalyzer()
        trend_data = analyzer.get_employee_trend(employee_id, days)
        
        if not trend_data.get('has_data'):
            return jsonify({
                'error': 'No data found for employee',
                'employee_id': employee_id
            }), 404
        
        # Cache for 1 hour
        cache.redis_client.setex(
            cache_key,
            3600,
            jsonify(trend_data).get_data(as_text=True)
        )
        
        return jsonify({
            'source': 'calculated',
            'data': trend_data
        })
        
    except Exception as e:
        logger.error(f"Error getting employee trend: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@trends_bp.route('/team', methods=['GET'])
@require_api_key
@rate_limit(requests_per_minute=60)
def get_team_trend():
    """Get productivity trend for a team or role"""
    try:
        # Get parameters
        role_id = request.args.get('role_id', type=int)
        days = request.args.get('days', 30, type=int)
        days = min(days, 90)  # Cap at 90 days
        
        # Calculate trend
        analyzer = TrendAnalyzer()
        trend_data = analyzer.get_team_trend(role_id, days)
        
        if not trend_data.get('has_data'):
            return jsonify({
                'error': 'No data found',
                'role_id': role_id
            }), 404
        
        return jsonify(trend_data)
        
    except Exception as e:
        logger.error(f"Error getting team trend: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@trends_bp.route('/employee/<int:employee_id>/prediction', methods=['GET'])
@require_api_key
@rate_limit(requests_per_minute=100)
def predict_monthly_performance(employee_id):
    """Predict if employee will meet monthly target"""
    try:
        # Try cache first
        cache_key = f"prediction:employee:{employee_id}:month:{date.today().strftime('%Y-%m')}"
        cached_data = cache.redis_client.get(cache_key)
        
        if cached_data:
            import json
            return jsonify({
                'source': 'cache',
                'data': json.loads(cached_data)
            })
        
        # Calculate prediction
        analyzer = TrendAnalyzer()
        prediction = analyzer.predict_monthly_performance(employee_id)
        
        if 'error' in prediction:
            return jsonify(prediction), 404
        
        # Cache for 2 hours
        cache.redis_client.setex(
            cache_key,
            7200,
            jsonify(prediction).get_data(as_text=True)
        )
        
        return jsonify({
            'source': 'calculated',
            'data': prediction
        })
        
    except Exception as e:
        logger.error(f"Error predicting performance: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@trends_bp.route('/employee/<int:employee_id>/patterns', methods=['GET'])
@require_api_key
@rate_limit(requests_per_minute=60)
def get_performance_patterns(employee_id):
    """Identify patterns in employee performance"""
    try:
        analyzer = TrendAnalyzer()
        patterns = analyzer.identify_performance_patterns(employee_id)
        
        return jsonify(patterns)
        
    except Exception as e:
        logger.error(f"Error identifying patterns: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@trends_bp.route('/insights', methods=['GET'])
@require_api_key
@rate_limit(requests_per_minute=30)
def get_insights():
    """Get overall productivity insights"""
    try:
        analyzer = TrendAnalyzer()
        db = analyzer.db
        
        # Get various insights
        insights = {
            'generated_at': datetime.now().isoformat(),
            'insights': []
        }
        
        # 1. Overall trend
        overall_trend = analyzer.get_team_trend(days=30)
        if overall_trend.get('has_data'):
            if overall_trend['trend_direction'] == 'improving':
                insights['insights'].append({
                    'type': 'positive',
                    'category': 'overall',
                    'message': f"Overall productivity is improving! Average daily points up to {overall_trend['average_daily_points']}"
                })
            elif overall_trend['trend_direction'] == 'declining':
                insights['insights'].append({
                    'type': 'concern',
                    'category': 'overall',
                    'message': f"Overall productivity is declining. Average daily points down to {overall_trend['average_daily_points']}"
                })
        
        # 2. At-risk employees
        ct_date = tz_helper.get_current_ct_date()
        month_year = ct_date.strftime('%Y-%m')
        day_of_month = ct_date.day

        at_risk = db.execute_query(
            """
            SELECT
                e.id,
                e.name,
                rc.role_name,
                ms.total_points,
                ms.target_points,
                (ms.total_points / ms.target_points * 100) as progress_percent
            FROM monthly_summaries ms
            JOIN employees e ON ms.employee_id = e.id
            JOIN role_configs rc ON e.role_id = rc.id
            WHERE ms.month_year = %s
            AND ms.total_points < ms.target_points * 0.7
            AND %s > 20
            ORDER BY progress_percent
            LIMIT 5
            """,
            (month_year, day_of_month)
        )
        
        if at_risk:
            insights['insights'].append({
                'type': 'alert',
                'category': 'at_risk',
                'message': f"{len(at_risk)} employees at risk of missing monthly targets",
                'details': [
                    {
                        'name': emp['name'],
                        'role': emp['role_name'],
                        'progress': f"{emp['progress_percent']:.1f}%"
                    }
                    for emp in at_risk
                ]
            })
        
        # 3. Top improvers
        date_7d_ago = ct_date - timedelta(days=7)
        date_14d_ago = ct_date - timedelta(days=14)

        improvers = db.execute_query(
            """
            SELECT
                e.id,
                e.name,
                rc.role_name,
                AVG(CASE WHEN ds.score_date >= %s
                    THEN ds.points_earned END) as recent_avg,
                AVG(CASE WHEN ds.score_date < %s
                    AND ds.score_date >= %s
                    THEN ds.points_earned END) as previous_avg
            FROM daily_scores ds
            JOIN employees e ON ds.employee_id = e.id
            JOIN role_configs rc ON e.role_id = rc.id
            WHERE ds.score_date >= %s
            GROUP BY e.id, e.name, rc.role_name
            HAVING recent_avg > previous_avg * 1.1
            ORDER BY (recent_avg - previous_avg) DESC
            LIMIT 5
            """,
            (date_7d_ago, date_7d_ago, date_14d_ago, date_14d_ago)
        )
        
        if improvers:
            insights['insights'].append({
                'type': 'positive',
                'category': 'improvement',
                'message': f"{len(improvers)} employees showing significant improvement",
                'details': [
                    {
                        'name': emp['name'],
                        'role': emp['role_name'],
                        'improvement': f"+{((emp['recent_avg'] / emp['previous_avg'] - 1) * 100):.1f}%"
                    }
                    for emp in improvers
                ]
            })
        
        # 4. Consistency champions
        date_30d_ago = ct_date - timedelta(days=30)

        consistent = db.execute_query(
            """
            SELECT
                e.id,
                e.name,
                rc.role_name,
                AVG(ds.points_earned) as avg_points,
                STDDEV(ds.points_earned) as std_dev,
                COUNT(*) as days_worked
            FROM daily_scores ds
            JOIN employees e ON ds.employee_id = e.id
            JOIN role_configs rc ON e.role_id = rc.id
            WHERE ds.score_date >= %s
            GROUP BY e.id, e.name, rc.role_name
            HAVING days_worked >= 20
            AND std_dev / avg_points < 0.15
            ORDER BY avg_points DESC
            LIMIT 3
            """,
            (date_30d_ago,)
        )
        
        if consistent:
            insights['insights'].append({
                'type': 'positive',
                'category': 'consistency',
                'message': "Most consistent performers",
                'details': [
                    {
                        'name': emp['name'],
                        'role': emp['role_name'],
                        'avg_points': round(emp['avg_points'], 2)
                    }
                    for emp in consistent
                ]
            })
        
        return jsonify(insights)
        
    except Exception as e:
        logger.error(f"Error generating insights: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@trends_bp.route('/comparison', methods=['POST'])
@require_api_key
@rate_limit(requests_per_minute=30)
def compare_employees():
    """Compare performance between multiple employees"""
    try:
        data = request.get_json()
        if not data or 'employee_ids' not in data:
            return jsonify({'error': 'employee_ids required'}), 400
        
        employee_ids = data['employee_ids']
        if not isinstance(employee_ids, list) or len(employee_ids) < 2:
            return jsonify({'error': 'At least 2 employee IDs required'}), 400
        
        if len(employee_ids) > 10:
            return jsonify({'error': 'Maximum 10 employees for comparison'}), 400
        
        days = data.get('days', 30)
        analyzer = TrendAnalyzer()
        
        comparisons = []
        for emp_id in employee_ids:
            trend = analyzer.get_employee_trend(emp_id, days)
            if trend.get('has_data'):
                comparisons.append({
                    'employee_id': emp_id,
                    'average_points': trend['average_daily_points'],
                    'trend_direction': trend['trend_direction'],
                    'consistency_score': trend['consistency_score'],
                    'efficiency': trend['average_efficiency']
                })
        
        if not comparisons:
            return jsonify({'error': 'No data found for specified employees'}), 404
        
        # Sort by average points
        comparisons.sort(key=lambda x: x['average_points'], reverse=True)
        
        # Add rankings
        for i, comp in enumerate(comparisons):
            comp['rank'] = i + 1
        
        return jsonify({
            'period_days': days,
            'employee_count': len(comparisons),
            'comparisons': comparisons
        })
        
    except Exception as e:
        logger.error(f"Error comparing employees: {e}")
        return jsonify({'error': 'Internal server error'}), 500
