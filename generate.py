#!/usr/bin/env python3
"""Build channels.json and category TXT playlists from the public channel catalog.

This does not imitate browser sessions, bypass access controls, or resolve
protected playback tokens. If api.php is unavailable to a plain HTTP client,
the workflow fails rather than publishing stale IDs.
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
JSON_OUTPUT = Path("channels.json")
TXT_OUTPUT = Path("infotainment.txt")

TARGETS = {
    "DISCOVERY HINDI": {
        "name": "Discovery HD",
        "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/082c33fedac20343e59eb52d7d13a139.png",
    },
    "SONY BBC EARTH": {
        "name": "Sony BBC Earth HD",
        "logo": "https://d2ljy97uzhlwv2.cloudfront.net/sonypicturesnetworksindia/logo/32_254.png",
    },
    "ANIMAL PLANET | IN": {
        "name": "Animal Planet HD",
        "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/36d31ab0f2693fcdc87bcb4ffec3bcb8.png",
    },
    "NATGEO WILD HINDI": {
        "name": "Nat Geo Wild HD",
        "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/c6b17fad2bf31a052f3dd2c688ae3257.png",
    },
    "NATIONAL GEOGRAPHIC HD | IN": {
        "name": "National Geographic HD",
        "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/a59081e5d6c95ca73f6f89855fb37a18.png",
    },
    "HISTORY HINDI": {
        "name": "History TV18 HD",
        "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/india/history-tv18-hd-in.png",
    },
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


def find_targets(catalog: list[dict]) -> list[tuple[str, dict, dict]]:
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

    result = []
    for catalog_name, metadata in TARGETS.items():
        channel = by_name[catalog_name]
        channel_id = str(channel.get("id", "")).strip()
        if not channel_id:
            raise RuntimeError(f"{metadata['name']} has no catalog ID.")
        result.append((catalog_name, channel, metadata))

    return result


def build_json(targets: list[tuple[str, dict, dict]]) -> dict:
    channels = []
    for _, channel, metadata in targets:
        channel_id = str(channel["id"]).strip()
        channels.append(
            {
                "name": metadata["name"],
                "id": channel_id,
                "group": str(channel.get("group", "")),
                "logo": metadata["logo"],
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


def build_txt(targets: list[tuple[str, dict, dict]]) -> str:
    entries = []
    for _, channel, metadata in targets:
        channel_id = str(channel["id"]).strip()
        stream_url = f"{BASE_URL}/play.php?id={channel_id}"
        entries.append(
            f"{metadata['name']}\n{metadata['logo']}\n{stream_url}"
        )
    return "\n\n".join(entries) + "\n"


def main() -> int:
    try:
        catalog = fetch_catalog()
        targets = find_targets(catalog)
        result = build_json(targets)

        JSON_OUTPUT.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        TXT_OUTPUT.write_text(build_txt(targets), encoding="utf-8")

        print(f"Wrote {len(result['channels'])} channel URLs to {JSON_OUTPUT}.")
        print(f"Wrote category playlist to {TXT_OUTPUT}.")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
