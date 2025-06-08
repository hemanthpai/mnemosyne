# Create scripts/health-check.sh
#!/bin/bash
# Health check script for monitoring

# Check if server is responding
if ! curl -f http://localhost:8000/api/health/ > /dev/null 2>&1; then
    echo "UNHEALTHY: Server not responding"
    exit 1
fi

# Check database connection
if ! python manage.py check --database default > /dev/null 2>&1; then
    echo "UNHEALTHY: Database connection failed"
    exit 1
fi

# Check Qdrant connection
if ! python manage.py test_qdrant_connection > /dev/null 2>&1; then
    echo "UNHEALTHY: Qdrant connection failed"
    exit 1
fi

echo "HEALTHY: All systems operational"
exit 0