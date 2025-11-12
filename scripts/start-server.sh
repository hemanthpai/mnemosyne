# Create scripts/start-server.sh
#!/bin/bash
set -e

echo "=== Mnemosyne AI Memory Service Startup ==="
echo "Timestamp: $(date)"

# Wait for database connection (basic connectivity only)
echo "Waiting for database connection..."
until pg_isready -h ${DATABASE_HOST:-db} -p ${DATABASE_PORT:-5432} -U ${DATABASE_USER:-postgres}; do
    echo "Database unavailable - sleeping"
    sleep 2
done
echo "Database connected successfully"

# Run migrations FIRST (before any Django operations that might access models)
echo "Running database migrations..."
python manage.py migrate --noinput

# Now we can safely do Django operations that access the database
echo "Checking Django database configuration..."
python manage.py check --database default

# Wait for Qdrant
echo "Waiting for Qdrant connection..."
until python manage.py test_qdrant; do
    echo "Qdrant unavailable - sleeping"
    sleep 2
done
echo "Qdrant connected successfully"

# Initialize Qdrant collection
echo "Initializing Qdrant collection..."
python manage.py init_qdrant

# Phase 1: Settings are configured via environment variables
# No need to create default settings in database
echo "Phase 1: Settings configured via environment variables"

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear || echo "Static files collection skipped"

echo "=== Starting Django-Q Worker Cluster ==="
# Start Django-Q cluster in background for async task processing
python manage.py qcluster &
QCLUSTER_PID=$!
echo "Django-Q cluster started with PID: $QCLUSTER_PID"

# Give Django-Q a moment to initialize
sleep 2

echo "=== Starting Gunicorn Server ==="
# Minimal but production-ready gunicorn config
# Run in background (not exec) so qcluster stays alive
gunicorn memory_service.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile - \
    --log-level info &
GUNICORN_PID=$!
echo "Gunicorn server started with PID: $GUNICORN_PID"

echo "=== Mnemosyne AI Memory Service Started Successfully ==="
echo "Django-Q PID: $QCLUSTER_PID | Gunicorn PID: $GUNICORN_PID"

# Trap SIGTERM and SIGINT to gracefully shutdown both processes
trap "echo 'Shutting down...'; kill -TERM $QCLUSTER_PID $GUNICORN_PID 2>/dev/null; wait" SIGTERM SIGINT

# Wait for both processes - if either exits, the script will exit
wait