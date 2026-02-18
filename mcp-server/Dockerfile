FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project
COPY src ./src
RUN uv sync --no-dev

ENV BACKEND_URL=http://backend:3000
ENV MCP_PORT=8080
EXPOSE 8080

CMD ["uv", "run", "mnemosyne-mcp"]
