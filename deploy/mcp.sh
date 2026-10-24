#!/usr/bin/env bash
# Install or update the MCP server on the server host (outside the studio containers; it does not touch them).
#   STUDIO_VPS=deploy@your.host deploy/mcp.sh
set -euo pipefail
: "${STUDIO_VPS:?set STUDIO_VPS=user@host}"
cd "$(dirname "$0")/.."
ssh "$STUDIO_VPS" 'mkdir -p ~/studio-mcp && chmod 700 ~/studio-mcp'
scp -q studio_mcp/gateway.py studio_mcp/server.py studio_mcp/run.sh studio_mcp/requirements.txt "$STUDIO_VPS:studio-mcp/"
ssh "$STUDIO_VPS" 'cd ~/studio-mcp && chmod 700 run.sh && { [ -d venv ] || python3 -m venv venv; } && venv/bin/pip install -q -r requirements.txt && venv/bin/python -c "import mcp, importlib.metadata as m; print(\"mcp\", m.version(\"mcp\"))"'
echo "MCP server installed in ~/studio-mcp. Read-only client command:  ssh -T $STUDIO_VPS /home/deploy/studio-mcp/run.sh"
