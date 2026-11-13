/* Small SVG chart helpers shared by the project decks and demos. No dependencies. */
const MM = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const INK = "#0f172a", MUTED = "#64748b", GRID = "#e2e8f0", BASE = "#94a3b8";
  const C = { context: "#b9c3d0", focus: "#1f3a5f", accent: "#d9731a", series: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"] };

  function el(tag, attrs, parent, text) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  let tipEl;
  function tip(html, evt) {
    if (!tipEl) {
      tipEl = document.createElement("div");
      tipEl.style.cssText = "position:fixed;pointer-events:none;background:#0f1e33;color:#fff;font:12px/1.45 Inter,system-ui,sans-serif;padding:8px 10px;border-radius:6px;box-shadow:0 6px 18px rgba(0,0,0,.25);z-index:50;max-width:240px;display:none";
      document.body.appendChild(tipEl);
    }
    if (!html) { tipEl.style.display = "none"; return; }
    tipEl.innerHTML = html;
    tipEl.style.display = "block";
    const w = tipEl.offsetWidth, x = Math.min(evt.clientX + 14, window.innerWidth - w - 8);
    tipEl.style.left = x + "px";
    tipEl.style.top = (evt.clientY + 14) + "px";
  }
  function ticks(lo, hi, n) {
    const span = hi - lo, step0 = Math.pow(10, Math.floor(Math.log10(span / n)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * step0).find(s => span / s <= n) || step0 * 10;
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Math.round(v / step) * step);
    return out;
  }
  function svgIn(target, w, h) {
    const host = typeof target === "string" ? document.querySelector(target) : target;
    host.innerHTML = "";
    const s = el("svg", { viewBox: `0 0 ${w} ${h}`, width: "100%", role: "img", style: "display:block;font-family:Inter,system-ui,sans-serif" }, host);
    return s;
  }

  /* Vertical bars. data: [{label, value, lo, hi, color, tip}] */
  function bars(target, o) {
    const w = o.width || 640, h = o.height || 320, m = { t: 26, r: 12, b: o.xTitle ? 52 : 34, l: 54 };
    const s = svgIn(target, w, h), fmt = o.fmt || (v => v);
    const vals = o.data.flatMap(d => [d.value, d.lo ?? d.value, d.hi ?? d.value, 0]);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.12; hi += pad; if (lo < 0) lo -= pad;
    const y = v => m.t + (hi - v) / (hi - lo) * (h - m.t - m.b);
    const bw = (w - m.l - m.r) / o.data.length, barW = Math.min(bw - 2, o.maxBar || 56);
    ticks(lo, hi, 5).forEach(t => {
      el("line", { x1: m.l, x2: w - m.r, y1: y(t), y2: y(t), stroke: t === 0 ? BASE : GRID, "stroke-width": 1 }, s);
      el("text", { x: m.l - 8, y: y(t) + 4, "text-anchor": "end", "font-size": 11, fill: MUTED }, s, fmt(t));
    });
    o.data.forEach((d, i) => {
      const cx = m.l + bw * (i + 0.5), x0 = cx - barW / 2, y0 = y(0), y1 = y(d.value), r = Math.min(4, Math.abs(y1 - y0));
      const up = d.value >= 0;
      const path = up
        ? `M${x0},${y0}V${y1 + r}Q${x0},${y1} ${x0 + r},${y1}H${x0 + barW - r}Q${x0 + barW},${y1} ${x0 + barW},${y1 + r}V${y0}Z`
        : `M${x0},${y0}V${y1 - r}Q${x0},${y1} ${x0 + r},${y1}H${x0 + barW - r}Q${x0 + barW},${y1} ${x0 + barW},${y1 - r}V${y0}Z`;
      const bar = el("path", { d: path, fill: d.color || C.context }, s);
      if (d.lo !== undefined) {
        el("line", { x1: cx, x2: cx, y1: y(d.lo), y2: y(d.hi), stroke: INK, "stroke-width": 1.25 }, s);
        [d.lo, d.hi].forEach(v => el("line", { x1: cx - 4, x2: cx + 4, y1: y(v), y2: y(v), stroke: INK, "stroke-width": 1.25 }, s));
      }
      const top = d.hi !== undefined ? (up ? y(d.hi) : y(d.lo)) : y1;
      el("text", { x: cx, y: up ? top - 6 : top + 14, "text-anchor": "middle", "font-size": 11.5, "font-weight": 600, fill: INK }, s, fmt(d.value));
      const lab = String(d.label).split("\n");
      lab.forEach((t, k) => el("text", { x: cx, y: h - m.b + 16 + k * 13, "text-anchor": "middle", "font-size": 11, fill: MUTED }, s, t));
      const hit = el("rect", { x: cx - bw / 2, y: m.t, width: bw, height: h - m.t - m.b, fill: "transparent" }, s);
      hit.addEventListener("mousemove", e => { bar.setAttribute("opacity", 0.8); tip(d.tip || `<b>${lab.join(" ")}</b><br>${fmt(d.value)}`, e); });
      hit.addEventListener("mouseleave", () => { bar.setAttribute("opacity", 1); tip(); });
    });
    if (o.xTitle) el("text", { x: (m.l + w - m.r) / 2, y: h - 6, "text-anchor": "middle", "font-size": 11.5, fill: MUTED }, s, o.xTitle);
    if (o.yTitle) el("text", { x: 4, y: 12, "font-size": 11.5, fill: MUTED }, s, o.yTitle);
  }

  /* Horizontal bars. data: [{label, value, color, tip}] */
  function hbars(target, o) {
    const w = o.width || 640, row = o.row || 30, m = { t: 6, r: 56, b: 6, l: o.labelWidth || 220 };
    const h = m.t + m.b + row * o.data.length, s = svgIn(target, w, h), fmt = o.fmt || (v => v);
    const max = Math.max(...o.data.map(d => d.value));
    o.data.forEach((d, i) => {
      const yy = m.t + row * i, bh = Math.min(16, row - 8), len = Math.max(2, d.value / max * (w - m.l - m.r));
      el("text", { x: m.l - 10, y: yy + row / 2 + 4, "text-anchor": "end", "font-size": 12, fill: INK }, s, d.label);
      const bar = el("path", { d: `M${m.l},${yy + (row - bh) / 2}h${len - 4}q4,0 4,4v${bh - 8}q0,4 -4,4h${-(len - 4)}z`, fill: d.color || C.focus }, s);
      el("text", { x: m.l + len + 6, y: yy + row / 2 + 4, "font-size": 11.5, "font-weight": 600, fill: INK }, s, fmt(d.value));
      const hit = el("rect", { x: 0, y: yy, width: w, height: row, fill: "transparent" }, s);
      hit.addEventListener("mousemove", e => { bar.setAttribute("opacity", 0.8); tip(d.tip || `<b>${d.label}</b><br>${fmt(d.value)}`, e); });
      hit.addEventListener("mouseleave", () => { bar.setAttribute("opacity", 1); tip(); });
    });
  }

  /* Lines. series: [{name, color, points: [[x, y], ...]}]; one shared y axis. */
  function lines(target, o) {
    const w = o.width || 640, h = o.height || 320, m = { t: 34, r: o.rightPad || 150, b: 44, l: 58 };
    const s = svgIn(target, w, h), xf = o.xFmt || (v => v), yf = o.yFmt || (v => v);
    const xs = o.series[0].points.map(p => p[0]);
    const all = o.series.flatMap(q => q.points.map(p => p[1]))
      .concat(o.band ? o.band.lo.concat(o.band.hi) : [])
      .concat(o.zeroBase === false ? [] : [0]);
    let lo = Math.min(...all), hi = Math.max(...all); const pad = (hi - lo) * 0.1; hi += pad; if (lo < 0) lo -= pad;
    const x = v => m.l + (v - xs[0]) / (xs[xs.length - 1] - xs[0]) * (w - m.l - m.r);
    const y = v => m.t + (hi - v) / (hi - lo) * (h - m.t - m.b);
    // an expected range, drawn behind everything else
    if (o.band) {
      const pts = xs.map((v, i) => [x(v), y(o.band.hi[i])]).concat(xs.map((v, i) => [x(v), y(o.band.lo[i])]).reverse());
      const usable = pts.every(p => isFinite(p[0]) && isFinite(p[1]));
      if (usable) el("path", { d: pts.map((p, i) => (i ? "L" : "M") + p[0] + "," + p[1]).join("") + "Z",
                               fill: o.bandColor || "#e8eef6", stroke: "none" }, s);
    }
    ticks(lo, hi, 5).forEach(t => {
      el("line", { x1: m.l, x2: w - m.r, y1: y(t), y2: y(t), stroke: t === 0 ? BASE : GRID }, s);
      el("text", { x: m.l - 8, y: y(t) + 4, "text-anchor": "end", "font-size": 11, fill: MUTED }, s, yf(t));
    });
    ticks(xs[0], xs[xs.length - 1], 6).forEach(t => el("text", { x: x(t), y: h - m.b + 16, "text-anchor": "middle", "font-size": 11, fill: MUTED }, s, xf(t)));
    if (o.xTitle) el("text", { x: (m.l + w - m.r) / 2, y: h - 6, "text-anchor": "middle", "font-size": 11.5, fill: MUTED }, s, o.xTitle);
    if (o.yTitle) el("text", { x: 4, y: 12, "font-size": 11.5, fill: MUTED }, s, o.yTitle);
    const ends = o.series.map((q, i) => ({ i, y: y(q.points[q.points.length - 1][1]) })).sort((a, b) => a.y - b.y);
    for (let k = 1; k < ends.length; k++) if (ends[k].y - ends[k - 1].y < 14) ends[k].y = ends[k - 1].y + 14;   // keep end labels apart
    o.series.forEach((q, i) => {
      const col = q.color || C.series[i];
      el("path", { d: q.points.map((p, k) => (k ? "L" : "M") + x(p[0]) + "," + y(p[1])).join(""), fill: "none", stroke: col, "stroke-width": 2, "stroke-linejoin": "round" }, s);
      if (q.mark) q.points.forEach((p, k) => { if (q.mark[k]) el("circle", { cx: x(p[0]), cy: y(p[1]), r: 5,
        fill: C.accent, stroke: "#fff", "stroke-width": 2 }, s); });
      const ly = ends.find(e => e.i === i).y, last = q.points[q.points.length - 1];
      el("circle", { cx: x(last[0]), cy: y(last[1]), r: 4, fill: col, stroke: "#fff", "stroke-width": 2 }, s);
      el("line", { x1: w - m.r + 8, x2: w - m.r + 20, y1: ly, y2: ly, stroke: col, "stroke-width": 3 }, s);
      el("text", { x: w - m.r + 26, y: ly + 4, "font-size": 11.5, fill: INK }, s, q.name);
    });
    const mark = el("line", { y1: m.t, y2: h - m.b, stroke: INK, "stroke-width": 1, "stroke-dasharray": "3 3", visibility: "hidden" }, s);
    const fixed = o.mark !== undefined ? el("line", { x1: x(o.mark), x2: x(o.mark), y1: m.t, y2: h - m.b, stroke: MUTED, "stroke-width": 1.5 }, s) : null;
    if (fixed && o.markLabel) el("text", { x: x(o.mark), y: m.t - 8, "text-anchor": "middle", "font-size": 11, fill: MUTED }, s, o.markLabel);
    const hit = el("rect", { x: m.l, y: m.t, width: w - m.l - m.r, height: h - m.t - m.b, fill: "transparent" }, s);
    hit.addEventListener("mousemove", e => {
      const box = s.getBoundingClientRect(), px = (e.clientX - box.left) / box.width * w;
      const k = xs.reduce((b, v, j) => Math.abs(x(v) - px) < Math.abs(x(xs[b]) - px) ? j : b, 0);
      mark.setAttribute("x1", x(xs[k])); mark.setAttribute("x2", x(xs[k])); mark.setAttribute("visibility", "visible");
      tip(`<b>${xf(xs[k])}</b><br>` + o.series.map((q, i) => `<span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:${q.color || C.series[i]};margin-right:6px"></span>${q.name}: ${yf(q.points[k][1])}`).join("<br>"), e);
    });
    hit.addEventListener("mouseleave", () => { mark.setAttribute("visibility", "hidden"); tip(); });
  }

  /* Forest plot: estimate with interval per row, optional reference marker. data: [{label, value, lo, hi, ref, tip}] */
  function forest(target, o) {
    const w = o.width || 640, row = o.row || 24, m = { t: 22, r: 16, b: o.xTitle ? 44 : 26, l: o.labelWidth || 230 };
    const h = m.t + m.b + row * o.data.length, s = svgIn(target, w, h), fmt = o.fmt || (v => v.toFixed(2));
    const all = o.data.flatMap(d => [d.lo, d.hi, d.ref ?? 0, 0]);
    let lo = Math.min(...all), hi = Math.max(...all); const pad = (hi - lo) * 0.06; lo -= pad; hi += pad;
    const x = v => m.l + (v - lo) / (hi - lo) * (w - m.l - m.r);
    ticks(lo, hi, 6).forEach(t => {
      el("line", { x1: x(t), x2: x(t), y1: m.t, y2: h - m.b, stroke: t === 0 ? BASE : GRID }, s);
      el("text", { x: x(t), y: h - m.b + 15, "text-anchor": "middle", "font-size": 11, fill: MUTED }, s, fmt(t));
    });
    o.data.forEach((d, i) => {
      const cy = m.t + row * (i + 0.5);
      el("text", { x: m.l - 10, y: cy + 4, "text-anchor": "end", "font-size": 11.5, fill: INK }, s, d.label);
      el("line", { x1: x(d.lo), x2: x(d.hi), y1: cy, y2: cy, stroke: C.focus, "stroke-width": 2 }, s);
      const dot = el("circle", { cx: x(d.value), cy, r: 4.5, fill: C.focus, stroke: "#fff", "stroke-width": 2 }, s);
      if (d.ref !== undefined) el("path", { d: `M${x(d.ref)},${cy - 7}l5,7l-5,7l-5,-7z`, fill: "none", stroke: C.accent, "stroke-width": 2 }, s);
      const hit = el("rect", { x: 0, y: cy - row / 2, width: w, height: row, fill: "transparent" }, s);
      hit.addEventListener("mousemove", e => { dot.setAttribute("r", 6); tip(d.tip || `<b>${d.label}</b><br>Estimate ${fmt(d.value)} (${fmt(d.lo)} to ${fmt(d.hi)})` + (d.ref !== undefined ? `<br>True ${fmt(d.ref)}` : ""), e); });
      hit.addEventListener("mouseleave", () => { dot.setAttribute("r", 4.5); tip(); });
    });
    if (o.legend) {
      el("circle", { cx: m.l + 6, cy: 9, r: 4.5, fill: C.focus }, s);
      el("text", { x: m.l + 16, y: 13, "font-size": 11.5, fill: INK }, s, o.legend[0]);
      const lx = m.l + 26 + o.legend[0].length * 6.4;
      el("path", { d: `M${lx},2l5,7l-5,7l-5,-7z`, fill: "none", stroke: C.accent, "stroke-width": 2 }, s);
      el("text", { x: lx + 11, y: 13, "font-size": 11.5, fill: INK }, s, o.legend[1]);
    }
    if (o.xTitle) el("text", { x: (m.l + w - m.r) / 2, y: h - 4, "text-anchor": "middle", "font-size": 11.5, fill: MUTED }, s, o.xTitle);
  }

  const cad = v => (v < 0 ? "-$" : "$") + Math.abs(Math.round(v)).toLocaleString("en-CA");
  const cadK = v => (v < 0 ? "-$" : "$") + Math.abs(v / 1000).toFixed(0) + "k";
  const pct = (v, d = 1) => (v * 100).toFixed(d) + "%";
  return { bars, hbars, lines, forest, C, cad, cadK, pct };
})();
