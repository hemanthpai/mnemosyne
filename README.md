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

- **Memories App**: Handles memory extraction, retrieval, and listing.
- **Settings App**: Manages application settings such as API endpoint configurations.

### API Endpoints

1. **Extract Memories**: Accepts a string input (conversation snippet) and returns the number of memories extracted.
2. **Retrieve Memories**: Accepts a prompt and returns a list of relevant memories.
3. **List All Memories**: Accepts a user ID and returns all memories associated with that user.

## Frontend

The frontend is built using React and provides a user interface for interacting with the memory service. Key components include:

- **Memories Page**: Displays a list of all memories, filterable by user ID.
- **Memory Detail Page**: Allows editing or deleting of specific memories.
- **Settings Page**: Enables configuration of various application settings.

## Local Development Setup

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for local development without Docker)
- Node.js 18+ (for frontend development)

### Quick Start with Docker Compose

1. **Clone the repository**
```bash
git clone <repository-url>
cd mnemosyne
```

2. **Start all services**
```bash
docker-compose up -d
```

This will start:
- PostgreSQL database (port 5432)
- Qdrant vector database (port 6333)
- Django backend (port 8000)
- React frontend (port 3000)

3. **Initialize the database**
```bash
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py init_qdrant
```

4. **Test the setup**
```bash
# Test database connections
docker-compose exec backend python manage.py test_llm
docker-compose exec backend python manage.py test_qdrant
```

### Local Development (without Docker)

1. **Start Qdrant**
```bash
docker run -p 6333:6333 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant
```

2. **Start PostgreSQL**
```bash
docker run --name postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=mnemosyne -p 5432:5432 -d postgres:15
```

3. **Backend setup**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py init_qdrant
python manage.py runserver
```

4. **Frontend setup**
```bash
cd frontend
npm install
npm start
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
REDIS_URL=redis://redis:6379/0
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.100,your-server-ip

# Ollama settings (adjust to your setup)
OLLAMA_BASE_URL=http://192.168.1.50:11434  # Replace with your Ollama server IP
```

3. **Create home server Docker Compose file**

Create `docker-compose.homeserver.yml`:
```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: mnemosyne
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-homeserver_postgres_pass}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"  # Expose for direct access if needed
    volumes:
      - qdrant_data:/qdrant/storage
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped
    command: redis-server --appendonly yes

  app:
    build: .
    ports:
      - "8080:8000"  # Use 8080 to avoid conflicts
    environment:
      - DEBUG=False
      - DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD:-homeserver_postgres_pass}@db:5432/mnemosyne
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=${SECRET_KEY}
      - ALLOWED_HOSTS=${ALLOWED_HOSTS}
      - OLLAMA_BASE_URL=${OLLAMA_BASE_URL}
    depends_on:
      db:
        condition: service_healthy
      qdrant:
        condition: service_healthy
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs  # Optional: for persistent logs

volumes:
  postgres_data:
  qdrant_data:
  redis_data:
```

4. **Deploy the application**
```bash
# Build and start services
docker-compose -f docker-compose.homeserver.yml up -d

# Initialize the database
docker-compose -f docker-compose.homeserver.yml exec app python manage.py migrate
docker-compose -f docker-compose.homeserver.yml exec app python manage.py init_qdrant
```

5. **Access your application**
- Visit `http://YOUR_SERVER_IP:8080` from any device on your network
- Qdrant dashboard: `http://YOUR_SERVER_IP:6333/dashboard`

### Advanced Home Server Setup with Caddy + Tailscale

This setup provides secure remote access through Tailscale with automatic HTTPS using Caddy.

#### Prerequisites
- Tailscale account and devices configured
- Caddy knowledge (basic)

#### Setup Steps

1. **Install Tailscale on your home server**
```bash
# Ubuntu/Debian
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Enable Tailscale subnet routing (optional, for accessing other devices)
sudo tailscale up --advertise-routes=192.168.1.0/24 --accept-routes
```

2. **Create Caddyfile**

Create `Caddyfile` in your project root:
```caddy
# Replace with your Tailscale machine name or Tailscale IP
mnemosyne.your-tailnet.ts.net {
    # Automatic HTTPS with Tailscale certs
    tls internal

    # Main application
    reverse_proxy app:8000

    # Optional: Custom headers for better security
    header {
        # Security headers
        X-Frame-Options "SAMEORIGIN"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        
        # Remove server info
        -Server
    }

    # Optional: Basic auth for extra security
    # basicauth {
    #     admin $2a$14$Zkx19XLiW6VYouLHR5NmfOFU0z2GTNqq9qAQx4YF/v8N5UKW.NMjq  # password: secure123
    # }

    # Rate limiting
    rate_limit {
        zone static_ip_zone {
            key {remote_host}
            events 100
            window 1m
        }
    }
}

# Optional: Redirect HTTP to HTTPS
http://mnemosyne.your-tailnet.ts.net {
    redir https://mnemosyne.your-tailnet.ts.net{uri}
}

# Optional: Expose Qdrant dashboard (be careful with this)
qdrant.your-tailnet.ts.net {
    tls internal
    reverse_proxy qdrant:6333
    
    # Strongly recommend basic auth for Qdrant
    basicauth {
        admin $2a$14$Zkx19XLiW6VYouLHR5NmfOFU0z2GTNqq9qAQx4YF/v8N5UKW.NMjq
    }
}
```

3. **Create Tailscale-enabled Docker Compose file**

Create `docker-compose.tailscale.yml`:
```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: mnemosyne
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-tailscale_postgres_pass}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    networks:
      - mnemosyne_network

  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrant_data:/qdrant/storage
    restart: unless-stopped
    networks:
      - mnemosyne_network

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped
    command: redis-server --appendonly yes
    networks:
      - mnemosyne_network

  app:
    build: .
    environment:
      - DEBUG=False
      - DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD:-tailscale_postgres_pass}@db:5432/mnemosyne
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=${SECRET_KEY}
      - ALLOWED_HOSTS=mnemosyne.your-tailnet.ts.net,localhost,127.0.0.1
      - OLLAMA_BASE_URL=${OLLAMA_BASE_URL}
    depends_on:
      - db
      - qdrant
      - redis
    restart: unless-stopped
    networks:
      - mnemosyne_network

  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    restart: unless-stopped
    networks:
      - mnemosyne_network
    # Important: Use host networking for Tailscale to work properly
    network_mode: host
    depends_on:
      - app

networks:
  mnemosyne_network:
    driver: bridge

volumes:
  postgres_data:
  qdrant_data:
  redis_data:
  caddy_data:
  caddy_config:
```

4. **Deploy with Tailscale**
```bash
# Set your environment variables
export SECRET_KEY="your-secret-key-here"
export POSTGRES_PASSWORD="your-postgres-password"
export OLLAMA_BASE_URL="http://localhost:11434"  # or your Ollama server

# Start services
docker-compose -f docker-compose.tailscale.yml up -d

# Initialize
docker-compose -f docker-compose.tailscale.yml exec app python manage.py migrate
docker-compose -f docker-compose.tailscale.yml exec app python manage.py init_qdrant
```

5. **Access from anywhere**
- Install Tailscale on your devices (phone, laptop, etc.)
- Access `https://mnemosyne.your-tailnet.ts.net` from any Tailscale-connected device
- Qdrant dashboard: `https://qdrant.your-tailnet.ts.net` (if enabled)

#### Tailscale Benefits
- **Secure**: End-to-end encrypted WireGuard tunnels
- **Simple**: No port forwarding or firewall configuration
- **Multi-device**: Access from phone, laptop, anywhere
- **Automatic HTTPS**: Caddy handles certificates automatically
- **No external domain required**: Uses Tailscale's MagicDNS

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

## Production Deployment

### Prerequisites
- VPS or cloud server (minimum 2 GB RAM, 2 vCPUs)
- Docker and Docker Compose installed
- Domain name (optional but recommended)
- SSL certificate (Let's Encrypt recommended)

### Deploy with Docker Compose

1. **Clone the repository on your server**
```bash
git clone <repository-url>
cd mnemosyne
```

2. **Set up environment variables**
```bash
cp .env.prod.example .env.prod
# Edit .env.prod with your values
nano .env.prod
```

3. **Generate SSL certificates (using Let's Encrypt)**
```bash
# Install certbot
sudo apt update
sudo apt install certbot

# Generate certificates
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Copy certificates to project directory
sudo mkdir -p ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/key.pem
sudo chown -R $USER:$USER ssl/
```

4. **Deploy the application**
```bash
# Build and start services
docker-compose -f docker-compose.prod.yml up -d

# Initialize the database
docker-compose -f docker-compose.prod.yml exec app python manage.py migrate
docker-compose -f docker-compose.prod.yml exec app python manage.py init_qdrant
```

5. **Set up SSL certificate renewal**
```bash
# Add to crontab for automatic renewal
echo "0 12 * * * /usr/bin/certbot renew --quiet && docker-compose -f /path/to/mnemosyne/docker-compose.prod.yml restart nginx" | sudo crontab -
```

### Alternative: Single Container Deployment

For simpler deployments, you can use the single Dockerfile that includes both frontend and backend:

```bash
# Build the image
docker build -t mnemosyne .

# Run with external dependencies
docker run -d \
  --name mnemosyne \
  -p 8000:8000 \
  -e DATABASE_URL=your_database_url \
  -e QDRANT_HOST=your_qdrant_host \
  -e SECRET_KEY=your_secret_key \
  mnemosyne
```

### Cloud Platform Deployment

#### Deploy to Railway

1. Fork this repository
2. Connect Railway to your GitHub account
3. Create a new project from your fork
4. Set environment variables in Railway dashboard
5. Deploy automatically on git push

#### Deploy to DigitalOcean App Platform

1. Create a new app in DigitalOcean
2. Connect your repository
3. Configure build settings:
   - Build command: `docker build -t mnemosyne .`
   - Run command: `gunicorn --bind 0.0.0.0:8000 memory_service.wsgi:application`
4. Add PostgreSQL and Redis databases
5. Configure environment variables
6. Deploy

#### Deploy to AWS ECS/Fargate

1. Build and push image to ECR
2. Create ECS cluster and task definition
3. Configure RDS (PostgreSQL) and ElastiCache (Redis)
4. Set up Application Load Balancer
5. Configure auto-scaling and health checks

### Environment Variables

#### Development (.env)
```
DEBUG=True
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mnemosyne
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

#### Home Server (.env.homeserver)
```
DEBUG=False
SECRET_KEY=your_secret_key_here
DATABASE_URL=postgresql://postgres:password@db:5432/mnemosyne
QDRANT_HOST=qdrant
QDRANT_PORT=6333
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.100,your-tailscale-hostname
OLLAMA_BASE_URL=http://192.168.1.50:11434
```

#### Production (.env.prod)
```
DEBUG=False
SECRET_KEY=your_secret_key_here
DATABASE_URL=postgresql://user:password@host:port/database
QDRANT_HOST=qdrant_host
QDRANT_PORT=6333
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
REDIS_URL=redis://redis:6379/0
```

### Monitoring and Maintenance

#### Health Checks
```bash
# Check application health
curl http://localhost:8080/health/  # Home server
curl http://localhost:8000/health/  # Production

# Check all services
docker-compose -f docker-compose.homeserver.yml ps  # Home server
docker-compose -f docker-compose.prod.yml ps        # Production
```

#### Logs
```bash
# View application logs
docker-compose -f docker-compose.homeserver.yml logs -f app  # Home server
docker-compose -f docker-compose.prod.yml logs -f app       # Production

# View all service logs
docker-compose -f docker-compose.homeserver.yml logs -f     # Home server
docker-compose -f docker-compose.prod.yml logs -f          # Production
```

#### Backup Database
```bash
# Create backup (home server)
docker-compose -f docker-compose.homeserver.yml exec db pg_dump -U postgres mnemosyne > backup.sql

# Create backup (production)
docker-compose -f docker-compose.prod.yml exec db pg_dump -U postgres mnemosyne > backup.sql

# Restore backup
docker-compose -f docker-compose.homeserver.yml exec -T db psql -U postgres mnemosyne < backup.sql
```

#### Update Application
```bash
# Pull latest changes
git pull origin main

# Rebuild and restart (home server)
docker-compose -f docker-compose.homeserver.yml up -d --build

# Rebuild and restart (production)
docker-compose -f docker-compose.prod.yml up -d --build

# Run migrations if needed
docker-compose -f docker-compose.homeserver.yml exec app python manage.py migrate
```

### Qdrant Dashboard

Access Qdrant's web UI at:
- Development: http://localhost:6333/dashboard
- Home server: http://YOUR_SERVER_IP:6333/dashboard
- Tailscale: https://qdrant.your-tailnet.ts.net (if configured)
- Production: https://yourdomain.com:6333/dashboard

### Useful Commands

```bash
# View logs (adjust compose file as needed)
docker-compose logs -f backend
docker-compose logs -f qdrant

# Restart services
docker-compose restart backend
docker-compose restart qdrant

# Reset Qdrant data
docker-compose down
docker volume rm mnemosyne_qdrant_data
docker-compose up -d

# Test vector operations
docker-compose exec backend python manage.py test_qdrant
```

## Security Considerations

- Always use HTTPS in production
- Set strong passwords for database and Redis
- Keep dependencies updated
- Use environment variables for sensitive data
- Implement rate limiting (included in nginx config)
- Regular security updates
- Monitor logs for suspicious activity
- For home servers: Consider VPN or Tailscale for external access
- Use basic auth for sensitive endpoints like Qdrant dashboard

## Performance Optimization

- Use Redis for caching
- Configure PostgreSQL connection pooling
- Set appropriate Qdrant collection parameters
- Monitor resource usage and scale accordingly
- Use CDN for static files in high-traffic scenarios
- For home servers: Monitor disk I/O and RAM usage

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License.