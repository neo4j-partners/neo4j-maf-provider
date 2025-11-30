#!/bin/bash
set -e

IMAGE_NAME="simple-ai-agents"
CONTAINER_NAME="simple-ai-agents"
PORT="${PORT:-8000}"

echo "Building Docker image..."
docker build -t "$IMAGE_NAME" .

echo "Stopping existing container (if any)..."
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

echo "Starting container on port $PORT..."
# Create clean env file (docker --env-file reads quotes literally)
CLEAN_ENV=$(mktemp)
grep -v '^#' src/.env | grep -v '^$' | sed 's/"//g' > "$CLEAN_ENV"

docker run -d \
    --name "$CONTAINER_NAME" \
    -p "$PORT:50505" \
    -v ~/.azure:/root/.azure:ro \
    --env-file "$CLEAN_ENV" \
    "$IMAGE_NAME"

rm -f "$CLEAN_ENV"

echo "Container started. API available at http://localhost:$PORT"
echo "View logs: docker logs -f $CONTAINER_NAME"
