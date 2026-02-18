# Mnemosyne Development Rules

## Architecture

- **Backend**: Node.js 22 + TypeScript + Fastify v5
- **MCP Server**: Python 3.12 + official Anthropic MCP SDK
- **Frontend**: React (future)
- **Infrastructure**: Docker + docker-compose

## Development Principles

1. **Build incrementally, test often** - Every component gets tests before moving on
2. **App factory pattern** - Backend uses `app.ts` (factory) separate from `index.ts` (entry) for testability
3. **Docker-based integration testing** - Integration tests run in containers via docker-compose
4. **Don't assume, clarify** - When requirements are ambiguous, ask

## Code Standards

### TypeScript (Backend)
- Strict mode enabled
- ES2022 target, Node16 module resolution
- Use Fastify's type system for route schemas
- Tests with Vitest v3, using Fastify's `inject()` for HTTP testing

### Python (MCP Server)
- Python 3.12+
- Use `uv` for package management
- httpx for async HTTP calls
- Tests with pytest, mock external HTTP calls

## Testing Strategy

- **Unit tests**: Run locally, fast, no external dependencies
- **Integration tests**: Run in Docker, test real service communication
- **Test command (backend)**: `npm test`
- **Test command (MCP)**: `uv run pytest`
- **Integration tests**: `docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from test-runner`

## MCP Server

- Dual transport: stdio (local/Claude Desktop) + streamable-http (Docker/networked)
- All backend communication via httpx.AsyncClient
- Configuration via environment variables

## API Conventions

- RESTful routes under `/api/`
- Health check at `GET /health`
- JSON request/response bodies
- Proper HTTP status codes (201 for creation, 400 for validation errors)
