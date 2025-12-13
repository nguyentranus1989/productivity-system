"""
Gamification System for Productivity Tracking
Includes achievements, badges, streaks, and challenges
"""

from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from database.db_manager import DatabaseManager
from utils.timezone_helpers import TimezoneHelper
from enum import Enum

logger = logging.getLogger(__name__)

class AchievementType(Enum):
    """Types of achievements"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    MILESTONE = "milestone"
    STREAK = "streak"
    SPECIAL = "special"

class BadgeLevel(Enum):
    """Badge levels"""
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"

class GamificationEngine:
    """Handle gamification features: achievements, badges, streaks, challenges"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.tz_helper = TimezoneHelper()
        self._initialize_achievements()
    
    def _initialize_achievements(self):
        """Define all possible achievements"""
        self.achievements = {
            # Daily achievements
            "daily_target_met": {
                "name": "Daily Champion",
                "description": "Meet your daily points target",
                "type": AchievementType.DAILY,
                "points": 10,
                "icon": "🎯"
            },
            "perfect_efficiency": {
                "name": "Efficiency Master",
                "description": "Achieve 90%+ efficiency for a day",
                "type": AchievementType.DAILY,
                "points": 15,
                "icon": "⚡"
            },
            "early_bird": {
                "name": "Early Bird",
                "description": "Start work before 7:30 AM",
                "type": AchievementType.DAILY,
                "points": 5,
                "icon": "🌅"
            },
            
            # Weekly achievements
            "weekly_consistency": {
                "name": "Consistency King",
                "description": "Meet daily target 5 days in a week",
                "type": AchievementType.WEEKLY,
                "points": 50,
                "icon": "👑"
            },
            "improvement_week": {
                "name": "Rising Star",
                "description": "Improve performance by 10% from last week",
                "type": AchievementType.WEEKLY,
                "points": 30,
                "icon": "🌟"
            },
            
            # Streak achievements
            "streak_3": {
                "name": "On Fire",
                "description": "3-day streak of meeting targets",
                "type": AchievementType.STREAK,
                "points": 20,
                "icon": "🔥"
            },
            "streak_7": {
                "name": "Week Warrior",
                "description": "7-day streak of meeting targets",
                "type": AchievementType.STREAK,
                "points": 75,
                "icon": "⚔️"
            },
            "streak_30": {
                "name": "Legendary",
                "description": "30-day streak of meeting targets",
                "type": AchievementType.STREAK,
                "points": 500,
                "icon": "🏆"
            },
            
            # Milestone achievements
            "first_1000_points": {
                "name": "Thousand Club",
                "description": "Earn 1,000 total points",
                "type": AchievementType.MILESTONE,
                "points": 25,
                "icon": "💎"
            },
            "first_10000_points": {
                "name": "Elite Performer",
                "description": "Earn 10,000 total points",
                "type": AchievementType.MILESTONE,
                "points": 100,
                "icon": "💫"
            },
            
            # Special achievements
            "team_player": {
                "name": "Team Player",
                "description": "Help team achieve weekly goal",
                "type": AchievementType.SPECIAL,
                "points": 40,
                "icon": "🤝"
            },
            "zero_idle": {
                "name": "Always Active",
                "description": "Complete a day with zero idle periods",
                "type": AchievementType.SPECIAL,
                "points": 25,
                "icon": "🚀"
            }
        }
    
    def check_daily_achievements(self, employee_id: int, check_date: date = None) -> List[Dict]:
        """Check and award daily achievements"""
        if not check_date:
            check_date = self.tz_helper.get_current_ct_date()

        # Get UTC boundaries for the CT date
        utc_start, utc_end = self.tz_helper.ct_date_to_utc_range(check_date)

        earned_achievements = []

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # Get daily score data (score_date is already in CT)
            cursor.execute("""
                SELECT
                    ds.*,
                    rc.monthly_target / 22 as daily_target,
                    e.name as employee_name
                FROM daily_scores ds
                JOIN employees e ON ds.employee_id = e.id
                JOIN role_configs rc ON e.role_id = rc.id
                WHERE ds.employee_id = %s
                AND ds.score_date = %s
            """, (employee_id, check_date))

            daily_data = cursor.fetchone()
            if not daily_data:
                return earned_achievements

            # Check daily target met
            if float(daily_data['points_earned']) >= float(daily_data['daily_target']):
                if self._award_achievement(employee_id, 'daily_target_met', check_date):
                    earned_achievements.append(self.achievements['daily_target_met'])

            # Check perfect efficiency
            if float(daily_data['efficiency_rate']) >= 0.9:
                if self._award_achievement(employee_id, 'perfect_efficiency', check_date):
                    earned_achievements.append(self.achievements['perfect_efficiency'])

            # Check early bird (clock_in is in UTC, use UTC range)
            cursor.execute("""
                SELECT MIN(clock_in) as first_clock
                FROM clock_times
                WHERE employee_id = %s
                AND clock_in >= %s AND clock_in < %s
            """, (employee_id, utc_start, utc_end))

            clock_data = cursor.fetchone()
            if clock_data and clock_data['first_clock']:
                # Convert UTC to CT for hour check
                first_clock_ct = self.tz_helper.utc_to_ct(clock_data['first_clock'])
                if first_clock_ct.hour < 7 or (first_clock_ct.hour == 7 and first_clock_ct.minute <= 30):
                    if self._award_achievement(employee_id, 'early_bird', check_date):
                        earned_achievements.append(self.achievements['early_bird'])

            # Check zero idle (start_time is in UTC, use UTC range)
            cursor.execute("""
                SELECT COUNT(*) as idle_count
                FROM idle_periods
                WHERE employee_id = %s
                AND start_time >= %s AND start_time < %s
            """, (employee_id, utc_start, utc_end))

            idle_data = cursor.fetchone()
            if idle_data and idle_data['idle_count'] == 0:
                if self._award_achievement(employee_id, 'zero_idle', check_date):
                    earned_achievements.append(self.achievements['zero_idle'])

        return earned_achievements
    
    def check_streak_achievements(self, employee_id: int) -> List[Dict]:
        """Check and award streak achievements"""
        earned_achievements = []

        # Get current CT date and calculate 30 days ago
        ct_date = self.tz_helper.get_current_ct_date()
        date_30_days_ago = ct_date - timedelta(days=30)

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # Calculate current streak (score_date is in CT)
            cursor.execute("""
                SELECT
                    ds.score_date,
                    ds.points_earned,
                    rc.monthly_target / 22 as daily_target
                FROM daily_scores ds
                JOIN employees e ON ds.employee_id = e.id
                JOIN role_configs rc ON e.role_id = rc.id
                WHERE ds.employee_id = %s
                AND ds.score_date >= %s
                ORDER BY ds.score_date DESC
            """, (employee_id, date_30_days_ago))

            scores = cursor.fetchall()

            # Calculate streak
            current_streak = 0

            for i, score in enumerate(scores):
                expected_date = ct_date - timedelta(days=i)
                if score['score_date'] == expected_date and float(score['points_earned']) >= float(score['daily_target']):
                    current_streak += 1
                else:
                    break

            # Check streak achievements
            if current_streak >= 3 and self._award_achievement(employee_id, 'streak_3'):
                earned_achievements.append(self.achievements['streak_3'])

            if current_streak >= 7 and self._award_achievement(employee_id, 'streak_7'):
                earned_achievements.append(self.achievements['streak_7'])

            if current_streak >= 30 and self._award_achievement(employee_id, 'streak_30'):
                earned_achievements.append(self.achievements['streak_30'])

            # Update employee's current streak
            cursor.execute("""
                UPDATE employees
                SET current_streak = %s
                WHERE id = %s
            """, (current_streak, employee_id))

            conn.commit()

        return earned_achievements
    
    def check_milestone_achievements(self, employee_id: int) -> List[Dict]:
        """Check and award milestone achievements"""
        earned_achievements = []
        
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Get total points
            cursor.execute("""
                SELECT SUM(points_earned) as total_points
                FROM daily_scores
                WHERE employee_id = %s
            """, (employee_id,))
            
            result = cursor.fetchone()
            total_points = float(result['total_points'] or 0)
            
            # Check milestones
            if total_points >= 1000 and self._award_achievement(employee_id, 'first_1000_points'):
                earned_achievements.append(self.achievements['first_1000_points'])
            
            if total_points >= 10000 and self._award_achievement(employee_id, 'first_10000_points'):
                earned_achievements.append(self.achievements['first_10000_points'])
        
        return earned_achievements
    
    def _award_achievement(self, employee_id: int, achievement_key: str,
                          earned_date: date = None) -> bool:
        """Award an achievement to an employee"""
        if not earned_date:
            earned_date = self.tz_helper.get_current_ct_date()

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # Check if already earned (earned_date is stored as date, no conversion needed)
            cursor.execute("""
                SELECT id FROM achievements
                WHERE employee_id = %s
                AND achievement_key = %s
                AND earned_date = %s
            """, (employee_id, achievement_key, earned_date))

            if cursor.fetchone():
                return False  # Already earned

            achievement = self.achievements[achievement_key]

            # Award achievement
            cursor.execute("""
                INSERT INTO achievements
                (employee_id, achievement_key, achievement_name, description,
                 points_awarded, achievement_type, earned_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                employee_id,
                achievement_key,
                achievement['name'],
                achievement['description'],
                achievement['points'],
                achievement['type'].value,
                earned_date
            ))

            # Update employee's total achievement points
            cursor.execute("""
                UPDATE employees
                SET achievement_points = achievement_points + %s
                WHERE id = %s
            """, (achievement['points'], employee_id))

            conn.commit()

            logger.info(f"Awarded {achievement['name']} to employee {employee_id}")
            return True
    
    def get_employee_achievements(self, employee_id: int) -> Dict:
        """Get all achievements for an employee"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Get earned achievements
            cursor.execute("""
                SELECT * FROM achievements
                WHERE employee_id = %s
                ORDER BY earned_date DESC
            """, (employee_id,))
            
            earned = cursor.fetchall()
            
            # Get employee stats
            cursor.execute("""
                SELECT 
                    achievement_points,
                    current_streak
                FROM employees
                WHERE id = %s
            """, (employee_id,))
            
            stats = cursor.fetchone()
            
            # Calculate badge level
            points = stats['achievement_points'] if stats else 0
            badge_level = self._calculate_badge_level(points)
            
            # Get recent achievements (last 7 days)
            recent = [a for a in earned if (date.today() - a['earned_date']).days <= 7]
            
            return {
                'total_achievements': len(earned),
                'total_points': points,
                'current_streak': stats['current_streak'] if stats else 0,
                'badge_level': badge_level,
                'recent_achievements': recent,
                'all_achievements': earned,
                'available_achievements': len(self.achievements),
                'completion_percentage': round(len(earned) / len(self.achievements) * 100, 1)
            }
    
    def _calculate_badge_level(self, points: int) -> str:
        """Calculate badge level based on points"""
        if points >= 5000:
            return BadgeLevel.DIAMOND.value
        elif points >= 2000:
            return BadgeLevel.PLATINUM.value
        elif points >= 1000:
            return BadgeLevel.GOLD.value
        elif points >= 500:
            return BadgeLevel.SILVER.value
        elif points >= 100:
            return BadgeLevel.BRONZE.value
        else:
            return "none"
    
    def create_team_challenge(self, role_id: Optional[int], challenge_type: str,
                             target_value: float, start_date: date, end_date: date) -> int:
        """Create a team challenge"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO team_challenges
                (role_id, challenge_type, challenge_name, description,
                 target_value, start_date, end_date, reward_points, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            """, (
                role_id,
                challenge_type,
                f"Team Challenge: {challenge_type}",
                f"Achieve {target_value} as a team",
                target_value,
                start_date,
                end_date,
                100  # Default reward
            ))
            
            conn.commit()
            return cursor.lastrowid
    
    def get_leaderboard(self, period: str = "weekly") -> List[Dict]:
        """Get gamification leaderboard"""
        # Calculate date boundaries in CT
        ct_date = self.tz_helper.get_current_ct_date()

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            if period == "daily":
                date_filter = "earned_date = %s"
                date_params = (ct_date,)
            elif period == "weekly":
                date_7_days_ago = ct_date - timedelta(days=7)
                date_filter = "earned_date >= %s"
                date_params = (date_7_days_ago,)
            elif period == "monthly":
                # First day of current month
                first_day_of_month = ct_date.replace(day=1)
                date_filter = "earned_date >= %s"
                date_params = (first_day_of_month,)
            else:
                date_filter = "1=1"  # All time
                date_params = ()

            # Build query with parameterized date filter
            query = f"""
                SELECT
                    e.id,
                    e.name,
                    rc.role_name,
                    e.achievement_points as total_points,
                    e.current_streak,
                    COUNT(a.id) as achievements_earned,
                    SUM(CASE WHEN {date_filter} THEN a.points_awarded ELSE 0 END) as period_points
                FROM employees e
                LEFT JOIN role_configs rc ON e.role_id = rc.id
                LEFT JOIN achievements a ON e.id = a.employee_id
                WHERE e.is_active = TRUE
                GROUP BY e.id, e.name, rc.role_name, e.achievement_points, e.current_streak
                ORDER BY period_points DESC, total_points DESC
                LIMIT 10
            """

            cursor.execute(query, date_params)

            leaderboard = []
            for i, row in enumerate(cursor.fetchall()):
                leaderboard.append({
                    'rank': i + 1,
                    'employee_id': row['id'],
                    'name': row['name'],
                    'role': row['role_name'],
                    'period_points': row['period_points'] or 0,
                    'total_points': row['total_points'] or 0,
                    'current_streak': row['current_streak'] or 0,
                    'achievements_earned': row['achievements_earned'] or 0,
                    'badge_level': self._calculate_badge_level(row['total_points'] or 0)
                })

            return leaderboard
