"""
Enhanced Idle Detection System with ML
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
import os
from database.db_manager import DatabaseManager
import logging

logger = logging.getLogger(__name__)

class EnhancedIdleDetector:
    """Advanced idle detection with ML and pattern recognition"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.model_path = "models/idle_detector_model.pkl"
        self.scaler_path = "models/idle_scaler.pkl"
        self.model = None
        self.scaler = None
        
        # Role-specific idle thresholds (in minutes)
        self.role_thresholds = {
            'Picker': 15,
            'Packer': 20,
            'Heat Pressing': 25,
            'Labeler': 20,
            'Film Matching': 30,
            'Packing and Shipping': 20
        }
        
        # Context-aware adjustments
        self.context_modifiers = {
            'shift_start': 1.5,
            'shift_end': 0.8,
            'after_break': 1.3,
            'high_productivity': 1.2,
            'low_productivity': 0.9
        }
        
        self._load_or_create_model()
    
    def _load_or_create_model(self):
        """Load existing model or create new one"""
        os.makedirs("models", exist_ok=True)
        
        if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
            self.model = joblib.load(self.model_path)
            self.scaler = joblib.load(self.scaler_path)
            logger.info("Loaded existing idle detection model")
        else:
            self.model = IsolationForest(
                contamination=0.1,
                random_state=42,
                n_estimators=100
            )
            self.scaler = StandardScaler()
            logger.info("Created new idle detection model")
    
    def get_employee_features(self, employee_id: int, check_time: datetime) -> np.ndarray:
        """Extract features for idle prediction"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            features = []
            
            # 1. Time since last activity
            cursor.execute("""
                SELECT TIMESTAMPDIFF(MINUTE, MAX(created_at), %s) as minutes_since_activity
                FROM activity_logs
                WHERE employee_id = %s
                AND created_at <= %s
            """, (check_time, employee_id, check_time))
            
            result = cursor.fetchone()
            minutes_since = result['minutes_since_activity'] or 0
            features.append(minutes_since)
            
            # 2. Average activity frequency (last hour)
            cursor.execute("""
                SELECT COUNT(*) as activity_count
                FROM activity_logs
                WHERE employee_id = %s
                AND created_at BETWEEN %s AND %s
            """, (
                employee_id,
                check_time - timedelta(hours=1),
                check_time
            ))
            
            result = cursor.fetchone()
            features.append(result['activity_count'])
            
            # 3. Time of day (normalized to 0-1)
            features.append(check_time.hour / 24.0)
            
            # 4. Day of week (0=Monday, 6=Sunday)
            features.append(check_time.weekday() / 7.0)
            
            # 5. Productivity in last hour
            cursor.execute("""
                SELECT COALESCE(SUM(points_earned), 0) as recent_points
                FROM activity_logs
                WHERE employee_id = %s
                AND created_at BETWEEN %s AND %s
            """, (
                employee_id,
                check_time - timedelta(hours=1),
                check_time
            ))
            
            result = cursor.fetchone()
            features.append(result['recent_points'])
            
            # 6. Historical idle frequency (last 7 days)
            cursor.execute("""
                SELECT COUNT(*) as idle_count
                FROM idle_periods
                WHERE employee_id = %s
                AND start_time >= %s
            """, (
                employee_id,
                check_time - timedelta(days=7)
            ))
            
            result = cursor.fetchone()
            features.append(result['idle_count'])
            
            # 7. Current efficiency
            cursor.execute("""
                SELECT efficiency_rate * 100 as efficiency_percent
                FROM daily_scores
                WHERE employee_id = %s
                AND score_date = %s
            """, (employee_id, check_time.date()))
            
            result = cursor.fetchone()
            features.append(result['efficiency_percent'] if result else 50.0)
            
            # 8. Break status
            cursor.execute("""
                SELECT COUNT(*) as recent_break
                FROM break_entries
                WHERE employee_id = %s
                AND end_time BETWEEN %s AND %s
            """, (
                employee_id,
                check_time - timedelta(minutes=30),
                check_time
            ))
            
            result = cursor.fetchone()
            features.append(1 if result['recent_break'] > 0 else 0)
            
        return np.array(features).reshape(1, -1)
    
    def get_contextual_threshold(self, employee_id: int, role: str, 
                                 check_time: datetime) -> int:
        """Get dynamic idle threshold based on context"""
        base_threshold = self.role_thresholds.get(role, 20)
        modifier = 1.0
        
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Check if near shift start/end
            shift_hour = check_time.hour
            if 7 <= shift_hour <= 8:
                modifier *= self.context_modifiers['shift_start']
            elif 15 <= shift_hour <= 16:
                modifier *= self.context_modifiers['shift_end']
            
            # Check if recently returned from break
            cursor.execute("""
                SELECT COUNT(*) as recent_break
                FROM break_entries
                WHERE employee_id = %s
                AND end_time BETWEEN %s AND %s
            """, (
                employee_id,
                check_time - timedelta(minutes=30),
                check_time
            ))
            
            if cursor.fetchone()['recent_break'] > 0:
                modifier *= self.context_modifiers['after_break']
            
            # Check recent productivity
            cursor.execute("""
                SELECT AVG(a.items_count) as avg_items
                FROM activity_logs a
                WHERE a.employee_id = %s
                AND a.created_at >= %s
            """, (
                employee_id,
                check_time - timedelta(hours=2)
            ))
            
            result = cursor.fetchone()
            if result and result['avg_items']:
                # Get expected performance
                cursor.execute("""
                    SELECT expected_per_hour / 6 as expected_per_window
                    FROM role_configs
                    WHERE role_name = %s
                """, (role,))
                
                expected = cursor.fetchone()
                if expected and result['avg_items'] > expected['expected_per_window'] * 1.2:
                    modifier *= self.context_modifiers['high_productivity']
                elif expected and result['avg_items'] < expected['expected_per_window'] * 0.8:
                    modifier *= self.context_modifiers['low_productivity']
        
        return int(base_threshold * modifier)
    
    def predict_idle_probability(self, employee_id: int, check_time: datetime) -> float:
        """Predict probability of employee being idle using ML"""
        features = self.get_employee_features(employee_id, check_time)
        
        if self.model is None:
            return 0.5
        
        try:
            # Scale features
            features_scaled = self.scaler.fit_transform(features)
            
            # Get anomaly score
            prediction = self.model.decision_function(features_scaled)[0]
            
            # Convert to probability (0-1 range)
            idle_probability = 1 / (1 + np.exp(prediction * 2))
            
            return idle_probability
        except:
            return 0.5
    
    def detect_idle_patterns(self, employee_id: int) -> Dict:
        """Analyze idle patterns for an employee"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            patterns = {
                'common_idle_times': [],
                'average_idle_duration': 0,
                'idle_frequency_by_day': {},
                'productivity_impact': 0,
                'recommendations': []
            }
            
            # Common idle times
            cursor.execute("""
                SELECT 
                    HOUR(start_time) as idle_hour,
                    COUNT(*) as occurrences,
                    AVG(duration_minutes) as avg_duration
                FROM idle_periods
                WHERE employee_id = %s
                AND start_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                GROUP BY HOUR(start_time)
                ORDER BY occurrences DESC
                LIMIT 3
            """, (employee_id,))
            
            for row in cursor.fetchall():
                patterns['common_idle_times'].append({
                    'hour': row['idle_hour'],
                    'occurrences': row['occurrences'],
                    'avg_duration': round(float(row['avg_duration']), 1)
                })
            
            # Average idle duration
            cursor.execute("""
                SELECT AVG(duration_minutes) as avg_duration
                FROM idle_periods
                WHERE employee_id = %s
                AND start_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            """, (employee_id,))
            
            result = cursor.fetchone()
            patterns['average_idle_duration'] = round(float(result['avg_duration'] or 0), 1)
            
            # Generate recommendations
            if patterns['common_idle_times']:
                most_common_hour = patterns['common_idle_times'][0]['hour']
                patterns['recommendations'].append(
                    f"Schedule breaks around {most_common_hour}:00 to align with natural patterns"
                )
            
            if patterns['average_idle_duration'] > 25:
                patterns['recommendations'].append(
                    "Consider shorter, more frequent breaks to reduce long idle periods"
                )
            
        return patterns
    
    def train_model(self, days_back: int = 30):
        """Train the ML model on historical data"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            print(f"Training idle detection model on last {days_back} days...")
            
            # Get all employees
            cursor.execute("SELECT id FROM employees WHERE is_active = TRUE")
            employees = [row['id'] for row in cursor.fetchall()]
            
            # Collect training data
            all_features = []
            
            for employee_id in employees:
                # Get idle periods
                cursor.execute("""
                    SELECT start_time, duration_minutes
                    FROM idle_periods
                    WHERE employee_id = %s
                    AND start_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
                """, (employee_id, days_back))
                
                idle_periods = cursor.fetchall()
                
                # For each idle period, get features
                for period in idle_periods[:10]:  # Limit to 10 per employee
                    features = self.get_employee_features(
                        employee_id, 
                        period['start_time']
                    )
                    all_features.append(features[0])
                
                # Also get some non-idle samples
                cursor.execute("""
                    SELECT DISTINCT created_at
                    FROM activity_logs
                    WHERE employee_id = %s
                    AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                    ORDER BY RAND()
                    LIMIT 10
                """, (employee_id, days_back))
                
                for row in cursor.fetchall():
                    features = self.get_employee_features(
                        employee_id,
                        row['created_at']
                    )
                    all_features.append(features[0])
            
            if all_features:
                # Convert to numpy array
                X = np.array(all_features)
                
                # Train scaler and model
                X_scaled = self.scaler.fit_transform(X)
                self.model.fit(X_scaled)
                
                # Save model
                joblib.dump(self.model, self.model_path)
                joblib.dump(self.scaler, self.scaler_path)
                
                print(f"Model trained on {len(all_features)} samples")
            else:
                print("Warning: No training data available")
