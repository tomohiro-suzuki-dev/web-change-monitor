import asyncio
import hashlib
import io
import json
import os
from datetime import datetime
from pathlib import Path

import requests
import yaml
from PIL import Image, ImageChops, ImageDraw
from playwright.async_api import async_playwright

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
SCREENSHOTS_DIR = Path("screenshots")
HASHES_FILE = Path("hashes.json")
DIFF_THRESHOLD = 30  # 0〜255：小さいほど微細な差分も検知


async def take_screenshot(page, url: str) -> bytes:
    await page.goto(url, wait_until="networkidle", timeout=30000)
    return await page.screenshot(full_page=True)


def compute_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def annotate_diff(prev_bytes: bytes, curr_bytes: bytes) -> bytes:
    """前回・今回のスクリーンショットを比較し、差分箇所に赤枠を描画して返す。"""
    prev = Image.open(io.BytesIO(prev_bytes)).convert("RGB")
    curr = Image.open(io.BytesIO(curr_bytes)).convert("RGB")

    if prev.size != curr.size:
        prev = prev.resize(curr.size)

    diff = ImageChops.difference(prev, curr)
    diff_thresh = diff.convert("L").point(lambda p: 255 if p > DIFF_THRESHOLD else 0)
    bbox = diff_thresh.getbbox()

    if bbox is None:
        output = io.BytesIO()
        curr.save(output, format="PNG")
        return output.getvalue()

    annotated = curr.copy()
    draw = ImageDraw.Draw(annotated)
    padding = 15
    left = max(0, bbox[0] - padding)
    upper = max(0, bbox[1] - padding)
    right = min(curr.width, bbox[2] + padding)
    lower = min(curr.height, bbox[3] + padding)
    draw.rectangle([left, upper, right, lower], outline=(255, 0, 0), width=4)

    output = io.BytesIO()
    annotated.save(output, format="PNG")
    return output.getvalue()


def send_discord_notification(url: str, screenshot: bytes):
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL not set. Skipping notification.")
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "embeds": [{
            "title": "変更を検知しました",
            "description": f"**URL:** {url}\n**検知時刻:** {timestamp}",
            "color": 0xFF6B35,
        }]
    }
    files = {
        "payload_json": (None, json.dumps(payload), "application/json"),
        "file": ("screenshot.png", screenshot, "image/png"),
    }
    resp = requests.post(DISCORD_WEBHOOK_URL, files=files)
    if resp.status_code not in (200, 204):
        print(f"Discord notification failed: {resp.status_code} {resp.text}")


async def main():
    with open("config.yml") as f:
        config = yaml.safe_load(f)

    urls = config.get("urls", [])
    if not urls:
        print("No URLs configured in config.yml.")
        return

    previous_hashes = {}
    if HASHES_FILE.exists():
        previous_hashes = json.loads(HASHES_FILE.read_text())

    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    current_hashes = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        for url in urls:
            print(f"Checking: {url}")
            try:
                screenshot = await take_screenshot(page, url)
            except Exception as e:
                print(f"Error accessing {url}: {e}")
                continue

            current_hash = compute_hash(screenshot)
            current_hashes[url] = current_hash

            safe_name = url.replace("://", "_").replace("/", "_").replace(".", "_")[:100]
            screenshot_path = SCREENSHOTS_DIR / f"{safe_name}.png"

            if url in previous_hashes:
                if previous_hashes[url] != current_hash:
                    print(f"Change detected: {url}")
                    if screenshot_path.exists():
                        annotated = annotate_diff(screenshot_path.read_bytes(), screenshot)
                    else:
                        annotated = screenshot
                    send_discord_notification(url, annotated)
                else:
                    print(f"No change: {url}")
            else:
                print(f"First run (baseline saved): {url}")

            screenshot_path.write_bytes(screenshot)

        await browser.close()

    HASHES_FILE.write_text(json.dumps(current_hashes, indent=2, ensure_ascii=False))
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
