# Watching the studio from your own computer

Nothing here opens a public port. Both ways listen on 127.0.0.1 (your computer only). Run the commands in a terminal on your PC.

## A. The live studio on the server (what is really happening)
The server's dashboard listens on the server's own loopback (127.0.0.1:8913) and on Tailscale. An SSH tunnel brings it to your PC:

    ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -L 127.0.0.1:8913:127.0.0.1:8913 deploy@vps-ai

Leave that terminal open, then open http://127.0.0.1:8913 in your browser and sign in with your dashboard password (type it yourself; nobody else needs it).
The "Right now" page is http://127.0.0.1:8913/now (it exists on the server only after the newest code is deployed: see PROGRESS.md).
Stop: press Ctrl+C in the terminal that runs the tunnel.

## B. A local test copy (your PC's own folder, not the live studio)
Shows the PC's old test videos, nothing from the server. Safe to play with.

    cd ~/Desktop/Youtube-automation && DASH_PORT=8914 .venv/bin/python dashboard.py

Open http://127.0.0.1:8914 (and http://127.0.0.1:8914/now). Stop: Ctrl+C in that terminal.
The dashboard binds to 127.0.0.1 only unless STUDIO_BIND is set (it is not).

## Checked on 25 Oct 2026
- B: started, answered 200 on `/`, `/now` and `/api/now`; a screenshot of `/now` was taken and looked at.
- A: the tunnel opened and the live dashboard answered through it: `/login` 200, `/` 303 to `/login` (so the login protects it). The tunnel was closed again afterwards.
