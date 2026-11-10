// The agent constellation: seven agents as stars, the real hand-offs between them as lines, and small lights travelling along the lines as they pass work on.
// It is an illustration of how the agents talk; only the concierge is ever driven by a real request (ping). It stops when off screen or when the tab is hidden,
// draws one still frame under prefers-reduced-motion, and caps the pixel ratio at 2.
const AGENTS = [
  { id: "concierge", name: "Concierge", x: 0.17, y: 0.30, r: 6.5 }, { id: "researcher", name: "Researcher", x: 0.43, y: 0.13, r: 4.5 },
  { id: "strategist", name: "Strategist", x: 0.72, y: 0.21, r: 4.5 }, { id: "scriptwriter", name: "Scriptwriter", x: 0.86, y: 0.43, r: 4.5 },
  { id: "reviewer", name: "Reviewer", x: 0.52, y: 0.60, r: 5 }, { id: "producer", name: "Producer", x: 0.25, y: 0.74, r: 4.5 }, { id: "publisher", name: "Publisher", x: 0.58, y: 0.87, r: 4.5 },
];
const EDGES = [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [4, 3], [2, 4]]; // concierge to researcher to strategist to scriptwriter to reviewer to producer to publisher, with revisions back
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;

export function mountSky(box, { labels = true } = {}) {
  const canvas = box.querySelector("canvas"), ctx = canvas.getContext("2d");
  const stars = Array.from({ length: 150 }, () => ({ x: Math.random(), y: Math.random(), s: Math.random() * 1.2 + 0.3, p: Math.random() * 6.28 }));
  const glow = Object.fromEntries(AGENTS.map((a) => [a.id, 0]));
  const rings = [];
  let pulses = [], W = 0, H = 0, dpr = 1, col = {}, raf = 0, visible = true, last = 0, nextPulse = 0, px = 0, py = 0, tx = 0, ty = 0, hover = -1;

  const readColors = () => { const s = getComputedStyle(document.documentElement); col = { moon: s.getPropertyValue("--moon").trim(), mist: s.getPropertyValue("--mist").trim(), lantern: s.getPropertyValue("--lantern").trim(), edge: s.getPropertyValue("--edge").trim() }; };
  const size = () => { const r = box.getBoundingClientRect(); dpr = Math.min(window.devicePixelRatio || 1, 2); W = r.width; H = r.height; canvas.width = W * dpr; canvas.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); };
  const P = (a) => ({ x: a.x * W + px, y: a.y * H + py });
  const ctl = (i) => { const [a, b] = EDGES[i], A = P(AGENTS[a]), B = P(AGENTS[b]), mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2, dx = B.x - A.x, dy = B.y - A.y, k = (i % 2 ? 1 : -1) * 0.14; return { A, B, c: { x: mx - dy * k, y: my + dx * k } }; };
  const at = (e, t) => { const u = 1 - t; return { x: u * u * e.A.x + 2 * u * t * e.c.x + t * t * e.B.x, y: u * u * e.A.y + 2 * u * t * e.c.y + t * t * e.B.y }; };
  const withAlpha = (c, a) => { const ctxc = document.createElement("canvas").getContext("2d"); ctxc.fillStyle = c; const v = ctxc.fillStyle; if (v[0] === "#") { const n = parseInt(v.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; } return v.replace("rgb(", "rgba(").replace(")", `,${a})`); };
  const alphaCache = new Map(); const A = (c, a) => { const k = c + a; if (!alphaCache.has(k)) alphaCache.set(k, withAlpha(c, a)); return alphaCache.get(k); };

  function frame(now) {
    raf = 0; if (!visible || document.hidden) return;
    const dt = Math.min((now - last) / 1000 || 0.016, 0.05); last = now;
    px += (tx - px) * 0.06; py += (ty - py) * 0.06;
    ctx.clearRect(0, 0, W, H);
    for (const s of stars) { const tw = reduce ? 0.6 : 0.45 + 0.35 * Math.sin(now / 1100 + s.p); ctx.fillStyle = A(col.moon, (0.12 + tw * 0.35).toFixed(2)); ctx.beginPath(); ctx.arc(s.x * W + px * 0.3, s.y * H + py * 0.3, s.s, 0, 6.283); ctx.fill(); }
    ctx.lineWidth = 1; EDGES.forEach((_, i) => { const e = ctl(i); ctx.strokeStyle = A(col.edge, "0.9"); ctx.beginPath(); ctx.moveTo(e.A.x, e.A.y); ctx.quadraticCurveTo(e.c.x, e.c.y, e.B.x, e.B.y); ctx.stroke(); });
    if (!reduce && now > nextPulse && pulses.length < 3) { pulses.push({ edge: Math.floor(Math.random() * EDGES.length), t: 0, dur: 1.5 + Math.random() * 1.1 }); nextPulse = now + 650 + Math.random() * 900; }
    pulses = pulses.filter((p) => {
      p.t += dt / p.dur; const e = ctl(p.edge);
      for (let k = 0; k < 7; k++) { const tt = Math.max(0, p.t - k * 0.025); const q = at(e, Math.min(tt, 1)); ctx.fillStyle = A(col.lantern, (0.85 - k * 0.12).toFixed(2)); ctx.beginPath(); ctx.arc(q.x, q.y, 2.6 - k * 0.25, 0, 6.283); ctx.fill(); }
      if (p.t >= 1) { glow[AGENTS[EDGES[p.edge][1]].id] = 1; return false; } return true;
    });
    AGENTS.forEach((a, i) => {
      const q = P(a); glow[a.id] = Math.max(0, glow[a.id] - dt * 0.9);
      const g = glow[a.id] + (hover === i ? 0.5 : 0), rr = a.r * (1 + g * 0.5);
      const halo = ctx.createRadialGradient(q.x, q.y, 0, q.x, q.y, rr * 6); halo.addColorStop(0, A(col.lantern, (0.18 + g * 0.3).toFixed(2))); halo.addColorStop(1, A(col.lantern, "0"));
      ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(q.x, q.y, rr * 6, 0, 6.283); ctx.fill();
      ctx.fillStyle = i === 0 || g > 0.2 ? col.lantern : col.moon; ctx.beginPath(); ctx.arc(q.x, q.y, rr, 0, 6.283); ctx.fill();
      if (labels) { ctx.font = `500 ${W < 360 ? 11 : 12.5}px Geist, system-ui, sans-serif`; ctx.fillStyle = g > 0.2 ? col.moon : col.mist; ctx.textAlign = a.x > 0.75 ? "right" : "left"; ctx.fillText(a.name, q.x + (a.x > 0.75 ? -12 : 12), q.y + 4.5); }
    });
    for (let i = rings.length - 1; i >= 0; i--) { const r = rings[i]; r.t += dt / 1.4; if (r.t >= 1) { rings.splice(i, 1); continue; } const q = P(AGENTS[r.i]); ctx.strokeStyle = A(col.lantern, (0.7 * (1 - r.t)).toFixed(2)); ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(q.x, q.y, 8 + r.t * 46, 0, 6.283); ctx.stroke(); }
    if (!reduce || rings.length) raf = requestAnimationFrame(frame);
  }
  const run = () => { if (!raf) { last = performance.now(); raf = requestAnimationFrame(frame); } };

  readColors(); size();
  new ResizeObserver(() => { size(); run(); }).observe(box);
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) run(); }).observe(box);
  document.addEventListener("visibilitychange", run);
  window.addEventListener("themechange", () => { readColors(); alphaCache.clear(); run(); });
  if (!reduce) box.addEventListener("pointermove", (e) => {
    const r = box.getBoundingClientRect(); tx = ((e.clientX - r.left) / r.width - 0.5) * -16; ty = ((e.clientY - r.top) / r.height - 0.5) * -16;
    hover = AGENTS.findIndex((a) => Math.hypot(a.x * W + px - (e.clientX - r.left), a.y * H + py - (e.clientY - r.top)) < 26);
  });
  box.addEventListener("pointerleave", () => { tx = ty = 0; hover = -1; });
  if (document.fonts) document.fonts.ready.then(run);
  run();
  return { ping(id) { const i = AGENTS.findIndex((a) => a.id === id); if (i >= 0) { glow[id] = 1; rings.push({ i, t: 0 }); run(); } } };
}
