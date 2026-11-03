#!/usr/bin/env python3
"""Build separate server JSON catalogs and one merged TXT playlist from the public catalog.

This does not imitate browser sessions, bypass access controls, or resolve
protected playback tokens. If api.php is unavailable to a plain HTTP client,
the workflow fails rather than publishing stale IDs.
"""

from __future__ import annotations

import json
import re
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE_URL = "https://rkdy-linkgen.wasmer.app"
OUTPUT_DIR = Path("Output")

# Show the source server in category TXT channel names.
SHOW_SERVER_IN_TXT = True

# Channel overrides use this three-line format:
# "CATALOG_KEY" SERVER, DISPLAY_NAME, LOGO_URL
CHANNEL_OVERRIDES = """
"STAR GOLD HD INDIA" 2
Star Gold HD
https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/star-gold-hd-in.png

"STAR GOLD 2" 1
Star Gold 2 HD
https://jiotvimages.cdn.jio.com/dare_images/images/channel/8bd0df3e5ad35c9b42efa4a720c3680c.png

"STAR GOLD THRILLS" 1
Star Gold Thrills
https://jiotvimages.cdn.jio.com/dare_images/images/channel/6fd63a1a3719b03299aa45daedad36ed.png

"STAR GOLD ROMANCE" 1
Star Gold Romance
https://jiotvimages.cdn.jio.com/dare_images/images/channel/904285d71367035368f9ac8bf8b8f03c.png

"SONY MAX" 1
Sony Max HD
https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/sony-max-hd-in.png

"SONY MAX 2" 1
Sony Max 2
https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/sony-max-2-in.png

"ZEE CINEMA" 1
Zee Cinema
https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/zee-cinema-in.png

"SONY WAH" 1
Sony Wah
https://d2ljy97uzhlwv2.cloudfront.net/sonypicturesnetworksindia/logo/10_258.png

"STAR UTSAV MOVIES" 1
Star Utsav Movies
https://intvschedule.com/logo/star-utsav-movies.webp

"ZEE ANMOL CINEMA" 1
Zee Anmol Cinema
https://images.weserv.nl/?url=https://tv-site.b-cdn.net/images/channel-logo/zee-anmol-cinema.png

"COLORS CINEPLEX" 1
Colors Cineplex
https://jiotvimages.cdn.jio.com/dare_images/images/channel/fa1e0b003da3eaef8602cbfb2833231f.png

"DISCOVERY HINDI" 1
Discovery HD
https://jiotvimages.cdn.jio.com/dare_images/images/channel/082c33fedac20343e59eb52d7d13a139.png

"SONY BBC EARTH" 1
Sony BBC Earth HD
https://d2ljy97uzhlwv2.cloudfront.net/sonypicturesnetworksindia/logo/32_254.png

"ANIMAL PLANET | IN" 1
Animal Planet HD
https://jiotvimages.cdn.jio.com/dare_images/images/channel/36d31ab0f2693fcdc87bcb4ffec3bcb8.png

"NATGEO WILD HINDI" 1
Nat Geo Wild HD
https://jiotvimages.cdn.jio.com/dare_images/images/channel/c6b17fad2bf31a052f3dd2c688ae3257.png

"NATIONAL GEOGRAPHIC HD | IN" 1
National Geographic HD
https://jiotvimages.cdn.jio.com/dare_images/images/channel/a59081e5d6c95ca73f6f89855fb37a18.png

"HISTORY HINDI" 1
History TV18 HD
https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/india/history-tv18-hd-in.png

"TV9 BHARATVARSH." 1
Tv9 Bharatvarsh
https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/india/tv9-bharatvarsh-in.png

"TIMES NOW  NAV BHARAT" 1
Times Now Navbharat
https://jiotvimages.cdn.jio.com/dare_images/images/channel/bc00f1e02773b93ec36890b5a4ef7ece.png

"NDTV INDIA" 1
NDTV India
https://jiotvimages.cdn.jio.com/dare_images/images/channel/b69d5a23fcfa02d4c2f47e958c704b46.png

"DD NEWS" 1
DD News
https://jiotvimages.cdn.jio.com/dare_images/images/channel/16dfa4cb5cb300bfad994dc6acb44c76.png

"TV9 GUJARATI" 1
Tv9 Gujarati
https://jiotvimages.cdn.jio.com/dare_images/images/channel/f344ea2f99c67074b52150e40cc30c24.png

"TV9 MARATHI" 1
Tv9 Marathi
https://jiotvimages.cdn.jio.com/dare_images/images/channel/cbfc396076a82705258fb3b019b1153b.png

"ZEE 24 KALAK" 1
Zee 24 Kalak
https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/india/zee-24-kalak-in.png

"ZEE 24 TAAS" 1
Zee 24 Taas
https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/india/zee-24-taas-in.png

"REPUBLIC BHARAT" 1
Republic Bharat
https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/india/republic-bharat-tv-in.png

"NEWS NATION" 1
News Nation
https://jiotvimages.cdn.jio.com/dare_images/images/channel/cd40fe9e8db4c7662414c19f09e38857.png

"AAJ TAK" 1
Aaj Tak
https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/india/aaj-tak-in.png

"ABP NEWS" 1
ABP News
https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/india/abp-news-in.png

"INDIA TV" 1
India TV
https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/india/india-tv-in.png

"NICK | IN" 1
Nick HD+
https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/nick-in.png

"SONIC | IN" 1
Sonic
https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/nickelodeon-sonic-in.png

"POGO | IN" 1
Pogo
https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/pogo-in.png

"CARTOON NETWORK FHD | IN" 1
Cartoon Network
https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/cartoon-network-in.png

"SUPER HUNGAMA" 1
Super Hungama
https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/super-hungama-in.png

"HUNGAMA TV | IN" 1
Hungama TV
https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/hungama-in.png

"24/7 OGGY AND THE COCKROACHES" 1
Oggy And The Cockroaches 24/7
https://upload.wikimedia.org/wikipedia/commons/3/3b/Oggy_and_the_Cockroaches_Logo.webp

"24/7 DORAEMON" 1
Doraemon 24/7
https://upload.wikimedia.org/wikipedia/en/c/c8/Doraemon_volume_1_cover.jpg

"24/7 MOTU PATLU" 1
Motu Patlu 24/7
https://upload.wikimedia.org/wikipedia/en/3/3b/Motu_Patlu.Jpg

"24/7 CHHOTA BHEEM" 1
Chota Bheem 24/7
https://upload.wikimedia.org/wikipedia/en/f/f9/Chhota_Bheem.jpg

"ZEE TV HD" 1
Zee TV HD
https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/zee-tv-hd-in.png

"STAR PLUS HD" 1
Star Plus HD
https://jiotvimages.cdn.jio.com/dare_images/images/channel/35b759b6ec89c654df9e4374e9548cbd.png

"BIGG BOSS" 1
Bigg Boss
https://upload.wikimedia.org/wikipedia/en/d/da/Bigg_Boss_Hindi_TV_Series_Logo.jpg
"""

def parse_channel_overrides(value: str) -> dict[str, dict]:
    overrides = {}
    lines = [line.strip() for line in value.splitlines() if line.strip()]

    for line_index in range(0, len(lines), 3):
        if line_index + 2 >= len(lines):
            raise ValueError("Channel overrides must contain three lines per entry.")

        key_and_server, display_name, logo = lines[line_index:line_index + 3]
        match = re.fullmatch(r'"(.+?)"\s+([12])', key_and_server)
        if not match:
            raise ValueError(
                'Invalid override header. Expected: "CATALOG_KEY" SERVER'
            )

        matched_key, server = match.groups()
        logo_match = re.fullmatch(r"\[(https?://[^\]]+)\]\((https?://[^)]+)\)", logo)
        if logo_match:
            logo = logo_match.group(2)
        elif not re.fullmatch(r"https?://\S+", logo):
            raise ValueError(f"Invalid channel logo URL: {logo}")

        matched_key = " ".join(matched_key.split())
        if matched_key not in TARGETS:
            raise ValueError(f"Unknown catalog key in channel override: {matched_key}")
        if not display_name:
            raise ValueError(f"Missing display name in channel override: {matched_key}")

        overrides[matched_key] = {
            "server": int(server),
            "name": display_name,
            "logo": logo,
        }
    return overrides

DEFAULT_SERVER_PRIORITY = (1, 2)

TARGETS = {
    "STAR GOLD HD INDIA": {"name": "Star Gold HD", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/star-gold-hd-in.png"},
    "STAR GOLD 2": {"name": "Star Gold 2 HD", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/8bd0df3e5ad35c9b42efa4a720c3680c.png"},
    "STAR GOLD THRILLS": {"name": "Star Gold Thrills", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/6fd63a1a3719b03299aa45daedad36ed.png"},
    "STAR GOLD ROMANCE": {"name": "Star Gold Romance", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/904285d71367035368f9ac8bf8b8f03c.png"},
    "SONY MAX": {"name": "Sony Max HD", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/sony-max-hd-in.png"},
    "SONY MAX 2": {"name": "Sony Max 2", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/sony-max-2-in.png"},
    "ZEE CINEMA": {"name": "Zee Cinema", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/zee-cinema-in.png"},
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

CHANNEL_OVERRIDES_BY_NAME = parse_channel_overrides(CHANNEL_OVERRIDES)

# Assign channels to your own playlist categories here. These keys must match
# the catalog names in TARGETS. Empty categories are skipped (no blank files).
CATEGORY_TARGETS = {
    "entertainment": [
        "STAR GOLD HD INDIA",
        "STAR GOLD 2",
        "STAR GOLD THRILLS",
        "STAR GOLD ROMANCE",
        "AND PICTURES",
        "SONY MAX",
        "SONY MAX 2",
        "ZEE CINEMA",
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


def fetch_catalog(server_id: int) -> list[dict]:
    catalog_url = f"{BASE_URL}/api.php?server={server_id}"
    request = Request(
        catalog_url,
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


def normalize_name(value: object) -> str:
    """Normalize channel names without changing meaningful punctuation."""
    return " ".join(str(value or "").split()).upper()


def find_targets(
    catalog: list[dict], require_all: bool = True,
) -> list[tuple[str, dict, dict]]:
    targets_by_normalized_name = {
        normalize_name(name): name for name in TARGETS
    }
    by_name: dict[str, dict] = {}
    duplicates: set[str] = set()

    for channel in catalog:
        if not isinstance(channel, dict):
            continue

        name = normalize_name(channel.get("name", ""))
        if name not in targets_by_normalized_name:
            continue

        if name in by_name:
            duplicates.add(targets_by_normalized_name[name])
            continue

        by_name[name] = channel

    if duplicates:
        raise RuntimeError(
            "Duplicate target channel records found: "
            + ", ".join(sorted(duplicates))
        )

    missing = [
        name for normalized, name in targets_by_normalized_name.items()
        if normalized not in by_name
    ]
    if missing and require_all:
        raise RuntimeError("Missing target channel(s): " + ", ".join(missing))

    result = []
    for catalog_name, metadata in TARGETS.items():
        normalized_name = normalize_name(catalog_name)
        if normalized_name not in by_name:
            continue
        channel = by_name[normalized_name]
        channel_id = str(channel.get("id", "")).strip()
        if not channel_id:
            raise RuntimeError(f"{metadata['name']} has no catalog ID.")
        if any(character.isspace() for character in channel_id):
            raise RuntimeError(f"{metadata['name']} has an invalid catalog ID.")

        result.append((catalog_name, channel, metadata))

    if not result:
        raise RuntimeError("No configured target channels were found in this source.")

    return result


def build_json(targets: list[tuple[str, dict, dict]], server_id: int) -> dict:
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
        "source": f"{BASE_URL}/api.php?server={server_id}",
        "channels": channels,
    }


def build_txt(targets: list[tuple[str, dict, dict]]) -> str:
    entries = []
    for _, channel, metadata in targets:
        channel_id = str(channel["id"]).strip()
        stream_url = f"{BASE_URL}/play.php?id={channel_id}"
        entries.append(f'{metadata["name"]}\n{metadata["logo"]}\n"{stream_url}"')
    return "\n\n".join(entries) + ("\n" if entries else "")


def build_category_playlists(
    server_targets: list[list[tuple[str, dict, dict]]],
) -> dict[Path, str]:
    """Merge servers into category TXT files using configurable source preference."""
    targets_by_name = {}
    for server_id, targets in enumerate(server_targets, start=1):
        for catalog_name, channel, metadata in targets:
            override = CHANNEL_OVERRIDES_BY_NAME.get(catalog_name, {})
            preferred_server = override.get("server")
            priority = (
                (preferred_server, 3 - preferred_server)
                if preferred_server in (1, 2)
                else DEFAULT_SERVER_PRIORITY
            )
            current = targets_by_name.get(catalog_name)
            if current is None:
                targets_by_name[catalog_name] = (server_id, channel, metadata)
                continue

            current_server_id = current[0]
            if (
                server_id in priority
                and current_server_id in priority
                and priority.index(server_id) < priority.index(current_server_id)
            ):
                targets_by_name[catalog_name] = (server_id, channel, metadata)

    playlists = {}
    for category, channel_names in CATEGORY_TARGETS.items():
        entries = []
        seen_names: set[str] = set()

        for catalog_name in channel_names:
            if catalog_name not in targets_by_name:
                continue

            server_id, channel, metadata = targets_by_name[catalog_name]
            normalized_name = normalize_name(metadata["name"])
            if normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)

            channel_id = str(channel["id"]).strip()
            stream_url = f"{BASE_URL}/play.php?id={channel_id}"
            override = CHANNEL_OVERRIDES_BY_NAME.get(catalog_name, {})
            channel_name = override.get("name", metadata["name"])
            channel_logo = override.get("logo", metadata["logo"])
            display_name = (
                f"{channel_name} (Server {server_id})"
                if SHOW_SERVER_IN_TXT else channel_name
            )
            entries.append(
                f'{display_name}\n{channel_logo}\n"{stream_url}"'
            )

        if entries:
            playlists[OUTPUT_DIR / f"{category}.txt"] = (
                "\n\n".join(entries) + "\n"
            )

    return playlists


def write_outputs_atomically(outputs: dict[Path, str]) -> None:
    """Stage every output beside its destination, then replace destination files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    staged: dict[Path, Path] = {}

    try:
        for destination, data in outputs.items():
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary.write(data)
                staged[destination] = Path(temporary.name)

        for destination, temporary in staged.items():
            os.replace(temporary, destination)
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def main() -> int:
    try:
        outputs = {}
        server_targets = []
        generated_count = 0

        for server_id in (1, 2):
            catalog = fetch_catalog(server_id)
            targets = find_targets(catalog, require_all=False)
            result = build_json(targets, server_id)

            json_path = OUTPUT_DIR / (
                "channels.json" if server_id == 1 else f"channels_server_{server_id}.json"
            )
            outputs[json_path] = json.dumps(
                result, ensure_ascii=False, indent=2,
            ) + "\n"
            server_targets.append(targets)
            generated_count += len(result["channels"])

        outputs.update(build_category_playlists(server_targets))

        write_outputs_atomically(outputs)

        print(f"Wrote {generated_count} channel entries across both sources.")
        for path in outputs:
            print(f"Wrote {path}.")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
, line)
        if not match:
            raise ValueError(
                'Invalid channel override. Expected: "CATALOG_KEY" SERVER '
                "DISPLAY_NAME LOGO_URL"
            )

        matched_key, server, display_name, logo = match.groups()
        matched_key = " ".join(matched_key.split())
        if matched_key not in TARGETS:
            raise ValueError(f"Unknown catalog key in channel override: {matched_key}")

        if not display_name:
            raise ValueError(f"Missing display name in channel override: {line}")

        overrides[matched_key] = {
            "server": int(server),
            "name": display_name,
            "logo": logo,
        }
    return overrides

DEFAULT_SERVER_PRIORITY = (1, 2)

TARGETS = {
    "STAR GOLD HD INDIA": {"name": "Star Gold HD", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/star-gold-hd-in.png"},
    "STAR GOLD 2": {"name": "Star Gold 2 HD", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/8bd0df3e5ad35c9b42efa4a720c3680c.png"},
    "STAR GOLD THRILLS": {"name": "Star Gold Thrills", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/6fd63a1a3719b03299aa45daedad36ed.png"},
    "STAR GOLD ROMANCE": {"name": "Star Gold Romance", "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/channel/904285d71367035368f9ac8bf8b8f03c.png"},
    "SONY MAX": {"name": "Sony Max HD", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/sony-max-hd-in.png"},
    "SONY MAX 2": {"name": "Sony Max 2", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/sony-max-2-in.png"},
    "ZEE CINEMA": {"name": "Zee Cinema", "logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/india/zee-cinema-in.png"},
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

CHANNEL_OVERRIDES_BY_NAME = parse_channel_overrides(CHANNEL_OVERRIDES)

# Assign channels to your own playlist categories here. These keys must match
# the catalog names in TARGETS. Empty categories are skipped (no blank files).
CATEGORY_TARGETS = {
    "entertainment": [
        "STAR GOLD HD INDIA",
        "STAR GOLD 2",
        "STAR GOLD THRILLS",
        "STAR GOLD ROMANCE",
        "AND PICTURES",
        "SONY MAX",
        "SONY MAX 2",
        "ZEE CINEMA",
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


def fetch_catalog(server_id: int) -> list[dict]:
    catalog_url = f"{BASE_URL}/api.php?server={server_id}"
    request = Request(
        catalog_url,
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


def normalize_name(value: object) -> str:
    """Normalize channel names without changing meaningful punctuation."""
    return " ".join(str(value or "").split()).upper()


def find_targets(
    catalog: list[dict], require_all: bool = True,
) -> list[tuple[str, dict, dict]]:
    targets_by_normalized_name = {
        normalize_name(name): name for name in TARGETS
    }
    by_name: dict[str, dict] = {}
    duplicates: set[str] = set()

    for channel in catalog:
        if not isinstance(channel, dict):
            continue

        name = normalize_name(channel.get("name", ""))
        if name not in targets_by_normalized_name:
            continue

        if name in by_name:
            duplicates.add(targets_by_normalized_name[name])
            continue

        by_name[name] = channel

    if duplicates:
        raise RuntimeError(
            "Duplicate target channel records found: "
            + ", ".join(sorted(duplicates))
        )

    missing = [
        name for normalized, name in targets_by_normalized_name.items()
        if normalized not in by_name
    ]
    if missing and require_all:
        raise RuntimeError("Missing target channel(s): " + ", ".join(missing))

    result = []
    for catalog_name, metadata in TARGETS.items():
        normalized_name = normalize_name(catalog_name)
        if normalized_name not in by_name:
            continue
        channel = by_name[normalized_name]
        channel_id = str(channel.get("id", "")).strip()
        if not channel_id:
            raise RuntimeError(f"{metadata['name']} has no catalog ID.")
        if any(character.isspace() for character in channel_id):
            raise RuntimeError(f"{metadata['name']} has an invalid catalog ID.")

        result.append((catalog_name, channel, metadata))

    if not result:
        raise RuntimeError("No configured target channels were found in this source.")

    return result


def build_json(targets: list[tuple[str, dict, dict]], server_id: int) -> dict:
    channels = []
    for _, channel, metadata in targets:
        channel_id = str(channel["id"]).strip()
        channels.append(
            {
                "name": metadata["name"],
                "id": f'"{channel_id}"',
                "group": str(channel.get("group", "")),
                "logo": metadata["logo"],
                "url": f"{BASE_URL}/play.php?id={channel_id}",
            }
        )

    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(ZoneInfo("Asia/Kolkata"))

    return {
        "updated_at": now_ist.isoformat(timespec="seconds"),
        "source": f"{BASE_URL}/api.php?server={server_id}",
        "channels": channels,
    }


def build_txt(targets: list[tuple[str, dict, dict]]) -> str:
    entries = []
    for _, channel, metadata in targets:
        channel_id = str(channel["id"]).strip()
        stream_url = f"{BASE_URL}/play.php?id={channel_id}"
        entries.append(f'{metadata["name"]}\n{metadata["logo"]}\n"{stream_url}"')
    return "\n\n".join(entries) + ("\n" if entries else "")


def build_category_playlists(
    server_targets: list[list[tuple[str, dict, dict]]],
) -> dict[Path, str]:
    """Merge servers into category TXT files using configurable source preference."""
    targets_by_name = {}
    for server_id, targets in enumerate(server_targets, start=1):
        for catalog_name, channel, metadata in targets:
            override = CHANNEL_OVERRIDES_BY_NAME.get(catalog_name, {})
            preferred_server = override.get("server")
            priority = (
                (preferred_server, 3 - preferred_server)
                if preferred_server in (1, 2)
                else DEFAULT_SERVER_PRIORITY
            )
            current = targets_by_name.get(catalog_name)
            if current is None:
                targets_by_name[catalog_name] = (server_id, channel, metadata)
                continue

            current_server_id = current[0]
            if (
                server_id in priority
                and current_server_id in priority
                and priority.index(server_id) < priority.index(current_server_id)
            ):
                targets_by_name[catalog_name] = (server_id, channel, metadata)

    playlists = {}
    for category, channel_names in CATEGORY_TARGETS.items():
        entries = []
        seen_names: set[str] = set()

        for catalog_name in channel_names:
            if catalog_name not in targets_by_name:
                continue

            server_id, channel, metadata = targets_by_name[catalog_name]
            normalized_name = normalize_name(metadata["name"])
            if normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)

            channel_id = str(channel["id"]).strip()
            stream_url = f"{BASE_URL}/play.php?id={channel_id}"
            override = CHANNEL_OVERRIDES_BY_NAME.get(catalog_name, {})
            channel_name = override.get("name", metadata["name"])
            channel_logo = override.get("logo", metadata["logo"])
            display_name = (
                f"{channel_name} (Server {server_id})"
                if SHOW_SERVER_IN_TXT else channel_name
            )
            entries.append(
                f'{display_name}\n{channel_logo}\n"{stream_url}"'
            )

        if entries:
            playlists[OUTPUT_DIR / f"{category}.txt"] = (
                "\n\n".join(entries) + "\n"
            )

    return playlists


def write_outputs_atomically(outputs: dict[Path, str]) -> None:
    """Stage every output beside its destination, then replace destination files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    staged: dict[Path, Path] = {}

    try:
        for destination, data in outputs.items():
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary.write(data)
                staged[destination] = Path(temporary.name)

        for destination, temporary in staged.items():
            os.replace(temporary, destination)
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def main() -> int:
    try:
        outputs = {}
        server_targets = []
        generated_count = 0

        for server_id in (1, 2):
            catalog = fetch_catalog(server_id)
            targets = find_targets(catalog, require_all=False)
            result = build_json(targets, server_id)

            json_path = OUTPUT_DIR / (
                "channels.json" if server_id == 1 else f"channels_server_{server_id}.json"
            )
            outputs[json_path] = json.dumps(
                result, ensure_ascii=False, indent=2,
            ) + "\n"
            server_targets.append(targets)
            generated_count += len(result["channels"])

        outputs.update(build_category_playlists(server_targets))

        write_outputs_atomically(outputs)

        print(f"Wrote {generated_count} channel entries across both sources.")
        for path in outputs:
            print(f"Wrote {path}.")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
