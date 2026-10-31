"""My Downloads: save the owner's own YouTube videos to a folder on the Desktop.

A small app that runs on the owner's own computer (not on the server). The dashboard has a page with a button that opens it.
Plan and limits: docs/superpowers/plans/2026-10-31-my-downloads.md. Only videos of channels the owner lists as their own are ever downloaded.
"""

HOST = "127.0.0.1"
PORT = 8923
ADDRESS = f"http://{HOST}:{PORT}"
