# Mnemosyne - AI Memory Management

<img align="left" src="https://upload.wikimedia.org/wikipedia/commons/3/32/Mnemosyne_Rossetti.jpg" width="75" style="margin-right: 20px;"/>

*Mnemosyne, the Greek goddess of memory and remembrance*

Mnemosyne enables AI models to remember important information from past conversations. It extracts and stores memories from chat interactions, then retrieves relevant memories to provide context for future conversations.

<br clear="left"/>

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Open WebUI    │    │   Mnemosyne     │    │    Ollama       │
│   (Chat UI)     │◄──►│  (Memories)     │◄──►│   (LLM API)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                       ┌─────────────────┐
                       │   PostgreSQL    │
                       │   + Qdrant      │
                       │   (Storage)     │
                       └─────────────────┘
```

**Components:**
- **Django Backend**: REST API for memory extraction, storage, and retrieval
- **React Frontend**: Web UI for managing memories and settings
- **PostgreSQL**: Stores memory content and metadata
- **Qdrant**: Vector database for semantic memory search
- **OpenWebUI Filter**: Integrates memory into chat conversations

## Quick Start with Docker

### Prerequisites
- Docker and Docker Compose
- [Ollama](https://ollama.ai) running locally with your preferred models

### 1. Set up Mnemosyne

```bash
# Clone the repository
git clone <repository-url>
cd mnemosyne

# Create environment file
cp .env.example .env

# Edit .env and set required values:
# - SECRET_KEY (generate with: openssl rand -hex 32)
# - POSTGRES_PASSWORD
# - OLLAMA_BASE_URL (default: http://host.docker.internal:11434)
# - ALLOWED_HOSTS (add your IP/domain)

# Start all services
docker-compose -f docker-compose.homeserver.yml up -d

# Check status
docker-compose -f docker-compose.homeserver.yml ps
```

Mnemosyne will be available at `http://localhost:8080`

### 2. Set up Open WebUI

```bash
# Run Open WebUI with Docker
docker run -d -p 3000:8080 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -v open-webui:/app/backend/data \
  --name open-webui \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

Open WebUI will be available at `http://localhost:3000`

### 3. Install the Memory Filter

```bash
# Copy the filter to Open WebUI's functions directory
docker cp openwebui_mnemosyne_integration_v3.py open-webui:/app/backend/data/functions/
```

**Alternative**: In Open WebUI, go to **Settings** → **Functions** → **Import Function** and paste the contents of `openwebui_mnemosyne_integration_v3.py`

### 4. Configure the Filter

In Open WebUI:
1. Go to **Settings** → **Functions**
2. Enable "**Mnemosyne Memory Integration**"
3. Configure settings:
   - **Mnemosyne Endpoint**: `http://host.docker.internal:8080` (if both running in Docker)
   - **Optimization Level**: `fast` (recommended)
   - **Memory Limit**: `10` memories per retrieval

### 5. Test the Integration

1. Start a conversation in Open WebUI
2. You should see status messages like:
   - "🔍 Searching for relevant memories..."
   - "🤔 No relevant memories found" (for first conversation)
   - "🚀 Forwarding enhanced prompt to AI..."
3. After the AI responds, you'll see:
   - "💭 Analyzing new messages..."
   - "🎉 Extracted X new memories!"

## Configuring Mnemosyne

### Access the Settings UI

Navigate to `http://localhost:8080` and click **Settings** to configure the service.

### LLM Configuration

**Extraction Settings** (for memory extraction):
- **Provider**: Select `Ollama` (default), `OpenAI`, or `OpenAI Compatible`
- **Endpoint URL**: `http://host.docker.internal:11434` (Docker) or `http://localhost:11434`
- **Model**: The model used for all memory operations (extraction, search, analysis)
- **API Key**: Optional, only needed for OpenAI or compatible providers

**Recommended Ollama Models:**
```bash
# Install a good general-purpose model
ollama pull llama3.2:3b        # Fast, efficient
ollama pull mistral:7b         # More capable
ollama pull qwen2.5:14b        # Best quality

# Install embedding model (required)
ollama pull nomic-embed-text   # Fast embeddings
ollama pull mxbai-embed-large  # Better quality embeddings
```

**Embeddings Configuration**:
- **Provider**: Usually same as extraction provider
- **Endpoint URL**: Same as extraction endpoint
- **Model**: `nomic-embed-text` or `mxbai-embed-large`

### Generation Parameters

Fine-tune LLM behavior:
- **Temperature**: 0.6 (default) - Controls randomness (0.0-2.0)
- **Top-p**: 0.95 - Nucleus sampling for diversity
- **Top-k**: 20 - Limits vocabulary choices
- **Max Tokens**: 2048 - Maximum response length

### Search Configuration

**Semantic Enhancement**:
- **Enable Semantic Connections**: Find related memories using graph analysis
- **Enhancement Threshold**: 3 - Minimum memories before enhancement kicks in

**Search Thresholds** (similarity scores 0.0-1.0):
- **Direct**: 0.7 - Exact topic matches
- **Semantic**: 0.5 - Related concepts
- **Experiential**: 0.6 - Past experiences
- **Contextual**: 0.4 - Situational relevance
- **Interest**: 0.5 - General interests

**Memory Quality Threshold**: 0.35 - Filters out low-quality memories

### Prompt Templates

The system uses customizable prompts for different operations. You can modify these in the **Prompts** tab to improve extraction quality for your use case. Each prompt includes examples and formatting instructions.

## Testing with DevTools

Mnemosyne includes DevTools for testing memory operations without OpenWebUI.

### Access DevTools

Navigate to `http://localhost:8080` and click **DevTools** in the navigation.

### Test Memory Extraction

1. **Enter user message text** in the extraction panel:
   ```
   My name is Alex Chen and I'm a senior software engineer in San Francisco.
   I love hiking - last weekend I did the Dipsea Trail and got amazing photos
   of the coastline. I'm vegetarian and really into Radiohead lately. Currently
   learning Rust for systems programming while working with React/TypeScript
   at my day job.
   ```

2. **Enter User ID**: Use a UUID like `550e8400-e29b-41d4-a716-446655440000`
   - Must be a valid UUID format
   - Same ID links memories to the same user

3. **Click "Extract Memories"** to process the text

4. **View results**: See extracted memories with tags and metadata

### Test Memory Retrieval

1. **Enter a search prompt**: "I need to plan a weekend activity with Alex. Can you suggest something based on their interests and location?"

2. **Use the same User ID** from extraction

3. **Select optimization level**:
   - **Fast**: Minimal data, best performance
   - **Detailed**: Includes search metadata for debugging
   - **Full**: Everything including AI-generated summary

4. **Click "Retrieve Memories"** to search

5. **View results**: Relevant memories with similarity scores

### Sample Data

Click **"Load Sample Data"** to populate the forms with example conversation and user ID for quick testing.

### Tips for Testing

- Use consistent User IDs to build up memory for a test user
- Try different prompts to see how semantic search works
- Check the **Memories** page to view/edit all stored memories
- Use **Statistics** to monitor memory counts and performance

## Architecture Deep Dive

### Memory Lifecycle
1. **Extraction**: User messages are analyzed by LLM to extract meaningful memories
2. **Storage**: Memories are stored in PostgreSQL with vector embeddings in Qdrant
3. **Retrieval**: When user asks questions, semantic search finds relevant memories
4. **Context**: Retrieved memories are added to conversation context before sending to AI

### Filter Integration
The OpenWebUI filter operates in two phases:
- **Inlet**: Retrieves relevant memories and adds them as context before LLM processing
- **Outlet**: Extracts new memories from user messages after LLM responds

### Key Features
- **Semantic Search**: Finds relevant memories using vector similarity
- **User Isolation**: Memories are stored per-user with proper access controls
- **Deduplication**: Prevents processing the same message multiple times
- **Rate Limiting**: Protects against API abuse
- **Optimization Levels**: Configurable response sizes (fast/detailed/full)

## Local Development (Non-Docker)

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL
- Qdrant

### Backend Setup
```bash
# Start Qdrant
docker run -d -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant

# Start PostgreSQL (or use system installation)
docker run --name postgres -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=mnemosyne -p 5432:5432 -d postgres:15

# Setup Python environment
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
export DATABASE_URL="postgresql://postgres:dev@localhost:5432/mnemosyne"
export QDRANT_HOST=localhost
export QDRANT_PORT=6333
export OLLAMA_BASE_URL=http://localhost:11434
export SECRET_KEY="your-secret-key-here"
export DEBUG=1

# Initialize database
python manage.py migrate

# Start backend server
python manage.py runserver
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

The development frontend will be available at `http://localhost:5173`

## Troubleshooting

### Common Issues

**Connection Errors**: Ensure all services are running and accessible:
```bash
# Check Mnemosyne
curl http://localhost:8080/api/memories/

# Check Ollama
curl http://localhost:11434/api/tags

# Check service logs
docker-compose -f docker-compose.homeserver.yml logs -f
```

**Filter Not Working**:
- Verify the filter is enabled in Open WebUI settings
- Check that the Mnemosyne endpoint URL is correct
- Ensure Docker containers can communicate (use `host.docker.internal` for cross-container access)

**Memory Extraction Failing**:
- Verify Ollama is running and models are available
- Check Mnemosyne logs for LLM connection issues
- Ensure sufficient disk space for vector storage

## API Reference

### Key Endpoints
- `POST /api/memories/extract/` - Extract memories from conversation
- `POST /api/memories/retrieve/` - Search for relevant memories
- `GET /api/memories/` - List all memories (with optional user_id filter)

### Filter Configuration
The v3 filter includes enhanced features:
- **Persistent tracking**: Remembers processed messages across restarts
- **Session isolation**: Multiple chat threads operate independently
- **Smart status updates**: Shows forwarding progress for slow models
- **Configurable delays**: Adjustable timing for status messages

## License

This project is licensed under the MIT License.