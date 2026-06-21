import asyncio
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

import requests
import yaml
from playwright.async_api import async_playwright

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
SCREENSHOTS_DIR = Path("screenshots")
HASHES_FILE = Path("hashes.json")


async def take_screenshot(page, url: str) -> bytes:
    await page.goto(url, wait_until="networkidle", timeout=30000)
    return await page.screenshot(full_page=True)


def compute_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
            (SCREENSHOTS_DIR / f"{safe_name}.png").write_bytes(screenshot)

            if url in previous_hashes:
                if previous_hashes[url] != current_hash:
                    print(f"Change detected: {url}")
                    send_discord_notification(url, screenshot)
                else:
                    print(f"No change: {url}")
            else:
                print(f"First run (baseline saved): {url}")

        await browser.close()

    HASHES_FILE.write_text(json.dumps(current_hashes, indent=2, ensure_ascii=False))
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
