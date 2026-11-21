# IPTV Automation

A Python automation script that reads the configured public channel catalog, matches channels listed in `Sorted Channels/`, validates generated playback endpoints, and writes category playlists.

## Requirements

- Python 3.12 or newer
- Network access to the configured public catalog and playback endpoints

The project uses only Python standard-library modules; no pip installation is required.

## Run locally

```bash
python -m py_compile generate.py
python -m unittest discover -s tests -v
python generate.py
```

## Configuration

Each `Sorted Channels/*.txt` file contains channel records in three non-empty lines:

1. Catalog channel name and preferred server ID, for example `"CHANNEL NAME" 1`
2. Display name used in the playlist
3. HTTP(S) logo URL

The parser rejects malformed records and duplicate catalog keys across category files.

## Output

- `Output/*.txt`: category playlists, containing only endpoints that passed HTTP validation
- `Output/stream-validation-report.json`: validation totals and failure diagnostics
- `Servers/server_N.txt`: discovered channel catalog entries for servers other than 1 and 2

If no configured stream passes validation, generation stops and leaves the existing playlists untouched. If a channel is unavailable on its preferred server, the generator can use another configured server copy only when that endpoint validates successfully.

## Automation

GitHub Actions runs the refresh workflow twice daily and supports manual runs. Pull requests run syntax checks and unit tests with read-only repository permissions; they do not run the live catalog generator or receive write permissions.

## Notes

- Stream checks follow the public playback endpoint's HTTP redirect and inspect response metadata; they do not download or play the media body.
- A successful HTTP response is only an availability signal at validation time. It does not guarantee continuous playback or future availability.
- The catalog and playback endpoint are external dependencies and can change independently of this repository.
