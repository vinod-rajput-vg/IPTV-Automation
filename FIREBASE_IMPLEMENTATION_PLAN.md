# Firebase + Vercel implementation plan

Status: preparation only. No Firebase project has been provisioned, no secrets have been created, and no production deployment has been performed.

## 1. Confirmed decisions

- Repository: `vinod-rajput-vg/IPTV-Automation`
- Work branch: `feat/firebase-automation-foundation`
- Firebase project: a new, dedicated project for IPTV-Automation (project ID is not assigned yet).
- Automation: Firebase Cloud Functions for Python.
- Schedule: `10 0,12,18 * * *`, timezone `Asia/Kolkata` (00:10, 12:10, 18:10 IST).
- Primary catalog delivery: Firebase Storage.
- Fallback catalog delivery: GitHub repository `Output/` on `main`.
- Admin hosting: Vercel.
- GitHub Actions: retained as a manual/backup path and PR validation, not as a second scheduled publisher after cutover.
- Existing catalog output names and formats must remain compatible until the Android app integration is verified.

## 2. Target architecture

1. Cloud Scheduler invokes one scheduled Python function three times daily.
2. The function obtains the channel configuration from the repository's `Sorted Channels/` files and fetches the two source catalogs.
3. The existing generator logic produces `channels.json`, `channels_server_2.json`, and the category TXT playlists.
4. A validation stage checks schema, required fields, duplicate IDs/names, configured-channel coverage, URL structure, and non-empty outputs.
5. The function assigns a publication version and computes SHA-256 checksums.
6. It uploads immutable versioned files to Firebase Storage.
7. It publishes the same generated files to GitHub `Output/` in one Git commit using the Git Data API (blobs, tree, commit, ref update).
8. Firestore records the run and each destination's status. The Firebase active manifest is advanced only after the Firebase upload is complete and validated. GitHub mirror failures are recorded as pending and retried; they must not cause a partially written Firebase catalog to become active.
9. Android reads and validates the Firebase manifest/catalog first, then tries the GitHub fallback, then uses its last-known-good local cache.

The Firebase and GitHub outputs must be generated from the same in-memory output set. Do not independently run the generator for each destination.

## 3. Storage layout and manifest contract

Suggested Firebase Storage layout:

```
catalog/
  versions/
    <version>/
      channels.json
      channels_server_2.json
      drama.txt
      entertainment.txt
      infotainment.txt
      kids.txt
      news.txt
      manifest.json
  current/
    manifest.json
```

The version manifest should contain:
- `version`: immutable publication identifier
- `generated_at`: ISO-8601 timestamp with timezone
- `source_revision`: Git commit SHA for the configuration used
- `files`: relative path, byte size, SHA-256, and content type for every output
- `channel_counts`: counts by catalog/category
- `validation`: successful validation summary

The current manifest is the small pointer Android checks first. Publish it last, after every versioned file has uploaded successfully. The existing JSON schema and TXT formatting remain unchanged.

GitHub keeps the current compatibility paths in `Output/` and adds `Output/manifest.json`. A Git tree/commit publishes the complete output set as one commit so clients do not observe a sequence of per-file updates.

## 4. Firestore data model

Suggested collections:

- `automationRuns/{runId}`: trigger type, scheduled time, start/end timestamps, status, version, channel counts, validation summary, error details, and destination statuses.
- `catalogState/current`: active Firebase version, last successful generation, GitHub mirror version/status, and last-known-good version.
- `automationLocks/catalogRefresh`: lease owner, lease expiry, and run ID.

Use a Firestore transaction to acquire/renew/release the lock. Use a stable idempotency key derived from the scheduler job name and scheduled execution time. Never hold a transaction open while fetching catalogs or uploading files.

## 5. Failure and retry policy

- Source fetch or validation failure: do not publish; keep the previous active Firebase manifest and GitHub output.
- Firebase version upload failure: do not advance the Firebase current manifest.
- GitHub publication failure after Firebase publication: keep Firebase active, record GitHub as pending, and retry the mirror from the immutable Firebase version snapshot.
- Partial GitHub writes: avoid Contents API per-file commits; use one Git Data API tree/commit and update the branch ref only after the commit is ready.
- Concurrent or duplicate invocation: reject/skip while a valid lock exists; use idempotency to avoid duplicate publications.
- Both remote sources unavailable on Android: use last-known-good local catalog without interrupting current playback.
- Do not equate a syntactically valid playback URL with a playable stream. Stream availability checks must be reported separately from catalog generation.

## 6. Security boundaries

- Use a dedicated Firebase project; do not put its project ID or credentials into source until the project is created and confirmed.
- Use Cloud Functions Application Default Credentials for Firebase Admin SDK access.
- Store the GitHub fine-grained token as a Firebase Functions secret. Limit it to the one repository and required Contents read/write permission. Never expose it to Vercel browser code or Android.
- Vercel server-side API routes may call authenticated Firebase endpoints; validate Firebase ID tokens and enforce a single-admin allowlist/custom claim.
- Firebase Storage read access should expose only the published catalog paths needed by the Android client. Keep run metadata, locks, and admin data private.
- Do not commit service-account JSON, API tokens, signing keys, or real environment files.
- Add rate limiting and authorization to manual run endpoints.

## 7. Vercel admin panel scope

Initial admin screens:
- Overview: last successful run, next scheduled run, catalog version, counts, and Firebase/GitHub publishing health.
- Channels: view configured channel/category metadata.
- Automation: authorized manual run and run history.
- Output: inspect current manifest and published file versions.
- Settings: read/update only explicitly supported safe configuration.

Vercel hosts the UI and server-side API. Firebase owns the scheduled generator and publication state. Avoid adding a second Vercel cron for the same job.

## 8. GitHub Actions transition

Before Firebase is verified, keep the existing schedule unchanged. The currently inspected workflow runs at 18:40, 06:40, and 12:40 UTC, equivalent to 00:10, 12:10, and 18:10 IST.

After Firebase has passed deployment and end-to-end tests:
- remove the GitHub Actions schedule trigger (or disable scheduled runs),
- retain `workflow_dispatch` for manual recovery,
- retain pull-request syntax/validation checks,
- ensure backup execution uses the same generator and validation rules,
- prevent backup and Firebase from publishing concurrently.

Do not disable the existing schedule during initial preparation.

## 9. Implementation sequence

1. Refactor the generator into a pure generation stage that returns a complete output mapping; preserve a CLI wrapper for the current GitHub Actions workflow.
2. Add tests for category parsing, duplicate detection, missing configured channels, output schemas, checksums, and unchanged legacy formatting.
3. Implement Firebase Storage version publishing and current-manifest promotion.
4. Implement GitHub batch publisher and retry-from-snapshot path.
5. Implement Firestore run records, lock lease, idempotency, and status reporting.
6. Add the scheduled Python function with the exact timezone and schedule above.
7. Deploy to the new Firebase project and run a manual dry-run before enabling the schedule.
8. Integrate Vercel authentication/dashboard.
9. Update the Android app to use Firebase-first, GitHub-second, local-cache-last catalog resolution.
10. Run end-to-end tests, observe several scheduled executions, then perform the GitHub Actions schedule cutover.

## 10. External setup still required

The project owner must create the dedicated Firebase project and provide/confirm its non-secret project ID. The following setup must then be completed in that project: Blaze billing, Cloud Functions and Cloud Scheduler APIs, Cloud Storage bucket, Firestore database, Authentication, and least-privilege service identities.

Vercel project/team selection and the Android app repository are also not yet connected to this implementation branch. The Android repository must be inspected before changing its catalog loader; do not assume its current URL parsing or cache behavior.
