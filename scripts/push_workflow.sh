#!/usr/bin/env bash
# Push GitHub Actions workflow (requires PAT with repo + workflow scopes).
set -euo pipefail
cd "$(dirname "$0")/.."

if ! git diff --quiet .github/workflows/build-windows.yml 2>/dev/null; then
  git add .github/workflows/build-windows.yml
  git commit -m "ci: add Windows EXE build workflow" || true
fi

echo "Pushing workflow to GitHub..."
echo "When prompted, use GitHub username and a Personal Access Token with repo + workflow scopes."
git remote set-url origin https://github.com/zyic0611/fapiao.git
git push origin main

echo "Done. Open Actions: https://github.com/zyic0611/fapiao/actions"
