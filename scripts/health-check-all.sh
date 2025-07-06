# Create scripts/health-check-all.sh
#!/bin/bash
echo "=== Mnemosyne Local AI Server Health Check ==="

# Function to check if a container is running
container_exists() {
    docker ps --format "{{.Names}}" | grep -q "$1"
}

# Function to get container name by image pattern
get_container_by_image() {
    docker ps --format "{{.Names}}" --filter "ancestor=$1" | head -1
}

# Check service endpoints
echo -e "\nChecking service endpoints..."

# Mnemosyne health
if curl -s -f http://localhost:8000/health > /dev/null; then
    echo "✅ Mnemosyne API: Healthy"
else
    echo "❌ Mnemosyne API: Unhealthy"
fi

# Qdrant health
if curl -s -f http://localhost:6333/health > /dev/null; then
    echo "✅ Qdrant: Healthy"
else
    echo "❌ Qdrant: Unhealthy"
fi

# PostgreSQL health (find postgres container)
POSTGRES_CONTAINER=$(docker ps --format "{{.Names}}" --filter "ancestor=postgres" | head -1)
if [ -n "$POSTGRES_CONTAINER" ]; then
    if docker exec "$POSTGRES_CONTAINER" pg_isready -U postgres > /dev/null 2>&1; then
        echo "✅ PostgreSQL: Healthy"
    else
        echo "❌ PostgreSQL: Unhealthy"
    fi
else
    echo "ℹ️  PostgreSQL: Container not found"
fi

# Redis health (find redis container)
REDIS_CONTAINER=$(docker ps --format "{{.Names}}" --filter "ancestor=redis" | head -1)
if [ -n "$REDIS_CONTAINER" ]; then
    if docker exec "$REDIS_CONTAINER" redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis: Healthy"
    else
        echo "❌ Redis: Unhealthy"
    fi
else
    echo "ℹ️  Redis: Container not found"
fi

# Ollama health (external)
OLLAMA_URL=${OLLAMA_BASE_URL:-http://localhost:11434}
if curl -s -f ${OLLAMA_URL}/api/tags > /dev/null; then
    echo "✅ Ollama: Healthy"
else
    echo "❌ Ollama: Unhealthy"
fi

echo -e "\n=== Running Containers ==="
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"

echo -e "\n=== Resource Usage ==="
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"