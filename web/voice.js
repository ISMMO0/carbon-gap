/* Carbon Gap voice mode: talk to the analyst.
   Mic → OpenAI transcription → analyst (moves the map) → ElevenLabs voice, in a loop. */
'use strict';

const voice = (() => {
  const RING_COLORS = {idle: '#8C8A80', listening: '#1E5A86', transcribing: '#1E5A86', thinking: '#D77C4E', speaking: '#B6463B'};
  const LABELS = {idle: 'Tap to talk', listening: 'Listening', transcribing: 'Transcribing', thinking: 'Thinking', speaking: 'Speaking · tap to interrupt'};
  const el = id => document.getElementById(id);
  let phase = 'idle', open = false, ctx, micStream, micAnalyser, outAnalyser, recorder, audio, raf;
  const buf = new Float32Array(1024);

  function setPhase(p) {
    phase = p; el('vstate').textContent = LABELS[p];
    el('orb').setAttribute('aria-label', p === 'speaking' ? 'Interrupt' : p === 'listening' ? 'Stop and send' : 'Tap to talk');
  }
  function level(an) {
    if (!an) return 0;
    an.getFloatTimeDomainData(buf);
    let s = 0; for (let i = 0; i < buf.length; i++) s += buf[i] * buf[i];
    return Math.sqrt(s / buf.length);
  }
  const plain = t => t.replace(/\*\*(.+?)\*\*/g, '$1').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/[#*_`>]/g, '').trim();

  /* ---------- orb: contour rings that ripple with the voice ---------- */
  let smooth = 0;
  function drawOrb(t) {
    const c = el('orbc'), g = c.getContext('2d'), W = c.width, cx = W / 2;
    const live = phase === 'listening' ? level(micAnalyser) * 9 : phase === 'speaking' ? level(outAnalyser) * 7 : phase === 'thinking' || phase === 'transcribing' ? .25 + .15 * Math.sin(t / 300) : .05;
    smooth += (Math.min(1, live) - smooth) * .18;
    g.clearRect(0, 0, W, W);
    const col = RING_COLORS[phase];
    g.fillStyle = col + '1F'; g.beginPath(); g.arc(cx, cx, 26 + smooth * 10, 0, Math.PI * 2); g.fill();
    for (let i = 0; i < 9; i++) {
      const r0 = 30 + i * 10, amp = (3 + i * 1.6) * smooth, k = 3 + (i % 3), spin = phase === 'thinking' ? t / 900 : t / 2600;
      g.beginPath();
      for (let a = 0; a <= 96; a++) {
        const th = a / 96 * Math.PI * 2;
        const r = r0 + amp * Math.sin(th * k + spin * (i % 2 ? 1 : -1) + i) + amp * .5 * Math.sin(th * (k + 2) - spin * 1.7);
        a ? g.lineTo(cx + r * Math.cos(th), cx + r * Math.sin(th)) : g.moveTo(cx + r * Math.cos(th), cx + r * Math.sin(th));
      }
      g.closePath();
      g.strokeStyle = col; g.globalAlpha = 1 - i * .085; g.lineWidth = i === 0 ? 2.2 : 1.3;
      g.setLineDash(phase === 'thinking' && i % 2 ? [5, 6] : []);
      g.stroke();
    }
    g.globalAlpha = 1; g.setLineDash([]);
    raf = requestAnimationFrame(drawOrb);
  }

  /* ---------- audio plumbing ---------- */
  async function ensureAudio() {
    ctx ??= new AudioContext();
    if (ctx.state === 'suspended') await ctx.resume();
    if (!audio) {
      audio = new Audio();
      outAnalyser = ctx.createAnalyser(); outAnalyser.fftSize = 2048;
      ctx.createMediaElementSource(audio).connect(outAnalyser); outAnalyser.connect(ctx.destination);
    }
    if (!micStream) {
      micStream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}});
      micAnalyser = ctx.createAnalyser(); micAnalyser.fftSize = 2048;
      ctx.createMediaStreamSource(micStream).connect(micAnalyser);
    }
  }

  /** Record until ~1.1 s of silence after speech (or a tap). Resolves with a Blob, or null if nothing was said. */
  function record() {
    return new Promise(resolve => {
      const type = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find(t => MediaRecorder.isTypeSupported(t));
      recorder = new MediaRecorder(micStream, type ? {mimeType: type} : undefined);
      const chunks = [];
      let spoke = false, quietMs = 0, floor = 0, samples = 0, last = performance.now();
      const started = last;
      recorder.ondataavailable = e => e.data.size && chunks.push(e.data);
      recorder.onstop = () => resolve(spoke || chunks.length && performance.now() - started > 1500 ? new Blob(chunks, {type: recorder.mimeType}) : null);
      recorder.start(250);
      (function vad() {
        if (recorder.state !== 'recording') return;
        const now = performance.now(), dt = now - last; last = now;
        const rms = level(micAnalyser);
        if (samples < 15) { floor += rms; samples++; requestAnimationFrame(vad); return; }  // measure room noise
        const th = Math.max(.014, (floor / samples) * 2.6);
        if (rms > th) { spoke = true; quietMs = 0; } else if (spoke) quietMs += dt;
        if ((spoke && quietMs > 1100) || now - started > 20000 || (!spoke && now - started > 9000)) { recorder.stop(); return; }
        requestAnimationFrame(vad);
      })();
    });
  }

  /* ---------- one conversation turn ---------- */
  async function turn() {
    if (!open) return;
    el('vtools').innerHTML = '';
    setPhase('listening');
    const blob = await record();
    if (!open) return;
    if (!blob) { setPhase('idle'); return; }
    setPhase('transcribing');
    let text = '';
    try {
      const form = new FormData(); form.append('audio', blob, blob.type.includes('mp4') ? 'speech.mp4' : 'speech.webm');
      const r = await fetch('/api/transcribe', {method: 'POST', body: form});
      text = r.ok ? (await r.json()).text : '';
    } catch { /* handled below */ }
    if (!open) return;
    if (!text) { el('vyou').textContent = 'I did not catch that.'; setPhase('idle'); return; }
    el('vyou').textContent = `“${text}”`; el('vai').textContent = '';
    setPhase('thinking');
    const answer = await ask(text, {voice: true, hooks: {
      onTool: (name, args) => el('vtools').insertAdjacentHTML('beforeend', `<span class="tool"><code>${esc(name)}</code> ${esc(args)}</span>`),
      onDelta: t => { el('vai').textContent = plain(t); },
    }});
    if (!open) return;
    if (!answer) { setPhase('idle'); return; }
    el('vai').textContent = plain(answer);
    setPhase('speaking');
    audio.src = '/api/speak?text=' + encodeURIComponent(plain(answer).slice(0, 1200));
    audio.onended = () => { if (open && phase === 'speaking') turn(); };
    audio.onerror = () => { if (open) { el('vyou').textContent = 'The voice is unavailable. The answer is written above.'; setPhase('idle'); } };
    audio.play().catch(() => setPhase('idle'));
  }

  async function start() {
    open = true;
    el('voice').hidden = false; document.querySelector('.main').classList.add('voice-open');
    el('talk').setAttribute('aria-pressed', 'true');
    el('vyou').textContent = ''; el('vai').textContent = 'Ask me about any country, sector or site.'; el('vtools').innerHTML = '';
    cancelAnimationFrame(raf); raf = requestAnimationFrame(drawOrb);
    try { await ensureAudio(); } catch {
      setPhase('idle'); el('vai').textContent = 'Microphone access was blocked. Allow it in the browser to talk.'; return;
    }
    turn();
  }
  function stop() {
    open = false;
    if (recorder?.state === 'recording') recorder.stop();
    audio?.pause();
    micStream?.getTracks().forEach(t => t.stop()); micStream = null;
    cancelAnimationFrame(raf);
    el('voice').hidden = true; document.querySelector('.main').classList.remove('voice-open');
    el('talk').setAttribute('aria-pressed', 'false'); setPhase('idle');
  }
  function tapOrb() {
    if (phase === 'listening') recorder?.stop();
    else if (phase === 'speaking') { audio.pause(); turn(); }
    else if (phase === 'idle') (micStream ? turn() : start());
  }

  el('talk').onclick = () => (open ? stop() : start());
  el('vclose').onclick = stop;
  el('orb').onclick = tapOrb;
  addEventListener('keydown', e => {
    if (!open) return;
    if (e.key === 'Escape') stop();
    if (e.code === 'Space' && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) { e.preventDefault(); tapOrb(); }
  });
  return {start, stop, get phase() { return phase; }};
})();
