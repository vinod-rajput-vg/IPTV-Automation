#!/usr/bin/env python3
"""Build server JSON catalogs and category TXT playlists from the public catalog.

Playback URLs are resolved by following the public play.php HTTP redirect.
This does not imitate browser sessions or bypass access controls.
"""

from __future__ import annotations

import json
import re
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE_URL = "https://rkdy-linkgen.wasmer.app"
OUTPUT_DIR = Path("Output")

# Show the source server in category TXT channel names.
SHOW_SERVER_IN_TXT = False

# Channel metadata and category order are loaded from Sorted Channels/*.txt.
CATEGORY_DIR = Path("Sorted Channels")

# Stream validation uses response headers only; it does not download or play media.
STREAM_TIMEOUT = 7
VALIDATION_ATTEMPTS = 4
VALIDATION_RETRY_BASE_SECONDS = 5
VALIDATION_RETRY_MAX_SECONDS = 20
# Keep requests gentle on the public endpoint; high concurrency can trigger HTTP 5xx.
VALIDATION_WORKERS = 8
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
        if server_id in seen:
            raise RuntimeError(f"Duplicate server key: {key}")
        seen.add(server_id)
        servers.append((server_id, str(item.get("label", "")).strip() or f"Server {server_id}"))
    return servers


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


def build_stream_url(channel_id: str) -> str:
    return f"{BASE_URL}/play.php?{urlencode({'id': channel_id})}"


class StreamValidationError(RuntimeError):
    """A stream validation failure with reportable HTTP and redirect details."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        final_url: str | None = None,
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.final_url = final_url
        self.retryable = retryable


class PermanentStreamError(StreamValidationError):
    """An HTTP response indicating that retrying the same endpoint is not useful."""


def validate_stream_url(url: str) -> dict:
    """Check response headers and return the final redirect and response details."""
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.apple.mpegurl, application/x-mpegURL, "
            "audio/*, video/*, application/octet-stream, */*",
            "User-Agent": "IPTV-Automation/1.0",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=STREAM_TIMEOUT) as response:
            status = getattr(response, "status", response.getcode())
            final_url = response.geturl()
            if not 200 <= status < 300:
                raise StreamValidationError(
                    f"HTTP {status}", status=status, final_url=final_url,
                )
            if urlsplit(final_url).scheme not in ("http", "https"):
                raise StreamValidationError(
                    "Redirect did not resolve to HTTP(S)",
                    status=status,
                    final_url=final_url,
                )

            content_type = response.headers.get_content_type().lower()
            if content_type in ("text/html", "application/json", "application/problem+json"):
                raise StreamValidationError(
                    f"Unexpected response type: {content_type}",
                    status=status,
                    final_url=final_url,
                )
            return {
                "status": status,
                "final_url": final_url,
                "content_type": content_type,
            }
    except HTTPError as exc:
        message = f"HTTP {exc.code}"
        details = {
            "status": exc.code,
            "final_url": exc.geturl() or url,
        }
        if exc.code in (400, 401, 403, 404, 410):
            raise PermanentStreamError(
                f"{message} (non-retryable)", **details, retryable=False,
            ) from exc
        raise StreamValidationError(message, **details) from exc
    except URLError as exc:
        raise StreamValidationError(f"Connection failed: {exc.reason}") from exc


def write_validation_report(
    streams: dict[str, str],
    validated: dict[str, dict],
    failures: dict[str, tuple[str, dict]],
    attempts: int,
) -> None:
    """Persist validation diagnostics separately from generated playlists."""
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "result": "passed" if not failures else "failed",
        "total_streams": len(streams),
        "validated_streams": len(validated),
        "failed_streams": len(failures),
        "attempts": attempts,
        "failures": [
            {
                "channel": name,
                "requested_url": url,
                **details,
            }
            for url, (name, details) in sorted(failures.items(), key=lambda item: item[1][0])
        ],
    }
    report_path = OUTPUT_DIR / "stream-validation-report.json"
    write_outputs_atomically({
        report_path: json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    })
    print(f"Wrote validation diagnostics to {report_path}.")


def validate_streams(server_targets: dict[int, list[tuple[str, dict, dict]]]) -> set[str]:
    """Retry failed streams and return the endpoints that passed validation."""
    streams = {}
    for targets in server_targets.values():
        for catalog_name, channel, metadata in targets:
            channel_id = str(channel["id"]).strip()
            url = build_stream_url(channel_id)
            streams.setdefault(url, metadata["name"])

    if not streams:
        raise RuntimeError("No configured streams were found to validate.")

    pending = dict(streams)
    permanent = {}
    validated = {}
    attempts_used = 0
    failed = {}
    for attempt in range(1, VALIDATION_ATTEMPTS + 1):
        attempts_used = attempt
        failed = {}
        newly_permanent = {}
        with ThreadPoolExecutor(max_workers=VALIDATION_WORKERS) as executor:
            futures = {
                executor.submit(validate_stream_url, url): (url, name)
                for url, name in pending.items()
            }
            for future in as_completed(futures):
                url, name = futures[future]
                try:
                    validated[url] = future.result()
                except StreamValidationError as exc:
                    details = {
                        "status": exc.status,
                        "final_url": exc.final_url,
                        "error": str(exc),
                        "retryable": exc.retryable,
                    }
                    if exc.retryable:
                        failed[url] = (name, details)
                    else:
                        newly_permanent[url] = (name, details)
                except Exception as exc:
                    failed[url] = (name, {
                        "status": None,
                        "final_url": None,
                        "error": str(exc),
                        "retryable": True,
                    })

        permanent.update(newly_permanent)
        passed = len(pending) - len(failed) - len(newly_permanent)
        print(
            f"Stream validation attempt {attempt}/{VALIDATION_ATTEMPTS}: "
            f"{passed}/{len(pending)} passed; "
            f"{len(newly_permanent)} non-retryable."
        )
        if not failed and not permanent:
            write_validation_report(streams, validated, {}, attempts_used)
            write_validation_report(streams, validated, {}, attempts_used)
            print(f"Validated all {len(streams)} unique configured stream endpoints.")
            return set(validated)

        for name, details in newly_permanent.values():
            print(f"Stream rejected: {name} ({details['error']})")
        for name, details in failed.values():
            print(f"Stream temporarily unavailable: {name} ({details['error']})")

        pending = {url: name for url, (name, _details) in failed.items()}
        if not pending:
            break
        if attempt < VALIDATION_ATTEMPTS:
            delay = min(
                VALIDATION_RETRY_BASE_SECONDS * (2 ** (attempt - 1)),
                VALIDATION_RETRY_MAX_SECONDS,
            )
            print(f"Retrying {len(pending)} temporary failures in {delay} seconds.")
            time.sleep(delay)

    remaining = {**permanent, **failed}
    write_validation_report(streams, validated, remaining, attempts_used)
    failed_names = ", ".join(sorted({name for name, _details in remaining.values()}))
    print(
        f"Validation finished: {len(validated)}/{len(streams)} streams passed; "
        f"{len(remaining)} failed after {attempts_used} attempts: {failed_names}."
    )
    return set(validated)


def ensure_all_configured_channels_found(
    server_targets: dict[int, list[tuple[str, dict, dict]]],
) -> None:
    configured = {
        normalize_name(entry["key"]): entry["name"]
        for entries in load_category_files().values()
        for entry in entries
    }
    found = {
        normalize_name(catalog_name)
        for targets in server_targets.values()
        for catalog_name, _channel, _metadata in targets
    }
    missing = sorted(name for key, name in configured.items() if key not in found)
    if missing:
        raise RuntimeError(
            "Configured channels missing from every discovered server: "
            + ", ".join(missing)
        )


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
                "url": build_stream_url(channel_id),
            }
        )

    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(ZoneInfo("Asia/Kolkata"))

    return {
        "updated_at": now_ist.isoformat(timespec="seconds"),
        "source": f"{BASE_URL}/api.php?server={server_id}",
        "channels": channels,
    }


def load_category_files() -> dict[str, list[dict]]:
    """Load every category and channel entry from Sorted Channels/*.txt."""
    categories = {}

    if not CATEGORY_DIR.is_dir():
        raise RuntimeError(f"Category directory not found: {CATEGORY_DIR}")

    for category_file in sorted(CATEGORY_DIR.glob("*.txt")):
        lines = [line.strip() for line in category_file.read_text(encoding="utf-8").splitlines() if line.strip()]
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
                    f'Invalid channel header in {category_file}: {header}'
                )

            catalog_name, server = match.groups()
            catalog_name = " ".join(catalog_name.split())
            if not display_name:
                raise ValueError(f"Missing display name in {category_file}: {header}")
            if not re.fullmatch(r"https?://\S+", logo):
                raise ValueError(f"Invalid logo URL in {category_file}: {logo}")

            entries.append({
                "key": catalog_name,
                "server": int(server),
                "name": display_name,
                "logo": logo,
            })

        categories[category_file.stem] = entries

    return categories


def build_category_playlists(
    server_targets: dict[int, list[tuple[str, dict, dict]]],
) -> dict[Path, str]:
    """Generate playlists, preferring the configured server then available fallbacks."""
    targets_by_server = {
        server_id: {
            catalog_name: (channel, metadata)
            for catalog_name, channel, metadata in targets
        }
        for server_id, targets in server_targets.items()
    }

    playlists = {}
    for category, category_entries in load_category_files().items():
        entries = []
        seen_names: set[str] = set()

        for category_entry in category_entries:
            catalog_name = category_entry["key"]
            preferred_server = category_entry["server"]
            server_order = [preferred_server] + [
                candidate_id for candidate_id in sorted(targets_by_server)
                if candidate_id != preferred_server
            ]
            selected = None
            server_id = preferred_server
            for candidate_id in server_order:
                candidate = targets_by_server[candidate_id].get(catalog_name)
                if candidate is not None:
                    selected = candidate
                    server_id = candidate_id
                    break
            if selected is None:
                continue

            channel, _metadata = selected
            normalized_name = normalize_name(category_entry["name"])
            if normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)

            channel_id = str(channel["id"]).strip()
            stream_url = build_stream_url(channel_id)
            channel_name = category_entry["name"]
            channel_logo = category_entry["logo"]
            display_name = (
                f"{channel_name} (Server {server_id})"
                if SHOW_SERVER_IN_TXT else channel_name
            )
            entries.append(f"{display_name}\n{channel_logo}\n{stream_url}")

        playlists[OUTPUT_DIR / f"{category}.txt"] = (
            "\n\n".join(entries) + ("\n" if entries else "")
        )

    return playlists


def build_server_files(server_catalogs: dict[int, list[dict]]) -> dict[Path, str]:
    """Generate server_N.txt files for newly discovered servers; preserve files 1 and 2."""
    outputs = {}
    for server_id, catalog in server_catalogs.items():
        if server_id in (1, 2):
            continue
        entries = []
        seen_names = set()
        for channel in catalog:
            if not isinstance(channel, dict):
                continue
            name = " ".join(str(channel.get("name", "")).split())
            if not name or any(char in name for char in '\r\n"'):
                continue
            normalized = normalize_name(name)
            if normalized in seen_names:
                continue
            seen_names.add(normalized)
            entries.append(f'"{normalized}" {server_id}\n{name}')
        if entries:
            outputs[Path("Servers") / f"server_{server_id}.txt"] = "\n\n".join(entries) + "\n\n"
    return outputs


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
        server_targets = {}
        server_catalogs = {}

        servers = fetch_server_list()
        for server_id, server_label in servers:
            catalog = fetch_catalog(server_id)
            server_catalogs[server_id] = catalog
            server_targets[server_id] = find_targets(catalog)

        ensure_all_configured_channels_found(server_targets)
        validated_urls = validate_streams(server_targets)

        # Publish only channels whose stream endpoints passed validation.
        working_targets = {}
        total_count = sum(len(targets) for targets in server_targets.values())
        generated_count = 0
        for server_id, targets in server_targets.items():
            working = [
                target for target in targets
                if build_stream_url(str(target[1]["id"]).strip()) in validated_urls
            ]
            working_targets[server_id] = working
            result = build_json(working, server_id)
            json_path = OUTPUT_DIR / (
                "channels.json" if server_id == 1 else f"channels_server_{server_id}.json"
            )
            outputs[json_path] = json.dumps(
                result, ensure_ascii=False, indent=2,
            ) + "\n"
            generated_count += len(result["channels"])

        outputs.update(build_server_files(server_catalogs))
        outputs.update(build_category_playlists(working_targets))
        write_outputs_atomically(outputs)

        skipped_count = total_count - generated_count
        print(
            f"Discovered {len(servers)} servers. Wrote {generated_count} "
            f"validated configured channel entries; skipped {skipped_count} failed entries."
        )
        for path in outputs:
            print(f"Wrote {path}.")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
