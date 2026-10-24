/* Carbon Gap — motion film director.
   Injected into the mockup page. Drives the real app on a timeline; the
   recorder advances a fake clock frame by frame, so every animation here
   uses performance.now / requestAnimationFrame / setTimeout. */
(() => {
const W = innerWidth, H = innerHeight;
const at = (s, fn) => setTimeout(fn, s * 1000);
const outC = e => 1 - Math.pow(1 - e, 3);
const io = e => e < .5 ? 4 * e * e * e : 1 - Math.pow(-2 * e + 2, 3) / 2;
const outE = e => e === 1 ? 1 : 1 - Math.pow(2, -10 * e);
function tween(dur, fn, ease = io) {
  return new Promise(res => {
    const s = performance.now();
    (function f() { const p = Math.min(1, (performance.now() - s) / (dur * 1000)); fn(ease(p)); p < 1 ? requestAnimationFrame(f) : res(); })();
  });
}
window.REPORT_STEP_MS = 110;

/* ---------- camera on the whole app ---------- */
const app = document.querySelector('.app');
app.style.transformOrigin = '0 0'; app.style.willChange = 'transform';
let cam = { s: 1, x: 0, y: 0 };
const setCam = c => { cam = c; app.style.transform = `translate(${c.x}px,${c.y}px) scale(${c.s})`; };
const camTo = (t, dur, ease = io) => { const a = { ...cam }; return tween(dur, p => setCam({ s: a.s + (t.s - a.s) * p, x: a.x + (t.x - a.x) * p, y: a.y + (t.y - a.y) * p }), ease); };
function focus(r, s) {
  const cx = r.x + r.w / 2, cy = r.y + r.h / 2;
  let x = W / 2 - cx * s, y = H / 2 - cy * s;
  x = Math.min(0, Math.max(W - W * s, x)); y = Math.min(0, Math.max(H - H * s, y));
  return { s, x, y };
}
const R = sel => { const t = app.style.transform; app.style.transform = ''; const b = document.querySelector(sel).getBoundingClientRect(); app.style.transform = t; return { x: b.x, y: b.y, w: b.width, h: b.height }; };
const rStage = R('#stage'), rSheet = R('#sheet');

/* ---------- overlay ---------- */
const css = `
#film{position:fixed;inset:0;pointer-events:none;z-index:100;font-family:var(--font)}
#film .card{position:absolute;inset:0;background:var(--paper);display:flex;flex-direction:column;justify-content:center;padding:0 180px}
#film h1{font:700 104px/0.98 var(--cond);margin:0;letter-spacing:-.01em;color:var(--ink)}
#film h1 .w{display:inline-block;opacity:0;transform:translateY(40px)}
#film .l2{color:var(--crit)}
#film .st{margin-top:56px;width:1100px}
#film .st text{font:600 22px var(--cond);letter-spacing:.06em;text-transform:uppercase;fill:var(--ink)}
#film .st .num{font:600 26px var(--font);letter-spacing:0;text-transform:none;fill:var(--ink-2)}
#film .st .gapn{font:700 40px var(--cond);fill:var(--crit);letter-spacing:0}
#cap{position:absolute;left:50%;bottom:54px;transform:translateX(-50%);background:var(--shell);color:var(--shell-ink);font:500 34px/1.25 var(--font);padding:14px 28px;border-radius:5px;white-space:nowrap;box-shadow:0 18px 40px -16px rgba(0,0,0,.5);opacity:0}
#cap b{color:var(--g1);font-weight:600}
#cap.top{bottom:auto;top:84px}
#mkt{position:absolute;left:272px;top:96px;width:430px;background:var(--sheet);border:1.5px solid var(--ink);padding:18px 20px;opacity:0;box-shadow:0 18px 40px -18px rgba(28,35,32,.45)}
#mkt h4{margin:0 0 4px;font:700 22px/1 var(--cond);letter-spacing:.05em;text-transform:uppercase}
#mkt .sub{font-size:15px;color:var(--ink-3);margin-bottom:12px}
#mkt .row{display:grid;grid-template-columns:18px 1fr auto auto;gap:12px;align-items:center;padding:7px 0;border-top:1px solid var(--rule);font-size:18px}
#mkt .sw{width:16px;height:12px;border:1px solid var(--ink)}
#mkt .tag{font:700 14px var(--cond);letter-spacing:.08em;text-transform:uppercase;padding:3px 7px;border-radius:3px;color:#fff}
#mkt .v{font-weight:600}
#outro{opacity:0;align-items:flex-start}
#outro .mark{display:flex;align-items:center;gap:26px}
#outro .mark svg{width:150px;height:150px}
#outro h1{font-size:200px}
#outro p{font:500 58px/1.2 var(--font);color:var(--ink-2);margin:26px 0 0;max-width:30ch}
#outro .foot{position:absolute;left:180px;right:180px;bottom:70px;display:flex;justify-content:space-between;font:600 22px var(--cond);letter-spacing:.06em;text-transform:uppercase;color:var(--ink-2);border-top:2px solid var(--ink);padding-top:16px}
`;
const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
const film = document.createElement('div'); film.id = 'film';
const words = (t, cls = '') => t.split(' ').map(w => `<span class="w ${cls}">${w}</span>`).join(' ');
film.innerHTML = `
<div class="card" id="intro">
  <h1>${words('Every country declares its emissions.')}</h1>
  <h1 class="l2">${words('But what do they really emit?', 'l2')}</h1>
  <svg class="st" viewBox="0 0 1100 170">
    <text x="0" y="22">Declared</text><text class="num" id="in-dn" x="0" y="22" text-anchor="end" opacity="0">300 Mt</text>
    <rect id="in-d" x="2" y="36" width="0" height="40" fill="var(--g0)" stroke="var(--ink)" stroke-width="2"/>
    <rect id="in-o" x="2" y="88" width="0" height="40" fill="var(--sea)" stroke="var(--ink)" stroke-width="2"/>
    <rect id="in-g" x="760" y="88" width="0" height="40" fill="url(#hatch-gap)" stroke="var(--crit)" stroke-width="2"/>
    <line id="in-line" x1="762" x2="762" y1="28" y2="136" stroke="var(--ink)" stroke-width="2" stroke-dasharray="5 4" opacity="0"/>
    <text x="0" y="162">Observed</text><text class="gapn" id="in-gn" x="1090" y="164" text-anchor="end" opacity="0">+19.7% gap</text>
  </svg>
</div>
<div id="cap"></div>
<div id="mkt"></div>
<div class="card" id="outro">
  <div class="mark"><svg viewBox="0 0 24 24" fill="none" stroke="var(--ink)" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M2.5 9h19M2.5 15h19"/><path d="M4 15h16" stroke="var(--g2)" stroke-width="3.2"/></svg><h1>Carbon Gap</h1></div>
  <p>The price of carbon deserves a real measure.</p>
  <div class="foot"><span>Built with the OpenAI API</span><span>OpenAI Paris DevDay Community Hackathon</span><span>#parisdevdayhack</span></div>
</div>`;
document.body.appendChild(film);
const $f = s => film.querySelector(s);

/* ---------- captions ---------- */
let capTimer;
function caption(html, dur, pos = 'bottom') {
  const c = $f('#cap'); c.innerHTML = html; c.className = pos === 'top' ? 'top' : '';
  tween(.35, p => { c.style.opacity = p; c.style.transform = `translateX(-50%) translateY(${(1 - p) * 18}px)`; }, outC);
  clearTimeout(capTimer);
  capTimer = setTimeout(() => tween(.25, p => { c.style.opacity = 1 - p; }), dur * 1000);
}
function rise(els, stagger = .07, dur = .55) {
  els.forEach((el, i) => setTimeout(() => tween(dur, p => { el.style.opacity = p; el.style.transform = `translateY(${(1 - p) * 40}px)`; }, outE), i * stagger * 1000));
}

/* ---------- globe helpers ---------- */
let spinning = false;
function spin(speed = 14) { // degrees per second
  spinning = true; let last = performance.now();
  (function f() { if (!spinning) return; const n = performance.now(), r = proj.rotate(); proj.rotate([r[0] + speed * (n - last) / 1000, r[1], r[2]]); last = n; draw(); requestAnimationFrame(f); })();
}
const clickMetric = m => document.querySelector(`[data-metric="${m}"]`).click();

/* ================= TIMELINE ================= */
// Start: app zoomed on the globe, intro card on top.
proj.rotate([-5, -30, 0]); draw();
setCam(focus({ x: rStage.x, y: rStage.y, w: rStage.w * .84, h: rStage.h }, 1.28));
spin(16);

// S1 intro (0 – 4.3)
at(.25, () => rise([...film.querySelectorAll('#intro h1:not(.l2) .w')]));
at(.6, () => tween(1.3, p => $f('#in-d').setAttribute('width', 760 * p), io));
at(1.8, () => tween(.3, p => $f('#in-dn').setAttribute('opacity', p)));
at(1.8, () => { const t = $f('#in-dn'); t.setAttribute('x', 760); });
at(2.4, () => rise([...film.querySelectorAll('#intro .l2 .w')]));
at(2.5, () => tween(1.1, p => $f('#in-o').setAttribute('width', 910 * p), io));
at(2.5, () => tween(.3, p => $f('#in-line').setAttribute('opacity', p)));
at(3.1, () => tween(.5, p => $f('#in-g').setAttribute('width', 150 * p), outC));
at(3.35, () => tween(.3, p => $f('#in-gn').setAttribute('opacity', p)));
at(3.95, () => tween(.6, p => { $f('#intro').style.clipPath = `inset(0 0 ${p * 100}% 0)`; }, io));

// S2 the gap, globally (4.3 – 9.3)
at(4.35, () => caption('Carbon Gap compares what is <b>declared</b> with what is <b>observed</b>', 4.6));
at(4.5, () => camTo({ s: 1, x: 0, y: 0 }, 3.2, io));
at(6.3, () => clickMetric('declared'));
at(7.1, () => clickMetric('observed'));
at(7.9, () => clickMetric('gap'));

// S3 countries (9.5 – 13.6)
at(9.4, () => { spinning = false; caption('Open any country: <b>France</b>, <b>United States</b>, <b>Australia</b>', 4.1); });
at(9.6, () => selectCountry('France', { fly: true }));
at(11.0, () => selectCountry('United States of America', { fly: true }));
at(12.4, () => selectCountry('Australia', { fly: true }));

// S4 the sheet (13.9 – 18.2)
at(13.85, () => caption('The gap, <b>sector by sector</b>, site by site, priced in euros', 4.3));
at(13.8, () => camTo(focus({ x: rSheet.x, y: rSheet.y, w: rSheet.w, h: 560 }, 1.72), 1.0, io));
at(15.3, () => { const sh = document.querySelector('#sheet'); tween(1.9, p => { sh.scrollTop = 560 * p; }, io); });
at(16.2, () => { const s = state.siteLayer && [...state.siteLayer].sort((a, b) => (b.observed - b.declared) - (a.observed - a.declared))[0]; if (s) { state.activeSite = s.id; draw(); document.querySelectorAll('tr[data-s]').forEach(tr => tr.classList.toggle('on', tr.dataset.s === s.id)); } });

// S5 analyst (18.4 – 21.8)
at(17.9, () => { document.querySelector('#sheet').scrollTop = 0; const r = R('#analyst'); camTo(focus({ x: r.x - 160, y: r.y - 40, w: r.w + 160, h: r.h + 40 }, 1.5), .75, io); });
at(18.3, () => caption('Ask the analyst anything. <b>It moves the map.</b>', 3.4, 'top'));
at(18.6, () => { const q = 'Which countries have the biggest gap?', inp = document.querySelector('#q'); tween(1.0, p => { inp.value = q.slice(0, Math.round(q.length * p)); }, e => e); });
at(19.7, () => { const inp = document.querySelector('#q'); const q = inp.value; inp.value = ''; ask(q); });
at(20.35, () => camTo({ s: 1, x: 0, y: 0 }, 1.1, io));

// S6 report (22.0 – 23.7)
at(21.75, () => caption('A <b>sourced report</b> in seconds', 1.9));
at(21.8, () => openReport('China'));
at(22.5, () => camTo(focus({ x: rStage.x + 200, y: rStage.y + 40, w: rStage.w - 400, h: 640 }, 1.32), .8, io));
at(22.9, () => { const el = document.querySelector('#report'); tween(1.0, p => { el.scrollTop = 420 * p; }, io); });

// S7 market (23.9 – 26.6)
at(23.75, () => {
  closeReport(); document.querySelector('#analyst').classList.add('min'); state.selected = null; state.siteLayer = null; state.highlight.clear(); renderSheet();
  camTo({ s: 1, x: 0, y: 0 }, .55, io);
  flyToPoint([45, 22], 1.05);
  caption('Know who has carbon <b>to sell</b>, and who needs <b>to buy</b>', 2.9);
  const recs = [...data.values()].map(r => ({ r, a: agg(r) })).filter(x => x.a.d > 25);
  const sell = new Set(recs.filter(x => x.a.pct < .045).map(x => x.r.name));
  const buy = new Set(recs.filter(x => x.a.pct >= .15).map(x => x.r.name));
  setTimeout(() => gC.selectAll('path').attr('fill', f => sell.has(f.properties.name) ? '#5E9E8F' : buy.has(f.properties.name) ? '#B6463B' : '#E6E3D2'), 250);
  const top = (arr, k) => arr.slice(0, k);
  const sellers = top(recs.filter(x => sell.has(x.r.name)).sort((a, b) => b.a.d - a.a.d), 3);
  const buyers = top(recs.filter(x => buy.has(x.r.name)).sort((a, b) => b.a.gap - a.a.gap), 3);
  const name = n => n === 'United States of America' ? 'United States' : n;
  const m = $f('#mkt');
  m.innerHTML = `<h4>Allowance balance</h4><div class="sub">Synthetic · ${state.year} · €${PRICE}/t</div>` +
    sellers.map(x => `<div class="row"><span class="sw" style="background:#5E9E8F"></span><span>${name(x.r.name)}</span><span class="v">${fmtMt(x.a.d * .06)} Mt</span><span class="tag" style="background:#3B7653">Sell</span></div>`).join('') +
    buyers.map(x => `<div class="row"><span class="sw" style="background:#B6463B"></span><span>${name(x.r.name)}</span><span class="v">${fmtMt(x.a.gap)} Mt</span><span class="tag" style="background:#A3362E">Buy</span></div>`).join('');
  setTimeout(() => tween(.45, p => { m.style.opacity = p; m.style.transform = `translateY(${(1 - p) * 22}px)`; }, outC), 500);
  // trade arcs
  setTimeout(() => {
    const g = svg.append('g').attr('id', 'arcs').attr('fill', 'none').attr('stroke', 'var(--ink)').attr('stroke-width', 4).attr('stroke-linecap', 'round').style('paint-order','stroke');
    const pairs = sellers.map((s, i) => [s.r.name, buyers[i % buyers.length].r.name]);
    pairs.forEach(([a, b]) => {
      const ca = d3.geoCentroid(data.get(a).feature), cb = d3.geoCentroid(data.get(b).feature);
      const halo = g.append('path').datum({ type: 'LineString', coordinates: [ca, cb] }).attr('d', path).attr('stroke', 'var(--sheet)').attr('stroke-width', 9);
      const p = g.append('path').datum({ type: 'LineString', coordinates: [ca, cb] }).attr('d', path);
      const len = p.node().getTotalLength();
      [p, halo].forEach(e => e.attr('stroke-dasharray', `${len} ${len}`).attr('stroke-dashoffset', len));
      tween(.9, q => [p, halo].forEach(e => e.attr('stroke-dashoffset', len * (1 - q))), io);
    });
  }, 1250);
});

// S8 outro (26.6 – 30.5)
at(26.55, () => {
  const o = $f('#outro'); $f('#cap').style.opacity = 0;
  tween(.6, p => { o.style.opacity = 1; o.style.clipPath = `inset(${(1 - p) * 100}% 0 0 0)`; }, io);
  rise([o.querySelector('.mark'), o.querySelector('p'), o.querySelector('.foot')], .18, .7);
});
})();
