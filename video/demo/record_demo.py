"""Record the Carbon Gap demo film: the live app driven scene by scene, frame by frame.

The page runs on Playwright's virtual clock. Frames are captured while the clock advances; while we wait for a live
API (analyst, agents), the clock is paused and nothing is captured, which cuts the waiting out of the film.
Voiceover lines (vo/*.wav) are placed at each scene start; voice-mode audio at the moment it happens.

Run (server on :8010): backend/.venv/bin/python video/demo/record_demo.py
"""
import asyncio
import json
import subprocess
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).parent
FRAMES = HERE / "frames"
FPS = 30
SCRIPT = {s["id"]: s for s in json.loads((HERE / "script.json").read_text())}


class Film:
    def __init__(self, page):
        self.page, self.frame, self.audio = page, 0, []  # audio: (seconds, wav path)

    @property
    def t(self):
        return self.frame / FPS

    async def cap(self, seconds):
        for _ in range(int(seconds * FPS)):
            await self.page.clock.run_for(round((self.frame + 1) * 1000 / FPS) - round(self.frame * 1000 / FPS))
            await self.page.screenshot(path=str(FRAMES / f"{self.frame:05d}.jpg"), type="jpeg", quality=92)
            self.frame += 1

    async def js(self, code):
        """Run an action without waiting for any promise it starts (animations follow the virtual clock)."""
        await self.page.evaluate(f"() => {{ {code}; }}")

    async def val(self, expr):
        return await self.page.evaluate(f"() => ({expr})")

    async def until(self, cond, show=1.5, timeout=150, keep_clock=False):
        """Film up to `show` seconds, then (unless keep_clock) wait with the clock paused until cond is true."""
        for i in range(int(show * FPS)):
            await self.cap(1 / FPS)
            if i % 6 == 0 and await self.val(cond):
                return True
        waited = 0.0
        while not await self.val(cond):
            if waited > timeout:
                print("  timeout:", cond)
                return False
            if keep_clock:
                await self.cap(1 / FPS)
                waited += 0.15
            else:
                await asyncio.sleep(0.5)
                waited += 0.5
        return True

    async def scene(self, sid, body, pad=0.5):
        start = self.t
        self.audio.append((start, HERE / "vo" / f"{sid}.wav"))
        await body()
        rest = SCRIPT[sid]["dur"] + pad - (self.t - start)
        if rest > 0:
            await self.cap(rest)
        print(f"{sid} {start:6.1f}s → {self.t:6.1f}s", flush=True)


async def main():
    FRAMES.mkdir(exist_ok=True)
    for f in FRAMES.glob("*.jpg"):
        f.unlink()
    fake_mic = HERE / "vo" / "fake_mic.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-t", "1", "-i", "anullsrc=r=48000:cl=mono",
                    "-i", str(HERE / "vo" / "user_q.wav"), "-f", "lavfi", "-t", "8", "-i", "anullsrc=r=48000:cl=mono",
                    "-filter_complex", "[0][1][2]concat=n=3:v=0:a=1", "-ar", "48000", str(fake_mic)], check=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", args=[
            "--hide-scrollbars", "--force-color-profile=srgb", "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream", f"--use-file-for-fake-audio-capture={fake_mic}",
            "--autoplay-policy=no-user-gesture-required"])
        ctx = await browser.new_context(viewport={"width": 1600, "height": 900}, device_scale_factor=1.2,
                                        permissions=["microphone"])
        page = await ctx.new_page()
        await page.clock.install()
        await page.goto("http://localhost:8010/")
        await page.wait_for_function("typeof byIso!=='undefined' && byIso.size>0 && COMPANIES.length>0", polling=200)
        await page.evaluate("document.fonts.ready.then(() => true)")
        await page.wait_for_timeout(800)
        await page.clock.pause_at(await page.evaluate("Date.now() + 1000"))
        await page.add_script_tag(path=str(HERE / "overlay.js"))
        await page.evaluate("window.__noDownload = true; document.querySelector('#analyst').classList.add('min')")
        f = Film(page)

        async def s00():
            await f.js("window.__card = film.card('Carbon Gap', 'Declared vs observed greenhouse-gas emissions')")
            await f.cap(SCRIPT["s00"]["dur"])
            await f.js("film.hide(window.__card)")
        await f.scene("s00", s00, pad=0.2)

        async def s01():
            await f.js("film.chapter('1', 'The headline')")
            await f.cap(9)
        await f.scene("s01", s01)

        async def s02():
            await f.js("document.querySelector('#hero').hidden = true; film.chapter('2', 'The gap, country by country'); flyToPoint([40, 30], 1)")
            await f.cap(3.5)
            for m in ("declared", "observed", "gap"):
                await f.js(f"setMetric('{m}')")
                await f.cap(2)
        await f.scene("s02", s02)

        async def s03():
            await f.js("film.chapter('3', 'A country'); setView('gap', 'CHN')")
            await f.cap(8)
            await f.js("(() => { const sh = document.querySelector('#sheet'); const b = [...sh.querySelectorAll('h3')].find(h => h.textContent.includes('Climate commitments')); if (b) sh.scrollTo({top: b.offsetTop - 80, behavior: 'smooth'}); })()")
            await f.cap(6)
        await f.scene("s03", s03)

        async def s04():
            await f.js("film.chapter('4', 'Sites, seen from space'); document.querySelector('#sheet').scrollTop = 0; setView('gap', 'POL')")
            await f.until("state.sites.length > 0", show=2)
            await f.cap(1.5)
            await f.js("focusSite(state.sites.find(s => /Belchat/i.test(s.name))?.id || state.sites[0].id)")
            await f.cap(4)
        await f.scene("s04", s04)

        async def s05():
            await f.js("document.querySelector('#sat').hidden = true; film.chapter('5', 'Ask the analyst'); clearSelection()")
            await f.cap(1.5)
            q = "Which countries have the biggest gap, and why is Russia so high?"
            await f.js(f"(() => {{ const a = document.querySelector('#analyst'); a.classList.remove('min'); const i = document.querySelector('#q'); i.value = ''; window.__typing = {json.dumps(q)}; }})()")
            for k in range(0, len(q) + 1, 3):  # typing
                await f.js(f"document.querySelector('#q').value = window.__typing.slice(0, {k})")
                await f.cap(0.06)
            await f.js("window.__answer = null; ask(window.__typing).then(t => window.__answer = t); document.querySelector('#q').value = ''")
            await f.until("window.__answer !== null", show=2.5)
            await f.cap(3)
        await f.scene("s05", s05)

        async def s06():
            await f.js("film.chapter('6', 'A sourced dossier'); openReport('RUS')")
            await f.until("!!document.querySelector('.doc')", show=1.2)
            await f.cap(1.2)
            await f.js("document.querySelector('#report').scrollTo({top: 700, behavior: 'smooth'})")
            await f.cap(3)
        await f.scene("s06", s06)

        async def s07():
            await f.js("closeReport(); document.querySelector('#analyst').classList.add('min'); film.chapter('7', 'Companies'); selectCompany('coal-india')")
            await f.cap(10)
        await f.scene("s07", s07)

        async def s08():
            await f.js("film.chapter('8', 'Research any company'); setView('companies', null)")
            await f.cap(1.5)
            await f.js("(() => { const i = document.querySelector('#discover-q'); i.value = 'CRH'; })()")
            await f.cap(1)
            await f.js("search('CRH')")
            await f.until("state.company === 'crh'", show=4, timeout=180)
            await f.cap(3)
        await f.scene("s08", s08)

        async def s09():
            await f.js("film.chapter('9', 'A swarm of research agents'); setView('gap', null)")
            await f.cap(1.5)
            await f.js("launchSwarm(4)")
            await f.until("swarmAgents.length > 0 && swarmAgents.some(a => a.status === 'running')", show=3)
            await f.cap(2)
            await f.until("swarmAgents.some(a => ['found','not_found','error'].includes(a.status))", show=2, timeout=100)
            await f.cap(2.5)
        await f.scene("s09", s09)

        async def s10():
            await f.js("document.querySelector('#swarm').hidden = true; film.chapter('10', 'The carbon market'); setView('market', 'POL')")
            await f.cap(5)
            await f.js("document.querySelector('#sheet').scrollTo({top: 330, behavior: 'smooth'})")
            await f.cap(5)
        await f.scene("s10", s10)

        async def s11():
            await f.js("film.chapter('11', 'Talk to it'); setView('gap', null)")
            await f.cap(1.5)
        await f.scene("s11", s11, pad=0.2)
        # voice turn: the clock keeps running (silence detection needs it)
        await f.js("document.querySelector('#talk').click()")
        f.audio.append((f.t + 0.3, HERE / "vo" / "user_q.wav"))
        await f.until("voice.phase === 'speaking'", show=60, timeout=90, keep_clock=True)
        answer = await f.val("document.querySelector('#vai').textContent")
        ans_wav = HERE / "vo" / "answer.wav"
        subprocess.run(["curl", "-s", "-G", "--data-urlencode", f"text={answer[:600]}", "http://localhost:8010/api/speak",
                        "-o", str(HERE / "vo" / "answer.mp3")], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(HERE / "vo" / "answer.mp3"), "-ar", "48000", "-ac", "1", str(ans_wav)], check=True)
        dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ans_wav)]))
        f.audio.append((f.t, ans_wav))
        print(f"voice answer {dur:.1f}s: {answer[:120]}")
        await f.cap(dur + 0.6)
        await f.js("voice.stop()")

        async def s12():
            await f.js("film.chapter('12', 'Share a finding'); selectCompany('coal-india', {fly: false})")
            await f.cap(0.8)
            await f.js("""(async () => { const c = COMPANIES.find(x => x.id === 'coal-india'), m = c.compare;
              const url = await shareCard({title: c.name, kicker: 'Scope 1 reported vs tracked sites', aLabel: `Reported Scope 1 (${m.reported_year})`, a: m.reported,
                bLabel: `Its tracked sites (${m.year}, Climate TRACE)`, b: m.observed, verdict: `Tracked sites alone: ${d3.format('.1f')(m.ratio)}× its reported Scope 1`, source: 'Sources: Coal India sustainability report; Climate TRACE.'});
              window.__shot = film.image(url); })()""")
            await f.cap(3)
        await f.scene("s12", s12)

        async def s13():
            await f.js("film.hideChapter(); window.__shot && film.hide(window.__shot); window.__end = film.card('Carbon Gap', 'Carbon has a price. It deserved a check.', '<span>Built with the OpenAI API</span><span>OpenAI Paris DevDay Community Hackathon</span><span>#parisdevdayhack</span>')")
            await f.cap(4.5)
        await f.scene("s13", s13, pad=1.5)

        (HERE / "audio_events.json").write_text(json.dumps([(t, str(p)) for t, p in f.audio]))
        print(f"done: {f.frame} frames, {f.t:.1f}s")
        await browser.close()


asyncio.run(main())
