import os

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:3000")
MCP_PORT = int(os.environ.get("MCP_PORT", "8080"))
