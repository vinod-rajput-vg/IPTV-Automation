# IPTV Automation

Refreshes catalog IDs and constructs channel URLs for two configured channels.

## Schedule

GitHub Actions runs at 12:05 AM and 12:05 PM India Standard Time (IST):

- 18:35 UTC daily = 12:05 AM IST (next calendar day)
- 06:35 UTC daily = 12:05 PM IST

Run manually from **Actions → Refresh channel URLs → Run workflow**.

## Output

The workflow writes current catalog IDs and corresponding `play.php?id=...` URLs to `channels.json`, then commits the file only when it changes.

## Access behavior

The workflow fetches the catalog endpoint using a standard HTTP request. It does not simulate a browser session, bypass access restrictions, or resolve protected playback tokens.

If the catalog endpoint denies GitHub Actions' request, the run fails and leaves the previous `channels.json` unchanged. A successful request from a normal browser does not guarantee automated requests are accepted.

The generated URL is constructed from the catalog ID. This does not verify playback or token validity.
