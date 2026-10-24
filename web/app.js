/* Carbon Gap front-end: globe, country sheets, analyst (SSE), reports. */
'use strict';

const KINDS = {
  power:  {name: 'Power plant',     color: '#5E9E8F', sym: d3.symbolTriangle},
  steel:  {name: 'Iron & steel',    color: '#D9533F', sym: d3.symbolSquare},
  cement: {name: 'Cement',          color: '#3E9DB8', sym: d3.symbolDiamond},
  oil:    {name: 'Oil & gas',       color: '#86509A', sym: d3.symbolCircle},
  mining: {name: 'Mining',          color: '#B08A3E', sym: d3.symbolCross},
  other:  {name: 'Other industry',  color: '#79A957', sym: d3.symbolWye},
};
const GAP_BREAKS = [0, .02, .05, .10, .20, .35];
const GAP_COLS = ['var(--neg)', 'var(--g0)', 'var(--g1)', 'var(--g2)', 'var(--g3)', 'var(--g4)', 'var(--g5)'];
const TOT_BREAKS = [10, 30, 100, 300, 1000, 3000];
const TOT_COLS = ['#EAE9DD', '#CFD3BF', '#A9B79C', '#7F997C', '#58775F', '#36553F', '#1E3628'];
const NO_DATA = '#E4E2D9';
const SUGGESTIONS = ['Which countries have the biggest gap?', 'Why is Russia so far above its declaration?',
  'Compare France and Germany', 'Which big emitters have no recent UN inventory?', 'Show the largest sites in Poland'];

/* ---------- helpers ---------- */
const $ = s => document.querySelector(s);
const sleep = ms => new Promise(r => setTimeout(r, ms));
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const fmtMt = v => v == null ? '–' : Math.abs(v) >= 100 ? d3.format(',.0f')(v) : Math.abs(v) >= 10 ? d3.format('.1f')(v) : d3.format('.2f')(v);
const fmtPct = v => (v >= 0 ? '+' : '−') + d3.format('.1f')(Math.abs(v * 100)) + '%';
const fmtEur = e => { const s = e < 0 ? '−' : ''; e = Math.abs(e); return e >= 1e9 ? `${s}€${d3.format('.1f')(e / 1e9)} bn` : `${s}€${d3.format('.0f')(e / 1e6)} m`; };
const reduceMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
function toast(t) { const el = $('#toast'); el.textContent = t; el.classList.add('show'); clearTimeout(toast._t); toast._t = setTimeout(() => el.classList.remove('show'), 2400); }
function icons() { lucide.createIcons({attrs: {'stroke-width': 1.75}}); }
/** Minimal, safe markdown: **bold**, [text](url), lists, paragraphs. */
function md(text) {
  const inline = s => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  return text.trim().split(/\n{2,}/).map(block => {
    const lines = block.split('\n');
    if (lines.every(l => /^\s*([-*]|\d+\.)\s+/.test(l))) {
      const tag = /^\s*\d+\./.test(lines[0]) ? 'ol' : 'ul';
      return `<${tag}>${lines.map(l => `<li>${inline(l.replace(/^\s*([-*]|\d+\.)\s+/, ''))}</li>`).join('')}</${tag}>`;
    }
    return `<p>${lines.map(inline).join('<br>')}</p>`;
  }).join('');
}

/* ---------- state ---------- */
const state = {metric: 'gap', selected: null, highlight: new Set(), sites: [], activeSite: null, sort: {key: 'gap', dir: -1}};
let META = {}, byIso = new Map(), byNum = new Map(), features = [];
const siteCache = new Map();
const isDeclared = c => c && c.declared != null;
const disp = c => c.name;

/* ---------- colour ---------- */
function colourOf(c) {
  if (!c) return NO_DATA;
  if (state.metric === 'gap') {
    if (!isDeclared(c)) return 'url(#hatch-nodecl)';
    let i = 0; while (i < GAP_BREAKS.length && c.gap_pct >= GAP_BREAKS[i]) i++; return GAP_COLS[i];
  }
  const v = state.metric === 'declared' ? c.declared : (isDeclared(c) ? c.observed : c.observed_latest?.total);
  if (v == null) return state.metric === 'declared' ? 'url(#hatch-nodecl)' : NO_DATA;
  let i = 0; while (i < TOT_BREAKS.length && v >= TOT_BREAKS[i]) i++; return TOT_COLS[i];
}
function renderLegend() {
  const g = state.metric === 'gap';
  const cols = g ? GAP_COLS : TOT_COLS, ticks = g ? ['<0', '0', '2%', '5%', '10%', '20%', '35%+'] : ['<10', '10', '30', '100', '300', '1k', '3k+'];
  $('#legend').innerHTML = `<h4>${g ? 'Gap: observed vs declared' : (state.metric === 'declared' ? 'Declared' : 'Observed') + ' emissions, MtCO₂e'}</h4>
    <div class="ramp">${cols.map(c => `<span style="background:${c}"></span>`).join('')}</div>
    <div class="ticks">${ticks.map(t => `<span>${t}</span>`).join('')}</div>
    <div class="conf"><svg class="sw" viewBox="0 0 18 12"><rect width="18" height="12" fill="url(#hatch-nodecl)"/></svg>No UN inventory since 2015</div>`;
  $('#metric-note').textContent = {
    gap: 'Observed minus declared, as a share of what was declared, same year.',
    declared: 'What the country reported to the UN for its latest inventory year.',
    observed: 'Independent Climate TRACE estimate (inventory year, or 2024 when there is no inventory).',
  }[state.metric];
}

/* ---------- globe ---------- */
const svg = d3.select('#globe');
const proj = d3.geoOrthographic().clipAngle(90).precision(.4);
const path = d3.geoPath(proj);
let base = 300, W = 800, H = 600;
let gSea, gGrat, gC, gHl, gSel, gSites, gLab, gRim;

function initGlobe() {
  gSea = svg.append('path').datum({type: 'Sphere'}).attr('fill', 'var(--sea)');
  gGrat = svg.append('path').datum(d3.geoGraticule10()).attr('fill', 'none').attr('stroke', 'var(--sea-line)').attr('stroke-width', .6);
  gC = svg.append('g'); gHl = svg.append('g'); gSel = svg.append('g'); gSites = svg.append('g'); gLab = svg.append('g');
  gRim = svg.append('path').datum({type: 'Sphere'}).attr('fill', 'none').attr('stroke', 'var(--ink)').attr('stroke-width', 1.2);
  gC.selectAll('path').data(features).join('path').attr('class', 'country')
    .on('click', (e, f) => { const c = byNum.get(f.id); c ? selectCountry(c.iso3, {fly: true}) : toast(`No data for ${f.properties.name}`); })
    .append('title').text(f => f.properties.name);
  svg.call(d3.drag().on('drag', e => { const k = 70 / proj.scale(), r = proj.rotate(); proj.rotate([r[0] + e.dx * k, Math.max(-85, Math.min(85, r[1] - e.dy * k)), r[2]]); draw(); }));
  svg.node().addEventListener('wheel', e => { e.preventDefault(); zoomBy(e.deltaY < 0 ? 1.1 : 1 / 1.1, false); }, {passive: false});
  resize(); proj.rotate([-12, -38, 0]); recolour(); draw();
}
function resize() {
  const r = $('#stage').getBoundingClientRect(); if (r.width < 10 || r.height < 10) return;
  W = r.width; H = r.height;
  const k0 = gC ? proj.scale() / base : 1, k = isFinite(k0) && k0 > 0 ? k0 : 1;
  base = Math.min(W, H) * .43;
  proj.translate([W * .42, H * .47]).scale(base * k); svg.attr('viewBox', `0 0 ${W} ${H}`); draw();
}
const visible = p => { const r = proj.rotate(); return d3.geoDistance(p, [-r[0], -r[1]]) < Math.PI / 2 - .02; };
const featureOf = iso => { const c = byIso.get(iso); return c && features.find(f => f.id === c.numeric); };
function draw() {
  if (!gC) return;
  gSea.attr('d', path); gGrat.attr('d', path); gRim.attr('d', path);
  gC.selectAll('path').attr('d', path);
  const hl = [...state.highlight].map(featureOf).filter(Boolean);
  gHl.selectAll('path').data(hl, f => f.id).join('path').attr('class', 'hl').attr('d', path);
  const sel = state.selected ? [featureOf(state.selected)].filter(Boolean) : [];
  gSel.selectAll('path').data(sel).join('path').attr('class', 'sel').attr('d', path);
  const sites = state.sites.filter(s => visible(s.coord));
  gSites.selectAll('path').data(sites, s => s.id).join('path')
    .attr('class', s => 'site' + (s.id === state.activeSite ? ' on' : ''))
    .attr('fill', s => KINDS[s.kind].color)
    .attr('d', s => d3.symbol(KINDS[s.kind].sym, s.id === state.activeSite ? 170 : 40 + Math.min(110, s.observed * 6))())
    .attr('transform', s => `translate(${proj(s.coord)})`)
    .on('click', (e, s) => { e.stopPropagation(); focusSite(s.id); })
    .selectAll('title').data(s => [s]).join('title').text(s => `${s.name}${s.owner ? ' · ' + s.owner : ''} · ${fmtMt(s.observed)} Mt`);
  const labs = hl.map(f => ({f, c: d3.geoCentroid(f)})).filter(l => visible(l.c));
  gLab.selectAll('text').data(labs, l => l.f.id).join('text').attr('class', 'glabel').attr('text-anchor', 'middle')
    .attr('x', l => proj(l.c)[0]).attr('y', l => proj(l.c)[1] + 4).text(l => byNum.get(l.f.id)?.name || l.f.properties.name);
}
function recolour() { gC.selectAll('path').attr('fill', f => colourOf(byNum.get(f.id))); }
function zoomBy(k, anim = true) {
  const s0 = proj.scale(), s1 = Math.max(base * .8, Math.min(base * 9, s0 * k));
  if (!anim) { proj.scale(s1); draw(); return; }
  d3.transition().duration(350).tween('z', () => t => { proj.scale(s0 + (s1 - s0) * t); draw(); });
}
function flyToPoint(c, scaleK) {
  const r0 = proj.rotate(); let lon = -c[0]; while (lon - r0[0] > 180) lon -= 360; while (lon - r0[0] < -180) lon += 360;
  const r1 = [lon, -c[1], 0], s0 = proj.scale(), s1 = base * scaleK, ir = d3.interpolate(r0, r1);
  return new Promise(res => {
    if (reduceMotion()) { proj.rotate(r1).scale(s1); draw(); return res(); }
    d3.transition().duration(1150).ease(d3.easeCubicInOut).tween('fly', () => t => {
      proj.rotate(ir(t)); const mid = Math.min(s0, s1) * .92;
      proj.scale(t < .5 ? s0 + (mid - s0) * t * 2 : mid + (s1 - mid) * (t - .5) * 2); draw();
    }).on('end', res).on('interrupt', res);
  });
}
function flyToCountry(iso) {
  const f = featureOf(iso); if (!f) return Promise.resolve();
  // biggest polygon centroid avoids overseas territories pulling the view away
  let target = f;
  if (f.geometry.type === 'MultiPolygon') {
    const polys = f.geometry.coordinates.map(c => ({type: 'Polygon', coordinates: c}));
    target = polys.reduce((a, b) => d3.geoArea(b) > d3.geoArea(a) ? b : a);
  }
  const ang = Math.sqrt(d3.geoArea(target) / Math.PI);
  return flyToPoint(d3.geoCentroid(target), Math.max(1, Math.min(5, .42 / ang)));
}

function flyToMany(isos) {
  const fs = isos.map(featureOf).filter(Boolean);
  if (fs.length < 2) return fs.length ? flyToCountry(isos[0]) : Promise.resolve();
  const centers = fs.map(f => d3.geoCentroid(f));
  const mid = d3.geoCentroid({type: 'MultiPoint', coordinates: centers});
  const spread = d3.max(centers, c => d3.geoDistance(c, mid));
  return flyToPoint(mid, Math.max(.95, Math.min(4, .55 / Math.max(spread, .05))));
}

/* ---------- strata: declared vs observed with the gap hatched ---------- */
function strata(d, o, max, {h = 16, labels = true, w = 380} = {}) {
  const x = v => Math.max(0, v / max * (w - 2)), up = o >= d;
  const y1 = labels ? 16 : 0, y2 = y1 + h + 3, HH = y2 + h + (labels ? 18 : 0);
  return `<svg class="strata" viewBox="0 0 ${w} ${HH}" role="img" aria-label="Declared ${fmtMt(d)} Mt, observed ${fmtMt(o)} Mt">
    ${labels ? `<text class="lbl" x="0" y="11">Declared</text><text x="${Math.max(60, x(d))}" y="11" text-anchor="end">${fmtMt(d)} Mt</text>` : ''}
    <rect x="1" y="${y1}" width="${x(d)}" height="${h}" fill="var(--g0)" stroke="var(--ink)"/>
    ${!up ? `<rect x="${1 + x(o)}" y="${y1}" width="${x(d) - x(o)}" height="${h}" fill="url(#hatch-neg)" stroke="var(--ok)"/>` : ''}
    <rect x="1" y="${y2}" width="${x(o)}" height="${h}" fill="var(--sea)" stroke="var(--ink)"/>
    ${up ? `<rect x="${1 + x(d)}" y="${y2}" width="${Math.max(1.5, x(o) - x(d))}" height="${h}" fill="url(#hatch-gap)" stroke="var(--crit)"/>` : ''}
    <line x1="${1 + x(d)}" x2="${1 + x(d)}" y1="${y1 - 3}" y2="${y2 + h + 3}" stroke="var(--ink)" stroke-dasharray="2 2"/>
    ${labels ? `<text class="lbl" x="0" y="${y2 + h + 14}">Observed</text><text x="${Math.max(60, x(o))}" y="${y2 + h + 14}" text-anchor="end">${fmtMt(o)} Mt</text>` : ''}
  </svg>`;
}
function confTag(c) {
  const k = (c || '').toLowerCase();
  const fill = k.includes('high') ? '<rect width="12" height="10" fill="var(--ink-2)"/>' : k.includes('medium') ? '<rect width="6" height="10" fill="var(--ink-3)"/>' : '<rect width="12" height="10" fill="url(#hatch-nodecl)"/>';
  return `<span class="cf"><svg class="sw" viewBox="0 0 12 10"><rect width="12" height="10" fill="var(--sheet)"/>${fill}</svg>${esc(c ? c[0].toUpperCase() + c.slice(1) : 'Unknown')}</span>`;
}

/* ---------- right sheet ---------- */
function renderWorld() {
  const all = [...byIso.values()], dec = all.filter(isDeclared);
  const D = d3.sum(dec, c => c.declared), O = d3.sum(dec, c => c.observed);
  const k = state.sort.key, dir = state.sort.dir;
  const rows = dec.filter(c => c.declared >= 20).sort((a, b) => dir * (a[k] - b[k]));
  const noInv = all.filter(c => !isDeclared(c)).sort((a, b) => (b.observed_latest?.total || 0) - (a.observed_latest?.total || 0)).slice(0, 6);
  const th = (key, label) => `<th><button data-sort="${key}" ${k === key ? `aria-sort="${dir > 0 ? 'ascending' : 'descending'}"` : ''}>${label}</button></th>`;
  $('#sheet').innerHTML = `
    <div class="sheet-head"><div class="crumb">Latest UN inventory year per country</div><h2>World</h2>
      <div class="meta"><span>${dec.length} countries with a UN inventory since 2015, ${dec.filter(c => c.agent).length} found by research agents</span><span>Carbon price €${META.carbon_price}/t (assumption)</span></div></div>
    <div class="block"><h3>Declared vs observed, all compared countries</h3>${strata(D, O, Math.max(D, O))}
      <dl class="figs"><div><dt>Declared</dt><dd>${fmtMt(D / 1000)} <small>Gt</small></dd></div><div><dt>Observed</dt><dd>${fmtMt(O / 1000)} <small>Gt</small></dd></div>
      <div class="gap"><dt>Gap</dt><dd>${fmtPct((O - D) / D)}</dd></div><div class="gap"><dt>At €${META.carbon_price}/t</dt><dd>${fmtEur((O - D) * 1e6 * META.carbon_price)}</dd></div></dl></div>
    <div class="block"><h3>Largest gaps</h3>
      <table><thead><tr><th>Country</th>${th('declared', 'Declared')}${th('observed', 'Observed')}${th('gap', 'Gap Mt')}${th('gap_pct', 'Gap %')}</tr></thead>
      <tbody>${rows.slice(0, 15).map(c => `<tr data-c="${c.iso3}"><td>${esc(c.name)}<span class="sub">${c.year} · ${esc(c.source.replace('UNFCCC ', ''))}</span></td><td>${fmtMt(c.declared)}</td><td>${fmtMt(c.observed)}</td><td class="${c.gap >= 0 ? 'gpos' : 'gneg'}">${fmtMt(c.gap)}</td><td class="${c.gap >= 0 ? 'gpos' : 'gneg'}">${fmtPct(c.gap_pct)}</td></tr>`).join('')}</tbody></table></div>
    <div class="block"><h3>Big emitters with no UN inventory since 2015</h3>
      <table><thead><tr><th>Country</th><th>Observed ${noInv[0]?.observed_latest?.year || ''}</th></tr></thead>
      <tbody>${noInv.map(c => `<tr data-c="${c.iso3}"><td>${esc(c.name)}</td><td>${fmtMt(c.observed_latest?.total)} Mt</td></tr>`).join('')}</tbody></table>
      <p class="lede" style="margin-top:10px">Select a country to see the sectors and sites behind its emissions.</p></div>`;
  bindSheet();
}
function sectorBars(sectors) {
  const rows = Object.entries(sectors || {}).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
  const max = d3.max(rows, r => r[1]) || 1;
  return rows.map(([k, v]) => `<div class="secrow"><span class="n">${esc(META.sector_labels[k] || k)}</span><div class="hbar" style="width:${Math.max(1, v / max * 100)}%"></div><span class="v">${fmtMt(v)}</span></div>`).join('');
}
function sitesBlock(c) {
  if (!state.sites.length) return `<p class="skeleton" id="sites-msg">Loading the largest sites…</p>`;
  const k = state.sort.key === 'name' ? 'name' : 'observed', dir = state.sort.dir;
  const list = [...state.sites].sort((a, b) => k === 'name' ? dir * a.name.localeCompare(b.name) : -(a.observed - b.observed));
  return `<table><thead><tr><th><button data-sort="name">Site</button></th><th>Observed ${state.sites[0].year}</th></tr></thead>
    <tbody>${list.slice(0, 15).map(s => `<tr data-s="${s.id}" class="${s.id === state.activeSite ? 'on' : ''}"><td><span class="secdot" style="background:${KINDS[s.kind].color}"></span>${esc(s.name)}<span class="sub">${esc(s.owner || 'Owner unknown')} · ${confTag(s.confidence)}</span></td><td>${fmtMt(s.observed)} Mt</td></tr>`).join('')}</tbody></table>`;
}
function renderCountry(iso) {
  const c = byIso.get(iso);
  const head = `<div class="sheet-head"><div class="crumb"><button id="back">World</button><span>/</span><span>${esc(c.name)}</span></div><h2>${esc(c.name)}</h2>
    <div class="meta">${isDeclared(c) ? `<span>Inventory year ${c.year}</span><span>${esc(c.agent ? 'Found by research agent · unverified' : c.source)}</span>` : `<span>No UN inventory since 2015 in our dataset</span>`}</div></div>`;
  let body;
  if (isDeclared(c)) {
    body = `<div class="block"><h3>Declared vs observed, ${c.year}</h3>${strata(c.declared, c.observed, Math.max(c.declared, c.observed))}
      <dl class="figs"><div><dt>Declared</dt><dd>${fmtMt(c.declared)} <small>Mt</small></dd></div><div><dt>Observed</dt><dd>${fmtMt(c.observed)} <small>Mt</small></dd></div>
      <div class="gap"><dt>Gap</dt><dd>${fmtMt(c.gap)} <small>Mt · ${fmtPct(c.gap_pct)}</small></dd></div><div class="gap"><dt>At €${META.carbon_price}/t</dt><dd>${fmtEur(c.value_eur)}</dd></div></dl>
      ${c.observed_latest ? `<p class="lede" style="margin-top:10px">Observed in ${c.observed_latest.year}: <b>${fmtMt(c.observed_latest.total)} Mt</b>.</p>` : ''}
      ${c.agent ? agentBox(c.agent) : ''}</div>
    ${groupsBlock(c)}`;
  } else {
    body = `<div class="block"><h3>Observed, ${c.observed_latest?.year}</h3>
      <dl class="figs" style="grid-template-columns:1fr 1fr"><div><dt>Observed</dt><dd>${fmtMt(c.observed_latest?.total)} <small>Mt</small></dd></div><div><dt>Declared</dt><dd><small>No inventory since 2015</small></dd></div></dl>
      <div class="note-box">Our dataset has no UN inventory for this country since 2015. A research agent can search recent UN reports (Biennial Transparency Reports) for a newer declaration.
        ${c.research?.status === 'not_found' ? `<br><br><b>Last search:</b> nothing usable found${c.research.notes ? '. ' + esc(c.research.notes) : ''}` : ''}</div>
      <div id="research"><button class="btn ghost" id="dores" style="margin-top:10px"><i data-lucide="search" class="icon"></i>${c.research ? 'Search again' : 'Find its latest declaration'}</button></div></div>`;
  }
  $('#sheet').innerHTML = head + body + `
    <div class="block bars"><h3>Observed by sector</h3>${sectorBars(c.sectors)}</div>
    <div class="block"><h3>Largest observed sites</h3><div id="sites">${sitesBlock(c)}</div></div>
    <div class="block"><h3>Sources</h3><ul class="sources">
      ${isDeclared(c) ? (c.agent ? `<li><a href="${esc(c.agent.source_url)}" target="_blank" rel="noopener">${esc(c.agent.document)}</a><span>${c.year}</span></li>`
        : `<li><span>${esc(c.source)} inventory, via Climate Watch</span><span>${c.year}</span></li>`) : ''}
      <li><span>Climate TRACE country estimates</span><span>${isDeclared(c) ? c.year : c.observed_latest?.year}</span></li>
      <li><span>Climate TRACE asset-level estimates (sites)</span><span>2024</span></li></ul>
      <p class="lede" style="margin-top:10px">A gap is a lead to investigate, not proof of misreporting.</p></div>
    <div class="actions"><button class="btn" id="mkreport"><i data-lucide="file-text" class="icon"></i>Generate report</button><button class="btn ghost" id="askwhy"><i data-lucide="message-square-text" class="icon"></i>Ask why</button></div>`;
  $('#back').onclick = () => clearSelection();
  $('#dores')?.addEventListener('click', () => runResearch(iso));
  $('#mkreport').onclick = () => openReport(iso);
  $('#askwhy').onclick = () => ask(isDeclared(c) ? `Why is ${c.name}'s gap ${c.gap >= 0 ? 'positive' : 'negative'}?` : `What drives ${c.name}'s emissions?`);
  bindSheet(); icons();
}
function groupsBlock(c) {
  const rows = Object.entries(c.groups).filter(([, g]) => g.declared != null);
  if (!rows.length) return '';
  const gmax = d3.max(rows, ([, g]) => Math.max(g.declared, g.observed)) || 1;
  return `<div class="block"><h3>By inventory sector</h3>${rows.map(([k, g]) =>
    `<div class="secrow"><span class="n">${esc(META.group_labels[k])}</span>${strata(g.declared, g.observed, gmax, {h: 7, labels: false, w: 220})}<span class="v ${g.observed >= g.declared ? 'pos' : 'neg'}">${fmtPct((g.observed - g.declared) / g.declared)}</span></div>`).join('')}</div>`;
}
function agentBox(a) {
  return `<div class="note-box"><b>Declared figure found by a research agent</b> (confidence ${esc(a.confidence)}, not yet verified by a person).<br>
    “${esc(a.quote)}”<br><a href="${esc(a.source_url)}" target="_blank" rel="noopener">${esc(a.source_title || a.document)} ↗</a></div>`;
}
async function reloadData() {
  const api = await fetch('/api/countries').then(r => r.json());
  META = api; byIso.clear(); byNum.clear();
  for (const c of api.countries) { byIso.set(c.iso3, c); byNum.set(c.numeric, c); }
  recolour(); renderSheet();
}
async function runResearch(iso) {
  const box = $('#research'); if (!box) return;
  box.innerHTML = '<ol class="steps" style="margin:12px 0 0;max-width:none"></ol>';
  const list = box.querySelector('ol');
  const step = t => { list.querySelector('.now')?.classList.replace('now', 'done'); list.insertAdjacentHTML('beforeend', `<li class="now"><span class="dot"></span>${esc(t)}</li>`); };
  try {
    await readSSE(await fetch(`/api/research/${iso}`, {method: 'POST'}), ev => {
      if (ev.type === 'step') step(ev.text);
      else if (ev.type === 'error') step(ev.message);
      else if (ev.type === 'result') {
        list.querySelector('.now')?.classList.replace('now', 'done');
        if (ev.finding.status === 'found') { toast(`${byIso.get(iso).name}: declaration found`); reloadData().then(() => draw()); }
        else step('Nothing usable found. Try again later.');
      }
    });
  } catch { step('The research agent is unreachable.'); }
}
async function readSSE(res, onEvent) {
  if (!res.ok || !res.body) throw new Error('http');
  const reader = res.body.getReader(), dec = new TextDecoder(); let buf = '';
  for (;;) {
    const {value, done} = await reader.read(); if (done) break;
    buf += dec.decode(value, {stream: true});
    let i;
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const line = buf.slice(0, i).replace(/^data: /, ''); buf = buf.slice(i + 2);
      if (line.trim()) onEvent(JSON.parse(line));
    }
  }
}
function bindSheet() {
  $('#sheet').querySelectorAll('tr[data-c]').forEach(tr => tr.onclick = () => selectCountry(tr.dataset.c, {fly: true}));
  $('#sheet').querySelectorAll('tr[data-s]').forEach(tr => tr.onclick = () => focusSite(tr.dataset.s));
  $('#sheet').querySelectorAll('[data-sort]').forEach(b => b.onclick = () => {
    const key = b.dataset.sort; state.sort = {key, dir: state.sort.key === key ? -state.sort.dir : (key === 'name' ? 1 : -1)}; renderSheet();
  });
}
function renderSheet() { state.selected ? renderCountry(state.selected) : renderWorld(); }

async function loadSites(iso) {
  if (siteCache.has(iso)) return siteCache.get(iso);
  try {
    const r = await fetch(`/api/countries/${iso}/sites?limit=25`);
    if (!r.ok) throw 0;
    const {sites} = await r.json(); siteCache.set(iso, sites); return sites;
  } catch { return null; }
}
async function selectCountry(iso, {fly = false} = {}) {
  if (!byIso.has(iso)) return;
  state.selected = iso; state.activeSite = null; state.sites = []; state.sort = {key: 'gap', dir: -1};
  renderSheet(); draw(); history.replaceState(null, '', '#' + iso);
  const sitesP = loadSites(iso).then(sites => {
    if (state.selected !== iso) return;
    if (!sites) { const m = $('#sites-msg'); if (m) m.textContent = 'Site data is unavailable right now.'; return; }
    state.sites = sites; $('#sites').innerHTML = sitesBlock(byIso.get(iso)); bindSheet(); draw();
  });
  if (fly) await flyToCountry(iso);
  return sitesP;
}
function clearSelection() {
  state.selected = null; state.sites = []; state.activeSite = null; state.highlight.clear(); state.sort = {key: 'gap', dir: -1};
  renderSheet(); draw(); history.replaceState(null, '', location.pathname); flyToPoint([12, 30], 1);
}
function focusSite(id) {
  const s = state.sites.find(x => x.id === id); if (!s) return false;
  state.activeSite = id; draw();
  $('#sheet').querySelectorAll('tr[data-s]').forEach(tr => tr.classList.toggle('on', tr.dataset.s === id));
  flyToPoint(s.coord, Math.max(proj.scale() / base, 4));
  $(`tr[data-s="${CSS.escape(id)}"]`)?.scrollIntoView({block: 'nearest', behavior: 'smooth'});
  return true;
}

/* ---------- report ---------- */
async function openReport(iso) {
  const c = byIso.get(iso), el = $('#report');
  el.classList.add('open'); el.dataset.iso = iso;
  const steps = ['Reading declared and observed data', 'Ranking the largest sites', 'Searching recent context on the web', 'Writing the dossier'];
  el.innerHTML = `<div class="report-tools"><span class="t">Report · ${esc(c.name)}</span><button class="btn ghost" id="rclose"><i data-lucide="x" class="icon"></i>Close</button></div><ol class="steps">${steps.map(s => `<li><span class="dot"></span>${s}</li>`).join('')}</ol>`;
  icons(); $('#rclose').onclick = closeReport;
  const lis = [...el.querySelectorAll('.steps li')];
  let done = false;
  (async () => { for (let i = 0; i < lis.length && !done; i++) { lis[i].classList.add('now'); await sleep(i < lis.length - 1 ? 1800 : 0); if (!done && i < lis.length - 1) lis[i].classList.replace('now', 'done'); } })();
  let r;
  try {
    const res = await fetch(`/api/report/${iso}`, {method: 'POST'});
    if (!res.ok) throw 0;
    r = await res.json();
  } catch {
    done = true; if (el.dataset.iso !== iso) return;
    el.querySelector('.steps').insertAdjacentHTML('afterend', '<p class="err-line" style="text-align:center">The report could not be written. Try again in a moment.</p>');
    return;
  }
  done = true;
  if (!el.classList.contains('open') || el.dataset.iso !== iso) return;
  const d = r.data, today = new Date().toLocaleDateString('en-GB', {day: 'numeric', month: 'long', year: 'numeric'});
  el.innerHTML = `<div class="report-tools"><span class="t">Report · ${esc(c.name)}</span>
      <button class="btn ghost" id="rlink"><i data-lucide="link" class="icon"></i>Copy link</button>
      <button class="btn ghost" id="rprint"><i data-lucide="printer" class="icon"></i>Save as PDF</button>
      <button class="btn ghost" id="rclose"><i data-lucide="x" class="icon"></i>Close</button></div>
    <article class="doc">
      <div class="titleblock"><h1>${esc(r.headline)}</h1><div class="tb-meta">Carbon Gap dossier<br>${esc(c.name)}${d.inventory_year ? `<br>Inventory year ${d.inventory_year}` : ''}<br>Generated ${today}</div></div>
      <div class="listen"><button class="btn ghost" id="rlisten"><i data-lucide="volume-2" class="icon"></i>Listen to the briefing</button><span class="lede" id="rlisten-msg"></span></div>
      <h3>Summary</h3>${md(r.summary)}
      ${d.declared_Mt != null ? `<h3>Declared vs observed</h3>${strata(d.declared_Mt, d.observed_Mt, Math.max(d.declared_Mt, d.observed_Mt), {h: 22, w: 700})}
      <dl class="figs"><div><dt>Declared</dt><dd>${fmtMt(d.declared_Mt)} <small>Mt</small></dd></div><div><dt>Observed</dt><dd>${fmtMt(d.observed_Mt)} <small>Mt</small></dd></div><div class="gap"><dt>Gap</dt><dd>${fmtMt(d.gap_Mt)} <small>Mt · ${d.gap_pct > 0 ? '+' : ''}${d.gap_pct}%</small></dd></div><div class="gap"><dt>At €${d.carbon_price_eur_per_t}/t</dt><dd>${fmtEur(d.gap_value_eur)}</dd></div></dl>` : ''}
      <h3>Key findings</h3><ul>${r.findings.map(f => `<li>${esc(f)}</li>`).join('')}</ul>
      <h3>By sector</h3><table><tbody>${r.sectors.map(s => `<tr><td style="width:30%"><b>${esc(s.group)}</b></td><td style="text-align:left">${esc(s.note)}</td></tr>`).join('')}</tbody></table>
      <h3>Sites to investigate</h3><table><thead><tr><th>Site</th><th style="text-align:left">Owner</th><th style="text-align:left">Why</th></tr></thead>
      <tbody>${r.sites_to_investigate.map(s => `<tr><td>${esc(s.name)}</td><td style="text-align:left">${esc(s.owner)}</td><td style="text-align:left">${esc(s.why)}</td></tr>`).join('')}</tbody></table>
      <h3>Next steps</h3><ol>${r.next_steps.map(s => `<li>${esc(s)}</li>`).join('')}</ol>
      <div class="callout"><b>Caveats.</b> ${r.caveats.map(esc).join(' ')}</div>
      <h3>Sources</h3><ul class="sources">
        ${d.declared_source ? `<li><span>${esc(d.declared_source)} inventory via Climate Watch</span><span>${d.inventory_year}</span></li>` : ''}
        <li><span>Climate TRACE country and asset estimates</span><span>climatetrace.org</span></li>
        ${(r.sources || []).map(s => `<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a><span>web</span></li>`).join('')}</ul>
      <p style="margin-top:12px;font-size:13px;color:var(--ink-3)">Written by GPT-5.5 from the data above, with web search for context. Check figures against the sources before publishing.</p>
    </article>`;
  icons();
  $('#rclose').onclick = closeReport; $('#rprint').onclick = () => window.print();
  $('#rlink').onclick = () => navigator.clipboard?.writeText(location.origin + '/#' + iso).then(() => toast('Link copied'), () => toast('Could not copy the link'));
  $('#rlisten').onclick = async () => {
    const b = $('#rlisten'); b.disabled = true; $('#rlisten-msg').textContent = 'Recording the briefing…';
    const audio = new Audio(`/api/report/${iso}/audio`);
    audio.oncanplay = () => { $('#rlisten-msg').textContent = ''; b.replaceWith(Object.assign(document.createElement('audio'), {controls: true, src: audio.src, autoplay: true})); };
    audio.onerror = () => { b.disabled = false; $('#rlisten-msg').textContent = 'The briefing could not be recorded.'; };
    audio.load();
  };
}
function closeReport() { const el = $('#report'); el.classList.remove('open'); el.innerHTML = ''; delete el.dataset.iso; }

/* ---------- analyst ---------- */
const log = $('#log');
let lastResponseId = null, busy = false;
const scrollLog = () => { log.scrollTop = log.scrollHeight; };
function addMsg(cls, html) { const d = document.createElement('div'); d.className = 'msg ' + cls; d.innerHTML = html; log.appendChild(d); scrollLog(); return d; }
function addTool(name, args) {
  const d = document.createElement('div'); d.className = 'tool';
  d.innerHTML = `<i data-lucide="${{web_search: 'globe', knowledge_base: 'book-open', research_declaration: 'file-search'}[name] || 'map-pin'}" class="icon"></i><code>${esc(name)}</code> ${esc(args)}`;
  log.appendChild(d); icons(); scrollLog();
}
async function runAction(a) {
  switch (a.name) {
    case 'select_country': state.highlight.clear(); await selectCountry(a.iso3, {fly: true}); break;
    case 'highlight_countries':
      state.highlight = new Set(a.iso3s); state.selected = null; state.sites = []; renderSheet(); draw();
      flyToMany(a.iso3s);
      break;
    case 'focus_site':
      if (a.iso3 && state.selected !== a.iso3) await selectCountry(a.iso3, {fly: false});
      if (!focusSite(a.site_id)) { const s = await loadSites(a.iso3); if (s) { state.sites = s; focusSite(a.site_id); } }
      break;
    case 'set_metric': setMetric(a.metric); break;
    case 'open_report': openReport(a.iso3); break;
    case 'refresh_data': await reloadData(); if (a.iso3) await selectCountry(a.iso3, {fly: true}); break;
  }
}
async function ask(q) {
  q = q.trim(); if (busy || !q) return;
  busy = true; $('#ask button').disabled = true; $('#analyst').classList.remove('min');
  [...$('#sugg').children].forEach(b => { if (b.textContent === q) b.remove(); });
  $('#sugg').hidden = true;
  addMsg('user', esc(q));
  const thinking = document.createElement('div'); thinking.className = 'thinking'; thinking.innerHTML = '<i></i>Thinking'; log.appendChild(thinking); scrollLog();
  let text = '', bubble = null;
  try {
    const res = await fetch('/api/chat', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: q, previous_response_id: lastResponseId, selected: state.selected ? byIso.get(state.selected).name : null})});
    await readSSE(res, ev => {
      if (ev.type === 'delta') {
        thinking.remove(); if (!bubble) bubble = addMsg('ai', '');
        text += ev.text; bubble.innerHTML = md(text); scrollLog();
      } else if (ev.type === 'tool') { thinking.remove(); addTool(ev.name, ev.args); bubble = null; text = ''; }
      else if (ev.type === 'action') runAction(ev);
      else if (ev.type === 'sources' && ev.items.length) {
        const d = document.createElement('div'); d.className = 'cites';
        d.innerHTML = ev.items.slice(0, 4).map(x => `<a href="${esc(x.url)}" target="_blank" rel="noopener">↗ ${esc(x.title)}</a>`).join('');
        log.appendChild(d); scrollLog();
      } else if (ev.type === 'done') lastResponseId = ev.response_id;
      else if (ev.type === 'error') { thinking.remove(); addMsg('err', esc(ev.message)); }
    });
  } catch {
    thinking.remove(); addMsg('err', 'The analyst is unreachable. Check that the server is running, then try again.');
  } finally {
    thinking.remove(); busy = false; $('#ask button').disabled = false;
  }
}

/* ---------- controls ---------- */
function setMetric(m) {
  state.metric = m;
  document.querySelectorAll('[data-metric]').forEach(x => x.setAttribute('aria-pressed', x.dataset.metric === m));
  renderLegend(); recolour();
}
function initControls() {
  $('#symbols').innerHTML = Object.values(KINDS).map(s => `<div class="keyrow"><svg class="sw" viewBox="-9 -7 18 14" style="border:0"><path d="${d3.symbol(s.sym, 50)()}" fill="${s.color}" stroke="#1C2320"/></svg>${s.name}</div>`).join('');
  document.querySelectorAll('[data-metric]').forEach(b => b.onclick = () => setMetric(b.dataset.metric));
  $('#zin').onclick = () => zoomBy(1.4); $('#zout').onclick = () => zoomBy(1 / 1.4); $('#zreset').onclick = () => clearSelection();
  document.querySelectorAll('[data-soon]').forEach(b => b.onclick = () => toast('Coming soon'));
  const names = [...byIso.values()].map(c => c.name).sort();
  $('#countries').innerHTML = names.map(n => `<option value="${esc(n)}">`).join('');
  $('#search').onchange = e => {
    const v = e.target.value.trim().toLowerCase();
    const c = [...byIso.values()].find(c => c.name.toLowerCase() === v || c.iso3.toLowerCase() === v) || [...byIso.values()].find(c => c.name.toLowerCase().includes(v));
    if (c) { selectCountry(c.iso3, {fly: true}); e.target.value = ''; } else toast(`No country matches “${e.target.value}”`);
  };
  $('#ask').onsubmit = e => { e.preventDefault(); const q = $('#q').value; $('#q').value = ''; ask(q); };
  $('#amin').onclick = () => { const a = $('#analyst'); a.classList.toggle('min'); $('#amin').setAttribute('aria-label', a.classList.contains('min') ? 'Expand analyst' : 'Minimise analyst'); };
  $('#sugg').innerHTML = SUGGESTIONS.map(s => `<button type="button">${esc(s)}</button>`).join('');
  $('#sugg').querySelectorAll('button').forEach(b => b.onclick = () => ask(b.textContent));
  addMsg('ai', '<p>Ask me where declared and observed emissions disagree. I read the data, move the map, search the web for context and write sourced reports.</p>');
  addEventListener('resize', resize);
  addEventListener('keydown', e => { if (e.key === 'Escape' && $('#report').classList.contains('open')) closeReport(); });
}

/* ---------- boot ---------- */
icons();
Promise.all([
  d3.json('https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json'),
  fetch('/api/countries').then(r => { if (!r.ok) throw new Error('api'); return r.json(); }),
]).then(([topo, api]) => {
  META = api;
  for (const c of api.countries) { byIso.set(c.iso3, c); byNum.set(c.numeric, c); }
  features = topojson.feature(topo, topo.objects.countries).features.filter(f => f.properties.name !== 'Antarctica');
  $('#stage-msg').remove();
  initControls(); renderLegend(); initGlobe(); renderSheet();
  const h = location.hash.slice(1).toUpperCase(); if (byIso.has(h)) selectCountry(h, {fly: true});
}).catch(() => { $('#stage-msg').textContent = 'The map could not load. Check your connection and that the server is running, then reload.'; });
