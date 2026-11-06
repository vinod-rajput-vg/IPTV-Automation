# Firebase Functions implementation

This directory is reserved for the Firebase Python Functions runtime.

The scheduled function is intentionally not enabled in this preparation commit. Before adding it, the generator must expose a side-effect-free API that returns all generated files as a mapping. The function can then publish that exact mapping to Firebase Storage and GitHub without generating two different snapshots.

Confirmed scheduler configuration:

- Cron: `10 0,12,18 * * *`
- Timezone: `Asia/Kolkata`
- Runtime target: Python 3.12 (verify current Firebase CLI/runtime support during deployment)

Required runtime responsibilities:

1. Acquire a Firestore lease/idempotency key.
2. Load category configuration and fetch source catalogs.
3. Generate and validate all output files.
4. Upload immutable Firebase Storage version files.
5. Publish the matching GitHub Output tree/commit.
6. Promote the Firebase current manifest only after its version files validate.
7. Record destination statuses and release the lease.

Use Application Default Credentials in Google Cloud. Inject the GitHub token through Firebase Functions Secret Manager; never add secrets to this directory or repository.

See `FIREBASE_IMPLEMENTATION_PLAN.md` for the full contract, failure handling, data model, security boundaries, and rollout plan.
