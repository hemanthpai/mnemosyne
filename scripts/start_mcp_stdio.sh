#!/usr/bin/env bash
#
# Start Mnemosyne MCP Server (stdio transport)
#
# For: Claude Desktop, Cursor, Cline, Continue (local clients)
#
# Usage:
#   ./scripts/start_mcp_stdio.sh
#
# Claude Desktop Configuration:
#   Add to ~/.config/Claude/claude_desktop_config.json:
#   {
#     "mcpServers": {
#       "mnemosyne": {
#         "command": "/path/to/mnemosyne/scripts/start_mcp_stdio.sh"
#       }
#     }
#   }
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

# Start MCP server with stdio transport
exec python3 mcp_server_fastmcp.py --transport stdio
