# Vendored: /watch (claude-video)

- Source: https://github.com/rroledo/claude-video-skills at commit 0be1933 (MIT, Bradley Bonanno; upstream bradautomates/claude-video).
- Reviewed before install: the only network calls are the optional Whisper uploads (Groq/OpenAI, only if a key is set in `~/.config/watch/.env`) and yt-dlp for URLs. No eval, shell=True, curl or credential reads beyond that file.
- Installed by copying, not through the plugin marketplace, so it never auto-updates. The plugin's SessionStart hook is not installed.
- Studio use: LOCAL files only (`/watch output/<slug>/video.mp4`). Do not set a Whisper key for studio videos and do not use yt-dlp on other people's videos.
- To update: re-read the diff of the upstream commit, then copy again.
