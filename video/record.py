"""Record the Carbon Gap motion film frame by frame.

Needs the dev server on http://localhost:8010 (see .claude/launch.json).
Usage: backend/.venv/bin/python video/record.py [duration_s]
"""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).parent
FRAMES = HERE / "frames"
FPS = 30
DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 30.6


async def main():
    FRAMES.mkdir(exist_ok=True)
    for f in FRAMES.glob("*.jpg"):
        f.unlink()
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", args=["--hide-scrollbars", "--force-color-profile=srgb"])
        page = await browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        await page.clock.install()
        await page.goto("http://localhost:8010/")
        await page.wait_for_function(
            "typeof data !== 'undefined' && data.size > 0 && document.querySelector('#globe path.country')",
            polling=100,
        )
        await page.evaluate("document.fonts.ready.then(() => true)")
        await page.wait_for_timeout(600)
        await page.clock.pause_at(await page.evaluate("Date.now() + 1000"))
        await page.add_script_tag(path=str(HERE / "director.js"))
        n = int(DUR * FPS)
        prev = 0
        for i in range(n):
            target = round(i * 1000 / FPS)
            if target > prev:
                await page.clock.run_for(target - prev)
                prev = target
            await page.screenshot(path=str(FRAMES / f"{i:04d}.jpg"), type="jpeg", quality=93)
            if i % 60 == 0:
                print(f"frame {i}/{n}", flush=True)
        await browser.close()


asyncio.run(main())
