#!/usr/bin/env bash
# Rebuilds the v0.3.1 adventure from its git tag in a temporary directory and checks the ROMs match the archive.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
git -C "$ROOT" archive v0.3.1 | tar -x -C "$WORK"
cd "$WORK"
uv sync --python 3.12 --quiet
make rom > /dev/null
diff release/SHA256SUMS "$ROOT/release/v0.3.1/SHA256SUMS"
echo "v0.3.1 REPRODUCED"
