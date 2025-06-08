# Create scripts/health-check-all.sh
#!/bin/bash
echo "=== Mnemosyne Local AI Server Health Check ==="

# Check Docker containers
echo "Checking Docker containers..."
docker-compose -f docker-compose.ai-server.yml ps

# Check service endpoints
echo -e "\nChecking service endpoints..."

# Mnemosyne health
if curl -s -f http://localhost:8000/api/health/ > /dev/null; then
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

# PostgreSQL health
if docker-compose -f docker-compose.ai-server.yml exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    echo "✅ PostgreSQL: Healthy"
else
    echo "❌ PostgreSQL: Unhealthy"
fi

# Redis health
if docker-compose -f docker-compose.ai-server.yml exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis: Healthy"
else
    echo "❌ Redis: Unhealthy"
fi

# Ollama health (external)
OLLAMA_URL=${OLLAMA_BASE_URL:-http://localhost:11434}
if curl -s -f ${OLLAMA_URL}/api/tags > /dev/null; then
    echo "✅ Ollama: Healthy"
else
    echo "❌ Ollama: Unhealthy (check OLLAMA_BASE_URL)"
fi

echo -e "\n=== Resource Usage ==="
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"