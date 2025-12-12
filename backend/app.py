from dotenv import load_dotenv
load_dotenv()

import os
import logging
from api.gamification import gamification_bp
from api.team_metrics import team_metrics_bp
from api.connecteam import connecteam_bp
from api.dashboard import dashboard_bp
from api.employee_auth import employee_auth_bp
from api.admin_auth import admin_auth_bp
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime
from logging.handlers import RotatingFileHandler
from apscheduler.schedulers.background import BackgroundScheduler
from api.system_control import system_control_bp

# Import configuration
from config import config

# Import API blueprints
from api.activities import activity_bp
from api.cache import cache_bp
from api.flags import flags_bp
from api.trends import trends_bp
from api.schedule import schedule_bp
from api.idle import idle_bp
from api.gamification import gamification_bp
from api.team_metrics import team_metrics_bp
from api.connecteam import connecteam_bp

# Import services
from calculations.scheduler import ProductivityScheduler
from integrations.connecteam_sync import ConnecteamSync

# Initialize schedulers
productivity_scheduler = None
background_scheduler = None

def init_schedulers(app):
    """Initialize all schedulers"""
    global productivity_scheduler, background_scheduler
    
    # Initialize productivity scheduler
    productivity_scheduler = ProductivityScheduler()
    productivity_scheduler.start()
    app.logger.info("Productivity scheduler initialized and started")
    
    # Initialize background scheduler for Connecteam
    background_scheduler = BackgroundScheduler()
    
    # Connecteam sync scheduler (if enabled)
    if getattr(config, 'ENABLE_AUTO_SYNC', False):
        connecteam_sync = ConnecteamSync(
            config.CONNECTEAM_API_KEY,
            config.CONNECTEAM_CLOCK_ID
        )
        
        # Sync current shifts every 5 minutes
        background_scheduler.add_job(
            func=connecteam_sync.sync_todays_shifts,
            trigger="interval",
            minutes=5,
            id='connecteam_shifts_sync',
            name='Sync Connecteam shifts',
            replace_existing=True
        )
        
        # Sync employees daily at 2 AM
        background_scheduler.add_job(
            func=connecteam_sync.sync_employees,
            trigger="cron",
            hour=2,
            minute=0,
            id='connecteam_employee_sync',
            name='Sync Connecteam employees',
            replace_existing=True
        )
        
        app.logger.info("Connecteam auto-sync enabled")
    
    background_scheduler.start()
    app.logger.info("Background scheduler started")

def create_app(config_name=None):
    """Create and configure the Flask application"""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config)
    
    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": "*", "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"], "allow_headers": ["Content-Type", "X-API-Key"]}})
    
    # Configure logging
    configure_logging(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)

    # Initialize schedulers
    init_schedulers(app)
    
    return app

def configure_logging(app):
    """Configure application logging"""
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    file_handler = RotatingFileHandler(
        app.config['LOG_FILE'],
        maxBytes=10240000,  # 10MB
        backupCount=10
    )
    
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    )
    file_handler.setFormatter(formatter)
    
    log_level = getattr(logging, app.config['LOG_LEVEL'].upper())
    file_handler.setLevel(log_level)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(log_level)
    
    app.logger.info('Productivity Tracker startup')

def register_blueprints(app):
    """Register Flask blueprints"""
    app.register_blueprint(activity_bp, url_prefix='/api/activities')
    app.register_blueprint(cache_bp, url_prefix='/api/cache')
    app.register_blueprint(flags_bp, url_prefix='/api/flags')
    app.register_blueprint(trends_bp, url_prefix='/api/trends')
    app.register_blueprint(idle_bp, url_prefix='/api/idle')
    app.register_blueprint(gamification_bp, url_prefix='/api/gamification')
    app.register_blueprint(team_metrics_bp, url_prefix='/api/team-metrics')
    app.register_blueprint(connecteam_bp, url_prefix='/api/connecteam')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    app.register_blueprint(employee_auth_bp)
    app.register_blueprint(admin_auth_bp)
    app.register_blueprint(schedule_bp)
    app.register_blueprint(system_control_bp)  # No url_prefix needed as routes include /api/system
    app.logger.info("All blueprints registered successfully")

def register_error_handlers(app):
    """Register error handlers"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({'error': 'Resource not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'Server Error: {error}')
        return jsonify({'error': 'Internal server error'}), 500
    
    @app.errorhandler(400)
    def bad_request_error(error):
        return jsonify({'error': 'Bad request'}), 400

# Create Flask app
app = create_app()

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'Productivity Tracker API',
        'features': {
            'core': True,
            'analytics': True,
            'gamification': True,
            'team_metrics': True,
            'connecteam': True
        }
    }), 200

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'message': 'Productivity Tracker API',
        'version': '2.0.0',
        'endpoints': {
            'health': '/health',
            'api': {
                'activities': '/api/activities',
                'cache': '/api/cache',
                'flags': '/api/flags',
                'trends': '/api/trends',
                'idle': '/api/idle',
                'gamification': '/api/gamification',
                'team_metrics': '/api/team-metrics',
                'connecteam': '/api/connecteam'
            }
        }
    }), 200

@app.route('/api/scheduler/status', methods=['GET'])
def scheduler_status():
    """Get scheduler status"""
    status = {
        'productivity_scheduler': 'not initialized',
        'background_scheduler': 'not initialized'
    }
    
    if productivity_scheduler:
        jobs = productivity_scheduler.get_job_status()
        status['productivity_scheduler'] = {
            'status': 'running',
            'jobs': jobs
        }
    
    if background_scheduler and background_scheduler.running:
        bg_jobs = []
        for job in background_scheduler.get_jobs():
            bg_jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None
            })
        status['background_scheduler'] = {
            'status': 'running',
            'jobs': bg_jobs
        }
    
    return jsonify(status)

@app.route('/api/connecteam/status', methods=['GET'])
def connecteam_status():
    """Get Connecteam integration status"""
    return jsonify({
        'enabled': getattr(config, 'ENABLE_AUTO_SYNC', False),
        'sync_interval': getattr(config, 'SYNC_INTERVAL', 300),
        'clock_id': config.CONNECTEAM_CLOCK_ID
    })

# ============= STATION ASSIGNMENT ROUTES =============
@app.route('/api/station-performance', methods=['GET'])
def get_station_performance():
    """Get employee performance data by station"""
    from database.db_manager import DatabaseManager
    
    db = DatabaseManager()
    try:
        query = """
            SELECT 
                e.id as employee_id,
                e.name as employee_name,
                al.activity_type as station,
                AVG(al.items_count / GREATEST(al.duration_minutes/60, 0.1)) as avg_items_per_hour
            FROM employees e
            JOIN activity_logs al ON e.id = al.employee_id
            WHERE al.window_start >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                AND al.items_count > 0
            GROUP BY e.id, e.name, al.activity_type
            HAVING avg_items_per_hour > 0
        """
        
        # Use execute_query method from DatabaseManager
        results = db.execute_query(query)
        
        stations = {}
        for row in results:
            station = row.get('station', '')
            if station == 'In Production':
                station = 'Heat Press'
            if station and station not in stations:
                stations[station] = []
            if station:
                stations[station].append({
                    'employee_id': row['employee_id'],
                    'employee_name': row['employee_name'],
                    'avg_items_per_hour': round(float(row.get('avg_items_per_hour', 0)), 1)
                })
        
        return jsonify({'success': True, 'data': stations})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        app.logger.info('Shutting down...')
        shutdown_schedulers()
    except Exception as e:
        app.logger.error(f'Error running app: {e}')
        shutdown_schedulers()
