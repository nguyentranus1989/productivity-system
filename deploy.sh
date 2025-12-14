#!/bin/bash
MESSAGE=${1:-"Update from local development"}
FRONTEND_ONLY=${2:-""}

echo "🚀 Deploying: $MESSAGE"

# Add and commit
git add .
git commit -m "$MESSAGE"

# Push to GitHub
git push

# Deploy to production
echo "📥 Updating production server..."
if [ "$FRONTEND_ONLY" = "--frontend" ]; then
    # Frontend only - just pull, no service restart
    ssh root@134.199.194.237 << 'ENDSSH'
cd /var/www/productivity-system
git pull
echo "✅ Frontend updated (no backend restart)"
ENDSSH
else
    # Full deploy - pull and restart services
    ssh root@134.199.194.237 << 'ENDSSH'
cd /var/www/productivity-system
git pull
cd backend
source venv/bin/activate
pm2 restart flask-backend
pm2 restart podfactory-sync
echo "✅ Production updated!"
ENDSSH
fi

echo "✅ Deployment complete!"
echo "🔗 Check: http://134.199.194.237"
