#!/usr/bin/env python3
"""Build channels.json from the generator's public channel catalog.

This intentionally does not imitate browser sessions, bypass access controls,
or attempt to resolve protected playback tokens. If api.php is unavailable to
a plain HTTP client, the workflow fails rather than publishing stale IDs.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE_URL = "https://rkdy-linkgen.wasmer.app"
CATALOG_URL = f"{BASE_URL}/api.php"
OUTPUT_FILE = Path("channels.json")

TARGETS = {
    "DISCOVERY HINDI": "Discovery HD",
    "SONY BBC EARTH": "Sony BBC Earth HD",
    "ANIMAL PLANET | IN": "Animal Planet HD",
    "NATGEO WILD HINDI": "Nat Geo Wild HD",
    "NATIONAL GEOGRAPHIC HD | IN": "National Geographic HD",
    "HISTORY HINDI": "History TV18 HD",
}


def fetch_catalog() -> list[dict]:
    request = Request(
        CATALOG_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "IPTV-Automation/1.0 (+https://github.com/vinod-rajput-vg/IPTV-Automation)",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=20) as response:
            if response.status != 200:
                raise RuntimeError(f"Catalog returned HTTP {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(
            f"Catalog access denied or unavailable (HTTP {exc.code}). "
            "The website may only serve this endpoint in its own browser context. "
            "No browser-session or access-control bypass is attempted."
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach channel catalog: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Catalog response was not valid JSON.") from exc

    if not isinstance(payload, list):
        raise RuntimeError("Catalog JSON must be an array.")

    return payload


def build_output(catalog: list[dict]) -> dict:
    by_name: dict[str, dict] = {}
    for channel in catalog:
        if not isinstance(channel, dict):
            continue
        name = str(channel.get("name", "")).strip().upper()
        if name in TARGETS:
            by_name[name] = channel

    missing = [name for name in TARGETS if name not in by_name]
    if missing:
        raise RuntimeError("Missing target channel(s): " + ", ".join(missing))

    channels = []
    for catalog_name, display_name in TARGETS.items():
        channel = by_name[catalog_name]
        channel_id = str(channel.get("id", "")).strip()
        if not channel_id:
            raise RuntimeError(f"{display_name} has no catalog ID.")

        channels.append(
            {
                "name": display_name,
                "id": channel_id,
                "group": str(channel.get("group", "")),
                "url": f"{BASE_URL}/play.php?id={channel_id}",
            }
        )

    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(ZoneInfo("Asia/Kolkata"))

    return {
        "updated_at": now_ist.isoformat(timespec="seconds"),
        "source": CATALOG_URL,
        "channels": channels,
    }


def main() -> int:
    try:
        catalog = fetch_catalog()
        result = build_output(catalog)
        OUTPUT_FILE.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {len(result['channels'])} channel URLs to {OUTPUT_FILE}.")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
