module.exports = {
  apps: [
    {
      name: 'predictions-morning',
      script: 'run_daily.py',
      interpreter: '/var/www/productivity-system/backend/venv/bin/python3',
      cwd: '/var/www/productivity-system/backend/prediction_model',
      cron_restart: '0 6 * * *',  // 6:00 AM daily
      autorestart: false,
      watch: false
    },
    {
      name: 'predictions-learning',
      script: 'update_midnight.py',
      interpreter: '/var/www/productivity-system/backend/venv/bin/python3',
      cwd: '/var/www/productivity-system/backend/prediction_model',
      cron_restart: '59 23 * * *',  // 11:59 PM daily
      autorestart: false,
      watch: false
    }
  ]
}
