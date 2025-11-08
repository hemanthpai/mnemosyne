#!/usr/bin/env bash
#
# Start Mnemosyne MCP Server
#
# Usage:
#   ./scripts/start_mcp_server.sh
#
# For Claude Desktop:
#   Configure in Claude Desktop settings -> Developer -> MCP Servers
#   Add the claude_desktop_config.json configuration
#

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Activate virtual environment if it exists
if [ -d "$PROJECT_ROOT/venv" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Change to backend directory
cd "$PROJECT_ROOT/backend"

# Start MCP server
echo "Starting Mnemosyne MCP Server..."
echo "Press Ctrl+C to stop"
echo ""

python3 mcp_server.py
