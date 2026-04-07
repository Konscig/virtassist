#!/bin/bash
set -e

SERVER="ave@iv-ml.orienteer.ru"
REMOTE_DIR="/srv/tgu/annotation_service"
LOCAL_DIR="Submodules/voproshalych/benchmarks/annotation_service"

echo "📦 Syncing files to server..."
rsync -avz --delete \
  --exclude "*.tar" \
  --exclude "*.md" \
  --exclude "docker-compose*.yml" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  "$LOCAL_DIR/" "$SERVER:$REMOTE_DIR/"

echo "✅ Sync complete!"
echo ""
echo "🔧 Run on server to build and start:"
echo "   cd /srv/tgu/annotation_service && bash restart.sh"
