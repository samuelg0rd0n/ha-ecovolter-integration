#!/usr/bin/env bash
# Set the "version" field in the integration's manifest.json to a new value.
#
# Uses a targeted sed replace (not `jq`) so the rest of the file's formatting
# (key order, inline arrays like "codeowners") is left byte-for-byte untouched.
#
# Usage: bump_manifest_version.sh <new_version> [manifest_path]

set -euo pipefail

new_version="${1:?usage: bump_manifest_version.sh <new_version> [manifest_path]}"
manifest="${2:-custom_components/ecovolter/manifest.json}"

if [[ ! -f "$manifest" ]]; then
  echo "error: manifest not found at $manifest" >&2
  exit 1
fi

old_version=$(grep -o '"version": *"[^"]*"' "$manifest" | sed -E 's/.*"([^"]+)"$/\1/')
if [[ -z "$old_version" ]]; then
  echo "error: no \"version\" field found in $manifest" >&2
  exit 1
fi

sed -i '' -E "s/\"version\": *\"[^\"]*\"/\"version\": \"${new_version}\"/" "$manifest"

echo "bumped $manifest: $old_version -> $new_version"
