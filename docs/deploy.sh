#!/bin/bash
set -euo pipefail

# Publish the VitePress site, including the cookbook, to GitHub Pages.
# gh-pages is replaced on each run because the branch holds only the built site.

if [ -f ".vitepress/config.ts" ]; then
  ROOT="."
  DIST_DIR=".vitepress/dist"
elif [ -f "docs/.vitepress/config.ts" ]; then
  ROOT="docs"
  DIST_DIR="docs/.vitepress/dist"
else
  echo "Run this from the repository root or the docs directory." >&2
  exit 1
fi

echo "Building site from ${ROOT}..."
npm --prefix "$ROOT" install
npm --prefix "$ROOT" run docs:build

cd "$DIST_DIR"
touch .nojekyll
git init
git add -A
git commit -m "Deploy docs $(date '+%Y-%m-%d %H:%M:%S')"
git push -f git@github.com:IBM/mcp-composer.git HEAD:gh-pages
cd - >/dev/null
rm -rf "$DIST_DIR/.git"

echo "Deployed to: https://ibm.github.io/mcp-composer/"
