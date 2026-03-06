#!/bin/bash
set -e

echo "🛑 Stopping container..."
docker stop voproshalych-annotation || true
docker rm voproshalych-annotation -f || true

echo "🏗️  Building new image..."
docker buildx build --platform linux/amd64 --load \
  -f Dockerfile -t voproshalych-annotation .

echo "🚀 Starting container..."
docker run -d \
  --name voproshalych-annotation \
  --restart unless-stopped \
  --entrypoint "" \
  --cpu-shares 100 \
  -p 11434:11434 \
  -v $(pwd)/data:/app/data \
  -v ollama_models:/root/.ollama/models \
  -e OLLAMA_FLASH_ATTENTION=false \
  -e OLLAMA_NUM_THREAD=16 \
  -e OLLAMA_NUM_GPU_LAYERS=0 \
  voproshalych-annotation:latest \
  /app/entrypoint.sh

echo "📊 Container status:"
docker ps | grep voproshalych-annotation || echo "❌ Container not running"

echo ""
echo "📝 View logs:"
echo "   docker logs -f voproshalych-annotation"
