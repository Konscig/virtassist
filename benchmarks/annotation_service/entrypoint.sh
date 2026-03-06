#!/bin/bash
set -e

echo "Starting Ollama server..."
NUM_THREADS=${OLLAMA_NUM_THREAD:-16}
echo "Using $NUM_THREADS CPU threads"
ollama serve &
OLLAMA_PID=$!

echo "Waiting for Ollama to be ready..."
sleep 5

for i in {1..30}; do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "Ollama is ready!"
        break
    fi
    echo "Waiting for Ollama... ($i/30)"
    sleep 2
done

echo "Checking/ downloading model qwen3.5:35b-a3b..."
ollama pull qwen3.5:35b-a3b

echo "Starting annotation..."
cd /app

python3 annotate_with_ollama.py \
    --input /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated.json \
    --model qwen3.5:35b-a3b \
    --batch-size 10 \
    --delay 0

echo "Annotation completed!"

kill $OLLAMA_PID
