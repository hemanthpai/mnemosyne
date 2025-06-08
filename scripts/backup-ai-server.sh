# Create scripts/backup-ai-server.sh
#!/bin/bash
set -e

BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "=== Mnemosyne AI Server Backup ==="
echo "Backup directory: $BACKUP_DIR"

# Backup database
echo "Backing up PostgreSQL database..."
docker-compose -f docker-compose.ai-server.yml exec -T postgres \
    pg_dump -U postgres mnemosyne > "$BACKUP_DIR/database.sql"

# Backup Qdrant vectors
echo "Backing up Qdrant vectors..."
docker-compose -f docker-compose.ai-server.yml stop qdrant
tar -czf "$BACKUP_DIR/qdrant_vectors.tar.gz" -C ./data qdrant/ 2>/dev/null || echo "Qdrant data directory not found"
docker-compose -f docker-compose.ai-server.yml start qdrant

# Backup configuration
echo "Backing up configuration files..."
cp .env "$BACKUP_DIR/env_backup" 2>/dev/null || echo "No .env file found"
cp docker-compose.ai-server.yml "$BACKUP_DIR/"

# Create restore script
cat > "$BACKUP_DIR/restore.sh" << 'EOF'
#!/bin/bash
set -e
echo "Restoring Mnemosyne backup..."

# Restore database
if [ -f "database.sql" ]; then
    echo "Restoring database..."
    docker-compose -f docker-compose.ai-server.yml exec -T postgres \
        psql -U postgres -d mnemosyne < database.sql
fi

# Restore Qdrant
if [ -f "qdrant_vectors.tar.gz" ]; then
    echo "Restoring Qdrant vectors..."
    docker-compose -f docker-compose.ai-server.yml stop qdrant
    tar -xzf qdrant_vectors.tar.gz -C ./data/
    docker-compose -f docker-compose.ai-server.yml start qdrant
fi

echo "Restore completed!"
EOF

chmod +x "$BACKUP_DIR/restore.sh"

echo "Backup completed: $BACKUP_DIR"
echo "To restore: cd $BACKUP_DIR && ./restore.sh"