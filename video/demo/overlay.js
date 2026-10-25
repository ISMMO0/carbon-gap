/* Demo film overlay: title cards, chapter chips, image cards. Injected into the live app by record_demo.py.
   Animations use requestAnimationFrame so they follow the recorder's virtual clock. */
(() => {
  const css = `
  #film{position:fixed;inset:0;pointer-events:none;z-index:200;font-family:var(--font)}
  #film .card{position:absolute;inset:0;background:var(--paper);display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;opacity:0}
  #film .card img{width:120px;height:120px}
  #film .card h1{font:700 110px/1 var(--cond);margin:22px 0 0;color:var(--ink)}
  #film .card p{font:500 30px/1.3 var(--font);color:var(--ink-2);margin:14px 0 0}
  #film .card .foot{position:absolute;left:12%;right:12%;bottom:60px;display:flex;justify-content:space-between;border-top:2px solid var(--ink);padding-top:14px;font:600 18px var(--cond);letter-spacing:.06em;text-transform:uppercase;color:var(--ink-2)}
  #film .chip{position:absolute;left:50%;top:64px;transform:translateX(-50%);background:var(--shell);color:var(--shell-ink);font:600 15px/1 var(--cond);letter-spacing:.08em;text-transform:uppercase;padding:9px 16px;border-radius:4px;opacity:0;box-shadow:0 10px 24px -12px rgba(0,0,0,.5)}
  #film .chip b{color:var(--g1);margin-right:8px}
  #film .shot{position:absolute;left:50%;top:50%;width:900px;transform:translate(-50%,-50%);box-shadow:0 30px 70px -20px rgba(0,0,0,.55);border:1px solid var(--ink);opacity:0}`;
  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
  const root = document.createElement('div'); root.id = 'film'; document.body.appendChild(root);
  const tween = (dur, fn) => new Promise(res => { const s = performance.now(); (function f() { const p = Math.min(1, (performance.now() - s) / (dur * 1000)); fn(1 - Math.pow(1 - p, 3)); p < 1 ? requestAnimationFrame(f) : res(); })(); });
  const fade = (el, to, dur = .5) => { const from = +getComputedStyle(el).opacity; return tween(dur, p => { el.style.opacity = from + (to - from) * p; }); };
  let chip;
  window.film = {
    card(title, sub, foot = '') {
      const c = document.createElement('div'); c.className = 'card';
      c.innerHTML = `<img src="logo.svg" alt=""><h1>${title}</h1><p>${sub}</p>${foot ? `<div class="foot">${foot}</div>` : ''}`;
      root.appendChild(c); fade(c, 1, .6); return c;
    },
    async hide(el, dur = .6) { if (!el) return; await fade(el, 0, dur); el.remove(); },
    chapter(n, text) {
      if (!chip) { chip = document.createElement('div'); chip.className = 'chip'; root.appendChild(chip); }
      chip.innerHTML = `<b>${n}</b>${text}`; chip.style.opacity = 0; fade(chip, 1, .4);
    },
    hideChapter() { if (chip) fade(chip, 0, .3); },
    image(src) { const i = document.createElement('img'); i.className = 'shot'; i.src = src; root.appendChild(i); fade(i, 1, .5); return i; },
  };
})();
