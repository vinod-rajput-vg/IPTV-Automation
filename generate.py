#!/usr/bin/env python3
"""Build channels.json and manually categorized TXT playlists from the public catalog.

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
OUTPUT_DIR = Path("Output")
JSON_OUTPUT = OUTPUT_DIR / "channels.json"

TARGETS = {
    "AND PICTURES": {"name": "&Pictures HD", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/and-pictures-hd-in.png"},
    "STAR GOLD": {"name": "Star Gold HD", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/star-gold-hd-in.png"},
    "STAR GOLD 2": {"name": "Star Gold 2 HD", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/8bd0df3e5ad35c9b42efa4a720c3680c.png"},
    "STAR GOLD THRILLS": {"name": "Star Gold Thrills", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/6fd63a1a3719b03299aa45daedad36ed.png"},
    "STAR GOLD ROMANCE": {"name": "Star Gold Romance", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/904285d71367035368f9ac8bf8b8f03c.png"},
    "SONY MAX": {"name": "Sony Max HD", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/sony-max-hd-in.png"},
    "SONY MAX 2": {"name": "Sony Max 2", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/sony-max-2-in.png"},
    "ZEE CINEMA": {"name": "Zee Cinema", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/zee-cinema-in.png"},
    "ZEE ACTION": {"name": "Zee Action", "logo": "https://images.weserv.nl/?url=https://tv-site.b-cdn.net/images/channel-logo/zee-action.png"},
    "ZEE CLASSIC": {"name": "Zee Classic", "logo": "https://images.weserv.nl/?url=https://tv-site.b-cdn.net/images/channel-logo/zee-classic.png"},
    "ZEE BOLLYWOOD": {"name": "Zee Bollywood", "logo": "https://images.weserv.nl/?url=https://tv-site.b-cdn.net/images/channel-logo/zee-bollywood.png"},
    "SONY WAH": {"name": "Sony Wah", "logo": "https://d2ljy97uzhlwv2.cloudfront.net/sonypicturesnetworksindia/logo/10_258.png"},
    "STAR UTSAV MOVIES": {"name": "Star Utsav Movies", "logo": "https://intvschedule.com/logo/star-utsav-movies.webp"},
    "ZEE ANMOL CINEMA": {"name": "Zee Anmol Cinema", "logo": "https://images.weserv.nl/?url=https://tv-site.b-cdn.net/images/channel-logo/zee-anmol-cinema.png"},
    "COLORS CINEPLEX": {"name": "Colors Cineplex", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/fa1e0b003da3eaef8602cbfb2833231f.png"},

    "DISCOVERY HINDI": {"name": "Discovery HD", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/082c33fedac20343e59eb52d7d13a139.png"},
    "SONY BBC EARTH": {"name": "Sony BBC Earth HD", "logo": "https://d2ljy97uzhlwv2.cloudfront.net/sonypicturesnetworksindia/logo/32_254.png"},
    "ANIMAL PLANET | IN": {"name": "Animal Planet HD", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/36d31ab0f2693fcdc87bcb4ffec3bcb8.png"},
    "NATGEO WILD HINDI": {"name": "Nat Geo Wild HD", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/c6b17fad2bf31a052f3dd2c688ae3257.png"},
    "NATIONAL GEOGRAPHIC HD | IN": {"name": "National Geographic HD", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/a59081e5d6c95ca73f6f89855fb37a18.png"},
    "HISTORY HINDI": {"name": "History TV18 HD", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/india/history-tv18-hd-in.png"},

    "TV9 BHARATVARSH.": {"name": "Tv9 Bharatvarsh", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/india/tv9-bharatvarsh-in.png"},
    "TIMES NOW  NAV BHARAT": {"name": "Times Now Navbharat", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/bc00f1e02773b93ec36890b5a4ef7ece.png"},
    "NDTV INDIA": {"name": "NDTV India", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/b69d5a23fcfa02d4c2f47e958c704b46.png"},
    "DD NEWS": {"name": "DD News", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/16dfa4cb5cb300bfad994dc6acb44c76.png"},
    "TV9 GUJARATI": {"name": "Tv9 Gujarati", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/f344ea2f99c67074b52150e40cc30c24.png"},
    "TV9 MARATHI": {"name": "Tv9 Marathi", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/cbfc396076a82705258fb3b019b1153b.png"},
    "ZEE 24 KALAK": {"name": "Zee 24 Kalak", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/india/zee-24-kalak-in.png"},
    "ZEE 24 TAAS": {"name": "Zee 24 Taas", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/india/zee-24-taas-in.png"},
    "REPUBLIC BHARAT": {"name": "Republic Bharat", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/india/republic-bharat-tv-in.png"},
    "NEWS NATION": {"name": "News Nation", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/cd40fe9e8db4c7662414c19f09e38857.png"},
    "AAJ TAK": {"name": "Aaj Tak", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/india/aaj-tak-in.png"},
    "ABP NEWS": {"name": "ABP News", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/india/abp-news-in.png"},
    "INDIA TV": {"name": "India TV", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/india/india-tv-in.png"},

    "NICK | IN": {"name": "Nick HD+", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/nick-in.png"},
    "SONIC | IN": {"name": "Sonic", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/nickelodeon-sonic-in.png"},
    "POGO | IN": {"name": "Pogo", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/pogo-in.png"},
    "CARTOON NETWORK FHD | IN": {"name": "Cartoon Network", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/cartoon-network-in.png"},
    "SUPER HUNGAMA": {"name": "Super Hungama", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/super-hungama-in.png"},
    "HUNGAMA TV | IN": {"name": "Hungama TV", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/hungama-in.png"},
    "24/7 OGGY AND THE COCKROACHES": {"name": "Oggy And The Cockroaches 24/7", "logo": "https://upload.wikimedia.org/wikipedia/commons/3/3b/Oggy_and_the_Cockroaches_Logo.webp"},
    "24/7 DORAEMON": {"name": "Doraemon 24/7", "logo": "https://upload.wikimedia.org/wikipedia/en/c/c8/Doraemon_volume_1_cover.jpg"},
    "24/7 MOTU PATLU": {"name": "Motu Patlu 24/7", "logo": "https://upload.wikimedia.org/wikipedia/en/3/3b/Motu_Patlu.Jpg"},
    "24/7 CHHOTA BHEEM": {"name": "Chota Bheem 24/7", "logo": "https://upload.wikimedia.org/wikipedia/en/f/f9/Chhota_Bheem.jpg"},

    "ZEE TV HD": {"name": "Zee TV HD", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/zee-tv-hd-in.png"},
    "STAR PLUS HD": {"name": "Star Plus HD", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/35b759b6ec89c654df9e4374e9548cbd.png"},
    "BIGG BOSS": {"name": "Bigg Boss", "logo": "https://upload.wikimedia.org/wikipedia/en/d/da/Bigg_Boss_Hindi_TV_Series_Logo.jpg"},
}

# Assign channels to your own playlist categories here. These keys must match
# the catalog names in TARGETS. Empty categories are skipped (no blank files).
CATEGORY_TARGETS = {
    "entertainment": [
        "SONY MAX",
        "SONY MAX 2",
        "AND PICTURES",
        "STAR GOLD",
        "STAR GOLD 2",
        "STAR GOLD THRILLS",
        "STAR GOLD ROMANCE",
        "ZEE CINEMA",
        "ZEE ACTION",
        "ZEE CLASSIC",
        "ZEE BOLLYWOOD",
        "SONY WAH",
        "STAR UTSAV MOVIES",
        "ZEE ANMOL CINEMA",
        "COLORS CINEPLEX",
    ],
    "infotainment": [
        "DISCOVERY HINDI",
        "SONY BBC EARTH",
        "ANIMAL PLANET | IN",
        "NATGEO WILD HINDI",
        "NATIONAL GEOGRAPHIC HD | IN",
        "HISTORY HINDI",
    ],
    "news": [
        "TV9 BHARATVARSH.",
        "TIMES NOW  NAV BHARAT",
        "NDTV INDIA",
        "DD NEWS",
        "TV9 GUJARATI",
        "TV9 MARATHI",
        "ZEE 24 KALAK",
        "ZEE 24 TAAS",
        "REPUBLIC BHARAT",
        "NEWS NATION",
        "AAJ TAK",
        "ABP NEWS",
        "INDIA TV",
    ],
    "kids": [
        "NICK | IN",
        "SONIC | IN",
        "POGO | IN",
        "CARTOON NETWORK FHD | IN",
        "SUPER HUNGAMA",
        "HUNGAMA TV | IN",
        "24/7 OGGY AND THE COCKROACHES",
        "24/7 DORAEMON",
        "24/7 MOTU PATLU",
        "24/7 CHHOTA BHEEM",
    ],
    "drama": [
        "ZEE TV HD",
        "STAR PLUS HD",
        "BIGG BOSS",
    ],
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
        entries.append(f"{metadata['name']}\n{metadata['logo']}\n{stream_url}")
    return "\n\n".join(entries) + ("\n" if entries else "")


def build_category_playlists(
    targets: list[tuple[str, dict, dict]],
) -> dict[Path, str]:
    targets_by_name = {catalog_name: (channel, metadata) for catalog_name, channel, metadata in targets}
    playlists = {}

    for category, channel_names in CATEGORY_TARGETS.items():
        entries = []
        for catalog_name in channel_names:
            if catalog_name not in targets_by_name:
                raise RuntimeError(
                    f"Category '{category}' references unknown target '{catalog_name}'."
                )
            channel, metadata = targets_by_name[catalog_name]
            channel_id = str(channel["id"]).strip()
            stream_url = f"{BASE_URL}/play.php?id={channel_id}"
            entries.append(
                f"{metadata['name']}\n{metadata['logo']}\n{stream_url}"
            )

        if entries:
            playlists[OUTPUT_DIR / f"{category}.txt"] = "\n\n".join(entries) + "\n"

    return playlists


def main() -> int:
    try:
        catalog = fetch_catalog()
        targets = find_targets(catalog)
        result = build_json(targets)
        playlists = build_category_playlists(targets)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        JSON_OUTPUT.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        for path, content in playlists.items():
            path.write_text(content, encoding="utf-8")

        print(f"Wrote {len(result['channels'])} channel URLs to {JSON_OUTPUT}.")
        for path in playlists:
            print(f"Wrote category playlist to {path}.")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
