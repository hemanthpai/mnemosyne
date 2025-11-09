#!/usr/bin/env bash
#
# Start Mnemosyne MCP Server (Streamable HTTP transport)
#
# For: Open WebUI, Home Assistant, web clients
#
# Usage:
#   ./scripts/start_mcp_http.sh [--host HOST] [--port PORT]
#
# Examples:
#   ./scripts/start_mcp_http.sh                    # Default: 0.0.0.0:3000
#   ./scripts/start_mcp_http.sh --port 8080        # Custom port
#   ./scripts/start_mcp_http.sh --host localhost   # Localhost only
#

set -e

# Default values
HOST="0.0.0.0"
PORT="3000"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 [--host HOST] [--port PORT]"
            exit 1
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Activate virtual environment if it exists
if [ -d "$PROJECT_ROOT/venv" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Change to backend directory
cd "$PROJECT_ROOT/backend"

echo "Starting Mnemosyne MCP Server (HTTP) on $HOST:$PORT..."
echo "Compatible with: Open WebUI, Home Assistant, web clients"
echo "Press Ctrl+C to stop"
echo ""

# Start MCP server with HTTP transport
exec python3 mcp_server_fastmcp.py --transport http --host "$HOST" --port "$PORT"
