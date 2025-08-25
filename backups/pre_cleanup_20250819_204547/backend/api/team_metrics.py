"""
API endpoints for advanced team metrics
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
from calculations.team_metrics_engine import TeamMetricsEngine
from api.auth import require_api_key
import logging

logger = logging.getLogger(__name__)

team_metrics_bp = Blueprint('team_metrics', __name__)
engine = TeamMetricsEngine()

@team_metrics_bp.route('/api/team-metrics/overview', methods=['GET'])
@require_api_key
def get_team_overview():
    """Get comprehensive team overview metrics"""
    try:
        role_id = request.args.get('role_id', type=int)
        overview = engine.get_team_overview(role_id)
        
        return jsonify({
            'generated_at': datetime.now().isoformat(),
            'role_filter': role_id,
            'data': overview
        })
    except Exception as e:
        logger.error(f"Error getting team overview: {e}")
        return jsonify({'error': str(e)}), 500

@team_metrics_bp.route('/api/team-metrics/comparison', methods=['GET'])
@require_api_key
def get_team_comparison():
    """Compare performance across different teams/roles"""
    try:
        comparison = engine.get_team_comparison()
        
        return jsonify({
            'generated_at': datetime.now().isoformat(),
            'data': comparison
        })
    except Exception as e:
        logger.error(f"Error getting team comparison: {e}")
        return jsonify({'error': str(e)}), 500

@team_metrics_bp.route('/api/team-metrics/trends', methods=['GET'])
@require_api_key
def get_team_trends():
    """Get team performance trends over time"""
    try:
        role_id = request.args.get('role_id', type=int)
        days = request.args.get('days', 30, type=int)
        days = min(days, 90)  # Cap at 90 days
        
        trends = engine.get_team_trends(role_id, days)
        
        return jsonify({
            'generated_at': datetime.now().isoformat(),
            'role_filter': role_id,
            'data': trends
        })
    except Exception as e:
        logger.error(f"Error getting team trends: {e}")
        return jsonify({'error': str(e)}), 500

@team_metrics_bp.route('/api/team-metrics/shift-analysis', methods=['GET'])
@require_api_key
def get_shift_analysis():
    """Analyze performance by shift times"""
    try:
        analysis = engine.get_shift_analysis()
        
        return jsonify({
            'generated_at': datetime.now().isoformat(),
            'data': analysis
        })
    except Exception as e:
        logger.error(f"Error getting shift analysis: {e}")
        return jsonify({'error': str(e)}), 500

@team_metrics_bp.route('/api/team-metrics/bottlenecks', methods=['GET'])
@require_api_key
def get_bottlenecks():
    """Identify performance bottlenecks"""
    try:
        bottlenecks = engine.get_bottlenecks()
        
        # Sort by severity
        severity_order = {'high': 0, 'medium': 1, 'low': 2}
        sorted_bottlenecks = sorted(bottlenecks, 
                                   key=lambda x: severity_order.get(x['severity'], 3))
        
        return jsonify({
            'generated_at': datetime.now().isoformat(),
            'total_bottlenecks': len(bottlenecks),
            'high_severity': len([b for b in bottlenecks if b['severity'] == 'high']),
            'bottlenecks': sorted_bottlenecks
        })
    except Exception as e:
        logger.error(f"Error getting bottlenecks: {e}")
        return jsonify({'error': str(e)}), 500

@team_metrics_bp.route('/api/team-metrics/capacity', methods=['GET'])
@require_api_key
def get_capacity_analysis():
    """Analyze team capacity and utilization"""
    try:
        capacity = engine.get_capacity_analysis()
        
        return jsonify({
            'generated_at': datetime.now().isoformat(),
            'data': capacity
        })
    except Exception as e:
        logger.error(f"Error getting capacity analysis: {e}")
        return jsonify({'error': str(e)}), 500

@team_metrics_bp.route('/api/team-metrics/health-score', methods=['GET'])
@require_api_key
def get_team_health_score():
    """Calculate overall team health score"""
    try:
        # Combine various metrics to calculate health score
        overview = engine.get_team_overview()
        bottlenecks = engine.get_bottlenecks()
        capacity = engine.get_capacity_analysis()
        
        # Calculate health score (0-100)
        health_score = 100
        
        # Deduct for attendance issues
        attendance_rate = overview['team_composition']['attendance_rate']
        if attendance_rate < 90:
            health_score -= (90 - attendance_rate) * 0.5
        
        # Deduct for efficiency issues
        avg_efficiency = overview['performance_week']['avg_efficiency']
        if avg_efficiency < 70:
            health_score -= (70 - avg_efficiency) * 0.3
        
        # Deduct for bottlenecks
        high_severity_bottlenecks = len([b for b in bottlenecks if b['severity'] == 'high'])
        health_score -= high_severity_bottlenecks * 5
        
        # Deduct for low utilization
        utilization = capacity['overall_utilization']
        if utilization < 70:
            health_score -= (70 - utilization) * 0.2
        
        health_score = max(0, min(100, health_score))
        
        # Determine status
        if health_score >= 85:
            status = 'excellent'
            color = 'green'
        elif health_score >= 70:
            status = 'good'
            color = 'yellow'
        elif health_score >= 50:
            status = 'needs_attention'
            color = 'orange'
        else:
            status = 'critical'
            color = 'red'
        
        # Generate recommendations
        recommendations = []
        
        if attendance_rate < 90:
            recommendations.append({
                'category': 'attendance',
                'priority': 'high',
                'action': f'Address attendance issues - current rate is {attendance_rate}%'
            })
        
        if avg_efficiency < 70:
            recommendations.append({
                'category': 'efficiency',
                'priority': 'high',
                'action': f'Improve team efficiency - current average is {avg_efficiency}%'
            })
        
        if high_severity_bottlenecks > 0:
            recommendations.append({
                'category': 'bottlenecks',
                'priority': 'high',
                'action': f'Resolve {high_severity_bottlenecks} high-severity bottlenecks'
            })
        
        if utilization < 70:
            recommendations.append({
                'category': 'capacity',
                'priority': 'medium',
                'action': f'Increase capacity utilization from {utilization}% to 80%+'
            })
        
        return jsonify({
            'generated_at': datetime.now().isoformat(),
            'health_score': round(health_score, 1),
            'status': status,
            'color': color,
            'factors': {
                'attendance_rate': attendance_rate,
                'avg_efficiency': avg_efficiency,
                'bottleneck_count': len(bottlenecks),
                'utilization': utilization
            },
            'recommendations': recommendations
        })
        
    except Exception as e:
        logger.error(f"Error calculating health score: {e}")
        return jsonify({'error': str(e)}), 500
