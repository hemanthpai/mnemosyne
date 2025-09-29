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
- **LLM Provider** (one of the following):
  - [Ollama](https://ollama.ai) running locally with your preferred models
  - OpenAI API key (or OpenAI-compatible endpoint)

### 1. Set up Mnemosyne

```bash
# Clone the repository
git clone <repository-url>
cd mnemosyne

# Create environment file
cp .env.example .env

# Edit .env and set required values:
# - DATABASE_URL="postgresql://postgres_user:your_password@localhost:5432/mnemosyne"
# - QDRANT_HOST=localhost
# - QDRANT_PORT=6333
# - OLLAMA_BASE_URL=http://localhost:11434
# - SECRET_KEY="your-secret-key-here"
# - DEBUG=false

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

**Choose Your Provider:**

**Option 1: Ollama (Local/Self-Hosted)**
- **Provider**: Select `Ollama`
- **Endpoint URL**:
  - Docker: `http://host.docker.internal:11434`
  - Local: `http://localhost:11434`
- **Model**: Using an instruction-following model is recommended. Model suggestion: `Qwen3-30B-A3B`
- **API Key**: Leave empty

**Option 2: OpenAI**
- **Provider**: Select `OpenAI`
- **Endpoint URL**: `https://api.openai.com/v1`
- **Model**: `gpt-4o-mini` or `gpt-4o`
- **API Key**: Your OpenAI API key

**Option 3: OpenAI-Compatible (Groq, Together, etc.)**
- **Provider**: Select `OpenAI Compatible`
- **Endpoint URL**: Your provider's API endpoint
- **Model**: Provider-specific model name
- **API Key**: Your provider's API key

**Embeddings Configuration**:
- **For Ollama**: Use `nomic-embed-text` or `mxbai-embed-large`
- **For OpenAI**: Use `text-embedding-3-small` or `text-embedding-ada-002`
- **Endpoint URL**: Same as your LLM endpoint

### Generation Parameters

Fine-tune LLM behavior:
- **Temperature**: 0.6 (default) - Controls randomness (0.0-2.0)
- **Top-p**: 0.95 - Nucleus sampling for diversity
- **Top-k**: 20 - Limits vocabulary choices
- **Max Tokens**: 2048 - Maximum response length

### Search Configuration

**Search Thresholds** (similarity scores 0.0-1.0):
- **Direct**: 0.7 - Exact topic matches
- **Semantic**: 0.5 - Related concepts
- **Experiential**: 0.6 - Past experiences
- **Contextual**: 0.4 - Situational relevance
- **Interest**: 0.5 - General interests

### Prompt Templates

The system uses customizable prompts for different operations. You can modify these in the **Prompts** tab to improve extraction quality for your use case. Each prompt includes examples and formatting instructions.

## Testing with DevTools

Mnemosyne includes DevTools for testing memory operations without OpenWebUI.

### Access DevTools

Navigate to `http://localhost:8080` and click **DevTools** in the navigation.

### Test Memory Extraction

1. **Enter conversation text** in the extraction panel:
   ```
   User: I love hiking in Colorado, especially the Maroon Bells trail.
   Assistant: That sounds amazing! When did you last visit?
   User: Last fall. The aspens were incredible.
   ```

2. **Enter User ID**: Use a UUID like `550e8400-e29b-41d4-a716-446655440000`
   - Must be a valid UUID format
   - Same ID links memories to the same user

3. **Click "Extract Memories"** to process the conversation

4. **View results**: See extracted memories with tags and metadata

### Test Memory Retrieval

1. **Enter a search prompt**: "What outdoor activities does the user enjoy?"

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
export DATABASE_URL="postgresql://postgres_user:your_password@localhost:5432/mnemosyne"
export QDRANT_HOST=localhost
export QDRANT_PORT=6333
export OLLAMA_BASE_URL=http://localhost:11434
export SECRET_KEY="your-secret-key-here"
export DEBUG=true

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

## License

This project is licensed under the MIT License.