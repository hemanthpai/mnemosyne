# Mnemosyne - AI Memory Management

<img align="left" src="https://upload.wikimedia.org/wikipedia/commons/3/32/Mnemosyne_Rossetti.jpg" width="75" style="margin-right: 20px;"/>

*Mnemosyne, the Greek goddess of memory and remembrance*

Mnemosyne enables AI models to remember important information from past conversations. It extracts atomic facts, builds knowledge graphs, and provides memory retrieval through a Model Context Protocol (MCP) server for integration with any MCP-compatible AI assistant.

<br clear="left"/>

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      AI Assistants (MCP Clients)                 │
├──────────────┬───────────────┬──────────────┬────────────────────┤
│ Claude       │ Cursor/Cline  │ Open WebUI   │ Home Assistant     │
│ Desktop      │ Continue      │ (v0.6.31+)   │ Voice Assistant    │
│ (stdio)      │ (stdio)       │ (HTTP)       │ (HTTP)             │
└──────┬───────┴───────┬───────┴──────┬───────┴──────┬─────────────┘
       │               │              │              │
       │     ┌─────────┴──────────────┴──────────────┴─────────┐
       │     │        Mnemosyne MCP Server (FastMCP)           │
       │     │   - stdio transport (local clients)             │
       │     │   - HTTP transport (networked clients)          │
       │     │   Tools, Resources, Prompts                     │
       │     └──────────────────┬──────────────────────────────┘
       │                        │
       │     ┌──────────────────┴──────────────────┐
       │     │      Mnemosyne Backend (Django)     │
       │     │   - REST API                        │
       │     │   - Memory extraction               │◄──── React Frontend
       │     │   - Knowledge graph building        │      (Web UI)
       │     └──────────────────┬──────────────────┘
       │                        │
       │     ┌──────────────────┴──────────────────┐
       │     │           Storage Layer             │
       │     │  - PostgreSQL (metadata)            │
       │     │  - Qdrant (vectors)                 │◄──── LLM API
       │     │  - Redis (cache + queue)            │      (Ollama/OpenAI)
       │     └─────────────────────────────────────┘
       │
       └─────► AI-Intuitive Tools: recall, remember, what_do_i_know
```

**Components:**
- **FastMCP Server**: Dual-transport MCP server (stdio + HTTP) with Tools, Resources, Prompts
- **Django Backend**: REST API for memory extraction, storage, and retrieval
- **React Frontend**: Web UI for managing memories, settings, and imports
- **PostgreSQL**: Stores conversation metadata and atomic notes
- **Qdrant**: Vector database for semantic memory search
- **Redis + Django-Q**: Cache and background task processing
- **LLM Integration**: Works with any Ollama or OpenAI-compatible endpoint

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
# - SECRET_KEY="your-secret-key-here"
# - DEBUG=false

# Start all services
docker-compose -f docker-compose.homeserver.yml up -d

# Check status
docker-compose -f docker-compose.homeserver.yml ps
```

Mnemosyne will be available at `http://localhost:8080`

### 2. Configure Settings

Navigate to `http://localhost:8080/settings` to configure your LLM provider:

**For Ollama:**
- Provider: `Ollama`
- Endpoint URL: `http://host.docker.internal:11434` (Docker) or `http://localhost:11434` (local)
- Embeddings Model: `nomic-embed-text` or `mxbai-embed-large`
- Generation Model: Your preferred instruction-following model (e.g., `qwen2.5:32b`, `llama3.1:70b`)
- Temperature: 0.6-0.8 for Qwen models, 0.7 for Llama models (adjust based on your model's recommendations)

**For OpenAI:**
- Provider: `OpenAI`
- Endpoint URL: `https://api.openai.com/v1`
- Embeddings Model: `text-embedding-3-small`
- Generation Model: `gpt-4o-mini` or `gpt-4o`
- API Key: Your OpenAI API key
- Temperature: Default 0.6 works well

### 3. Set up MCP Server

Mnemosyne provides a FastMCP-based server with two transports:
- **stdio**: For local clients (Claude Desktop, Cursor, Cline, Continue)
- **HTTP**: For networked clients (Open WebUI, Home Assistant, web apps)

**Docker (Auto-Start with HTTP)**:

The MCP server auto-starts with HTTP transport in Docker:

```bash
docker-compose -f docker-compose.homeserver.yml up -d
```

MCP server will be available at `http://localhost:3000`

**Local Development**:

Choose the appropriate transport for your client:

```bash
# For Claude Desktop, Cursor, Cline, Continue (stdio)
./scripts/start_mcp_stdio.sh

# For Open WebUI, Home Assistant, web clients (HTTP)
./scripts/start_mcp_http.sh
```

---

## MCP Client Integration

### Claude Desktop

**Transport**: stdio

**Configuration** (`~/.config/Claude/claude_desktop_config.json` on macOS):
```json
{
  "mcpServers": {
    "mnemosyne": {
      "command": "/path/to/mnemosyne/scripts/start_mcp_stdio.sh"
    }
  }
}
```

### Cursor / Cline / Continue

**Transport**: stdio

Follow your IDE's MCP configuration docs. The server command is:
```bash
/path/to/mnemosyne/scripts/start_mcp_stdio.sh
```

### Open WebUI

**Transport**: HTTP (native support, no proxy needed!)

**Requirements**: Open WebUI v0.6.31+

**Configuration**:

1. **Using Docker** (recommended):
   - Mnemosyne MCP server auto-starts at `http://mnemosyne_mcp_server:3000`
   - From Open WebUI container, use: `http://mnemosyne_mcp_server:3000`

2. **Local/Manual Setup**:
   ```bash
   # Start HTTP server
   ./scripts/start_mcp_http.sh
   ```

3. **Configure in Open WebUI**:
   - Go to ⚙️ Admin Settings → External Tools
   - Click + (Add Server)
   - Type: **MCP (Streamable HTTP)**
   - URL: `http://localhost:3000` (or `http://mnemosyne_mcp_server:3000` in Docker)
   - Save

Your LLM now has access to intuitive memory tools: `recall`, `remember`, `what_do_i_know`!

See [Open WebUI MCP docs](https://docs.openwebui.com/features/mcp/) for details.

**Known Limitation - Multi-User Context**:

Open WebUI currently uses a **shared MCP client** without per-user context passing (see [Discussion #14121](https://github.com/open-webui/open-webui/discussions/14121)). This means:

- All MCP tool calls from Open WebUI lack user identification
- Memories would be stored/retrieved for a single "system" user
- Multi-user deployments cannot maintain separate memory contexts

**Workaround**: Use the import feature to load existing Open WebUI conversations (preserves multi-user attribution), then use MCP for single-user setups until Open WebUI implements per-user MCP authentication.

**Status**: We're tracking this upstream and will add user context support when Open WebUI enables it.

### Home Assistant

**Transport**: HTTP

**Requirements**: Home Assistant with MCP integration enabled

Home Assistant can act as an **MCP Client**, allowing your voice assistants (using local Ollama LLMs) to access Mnemosyne's memory.

**Configuration**:

1. **Start Mnemosyne MCP server** (HTTP):
   ```bash
   ./scripts/start_mcp_http.sh
   ```
   Or use Docker (auto-starts on port 3000)

2. **Add MCP Server in Home Assistant**:
   - Go to Settings → Devices & Services → Integrations
   - Add "Model Context Protocol"
   - Server Type: **MCP Client**
   - Server URL: `http://your-mnemosyne-host:3000`
   - Save

3. **Configure Conversation Agent**:
   - The MCP tools become available to your conversation agent
   - Voice commands can now trigger memory search/storage
   - Works with local Ollama LLMs

**Example Conversation**:
```
User: "Remember that I prefer the living room lights at 40% in the evening"
Assistant: [Calls remember("I prefer the living room lights at 40% in the evening")]
          "Got it, I'll remember that preference."

User: "What did I say about my coffee preferences?"
Assistant: [Calls recall("coffee preferences")]
          "You mentioned you like your coffee with oat milk, no sugar."

User: "Turn on the lights"
Assistant: [Calls recall("light preferences")]
          [Finds: "prefers living room lights at 40% in evening"]
          "Setting living room lights to 40%"
```

Voice assistant naturally uses memory during conversations!

See [Home Assistant MCP docs](https://www.home-assistant.io/integrations/mcp/) for details.

---

## MCP Capabilities

Mnemosyne's MCP tools are designed for **AI intuitiveness** - models naturally understand when and how to use them.

**Tools** (Actions):

- **`recall(query)`** - Find relevant information from past conversations
  - **When to use**: Before answering questions that might benefit from context
  - Example: User asks "What's my favorite coffee?" → Call `recall("favorite coffee")`

- **`remember(what_user_said)`** - Store important information
  - **When to use**: When user shares preferences, personal info, or feedback
  - Example: User says "I'm allergic to peanuts" → Call `remember("I'm allergic to peanuts")`

- **`what_do_i_know()`** - Get overview of user context
  - **When to use**: Start of conversations or when unsure if you have context
  - Example: New conversation starts → Call `what_do_i_know()` to personalize greeting

**Resources** (Data Streams):
- `memory://recent` - Recent conversations (working memory)
- `memory://knowledge` - Extracted facts and knowledge graph

**Prompts** (Workflow Templates):
- `start_conversation_with_memory` - Guide for conversation start
- `answer_with_memory` - Guide for answering with context
- `user_shared_something_important` - Guide for what to remember

**Design Philosophy**:
- Natural language tool names (recall, remember vs search_memories, store_turn)
- Clear WHEN guidance (not just WHAT they do)
- Auto-inferred parameters (no manual user_id, session_id management)
- Higher-level abstractions (not 1:1 API mapping)

### 4. Import Existing Conversations (Optional)

If you have an Open WebUI history to import:

1. Navigate to `http://localhost:8080/import`
2. Upload your Open WebUI SQLite database
3. Optionally enable "Dry Run" to preview without storing
4. Click "Start Import"

The importer will:
- Extract all conversations
- Store them as conversation turns
- Automatically extract atomic notes in the background
- Build relationships between notes

## Using Mnemosyne

### DevTools (Testing Interface)

Navigate to `http://localhost:8080/devtools` to test memory operations:

1. **Store Conversations**: Enter user/assistant messages to create conversation turns
2. **Search**: Test semantic search with different queries and thresholds
3. **View Metrics**: See latency and performance in real-time

Use the "Load Sample Data" button for quick testing.

### Atomic Notes (Knowledge Graph)

Navigate to `http://localhost:8080/notes` to:

- View extracted atomic facts from conversations
- Filter by note type (preferences, skills, interests, etc.)
- Search notes by content
- Sort by importance score or confidence
- Delete incorrect notes
- See relationship counts

**Note Types:**
- `preference:ui` - UI/UX preferences
- `preference:editor` - Editor/IDE preferences
- `preference:tool` - Tool preferences
- `skill:programming` - Programming skills
- `interest:topic` - Topic interests
- `personal:location` - Location information
- `goal:career` - Career goals

## Architecture Deep Dive

### Memory Lifecycle

1. **Storage**: Conversations are stored with embeddings (via API or MCP)
2. **Extraction**: Background tasks extract atomic notes using LLM (~15 min delay)
3. **Relationships**: System builds knowledge graph by linking related notes
4. **Retrieval**: Semantic search finds relevant memories
5. **Context**: Memories are provided to AI through MCP tools

### Atomic Notes & Knowledge Graph

Based on [A-MEM research (NeurIPS 2025)](https://arxiv.org/abs/2502.12110):

- **Atomic Facts**: Each note is a single, discrete piece of knowledge
- **Rich Metadata**: Includes context, tags, confidence, importance scores
- **Dynamic Graph**: Notes are linked by relationships (related_to, contradicts, refines, etc.)
- **Importance Scoring**: Based on confidence + relationship strength

### Search Modes

**Fast Mode** (100-300ms):
- Direct vector similarity search
- Returns conversation turns or atomic notes
- Best for real-time queries

**Deep Mode** (500-1500ms):
- Multi-tier search across conversations and notes
- LLM-powered synthesis of findings
- Best for complex queries requiring context

## Local Development (Non-Docker)

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL
- Qdrant
- Redis

### Backend Setup
```bash
# Start dependencies
docker run -d -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant
docker run --name postgres -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=mnemosyne -p 5432:5432 -d postgres:15
docker run -d -p 6379:6379 redis:7

# Setup Python environment
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
export DATABASE_URL="postgresql://postgres:dev@localhost:5432/mnemosyne"
export QDRANT_HOST=localhost
export QDRANT_PORT=6333
export REDIS_URL="redis://localhost:6379/0"
export SECRET_KEY="your-secret-key-here"
export DEBUG=true

# Initialize database
python manage.py migrate

# Start Django-Q worker (for background tasks)
python manage.py qcluster &

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

### MCP Server Setup
```bash
# For stdio transport (Claude Desktop, Cursor, etc.)
./scripts/start_mcp_stdio.sh

# For HTTP transport (Open WebUI, Home Assistant, etc.)
./scripts/start_mcp_http.sh
```

## Testing

Run the test suite:

```bash
docker exec mnemosyne_app python manage.py test memories.tests
```

**Test Coverage**: 56/56 tests passing (100%)

Test files:
- `test_settings.py` - Settings model & API (15 tests)
- `test_llm_service.py` - LLM service configuration (9 tests)
- `test_extraction.py` - Extraction pipeline (11 tests)
- `test_relationships.py` - Relationship building (13 tests)
- `test_integration.py` - End-to-end flows (8 tests)

## API Documentation

### Conversation API

- `POST /api/conversations/store/` - Store conversation turn
- `POST /api/conversations/search/` - Semantic search (fast/deep modes)
- `GET /api/conversations/list/` - List recent conversations

### Atomic Notes API

- `GET /api/notes/list/` - List notes with filters, search, pagination
- `GET /api/notes/get/?note_id=<id>` - Get note with relationships
- `DELETE /api/notes/delete/` - Delete note
- `GET /api/notes/types/` - Get note types with counts
- `POST /api/notes/extract/` - Manually trigger extraction

### Settings API

- `GET /api/settings/` - Get current settings
- `PUT /api/settings/update/` - Update settings
- `POST /api/settings/validate-endpoint/` - Test LLM endpoint
- `POST /api/settings/fetch-models/` - Get available models

### Import API

- `POST /api/import/start/` - Start import task
- `GET /api/import/progress/?task_id=<id>` - Poll import progress
- `POST /api/import/cancel/?task_id=<id>` - Cancel import

## Configuration

All settings are managed through the database and editable via the Settings UI:

**Embeddings Configuration:**
- Provider (ollama, openai, openai_compatible)
- Endpoint URL
- Model name
- API key
- Timeout

**Generation Configuration:**
- Provider (falls back to embeddings if not set)
- Endpoint URL
- Model name
- API key
- Temperature (recommended: 0.6-0.8 for Qwen, 0.7 for Llama, 0.6 for GPT)
- Max tokens (default: 2048)
- Timeout

**Custom Prompts:**
- Extraction prompt (for extracting atomic notes)
- Relationship prompt (for building knowledge graph)

## Project Structure

```
mnemosyne/
├── backend/              # Django backend
│   ├── memories/         # Main app
│   │   ├── models.py     # Data models
│   │   ├── views.py      # API endpoints
│   │   ├── tasks.py      # Background tasks
│   │   ├── conversation_service.py
│   │   ├── llm_service.py
│   │   ├── vector_service.py
│   │   ├── graph_service.py
│   │   └── tests/        # Test suite
│   ├── memory_service/   # Django project
│   └── mcp_server_fastmcp.py  # FastMCP server (dual transport)
├── frontend/             # React frontend
│   └── src/
│       ├── pages/        # UI pages
│       └── services/     # API client
├── scripts/              # Utility scripts
│   ├── start_mcp_stdio.sh   # Start MCP server (stdio transport)
│   ├── start_mcp_http.sh    # Start MCP server (HTTP transport)
│   └── test_*.py            # Integration tests
└── docs/                 # Documentation
```

## License

This project is licensed under the MIT License.
