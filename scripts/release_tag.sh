#!/usr/bin/env bash
set -euo pipefail

# Create and push a release tag for reproducible deploy/rollback.
# Usage:
#   ./scripts/release_tag.sh
#   ./scripts/release_tag.sh v2026.04.25-ops

TAG="${1:-v$(date +%Y.%m.%d-%H%M)}"

git rev-parse --is-inside-work-tree >/dev/null
git diff --quiet || { echo "working tree has changes; commit first"; exit 1; }
git diff --cached --quiet || { echo "staged changes exist; commit first"; exit 1; }

git tag -a "${TAG}" -m "release ${TAG}"
git push origin "${TAG}"
echo "created and pushed tag: ${TAG}"

