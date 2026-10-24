#!/usr/bin/env bash
# Starts the MCP server over stdio. A client starts it by SSH: ssh -T deploy@<server> /home/deploy/studio-mcp/run.sh
# Add STUDIO_MCP_WRITE=1 (ssh -T deploy@<server> env STUDIO_MCP_WRITE=1 /home/deploy/studio-mcp/run.sh) to also offer hold, release, run-a-pass and backup.
cd "$(dirname "$0")" || exit 1
exec venv/bin/python server.py
