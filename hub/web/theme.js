// Runs in <head> before first paint so the page never flashes the wrong theme. A saved choice wins; otherwise the system setting decides (the CSS handles that case).
try { var t = localStorage.getItem("hub_theme"); if (t === "light" || t === "dark") document.documentElement.dataset.theme = t; } catch (e) { /* storage blocked: system setting applies */ }
