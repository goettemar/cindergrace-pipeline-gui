# Operations Handbook

This document captures day-to-day operational workflows used by the team.

## Release Management (Updater Assets)

The GUI updater installs release assets, not the git repository. Each release
must publish signed assets for verification.

Assets to upload to the GitHub Release:
- `update_<version>.tar.gz`
- `update_<version>.tar.gz.minisig`
- `update_<version>.sha256` (optional)

### Release Checklist

1) Bump version:
   - Update `VERSION`
   - Update `CHANGELOG.md` (if used)
2) Create/update git tag:
```bash
git tag v<version>
git push origin v<version>
```
3) Build signed assets:
```bash
./scripts/release_update.sh <version> /path/to/private.key dist
```
4) Create GitHub Release:
   - Title: `v<version>`
   - Notes: key changes + migration notes
5) Upload assets:
   - `dist/update_<version>.tar.gz`
   - `dist/update_<version>.tar.gz.minisig`
   - `dist/update_<version>.sha256` (optional)
6) Smoke test updater:
   - Open GUI → Updates tab
   - Check for updates → download/apply
   - Verify version in UI

### One-Command Build (Recommended)

Use the helper script:
```bash
./scripts/release_update.sh <version> <private_key> [output_dir]
```

Example:
```bash
./scripts/release_update.sh 0.6.1 /home/zorinadmin/cindergrace_update.key dist
```

### Manual Build (Fallback)

1) Update `VERSION` to the new release number.
2) Create the tarball:
```bash
git archive --format=tar --prefix=cindergrace_gui/ HEAD | gzip > update_<version>.tar.gz
```
3) Sign:
```bash
minisign -S -m update_<version>.tar.gz -s <private_key>
```
4) Optional checksum:
```bash
sha256sum update_<version>.tar.gz > update_<version>.sha256
```
5) Upload the assets to the GitHub Release tagged `v<version>`.

The public key used by the app is pinned at `config/update_public_key.pub`.

## Test Management (Quick Guide)

Recommended minimal checks before a release:
1) Unit tests:
```bash
pytest -q
```
2) Smoke check (no ComfyUI ping):
```bash
python scripts/smoke_test.py --ping
```
3) If update changes landed, verify the update flow via the GUI:
   - Check for updates.
   - Download + apply.
   - Verify version bump and startup.

## Key Material

- Keep the minisign private key offline and backed up.
- Only the public key should live in the repo.
