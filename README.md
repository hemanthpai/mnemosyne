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
├── Dockerfile
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

### Environment Variables

Create `.env` files for local development:

**backend/.env**
```
DEBUG=True
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mnemosyne
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

### Qdrant Dashboard

Access Qdrant's web UI at: http://localhost:6333/dashboard

### Useful Commands

```bash
# View logs
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

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License.