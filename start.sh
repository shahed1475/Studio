#!/usr/bin/env bash
# Starts the dashboard and opens it at an easy address.
cd "$(dirname "$0")"
(sleep 1.5; xdg-open "http://studio.localhost:8913" >/dev/null 2>&1) &
exec .venv/bin/python dashboard.py
