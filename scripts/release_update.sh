#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <version> <private_key> [output_dir]"
  exit 1
fi

version="$1"
private_key="$2"
output_dir="${3:-dist}"

if [[ ! -f "VERSION" ]]; then
  echo "ERROR: VERSION file not found in repo root."
  exit 1
fi

current_version="$(cat VERSION | tr -d '[:space:]')"
if [[ "$current_version" != "$version" ]]; then
  echo "WARNING: VERSION ($current_version) does not match requested version ($version)."
  echo "         Update VERSION before releasing."
fi

if ! command -v minisign >/dev/null 2>&1; then
  echo "ERROR: minisign is not installed."
  exit 1
fi

mkdir -p "$output_dir"

tarball="update_${version}.tar.gz"
tarball_path="${output_dir}/${tarball}"
sig_path="${tarball_path}.minisig"
sha_path="${output_dir}/update_${version}.sha256"

echo "Creating tarball: ${tarball_path}"
git archive --format=tar --prefix=cindergrace_gui/ HEAD | gzip > "${tarball_path}"

echo "Signing tarball with minisign..."
minisign -S -m "${tarball_path}" -s "${private_key}"

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "${tarball_path}" > "${sha_path}"
elif command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "${tarball_path}" > "${sha_path}"
else
  echo "WARNING: No SHA256 tool found. Skipping checksum."
fi

echo "Release assets created:"
echo " - ${tarball_path}"
echo " - ${sig_path}"
if [[ -f "${sha_path}" ]]; then
  echo " - ${sha_path}"
fi
