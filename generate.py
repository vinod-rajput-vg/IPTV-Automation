#!/usr/bin/env python3
"""Build category TXT playlists from the public channel catalog.

Playback URLs point to the public play.php redirect endpoint. The generator
does not resolve redirects, imitate browser sessions, or bypass access controls.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://rkdy-linkgen.wasmer.app"
OUTPUT_DIR = Path("Output")

# Show the source server in category TXT channel names.
SHOW_SERVER_IN_TXT = False

# Channel metadata and category order are loaded from Sorted Channels/*.txt.
CATEGORY_DIR = Path("Sorted Channels")

# Workflow retries reuse complete server catalogs from this run-level cache.
CACHE_DIR = Path(os.environ.get("IPTV_RETRY_CACHE", ".retry-cache"))


def fetch_server_list() -> list[tuple[int, str]]:
    """Read server keys exposed by the website's public api.php endpoint."""
    request = Request(
        f"{BASE_URL}/api.php",
        headers={"Accept": "application/json", "User-Agent": "IPTV-Automation/1.0"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=20) as response:
            if response.status != 200:
                raise RuntimeError(f"Server list returned HTTP {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Server list unavailable (HTTP {exc.code}).") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach server list: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Server list response was not valid JSON.") from exc

    if not isinstance(payload, list) or not payload:
        raise RuntimeError("Server list must be a non-empty JSON array.")

    servers = []
    seen = set()
    for item in payload:
        if not isinstance(item, dict):
            raise RuntimeError("Each server entry must be a JSON object.")
        key = str(item.get("key", "")).strip()
        if not re.fullmatch(r"[0-9]+", key):
            raise RuntimeError(f"Invalid server key: {key!r}")
        server_id = int(key)
        if server_id <= 0:
            raise RuntimeError(f"Server key must be a positive integer: {key!r}")
        if server_id in seen:
            raise RuntimeError(f"Duplicate server key: {key}")
        seen.add(server_id)
        label = str(item.get("label", "")).strip() or f"Server {server_id}"
        servers.append((server_id, label))

    return servers


def fetch_catalog(server_id: int) -> list[dict]:
    """Fetch one server's public channel catalog."""
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
    if not payload:
        raise RuntimeError(
            f"Server {server_id} returned an empty catalog; preserving existing outputs."
        )

    return payload


def load_cached_catalog(server_id: int) -> list[dict] | None:
    """Load a previously completed server catalog from the retry cache."""
    cache_file = CACHE_DIR / f"server-{server_id}.json"
    if not cache_file.is_file():
        return None

    try:
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cache_file.unlink(missing_ok=True)
        return None

    if not isinstance(payload, list) or not payload or not all(
        isinstance(item, dict) for item in payload
    ):
        cache_file.unlink(missing_ok=True)
        return None

    print(f"Server {server_id}: reusing saved catalog ({len(payload)} channels).")
    return payload


def save_cached_catalog(server_id: int, catalog: list[dict]) -> None:
    """Atomically save a complete server catalog for the next retry."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    destination = CACHE_DIR / f"server-{server_id}.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(catalog, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(temporary, destination)


def ensure_server_channels_found(
    server_id: int,
    targets: list[tuple[str, dict, dict]],
    categories: dict[str, list[dict]],
) -> None:
    """Cache a server only after all channels assigned to it are present."""
    expected = {
        normalize_name(entry["key"])
        for entries in categories.values()
        for entry in entries
        if entry["server"] == server_id
    }
    found = {normalize_name(name) for name, _channel, _metadata in targets}
    missing = sorted(expected - found)
    if missing:
        raise RuntimeError(
            f"Server {server_id} catalog is incomplete; missing configured "
            f"channels: {', '.join(missing)}"
        )


def normalize_name(value: object) -> str:
    """Normalize channel names without changing meaningful punctuation."""
    return " ".join(str(value or "").split()).upper()


def load_category_files() -> dict[str, list[dict]]:
    """Load every category and channel entry from Sorted Channels/*.txt."""
    categories = {}
    seen_keys: dict[str, str] = {}
    seen_display_names: dict[str, str] = {}

    if not CATEGORY_DIR.is_dir():
        raise RuntimeError(f"Category directory not found: {CATEGORY_DIR}")

    for category_file in sorted(CATEGORY_DIR.glob("*.txt")):
        lines = [
            line.strip()
            for line in category_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if len(lines) % 3:
            raise ValueError(
                f"{category_file} must contain three non-empty lines per channel."
            )

        entries = []
        for index in range(0, len(lines), 3):
            header, display_name, logo = lines[index:index + 3]
            match = re.fullmatch(r'"(.+?)"\s+([0-9]+)', header)
            if not match:
                raise ValueError(
                    f"Invalid channel header in {category_file}: {header}"
                )

            catalog_name, server = match.groups()
            catalog_name = " ".join(catalog_name.split())
            server_id = int(server)
            if not catalog_name or server_id <= 0:
                raise ValueError(f"Invalid channel key or server in {category_file}: {header}")

            normalized_key = normalize_name(catalog_name)
            normalized_display = normalize_name(display_name)
            if normalized_key in seen_keys:
                raise ValueError(
                    f"Duplicate configured channel key {catalog_name!r} in "
                    f"{seen_keys[normalized_key]} and {category_file}."
                )
            if normalized_display in seen_display_names:
                raise ValueError(
                    f"Duplicate configured display name {display_name!r} in "
                    f"{seen_display_names[normalized_display]} and {category_file}."
                )
            seen_keys[normalized_key] = str(category_file)
            seen_display_names[normalized_display] = str(category_file)

            if not display_name:
                raise ValueError(
                    f"Missing display name in {category_file}: {header}"
                )
            if not re.fullmatch(r"https?://\S+", logo):
                raise ValueError(f"Invalid logo URL in {category_file}: {logo}")

            entries.append({
                "key": catalog_name,
                "server": server_id,
                "name": display_name,
                "logo": logo,
            })

        categories[category_file.stem] = entries

    if not categories:
        raise RuntimeError(f"No category TXT files found in {CATEGORY_DIR}")

    return categories


def find_targets(catalog: list[dict]) -> list[tuple[str, dict, dict]]:
    """Select catalog channels configured in Sorted Channels category files."""
    configured = {}
    for category_entries in load_category_files().values():
        for entry in category_entries:
            configured.setdefault(entry["key"], {
                "name": entry["name"],
                "logo": entry["logo"],
            })

    by_name = {}
    duplicates = set()
    configured_names = {normalize_name(key): key for key in configured}

    for channel in catalog:
        if not isinstance(channel, dict):
            continue
        name = normalize_name(channel.get("name", ""))
        configured_key = configured_names.get(name)
        if configured_key is None:
            continue
        if name in by_name:
            duplicates.add(configured_key)
            continue
        by_name[name] = channel

    if duplicates:
        raise RuntimeError(
            "Duplicate configured channel records found: "
            + ", ".join(sorted(duplicates))
        )

    result = []
    for catalog_name, metadata in configured.items():
        channel = by_name.get(normalize_name(catalog_name))
        if channel is None:
            continue
        channel_id = str(channel.get("id", "")).strip()
        if not channel_id or any(character.isspace() for character in channel_id):
            raise RuntimeError(f"{metadata['name']} has an invalid catalog ID.")
        result.append((catalog_name, channel, metadata))

    return result


def build_stream_url(channel_id: str, server_id: int) -> str:
    return f"{BASE_URL}/play.php?{urlencode({'s': server_id, 'id': channel_id})}"


def ensure_all_configured_channels_found(
    server_targets: dict[int, list[tuple[str, dict, dict]]],
) -> list[str]:
    """Report configured channels missing from their assigned server catalog."""
    found_by_server = {
        server_id: {
            normalize_name(catalog_name)
            for catalog_name, _channel, _metadata in targets
        }
        for server_id, targets in server_targets.items()
    }
    missing = []
    for entries in load_category_files().values():
        for entry in entries:
            key = normalize_name(entry["key"])
            if key not in found_by_server.get(entry["server"], set()):
                missing.append(
                    f"{entry['name']} (Server {entry['server']})"
                )

    if missing:
        details = ", ".join(sorted(set(missing)))
        raise RuntimeError(
            "Refusing to overwrite generated files because configured channels "
            f"are missing from their assigned server catalogs: {details}"
        )

    return missing


def build_category_playlists(
    server_targets: dict[int, list[tuple[str, dict, dict]]],
) -> dict[Path, str]:
    """Generate playlists using only each channel's explicitly assigned server."""
    targets_by_server = {
        server_id: {
            catalog_name: (channel, metadata)
            for catalog_name, channel, metadata in targets
        }
        for server_id, targets in server_targets.items()
    }

    playlists = {}
    categories = load_category_files()
    available_server_ids = set(server_targets)

    for category, category_entries in categories.items():
        destination = OUTPUT_DIR / f"{category}.txt"
        previous_entries = {}
        if destination.is_file():
            previous_blocks = destination.read_text(encoding="utf-8").strip().split("\n\n")
            for block in previous_blocks:
                lines = block.splitlines()
                if len(lines) == 3:
                    previous_entries[normalize_name(lines[0])] = block

        entries = []
        seen_names: set[str] = set()

        for category_entry in category_entries:
            catalog_name = category_entry["key"]
            preferred_server = category_entry["server"]
            channel_name = category_entry["name"]
            normalized_name = normalize_name(channel_name)
            if normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)

            selected = targets_by_server.get(preferred_server, {}).get(catalog_name)
            if selected is None:
                # A failed server must not remove its last published channel URL.
                # Keep the existing entry until that server returns successfully.
                if preferred_server not in available_server_ids:
                    old_display_name = (
                        f"{channel_name} (Server {preferred_server})"
                        if SHOW_SERVER_IN_TXT else channel_name
                    )
                    previous = previous_entries.get(normalize_name(old_display_name))
                    if previous:
                        entries.append(previous)
                continue

            channel, _metadata = selected
            channel_id = str(channel["id"]).strip()
            stream_url = build_stream_url(channel_id, preferred_server)
            display_name = (
                f"{channel_name} (Server {preferred_server})"
                if SHOW_SERVER_IN_TXT else channel_name
            )
            entries.append(
                f"{display_name}\n{category_entry['logo']}\n{stream_url}"
            )

        if entries:
            playlists[destination] = "\n\n".join(entries) + "\n"

    return playlists


def build_server_files(server_catalogs: dict[int, list[dict]]) -> dict[Path, str]:
    """Generate a current server_N.txt catalog for every successfully loaded server."""
    outputs = {}

    for server_id, catalog in server_catalogs.items():
        entries = []
        seen_names = set()

        for channel in catalog:
            if not isinstance(channel, dict):
                continue

            name = " ".join(str(channel.get("name", "")).split())
            if not name or any(char in name for char in '\\r\\n"'):
                continue

            normalized = normalize_name(name)
            if normalized in seen_names:
                continue

            seen_names.add(normalized)
            entries.append(f'"{normalized}" {server_id}\\n{name}')

        if entries:
            outputs[Path("Servers") / f"server_{server_id}.txt"] = (
                "\\n\\n".join(entries) + "\\n\\n"
            )

    return outputs


def write_outputs_atomically(outputs: dict[Path, str]) -> None:
    """Stage every output, then atomically replace each destination file.

    The replacement of an individual file is atomic; the complete set of files
    is not a single filesystem transaction.
    """
    for destination in outputs:
        destination.parent.mkdir(parents=True, exist_ok=True)

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
        server_targets = {}
        server_catalogs = {}
        categories = load_category_files()
        required_server_ids = {
            entry["server"]
            for category_entries in categories.values()
            for entry in category_entries
        }

        servers = fetch_server_list()
        available_server_ids = {server_id for server_id, _label in servers}
        missing_servers = required_server_ids - available_server_ids
        if missing_servers:
            ids = ", ".join(str(server_id) for server_id in sorted(missing_servers))
            raise RuntimeError(
                f"Category configuration references server IDs not advertised by "
                f"the catalog API: {ids}"
            )

        required_servers = [
            (server_id, server_label)
            for server_id, server_label in servers
            if server_id in required_server_ids
        ]

        def load_server(server_id: int, server_label: str):
            # Each required server is fetched independently and concurrently.
            # A successful complete catalog is cached even if another server
            # fails, so the next retry only needs to fetch the failed server.
            catalog = load_cached_catalog(server_id)
            from_cache = catalog is not None
            if catalog is None:
                catalog = fetch_catalog(server_id)

            targets = find_targets(catalog)
            ensure_server_channels_found(server_id, targets, categories)
            if not from_cache:
                save_cached_catalog(server_id, catalog)

            return server_id, server_label, catalog, targets

        errors = []
        with ThreadPoolExecutor(max_workers=max(1, len(required_servers))) as executor:
            futures = {
                executor.submit(load_server, server_id, server_label): server_id
                for server_id, server_label in required_servers
            }
            for future in as_completed(futures):
                server_id = futures[future]
                try:
                    loaded_id, server_label, catalog, targets = future.result()
                    server_catalogs[loaded_id] = catalog
                    server_targets[loaded_id] = targets
                    print(f"{server_label}: loaded {len(catalog)} channels.")
                except Exception as exc:
                    errors.append(f"Server {server_id}: {exc}")

        # Publish successful servers immediately. For failed servers, retain
        # their previous playlist entries and retry them in the workflow loop.
        outputs = build_server_files(server_catalogs)
        outputs.update(build_category_playlists(server_targets))
        write_outputs_atomically(outputs)

        print(f"Discovered {len(servers)} servers.")
        for path in outputs:
            print(f"Wrote {path}.")

        if errors:
            print(
                "Some servers are still unavailable; successful server updates "
                "were saved and failed servers will be retried: "
                + " | ".join(sorted(errors)),
                file=sys.stderr,
            )
            return 1

        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
