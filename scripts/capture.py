"""Render renders/*.png and the README's animations headless: start serve_viewer.py, open the
viewer's capture mode in headless Microsoft Edge (Chrome works too: set PENDULUM_BROWSER), wait
until the page reports done, then compose the multi-view sheets with Pillow.

Run: python scripts/capture.py [--gif]   (needs internet for three.js from the CDN)
"""
import os
import subprocess
import sys
import tempfile
import time

from PIL import Image, ImageDraw, ImageFont

import geom as G

PORT = 28768
BROWSERS = [os.environ.get("PENDULUM_BROWSER", ""),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"]
OUT = os.path.join(G.ROOT, "renders")
DONE = os.path.join(OUT, ".capture_done")


def run_capture(mode, timeout=1500):
    browser = next(b for b in BROWSERS if b and os.path.exists(b))
    if os.path.exists(DONE):
        os.remove(DONE)
    server = subprocess.Popen([sys.executable, os.path.join(G.ROOT, "scripts", "serve_viewer.py"), str(PORT)])
    prof = tempfile.mkdtemp(prefix="pendulum-capture-")
    time.sleep(1.5)
    url = f"http://127.0.0.1:{PORT}/viewer/?capture={mode}"
    br = subprocess.Popen([browser, "--headless=new", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                           "--hide-scrollbars", "--window-size=1600,1000", f"--user-data-dir={prof}",
                           "--disable-background-timer-throttling", "--disable-renderer-backgrounding", url])
    t0 = time.time()
    try:
        while not os.path.exists(DONE):
            if time.time() - t0 > timeout:
                raise TimeoutError(f"capture not done after {timeout} s")
            time.sleep(2)
    finally:
        br.kill()
        server.kill()
    os.remove(DONE)
    print(f"capture {mode}: {time.time() - t0:.0f} s")


def sheet(names, cols, out, labels=None, width=1600):
    ims = [Image.open(os.path.join(OUT, n + ".png")).convert("RGB") for n in names]
    w = width // cols
    tiles = [im.resize((w, round(im.height * w / im.width)), Image.Resampling.LANCZOS) for im in ims]
    rows = (len(tiles) + cols - 1) // cols
    h = max(t.height for t in tiles)
    canvas = Image.new("RGB", (w * cols, h * rows), (244, 246, 248))
    d = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("segoeui.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    for i, t in enumerate(tiles):
        x, y = (i % cols) * w, (i // cols) * h
        canvas.paste(t, (x, y))
        if labels:
            d.rectangle([x + 8, y + 8, x + 16 + d.textlength(labels[i], font=font), y + 40], fill=(255, 255, 255))
            d.text((x + 12, y + 10), labels[i], fill=(31, 35, 40), font=font)
    canvas.save(os.path.join(OUT, out + ".png"), optimize=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    run_capture("gif" if "--gif" in sys.argv else "1")
    if "--gif" not in sys.argv:
        sheet(["01_iso", "02_front", "03_end", "04_top"], 2, "00_all_sides", ["3-D", "front", "end (+x)", "top"])
        sheet(["06_motor_end", "07_idler_end", "08_carriage", "09_sensor", "05_belt_plane_cut", "10_hanging"], 2,
              "00_details", ["motor end", "idler end (tensioner)", "carriage", "sensor tower (AS5600)",
                             "cut on the belt plane", "pendulum hanging, cart at -110"])
        sheet(["13_as_built_v0", "01_iso"], 2, "00_v0_vs_v1", ["v0: as built, findings A1-A9", "v1: this design"])
    for f in sorted(os.listdir(OUT)):
        print(f"  renders/{f}  {os.path.getsize(os.path.join(OUT, f)) // 1024} KB")


if __name__ == "__main__":
    main()
