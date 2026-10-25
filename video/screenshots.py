"""Capture README screenshots of the live app (server on :8010). Run: backend/.venv/bin/python video/screenshots.py"""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
MIC = Path(__file__).parent / "demo" / "vo" / "fake_mic.wav"
import sys  # noqa: E402
ONLY = set(sys.argv[1:])  # optional: only these files (static shots only)

SHOTS = [  # (file, js to run, seconds to wait)
    ("01-home.jpg", "null", 2),
    ("02-country-china.jpg", "document.querySelector('#hero').hidden=true; setView('gap','CHN')", 4),
    ("03-climate-commitments.jpg", "(() => { const sh = document.querySelector('#sheet'); const b = [...sh.querySelectorAll('h3')].find(h => h.textContent.includes('Climate commitments')); sh.scrollTop = b.offsetTop - 60; })()", 1),
    ("04-satellite.jpg", "setView('gap','POL').then(() => setTimeout(() => { document.querySelector('#sheet').scrollTop = 0; focusSite(state.sites.find(s => /Belchat/i.test(s.name))?.id || state.sites[0].id); }, 2500))", 6),
    ("05-analyst.jpg", "clearSelection(); ask('Which countries have the biggest gap, and why is Russia so high?')", 30),
    ("06-report.jpg", "openReport('RUS')", 5),
    ("07-companies.jpg", "closeReport(); document.querySelector('#analyst').classList.add('min'); setView('companies', null)", 3),
    ("08-company-coal-india.jpg", "selectCompany('coal-india')", 4),
    ("09-carbon-market.jpg", "setView('market','POL')", 4),
    ("10-method.jpg", "setView('gap', null).then(() => renderMethod())", 2),
]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                                                            f"--use-file-for-fake-audio-capture={MIC}", "--autoplay-policy=no-user-gesture-required"])
        ctx = await b.new_context(viewport={"width": 1600, "height": 900}, device_scale_factor=1.25, permissions=["microphone"])
        pg = await ctx.new_page()
        await pg.goto("http://localhost:8010/")
        await pg.wait_for_function("typeof byIso!=='undefined' && byIso.size>0 && COMPANIES.length>0")
        await pg.wait_for_timeout(1500)
        for name, js, wait in [x for x in SHOTS if not ONLY or x[0] in ONLY]:
            await pg.evaluate(js)
            await pg.wait_for_timeout(int(wait * 1000))
            await pg.screenshot(path=str(OUT / name), type="jpeg", quality=82)
            print(name, flush=True)
        if ONLY:
            await b.close()
            return
        # agent swarm, mid-run
        await pg.evaluate("document.querySelector('#sheet').scrollTop = 0; launchSwarm(4)")
        await pg.wait_for_timeout(22000)
        await pg.screenshot(path=str(OUT / "11-agent-swarm.jpg"), type="jpeg", quality=82)
        print("11-agent-swarm.jpg")
        await pg.evaluate("document.querySelector('#swarm').hidden = true; swarmClosed = true")
        # voice mode, while speaking
        await pg.evaluate("document.querySelector('#talk').click()")
        await pg.wait_for_function("voice.phase === 'speaking'", timeout=90000)
        await pg.wait_for_timeout(1500)
        await pg.screenshot(path=str(OUT / "12-voice.jpg"), type="jpeg", quality=82)
        print("12-voice.jpg")
        await pg.evaluate("voice.stop()")
        # share card (the PNG itself)
        await pg.evaluate("window.__noDownload = true")
        data = await pg.evaluate("""(async () => { const c = COMPANIES.find(x => x.id === 'coal-india'), m = c.compare;
          const url = await shareCard({title: c.name, kicker: 'Scope 1 reported vs tracked sites', aLabel: `Reported Scope 1 (${m.reported_year})`, a: m.reported,
            bLabel: `Its tracked sites (${m.year}, Climate TRACE)`, b: m.observed, verdict: `Tracked sites alone: ${d3.format('.1f')(m.ratio)}× its reported Scope 1`, source: 'Sources: Coal India sustainability report; Climate TRACE.'});
          const blob = await fetch(url).then(r => r.blob()); return await new Promise(r => { const f = new FileReader(); f.onload = () => r(f.result); f.readAsDataURL(blob); }); })()""")
        import base64
        (OUT / "13-share-card.png").write_bytes(base64.b64decode(data.split(",", 1)[1]))
        print("13-share-card.png")
        await b.close()


asyncio.run(main())
