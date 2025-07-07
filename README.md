# Mnemosyne - AI Memory Management

This project is a service that allows persisting and retrieving memories to enable AI models to remember important items from their past interactions with users. The application consists of a Django backend and a React frontend.

## Project Structure

```
mnemosyne
├── backend
│   ├── memory_service
│   ├── memories
│   ├── settings_app
│   ├── manage.py
│   ├── requirements.txt
│   └── .env
├── frontend
│   ├── public
│   ├── src
│   └── .env
├── docker-compose.yml
├── docker-compose.prod.yml
├── docker-compose.homeserver.yml
├── Dockerfile
├── nginx.conf
├── Caddyfile
└── qdrant_storage
```

## Backend

The backend is built using Django and provides REST API endpoints for memory management. Key components include:

- **Memories**: Handles memory extraction, retrieval, and CRUD operations.
- **Settings**: Manages application settings such as API endpoint configurations.

### API Endpoints

1. **Extract Memories**: Accepts a string input (conversation snippet) and returns the number of memories extracted.
2. **Retrieve Memories**: Accepts a prompt and returns a list of relevant memories.
3. **List All Memories**: Accepts a user ID and returns all memories associated with that user.

## Frontend

The frontend is built using React and provides a user interface for interacting with the memory service. Key components include:

- **Memories Page**: Displays a list of all memories, filterable by user ID.
- **Memory Detail Page**: Allows editing or deleting of specific memories.
- **Settings**: Enables configuration of various application settings.
- **DevTools**: Enables testing memory extraction and retrieval. Useful for prompt tuning.
- **Statistics**: Various stats related to memories stored.

## Local Development Setup

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for local development without Docker)
- Node.js 18+ (for frontend development)

### Local Development

If you prefer not to use Docker or need to debug services individually:

1. **Start Qdrant**
```bash
docker run -d -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant
```

2. **Start PostgreSQL**
```bash
# Using your system's PostgreSQL or:
docker run --name postgres -e POSTGRES_PASSWORD= -e POSTGRES_DB=mnemosyne -p 5432:5432 -d postgres:15
```

3. **Backend setup**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="postgresql://postgres:your_password@localhost:5432/mnemosyne"
python manage.py migrate
python manage.py runserver
```

4. **Frontend setup**
```bash
cd frontend
npm install
npm run dev
```

## Home Server Deployment

Perfect for running on a Raspberry Pi, NUC, or home server for personal use or local network access.

### Prerequisites
- Home server with Docker and Docker Compose
- Minimum 2 GB RAM (4 GB recommended for better performance)
- Ollama running locally or accessible on your network

### Simple Home Server Setup

This setup is ideal for local network access without external domain requirements.

1. **Clone the repository on your home server**
```bash
git clone <repository-url>
cd mnemosyne
```

2. **Create home server environment file**
```bash
cp .env.example .env.homeserver
```

Edit `.env.homeserver`:
```bash
# Basic settings for home server
DEBUG=False
SECRET_KEY=your_secret_key_here
DATABASE_URL=postgresql://postgres:your_password@db:5432/mnemosyne
QDRANT_HOST=qdrant
QDRANT_PORT=6333
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.100,your-server-ip

# Ollama settings (adjust to your setup)
OLLAMA_BASE_URL=http://192.168.1.50:11434  # Replace with your Ollama server IP
```

3. **Modify the home server Docker Compose file if necessary**

The provided `docker-compose.homeserver.yml` includes:
* PostgreSQL database with persistent storage
* Qdrant vector database exposed on port 6333
* The backend APIs exposed on port 8080
* The frontend exposed on port 8080

4. **Deploy the application**
```bash
# Build and start services
docker-compose -f docker-compose.homeserver.yml up -d
```

5. **Access your application**
- Visit `http://YOUR_SERVER_IP:8080` from any device on your network
- Qdrant dashboard: `http://YOUR_SERVER_IP:6333/dashboard`

### Home Server Management

#### System Service (Optional)
Create a systemd service for automatic startup:

```bash
sudo nano /etc/systemd/system/mnemosyne.service
```

```ini
[Unit]
Description=Mnemosyne AI Memory Service
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/yourusername/mnemosyne
ExecStart=/usr/bin/docker-compose -f docker-compose.homeserver.yml up -d
ExecStop=/usr/bin/docker-compose -f docker-compose.homeserver.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Enable the service:
```bash
sudo systemctl enable mnemosyne.service
sudo systemctl start mnemosyne.service
```

#### Backup Script for Home Server
Create `backup.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/home/backups/mnemosyne"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
docker-compose -f docker-compose.homeserver.yml exec -T db pg_dump -U postgres mnemosyne > "$BACKUP_DIR/database_$DATE.sql"

# Backup Qdrant data (stop service first for consistency)
docker-compose -f docker-compose.homeserver.yml stop qdrant
tar -czf "$BACKUP_DIR/qdrant_$DATE.tar.gz" ./qdrant_storage/
docker-compose -f docker-compose.homeserver.yml start qdrant

# Keep only last 7 backups
find $BACKUP_DIR -name "database_*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "qdrant_*.tar.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
```

Make it executable and add to cron:
```bash
chmod +x backup.sh
crontab -e
# Add: 0 2 * * * /path/to/mnemosyne/backup.sh
```

#### Monitoring and Logs
```bash
# View all service status
docker-compose -f docker-compose.homeserver.yml ps

# Monitor logs in real-time
docker-compose -f docker-compose.homeserver.yml logs -f

# Check resource usage
docker stats

# View app logs only
docker-compose -f docker-compose.homeserver.yml logs -f app

# Restart if needed
docker-compose -f docker-compose.homeserver.yml restart app
```

#### Home Server Tips
1. **Resource Monitoring**: Consider using Portainer for Docker GUI management
2. **Auto-updates**: Use Watchtower for automatic container updates
3. **Notifications**: Set up monitoring with Uptime Kuma or similar
4. **Storage**: Monitor disk usage, especially for Qdrant vectors and database
5. **Performance**: Adjust Docker memory limits based on your server capacity

### Home Server Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Open WebUI    │    │    Ollama       │    │   Mnemosyne     │
│   Port: 8080    │◄──►│   Port: 11434   │◄──►│   Port: 8000    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────────────┐
                    │     Local Network       │
                    │  (192.168.1.0/24)      │
                    └─────────────────────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              │                                     │
    ┌─────────────────┐                   ┌─────────────────┐
    │   PostgreSQL    │                   │     Qdrant      │
    │   Port: 5432    │                   │   Port: 6333    │
    └─────────────────┘                   └─────────────────┘
```

### Troubleshooting

#### Common Issues

1. **Ollama Connection Failed**
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Test from container
docker-compose -f docker-compose.ai-server.yml exec mnemosyne \
  curl http://host.docker.internal:11434/api/tags
```

2. **Out of Memory Errors**
```bash
# Check memory usage
free -h
docker stats

# Reduce batch size
echo "VECTOR_BATCH_SIZE=25" >> .env
docker-compose -f docker-compose.ai-server.yml restart mnemosyne
```

3. **Slow Vector Search**
```bash
# Optimize Qdrant collection
docker-compose -f docker-compose.ai-server.yml exec mnemosyne \
  python manage.py optimize_qdrant --recreate
```

#### Performance Tuning

1. **For Lower-End Hardware (< 8GB RAM):**
```bash
# Reduce resource allocation
DJANGO_WORKERS=1
VECTOR_BATCH_SIZE=25
QDRANT_MAX_SEGMENT_SIZE=1000000
```

2. **For High-End Hardware (> 16GB RAM):**
```bash
# Increase performance
DJANGO_WORKERS=4
VECTOR_BATCH_SIZE=100
QDRANT_RAM_OPTIMIZED=True
```

### Integration Examples

#### Basic Memory Storage
```bash
# Store a conversation
curl -X POST http://localhost:8000/api/memories/extract/ \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_text": "I love hiking in the mountains every weekend.",
    "user_id": "user-123"
  }'
```

#### Memory Retrieval
```bash
# Retrieve relevant memories
curl -X POST http://localhost:8000/api/memories/retrieve/ \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What outdoor activities does the user enjoy?",
    "user_id": "user-123"
  }'
```

#### Open WebUI

Coming soon!

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License.
